from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/navigation-control", tags=["navigation-control"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.get("/overview")
async def get_navigation_overview(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "navigation:read")
    return {
        "resource_type": "navigation_center_overview",
        "resource_id": principal.session_id or principal.user_id,
        "primary": {
            "recent_pages": ["overview", "execution_overview", "tools_overview"],
            "favorite_pages": ["overview", "market_overview", "org_overview"],
            "search_enabled": True,
            "risk_level": "low",
        },
        "linked_summaries": {
            "recent": {"summary": {"title": "recent pages"}, "data": {"count": 3}},
            "favorites": {"summary": {"title": "favorite pages"}, "data": {"count": 3}},
            "search": {"summary": {"title": "search index"}, "data": {"count": 24, "available": True}},
            "shortcuts": {"summary": {"title": "quick shortcuts"}, "data": {"count": 6}},
        },
    }


@router.get("/search")
async def get_navigation_search(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "navigation:read")
    return {
        "resource_type": "navigation_center_search",
        "resource_id": principal.session_id or principal.user_id,
        "primary": {
            "query": "",
            "result_count": 12,
            "categories": ["page", "tool", "memory", "organization", "market"],
            "risk_level": "low",
        },
        "linked_summaries": {
            "recent": {"summary": {"title": "recent search"}, "data": {"count": 5}},
            "favorites": {"summary": {"title": "search filters"}, "data": {"count": 4}},
            "search": {"summary": {"title": "search results"}, "data": {"count": 12}},
            "shortcuts": {"summary": {"title": "result shortcuts"}, "data": {"count": 6}},
        },
    }


@router.get("/shortcuts")
async def get_navigation_shortcuts(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "navigation:read")
    return {
        "resource_type": "navigation_center_shortcuts",
        "resource_id": principal.session_id or principal.user_id,
        "primary": {
            "shortcut_count": 6,
            "favorite_count": 3,
            "recent_count": 3,
            "risk_level": "low",
        },
        "linked_summaries": {
            "recent": {"summary": {"title": "recent shortcuts"}, "data": {"count": 3}},
            "favorites": {"summary": {"title": "favorite shortcuts"}, "data": {"count": 3}},
            "search": {"summary": {"title": "search shortcuts"}, "data": {"count": 12}},
            "shortcuts": {"summary": {"title": "quick actions"}, "data": {"count": 6}},
        },
    }
