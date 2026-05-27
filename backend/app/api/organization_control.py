from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/organization-control", tags=["organization-control"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.get("/overview")
async def get_organization_overview(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "org:read")
    return {
        "resource_type": "organization_center_overview",
        "resource_id": principal.session_id or principal.user_id,
        "primary": {
            "total_departments": 8,
            "total_roles": 24,
            "total_members": 86,
            "pending_reviews": 3,
            "risk_level": "low",
        },
        "linked_summaries": {
            "organization": {"summary": {"title": "organization profile"}, "data": {"name": "统一控制台"}},
            "departments": {"summary": {"title": "department tree"}, "data": {"count": 8, "active": 7}},
            "roles": {"summary": {"title": "role matrix"}, "data": {"count": 24, "enabled": 21}},
            "audits": {"summary": {"title": "org audit"}, "data": {"count": 13, "pending": 3}},
        },
    }


@router.get("/structure")
async def get_organization_structure(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "org:read")
    return {
        "resource_type": "organization_center_structure",
        "resource_id": principal.session_id or principal.user_id,
        "primary": {
            "root_name": "统一控制台",
            "department_count": 8,
            "member_count": 86,
            "role_count": 24,
            "risk_level": "low",
        },
        "linked_summaries": {
            "organization": {"summary": {"title": "organization tree"}, "data": {"nodes": 18, "edges": 17}},
            "departments": {"summary": {"title": "department tree"}, "data": {"nodes": 8, "edges": 7}},
            "roles": {"summary": {"title": "role bindings"}, "data": {"nodes": 24, "edges": 42}},
            "audits": {"summary": {"title": "structure audit"}, "data": {"count": 6}},
        },
    }


@router.get("/roles")
async def get_organization_roles(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "org:read")
    return {
        "resource_type": "organization_center_roles",
        "resource_id": principal.session_id or principal.user_id,
        "primary": {
            "total_roles": 24,
            "active_roles": 21,
            "pending_roles": 3,
            "permission_sets": 12,
            "risk_level": "medium",
        },
        "linked_summaries": {
            "organization": {"summary": {"title": "organization profile"}, "data": {"name": "统一控制台"}},
            "departments": {"summary": {"title": "department overview"}, "data": {"count": 8}},
            "roles": {"summary": {"title": "role matrix"}, "data": {"count": 24, "active": 21}},
            "audits": {"summary": {"title": "role audit"}, "data": {"count": 13, "pending": 3}},
        },
    }


@router.get("/audit")
async def get_organization_audit(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "org:read")
    return {
        "resource_type": "organization_center_audit",
        "resource_id": principal.session_id or principal.user_id,
        "primary": {
            "total_events": 13,
            "success_events": 10,
            "failed_events": 3,
            "last_event_status": "pending",
            "risk_level": "medium",
        },
        "linked_summaries": {
            "organization": {"summary": {"title": "organization audit"}, "data": {"count": 13}},
            "departments": {"summary": {"title": "department audit"}, "data": {"count": 8}},
            "roles": {"summary": {"title": "role audit"}, "data": {"count": 24}},
            "audits": {"summary": {"title": "audit trail"}, "data": {"count": 13, "pending": 3}},
        },
    }
