"""审计外送(P1-04): syslog(RFC5424) / webhook 双通道 + S3/WORM 接口抽象。

设计要点:
- 不阻塞主请求: 审计记录先入内存有界队列, 后台 worker 批量发送。
- 失败缓冲重试: 单批发送失败按指数退避重试, 最终失败写入死信文件
  (可选)并计数, 绝不向调用方抛异常。
- 显式降级: S3/WORM 在无 boto3 环境下 send 时抛出
  :class:`AuditExportUnavailable`(配置占位, 见报告说明), 不静默假成功。

接线说明(集成波): ``AuditShipper`` 生命周期挂在 FastAPI lifespan
(start/stop); 审计记录入口在 ``AuditStore.record`` 或中间件之后调用
``shipper.enqueue(record.model_dump(mode="json"))``。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import socket
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from hmac import new as hmac_new
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AuditExportUnavailable(RuntimeError):
    """外送通道所需依赖未安装/未配置时的显式降级错误。"""


# ---------------------------------------------------------------------------
# RFC5424 格式化
# ---------------------------------------------------------------------------


class RFC5424Formatter:
    """把审计记录格式化为 RFC5424 syslog 消息。

    消息形态::

        <PRI>1 TIMESTAMP HOSTNAME APP-NAME PROCID MSGID [SD] MSG

    其中 SD 使用私有 enterprise number 占位(32473 为 IANA 文档示例号,
    商用部署应替换为自有 PEN); MSG 为记录 JSON(UTF-8)。
    """

    ENTERPRISE_ID = 32473  # IANA 私有企业号占位(文档示例); 部署时替换

    # facility 13 = log audit; severity 依 outcome 映射
    _SEVERITY_BY_OUTCOME: ClassVar[dict[str, int]] = {
        "success": 6,   # informational
        "partial": 5,   # notice
        "failure": 4,   # warning
        "denied": 4,    # warning
        "error": 3,     # err
    }

    def __init__(
        self,
        *,
        hostname: str | None = None,
        app_name: str = "xagent",
        proc_id: str = "-",
        facility: int = 13,
    ) -> None:
        self.hostname = hostname or socket.gethostname()
        self.app_name = app_name
        self.proc_id = proc_id
        self.facility = facility

    def severity_for(self, record: dict[str, Any]) -> int:
        return self._SEVERITY_BY_OUTCOME.get(str(record.get("outcome", "success")), 6)

    @staticmethod
    def _escape_sd(value: Any) -> str:
        return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("]", "\\]")

    @staticmethod
    def _format_timestamp(raw: Any) -> str:
        if isinstance(raw, datetime):
            ts = raw
        else:
            try:
                ts = datetime.fromisoformat(str(raw))
            except ValueError:
                ts = datetime.now(UTC)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return ts.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    def format(self, record: dict[str, Any]) -> str:
        severity = self.severity_for(record)
        pri = self.facility * 8 + severity
        timestamp = self._format_timestamp(record.get("created_at") or record.get("timestamp"))
        msg_id = self._escape_sd(record.get("action") or "-")

        sd_fields = {
            "tenant": record.get("tenant_id"),
            "actor": record.get("actor_id"),
            "action": record.get("action"),
            "resource_type": record.get("resource_type"),
            "resource_id": record.get("resource_id"),
            "outcome": record.get("outcome"),
            "trace_id": record.get("trace_id"),
            "run_id": record.get("run_id"),
            "workflow_id": record.get("workflow_id"),
            "record_id": record.get("id"),
        }
        sd = " ".join(
            f'{key}="{self._escape_sd(value)}"'
            for key, value in sd_fields.items()
            if value is not None
        )
        structured_data = f"[xagent@{self.ENTERPRISE_ID} {sd}]" if sd else "-"
        msg = json.dumps(record, ensure_ascii=False, default=str)

        return (
            f"<{pri}>1 {timestamp} {self.hostname} {self.app_name} "
            f"{self.proc_id} {msg_id} {structured_data} {msg}"
        )


# ---------------------------------------------------------------------------
# 外送通道抽象
# ---------------------------------------------------------------------------


class AuditExporter(ABC):
    """外送通道抽象基类。"""

    name: str = "exporter"

    @abstractmethod
    async def send(self, records: list[dict[str, Any]]) -> None:
        """发送一批审计记录; 失败必须抛异常(由 shipper 负责重试/死信)。"""

    async def close(self) -> None:
        """释放资源(可选)。"""
        return None


class SyslogExporter(AuditExporter):
    """syslog 外送(RFC5424, UDP 或 TCP)。

    UDP: 每条消息一个数据报。TCP: 批量消息以换行分帧(non-transparent
    framing, 兼容 rsyslog/syslog-ng 默认)。
    """

    name = "syslog"

    def __init__(
        self,
        host: str,
        port: int = 514,
        *,
        protocol: str = "udp",
        formatter: RFC5424Formatter | None = None,
        timeout: float = 5.0,
    ) -> None:
        if protocol not in ("udp", "tcp"):
            raise ValueError(f"unsupported syslog protocol: {protocol}")
        self.host = host
        self.port = port
        self.protocol = protocol
        self.formatter = formatter or RFC5424Formatter()
        self.timeout = timeout

    async def send(self, records: list[dict[str, Any]]) -> None:
        messages = [self.formatter.format(record) for record in records]
        if self.protocol == "udp":
            await asyncio.to_thread(self._send_udp, messages)
        else:
            await asyncio.to_thread(self._send_tcp, messages)

    def _send_udp(self, messages: list[str]) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(self.timeout)
            for message in messages:
                sock.sendto(message.encode("utf-8"), (self.host, self.port))

    def _send_tcp(self, messages: list[str]) -> None:
        payload = "".join(message + "\n" for message in messages).encode("utf-8")
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
            sock.sendall(payload)


class WebhookExporter(AuditExporter):
    """webhook 外送(HTTP POST JSON 批量)。

    支持自定义头、Bearer Token, 以及 HMAC-SHA256 请求体签名头
    ``X-XAgent-Signature-256: sha256=<hex>``(供接收方验签)。
    非 2xx 响应抛异常进入重试。
    """

    name = "webhook"

    def __init__(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        bearer_token: str | None = None,
        hmac_secret: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.url = url
        self.headers = dict(headers or {})
        self.bearer_token = bearer_token
        self.hmac_secret = hmac_secret
        self.timeout = timeout
        self._client: Any = None  # httpx.AsyncClient, 延迟到 async 上下文创建

    def _get_client(self) -> Any:
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def send(self, records: list[dict[str, Any]]) -> None:
        body = json.dumps(
            {
                "source": "xagent-audit",
                "format": "xagent.audit.v1",
                "timestamp": datetime.now(UTC).isoformat(),
                "events": records,
            },
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "xagent-audit-shipper/1.0",
            **self.headers,
        }
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        if self.hmac_secret:
            digest = hmac_new(
                self.hmac_secret.encode("utf-8"), body, sha256
            ).hexdigest()
            headers["X-XAgent-Signature-256"] = f"sha256={digest}"

        response = await self._get_client().post(self.url, content=body, headers=headers)
        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(
                f"webhook export failed: HTTP {response.status_code} "
                f"from {self.url}: {response.text[:200]}"
            )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


class S3WormExporter(AuditExporter):
    """S3 / WORM 外送(接口抽象 + 配置占位)。

    无 boto3 环境时, :meth:`send` 抛出 :class:`AuditExportUnavailable`
    显式降级; 安装 ``boto3`` 后按批次写入
    ``s3://<bucket>/<prefix>YYYY/MM/DD/<batch>.jsonl``,
    并附带 Object Lock(COMPLIANCE 模式)实现 WORM 留存。

    本环境未安装 boto3, 该通道为配置占位(见 Wave A 报告)。
    """

    name = "s3_worm"

    def __init__(
        self,
        bucket: str,
        *,
        prefix: str = "audit/",
        region: str | None = None,
        endpoint_url: str | None = None,
        object_lock_mode: str = "COMPLIANCE",
        retention_days: int = 365 * 7,
        client: Any = None,
    ) -> None:
        self.bucket = bucket
        self.prefix = prefix
        self.region = region
        self.endpoint_url = endpoint_url
        self.object_lock_mode = object_lock_mode
        self.retention_days = retention_days
        self._client = client
        self._boto3: Any = None
        try:
            import boto3  # type: ignore[import-untyped]

            self._boto3 = boto3
        except ImportError:
            self._boto3 = None

    @property
    def available(self) -> bool:
        return self._client is not None or self._boto3 is not None

    def _get_client(self) -> Any:
        if self._client is None:
            if self._boto3 is None:
                raise AuditExportUnavailable(
                    "S3/WORM 外送需要 boto3(当前环境未安装, 本通道为配置占位)。"
                    "启用方式: pip install boto3 并在对象存储侧开启 Object Lock。"
                )
            self._client = self._boto3.client(
                "s3", region_name=self.region, endpoint_url=self.endpoint_url
            )
        return self._client

    async def send(self, records: list[dict[str, Any]]) -> None:
        client = self._get_client()  # 无 boto3 时在此显式抛出
        now = datetime.now(UTC)
        key = (
            f"{self.prefix}{now:%Y/%m/%d}/"
            f"audit-{now:%Y%m%dT%H%M%S%fZ}-{len(records)}.jsonl"
        )
        body = "\n".join(
            json.dumps(record, ensure_ascii=False, default=str) for record in records
        ).encode("utf-8")
        retain_until = now + timedelta(days=self.retention_days)

        def _put() -> None:
            client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=body,
                ContentType="application/x-ndjson",
                ObjectLockMode=self.object_lock_mode,
                ObjectLockRetainUntilDate=retain_until,
            )

        await asyncio.to_thread(_put)


# ---------------------------------------------------------------------------
# 外送调度器
# ---------------------------------------------------------------------------


class AuditShipperConfig(BaseModel):
    """shipper 运行参数。"""

    queue_maxsize: int = Field(default=10_000, ge=1)
    batch_size: int = Field(default=100, ge=1)
    flush_interval_seconds: float = Field(default=1.0, gt=0)
    retry_attempts: int = Field(default=5, ge=1)
    retry_base_delay_seconds: float = Field(default=0.5, ge=0)
    retry_max_delay_seconds: float = Field(default=30.0, gt=0)
    dead_letter_path: Path | None = None


class AuditShipper:
    """异步审计外送调度器。

    使用方式::

        shipper = AuditShipper([SyslogExporter("127.0.0.1"), WebhookExporter(url)])
        await shipper.start()
        shipper.enqueue(record_dict)   # 同步、非阻塞
        ...
        await shipper.stop()           # 尽量排空队列后退出

    简化 API (P1-04)::

        shipper = AuditShipper(webhook_url="https://example.com/audit")
        ok = await shipper.ship(event_dict)
        count = await shipper.ship_batch([event1, event2])

    ``enqueue`` 面向异步请求处理线程调用(asyncio 单线程语义);
    队列满时不阻塞, 直接落入死信并计 dropped。
    """

    def __init__(
        self,
        exporters: list[AuditExporter] | None = None,
        config: AuditShipperConfig | None = None,
        *,
        webhook_url: str | None = None,
        syslog_host: str | None = None,
        syslog_port: int = 514,
    ) -> None:
        # 支持简化构造: AuditShipper(webhook_url=..., syslog_host=...)
        if exporters is None:
            exporters = []
            if webhook_url:
                exporters.append(WebhookExporter(webhook_url))
            if syslog_host:
                exporters.append(SyslogExporter(syslog_host, port=syslog_port))
        self.exporters = list(exporters)
        self.config = config or AuditShipperConfig()
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=self.config.queue_maxsize
        )
        self._task: asyncio.Task[None] | None = None
        self._stopping = False
        self._stats: dict[str, int] = {
            "queued": 0,
            "sent": 0,
            "failed_batches": 0,
            "dropped": 0,
            "dead_lettered": 0,
        }
        self._exporter_errors: dict[str, int] = {}

    # ------------------------------------------------------------ lifecycle

    async def start(self) -> None:
        """启动后台发送 worker。"""
        if self._task is not None:
            return
        self._stopping = False
        self._task = asyncio.create_task(self._run(), name="audit-shipper")

    async def stop(self, *, drain_timeout: float = 10.0) -> None:
        """停止 worker: 等待队列排空(至多 drain_timeout 秒), 然后关闭通道。"""
        if self._task is None:
            return
        self._stopping = True
        try:
            await asyncio.wait_for(self._drain(), timeout=drain_timeout)
        except TimeoutError:
            logger.warning(
                "audit shipper stop: queue not fully drained (%d pending)",
                self._queue.qsize(),
            )
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        for exporter in self.exporters:
            try:
                await exporter.close()
            except Exception:
                logger.exception("audit exporter %s close failed", exporter.name)

    async def _drain(self) -> None:
        while not self._queue.empty():
            await asyncio.sleep(0.05)

    # --------------------------------------------------------------- intake

    def enqueue(self, record: dict[str, Any]) -> bool:
        """非阻塞入队。队列满时落死信并返回 False。"""
        try:
            self._queue.put_nowait(record)
            self._stats["queued"] += 1
            return True
        except asyncio.QueueFull:
            self._stats["dropped"] += 1
            self._dead_letter([record], reason="queue_full")
            return False

    def enqueue_event(self, record: Any) -> bool:
        """接受 pydantic 记录对象(自动 model_dump)或 dict。"""
        if hasattr(record, "model_dump"):
            record = record.model_dump(mode="json")
        return self.enqueue(record)

    # ---------------------------------------------------------------- worker

    async def _run(self) -> None:
        while True:
            batch = await self._collect_batch()
            if not batch:
                continue
            for exporter in self.exporters:
                await self._send_with_retry(exporter, batch)

    async def _collect_batch(self) -> list[dict[str, Any]]:
        first = await self._queue.get()
        batch = [first]
        while len(batch) < self.config.batch_size:
            try:
                item = await asyncio.wait_for(
                    self._queue.get(), timeout=self.config.flush_interval_seconds
                )
                batch.append(item)
            except TimeoutError:
                break
        return batch

    async def _send_with_retry(
        self, exporter: AuditExporter, batch: list[dict[str, Any]]
    ) -> None:
        delay = self.config.retry_base_delay_seconds
        for attempt in range(1, self.config.retry_attempts + 1):
            try:
                await exporter.send(batch)
                self._stats["sent"] += len(batch)
                return
            except Exception as exc:
                self._exporter_errors[exporter.name] = (
                    self._exporter_errors.get(exporter.name, 0) + 1
                )
                logger.warning(
                    "audit export via %s failed (attempt %d/%d): %s",
                    exporter.name,
                    attempt,
                    self.config.retry_attempts,
                    exc,
                )
                if attempt < self.config.retry_attempts:
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, self.config.retry_max_delay_seconds)
        self._stats["failed_batches"] += 1
        self._dead_letter(batch, reason=f"{exporter.name}_exhausted")

    def _dead_letter(self, records: list[dict[str, Any]], *, reason: str) -> None:
        self._stats["dead_lettered"] += len(records)
        path = self.config.dead_letter_path
        if path is None:
            logger.error(
                "audit shipper dead-lettered %d record(s) (%s); "
                "configure dead_letter_path to persist them",
                len(records),
                reason,
            )
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                for record in records:
                    handle.write(
                        json.dumps(
                            {
                                "dead_lettered_at": datetime.now(UTC).isoformat(),
                                "reason": reason,
                                "record": record,
                            },
                            ensure_ascii=False,
                            default=str,
                        )
                        + "\n"
                    )
        except OSError:
            logger.exception("audit shipper failed to write dead letter file %s", path)

    # ------------------------------------------------------- simplified API (P1-04)

    async def ship(self, event: dict[str, Any]) -> bool:
        """直接发送单条审计事件到所有已配置通道(同步等待结果)。

        返回 True 表示至少一个通道发送成功; 无通道或全部失败返回 False。
        失败时写入死信队列(如已配置)。
        """
        if not self.exporters:
            return self.enqueue(event)
        success = False
        for exporter in self.exporters:
            try:
                await exporter.send([event])
                self._stats["sent"] += 1
                success = True
            except Exception as exc:
                logger.warning(
                    "audit ship single event via %s failed: %s", exporter.name, exc
                )
                self._exporter_errors[exporter.name] = (
                    self._exporter_errors.get(exporter.name, 0) + 1
                )
        if not success:
            self._stats["failed_batches"] += 1
            self._dead_letter([event], reason="ship_all_exporters_failed")
        return success

    async def ship_batch(self, events: list[dict[str, Any]]) -> int:
        """批量发送审计事件, 返回成功发送的事件总数。

        对每个通道尝试发送整批; 通道失败时按指数退避重试,
        最终失败写入死信队列。
        """
        if not events:
            return 0
        if not self.exporters:
            # 无通道时入队(后台 worker 处理)
            count = 0
            for event in events:
                if self.enqueue(event):
                    count += 1
            return count

        total_sent = 0
        for exporter in self.exporters:
            delay = self.config.retry_base_delay_seconds
            sent = False
            for attempt in range(1, self.config.retry_attempts + 1):
                try:
                    await exporter.send(events)
                    total_sent += len(events)
                    sent = True
                    break
                except Exception as exc:
                    self._exporter_errors[exporter.name] = (
                        self._exporter_errors.get(exporter.name, 0) + 1
                    )
                    logger.warning(
                        "audit ship_batch via %s failed (attempt %d/%d): %s",
                        exporter.name, attempt, self.config.retry_attempts, exc,
                    )
                    if attempt < self.config.retry_attempts:
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, self.config.retry_max_delay_seconds)
            if not sent:
                self._stats["failed_batches"] += 1
                self._dead_letter(events, reason=f"{exporter.name}_batch_exhausted")
        self._stats["sent"] += total_sent
        return total_sent

    # ----------------------------------------------------------------- misc

    @property
    def pending(self) -> int:
        return self._queue.qsize()

    def stats(self) -> dict[str, Any]:
        return {
            **self._stats,
            "pending": self._queue.qsize(),
            "exporter_errors": dict(self._exporter_errors),
            "exporters": [exporter.name for exporter in self.exporters],
        }


# ---------------------------------------------------------------------------
# 配置装配(集成波入口)
# ---------------------------------------------------------------------------


class SyslogChannelConfig(BaseModel):
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 514
    protocol: str = "udp"  # udp | tcp


class WebhookChannelConfig(BaseModel):
    enabled: bool = False
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    bearer_token: str | None = None
    hmac_secret: str | None = None


class S3WormChannelConfig(BaseModel):
    enabled: bool = False
    bucket: str = ""
    prefix: str = "audit/"
    region: str | None = None
    endpoint_url: str | None = None
    object_lock_mode: str = "COMPLIANCE"
    retention_days: int = 365 * 7


class AuditShipperChannels(BaseModel):
    """双通道 + S3/WORM 占位的总配置。"""

    syslog: SyslogChannelConfig = Field(default_factory=SyslogChannelConfig)
    webhook: WebhookChannelConfig = Field(default_factory=WebhookChannelConfig)
    s3_worm: S3WormChannelConfig = Field(default_factory=S3WormChannelConfig)
    shipper: AuditShipperConfig = Field(default_factory=AuditShipperConfig)


def build_shipper(channels: AuditShipperChannels) -> AuditShipper:
    """按配置装配 AuditShipper(仅启用的通道会被实例化)。"""
    exporters: list[AuditExporter] = []
    if channels.syslog.enabled:
        exporters.append(
            SyslogExporter(
                channels.syslog.host,
                channels.syslog.port,
                protocol=channels.syslog.protocol,
            )
        )
    if channels.webhook.enabled:
        exporters.append(
            WebhookExporter(
                channels.webhook.url,
                headers=channels.webhook.headers,
                bearer_token=channels.webhook.bearer_token,
                hmac_secret=channels.webhook.hmac_secret,
            )
        )
    if channels.s3_worm.enabled:
        exporters.append(
            S3WormExporter(
                channels.s3_worm.bucket,
                prefix=channels.s3_worm.prefix,
                region=channels.s3_worm.region,
                endpoint_url=channels.s3_worm.endpoint_url,
                object_lock_mode=channels.s3_worm.object_lock_mode,
                retention_days=channels.s3_worm.retention_days,
            )
        )
    return AuditShipper(exporters, config=channels.shipper)
