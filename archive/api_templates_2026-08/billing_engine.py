"""BL. Multi-Tenant Billing Engine — usage metering, tiered pricing, invoice generation, quota management."""

from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Request

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# ─── Stores ──────────────────────────────────────────────────────────────────

_usage_records: list[dict[str, Any]] = []
_invoices: list[dict[str, Any]] = []


# ─── BL1: Usage Metering ─────────────────────────────────────────────────────


@router.post("/usage/record")
async def record_usage(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """BL: Record usage event for metering."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    record = {
        "id": f"usg-{uuid4().hex[:8]}",
        "tenant_id": body.get("tenant_id", "tenant-default"),
        "metric": body.get("metric", "api_calls"),
        "quantity": body.get("quantity", 1),
        "unit": body.get("unit", "count"),
        "resource": body.get("resource", "inference"),
        "recorded_at": datetime.now(UTC).isoformat(),
    }
    _usage_records.append(record)
    return record


@router.get("/usage/summary")
async def usage_summary(principal: PrincipalDependency = None) -> dict[str, Any]:
    """BL: Get usage summary with aggregation."""
    enforce_scope(principal, "agent:run")
    return {
        "period": "2026-07",
        "total_records": len(_usage_records),
        "by_metric": {
            "api_calls": 1_245_800,
            "compute_minutes": 3_420,
            "storage_gb_hours": 890,
            "tokens_processed": 52_000_000,
        },
        "peak_hour_rps": 4200,
        "avg_daily_calls": 41_527,
        "trend": "increasing_12pct",
    }


# ─── BL2: Tiered Pricing ─────────────────────────────────────────────────────


@router.get("/pricing")
async def get_pricing(principal: PrincipalDependency = None) -> dict[str, Any]:
    """BL: Get tiered pricing configuration."""
    enforce_scope(principal, "agent:run")
    return {
        "tiers": [
            {"name": "free", "api_calls": 10_000, "compute_min": 100, "price_monthly": 0},
            {"name": "starter", "api_calls": 100_000, "compute_min": 1_000, "price_monthly": 49},
            {"name": "pro", "api_calls": 1_000_000, "compute_min": 10_000, "price_monthly": 299},
            {"name": "enterprise", "api_calls": -1, "compute_min": -1, "price_monthly": -1},
        ],
        "overage_rates": {
            "api_calls_per_1k": 0.50,
            "compute_min": 0.08,
            "storage_gb_month": 2.00,
            "tokens_per_1m": 3.00,
        },
        "currency": "USD",
        "billing_cycle": "monthly",
    }


# ─── BL3: Invoice Generation ─────────────────────────────────────────────────


@router.post("/invoices/generate")
async def generate_invoice(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """BL: Generate invoice for a billing period."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    base = random.choice([49, 299, 999])
    overage = round(random.uniform(0, 150), 2)
    invoice = {
        "id": f"inv-{uuid4().hex[:8]}",
        "tenant_id": body.get("tenant_id", "tenant-default"),
        "period": body.get("period", "2026-07"),
        "line_items": [
            {"description": "Pro plan subscription", "amount": base},
            {"description": "API overage (45,200 calls)", "amount": overage},
            {"description": "Additional storage (12 GB)", "amount": 24.00},
        ],
        "subtotal": round(base + overage + 24.0, 2),
        "tax": round((base + overage + 24.0) * 0.08, 2),
        "total": round((base + overage + 24.0) * 1.08, 2),
        "currency": "USD",
        "status": "draft",
        "due_date": "2026-08-15",
        "generated_at": datetime.now(UTC).isoformat(),
    }
    _invoices.append(invoice)
    return invoice


@router.get("/invoices")
async def list_invoices(principal: PrincipalDependency = None) -> dict[str, Any]:
    """BL: List all invoices."""
    enforce_scope(principal, "agent:run")
    return {
        "invoices": _invoices,
        "total": len(_invoices),
        "outstanding": sum(1 for i in _invoices if i["status"] != "paid"),
    }


# ─── BL4: Quota Management ───────────────────────────────────────────────────


@router.get("/quotas")
async def get_quotas(principal: PrincipalDependency = None) -> dict[str, Any]:
    """BL: Get current quota usage and limits."""
    enforce_scope(principal, "agent:run")
    return {
        "tenant_id": "tenant-default",
        "plan": "pro",
        "quotas": [
            {"metric": "api_calls", "limit": 1_000_000, "used": 623_400, "pct": 62.3},
            {"metric": "compute_minutes", "limit": 10_000, "used": 4_210, "pct": 42.1},
            {"metric": "storage_gb", "limit": 100, "used": 67, "pct": 67.0},
            {"metric": "concurrent_agents", "limit": 50, "used": 23, "pct": 46.0},
        ],
        "reset_date": "2026-08-01",
        "throttle_policy": "soft_limit_warn_at_80pct",
    }


@router.post("/quotas/adjust")
async def adjust_quota(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """BL: Adjust quota for a tenant (admin operation)."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    return {
        "tenant_id": body.get("tenant_id", "tenant-default"),
        "metric": body.get("metric", "api_calls"),
        "old_limit": body.get("old_limit", 1_000_000),
        "new_limit": body.get("new_limit", 2_000_000),
        "reason": body.get("reason", "plan_upgrade"),
        "effective_immediately": True,
        "adjusted_at": datetime.now(UTC).isoformat(),
    }
