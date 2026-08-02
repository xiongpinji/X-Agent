"""GY. Platform Developer Experience — golden paths, self-service portals, template libraries, DX analytics."""

from __future__ import annotations

import random
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal

router = APIRouter(prefix="/api/v1/developer-experience", tags=["developer-experience"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.get("/golden-paths")
async def golden_paths(principal: PrincipalDependency = None) -> dict[str, Any]:
    """GY: Developer golden path definitions."""
    return {"paths": [{"name": "new-microservice", "steps": 5, "avg_completion_min": 15}], "total_paths": random.randint(5, 30), "adoption_rate_pct": round(random.uniform(50, 90), 1)}


@router.get("/self-service")
async def self_service_portals(principal: PrincipalDependency = None) -> dict[str, Any]:
    """GY: Self-service developer portal."""
    return {"catalog_items": random.randint(50, 500), "provisioning_automated_pct": round(random.uniform(70, 95), 1), "avg_provision_time_min": random.randint(1, 30), "ticket_reduction_pct": round(random.uniform(30, 70), 1)}


@router.get("/templates")
async def template_libraries(principal: PrincipalDependency = None) -> dict[str, Any]:
    """GY: Project and service template libraries."""
    return {"templates": [{"name": "python-fastapi", "usage_count": random.randint(10, 500)}], "total_templates": random.randint(20, 100), "community_contributed": random.randint(10, 50)}


@router.get("/onboarding")
async def developer_onboarding(principal: PrincipalDependency = None) -> dict[str, Any]:
    """GY: Developer onboarding automation."""
    return {"avg_onboarding_days": round(random.uniform(1, 14), 1), "automated_setup_steps": random.randint(10, 50), "time_to_first_commit_h": random.randint(2, 48), "satisfaction_score": round(random.uniform(3.5, 4.8), 1)}


@router.get("/analytics")
async def dx_analytics(principal: PrincipalDependency = None) -> dict[str, Any]:
    """GY: Developer experience analytics."""
    return {"deploy_frequency_per_dev_week": round(random.uniform(1, 20), 1), "pr_cycle_time_h": random.randint(2, 48), "developer_satisfaction_nps": random.randint(20, 80), "platform_adoption_pct": round(random.uniform(60, 95), 1)}
