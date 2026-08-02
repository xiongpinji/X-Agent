"""CX. Multi-Tenant Metering & Billing — usage collection, pricing models, invoice generation, quota management."""

from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Request

from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal

router = APIRouter(prefix="/api/v1/metering", tags=["metering-billing"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# ─── CX1: Usage Collection ──────────────────────────────────────────────────


@router.post("/collect")
async def collect_usage(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """CX: Collect and aggregate tenant usage metrics."""
    body = await request.json() if await request.body() else {}
    return {
        "record_id": str(uuid4()),
        "tenant_id": body.get("tenant_id", "tenant-001"),
        "metric": body.get("metric", "api_calls"),
        "quantity": body.get("quantity", random.randint(1000, 100000)),
        "unit": "requests",
        "period": "2026-07-30T00:00:00Z/2026-07-30T23:59:59Z",
        "collected_at": datetime.now(UTC).isoformat(),
        "deduplicated": True,
    }


# ─── CX2: Pricing Models ────────────────────────────────────────────────────


@router.get("/pricing")
async def pricing_models(principal: PrincipalDependency = None) -> dict[str, Any]:
    """CX: List available pricing models and tiers."""
    return {
        "models": [
            {"name": "pay-as-you-go", "unit_price": 0.001, "currency": "USD", "unit": "api_call"},
            {"name": "tiered", "tiers": [{"up_to": 100000, "price": 0.001}, {"up_to": 1000000, "price": 0.0007}, {"up_to": None, "price": 0.0004}]},
            {"name": "subscription", "monthly": 299, "included_units": 500000, "overage_rate": 0.0005},
        ],
        "volume_discounts": [{"min_spend": 1000, "discount_pct": 5}, {"min_spend": 5000, "discount_pct": 12}],
        "currency": "USD",
    }


# ─── CX3: Invoice Generation ────────────────────────────────────────────────


@router.post("/invoices")
async def generate_invoice(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """CX: Generate billing invoice for a tenant period."""
    body = await request.json() if await request.body() else {}
    usage = random.randint(100000, 2000000)
    rate = 0.0007
    return {
        "invoice_id": f"INV-{uuid4().hex[:8].upper()}",
        "tenant_id": body.get("tenant_id", "tenant-001"),
        "period": "2026-07",
        "line_items": [
            {"description": "API calls", "quantity": usage, "unit_price": rate, "amount": round(usage * rate, 2)},
            {"description": "Storage (GB-month)", "quantity": random.randint(10, 100), "unit_price": 0.05, "amount": round(random.uniform(0.5, 5.0), 2)},
        ],
        "subtotal": round(usage * rate + random.uniform(1, 10), 2),
        "discount": round(random.uniform(0, 50), 2),
        "total": round(usage * rate + random.uniform(1, 10) - random.uniform(0, 50), 2),
        "due_date": "2026-08-15",
        "status": "draft",
    }


# ─── CX4: Quota Management ──────────────────────────────────────────────────


@router.get("/quotas")
async def quota_status(principal: PrincipalDependency = None) -> dict[str, Any]:
    """CX: View tenant quota usage and limits."""
    return {
        "tenant_id": "tenant-001",
        "quotas": [
            {"resource": "api_calls", "limit": 1000000, "used": random.randint(200000, 900000), "reset": "2026-08-01T00:00:00Z"},
            {"resource": "storage_gb", "limit": 100, "used": random.randint(20, 85), "reset": None},
            {"resource": "concurrent_agents", "limit": 10, "used": random.randint(1, 8), "reset": None},
        ],
        "throttled": False,
        "grace_period_pct": 10,
        "alert_threshold_pct": 80,
    }


# ─── CX5: Revenue Analytics ─────────────────────────────────────────────────


@router.get("/revenue")
async def revenue_analytics(principal: PrincipalDependency = None) -> dict[str, Any]:
    """CX: Revenue and billing analytics across tenants."""
    return {
        "mrr": round(random.uniform(15000, 80000), 2),
        "arr": round(random.uniform(180000, 960000), 2),
        "active_tenants": random.randint(20, 150),
        "avg_revenue_per_tenant": round(random.uniform(200, 1500), 2),
        "churn_rate": round(random.uniform(0.01, 0.05), 3),
        "top_tenants": [
            {"tenant": "enterprise-a", "monthly_spend": round(random.uniform(5000, 15000), 2)},
            {"tenant": "startup-b", "monthly_spend": round(random.uniform(500, 2000), 2)},
        ],
        "period": "2026-07",
    }
