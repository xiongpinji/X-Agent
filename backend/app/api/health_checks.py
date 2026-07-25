"""Health check endpoints for production readiness."""

import asyncio
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


class HealthStatus(BaseModel):
    """Health status response model."""
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: datetime
    version: str
    checks: dict[str, Any]
    uptime_seconds: float


class ReadinessStatus(BaseModel):
    """Readiness status response model."""
    ready: bool
    timestamp: datetime
    checks: dict[str, Any]


class LivenessStatus(BaseModel):
    """Liveness status response model."""
    alive: bool
    timestamp: datetime


class HealthChecker:
    """Centralized health check coordinator."""

    def __init__(self):
        self.start_time = datetime.utcnow()
        self.checks: dict[str, callable] = {}

    def register_check(self, name: str, check_func: callable) -> None:
        """Register a health check function."""
        self.checks[name] = check_func

    async def run_checks(self) -> dict[str, Any]:
        """Run all registered health checks."""
        results = {}
        for name, check_func in self.checks.items():
            try:
                result = await check_func() if asyncio.iscoroutinefunction(check_func) else check_func()
                results[name] = {
                    "status": "healthy" if result else "unhealthy",
                    "details": result
                }
            except Exception as e:
                logger.error(f"Health check '{name}' failed: {e!s}")
                results[name] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
        return results

    def get_uptime(self) -> float:
        """Get uptime in seconds."""
        return (datetime.utcnow() - self.start_time).total_seconds()


# Global health checker instance
health_checker = HealthChecker()


# Health check functions
async def check_database() -> dict[str, Any]:
    """Check database connectivity."""
    try:
        from backend.app.dependencies import get_db
        db = await get_db()
        # Simple query to verify connection
        await db.execute("SELECT 1")
        return {"connected": True, "type": "postgresql"}
    except Exception as e:
        logger.error(f"Database check failed: {e!s}")
        return {"connected": False, "error": str(e)}


async def check_redis() -> dict[str, Any]:
    """Check Redis connectivity."""
    try:
        import redis.asyncio as redis

        from backend.app.settings import get_settings
        settings = get_settings()
        r = redis.from_url(settings.redis_url)
        await r.ping()
        await r.close()
        return {"connected": True, "type": "redis"}
    except Exception as e:
        logger.error(f"Redis check failed: {e!s}")
        return {"connected": False, "error": str(e)}


async def check_qdrant() -> dict[str, Any]:
    """Check Qdrant vector database connectivity."""
    try:
        from backend.app.services.memory.qdrant_client import vector_client
        health = await vector_client.get_health()
        return {"connected": True, "status": health}
    except Exception as e:
        logger.error(f"Qdrant check failed: {e!s}")
        return {"connected": False, "error": str(e)}


async def check_disk_space() -> dict[str, Any]:
    """Check available disk space."""
    try:
        import shutil
        from pathlib import Path

        data_dir = Path("./data")
        total, used, free = shutil.disk_usage(data_dir)

        free_gb = free / (1024 ** 3)
        total_gb = total / (1024 ** 3)
        used_percent = (used / total) * 100

        return {
            "total_gb": round(total_gb, 2),
            "used_gb": round(used / (1024 ** 3), 2),
            "free_gb": round(free_gb, 2),
            "used_percent": round(used_percent, 2),
            "status": "healthy" if free_gb > 5 else "warning"
        }
    except Exception as e:
        logger.error(f"Disk space check failed: {e!s}")
        return {"error": str(e)}


async def check_memory() -> dict[str, Any]:
    """Check system memory usage."""
    try:
        import psutil
        memory = psutil.virtual_memory()
        return {
            "total_gb": round(memory.total / (1024 ** 3), 2),
            "used_gb": round(memory.used / (1024 ** 3), 2),
            "available_gb": round(memory.available / (1024 ** 3), 2),
            "percent": memory.percent,
            "status": "healthy" if memory.percent < 80 else "warning"
        }
    except Exception as e:
        logger.error(f"Memory check failed: {e!s}")
        return {"error": str(e)}


async def check_cpu() -> dict[str, Any]:
    """Check CPU usage."""
    try:
        import psutil
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        return {
            "percent": cpu_percent,
            "count": cpu_count,
            "status": "healthy" if cpu_percent < 80 else "warning"
        }
    except Exception as e:
        logger.error(f"CPU check failed: {e!s}")
        return {"error": str(e)}


async def check_llm_api() -> dict[str, Any]:
    """Check LLM API connectivity."""
    try:
        from backend.app.core.llm import get_llm_client
        client = get_llm_client()
        # Simple API call to verify connectivity
        response = await client.models.list()
        return {"connected": True, "models_available": len(response.data) if hasattr(response, 'data') else 0}
    except Exception as e:
        logger.error(f"LLM API check failed: {e!s}")
        return {"connected": False, "error": str(e)}


# Register all checks
health_checker.register_check("database", check_database)
health_checker.register_check("redis", check_redis)
health_checker.register_check("qdrant", check_qdrant)
health_checker.register_check("disk_space", check_disk_space)
health_checker.register_check("memory", check_memory)
health_checker.register_check("cpu", check_cpu)
health_checker.register_check("llm_api", check_llm_api)


@router.get("/live", response_model=LivenessStatus)
async def liveness_probe() -> LivenessStatus:
    """Liveness probe - indicates if the service is running."""
    return LivenessStatus(
        alive=True,
        timestamp=datetime.utcnow()
    )


@router.get("/ready", response_model=ReadinessStatus)
async def readiness_probe() -> ReadinessStatus:
    """Readiness probe - indicates if the service is ready to accept traffic."""
    checks = await health_checker.run_checks()

    # Service is ready if critical components are healthy
    critical_checks = ["database", "redis"]
    ready = all(
        checks.get(check, {}).get("status") == "healthy"
        for check in critical_checks
    )

    return ReadinessStatus(
        ready=ready,
        timestamp=datetime.utcnow(),
        checks=checks
    )


@router.get("/", response_model=HealthStatus)
async def health_check() -> HealthStatus:
    """Comprehensive health check endpoint."""
    checks = await health_checker.run_checks()

    # Determine overall status
    statuses = [check.get("status") for check in checks.values()]
    if all(s == "healthy" for s in statuses):
        overall_status = "healthy"
    elif any(s == "unhealthy" for s in statuses):
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"

    if overall_status == "unhealthy":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is unhealthy"
        )

    return HealthStatus(
        status=overall_status,
        timestamp=datetime.utcnow(),
        version="0.1.0",
        checks=checks,
        uptime_seconds=health_checker.get_uptime()
    )


@router.get("/detailed")
async def detailed_health_check() -> dict[str, Any]:
    """Detailed health check with all metrics."""
    checks = await health_checker.run_checks()

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": health_checker.get_uptime(),
        "checks": checks,
        "environment": {
            "app_mode": "production",
            "version": "0.1.0"
        }
    }
