"""
Resource monitoring and metrics collection for X-Agent.

Implements:
- Connection pool monitoring
- Concurrency limiter monitoring
- Task queue monitoring
- Resource usage alerts
- Metrics export
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ResourceAlert:
    """Alert for resource exhaustion."""

    timestamp: float = field(default_factory=time.time)
    alert_type: str = ""
    severity: str = "warning"  # "info", "warning", "critical"
    message: str = ""
    resource_name: str = ""
    current_value: float = 0.0
    threshold: float = 0.0


class ResourceMonitor:
    """
    Monitor resource usage and enforce limits.

    Features:
    - Connection pool monitoring
    - Concurrency limiter monitoring
    - Task queue monitoring
    - Alert generation
    - Metrics collection
    """

    def __init__(
        self,
        check_interval: float = 10.0,
        pool_utilization_threshold: float = 0.8,
        queue_size_threshold: float = 0.8,
        active_tasks_threshold: float = 0.9,
    ) -> None:
        self._check_interval = check_interval
        self._pool_utilization_threshold = pool_utilization_threshold
        self._queue_size_threshold = queue_size_threshold
        self._active_tasks_threshold = active_tasks_threshold

        self._pools: dict[str, Any] = {}
        self._limiters: dict[str, Any] = {}
        self._queues: dict[str, Any] = {}
        self._alerts: list[ResourceAlert] = []
        self._alert_callbacks: list[Callable[[ResourceAlert], None]] = []
        self._lock = asyncio.Lock()
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start the resource monitor."""
        if self._running:
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Resource monitor started")

    async def stop(self) -> None:
        """Stop the resource monitor."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Resource monitor stopped")

    async def register_pool(self, name: str, pool: Any) -> None:
        """Register a connection pool for monitoring."""
        async with self._lock:
            self._pools[name] = pool

    async def register_limiter(self, name: str, limiter: Any) -> None:
        """Register a concurrency limiter for monitoring."""
        async with self._lock:
            self._limiters[name] = limiter

    async def register_queue(self, name: str, queue: Any) -> None:
        """Register a task queue for monitoring."""
        async with self._lock:
            self._queues[name] = queue

    def add_alert_callback(self, callback: Callable[[ResourceAlert], None]) -> None:
        """Add a callback for alerts."""
        self._alert_callbacks.append(callback)

    async def _monitor_loop(self) -> None:
        """Periodically check resource usage."""
        while self._running:
            try:
                await asyncio.sleep(self._check_interval)
                await self._check_resources()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")

    async def _check_resources(self) -> None:
        """Check resource usage and generate alerts."""
        async with self._lock:
            # Check pools
            for name, pool in self._pools.items():
                await self._check_pool(name, pool)

            # Check limiters
            for name, limiter in self._limiters.items():
                await self._check_limiter(name, limiter)

            # Check queues
            for name, queue in self._queues.items():
                await self._check_queue(name, queue)

    async def _check_pool(self, name: str, pool: Any) -> None:
        """Check connection pool usage."""
        try:
            stats = pool.get_stats()
            if stats.total_connections == 0:
                return

            utilization = stats.active_connections / stats.total_connections
            if utilization > self._pool_utilization_threshold:
                alert = ResourceAlert(
                    alert_type="pool_utilization",
                    severity="warning" if utilization < 0.95 else "critical",
                    message=f"Pool {name} utilization high: {utilization:.1%}",
                    resource_name=name,
                    current_value=utilization,
                    threshold=self._pool_utilization_threshold,
                )
                await self._emit_alert(alert)

            if stats.errors > 0:
                alert = ResourceAlert(
                    alert_type="pool_error",
                    severity="warning",
                    message=f"Pool {name} has {stats.errors} errors",
                    resource_name=name,
                    current_value=stats.errors,
                )
                await self._emit_alert(alert)

        except Exception as e:
            logger.error(f"Error checking pool {name}: {e}")

    async def _check_limiter(self, name: str, limiter: Any) -> None:
        """Check concurrency limiter usage."""
        try:
            stats = limiter.get_stats()
            max_concurrent = stats.get("max_concurrent", 0)
            if max_concurrent == 0:
                return

            active_ratio = stats.get("active_tasks", 0) / max_concurrent
            if active_ratio > self._active_tasks_threshold:
                alert = ResourceAlert(
                    alert_type="limiter_saturation",
                    severity="warning" if active_ratio < 0.99 else "critical",
                    message=f"Limiter {name} saturation high: {active_ratio:.1%}",
                    resource_name=name,
                    current_value=active_ratio,
                    threshold=self._active_tasks_threshold,
                )
                await self._emit_alert(alert)

            success_rate = stats.get("success_rate", 1.0)
            if success_rate < 0.8:
                alert = ResourceAlert(
                    alert_type="limiter_failure_rate",
                    severity="critical",
                    message=f"Limiter {name} success rate low: {success_rate:.1%}",
                    resource_name=name,
                    current_value=success_rate,
                    threshold=0.8,
                )
                await self._emit_alert(alert)

        except Exception as e:
            logger.error(f"Error checking limiter {name}: {e}")

    async def _check_queue(self, name: str, queue: Any) -> None:
        """Check task queue usage."""
        try:
            stats = queue.get_stats()
            queue_size = stats.get("queue_size", 0)
            max_size = stats.get("max_queue_size", 1000)

            if max_size > 0:
                queue_utilization = queue_size / max_size
                if queue_utilization > self._queue_size_threshold:
                    alert = ResourceAlert(
                        alert_type="queue_backlog",
                        severity="warning" if queue_utilization < 0.95 else "critical",
                        message=f"Queue {name} backlog high: {queue_utilization:.1%}",
                        resource_name=name,
                        current_value=queue_utilization,
                        threshold=self._queue_size_threshold,
                    )
                    await self._emit_alert(alert)

            failed_tasks = stats.get("failed_tasks", 0)
            if failed_tasks > 0:
                alert = ResourceAlert(
                    alert_type="queue_failure",
                    severity="warning",
                    message=f"Queue {name} has {failed_tasks} failed tasks",
                    resource_name=name,
                    current_value=failed_tasks,
                )
                await self._emit_alert(alert)

        except Exception as e:
            logger.error(f"Error checking queue {name}: {e}")

    async def _emit_alert(self, alert: ResourceAlert) -> None:
        """Emit an alert."""
        async with self._lock:
            self._alerts.append(alert)

        logger.log(
            logging.WARNING if alert.severity == "warning" else logging.ERROR,
            f"[{alert.alert_type}] {alert.message}",
        )

        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

    def get_report(self) -> dict[str, Any]:
        """Get comprehensive resource usage report."""
        report = {
            "timestamp": time.time(),
            "pools": {},
            "limiters": {},
            "queues": {},
            "alerts": [],
        }

        # Collect pool stats
        for name, pool in self._pools.items():
            try:
                stats = pool.get_stats()
                report["pools"][name] = {
                    "total_connections": stats.total_connections,
                    "active_connections": stats.active_connections,
                    "idle_connections": stats.idle_connections,
                    "peak_active": stats.peak_active,
                    "errors": stats.errors,
                    "utilization": (
                        stats.active_connections / stats.total_connections
                        if stats.total_connections > 0
                        else 0
                    ),
                }
            except Exception as e:
                logger.error(f"Error getting pool stats for {name}: {e}")

        # Collect limiter stats
        for name, limiter in self._limiters.items():
            try:
                stats = limiter.get_stats()
                report["limiters"][name] = stats
            except Exception as e:
                logger.error(f"Error getting limiter stats for {name}: {e}")

        # Collect queue stats
        for name, queue in self._queues.items():
            try:
                stats = queue.get_stats()
                report["queues"][name] = stats
            except Exception as e:
                logger.error(f"Error getting queue stats for {name}: {e}")

        # Include recent alerts
        report["alerts"] = [
            {
                "timestamp": alert.timestamp,
                "type": alert.alert_type,
                "severity": alert.severity,
                "message": alert.message,
                "resource": alert.resource_name,
            }
            for alert in self._alerts[-100:]  # Last 100 alerts
        ]

        return report

    def get_health_status(self) -> dict[str, Any]:
        """Get health status of all resources."""
        status = {
            "healthy": True,
            "issues": [],
        }

        # Check for critical alerts
        for alert in self._alerts[-50:]:  # Check last 50 alerts
            if alert.severity == "critical":
                status["healthy"] = False
                status["issues"].append(
                    {
                        "type": alert.alert_type,
                        "resource": alert.resource_name,
                        "message": alert.message,
                    }
                )

        return status


# Global resource monitor
_resource_monitor: ResourceMonitor | None = None


def get_resource_monitor() -> ResourceMonitor:
    """Get or create the global resource monitor."""
    global _resource_monitor
    if _resource_monitor is None:
        _resource_monitor = ResourceMonitor()
    return _resource_monitor


async def close_resource_monitor() -> None:
    """Close the global resource monitor."""
    global _resource_monitor
    if _resource_monitor is not None:
        await _resource_monitor.stop()
        _resource_monitor = None
