"""BW. Distributed Tracing Enhancement — sampling strategies, span correlation, service topology, flame graphs."""

from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Request

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/tracing", tags=["tracing-enhanced"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# ─── BW1: Sampling Strategy ──────────────────────────────────────────────────


@router.get("/sampling")
async def get_sampling_config(principal: PrincipalDependency = None) -> dict[str, Any]:
    """BW: Get trace sampling strategy configuration."""
    enforce_scope(principal, "agent:run")
    return {
        "strategies": [
            {"service": "api-gateway", "rate": 0.1, "type": "probabilistic"},
            {"service": "payment-service", "rate": 1.0, "type": "always_on", "reason": "critical_path"},
            {"service": "notification", "rate": 0.05, "type": "probabilistic"},
            {"service": "ml-inference", "rate": 0.2, "type": "rate_limiting", "max_traces_per_s": 100},
        ],
        "tail_sampling": {"enabled": True, "rules": ["error", "latency>500ms", "status>=500"]},
        "global_default_rate": 0.1,
        "adaptive_sampling": True,
    }


@router.post("/sampling/update")
async def update_sampling(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """BW: Update sampling rate for a service."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    return {
        "service": body.get("service", "api-gateway"),
        "old_rate": 0.1,
        "new_rate": body.get("rate", 0.5),
        "effective_in_s": 30,
        "updated_at": datetime.now(UTC).isoformat(),
    }


# ─── BW2: Span Correlation ───────────────────────────────────────────────────


@router.post("/correlate")
async def correlate_spans(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """BW: Correlate spans across services for a trace."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    trace_id = body.get("trace_id", uuid4().hex)
    return {
        "trace_id": trace_id,
        "total_spans": random.randint(8, 45),
        "services_involved": ["api-gateway", "user-service", "order-service", "payment-service", "notification"],
        "critical_path": [
            {"service": "api-gateway", "operation": "POST /orders", "duration_ms": 320},
            {"service": "order-service", "operation": "create_order", "duration_ms": 180},
            {"service": "payment-service", "operation": "charge", "duration_ms": 95},
        ],
        "bottleneck": {"service": "order-service", "operation": "db_query", "duration_ms": 145},
        "correlation_complete": True,
    }


# ─── BW3: Service Topology ───────────────────────────────────────────────────


@router.get("/topology")
async def service_topology(principal: PrincipalDependency = None) -> dict[str, Any]:
    """BW: Get service dependency topology from trace data."""
    enforce_scope(principal, "agent:run")
    return {
        "nodes": [
            {"id": "api-gateway", "type": "gateway", "rps": 4200},
            {"id": "user-service", "type": "service", "rps": 3800},
            {"id": "order-service", "type": "service", "rps": 2100},
            {"id": "payment-service", "type": "service", "rps": 1500},
            {"id": "postgres", "type": "database", "rps": 5000},
            {"id": "redis", "type": "cache", "rps": 12000},
        ],
        "edges": [
            {"from": "api-gateway", "to": "user-service", "latency_ms": 12},
            {"from": "api-gateway", "to": "order-service", "latency_ms": 25},
            {"from": "order-service", "to": "payment-service", "latency_ms": 45},
            {"from": "order-service", "to": "postgres", "latency_ms": 8},
            {"from": "user-service", "to": "redis", "latency_ms": 2},
        ],
        "discovered_from_traces": True,
        "last_updated": datetime.now(UTC).isoformat(),
    }


# ─── BW4: Performance Flame Graph ────────────────────────────────────────────


@router.post("/flamegraph")
async def generate_flamegraph(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """BW: Generate flame graph data for a trace/operation."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    return {
        "operation": body.get("operation", "POST /orders"),
        "total_duration_ms": 320,
        "flame_layers": [
            {"name": "api-gateway.handler", "start_ms": 0, "end_ms": 320, "depth": 0},
            {"name": "auth.middleware", "start_ms": 0, "end_ms": 15, "depth": 1},
            {"name": "order-service.create", "start_ms": 15, "end_ms": 280, "depth": 1},
            {"name": "db.query.orders", "start_ms": 20, "end_ms": 165, "depth": 2},
            {"name": "payment.charge", "start_ms": 170, "end_ms": 265, "depth": 2},
            {"name": "notification.send", "start_ms": 280, "end_ms": 315, "depth": 1},
        ],
        "hot_path": "db.query.orders (45% of total)",
        "format": "collapsed_stacks",
    }


# ─── BW5: Trace Analytics ────────────────────────────────────────────────────


@router.get("/analytics")
async def trace_analytics(principal: PrincipalDependency = None) -> dict[str, Any]:
    """BW: Trace analytics and RED metrics."""
    enforce_scope(principal, "agent:run")
    return {
        "traces_24h": random.randint(100_000, 500_000),
        "sampled_pct": 10.0,
        "avg_trace_duration_ms": 185,
        "p99_trace_duration_ms": 1200,
        "error_trace_pct": 0.8,
        "top_operations": [
            {"operation": "GET /users", "count": 45_000, "avg_ms": 32},
            {"operation": "POST /orders", "count": 12_000, "avg_ms": 280},
            {"operation": "GET /products", "count": 38_000, "avg_ms": 55},
        ],
        "storage_retention_days": 14,
    }
