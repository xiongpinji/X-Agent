from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.core.evolution import evolution_store
from backend.app.core.evolution_engine import evolution_engine
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/evolution", tags=["evolution"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


class EvolutionSummaryResponse(BaseModel):
    reflections: int
    learnings: int
    capabilities: int


class EvolutionStatsResponse(BaseModel):
    total_executions: int
    skill_drafts: int
    promoted_skills: int
    skill_names: list[str]


class TriggerRequest(BaseModel):
    trajectory: dict[str, Any] = {}
    result: dict[str, Any] = {}


@router.get("/summary", response_model=EvolutionSummaryResponse)
async def get_evolution_summary(principal: PrincipalDependency, agent_id: str | None = None) -> EvolutionSummaryResponse:
    enforce_scope(principal, "agent:read")
    return EvolutionSummaryResponse(
        reflections=len(evolution_store.list_reflections(agent_id=agent_id)),
        learnings=len(evolution_store.list_learnings(agent_id=agent_id)),
        capabilities=len(evolution_store.list_capabilities(agent_id=agent_id)),
    )


@router.get("/stats", response_model=EvolutionStatsResponse)
async def get_evolution_stats(principal: PrincipalDependency) -> EvolutionStatsResponse:
    """P1-06: 自进化引擎统计 (GEPA 闭环状态)."""
    enforce_scope(principal, "agent:read")
    stats = evolution_engine.get_stats()
    return EvolutionStatsResponse(**stats)


@router.get("/skills")
async def list_promoted_skills(principal: PrincipalDependency) -> list[dict[str, Any]]:
    """P1-06: 列出已晋升的可复用技能."""
    enforce_scope(principal, "agent:read")
    return [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "trigger_pattern": s.trigger_pattern,
            "tool_sequence": s.tool_sequence,
            "usage_count": s.usage_count,
            "success_rate": s.success_rate,
        }
        for s in evolution_engine.promoted_skills
    ]


@router.post("/trigger")
async def trigger_evolution(principal: PrincipalDependency, req: TriggerRequest) -> dict[str, Any]:
    """P1-06: 手动触发自进化闭环 (Execute-Evaluate-Optimize-Learn)."""
    enforce_scope(principal, "agent:write")
    reflection = await evolution_engine.on_task_complete(req.trajectory, req.result)
    if reflection is None:
        return {"status": "skipped", "reason": "task not successful or no pattern"}
    return {
        "status": "completed",
        "should_create_skill": reflection.should_create_skill,
        "skill_name": reflection.skill_name_suggestion,
        "confidence": reflection.confidence,
        "key_patterns": reflection.key_patterns,
    }


@router.get("/reflections")
async def list_reflections(principal: PrincipalDependency, agent_id: str | None = None) -> list[dict[str, object]]:
    enforce_scope(principal, "agent:read")
    return [item.model_dump(mode="json") for item in evolution_store.list_reflections(agent_id=agent_id)]


@router.get("/learnings")
async def list_learnings(principal: PrincipalDependency, agent_id: str | None = None) -> list[dict[str, object]]:
    enforce_scope(principal, "agent:read")
    return [item.model_dump(mode="json") for item in evolution_store.list_learnings(agent_id=agent_id)]


@router.get("/capabilities")
async def list_capabilities(principal: PrincipalDependency, agent_id: str | None = None) -> list[dict[str, object]]:
    enforce_scope(principal, "agent:read")
    return [item.model_dump(mode="json") for item in evolution_store.list_capabilities(agent_id=agent_id)]
