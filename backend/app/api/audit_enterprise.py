"""P2-12: 企业级审计日志增强 API.

端点:
- POST /api/v1/audit-enterprise/export/siem — 触发 SIEM 外送
- GET  /api/v1/audit-enterprise/export/formats — 支持的导出格式
- POST /api/v1/audit-enterprise/retention/configure — 配置留存策略
- GET  /api/v1/audit-enterprise/retention/status — 留存合规状态
- POST /api/v1/audit-enterprise/retention/enforce — 执行留存清理
- GET  /api/v1/audit-enterprise/analytics — 审计分析聚合
"""

from __future__ import annotations

import contextlib
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend.app.core.audit_enhanced.retention import RetentionEngine, RetentionPolicy
from backend.app.core.audit_enhanced.siem_exporter import SIEMConfig, SIEMExporter, SIEMFormat

router = APIRouter(prefix="/api/v1/audit-enterprise", tags=["audit-enterprise"])

# ─── 模块级单例 ─────────────────────────────────────────────────────────────────

_exporter: SIEMExporter | None = None
_retention_engine: RetentionEngine | None = None


def _get_exporter() -> SIEMExporter:
    global _exporter
    if _exporter is None:
        _exporter = SIEMExporter(SIEMConfig())
    return _exporter


def _get_retention_engine() -> RetentionEngine:
    global _retention_engine
    if _retention_engine is None:
        _retention_engine = RetentionEngine()
    return _retention_engine


# ─── 请求/响应模型 ─────────────────────────────────────────────────────────────


class SIEMExportRequest(BaseModel):
    format: str = Field("cef", description="导出格式: cef/syslog/jsonl")
    records: list[dict[str, Any]] = Field(default_factory=list, description="要导出的记录")
    tenant_id: str | None = Field(None, description="按租户过滤")


class RetentionConfigureRequest(BaseModel):
    retention_days: int = Field(365, ge=30, le=3650)
    archive_after_days: int = Field(90, ge=7, le=365)
    immutable: bool = Field(True)
    max_records: int = Field(1_000_000, ge=1000)
    compliance_standard: str = Field("SOC2")


# ─── 端点 ─────────────────────────────────────────────────────────────────────


@router.post("/export/siem")
async def export_siem(req: SIEMExportRequest):
    """触发 SIEM 外送."""
    exporter = _get_exporter()
    # 更新格式
    try:
        fmt = SIEMFormat(req.format)
    except ValueError:
        fmt = SIEMFormat.CEF
    exporter._config.format = fmt

    records = req.records
    if req.tenant_id:
        records = [r for r in records if r.get("tenant_id") == req.tenant_id]

    result = await exporter.flush(records)
    return {
        "exported": result.exported,
        "failed": result.failed,
        "format": result.format,
        "target": result.target,
        "timestamp": result.timestamp,
    }


@router.get("/export/formats")
async def list_export_formats():
    """支持的导出格式."""
    return {
        "formats": [
            {"id": "cef", "name": "Common Event Format", "description": "ArcSight/Splunk 通用格式"},
            {"id": "syslog", "name": "RFC 5424 Syslog", "description": "通用 syslog 协议"},
            {"id": "jsonl", "name": "JSON Lines", "description": "通用 JSON 行格式"},
        ]
    }


@router.post("/retention/configure")
async def configure_retention(req: RetentionConfigureRequest):
    """配置留存策略."""
    engine = _get_retention_engine()
    policy = RetentionPolicy(
        retention_days=req.retention_days,
        archive_after_days=req.archive_after_days,
        immutable=req.immutable,
        max_records=req.max_records,
        compliance_standard=req.compliance_standard,
    )
    engine.configure(policy)
    return {"status": "configured", "policy": policy.to_dict()}


@router.get("/retention/status")
async def retention_status():
    """留存合规状态."""
    engine = _get_retention_engine()
    # 使用空记录列表 (实际从 audit store 获取)
    status = engine.get_compliance_status([])
    return status.to_dict()


@router.post("/retention/enforce")
async def enforce_retention():
    """执行留存清理."""
    engine = _get_retention_engine()
    # 使用空记录列表 (实际从 audit store 获取)
    result = engine.enforce([])
    return result.to_dict()


@router.get("/analytics")
async def audit_analytics(
    tenant_id: str | None = Query(None),
    records: str | None = Query(None, description="JSON 编码的记录列表 (测试用)"),
):
    """审计分析聚合.

    按时间/租户/操作类型聚合审计记录统计。
    """
    import json

    # 解析记录 (实际从 audit store 获取)
    parsed_records: list[dict[str, Any]] = []
    if records:
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            parsed_records = json.loads(records)

    if tenant_id:
        parsed_records = [r for r in parsed_records if r.get("tenant_id") == tenant_id]

    # 聚合统计
    by_action: dict[str, int] = {}
    by_outcome: dict[str, int] = {}
    by_resource_type: dict[str, int] = {}
    by_tenant: dict[str, int] = {}

    for record in parsed_records:
        action = record.get("action", "unknown")
        outcome = record.get("outcome", "unknown")
        resource_type = record.get("resource_type", "unknown")
        tid = record.get("tenant_id", "default")

        by_action[action] = by_action.get(action, 0) + 1
        by_outcome[outcome] = by_outcome.get(outcome, 0) + 1
        by_resource_type[resource_type] = by_resource_type.get(resource_type, 0) + 1
        by_tenant[tid] = by_tenant.get(tid, 0) + 1

    return {
        "total_records": len(parsed_records),
        "by_action": by_action,
        "by_outcome": by_outcome,
        "by_resource_type": by_resource_type,
        "by_tenant": by_tenant,
    }
