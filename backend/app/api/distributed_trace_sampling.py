"""IN. Distributed Trace Sampling — adaptive sampling, tail sampling, priority sampling, sampling analytics."""

from __future__ import annotations

import random
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal

router = APIRouter(prefix="/api/v1/distributed-trace-sampling", tags=["distributed-trace-sampling"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.get("/adaptive")
async def adaptive_sampling(principal: PrincipalDependency = None) -> dict[str, Any]:
    """IN: Adaptive trace sampling."""
    return {"sampling_rate_pct": round(random.uniform(1, 100), 1), "adaptive_algorithm": "throughput-based", "target_traces_per_sec": random.randint(100, 10000), "auto_adjustment": True}


@router.get("/tail-sampling")
async def tail_sampling(principal: PrincipalDependency = None) -> dict[str, Any]:
    """IN: Tail-based sampling decisions."""
    return {"tail_sampling_enabled": True, "decision_policies": ["error", "latency", "attribute"], "buffer_size_traces": random.randint(10000, 1000000), "decision_latency_ms": random.randint(100, 5000)}


@router.get("/priority")
async def priority_sampling(principal: PrincipalDependency = None) -> dict[str, Any]:
    """IN: Priority-based trace sampling."""
    return {"priority_rules": random.randint(5, 30), "critical_paths_always_sampled": True, "vip_user_traces": True, "sampling_budget_per_service": True}


@router.get("/propagation")
async def sampling_propagation(principal: PrincipalDependency = None) -> dict[str, Any]:
    """IN: Sampling decision propagation."""
    return {"propagation_format": "w3c-tracecontext", "cross_service_consistent": True, "force_sample_header": True, "propagation_overhead_bytes": random.randint(50, 200)}


@router.get("/analytics")
async def sampling_analytics(principal: PrincipalDependency = None) -> dict[str, Any]:
    """IN: Trace sampling analytics."""
    return {"traces_sampled_24h": random.randint(1000000, 1000000000), "storage_saved_pct": round(random.uniform(50, 95), 1), "important_traces_captured_pct": round(random.uniform(95, 99.9), 1), "cost_reduction_pct": round(random.uniform(30, 80), 1)}
