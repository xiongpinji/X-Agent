"""X. Commercial Billing Engine — metering, subscriptions, invoices, payment webhooks."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Request

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# ─── In-memory stores (replace with DB in production) ────────────────────────

_usage_records: list[dict[str, Any]] = []
_subscriptions: dict[str, dict[str, Any]] = {}
_invoices: list[dict[str, Any]] = []

# ─── Plan definitions ────────────────────────────────────────────────────────

PLANS: dict[str, dict[str, Any]] = {
    "free": {
        "name": "Free",
        "price_monthly": 0,
        "price_yearly": 0,
        "limits": {"agent_runs": 100, "tokens": 50_000, "workflows": 3, "seats": 1},
        "features": ["basic_agents", "community_support"],
    },
    "pro": {
        "name": "Pro",
        "price_monthly": 29,
        "price_yearly": 290,
        "limits": {"agent_runs": 5_000, "tokens": 2_000_000, "workflows": 50, "seats": 5},
        "features": ["advanced_agents", "parallel_execution", "priority_support", "custom_workflows"],
    },
    "team": {
        "name": "Team",
        "price_monthly": 99,
        "price_yearly": 990,
        "limits": {"agent_runs": 50_000, "tokens": 20_000_000, "workflows": 500, "seats": 25},
        "features": ["all_pro", "rbac", "audit_log", "sso", "sla_99_9"],
    },
    "enterprise": {
        "name": "Enterprise",
        "price_monthly": -1,
        "price_yearly": -1,
        "limits": {"agent_runs": -1, "tokens": -1, "workflows": -1, "seats": -1},
        "features": ["all_team", "dedicated_infra", "custom_models", "on_premise", "dedicated_support"],
    },
}


# ─── X1: Plans & Pricing ─────────────────────────────────────────────────────


@router.get("/plans")
async def list_plans(principal: PrincipalDependency = None) -> dict[str, Any]:
    """List all available subscription plans with pricing and limits."""
    enforce_scope(principal, "agent:run")
    return {
        "plans": PLANS,
        "currency": "USD",
        "billing_intervals": ["monthly", "yearly"],
        "yearly_discount_pct": 17,
    }


# ─── X2: Usage Metering ──────────────────────────────────────────────────────


@router.post("/meter")
async def record_usage(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """Record a metered usage event (agent run, token consumption, API call)."""
    enforce_scope(principal, "agent:run")
    body = await request.json()

    record = {
        "id": str(uuid4()),
        "tenant_id": principal.tenant_id,
        "user_id": principal.user_id,
        "metric": body.get("metric", "agent_run"),
        "quantity": body.get("quantity", 1),
        "metadata": body.get("metadata", {}),
        "timestamp": datetime.now(UTC).isoformat(),
    }
    _usage_records.append(record)

    return {"recorded": True, "usage_id": record["id"], "metric": record["metric"]}


@router.get("/meter/summary")
async def get_usage_summary(principal: PrincipalDependency = None) -> dict[str, Any]:
    """Aggregated usage summary for current billing period."""
    enforce_scope(principal, "agent:run")

    tenant_records = [r for r in _usage_records if r["tenant_id"] == principal.tenant_id]

    metrics: dict[str, int] = {}
    for r in tenant_records:
        m = r["metric"]
        metrics[m] = metrics.get(m, 0) + r["quantity"]

    unit_prices = {"agent_run": 0.01, "token": 0.000002, "api_call": 0.001, "workflow_run": 0.05}
    cost_breakdown = {m: round(qty * unit_prices.get(m, 0.001), 4) for m, qty in metrics.items()}
    total_cost = round(sum(cost_breakdown.values()), 2)

    return {
        "tenant_id": principal.tenant_id,
        "period": datetime.now(UTC).strftime("%Y-%m"),
        "metrics": metrics,
        "cost_breakdown": cost_breakdown,
        "total_usage_cost": total_cost,
        "currency": "USD",
        "record_count": len(tenant_records),
    }


# ─── X3: Subscription Management ────────────────────────────────────────────


@router.get("/subscription")
async def get_subscription(principal: PrincipalDependency = None) -> dict[str, Any]:
    """Get current subscription status for tenant."""
    enforce_scope(principal, "agent:run")

    sub = _subscriptions.get(principal.tenant_id)
    if sub is None:
        return {
            "tenant_id": principal.tenant_id,
            "plan": "free",
            "status": "active",
            "started_at": None,
            "renews_at": None,
            "auto_renew": False,
            "plan_details": PLANS["free"],
        }
    return {**sub, "plan_details": PLANS.get(sub["plan"], PLANS["free"])}


@router.post("/subscription/upgrade")
async def upgrade_subscription(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """Upgrade tenant subscription plan."""
    enforce_scope(principal, "security:manage")
    body = await request.json()
    target_plan = body.get("plan", "pro")

    if target_plan not in PLANS:
        return {"error": f"Unknown plan: {target_plan}", "available": list(PLANS.keys())}

    now = datetime.now(UTC)
    sub = {
        "tenant_id": principal.tenant_id,
        "plan": target_plan,
        "status": "active",
        "started_at": now.isoformat(),
        "renews_at": now.replace(day=28).isoformat(),
        "auto_renew": body.get("auto_renew", True),
        "interval": body.get("interval", "monthly"),
        "upgraded_by": principal.user_id,
    }
    _subscriptions[principal.tenant_id] = sub

    return {"upgraded": True, "subscription": sub}


@router.post("/subscription/cancel")
async def cancel_subscription(principal: PrincipalDependency = None) -> dict[str, Any]:
    """Cancel subscription (downgrade to free at period end)."""
    enforce_scope(principal, "security:manage")

    sub = _subscriptions.get(principal.tenant_id)
    if sub is None:
        return {"cancelled": False, "reason": "No active paid subscription"}

    sub["status"] = "cancelled"
    sub["cancelled_at"] = datetime.now(UTC).isoformat()
    sub["cancels_at_period_end"] = True

    return {"cancelled": True, "effective_at": sub["renews_at"], "subscription": sub}


# ─── X4: Invoice Generation ──────────────────────────────────────────────────


@router.post("/invoices/generate")
async def generate_invoice(principal: PrincipalDependency = None) -> dict[str, Any]:
    """Generate an invoice for the current billing period."""
    enforce_scope(principal, "security:manage")

    tenant_records = [r for r in _usage_records if r["tenant_id"] == principal.tenant_id]
    metrics: dict[str, int] = {}
    for r in tenant_records:
        metrics[r["metric"]] = metrics.get(r["metric"], 0) + r["quantity"]

    unit_prices = {"agent_run": 0.01, "token": 0.000002, "api_call": 0.001, "workflow_run": 0.05}
    line_items = [
        {"description": f"{m} x {qty}", "unit_price": unit_prices.get(m, 0.001), "quantity": qty, "amount": round(qty * unit_prices.get(m, 0.001), 4)}
        for m, qty in metrics.items()
    ]

    sub = _subscriptions.get(principal.tenant_id, {})
    plan = sub.get("plan", "free")
    plan_price = PLANS[plan]["price_monthly"] if plan in PLANS else 0
    if plan_price > 0:
        line_items.insert(0, {"description": f"{PLANS[plan]['name']} Plan (monthly)", "unit_price": plan_price, "quantity": 1, "amount": plan_price})

    subtotal = round(sum(li["amount"] for li in line_items), 2)
    tax = round(subtotal * 0.0, 2)
    total = subtotal + tax

    invoice = {
        "id": f"INV-{uuid4().hex[:8].upper()}",
        "tenant_id": principal.tenant_id,
        "period": datetime.now(UTC).strftime("%Y-%m"),
        "issued_at": datetime.now(UTC).isoformat(),
        "due_at": datetime.now(UTC).isoformat(),
        "line_items": line_items,
        "subtotal": subtotal,
        "tax": tax,
        "total": total,
        "currency": "USD",
        "status": "draft",
    }
    _invoices.append(invoice)

    return {"invoice": invoice}


@router.get("/invoices")
async def list_invoices(principal: PrincipalDependency = None) -> dict[str, Any]:
    """List all invoices for the tenant."""
    enforce_scope(principal, "agent:run")
    tenant_invoices = [inv for inv in _invoices if inv["tenant_id"] == principal.tenant_id]
    return {"invoices": tenant_invoices, "total": len(tenant_invoices)}


# ─── X5: Payment Webhook (Stripe-compatible) ────────────────────────────────


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request) -> dict[str, Any]:
    """Handle Stripe payment webhooks (signature verification stub)."""
    payload = await request.body()

    try:
        import json
        event = json.loads(payload)
    except Exception:
        return {"received": False, "error": "Invalid JSON payload"}

    event_type = event.get("type", "unknown")
    handled_events = [
        "checkout.session.completed",
        "invoice.paid",
        "invoice.payment_failed",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ]

    return {
        "received": True,
        "event_type": event_type,
        "handled": event_type in handled_events,
        "supported_events": handled_events,
    }


# ─── X6: Revenue Dashboard ───────────────────────────────────────────────────


@router.get("/revenue")
async def get_revenue_dashboard(principal: PrincipalDependency = None) -> dict[str, Any]:
    """Revenue & MRR dashboard for platform operators."""
    enforce_scope(principal, "security:manage")

    active_subs = [s for s in _subscriptions.values() if s.get("status") == "active"]
    mrr = sum(PLANS.get(s["plan"], {}).get("price_monthly", 0) for s in active_subs if PLANS.get(s["plan"], {}).get("price_monthly", 0) > 0)

    plan_distribution: dict[str, int] = {}
    for s in _subscriptions.values():
        p = s.get("plan", "free")
        plan_distribution[p] = plan_distribution.get(p, 0) + 1

    return {
        "mrr": mrr,
        "arr": mrr * 12,
        "currency": "USD",
        "active_subscriptions": len(active_subs),
        "total_subscriptions": len(_subscriptions),
        "plan_distribution": plan_distribution,
        "total_invoices": len(_invoices),
        "usage_records": len(_usage_records),
        "metrics_tracked": ["agent_run", "token", "api_call", "workflow_run"],
        "generated_at": datetime.now(UTC).isoformat(),
    }
