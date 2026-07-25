"""Tenant Quota & Usage API endpoints.

Provides:
- GET  /api/v1/tenant/quota  — current tenant's quota limits + usage
- PUT  /api/v1/tenant/quota  — update quota limits (admin only)
- GET  /api/v1/tenant/usage  — detailed usage breakdown
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.core.security import Principal
from backend.app.core.tenant_quota import QuotaLimits, get_tenant_quota_manager
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/tenant", tags=["tenant-quota"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# ─── Request/Response Models ────────────────────────────────────────────────────


class QuotaLimitsUpdate(BaseModel):
    """Request body for updating tenant quota limits."""

    max_agents: int | None = Field(None, ge=0, description="Max agents allowed")
    max_workflows: int | None = Field(None, ge=0, description="Max workflows allowed")
    max_api_calls_per_day: int | None = Field(None, ge=0, description="Max API calls per day")
    max_memory_items: int | None = Field(None, ge=0, description="Max memory items")
    max_concurrent_runs: int | None = Field(None, ge=0, description="Max concurrent runs")
    max_storage_mb: int | None = Field(None, ge=0, description="Max storage in MB")


# ─── Endpoints ──────────────────────────────────────────────────────────────────


@router.get("/quota")
async def get_tenant_quota(principal: PrincipalDependency) -> dict[str, Any]:
    """Get current tenant's quota limits and usage summary.

    Returns the full quota report including limits, current usage, and
    per-resource breakdown with remaining capacity and usage percentages.
    """
    manager = get_tenant_quota_manager()
    report = manager.get_full_report(principal.tenant_id)
    return report


@router.put("/quota")
async def update_tenant_quota(
    body: QuotaLimitsUpdate,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Update quota limits for the current tenant (admin only).

    Only provided fields are updated; omitted fields retain their current values.
    Requires 'security:manage' scope (admin role).
    """
    enforce_scope(principal, "security:manage")
    manager = get_tenant_quota_manager()

    current = manager.get_limits(principal.tenant_id)
    # Merge: only override fields that were explicitly provided
    updated = QuotaLimits(
        max_agents=body.max_agents if body.max_agents is not None else current.max_agents,
        max_workflows=body.max_workflows if body.max_workflows is not None else current.max_workflows,
        max_api_calls_per_day=body.max_api_calls_per_day if body.max_api_calls_per_day is not None else current.max_api_calls_per_day,
        max_memory_items=body.max_memory_items if body.max_memory_items is not None else current.max_memory_items,
        max_concurrent_runs=body.max_concurrent_runs if body.max_concurrent_runs is not None else current.max_concurrent_runs,
        max_storage_mb=body.max_storage_mb if body.max_storage_mb is not None else current.max_storage_mb,
    )
    manager.set_limits(principal.tenant_id, updated)

    return {
        "tenant_id": principal.tenant_id,
        "limits": {
            "max_agents": updated.max_agents,
            "max_workflows": updated.max_workflows,
            "max_api_calls_per_day": updated.max_api_calls_per_day,
            "max_memory_items": updated.max_memory_items,
            "max_concurrent_runs": updated.max_concurrent_runs,
            "max_storage_mb": updated.max_storage_mb,
        },
        "message": "Quota limits updated successfully",
    }


@router.get("/usage")
async def get_tenant_usage_detail(principal: PrincipalDependency) -> dict[str, Any]:
    """Get detailed usage breakdown for the current tenant.

    Returns per-resource usage with limits, remaining capacity, and
    percentage utilization for capacity planning.
    """
    manager = get_tenant_quota_manager()
    report = manager.get_full_report(principal.tenant_id)

    # Return a focused usage view
    return {
        "tenant_id": principal.tenant_id,
        "usage": report["usage"],
        "breakdown": report["breakdown"],
    }
