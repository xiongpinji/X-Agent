from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.core.evolution import evolution_store
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/evolution", tags=["evolution"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


class EvolutionSummaryResponse(BaseModel):
    reflections: int
    learnings: int
    capabilities: int


@router.get("/summary", response_model=EvolutionSummaryResponse)
async def get_evolution_summary(principal: PrincipalDependency, agent_id: str | None = None) -> EvolutionSummaryResponse:
    enforce_scope(principal, "agent:read")
    return EvolutionSummaryResponse(
        reflections=len(evolution_store.list_reflections(agent_id=agent_id)),
        learnings=len(evolution_store.list_learnings(agent_id=agent_id)),
        capabilities=len(evolution_store.list_capabilities(agent_id=agent_id)),
    )


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
