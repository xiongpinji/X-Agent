"""Performance monitoring and metrics collection for X-Agent.

Implements real-time performance tracking, metrics aggregation, and performance alerts.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger("xagent.performance_monitoring")


@dataclass
class PerformanceMetrics:
    """Performance metrics for tracking."""

    endpoint: str
    method: str
    total_requests: int = 0
    total_time_ms: float = 0.0
    min_time_ms: float = float("inf")
    max_time_ms: float = 0.0
    error_count: int = 0
    p50_time_ms: float = 0.0
    p95_time_ms: float = 0.0
    p99_time_ms: float = 0.0
    response_times: list[float] = field(default_factory=list)
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def avg_time_ms(self) -> float:
        """Calculate average response time."""
        return self.total_time_ms / self.total_requests if self.total_requests > 0 else 0.0

    @property
    def error_rate(self) -> float:
        """Calculate error rate."""
        return self.error_count / self.total_requests if self.total_requests > 0 else 0.0

    def record_request(self, duration_ms: float, error: bool = False) -> None:
        """Record a request."""
        self.total_requests += 1
        self.total_time_ms += duration_ms
        self.min_time_ms = min(self.min_time_ms, duration_ms)
        self.max_time_ms = max(self.max_time_ms, duration_ms)
        self.response_times.append(duration_ms)

        # Keep only last 1000 response times for percentile calculation
        if len(self.response_times) > 1000:
            self.response_times.pop(0)

        # Update percentiles
        self._update_percentiles()

        if error:
            self.error_count += 1

        self.last_updated = datetime.now(UTC)

    def _update_percentiles(self) -> None:
        """Update percentile metrics."""
        if not self.response_times:
            return

        sorted_times = sorted(self.response_times)
        n = len(sorted_times)

        # P50 (median)
        self.p50_time_ms = sorted_times[n // 2]

        # P95
        p95_idx = int(n * 0.95)
        self.p95_time_ms = sorted_times[p95_idx]

        # P99
        p99_idx = int(n * 0.99)
        self.p99_time_ms = sorted_times[p99_idx]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "endpoint": self.endpoint,
            "method": self.method,
            "total_requests": self.total_requests,
            "avg_time_ms": self.avg_time_ms,
            "min_time_ms": self.min_time_ms,
            "max_time_ms": self.max_time_ms,
            "p50_time_ms": self.p50_time_ms,
            "p95_time_ms": self.p95_time_ms,
            "p99_time_ms": self.p99_time_ms,
            "error_count": self.error_count,
            "error_rate": self.error_rate,
            "last_updated": self.last_updated.isoformat(),
        }


class PerformanceMonitor:
    """Monitor and track performance metrics."""

    def __init__(self, retention_hours: int = 24):
        self._metrics: dict[str, PerformanceMetrics] = {}
        self._retention_hours = retention_hours
        self._lock = asyncio.Lock()

    async def record_request(
        self,
        endpoint: str,
        method: str,
        duration_ms: float,
        error: bool = False,
    ) -> None:
        """Record a request."""
        key = f"{method}:{endpoint}"

        async with self._lock:
            if key not in self._metrics:
                self._metrics[key] = PerformanceMetrics(endpoint=endpoint, method=method)

            self._metrics[key].record_request(duration_ms, error)

    async def get_metrics(self, endpoint: str | None = None) -> list[PerformanceMetrics]:
        """Get metrics for endpoint(s)."""
        async with self._lock:
            if endpoint:
                return [m for m in self._metrics.values() if m.endpoint == endpoint]
            return list(self._metrics.values())

    async def get_slow_endpoints(self, threshold_ms: float = 100.0, limit: int = 10) -> list[PerformanceMetrics]:
        """Get slowest endpoints."""
        async with self._lock:
            slow = [m for m in self._metrics.values() if m.avg_time_ms > threshold_ms]
            return sorted(slow, key=lambda m: m.avg_time_ms, reverse=True)[:limit]

    async def get_error_endpoints(self, threshold_rate: float = 0.01, limit: int = 10) -> list[PerformanceMetrics]:
        """Get endpoints with high error rates."""
        async with self._lock:
            errors = [m for m in self._metrics.values() if m.error_rate > threshold_rate]
            return sorted(errors, key=lambda m: m.error_rate, reverse=True)[:limit]

    async def cleanup_old_metrics(self) -> None:
        """Clean up old metrics."""
        cutoff_time = datetime.now(UTC) - timedelta(hours=self._retention_hours)

        async with self._lock:
            keys_to_delete = [
                k for k, m in self._metrics.items() if m.last_updated < cutoff_time
            ]
            for key in keys_to_delete:
                del self._metrics[key]

    def get_summary(self) -> dict[str, Any]:
        """Get performance summary."""
        if not self._metrics:
            return {}

        all_metrics = list(self._metrics.values())
        total_requests = sum(m.total_requests for m in all_metrics)
        total_errors = sum(m.error_count for m in all_metrics)
        avg_response_time = sum(m.total_time_ms for m in all_metrics) / total_requests if total_requests > 0 else 0

        return {
            "total_endpoints": len(self._metrics),
            "total_requests": total_requests,
            "total_errors": total_errors,
            "error_rate": total_errors / total_requests if total_requests > 0 else 0,
            "avg_response_time_ms": avg_response_time,
            "max_response_time_ms": max((m.max_time_ms for m in all_metrics), default=0),
            "min_response_time_ms": min((m.min_time_ms for m in all_metrics), default=0),
        }


class PerformanceAlert:
    """Performance alert system."""

    def __init__(
        self,
        slow_endpoint_threshold_ms: float = 500.0,
        error_rate_threshold: float = 0.05,
        check_interval_seconds: int = 60,
    ):
        self._slow_endpoint_threshold_ms = slow_endpoint_threshold_ms
        self._error_rate_threshold = error_rate_threshold
        self._check_interval_seconds = check_interval_seconds
        self._alerts: list[dict[str, Any]] = []
        self._alert_callbacks: list[Callable] = []

    def register_alert_callback(self, callback: Callable) -> None:
        """Register callback for alerts."""
        self._alert_callbacks.append(callback)

    async def check_performance(self, monitor: PerformanceMonitor) -> None:
        """Check performance and trigger alerts."""
        # Check for slow endpoints
        slow_endpoints = await monitor.get_slow_endpoints(
            threshold_ms=self._slow_endpoint_threshold_ms,
        )
        for endpoint in slow_endpoints:
            alert = {
                "type": "slow_endpoint",
                "endpoint": endpoint.endpoint,
                "avg_time_ms": endpoint.avg_time_ms,
                "threshold_ms": self._slow_endpoint_threshold_ms,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            self._alerts.append(alert)
            await self._trigger_alert(alert)

        # Check for high error rates
        error_endpoints = await monitor.get_error_endpoints(
            threshold_rate=self._error_rate_threshold,
        )
        for endpoint in error_endpoints:
            alert = {
                "type": "high_error_rate",
                "endpoint": endpoint.endpoint,
                "error_rate": endpoint.error_rate,
                "threshold_rate": self._error_rate_threshold,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            self._alerts.append(alert)
            await self._trigger_alert(alert)

    async def _trigger_alert(self, alert: dict[str, Any]) -> None:
        """Trigger alert callbacks."""
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

    def get_alerts(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent alerts."""
        return self._alerts[-limit:]


class PerformanceOptimizationTracker:
    """Track performance optimization progress."""

    def __init__(self):
        self._baseline_metrics: dict[str, float] = {}
        self._current_metrics: dict[str, float] = {}
        self._optimization_history: list[dict[str, Any]] = []

    def set_baseline(self, metric_name: str, value: float) -> None:
        """Set baseline metric."""
        self._baseline_metrics[metric_name] = value

    def record_optimization(self, metric_name: str, value: float) -> None:
        """Record optimization result."""
        self._current_metrics[metric_name] = value

        if metric_name in self._baseline_metrics:
            baseline = self._baseline_metrics[metric_name]
            improvement = ((baseline - value) / baseline * 100) if baseline > 0 else 0
            self._optimization_history.append({
                "metric": metric_name,
                "baseline": baseline,
                "current": value,
                "improvement_percent": improvement,
                "timestamp": datetime.now(UTC).isoformat(),
            })

    def get_optimization_summary(self) -> dict[str, Any]:
        """Get optimization summary."""
        if not self._optimization_history:
            return {}

        total_improvement = sum(h["improvement_percent"] for h in self._optimization_history)
        avg_improvement = total_improvement / len(self._optimization_history)

        return {
            "total_optimizations": len(self._optimization_history),
            "avg_improvement_percent": avg_improvement,
            "optimizations": self._optimization_history,
        }

    def get_performance_score(self) -> float:
        """Calculate overall performance score (0-100)."""
        if not self._current_metrics:
            return 0.0

        # Base score
        score = 50.0

        # Add points for improvements
        for metric_name, current_value in self._current_metrics.items():
            if metric_name in self._baseline_metrics:
                baseline = self._baseline_metrics[metric_name]
                if baseline > 0:
                    improvement = (baseline - current_value) / baseline
                    score += improvement * 50.0

        return min(100.0, max(0.0, score))
