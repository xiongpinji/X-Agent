#!/usr/bin/env python3
"""Health check script for Agent V2 deployment.

Performs comprehensive health checks on all services and components
required for Agent V2 deployment.
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import httpx


class HealthStatus(str, Enum):
    """Health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    name: str
    status: HealthStatus
    message: str = ""
    details: dict | None = None


class HealthChecker:
    """Performs health checks on services."""

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        db_host: str = "localhost",
        db_port: int = 5432,
        db_user: str = "xagent",
        db_password: str = "xagent",
        db_name: str = "xagent",
        redis_host: str = "localhost",
        redis_port: int = 6379,
        qdrant_url: str = "http://localhost:6333",
    ) -> None:
        """Initialize health checker.

        Args:
            api_url: API base URL.
            db_host: Database host.
            db_port: Database port.
            db_user: Database user.
            db_password: Database password.
            db_name: Database name.
            redis_host: Redis host.
            redis_port: Redis port.
            qdrant_url: Qdrant URL.
        """
        self.api_url = api_url
        self.db_host = db_host
        self.db_port = db_port
        self.db_user = db_user
        self.db_password = db_password
        self.db_name = db_name
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.qdrant_url = qdrant_url
        self.results: list[HealthCheckResult] = []

    async def check_api(self) -> HealthCheckResult:
        """Check API health.

        Returns:
            Health check result.
        """
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.api_url}/health")
                if response.status_code == 200:
                    return HealthCheckResult(
                        name="API",
                        status=HealthStatus.HEALTHY,
                        message="API is responding",
                        details=response.json() if response.text else {},
                    )
                else:
                    return HealthCheckResult(
                        name="API",
                        status=HealthStatus.UNHEALTHY,
                        message=f"API returned status {response.status_code}",
                    )
        except Exception as e:
            return HealthCheckResult(
                name="API",
                status=HealthStatus.UNHEALTHY,
                message=f"API health check failed: {e}",
            )

    async def check_database(self) -> HealthCheckResult:
        """Check database health.

        Returns:
            Health check result.
        """
        try:
            import asyncpg

            conn = await asyncpg.connect(
                host=self.db_host,
                port=self.db_port,
                user=self.db_user,
                password=self.db_password,
                database=self.db_name,
                timeout=10,
            )
            version = await conn.fetchval("SELECT version()")
            await conn.close()

            return HealthCheckResult(
                name="Database",
                status=HealthStatus.HEALTHY,
                message="Database is responding",
                details={"version": version},
            )
        except Exception as e:
            return HealthCheckResult(
                name="Database",
                status=HealthStatus.UNHEALTHY,
                message=f"Database health check failed: {e}",
            )

    async def check_redis(self) -> HealthCheckResult:
        """Check Redis health.

        Returns:
            Health check result.
        """
        try:
            import redis

            r = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                decode_responses=True,
                socket_connect_timeout=10,
            )
            info = r.info()
            r.close()

            return HealthCheckResult(
                name="Redis",
                status=HealthStatus.HEALTHY,
                message="Redis is responding",
                details={
                    "version": info.get("redis_version"),
                    "used_memory_mb": info.get("used_memory_human"),
                },
            )
        except Exception as e:
            return HealthCheckResult(
                name="Redis",
                status=HealthStatus.UNHEALTHY,
                message=f"Redis health check failed: {e}",
            )

    async def check_qdrant(self) -> HealthCheckResult:
        """Check Qdrant health.

        Returns:
            Health check result.
        """
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.qdrant_url}/health")
                if response.status_code == 200:
                    data = response.json()
                    return HealthCheckResult(
                        name="Qdrant",
                        status=HealthStatus.HEALTHY,
                        message="Qdrant is responding",
                        details=data,
                    )
                else:
                    return HealthCheckResult(
                        name="Qdrant",
                        status=HealthStatus.UNHEALTHY,
                        message=f"Qdrant returned status {response.status_code}",
                    )
        except Exception as e:
            return HealthCheckResult(
                name="Qdrant",
                status=HealthStatus.UNHEALTHY,
                message=f"Qdrant health check failed: {e}",
            )

    async def check_feature_flags(self) -> HealthCheckResult:
        """Check feature flags.

        Returns:
            Health check result.
        """
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.api_url}/admin/feature-flags/use_agent_v2"
                )
                if response.status_code == 200:
                    data = response.json()
                    return HealthCheckResult(
                        name="Feature Flags",
                        status=HealthStatus.HEALTHY,
                        message="Feature flags are accessible",
                        details=data,
                    )
                else:
                    return HealthCheckResult(
                        name="Feature Flags",
                        status=HealthStatus.DEGRADED,
                        message=f"Feature flags returned status {response.status_code}",
                    )
        except Exception as e:
            return HealthCheckResult(
                name="Feature Flags",
                status=HealthStatus.DEGRADED,
                message=f"Feature flags check failed: {e}",
            )

    async def check_metrics(self) -> HealthCheckResult:
        """Check metrics endpoint.

        Returns:
            Health check result.
        """
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.api_url}/admin/metrics/execution"
                )
                if response.status_code == 200:
                    data = response.json()
                    return HealthCheckResult(
                        name="Metrics",
                        status=HealthStatus.HEALTHY,
                        message="Metrics are available",
                        details=data,
                    )
                else:
                    return HealthCheckResult(
                        name="Metrics",
                        status=HealthStatus.DEGRADED,
                        message=f"Metrics returned status {response.status_code}",
                    )
        except Exception as e:
            return HealthCheckResult(
                name="Metrics",
                status=HealthStatus.DEGRADED,
                message=f"Metrics check failed: {e}",
            )

    async def run_all_checks(self) -> bool:
        """Run all health checks.

        Returns:
            True if all checks pass.
        """
        print("Running health checks...\n")

        checks = [
            self.check_api(),
            self.check_database(),
            self.check_redis(),
            self.check_qdrant(),
            self.check_feature_flags(),
            self.check_metrics(),
        ]

        results = await asyncio.gather(*checks)
        self.results = results

        # Print results
        all_healthy = True
        for result in results:
            status_symbol = {
                HealthStatus.HEALTHY: "✓",
                HealthStatus.DEGRADED: "⚠",
                HealthStatus.UNHEALTHY: "✗",
            }[result.status]

            print(f"{status_symbol} {result.name}: {result.message}")

            if result.details:
                for key, value in result.details.items():
                    print(f"  - {key}: {value}")

            if result.status != HealthStatus.HEALTHY:
                all_healthy = False

        print()
        return all_healthy

    def get_summary(self) -> dict:
        """Get health check summary.

        Returns:
            Summary dictionary.
        """
        healthy_count = sum(
            1 for r in self.results if r.status == HealthStatus.HEALTHY
        )
        degraded_count = sum(
            1 for r in self.results if r.status == HealthStatus.DEGRADED
        )
        unhealthy_count = sum(
            1 for r in self.results if r.status == HealthStatus.UNHEALTHY
        )

        return {
            "total": len(self.results),
            "healthy": healthy_count,
            "degraded": degraded_count,
            "unhealthy": unhealthy_count,
            "overall_status": (
                "healthy"
                if unhealthy_count == 0
                else "degraded" if degraded_count > 0 else "unhealthy"
            ),
        }


async def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    checker = HealthChecker()
    all_healthy = await checker.run_all_checks()

    summary = checker.get_summary()
    print("=" * 50)
    print("Health Check Summary")
    print("=" * 50)
    print(f"Total checks: {summary['total']}")
    print(f"Healthy: {summary['healthy']}")
    print(f"Degraded: {summary['degraded']}")
    print(f"Unhealthy: {summary['unhealthy']}")
    print(f"Overall status: {summary['overall_status']}")
    print("=" * 50)

    return 0 if all_healthy else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
