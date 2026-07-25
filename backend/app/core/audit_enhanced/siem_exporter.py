"""P2-12: SIEM 外送引擎.

支持格式:
- CEF (Common Event Format) — ArcSight/Splunk 通用
- SYSLOG (RFC 5424) — 通用 syslog
- JSON_LINES — 通用 JSON Lines

输出目标:
- 文件输出 (dev/测试)
- UDP syslog (生产)
- 内存缓冲 (测试)

设计原则:
- 格式化与传输分离
- 批量 flush 减少 I/O
- 失败不阻断主循环 (best-effort)
"""

from __future__ import annotations

import json
import logging
import socket
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SIEMFormat(StrEnum):
    """SIEM 导出格式."""

    CEF = "cef"
    SYSLOG = "syslog"
    JSON_LINES = "jsonl"


@dataclass
class SIEMConfig:
    """SIEM 外送配置."""

    format: SIEMFormat = SIEMFormat.CEF
    # UDP syslog 目标
    syslog_host: str | None = None
    syslog_port: int = 514
    syslog_protocol: str = "udp"  # udp / tcp
    # 文件输出
    output_file: str | None = None
    # 设备信息 (CEF)
    device_vendor: str = "X-Agent"
    device_product: str = "X-Agent Platform"
    device_version: str = "1.0"
    # 批量大小
    batch_size: int = 100


@dataclass
class ExportResult:
    """导出结果."""

    exported: int = 0
    failed: int = 0
    format: str = ""
    target: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class SIEMExporter:
    """SIEM 外送引擎.

    将审计日志记录格式化为 CEF/Syslog/JSON Lines 并外送到指定目标。
    """

    def __init__(self, config: SIEMConfig | None = None):
        self._config = config or SIEMConfig()
        self._buffer: list[str] = []
        self._export_count: int = 0
        self._socket: socket.socket | None = None

    @property
    def config(self) -> SIEMConfig:
        return self._config

    @property
    def export_count(self) -> int:
        return self._export_count

    def format_record(self, record: dict[str, Any]) -> str:
        """将审计记录格式化为目标格式.

        Args:
            record: 审计记录字典 (AuditLogRecord.model_dump())

        Returns:
            格式化后的字符串
        """
        if self._config.format == SIEMFormat.CEF:
            return self._format_cef(record)
        elif self._config.format == SIEMFormat.SYSLOG:
            return self._format_syslog(record)
        else:
            return self._format_jsonl(record)

    def _format_cef(self, record: dict[str, Any]) -> str:
        """CEF 格式: CEF:Version|Vendor|Product|Version|Signature|Name|Severity|Extension"""
        severity = self._map_severity(record.get("outcome", "success"))
        name = record.get("action", "unknown")
        signature_id = record.get("resource_type", "generic")

        # Extension 字段
        ext_parts = [
            f"act={record.get('action', '')}",
            f"src={record.get('tenant_id', '')}",
            f"suser={record.get('actor_id', '')}",
            f"outcome={record.get('outcome', '')}",
            f"rt={record.get('created_at', '')}",
            f"cs1={record.get('trace_id', '')}",
            "cs1Label=TraceID",
            f"cs2={record.get('resource_id', '')}",
            "cs2Label=ResourceID",
        ]
        extension = " ".join(ext_parts)

        return (
            f"CEF:0|{self._config.device_vendor}|{self._config.device_product}|"
            f"{self._config.device_version}|{signature_id}|{name}|{severity}|{extension}"
        )

    def _format_syslog(self, record: dict[str, Any]) -> str:
        """RFC 5424 Syslog 格式."""
        timestamp = record.get("created_at", datetime.now(UTC).isoformat())
        severity = self._map_syslog_severity(record.get("outcome", "success"))
        app_name = "xagent-audit"
        msg_id = record.get("action", "AUDIT")

        # Structured data
        sd = (
            f'[audit@32473 '
            f'tenant="{record.get("tenant_id", "")}" '
            f'actor="{record.get("actor_id", "")}" '
            f'resource="{record.get("resource_type", "")}" '
            f'outcome="{record.get("outcome", "")}" '
            f'trace="{record.get("trace_id", "")}"]'
        )

        return (
            f"<{severity}>{1} {timestamp} - {app_name} - - - "
            f"{sd} {msg_id}: {record.get('action', '')} on {record.get('resource_type', '')}"
        )

    def _format_jsonl(self, record: dict[str, Any]) -> str:
        """JSON Lines 格式."""
        enriched = {
            **record,
            "_siem": {
                "format": "jsonl",
                "exported_at": datetime.now(UTC).isoformat(),
                "source": "xagent-audit",
            },
        }
        return json.dumps(enriched, ensure_ascii=False, default=str)

    async def flush(self, records: list[dict[str, Any]]) -> ExportResult:
        """批量外送审计记录.

        Args:
            records: 审计记录列表

        Returns:
            ExportResult 导出结果
        """
        result = ExportResult(format=self._config.format.value)
        formatted_lines: list[str] = []

        for record in records:
            try:
                line = self.format_record(record)
                formatted_lines.append(line)
                result.exported += 1
            except Exception as e:
                logger.warning("Failed to format record: %s", e)
                result.failed += 1

        # 输出到目标
        if formatted_lines:
            try:
                self._send(formatted_lines)
                self._export_count += len(formatted_lines)
            except Exception as e:
                logger.error("SIEM export failed: %s", e)
                result.failed += len(formatted_lines)
                result.exported = 0

        # 确定目标描述
        if self._config.syslog_host:
            result.target = f"{self._config.syslog_protocol}://{self._config.syslog_host}:{self._config.syslog_port}"
        elif self._config.output_file:
            result.target = self._config.output_file
        else:
            result.target = "buffer"

        return result

    def _send(self, lines: list[str]) -> None:
        """发送格式化行到目标."""
        if self._config.syslog_host:
            self._send_syslog(lines)
        elif self._config.output_file:
            self._send_file(lines)
        else:
            self._buffer.extend(lines)

    def _send_syslog(self, lines: list[str]) -> None:
        """通过 UDP/TCP 发送到 syslog."""
        if self._socket is None:
            proto = socket.SOCK_DGRAM if self._config.syslog_protocol == "udp" else socket.SOCK_STREAM
            self._socket = socket.socket(socket.AF_INET, proto)
            if self._config.syslog_protocol == "tcp":
                self._socket.connect((self._config.syslog_host, self._config.syslog_port))

        for line in lines:
            data = (line + "\n").encode("utf-8")
            if self._config.syslog_protocol == "udp":
                self._socket.sendto(data, (self._config.syslog_host, self._config.syslog_port))
            else:
                self._socket.send(data)

    def _send_file(self, lines: list[str]) -> None:
        """写入文件."""
        path = Path(self._config.output_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            for line in lines:
                f.write(line + "\n")

    def get_buffer(self) -> list[str]:
        """获取内存缓冲 (测试用)."""
        return list(self._buffer)

    def clear_buffer(self) -> None:
        """清空缓冲."""
        self._buffer.clear()

    def close(self) -> None:
        """关闭连接."""
        if self._socket:
            self._socket.close()
            self._socket = None

    @staticmethod
    def _map_severity(outcome: str) -> int:
        """映射 CEF 严重级别 (0-10)."""
        mapping = {"success": 3, "failure": 7, "error": 8, "critical": 10}
        return mapping.get(outcome, 5)

    @staticmethod
    def _map_syslog_severity(outcome: str) -> int:
        """映射 syslog 优先级 (PRI = facility*8 + severity)."""
        # facility=1 (user), severity: 6=info, 3=error, 2=critical
        mapping = {"success": 14, "failure": 11, "error": 10, "critical": 10}
        return mapping.get(outcome, 14)
