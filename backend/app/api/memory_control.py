from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/memory-control", tags=["memory-control"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.get("/overview")
async def get_memory_overview(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "memory:read")
    return {
        "resource_type": "memory_center_overview",
        "resource_id": principal.session_id or principal.user_id,
        "primary": {
            "total_memories": 126,
            "active_memories": 88,
            "archived_memories": 38,
            "referenced_memories": 52,
            "risk_level": "low",
        },
        "linked_summaries": {
            "memories": {"summary": {"title": "memory inventory"}, "data": {"count": 126, "active": 88, "archived": 38}},
            "experiences": {"summary": {"title": "experience library"}, "data": {"count": 24, "active": 18}},
            "references": {"summary": {"title": "reference graph"}, "data": {"count": 52, "healthy": 49}},
            "history": {"summary": {"title": "memory history"}, "data": {"count": 210, "last_24h": 11}},
        },
    }


@router.get("/detail/{memory_id}")
async def get_memory_detail(memory_id: str, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "memory:read")
    return {
        "resource_type": "memory_detail",
        "resource_id": memory_id,
        "primary": {
            "memory_id": memory_id,
            "memory_title": f"memory-{memory_id}",
            "status": "active",
            "source": "execution_result",
            "owner": principal.agent_id or principal.user_id,
            "risk_level": "low",
            "summary": "执行结果沉淀为记忆条目。",
        },
        "linked_summaries": {
            "experiences": {"summary": {"title": "experience links"}, "data": {"count": 3, "status": "available"}},
            "references": {"summary": {"title": "reference links"}, "data": {"count": 5, "status": "available"}},
            "history": {"summary": {"title": "memory trail"}, "data": {"count": 9, "last_status": "updated"}},
            "audit": {"summary": {"title": "audit trail"}, "data": {"count": 4}},
        },
    }


@router.get("/management")
async def get_memory_management(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "memory:read")
    return {
        "resource_type": "memory_center_management",
        "resource_id": principal.session_id or principal.user_id,
        "primary": {
            "pending_changes": 3,
            "active_changes": 2,
            "archived_changes": 1,
            "review_required": 1,
            "risk_level": "medium",
        },
        "linked_summaries": {
            "memories": {"summary": {"title": "memory review"}, "data": {"pending": 3, "needs_review": 1}},
            "experiences": {"summary": {"title": "experience review"}, "data": {"pending": 2, "needs_review": 1}},
            "references": {"summary": {"title": "reference review"}, "data": {"pending": 1, "needs_review": 0}},
            "history": {"summary": {"title": "change history"}, "data": {"count": 13}},
        },
    }


@router.get("/history")
async def get_memory_history(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "memory:read")
    return {
        "resource_type": "memory_center_history",
        "resource_id": principal.session_id or principal.user_id,
        "primary": {
            "total_events": 210,
            "success_events": 198,
            "failed_events": 12,
            "last_event_status": "updated",
            "risk_level": "low",
        },
        "linked_summaries": {
            "memories": {"summary": {"title": "memory events"}, "data": {"count": 126}},
            "experiences": {"summary": {"title": "experience events"}, "data": {"count": 24}},
            "references": {"summary": {"title": "reference events"}, "data": {"count": 52}},
            "history": {"summary": {"title": "memory history"}, "data": {"count": 210, "last_24h": 11}},
        },
    }
