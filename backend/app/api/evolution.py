from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.core.evolution import evolution_store
from backend.app.core.evolution_engine import evolution_engine
from backend.app.core.security import Principal
from backend.app.core.self_evolution import self_evolution_engine
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/evolution", tags=["evolution"])
extended_router = APIRouter(prefix="/api/v1/evolution", tags=["evolution-extended"])  # C2: unmounted; handler bodies unchanged
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


@extended_router.get("/reflections")
async def list_reflections(principal: PrincipalDependency, agent_id: str | None = None) -> list[dict[str, object]]:
    enforce_scope(principal, "agent:read")
    return [item.model_dump(mode="json") for item in evolution_store.list_reflections(agent_id=agent_id)]


@extended_router.get("/learnings")
async def list_learnings(principal: PrincipalDependency, agent_id: str | None = None) -> list[dict[str, object]]:
    enforce_scope(principal, "agent:read")
    return [item.model_dump(mode="json") for item in evolution_store.list_learnings(agent_id=agent_id)]


@extended_router.get("/capabilities")
async def list_capabilities(principal: PrincipalDependency, agent_id: str | None = None) -> list[dict[str, object]]:
    enforce_scope(principal, "agent:read")
    return [item.model_dump(mode="json") for item in evolution_store.list_capabilities(agent_id=agent_id)]


# ─── P1-06: Self-Evolution Engine Endpoints (Execute-Evaluate-Optimize-Learn) ───


class RecordExecutionRequest(BaseModel):
    """Request to record an agent execution trace."""
    task_id: str = Field(..., min_length=1)
    trace: dict[str, Any] = Field(default_factory=dict)


class EvaluateRequest(BaseModel):
    """Request to evaluate an execution."""
    execution_id: str = Field(..., min_length=1)
    feedback: dict[str, Any] | None = None


class OptimizeRequest(BaseModel):
    """Request to optimize strategy for an execution."""
    execution_id: str = Field(..., min_length=1)
    score: float = Field(..., ge=0.0, le=1.0)


class DistillSkillRequest(BaseModel):
    """Request to distill a skill from executions."""
    execution_ids: list[str] = Field(..., min_length=1)


class TriggerCycleRequest(BaseModel):
    """Request to trigger a full evolution cycle."""
    task_id: str = Field(..., min_length=1)


@extended_router.post("/self-evolution/record")
async def se_record_execution(
    principal: PrincipalDependency,
    req: RecordExecutionRequest,
) -> dict[str, Any]:
    """P1-06 Stage 1: Record an agent execution trace."""
    enforce_scope(principal, "agent:write")
    execution_id = await self_evolution_engine.record_execution(req.task_id, req.trace)
    return {"execution_id": execution_id, "task_id": req.task_id, "stage": "execute"}


@extended_router.post("/self-evolution/evaluate")
async def se_evaluate_execution(
    principal: PrincipalDependency,
    req: EvaluateRequest,
) -> dict[str, Any]:
    """P1-06 Stage 2: Evaluate execution quality."""
    enforce_scope(principal, "agent:write")
    score = await self_evolution_engine.evaluate_execution(req.execution_id, req.feedback)
    return {"execution_id": req.execution_id, "score": score, "stage": "evaluate"}


@extended_router.post("/self-evolution/optimize")
async def se_optimize_strategy(
    principal: PrincipalDependency,
    req: OptimizeRequest,
) -> dict[str, Any]:
    """P1-06 Stage 3: Optimize strategy based on evaluation."""
    enforce_scope(principal, "agent:write")
    result = await self_evolution_engine.optimize_strategy(req.execution_id, req.score)
    return {**result, "stage": "optimize"}


@extended_router.post("/self-evolution/distill")
async def se_distill_skill(
    principal: PrincipalDependency,
    req: DistillSkillRequest,
) -> dict[str, Any]:
    """P1-06 Stage 4: Distill successful patterns into reusable skills."""
    enforce_scope(principal, "agent:write")
    result = await self_evolution_engine.distill_skill(req.execution_ids)
    return {**result, "stage": "learn"}


@extended_router.post("/self-evolution/cycle")
async def se_trigger_cycle(
    principal: PrincipalDependency,
    req: TriggerCycleRequest,
) -> dict[str, Any]:
    """P1-06: Trigger a full Execute-Evaluate-Optimize-Learn cycle."""
    enforce_scope(principal, "agent:write")
    result = await self_evolution_engine.trigger_evolution_cycle(req.task_id)
    return result


@extended_router.get("/self-evolution/history")
async def se_get_history(
    principal: PrincipalDependency,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """P1-06: Get evolution history records."""
    enforce_scope(principal, "agent:read")
    records = await self_evolution_engine.get_evolution_history(limit=limit)
    return [r.to_dict() for r in records]


@extended_router.get("/self-evolution/stats")
async def se_get_stats(principal: PrincipalDependency) -> dict[str, Any]:
    """P1-06: Get self-evolution engine statistics."""
    enforce_scope(principal, "agent:read")
    return self_evolution_engine.get_stats()


@extended_router.get("/self-evolution/skills")
async def se_list_skills(principal: PrincipalDependency) -> list[dict[str, Any]]:
    """P1-06: List distilled reusable skills."""
    enforce_scope(principal, "agent:read")
    return [s.to_dict() for s in self_evolution_engine._skills]
