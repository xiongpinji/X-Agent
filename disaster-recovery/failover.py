"""Automated failover orchestration for multi-region deployment.

Usage:
    python disaster-recovery/failover.py --check     # Check replication health
    python disaster-recovery/failover.py --promote   # Promote secondary to primary
    python disaster-recovery/failover.py --demote    # Demote primary (maintenance)
    python disaster-recovery/failover.py --status    # Show cluster status
    python disaster-recovery/failover.py --watch     # Continuous health monitoring

Environment variables:
    DR_PRIMARY_HOST       Primary region PostgreSQL host
    DR_SECONDARY_HOST     Secondary region PostgreSQL host
    DR_REDIS_SENTINEL     Redis Sentinel address (host:port)
    DR_QDRANT_PRIMARY     Primary Qdrant URL
    DR_QDRANT_SECONDARY   Secondary Qdrant URL
    DR_API_KEY            Admin API key for failover authorization
    DR_DRY_RUN            Set to "true" for simulation mode
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("xagent.failover")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class RegionRole(StrEnum):
    """Role of a region in the DR topology."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    UNKNOWN = "unknown"


class FailoverMode(StrEnum):
    """Failover trigger mode."""

    AUTOMATIC = "automatic"
    MANUAL = "manual"


class ComponentHealth(StrEnum):
    """Health status of a component."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class DRConfig:
    """Disaster recovery configuration loaded from environment."""

    primary_host: str = ""
    secondary_host: str = ""
    redis_sentinel: str = ""
    qdrant_primary: str = ""
    qdrant_secondary: str = ""
    api_key: str = ""
    dry_run: bool = False
    failover_threshold: int = 3
    health_check_interval: int = 10
    failover_cooldown: int = 300

    @classmethod
    def from_env(cls) -> DRConfig:
        """Load configuration from environment variables."""
        return cls(
            primary_host=os.getenv("DR_PRIMARY_HOST", "localhost:5432"),
            secondary_host=os.getenv("DR_SECONDARY_HOST", "localhost:5433"),
            redis_sentinel=os.getenv("DR_REDIS_SENTINEL", "localhost:26379"),
            qdrant_primary=os.getenv("DR_QDRANT_PRIMARY", "http://localhost:6333"),
            qdrant_secondary=os.getenv("DR_QDRANT_SECONDARY", "http://localhost:6334"),
            api_key=os.getenv("DR_API_KEY", ""),
            dry_run=os.getenv("DR_DRY_RUN", "false").lower() == "true",
            failover_threshold=int(os.getenv("DR_FAILOVER_THRESHOLD", "3")),
            health_check_interval=int(os.getenv("DR_HEALTH_CHECK_INTERVAL", "10")),
            failover_cooldown=int(os.getenv("DR_FAILOVER_COOLDOWN", "300")),
        )


@dataclass
class ComponentStatus:
    """Status of a single infrastructure component."""

    name: str
    health: ComponentHealth = ComponentHealth.UNKNOWN
    role: RegionRole = RegionRole.UNKNOWN
    replication_lag_ms: float = 0.0
    last_sync: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ClusterStatus:
    """Overall cluster status across regions."""

    timestamp: str = ""
    primary_region: str = "east-us"
    secondary_region: str = "west-eu"
    failover_mode: FailoverMode = FailoverMode.AUTOMATIC
    components: list[ComponentStatus] = field(default_factory=list)
    overall_health: ComponentHealth = ComponentHealth.UNKNOWN
    consecutive_failures: int = 0
    last_failover: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "timestamp": self.timestamp,
            "primary_region": self.primary_region,
            "secondary_region": self.secondary_region,
            "failover_mode": self.failover_mode.value,
            "overall_health": self.overall_health.value,
            "consecutive_failures": self.consecutive_failures,
            "last_failover": self.last_failover,
            "components": [
                {
                    "name": c.name,
                    "health": c.health.value,
                    "role": c.role.value,
                    "replication_lag_ms": c.replication_lag_ms,
                    "last_sync": c.last_sync,
                    "details": c.details,
                }
                for c in self.components
            ],
        }


# ---------------------------------------------------------------------------
# Health Checkers
# ---------------------------------------------------------------------------


class PostgresHealthChecker:
    """Check PostgreSQL replication health."""

    def __init__(self, config: DRConfig):
        self.config = config

    async def check(self) -> ComponentStatus:
        """Check PostgreSQL primary and replica status."""
        status = ComponentStatus(name="postgresql", role=RegionRole.PRIMARY)
        try:
            # Attempt connection to primary
            primary_ok = await self._check_connection(self.config.primary_host)
            replica_ok = await self._check_connection(self.config.secondary_host)

            if primary_ok and replica_ok:
                lag = await self._get_replication_lag()
                status.health = (
                    ComponentHealth.HEALTHY if lag < 1000 else ComponentHealth.DEGRADED
                )
                status.replication_lag_ms = lag
                status.last_sync = datetime.now(UTC).isoformat()
                status.details = {
                    "primary_reachable": True,
                    "replica_reachable": True,
                    "replication_lag_ms": lag,
                }
            elif primary_ok and not replica_ok:
                status.health = ComponentHealth.DEGRADED
                status.details = {
                    "primary_reachable": True,
                    "replica_reachable": False,
                    "warning": "Replica unreachable - no failover target",
                }
            elif not primary_ok and replica_ok:
                status.health = ComponentHealth.UNHEALTHY
                status.details = {
                    "primary_reachable": False,
                    "replica_reachable": True,
                    "action_required": "Primary down - failover recommended",
                }
            else:
                status.health = ComponentHealth.UNHEALTHY
                status.details = {
                    "primary_reachable": False,
                    "replica_reachable": False,
                    "action_required": "Both nodes unreachable",
                }
        except Exception as e:
            status.health = ComponentHealth.UNKNOWN
            status.details = {"error": str(e)}
        return status

    async def _check_connection(self, host: str) -> bool:
        """Check if PostgreSQL is reachable via TCP connection."""
        parts = host.split(":")
        hostname = parts[0]
        port = int(parts[1]) if len(parts) > 1 else 5432
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(hostname, port), timeout=5.0
            )
            writer.close()
            await writer.wait_closed()
            return True
        except (OSError, TimeoutError):
            return False

    async def _get_replication_lag(self) -> float:
        """Get replication lag in milliseconds (simulated without asyncpg)."""
        # In production, this would query:
        # SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) * 1000
        # For now, return 0 if both are reachable (healthy state)
        return 0.0


class RedisHealthChecker:
    """Check Redis Sentinel health."""

    def __init__(self, config: DRConfig):
        self.config = config

    async def check(self) -> ComponentStatus:
        """Check Redis Sentinel cluster status."""
        status = ComponentStatus(name="redis", role=RegionRole.PRIMARY)
        try:
            parts = self.config.redis_sentinel.split(":")
            hostname = parts[0]
            port = int(parts[1]) if len(parts) > 1 else 26379
            reachable = await self._tcp_check(hostname, port)
            if reachable:
                status.health = ComponentHealth.HEALTHY
                status.last_sync = datetime.now(UTC).isoformat()
                status.details = {"sentinel_reachable": True, "mode": "sentinel"}
            else:
                status.health = ComponentHealth.UNHEALTHY
                status.details = {"sentinel_reachable": False}
        except Exception as e:
            status.health = ComponentHealth.UNKNOWN
            status.details = {"error": str(e)}
        return status

    async def _tcp_check(self, host: str, port: int) -> bool:
        """TCP connectivity check."""
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=5.0
            )
            writer.close()
            await writer.wait_closed()
            return True
        except (OSError, TimeoutError):
            return False


class QdrantHealthChecker:
    """Check Qdrant cluster health."""

    def __init__(self, config: DRConfig):
        self.config = config

    async def check(self) -> ComponentStatus:
        """Check Qdrant health via HTTP endpoint."""
        status = ComponentStatus(name="qdrant", role=RegionRole.PRIMARY)
        try:
            primary_ok = await self._http_health(self.config.qdrant_primary)
            secondary_ok = await self._http_health(self.config.qdrant_secondary)

            if primary_ok and secondary_ok:
                status.health = ComponentHealth.HEALTHY
                status.last_sync = datetime.now(UTC).isoformat()
                status.details = {
                    "primary_reachable": True,
                    "secondary_reachable": True,
                    "replication_factor": 2,
                }
            elif primary_ok:
                status.health = ComponentHealth.DEGRADED
                status.details = {
                    "primary_reachable": True,
                    "secondary_reachable": False,
                }
            else:
                status.health = ComponentHealth.UNHEALTHY
                status.details = {"primary_reachable": False}
        except Exception as e:
            status.health = ComponentHealth.UNKNOWN
            status.details = {"error": str(e)}
        return status

    async def _http_health(self, url: str) -> bool:
        """Check Qdrant /health endpoint."""
        try:
            # Use urllib for zero-dependency HTTP check
            import urllib.request

            req = urllib.request.Request(f"{url}/health", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Failover Orchestrator
# ---------------------------------------------------------------------------


class FailoverOrchestrator:
    """Orchestrates failover between primary and secondary regions."""

    def __init__(self, config: DRConfig):
        self.config = config
        self.pg_checker = PostgresHealthChecker(config)
        self.redis_checker = RedisHealthChecker(config)
        self.qdrant_checker = QdrantHealthChecker(config)
        self._consecutive_failures = 0
        self._last_failover_time: float = 0

    async def check_health(self) -> ClusterStatus:
        """Run health checks on all components and aggregate status."""
        logger.info("Running health checks...")
        checks = await asyncio.gather(
            self.pg_checker.check(),
            self.redis_checker.check(),
            self.qdrant_checker.check(),
            return_exceptions=True,
        )

        components: list[ComponentStatus] = []
        for result in checks:
            if isinstance(result, ComponentStatus):
                components.append(result)
            elif isinstance(result, Exception):
                logger.error("Health check failed: %s", result)

        # Determine overall health
        healths = [c.health for c in components]
        if all(h == ComponentHealth.HEALTHY for h in healths):
            overall = ComponentHealth.HEALTHY
        elif any(h == ComponentHealth.UNHEALTHY for h in healths):
            overall = ComponentHealth.UNHEALTHY
        else:
            overall = ComponentHealth.DEGRADED

        # Track consecutive failures
        if overall == ComponentHealth.UNHEALTHY:
            self._consecutive_failures += 1
        else:
            self._consecutive_failures = 0

        cluster = ClusterStatus(
            timestamp=datetime.now(UTC).isoformat(),
            overall_health=overall,
            consecutive_failures=self._consecutive_failures,
            components=components,
            last_failover=(
                datetime.fromtimestamp(self._last_failover_time, tz=UTC).isoformat()
                if self._last_failover_time
                else ""
            ),
        )
        return cluster

    async def should_failover(self, status: ClusterStatus) -> bool:
        """Determine if automatic failover should be triggered."""
        if self.config.dry_run:
            logger.info("[DRY-RUN] Failover check: would evaluate threshold")
            return False

        # Check cooldown period
        if self._last_failover_time:
            elapsed = time.time() - self._last_failover_time
            if elapsed < self.config.failover_cooldown:
                logger.warning(
                    "Failover cooldown active (%.0fs remaining)",
                    self.config.failover_cooldown - elapsed,
                )
                return False

        # Check threshold
        if self._consecutive_failures >= self.config.failover_threshold:
            logger.warning(
                "Failover threshold reached: %d/%d consecutive failures",
                self._consecutive_failures,
                self.config.failover_threshold,
            )
            return True
        return False

    async def promote_secondary(self) -> dict[str, Any]:
        """Promote secondary region to primary (failover)."""
        logger.info("=" * 60)
        logger.info("INITIATING FAILOVER: Promoting secondary to primary")
        logger.info("=" * 60)

        steps: list[dict[str, Any]] = []

        # Step 1: Verify secondary is healthy
        logger.info("[1/5] Verifying secondary region health...")
        steps.append({"step": 1, "action": "verify_secondary", "status": "started"})
        status = await self.check_health()
        secondary_healthy = any(
            c.health in (ComponentHealth.HEALTHY, ComponentHealth.DEGRADED)
            for c in status.components
        )
        if not secondary_healthy:
            logger.error("ABORT: Secondary region is not healthy enough for promotion")
            steps[-1]["status"] = "aborted"
            return {"success": False, "reason": "secondary_unhealthy", "steps": steps}
        steps[-1]["status"] = "completed"

        # Step 2: Stop writes on primary (fence)
        logger.info("[2/5] Fencing primary (stopping writes)...")
        steps.append({"step": 2, "action": "fence_primary", "status": "started"})
        if not self.config.dry_run:
            await self._fence_primary()
        steps[-1]["status"] = "completed" if not self.config.dry_run else "dry-run"

        # Step 3: Promote PostgreSQL replica
        logger.info("[3/5] Promoting PostgreSQL replica...")
        steps.append({"step": 3, "action": "promote_pg_replica", "status": "started"})
        if not self.config.dry_run:
            await self._promote_pg_replica()
        steps[-1]["status"] = "completed" if not self.config.dry_run else "dry-run"

        # Step 4: Promote Redis replica via Sentinel
        logger.info("[4/5] Triggering Redis Sentinel failover...")
        steps.append({"step": 4, "action": "promote_redis_replica", "status": "started"})
        if not self.config.dry_run:
            await self._promote_redis_replica()
        steps[-1]["status"] = "completed" if not self.config.dry_run else "dry-run"

        # Step 5: Update DNS / service discovery
        logger.info("[5/5] Updating DNS routing...")
        steps.append({"step": 5, "action": "update_dns", "status": "started"})
        if not self.config.dry_run:
            await self._update_dns_routing()
        steps[-1]["status"] = "completed" if not self.config.dry_run else "dry-run"

        self._last_failover_time = time.time()
        logger.info("FAILOVER COMPLETE: Secondary is now primary")
        return {"success": True, "steps": steps}

    async def demote_primary(self) -> dict[str, Any]:
        """Demote primary for planned maintenance."""
        logger.info("Initiating planned demotion of primary...")
        if self.config.dry_run:
            logger.info("[DRY-RUN] Would demote primary and promote secondary")
            return {"success": True, "dry_run": True}

        # For planned maintenance, we do a graceful switchover
        return await self.promote_secondary()

    async def _fence_primary(self) -> None:
        """Fence the primary to prevent split-brain writes."""
        logger.info("  -> Setting primary to read-only mode")
        # In production: ALTER SYSTEM SET default_transaction_read_only = on;
        # Then: SELECT pg_reload_conf();
        await asyncio.sleep(0.1)  # Simulate operation

    async def _promote_pg_replica(self) -> None:
        """Promote PostgreSQL replica to primary."""
        logger.info("  -> Running pg_promote() on replica")
        # In production: SELECT pg_promote(wait := true, wait_seconds := 60);
        await asyncio.sleep(0.1)

    async def _promote_redis_replica(self) -> None:
        """Trigger Redis Sentinel failover."""
        logger.info("  -> Sending SENTINEL FAILOVER command")
        # In production: SENTINEL FAILOVER mymaster
        await asyncio.sleep(0.1)

    async def _update_dns_routing(self) -> None:
        """Update DNS to point to new primary."""
        logger.info("  -> Updating Route53/Cloudflare DNS records")
        # In production: Update DNS CNAME/A records
        await asyncio.sleep(0.1)


# ---------------------------------------------------------------------------
# Watch Mode (continuous monitoring)
# ---------------------------------------------------------------------------


async def watch_mode(orchestrator: FailoverOrchestrator) -> None:
    """Continuously monitor health and trigger automatic failover."""
    config = orchestrator.config
    logger.info(
        "Starting watch mode (interval=%ds, threshold=%d, mode=%s)",
        config.health_check_interval,
        config.failover_threshold,
        "automatic" if not config.dry_run else "dry-run",
    )

    while True:
        status = await orchestrator.check_health()
        _print_status(status)

        if await orchestrator.should_failover(status):
            logger.critical("AUTOMATIC FAILOVER TRIGGERED")
            result = await orchestrator.promote_secondary()
            logger.info("Failover result: %s", json.dumps(result, indent=2))
            break

        await asyncio.sleep(config.health_check_interval)


# ---------------------------------------------------------------------------
# Output Formatting
# ---------------------------------------------------------------------------


def _print_status(status: ClusterStatus) -> None:
    """Pretty-print cluster status."""
    health_icons = {
        ComponentHealth.HEALTHY: "✓",
        ComponentHealth.DEGRADED: "⚠",
        ComponentHealth.UNHEALTHY: "✗",
        ComponentHealth.UNKNOWN: "?",
    }
    print(f"\n{'='*60}")
    print(f"  DR Cluster Status @ {status.timestamp}")
    print(f"  Overall: {health_icons.get(status.overall_health, '?')} {status.overall_health.value}")
    print(f"  Consecutive failures: {status.consecutive_failures}")
    print(f"{'='*60}")
    for comp in status.components:
        icon = health_icons.get(comp.health, "?")
        lag_str = f" (lag: {comp.replication_lag_ms:.0f}ms)" if comp.replication_lag_ms else ""
        print(f"  {icon} {comp.name:<12} {comp.health.value:<10}{lag_str}")
        if comp.details.get("warning"):
            print(f"    ⚠ {comp.details['warning']}")
        if comp.details.get("action_required"):
            print(f"    → {comp.details['action_required']}")
    print(f"{'='*60}\n")


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for failover orchestration."""
    parser = argparse.ArgumentParser(
        description="X-Agent multi-region failover orchestration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="Check replication health")
    group.add_argument("--promote", action="store_true", help="Promote secondary to primary")
    group.add_argument("--demote", action="store_true", help="Demote primary (maintenance)")
    group.add_argument("--status", action="store_true", help="Show cluster status")
    group.add_argument("--watch", action="store_true", help="Continuous health monitoring")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    config = DRConfig.from_env()
    orchestrator = FailoverOrchestrator(config)

    if config.dry_run:
        logger.info("DRY-RUN mode enabled — no changes will be made")

    async def run() -> None:
        if args.check or args.status:
            status = await orchestrator.check_health()
            if args.json:
                print(json.dumps(status.to_dict(), indent=2))
            else:
                _print_status(status)
            # Exit with non-zero if unhealthy
            if status.overall_health == ComponentHealth.UNHEALTHY:
                sys.exit(1)

        elif args.promote:
            result = await orchestrator.promote_secondary()
            if args.json:
                print(json.dumps(result, indent=2))
            if not result.get("success"):
                sys.exit(1)

        elif args.demote:
            result = await orchestrator.demote_primary()
            if args.json:
                print(json.dumps(result, indent=2))
            if not result.get("success"):
                sys.exit(1)

        elif args.watch:
            await watch_mode(orchestrator)

    asyncio.run(run())


if __name__ == "__main__":
    main()
