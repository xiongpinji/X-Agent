from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/tools-control", tags=["tools-control"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.get("/overview")
async def get_tools_overview(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "tools:read")
    return {
        "resource_type": "tools_center_overview",
        "resource_id": principal.session_id or principal.user_id,
        "primary": {
            "total_tools": 18,
            "enabled_tools": 14,
            "disabled_tools": 4,
            "plugin_count": 6,
            "resource_count": 9,
            "risk_level": "low",
        },
        "linked_summaries": {
            "tools": {"summary": {"title": "tools manifest"}, "data": {"count": 18, "enabled": 14, "disabled": 4}},
            "plugins": {"summary": {"title": "plugins manifest"}, "data": {"count": 6, "enabled": 5}},
            "resources": {"summary": {"title": "resources inventory"}, "data": {"count": 9, "status": "healthy"}},
            "history": {"summary": {"title": "tool history"}, "data": {"count": 42, "last_24h": 7}},
        },
    }


@router.get("/detail/{tool_id}")
async def get_tool_detail(tool_id: str, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "tools:read")
    return {
        "resource_type": "tool_detail",
        "resource_id": tool_id,
        "primary": {
            "tool_id": tool_id,
            "tool_name": f"tool-{tool_id}",
            "status": "enabled",
            "version": "1.0.0",
            "owner": principal.agent_id or principal.user_id,
            "risk_level": "low",
            "description": "工具详情与调用概览。",
        },
        "linked_summaries": {
            "history": {"summary": {"title": "execution history"}, "data": {"count": 12, "last_status": "success"}},
            "plugins": {"summary": {"title": "plugin bindings"}, "data": {"count": 2, "enabled": 2}},
            "resources": {"summary": {"title": "resource bindings"}, "data": {"count": 3, "healthy": 3}},
            "audit": {"summary": {"title": "audit trail"}, "data": {"count": 5}},
        },
    }


@router.get("/management")
async def get_tools_management(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "tools:read")
    return {
        "resource_type": "tools_center_management",
        "resource_id": principal.session_id or principal.user_id,
        "primary": {
            "pending_changes": 2,
            "enabled_changes": 1,
            "disabled_changes": 1,
            "review_required": 1,
            "risk_level": "medium",
        },
        "linked_summaries": {
            "tools": {"summary": {"title": "tools review"}, "data": {"pending": 2, "needs_review": 1}},
            "plugins": {"summary": {"title": "plugins review"}, "data": {"pending": 1, "needs_review": 1}},
            "resources": {"summary": {"title": "resources review"}, "data": {"pending": 1, "needs_review": 0}},
            "history": {"summary": {"title": "change history"}, "data": {"count": 8}},
        },
    }


@router.get("/history")
async def get_tools_history(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "tools:read")
    return {
        "resource_type": "tools_center_history",
        "resource_id": principal.session_id or principal.user_id,
        "primary": {
            "total_events": 42,
            "success_events": 35,
            "failed_events": 7,
            "last_event_status": "success",
            "risk_level": "low",
        },
        "linked_summaries": {
            "tools": {"summary": {"title": "tool events"}, "data": {"count": 18}},
            "plugins": {"summary": {"title": "plugin events"}, "data": {"count": 6}},
            "resources": {"summary": {"title": "resource events"}, "data": {"count": 9}},
            "history": {"summary": {"title": "execution history"}, "data": {"count": 42, "last_24h": 7}},
        },
    }
