from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/marketplace-control", tags=["marketplace-control"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.get("/overview")
async def get_marketplace_overview(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "market:read")
    return {
        "resource_type": "marketplace_center_overview",
        "resource_id": principal.session_id or principal.user_id,
        "primary": {
            "total_items": 42,
            "published_items": 28,
            "installed_items": 19,
            "pending_approvals": 4,
            "risk_level": "low",
        },
        "linked_summaries": {
            "market": {"summary": {"title": "market catalog"}, "data": {"count": 42, "published": 28}},
            "plugins": {"summary": {"title": "plugin catalog"}, "data": {"count": 18, "installed": 11}},
            "tools": {"summary": {"title": "tool catalog"}, "data": {"count": 24, "enabled": 16}},
            "history": {"summary": {"title": "release history"}, "data": {"count": 33, "last_24h": 5}},
        },
    }


@router.get("/detail/{item_id}")
async def get_marketplace_detail(item_id: str, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "market:read")
    return {
        "resource_type": "marketplace_detail",
        "resource_id": item_id,
        "primary": {
            "item_id": item_id,
            "item_name": f"item-{item_id}",
            "item_type": "plugin",
            "version": "1.0.0",
            "status": "published",
            "owner": principal.agent_id or principal.user_id,
            "risk_level": "low",
            "description": "能力市场条目详情。",
        },
        "linked_summaries": {
            "market": {"summary": {"title": "market details"}, "data": {"published": True}},
            "plugins": {"summary": {"title": "plugin dependencies"}, "data": {"count": 2, "healthy": 2}},
            "tools": {"summary": {"title": "tool dependencies"}, "data": {"count": 3, "healthy": 3}},
            "history": {"summary": {"title": "release trail"}, "data": {"count": 7}},
        },
    }


@router.get("/management")
async def get_marketplace_management(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "market:read")
    return {
        "resource_type": "marketplace_center_management",
        "resource_id": principal.session_id or principal.user_id,
        "primary": {
            "pending_changes": 4,
            "published_changes": 2,
            "installed_changes": 2,
            "review_required": 3,
            "risk_level": "medium",
        },
        "linked_summaries": {
            "market": {"summary": {"title": "market review"}, "data": {"pending": 4, "needs_review": 3}},
            "plugins": {"summary": {"title": "plugin review"}, "data": {"pending": 2, "needs_review": 1}},
            "tools": {"summary": {"title": "tool review"}, "data": {"pending": 2, "needs_review": 1}},
            "history": {"summary": {"title": "change history"}, "data": {"count": 11}},
        },
    }


@router.get("/history")
async def get_marketplace_history(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "market:read")
    return {
        "resource_type": "marketplace_center_history",
        "resource_id": principal.session_id or principal.user_id,
        "primary": {
            "total_events": 33,
            "success_events": 29,
            "failed_events": 4,
            "last_event_status": "published",
            "risk_level": "low",
        },
        "linked_summaries": {
            "market": {"summary": {"title": "market events"}, "data": {"count": 42}},
            "plugins": {"summary": {"title": "plugin events"}, "data": {"count": 18}},
            "tools": {"summary": {"title": "tool events"}, "data": {"count": 24}},
            "history": {"summary": {"title": "release trail"}, "data": {"count": 33, "last_24h": 5}},
        },
    }
