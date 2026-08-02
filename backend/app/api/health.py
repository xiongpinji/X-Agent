"""Health check endpoints for X-Agent."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from backend.app.core.metrics import metrics_collector
from backend.app.dependencies import (
    get_approval_store,
    get_audit_store,
    get_memory,
    get_run_store,
    get_trace_store,
)

router = APIRouter(prefix="/api/v1/health", tags=["health"])
extended_router = APIRouter(prefix="/api/v1/health", tags=["health-extended"])  # C2: unmounted
extended_router = APIRouter(prefix="/api/v1/health", tags=["health-extended"])  # C2: unmounted
logger = logging.getLogger("xagent.health")


class HealthStatus:
    """Health status enumeration."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthCheckResult:
    """Result of a health check."""

    def __init__(self, name: str, status: str, message: str = "", latency_ms: float = 0):
        self.name = name
        self.status = status
        self.message = message
        self.latency_ms = latency_ms

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "latency_ms": self.latency_ms,
        }


async def check_redis() -> HealthCheckResult:
    """Check Redis connectivity."""
    import time

    start = time.perf_counter()
    try:
        from backend.app.core.redis_client import get_redis
        redis = get_redis()
        if redis.is_available:
            pong = await redis.ping()
            latency = (time.perf_counter() - start) * 1000
            if pong:
                return HealthCheckResult(
                    "redis",
                    HealthStatus.HEALTHY,
                    "Redis connected",
                    latency,
                )
        latency = (time.perf_counter() - start) * 1000
        return HealthCheckResult(
            "redis",
            HealthStatus.DEGRADED,
            "Redis not configured, using in-memory fallback",
            latency,
        )
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        logger.error(f"Redis health check failed: {e}")
        return HealthCheckResult(
            "redis",
            HealthStatus.DEGRADED,
            f"Redis check failed: {e!s}",
            latency,
        )


async def check_database() -> HealthCheckResult:
    """Check database connectivity."""
    import time

    start = time.perf_counter()
    try:
        trace_store = get_trace_store()
        count = len(trace_store.list_trace_ids())
        latency = (time.perf_counter() - start) * 1000
        return HealthCheckResult(
            "database",
            HealthStatus.HEALTHY,
            f"Database accessible, {count} traces found",
            latency,
        )
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        logger.error(f"Database health check failed: {e}")
        return HealthCheckResult(
            "database",
            HealthStatus.UNHEALTHY,
            f"Database check failed: {e!s}",
            latency,
        )


async def check_memory_store() -> HealthCheckResult:
    """Check memory store connectivity."""
    import time

    start = time.perf_counter()
    try:
        memory = get_memory()
        count = memory.count()
        if hasattr(count, "__await__"):
            count = await count
        latency = (time.perf_counter() - start) * 1000
        return HealthCheckResult(
            "memory_store",
            HealthStatus.HEALTHY,
            f"Memory store accessible, {count} items",
            latency,
        )
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        logger.error(f"Memory store health check failed: {e}")
        return HealthCheckResult(
            "memory_store",
            HealthStatus.UNHEALTHY,
            f"Memory store check failed: {e!s}",
            latency,
        )


async def check_audit_store() -> HealthCheckResult:
    """Check audit store connectivity."""
    import time

    start = time.perf_counter()
    try:
        audit_store = get_audit_store()
        count = audit_store.count()
        latency = (time.perf_counter() - start) * 1000
        return HealthCheckResult(
            "audit_store",
            HealthStatus.HEALTHY,
            f"Audit store accessible, {count} logs",
            latency,
        )
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        logger.error(f"Audit store health check failed: {e}")
        return HealthCheckResult(
            "audit_store",
            HealthStatus.UNHEALTHY,
            f"Audit store check failed: {e!s}",
            latency,
        )


async def check_approval_store() -> HealthCheckResult:
    """Check approval store connectivity."""
    import time

    start = time.perf_counter()
    try:
        approval_store = get_approval_store()
        pending = approval_store.pending_count()
        latency = (time.perf_counter() - start) * 1000
        return HealthCheckResult(
            "approval_store",
            HealthStatus.HEALTHY,
            f"Approval store accessible, {pending} pending",
            latency,
        )
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        logger.error(f"Approval store health check failed: {e}")
        return HealthCheckResult(
            "approval_store",
            HealthStatus.UNHEALTHY,
            f"Approval store check failed: {e!s}",
            latency,
        )


@router.get("/live", response_model=dict)
async def liveness_probe() -> dict:
    """Liveness probe - indicates if the service is running."""
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
    }


@extended_router.get("/ready", response_model=dict)
async def readiness_probe() -> dict:
    """Readiness probe - indicates if the service is ready to handle requests."""
    checks = await asyncio.gather(
        check_redis(),
        check_database(),
        check_memory_store(),
        check_audit_store(),
        check_approval_store(),
    )

    all_healthy = all(check.status == HealthStatus.HEALTHY for check in checks)
    any_degraded = any(check.status == HealthStatus.DEGRADED for check in checks)

    if all_healthy:
        status_code = HealthStatus.HEALTHY
    elif any_degraded:
        status_code = HealthStatus.DEGRADED
    else:
        status_code = HealthStatus.UNHEALTHY

    result = {
        "status": status_code,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": [check.to_dict() for check in checks],
    }

    if status_code == HealthStatus.UNHEALTHY:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=result)

    return result


@extended_router.get("/detailed", response_model=dict)
async def detailed_health_check() -> dict:
    """Detailed health check with all dependencies."""
    checks = await asyncio.gather(
        check_redis(),
        check_database(),
        check_memory_store(),
        check_audit_store(),
        check_approval_store(),
    )

    all_healthy = all(check.status == HealthStatus.HEALTHY for check in checks)
    any_degraded = any(check.status == HealthStatus.DEGRADED for check in checks)

    if all_healthy:
        status_code = HealthStatus.HEALTHY
    elif any_degraded:
        status_code = HealthStatus.DEGRADED
    else:
        status_code = HealthStatus.UNHEALTHY

    # Calculate metrics
    try:
        trace_store = get_trace_store()
        run_store = get_run_store()
        approval_store = get_approval_store()

        metrics_collector.set_traces_total(len(trace_store.list_trace_ids()))
        metrics_collector.set_runs_total(run_store.count())
        metrics_collector.set_approvals_pending(approval_store.pending_count())
    except Exception as e:
        logger.error(f"Failed to update metrics: {e}")

    return {
        "status": status_code,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": [check.to_dict() for check in checks],
        "metrics": {
            "total_checks": len(checks),
            "healthy_checks": sum(1 for c in checks if c.status == HealthStatus.HEALTHY),
            "degraded_checks": sum(1 for c in checks if c.status == HealthStatus.DEGRADED),
            "unhealthy_checks": sum(1 for c in checks if c.status == HealthStatus.UNHEALTHY),
        },
    }


# ─── R: Production Deployment Probes ─────────────────────────────────────────


@extended_router.get("/deploy-readiness")
async def deploy_readiness() -> dict:
    """K8s-style deployment readiness: all subsystems + version + uptime."""
    import os
    import time

    checks = await asyncio.gather(
        check_redis(),
        check_database(),
        check_memory_store(),
    )
    all_ok = all(c.status != HealthStatus.UNHEALTHY for c in checks)

    # Version from pyproject or env
    version = os.environ.get("XAGENT_VERSION", "0.4.0-alpha")

    return {
        "ready": all_ok,
        "version": version,
        "uptime_seconds": round(time.time() - _startup_time, 1),
        "checks": {c.name: c.status for c in checks},
        "environment": os.environ.get("XAGENT_APP_MODE", "development"),
    }


@extended_router.get("/drain-status")
async def drain_status() -> dict:
    """Graceful shutdown drain status: active requests, shutdown flag."""
    try:
        from backend.app.core.lifecycle import lifecycle
        return {
            "is_shutting_down": lifecycle.is_shutting_down,
            "active_requests": getattr(lifecycle, "active_requests", 0),
            "drain_complete": lifecycle.is_shutting_down and getattr(lifecycle, "active_requests", 0) == 0,
        }
    except Exception:
        return {"is_shutting_down": False, "active_requests": 0, "drain_complete": False}


# Module-level startup timestamp
import time as _time_mod

_startup_time = _time_mod.time()
