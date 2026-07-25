"""P2-11: 技能自沉淀 API.

端点:
- GET  /api/v1/skill-sediment/stats — 沉淀引擎统计
- GET  /api/v1/skill-sediment/skills — 列出沉淀的技能
- POST /api/v1/skill-sediment/skills/{name}/promote — 确认入库
- POST /api/v1/skill-sediment/skills/{name}/reject — 拒绝
- POST /api/v1/skill-sediment/prune — 淘汰低使用率技能
- GET  /api/v1/skill-sediment/events — 沉淀事件历史
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.app.core.skill_distillation.sedimentation import get_sedimentation_engine

router = APIRouter(prefix="/api/v1/skill-sediment", tags=["skill-sediment"])


# ─── 响应模型 ─────────────────────────────────────────────────────────────────


class SedimentStatsResponse(BaseModel):
    total_events: int
    sedimented_count: int
    trajectory_buffer_size: int
    total_skills: int
    promoted: int
    rejected: int
    pruned: int


class SedimentEventResponse(BaseModel):
    event_id: str
    trace_id: str
    task: str
    timestamp: str
    patterns_found: int
    drafts_generated: int
    drafts_accepted: int
    drafts_rejected_duplicate: int
    skill_names: list[str]
    decision: str


# ─── 端点 ─────────────────────────────────────────────────────────────────────


@router.get("/stats", response_model=SedimentStatsResponse)
def get_stats():
    """获取沉淀引擎统计."""
    engine = get_sedimentation_engine()
    return SedimentStatsResponse(**engine.get_stats())


@router.get("/skills")
def list_skills(status: str | None = Query(None, description="过滤状态: draft/promoted/rejected")):
    """列出沉淀的技能."""
    engine = get_sedimentation_engine()
    return engine.list_skills(status=status)


@router.post("/skills/{name}/promote")
def promote_skill(name: str):
    """确认技能入库."""
    engine = get_sedimentation_engine()
    if not engine.promote_skill(name):
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    return {"name": name, "status": "promoted"}


@router.post("/skills/{name}/reject")
def reject_skill(name: str):
    """拒绝技能."""
    engine = get_sedimentation_engine()
    if not engine.reject_skill(name):
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    return {"name": name, "status": "rejected"}


@router.post("/prune")
def prune_skills(min_usage: int = Query(1, ge=0, description="最低使用次数")):
    """淘汰低使用率技能."""
    engine = get_sedimentation_engine()
    pruned = engine.prune(min_usage)
    return {"pruned": pruned}


@router.get("/events", response_model=list[SedimentEventResponse])
def list_events(limit: int = Query(20, ge=1, le=100)):
    """沉淀事件历史."""
    engine = get_sedimentation_engine()
    events = engine.events[-limit:]
    return [
        SedimentEventResponse(
            event_id=e.event_id,
            trace_id=e.trace_id,
            task=e.task,
            timestamp=e.timestamp,
            patterns_found=e.patterns_found,
            drafts_generated=e.drafts_generated,
            drafts_accepted=e.drafts_accepted,
            drafts_rejected_duplicate=e.drafts_rejected_duplicate,
            skill_names=e.skill_names,
            decision=e.decision,
        )
        for e in reversed(events)
    ]
