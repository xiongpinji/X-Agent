"""Compatibility endpoints for frontend commercial feature probes.

These endpoints keep the frontend/backend contract mounted while the deeper
commercial feature implementations continue to evolve. They are authenticated
read endpoints only; mutating feature APIs stay in their dedicated routers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from backend.app.core.security import Principal
from backend.app.dependencies import require_authenticated_principal
from backend.app.models.forum import forum_store

PrincipalDependency = Annotated[Principal, Depends(require_authenticated_principal)]

router = APIRouter(
    prefix="/api/v1",
    tags=["frontend-commercial-contract"],
)


@router.get("/analytics/realtime")
async def analytics_realtime(principal: PrincipalDependency) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    return {
        "timestamp": now,
        "tenant_id": principal.tenant_id,
        "active_users": 0,
        "active_sessions": 0,
        "api_calls_per_minute": 0.0,
        "tokens_per_minute": 0,
        "error_rate": 0.0,
        "avg_response_time_ms": 0.0,
        "current_throughput": 0.0,
    }


@router.get("/analytics/costs")
async def analytics_costs(principal: PrincipalDependency) -> dict[str, Any]:
    return {
        "tenant_id": principal.tenant_id,
        "total_cost_usd": 0.0,
        "cost_by_model": {},
        "cost_by_feature": {},
        "cost_by_user": {},
        "cost_trend": 0.0,
    }


@router.get("/analytics/performance")
async def analytics_performance(principal: PrincipalDependency) -> dict[str, Any]:
    return {
        "tenant_id": principal.tenant_id,
        "avg_response_time_ms": 0.0,
        "p95_response_time_ms": 0.0,
        "p99_response_time_ms": 0.0,
        "error_rate": 0.0,
        "success_rate": 1.0,
        "throughput_rps": 0.0,
        "slow_endpoints": [],
    }


@router.get("/marketplace/plugins")
async def marketplace_plugins(principal: PrincipalDependency) -> dict[str, Any]:
    return {"tenant_id": principal.tenant_id, "plugins": [], "total": 0}


@router.get("/marketplace/skills")
async def marketplace_skills(principal: PrincipalDependency) -> dict[str, Any]:
    return {"tenant_id": principal.tenant_id, "skills": [], "total": 0}


@router.get("/marketplace/templates")
async def marketplace_templates(principal: PrincipalDependency) -> dict[str, Any]:
    return {"tenant_id": principal.tenant_id, "templates": [], "total": 0}


@router.get("/templates")
async def templates_list(principal: PrincipalDependency) -> dict[str, Any]:
    return {
        "tenant_id": principal.tenant_id,
        "total": 0,
        "limit": 20,
        "offset": 0,
        "templates": [],
    }


@router.get("/sessions")
async def sessions_list(principal: PrincipalDependency) -> dict[str, Any]:
    return {
        "tenant_id": principal.tenant_id,
        "sessions": [],
        "total_count": 0,
    }


@router.get("/skills")
async def skills_list(principal: PrincipalDependency) -> dict[str, Any]:
    return {
        "tenant_id": principal.tenant_id,
        "success": True,
        "skills": [],
        "count": 0,
    }


@router.get("/creative/projects")
async def creative_projects(principal: PrincipalDependency) -> dict[str, Any]:
    return {
        "tenant_id": principal.tenant_id,
        "projects": [],
        "total": 0,
    }


@router.get("/billing/plans")
async def billing_plans(principal: PrincipalDependency) -> list[dict[str, Any]]:
    return []


@router.get("/forum/posts")
async def forum_posts(
    principal: PrincipalDependency,
    category: str | None = None,
    tag: str | None = None,
    sort_by: str = "created_at",
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    posts, total = forum_store.list_posts(
        category=category,
        tag=tag,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
    )
    return {
        "data": [post.model_dump() for post in posts],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/forum/posts/{post_id}")
async def forum_post_detail(post_id: str, principal: PrincipalDependency) -> dict[str, Any]:
    post = forum_store.get_post(post_id)
    if post is None:
        return {"id": post_id, "found": False, "comments": []}
    return post.model_dump()
