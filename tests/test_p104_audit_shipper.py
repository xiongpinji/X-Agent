"""P1-04: 审计外送单元/集成测试。

覆盖:
- RFC5424 格式化(PRI/version/SD/MSG)
- syslog UDP 通道: 本地 UDP 套接字实测
- webhook 通道: 本地 HTTP 服务器实测(含 HMAC 签名验证)
- AuditShipper: 非阻塞入队、批量发送、失败重试、死信缓冲、stats
- S3/WORM: 无 boto3 环境显式降级(不静默假成功)
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading
from datetime import UTC, datetime
from hashlib import sha256
from hmac import new as hmac_new
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from backend.app.core.audit_shipper import (
    AuditExportUnavailable,
    AuditShipper,
    AuditShipperChannels,
    AuditShipperConfig,
    RFC5424Formatter,
    S3WormExporter,
    SyslogExporter,
    WebhookExporter,
    build_shipper,
)


def _record(i: int = 0, **overrides) -> dict:
    record = {
        "id": f"rec-{i:04d}",
        "tenant_id": "tenant-a",
        "actor_id": "user-1",
        "action": "agent.run",
        "resource_type": "agent",
        "resource_id": "agent-1",
        "outcome": "success",
        "trace_id": "trace-1",
        "created_at": datetime(2026, 7, 20, 12, 0, 0, tzinfo=UTC).isoformat(),
    }
    record.update(overrides)
    return record


# ---------------------------------------------------------------------------
# RFC5424 格式化
# ---------------------------------------------------------------------------


def test_rfc5424_format() -> None:
    formatter = RFC5424Formatter(hostname="testhost", app_name="xagent")
    message = formatter.format(_record())

    # facility 13 * 8 + severity 6 = 110; 版本 1
    assert message.startswith("<110>1 2026-07-20T12:00:00.000Z testhost xagent - agent.run ")
    assert "[xagent@32473" in message
    assert 'tenant="tenant-a"' in message
    assert 'actor="user-1"' in message
    assert 'outcome="success"' in message
    assert 'record_id="rec-0000"' in message
    # MSG 部分是可解析 JSON
    msg_json = message.split("] ", 1)[1]
    parsed = json.loads(msg_json)
    assert parsed["id"] == "rec-0000"


def test_rfc5424_severity_mapping() -> None:
    formatter = RFC5424Formatter(hostname="h")
    # failure → severity 4 (warning): pri = 13*8+4 = 108
    assert formatter.format(_record(outcome="failure")).startswith("<108>1 ")
    # denied → warning
    assert formatter.format(_record(outcome="denied")).startswith("<108>1 ")


def test_rfc5424_escapes_structured_data() -> None:
    formatter = RFC5424Formatter(hostname="h")
    message = formatter.format(_record(actor_id='evil"actor]\\'))
    assert 'actor="evil\\"actor\\]\\\\"' in message


# ---------------------------------------------------------------------------
# syslog UDP 实测
# ---------------------------------------------------------------------------


def test_syslog_udp_delivery() -> None:
    listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    listener.bind(("127.0.0.1", 0))
    listener.settimeout(5)
    port = listener.getsockname()[1]

    exporter = SyslogExporter("127.0.0.1", port, protocol="udp")

    async def _send() -> None:
        await exporter.send([_record(1), _record(2)])

    asyncio.run(_send())

    received = []
    for _ in range(2):
        data, _ = listener.recvfrom(65535)
        received.append(data.decode("utf-8"))
    listener.close()

    assert all(msg.startswith("<110>1 ") for msg in received)
    assert any("rec-0001" in msg for msg in received)
    assert any("rec-0002" in msg for msg in received)


# ---------------------------------------------------------------------------
# webhook 实测(本地 HTTP 服务器)
# ---------------------------------------------------------------------------


class _CapturedRequest:
    def __init__(self) -> None:
        self.bodies: list[bytes] = []
        self.headers: list[dict] = []
        self.status_code = 200
        self.event = threading.Event()


def _start_http_server(captured: _CapturedRequest) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            captured.bodies.append(body)
            captured.headers.append(dict(self.headers))
            captured.event.set()
            self.send_response(captured.status_code)
            self.end_headers()

        def log_message(self, *args) -> None:  # 静默
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_webhook_delivery_with_hmac_signature() -> None:
    captured = _CapturedRequest()
    server = _start_http_server(captured)
    url = f"http://127.0.0.1:{server.server_address[1]}/hook"

    secret = "webhook-secret"
    exporter = WebhookExporter(
        url,
        bearer_token="tok-123",
        hmac_secret=secret,
    )

    async def _send() -> None:
        await exporter.send([_record(1), _record(2)])
        await exporter.close()

    asyncio.run(_send())
    server.shutdown()

    assert captured.event.wait(5)
    assert len(captured.bodies) == 1
    body = captured.bodies[0]
    payload = json.loads(body)
    assert payload["source"] == "xagent-audit"
    assert len(payload["events"]) == 2
    assert payload["events"][0]["id"] == "rec-0001"

    headers = captured.headers[0]
    assert headers.get("Authorization") == "Bearer tok-123"
    expected = hmac_new(secret.encode(), body, sha256).hexdigest()
    assert headers.get("X-XAgent-Signature-256") == f"sha256={expected}"


def test_webhook_non_2xx_raises_for_retry() -> None:
    captured = _CapturedRequest()
    captured.status_code = 500
    server = _start_http_server(captured)
    url = f"http://127.0.0.1:{server.server_address[1]}/hook"

    exporter = WebhookExporter(url)

    async def _send() -> None:
        await exporter.send([_record(1)])

    with pytest.raises(RuntimeError, match="HTTP 500"):
        asyncio.run(_send())
    server.shutdown()


# ---------------------------------------------------------------------------
# AuditShipper 端到端
# ---------------------------------------------------------------------------


async def test_shipper_end_to_end_non_blocking(tmp_path) -> None:
    captured = _CapturedRequest()
    server = _start_http_server(captured)
    url = f"http://127.0.0.1:{server.server_address[1]}/hook"

    shipper = AuditShipper(
        [WebhookExporter(url)],
        config=AuditShipperConfig(flush_interval_seconds=0.1),
    )
    await shipper.start()
    try:
        for i in range(5):
            assert shipper.enqueue(_record(i)) is True  # 同步非阻塞
        for _ in range(100):
            await asyncio.sleep(0.05)
            if captured.event.is_set():
                break
        assert captured.event.is_set(), "webhook 应在 5s 内收到批量"
        await asyncio.sleep(0.3)
    finally:
        await shipper.stop()
    server.shutdown()

    stats = shipper.stats()
    assert stats["queued"] == 5
    assert stats["sent"] == 5
    assert stats["dropped"] == 0
    total_events = sum(len(json.loads(body)["events"]) for body in captured.bodies)
    assert total_events == 5


async def test_shipper_retry_then_dead_letter(tmp_path) -> None:
    captured = _CapturedRequest()
    captured.status_code = 500  # 持续失败
    server = _start_http_server(captured)
    url = f"http://127.0.0.1:{server.server_address[1]}/hook"

    dead_letter = tmp_path / "dead_letter.jsonl"
    shipper = AuditShipper(
        [WebhookExporter(url)],
        config=AuditShipperConfig(
            flush_interval_seconds=0.05,
            retry_attempts=2,
            retry_base_delay_seconds=0.05,
            dead_letter_path=dead_letter,
        ),
    )
    await shipper.start()
    try:
        shipper.enqueue(_record(1))
        # 等待重试耗尽并落死信
        for _ in range(100):
            await asyncio.sleep(0.05)
            if dead_letter.exists() and shipper.stats()["failed_batches"] >= 1:
                break
    finally:
        await shipper.stop()
    server.shutdown()

    stats = shipper.stats()
    assert stats["failed_batches"] == 1
    assert stats["dead_lettered"] == 1
    assert stats["sent"] == 0
    assert stats["exporter_errors"]["webhook"] >= 2  # 至少重试过 2 次

    lines = dead_letter.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["reason"] == "webhook_exhausted"
    assert entry["record"]["id"] == "rec-0001"


async def test_shipper_queue_full_drops_to_dead_letter(tmp_path) -> None:
    class _NeverSendExporter(WebhookExporter):
        async def send(self, records):  # 永不返回, 模拟下游 hang
            await asyncio.sleep(3600)

    dead_letter = tmp_path / "dead_letter.jsonl"
    shipper = AuditShipper(
        [_NeverSendExporter("http://127.0.0.1:1/")],
        config=AuditShipperConfig(
            queue_maxsize=2,
            batch_size=1,
            flush_interval_seconds=0.05,
            dead_letter_path=dead_letter,
        ),
    )
    await shipper.start()
    try:
        # worker 拿走 1 条并 hang; 队列容量 2 → 第 4 条开始溢出
        results = [shipper.enqueue(_record(i)) for i in range(6)]
        assert results.count(True) <= 3
        assert results.count(False) >= 3
    finally:
        await shipper.stop(drain_timeout=0.1)
    assert shipper.stats()["dropped"] >= 3


async def test_shipper_dual_channel_delivery(tmp_path) -> None:
    """syslog + webhook 双通道同批送达。"""
    captured = _CapturedRequest()
    server = _start_http_server(captured)
    url = f"http://127.0.0.1:{server.server_address[1]}/hook"

    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.bind(("127.0.0.1", 0))
    udp.settimeout(5)

    shipper = AuditShipper(
        [
            SyslogExporter("127.0.0.1", udp.getsockname()[1]),
            WebhookExporter(url),
        ],
        config=AuditShipperConfig(flush_interval_seconds=0.05),
    )
    await shipper.start()
    try:
        shipper.enqueue(_record(9))
        data, _ = await asyncio.to_thread(udp.recvfrom, 65535)
        assert "rec-0009" in data.decode("utf-8")
        for _ in range(100):
            await asyncio.sleep(0.05)
            if captured.event.is_set():
                break
        assert captured.event.is_set(), "webhook 应在 5s 内收到批量"
    finally:
        await shipper.stop()
        udp.close()
    server.shutdown()

    assert shipper.stats()["sent"] == 2  # 每通道各记 1 条


# ---------------------------------------------------------------------------
# S3/WORM 显式降级
# ---------------------------------------------------------------------------


def test_s3_worm_unavailable_without_boto3() -> None:
    try:
        import boto3  # noqa: F401

        pytest.skip("boto3 已安装, 跳过无 boto3 降级路径")
    except ImportError:
        pass

    exporter = S3WormExporter("my-bucket", prefix="audit/")
    assert exporter.available is False

    async def _send() -> None:
        await exporter.send([_record(1)])

    with pytest.raises(AuditExportUnavailable, match="boto3"):
        asyncio.run(_send())


def test_build_shipper_from_channels_config() -> None:
    channels = AuditShipperChannels()
    assert channels.syslog.enabled is False
    assert channels.webhook.enabled is False
    assert channels.s3_worm.enabled is False

    shipper = build_shipper(channels)
    assert shipper.exporters == []

    channels.syslog.enabled = True
    channels.webhook.enabled = True
    channels.webhook.url = "http://127.0.0.1:9/hook"
    channels.s3_worm.enabled = True
    channels.s3_worm.bucket = "b"
    shipper = build_shipper(channels)
    assert [e.name for e in shipper.exporters] == ["syslog", "webhook", "s3_worm"]
