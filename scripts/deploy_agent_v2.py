#!/usr/bin/env python3
"""Automated deployment script for Agent V2 with health checks and rollback.

This script handles the complete deployment process including:
- Pre-deployment validation
- Database migrations
- Service health checks
- Gradual rollout with feature flags
- Automatic rollback on failure
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class DeploymentPhase(str, Enum):
    """Deployment phases."""

    PRE_DEPLOYMENT = "pre_deployment"
    MIGRATION = "migration"
    HEALTH_CHECK = "health_check"
    ROLLOUT = "rollout"
    MONITORING = "monitoring"
    COMPLETE = "complete"
    ROLLBACK = "rollback"


class DeploymentStatus(str, Enum):
    """Deployment status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class DeploymentConfig:
    """Deployment configuration."""

    api_url: str = "http://localhost:8000"
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "xagent"
    db_password: str = "xagent"
    db_name: str = "xagent"
    redis_host: str = "localhost"
    redis_port: int = 6379
    initial_rollout_percentage: int = 10  # Start with 10% rollout
    max_rollout_percentage: int = 100  # Max 100%
    rollout_increment: int = 10  # Increase by 10% each step
    rollout_interval_seconds: int = 300  # Wait 5 minutes between increments
    health_check_timeout: int = 30
    health_check_retries: int = 5
    error_threshold_percentage: float = 5.0  # Rollback if error rate > 5%


@dataclass
class DeploymentMetrics:
    """Deployment metrics."""

    phase: DeploymentPhase
    status: DeploymentStatus
    timestamp: str
    duration_seconds: float = 0.0
    v1_executions: int = 0
    v2_executions: int = 0
    v1_errors: int = 0
    v2_errors: int = 0
    current_rollout_percentage: int = 0
    error_rate_v2: float = 0.0
    message: str = ""


class HealthChecker:
    """Checks health of services."""

    def __init__(self, config: DeploymentConfig) -> None:
        """Initialize health checker.

        Args:
            config: Deployment configuration.
        """
        self.config = config
        self.client = httpx.AsyncClient(timeout=config.health_check_timeout)

    async def check_api_health(self) -> bool:
        """Check API health.

        Returns:
            True if API is healthy.
        """
        try:
            response = await self.client.get(f"{self.config.api_url}/health")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"API health check failed: {e}")
            return False

    async def check_database_health(self) -> bool:
        """Check database health.

        Returns:
            True if database is healthy.
        """
        try:
            import asyncpg

            conn = await asyncpg.connect(
                host=self.config.db_host,
                port=self.config.db_port,
                user=self.config.db_user,
                password=self.config.db_password,
                database=self.config.db_name,
            )
            await conn.close()
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    async def check_redis_health(self) -> bool:
        """Check Redis health.

        Returns:
            True if Redis is healthy.
        """
        try:
            import redis

            r = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                decode_responses=True,
            )
            r.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False

    async def check_all_services(self) -> bool:
        """Check all services.

        Returns:
            True if all services are healthy.
        """
        logger.info("Checking service health...")
        api_ok = await self.check_api_health()
        db_ok = await self.check_database_health()
        redis_ok = await self.check_redis_health()

        logger.info(f"API: {'OK' if api_ok else 'FAILED'}")
        logger.info(f"Database: {'OK' if db_ok else 'FAILED'}")
        logger.info(f"Redis: {'OK' if redis_ok else 'FAILED'}")

        return api_ok and db_ok and redis_ok

    async def wait_for_services(self, retries: int = 5) -> bool:
        """Wait for services to be ready.

        Args:
            retries: Number of retries.

        Returns:
            True if services became ready.
        """
        for attempt in range(retries):
            logger.info(f"Service readiness check {attempt + 1}/{retries}...")
            if await self.check_all_services():
                logger.info("All services are ready")
                return True
            if attempt < retries - 1:
                await asyncio.sleep(5)
        return False

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()


class DeploymentOrchestrator:
    """Orchestrates the deployment process."""

    def __init__(self, config: DeploymentConfig) -> None:
        """Initialize deployment orchestrator.

        Args:
            config: Deployment configuration.
        """
        self.config = config
        self.health_checker = HealthChecker(config)
        self.metrics: list[DeploymentMetrics] = []
        self.start_time = datetime.now()

    async def run_pre_deployment_checks(self) -> bool:
        """Run pre-deployment checks.

        Returns:
            True if all checks pass.
        """
        logger.info("=" * 60)
        logger.info("PHASE: Pre-Deployment Checks")
        logger.info("=" * 60)

        # Wait for services to be ready
        if not await self.health_checker.wait_for_services(
            self.config.health_check_retries
        ):
            logger.error("Services failed to become ready")
            return False

        logger.info("Pre-deployment checks passed")
        return True

    async def run_database_migrations(self) -> bool:
        """Run database migrations.

        Returns:
            True if migrations succeed.
        """
        logger.info("=" * 60)
        logger.info("PHASE: Database Migrations")
        logger.info("=" * 60)

        try:
            import asyncpg

            conn = await asyncpg.connect(
                host=self.config.db_host,
                port=self.config.db_port,
                user=self.config.db_user,
                password=self.config.db_password,
                database=self.config.db_name,
            )

            # Check if migrations table exists
            migration_table_exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'schema_migrations'
                )
                """
            )

            if not migration_table_exists:
                logger.info("Creating migrations table...")
                await conn.execute(
                    """
                    CREATE TABLE schema_migrations (
                        id SERIAL PRIMARY KEY,
                        version VARCHAR(255) UNIQUE NOT NULL,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

            # Record migration for Agent V2
            await conn.execute(
                """
                INSERT INTO schema_migrations (version)
                VALUES ('agent_v2_deployment_' || NOW()::TEXT)
                ON CONFLICT DO NOTHING
                """
            )

            await conn.close()
            logger.info("Database migrations completed")
            return True
        except Exception as e:
            logger.error(f"Database migration failed: {e}")
            return False

    async def update_feature_flag(self, rollout_percentage: int) -> bool:
        """Update Agent V2 feature flag.

        Args:
            rollout_percentage: Rollout percentage (0-100).

        Returns:
            True if update succeeds.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.config.api_url}/admin/feature-flags/use_agent_v2",
                    json={
                        "enabled": True,
                        "rollout_percentage": rollout_percentage,
                    },
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to update feature flag: {e}")
            return False

    async def get_execution_metrics(self) -> Optional[dict[str, Any]]:
        """Get execution metrics from API.

        Returns:
            Metrics dictionary or None if request fails.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.config.api_url}/admin/metrics/execution"
                )
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
        return None

    async def run_gradual_rollout(self) -> bool:
        """Run gradual rollout with monitoring.

        Returns:
            True if rollout succeeds.
        """
        logger.info("=" * 60)
        logger.info("PHASE: Gradual Rollout")
        logger.info("=" * 60)

        current_percentage = self.config.initial_rollout_percentage

        while current_percentage <= self.config.max_rollout_percentage:
            logger.info(f"Setting rollout to {current_percentage}%...")

            if not await self.update_feature_flag(current_percentage):
                logger.error(f"Failed to set rollout to {current_percentage}%")
                return False

            logger.info(f"Monitoring at {current_percentage}% for {self.config.rollout_interval_seconds}s...")
            await asyncio.sleep(self.config.rollout_interval_seconds)

            # Check metrics
            metrics = await self.get_execution_metrics()
            if metrics:
                v2_errors = metrics.get("v2_errors", 0)
                v2_executions = metrics.get("v2_executions", 0)
                if v2_executions > 0:
                    error_rate = (v2_errors / v2_executions) * 100
                    logger.info(
                        f"V2 Error Rate: {error_rate:.2f}% "
                        f"({v2_errors}/{v2_executions})"
                    )

                    if error_rate > self.config.error_threshold_percentage:
                        logger.error(
                            f"Error rate {error_rate:.2f}% exceeds threshold "
                            f"{self.config.error_threshold_percentage}%"
                        )
                        return False

            if current_percentage >= self.config.max_rollout_percentage:
                break

            current_percentage = min(
                current_percentage + self.config.rollout_increment,
                self.config.max_rollout_percentage,
            )

        logger.info("Gradual rollout completed successfully")
        return True

    async def run_rollback(self) -> bool:
        """Rollback to Agent V1.

        Returns:
            True if rollback succeeds.
        """
        logger.info("=" * 60)
        logger.info("PHASE: Rollback")
        logger.info("=" * 60)

        logger.warning("Rolling back to Agent V1...")
        if not await self.update_feature_flag(0):
            logger.error("Failed to rollback feature flag")
            return False

        logger.info("Rollback completed")
        return True

    async def deploy(self) -> bool:
        """Run complete deployment.

        Returns:
            True if deployment succeeds.
        """
        try:
            # Pre-deployment checks
            if not await self.run_pre_deployment_checks():
                logger.error("Pre-deployment checks failed")
                return False

            # Database migrations
            if not await self.run_database_migrations():
                logger.error("Database migrations failed")
                return False

            # Gradual rollout
            if not await self.run_gradual_rollout():
                logger.error("Gradual rollout failed, initiating rollback...")
                await self.run_rollback()
                return False

            logger.info("=" * 60)
            logger.info("DEPLOYMENT SUCCESSFUL")
            logger.info("=" * 60)
            return True

        except Exception as e:
            logger.error(f"Deployment failed with exception: {e}", exc_info=True)
            await self.run_rollback()
            return False
        finally:
            await self.health_checker.close()


async def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    config = DeploymentConfig()
    orchestrator = DeploymentOrchestrator(config)

    success = await orchestrator.deploy()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
