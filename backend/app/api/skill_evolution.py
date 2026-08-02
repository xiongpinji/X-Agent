"""Skill self-evolution API (P0-B).

Exposes the closed-loop skill evolution system (discover → generate →
evaluate → deploy → monitor → optimize) over REST. Shares the
``/api/v1/evolution`` prefix with the legacy GEPA endpoints but uses
distinct sub-paths.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.core.security import Principal
from backend.app.core.skill_evolution import PatternStatus, skill_evolution_system
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/evolution", tags=["skill-evolution"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# ─── Request / response models ────────────────────────────────────────────────


class InteractionIn(BaseModel):
    task_description: str = Field(..., min_length=1)
    tool_calls: list[str] = Field(default_factory=list)
    duration_ms: float = Field(default=0.0, ge=0.0)
    success: bool = True
    user_id: str = "anonymous"


class GenerateRequest(BaseModel):
    pattern_id: str | None = Field(default=None, description="Explicit pattern to generate from.")
    task_description: str | None = Field(default=None, description="Ad-hoc description to synthesize a pattern.")
    tool_calls: list[str] = Field(default_factory=list)
    auto_deploy: bool = Field(default=True, description="Evaluate and deploy if it passes.")


class UsageIn(BaseModel):
    success: bool
    latency_ms: float = Field(default=0.0, ge=0.0)
    satisfaction: float | None = Field(default=None, ge=0.0, le=1.0)


class LoopControlIn(BaseModel):
    interval_seconds: float = Field(default=3600.0, ge=60.0)


# ─── Discovery ────────────────────────────────────────────────────────────────


@router.post("/interactions")
async def record_interaction(
    principal: PrincipalDependency,
    req: InteractionIn,
) -> dict[str, Any]:
    """Feed a user interaction into the discovery engine."""
    enforce_scope(principal, "agent:write")
    record = skill_evolution_system.record_interaction(
        req.task_description, req.tool_calls, req.duration_ms, req.success, req.user_id
    )
    return {"status": "recorded", "signature": record.signature}


@router.get("/discovered")
async def list_discovered(
    principal: PrincipalDependency,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """List discovered task patterns (optionally filtered by lifecycle status)."""
    enforce_scope(principal, "agent:read")
    # Refresh scores from recorded interactions before listing.
    skill_evolution_system.discovery.analyze()
    pattern_status = PatternStatus(status) if status else None
    return [p.to_dict() for p in skill_evolution_system.discovery.list_patterns(pattern_status)]


# ─── Generation ───────────────────────────────────────────────────────────────


@router.post("/generate")
async def generate_skill(
    principal: PrincipalDependency,
    req: GenerateRequest,
) -> dict[str, Any]:
    """Trigger skill generation for a discovered (or ad-hoc) pattern."""
    enforce_scope(principal, "agent:write")
    system = skill_evolution_system

    pattern = None
    if req.pattern_id:
        pattern = next((p for p in system.store.patterns if p.id == req.pattern_id), None)
        if pattern is None:
            return {"status": "error", "reason": "pattern_not_found"}
    elif req.task_description:
        record = system.record_interaction(req.task_description, req.tool_calls,
                                           duration_ms=1000.0, success=True)
        # Build/refresh patterns and pick the one matching this signature.
        system.discovery.analyze()
        pattern = next((p for p in system.store.patterns if p.signature == record.signature), None)
    else:
        return {"status": "error", "reason": "pattern_id_or_task_description_required"}

    skill = await system.generator.generate(pattern)
    result: dict[str, Any] = {
        "status": "generated",
        "skill_id": skill.id,
        "name": skill.name,
        "version": skill.active_version,
        "source": skill.current.generation_source if skill.current else "template",
    }

    if req.auto_deploy:
        evaluation = await system.evaluator.evaluate(skill)
        result["evaluation"] = evaluation.to_dict()
        if evaluation.passed:
            from backend.app.core.skill_evolution import AuditAction, SkillStatus
            skill.status = SkillStatus.ACTIVE
            system.store.metrics.skills_deployed += 1
            system.store.audit(AuditAction.SKILL_DEPLOYED, skill_id=skill.id,
                               details={"version": skill.active_version,
                                        "success_rate": evaluation.success_rate})
            system.store.save()
            result["deployed"] = True
        else:
            result["deployed"] = False
    return result


# ─── Metrics & history ────────────────────────────────────────────────────────


@router.get("/metrics")
async def evolution_metrics(principal: PrincipalDependency) -> dict[str, Any]:
    """Aggregate evolution statistics."""
    enforce_scope(principal, "agent:read")
    return skill_evolution_system.get_metrics()


@router.get("/history")
async def evolution_history(
    principal: PrincipalDependency,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Evolution audit trail (most recent first)."""
    enforce_scope(principal, "agent:read")
    return skill_evolution_system.get_history(limit=limit)


# ─── Skills: list / detail / optimize / usage / deprecate ─────────────────────


@router.get("/skills/generated")
async def list_generated_skills(principal: PrincipalDependency) -> list[dict[str, Any]]:
    """List all skills produced by the evolution system."""
    enforce_scope(principal, "agent:read")
    return [s.to_dict() for s in skill_evolution_system.store.skills]


@router.post("/optimize/{skill_id}")
async def optimize_skill(
    principal: PrincipalDependency,
    skill_id: str,
    force: bool = False,
) -> dict[str, Any]:
    """Trigger optimization / refactor of a specific skill."""
    enforce_scope(principal, "agent:write")
    return await skill_evolution_system.optimizer.optimize(skill_id, force=force)


@router.post("/skills/{skill_id}/usage")
async def record_usage(
    principal: PrincipalDependency,
    skill_id: str,
    req: UsageIn,
) -> dict[str, Any]:
    """Record a skill usage outcome (feeds monitoring + auto-optimization)."""
    enforce_scope(principal, "agent:write")
    return skill_evolution_system.record_skill_usage(
        skill_id, req.success, req.latency_ms, req.satisfaction
    )


# ─── Loop control ─────────────────────────────────────────────────────────────


@router.post("/loop/run")
async def run_loop_cycle(principal: PrincipalDependency) -> dict[str, Any]:
    """Manually run a single Discover → Generate → Evaluate → Deploy → Optimize cycle."""
    enforce_scope(principal, "agent:write")
    return await skill_evolution_system.loop.run_cycle()


@router.post("/loop/start")
async def start_loop(
    principal: PrincipalDependency,
    req: LoopControlIn | None = None,
) -> dict[str, Any]:
    """Start the background evolution loop."""
    enforce_scope(principal, "agent:write")
    if req is not None:
        skill_evolution_system.loop.interval_seconds = req.interval_seconds
    started = skill_evolution_system.loop.start()
    return {"status": "started" if started else "already_running",
            "interval_seconds": skill_evolution_system.loop.interval_seconds}


@router.post("/loop/stop")
async def stop_loop(principal: PrincipalDependency) -> dict[str, Any]:
    """Stop the background evolution loop."""
    enforce_scope(principal, "agent:write")
    await skill_evolution_system.loop.stop()
    return {"status": "stopped"}
