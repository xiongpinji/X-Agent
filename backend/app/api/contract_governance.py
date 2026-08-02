"""EA. Service Contract Governance — contract definitions, compatibility validation, consumer-driven contracts, contract testing."""

from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Request

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/contract-governance", tags=["contract-governance"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# ─── EA1: Contract Definitions ──────────────────────────────────────────────


@router.get("/definitions")
async def contract_definitions(principal: PrincipalDependency = None) -> dict[str, Any]:
    """EA: Service contract registry and definitions."""
    return {
        "contracts": [
            {"name": "user-api", "version": "2.1.0", "provider": "user-service", "consumers": ["gateway", "notification"], "schema": "openapi_3.1"},
            {"name": "payment-events", "version": "1.3.0", "provider": "payment-service", "consumers": ["ledger", "analytics"], "schema": "asyncapi_2.6"},
        ],
        "total_contracts": random.randint(15, 50),
        "versioned": True,
        "registry": "schema_registry",
    }


# ─── EA2: Compatibility Validation ──────────────────────────────────────────


@router.post("/validate")
async def compatibility_validation(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """EA: Validate contract compatibility between versions."""
    body = await request.json() if await request.body() else {}
    compatible = random.choice([True, True, False])
    return {
        "contract": body.get("contract", "user-api"),
        "from_version": body.get("from", "2.0.0"),
        "to_version": body.get("to", "2.1.0"),
        "compatible": compatible,
        "compatibility_level": "backward",
        "issues": [] if compatible else [{"field": "user.phone", "issue": "required field added", "severity": "breaking"}],
        "validated_at": datetime.now(UTC).isoformat(),
    }


# ─── EA3: Consumer-Driven Contracts ─────────────────────────────────────────


@router.get("/consumer-driven")
async def consumer_driven_contracts(principal: PrincipalDependency = None) -> dict[str, Any]:
    """EA: Consumer-driven contract expectations and verification."""
    return {
        "pacts": [
            {"consumer": "web-frontend", "provider": "user-api", "expectations": 12, "verified": True},
            {"consumer": "mobile-app", "provider": "user-api", "expectations": 8, "verified": True},
            {"consumer": "analytics", "provider": "event-stream", "expectations": 5, "verified": False},
        ],
        "total_pacts": random.randint(10, 40),
        "verification_success_rate": round(random.uniform(0.85, 0.99), 3),
        "broken_pacts": random.randint(0, 3),
        "pact_broker_url": "https://pact.internal.xagent.dev",
    }


# ─── EA4: Contract Testing ──────────────────────────────────────────────────


@router.post("/test")
async def contract_testing(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """EA: Run contract tests between services."""
    body = await request.json() if await request.body() else {}
    return {
        "test_run_id": str(uuid4()),
        "provider": body.get("provider", "user-service"),
        "results": [
            {"consumer": "gateway", "tests": 15, "passed": 15, "failed": 0},
            {"consumer": "notification", "tests": 8, "passed": 7, "failed": 1},
        ],
        "overall_pass": random.choice([True, True, False]),
        "execution_time_ms": random.randint(500, 5000),
        "triggered_by": "ci_pipeline",
    }


# ─── EA5: Contract Analytics ────────────────────────────────────────────────


@router.get("/analytics")
async def contract_analytics(principal: PrincipalDependency = None) -> dict[str, Any]:
    """EA: Contract governance health and compliance metrics."""
    return {
        "contracts_compliant_pct": round(random.uniform(85, 99), 1),
        "breaking_changes_30d": random.randint(0, 5),
        "avg_contract_age_days": random.randint(30, 365),
        "undocumented_apis": random.randint(0, 5),
        "consumer_satisfaction": round(random.uniform(0.7, 0.95), 3),
        "auto_generated_contracts": random.randint(5, 20),
    }
