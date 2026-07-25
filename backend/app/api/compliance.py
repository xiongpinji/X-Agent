"""合规与审计增强 API — SOC 2 证据收集、变更管理、事件响应。

P2-01: SOC 2 Type I 认证代码基础设施
P2-07: 渗透测试准备（安全头验证、漏洞披露）
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.core.compliance.change_management import (
    ChangeManagementEngine,
    ChangeRisk,
    ChangeType,
)
from backend.app.core.compliance.evidence import EvidenceCollector, build_default_collector
from backend.app.core.compliance.incident_response import (
    IncidentCategory,
    IncidentResponseEngine,
    IncidentSeverity,
)
from backend.app.core.compliance.trust_criteria import TrustServicesCriteria

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/compliance", tags=["compliance"])

# 全局实例
_evidence_collector: EvidenceCollector | None = None
_change_engine = ChangeManagementEngine()
_incident_engine = IncidentResponseEngine()
_trust_criteria = TrustServicesCriteria()


def _get_collector() -> EvidenceCollector:
    global _evidence_collector
    if _evidence_collector is None:
        _evidence_collector = build_default_collector()
    return _evidence_collector


# --- 证据收集 ---

@router.get("/evidence/controls")
async def list_controls() -> dict[str, Any]:
    """列出所有已注册的 SOC 2 控制点。"""
    collector = _get_collector()
    return {"controls": collector.registered_controls}


@router.post("/evidence/collect")
async def collect_evidence(control_id: str | None = None) -> dict[str, Any]:
    """收集控制点证据（全部或指定）。"""
    collector = _get_collector()
    if control_id:
        try:
            evidence = collector.collect_one(control_id)
            return {"evidence": evidence.to_dict()}
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Control not found: {control_id}")
    else:
        results = collector.collect_all()
        return {"evidence": [e.to_dict() for e in results], "count": len(results)}


@router.get("/evidence/report")
async def evidence_report() -> dict[str, Any]:
    """生成 SOC 2 证据收集报告。"""
    collector = _get_collector()
    return collector.generate_report()


# --- Trust Services Criteria ---

@router.get("/tsc/matrix")
async def tsc_matrix(category: str | None = None) -> dict[str, Any]:
    """获取 Trust Services Criteria 追溯矩阵。"""
    if category:
        mappings = _trust_criteria.get_by_category(category)
        return {"mappings": [m.__dict__ for m in mappings], "category": category}
    return {
        "matrix": _trust_criteria.to_matrix(),
        "summary": _trust_criteria.get_status_summary(),
        "compliance_score": _trust_criteria.get_compliance_score(),
    }


# --- 变更管理 ---

class CreateChangeRequest(BaseModel):
    title: str
    description: str = ""
    change_type: str = "code"
    risk_level: str = "medium"
    requester: str = "api"


@router.post("/changes")
async def create_change(req: CreateChangeRequest) -> dict[str, Any]:
    """创建变更请求。"""
    try:
        ct = ChangeType(req.change_type)
        rl = ChangeRisk(req.risk_level)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    cr = _change_engine.create_change(
        title=req.title,
        description=req.description,
        change_type=ct,
        risk_level=rl,
        requester=req.requester,
    )
    return {"change": cr.to_dict()}


@router.get("/changes")
async def list_changes(status_filter: str | None = None, risk: str | None = None) -> dict[str, Any]:
    """列出变更请求。"""
    from backend.app.core.compliance.change_management import ChangeStatus
    s = ChangeStatus(status_filter) if status_filter else None
    r = ChangeRisk(risk) if risk else None
    changes = _change_engine.list_changes(status=s, risk_level=r)
    return {"changes": [c.to_dict() for c in changes], "count": len(changes)}


@router.post("/changes/{change_id}/approve")
async def approve_change(change_id: str, approver: str = "admin", comment: str = "") -> dict[str, Any]:
    """审批变更。"""
    try:
        ok = _change_engine.approve(change_id, approver=approver, comment=comment)
        if not ok:
            raise HTTPException(status_code=400, detail="Cannot approve in current state")
        cr = _change_engine.get_change(change_id)
        return {"change": cr.to_dict() if cr else None}
    except KeyError:
        raise HTTPException(status_code=404, detail="Change not found")


@router.get("/changes/{change_id}/audit-trail")
async def change_audit_trail(change_id: str) -> dict[str, Any]:
    """获取变更审计轨迹。"""
    try:
        trail = _change_engine.get_audit_trail(change_id)
        return {"audit_trail": trail}
    except KeyError:
        raise HTTPException(status_code=404, detail="Change not found")


# --- 事件响应 ---

class ReportIncidentRequest(BaseModel):
    title: str
    description: str = ""
    category: str = "other"
    severity: str = "medium"
    reporter: str = "api"
    affected_tenants: list[str] = []


@router.post("/incidents")
async def report_incident(req: ReportIncidentRequest) -> dict[str, Any]:
    """报告安全事件。"""
    try:
        cat = IncidentCategory(req.category)
        sev = IncidentSeverity(req.severity)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    incident = _incident_engine.report_incident(
        title=req.title,
        description=req.description,
        category=cat,
        severity=sev,
        reporter=req.reporter,
        affected_tenants=req.affected_tenants,
    )
    return {"incident": incident.to_dict()}


@router.get("/incidents")
async def list_incidents(severity: str | None = None, phase: str | None = None) -> dict[str, Any]:
    """列出安全事件。"""
    from backend.app.core.compliance.incident_response import IncidentPhase
    s = IncidentSeverity(severity) if severity else None
    p = IncidentPhase(phase) if phase else None
    incidents = _incident_engine.list_incidents(severity=s, phase=p)
    return {"incidents": [i.to_dict() for i in incidents], "count": len(incidents)}


@router.get("/incidents/{incident_id}/sla")
async def incident_sla(incident_id: str) -> dict[str, Any]:
    """检查事件 SLA 合规性。"""
    try:
        return _incident_engine.check_sla_compliance(incident_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Incident not found")


# --- SOC 2 Readiness (auto-verified evidence) ---

@router.get("/soc2/report")
async def soc2_readiness_report() -> dict[str, Any]:
    """生成 SOC 2 就绪度报告 — 基于实际系统状态自动验证。"""
    from backend.app.core.compliance_evidence import get_evidence_collector
    collector = get_evidence_collector()
    return await collector.generate_readiness_report()


@router.get("/soc2/evidence/{control_id}")
async def soc2_control_evidence(control_id: str) -> dict[str, Any]:
    """获取指定控制点的自动验证证据。"""
    from backend.app.core.compliance_evidence import get_evidence_collector
    collector = get_evidence_collector()
    result = await collector.collect_control_evidence(control_id)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=result.get("error", "Control not found"))
    return result


# --- Security.txt (RFC 9116) ---

@router.get("/security.txt", include_in_schema=False)
async def security_txt() -> str:
    """RFC 9116 security.txt — 漏洞披露渠道。"""
    from fastapi.responses import PlainTextResponse
    content = """Contact: mailto:security@x-agent.dev
Expires: 2027-07-20T00:00:00.000Z
Preferred-Languages: en, zh
Policy: https://github.com/x-agent/x-agent/blob/main/SECURITY.md
Acknowledgments: https://github.com/x-agent/x-agent/blob/main/SECURITY.md
"""
    return PlainTextResponse(content=content, media_type="text/plain")
