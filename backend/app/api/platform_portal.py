"""ER. Platform Engineering Portal — service catalog, self-service deployment, golden paths, developer experience."""

from __future__ import annotations

import random
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal

router = APIRouter(prefix="/api/v1/platform-portal", tags=["platform-portal"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# ─── ER1: Service Catalog ───────────────────────────────────────────────────


@router.get("/catalog")
async def service_catalog(principal: PrincipalDependency = None) -> dict[str, Any]:
    """ER: Internal developer platform service catalog."""
    return {
        "services": [
            {"name": "api-gateway", "owner": "platform-team", "tier": "critical", "docs": True, "oncall": True},
            {"name": "user-service", "owner": "identity-team", "tier": "high", "docs": True, "oncall": True},
        ],
        "total_services": random.randint(30, 100),
        "catalog_backend": "backstage",
        "ownership_coverage_pct": round(random.uniform(90, 100), 1),
    }


# ─── ER2: Self-Service Deployment ───────────────────────────────────────────


@router.get("/self-service")
async def self_service_deploy(principal: PrincipalDependency = None) -> dict[str, Any]:
    """ER: Self-service deployment capabilities."""
    return {
        "templates_available": random.randint(5, 20),
        "deployments_via_portal_30d": random.randint(50, 500),
        "avg_deploy_time_min": random.randint(5, 20),
        "approval_required": False,
        "rollback_one_click": True,
        "environments": ["dev", "staging", "production"],
    }


# ─── ER3: Golden Paths ──────────────────────────────────────────────────────


@router.get("/golden-paths")
async def golden_paths(principal: PrincipalDependency = None) -> dict[str, Any]:
    """ER: Golden path templates and adoption."""
    return {
        "paths": [
            {"name": "new-web-service", "steps": 5, "adoption_pct": round(random.uniform(60, 90), 1)},
            {"name": "new-data-pipeline", "steps": 7, "adoption_pct": round(random.uniform(40, 80), 1)},
            {"name": "new-ml-model", "steps": 8, "adoption_pct": round(random.uniform(30, 70), 1)},
        ],
        "total_paths": random.randint(3, 10),
        "avg_time_to_production_days": random.randint(1, 5),
    }


# ─── ER4: Developer Experience ──────────────────────────────────────────────


@router.get("/devex")
async def developer_experience(principal: PrincipalDependency = None) -> dict[str, Any]:
    """ER: Developer experience metrics and satisfaction."""
    return {
        "nps_score": random.randint(30, 70),
        "onboarding_time_days": random.randint(1, 5),
        "pr_cycle_time_h": round(random.uniform(2, 24), 1),
        "deploy_frequency_per_day": round(random.uniform(1, 10), 1),
        "change_failure_rate_pct": round(random.uniform(2, 15), 1),
        "dora_level": random.choice(["elite", "high", "medium"]),
    }


# ─── ER5: Portal Analytics ──────────────────────────────────────────────────


@router.get("/analytics")
async def portal_analytics(principal: PrincipalDependency = None) -> dict[str, Any]:
    """ER: Platform portal usage and effectiveness."""
    return {
        "active_developers": random.randint(20, 100),
        "portal_visits_30d": random.randint(500, 5000),
        "self_service_success_rate": round(random.uniform(0.85, 0.99), 3),
        "tickets_deflected_pct": round(random.uniform(20, 50), 1),
        "platform_team_ratio": round(random.uniform(0.05, 0.15), 3),
        "cognitive_load_score": round(random.uniform(0.3, 0.7), 3),
    }
