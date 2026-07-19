"""Performance optimization integration for X-Agent.

Integrates all performance optimization components and provides unified API.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.app.core.performance_cache import MultiLayerCache, MemoryCacheBackend, RedisCacheBackend
from backend.app.core.database_optimization import DatabaseOptimizationManager
from backend.app.core.concurrency_optimization import AdaptiveConcurrencyLimiter
from backend.app.core.error_handling_optimization import ErrorRecoveryManager
from backend.app.core.performance_monitoring import (
    PerformanceMonitor,
    PerformanceAlert,
    PerformanceOptimizationTracker,
)

logger = logging.getLogger("xagent.performance_optimization")


class PerformanceOptimizationManager:
    """Unified performance optimization manager."""

    def __init__(
        self,
        database_url: str = "sqlite:///./data/xagent.db",
        enable_redis_cache: bool = False,
        redis_url: str = "redis://localhost:6379",
        initial_concurrency_limit: int = 10,
    ):
        # Initialize cache system
        l1_cache = MemoryCacheBackend(max_size=10000, default_ttl=3600)
        l2_cache = RedisCacheBackend(redis_url=redis_url) if enable_redis_cache else None
        self._cache = MultiLayerCache(
            l1_backend=l1_cache,
            l2_backend=l2_cache,
            enable_l2=enable_redis_cache,
        )

        # Initialize database optimization
        self._db_optimizer = DatabaseOptimizationManager(database_url)

        # Initialize concurrency control
        self._concurrency_limiter = AdaptiveConcurrencyLimiter(
            initial_limit=initial_concurrency_limit,
        )

        # Initialize error recovery
        self._error_recovery = ErrorRecoveryManager()

        # Initialize performance monitoring
        self._performance_monitor = PerformanceMonitor()
        self._performance_alert = PerformanceAlert()
        self._optimization_tracker = PerformanceOptimizationTracker()

        # Set baseline metrics
        self._set_baseline_metrics()

    def _set_baseline_metrics(self) -> None:
        """Set baseline performance metrics."""
        # These are typical baseline values for X-Agent
        self._optimization_tracker.set_baseline("avg_response_time_ms", 163.6)
        self._optimization_tracker.set_baseline("p95_response_time_ms", 380.1)
        self._optimization_tracker.set_baseline("throughput_rps", 600)
        self._optimization_tracker.set_baseline("error_rate", 0.02)

    def get_cache(self) -> MultiLayerCache:
        """Get cache system."""
        return self._cache

    def get_db_optimizer(self) -> DatabaseOptimizationManager:
        """Get database optimizer."""
        return self._db_optimizer

    def get_concurrency_limiter(self) -> AdaptiveConcurrencyLimiter:
        """Get concurrency limiter."""
        return self._concurrency_limiter

    def get_error_recovery(self) -> ErrorRecoveryManager:
        """Get error recovery manager."""
        return self._error_recovery

    def get_performance_monitor(self) -> PerformanceMonitor:
        """Get performance monitor."""
        return self._performance_monitor

    def get_performance_alert(self) -> PerformanceAlert:
        """Get performance alert system."""
        return self._performance_alert

    def get_optimization_tracker(self) -> PerformanceOptimizationTracker:
        """Get optimization tracker."""
        return self._optimization_tracker

    async def get_performance_report(self) -> dict[str, Any]:
        """Get comprehensive performance report."""
        monitor_summary = self._performance_monitor.get_summary()
        optimization_summary = self._optimization_tracker.get_optimization_summary()
        error_stats = self._error_recovery.get_stats()
        concurrency_stats = self._concurrency_limiter.get_stats()
        cache_stats = self._cache.get_stats()
        db_stats = self._db_optimizer.get_stats()

        performance_score = self._optimization_tracker.get_performance_score()

        return {
            "performance_score": performance_score,
            "monitor_summary": monitor_summary,
            "optimization_summary": optimization_summary,
            "error_stats": error_stats,
            "concurrency_stats": concurrency_stats,
            "cache_stats": cache_stats,
            "db_stats": db_stats,
            "timestamp": __import__("datetime").datetime.now(__import__("datetime").UTC).isoformat(),
        }

    async def record_request(
        self,
        endpoint: str,
        method: str,
        duration_ms: float,
        error: bool = False,
    ) -> None:
        """Record request for performance tracking."""
        await self._performance_monitor.record_request(
            endpoint=endpoint,
            method=method,
            duration_ms=duration_ms,
            error=error,
        )

        # Record optimization progress
        if not error:
            self._optimization_tracker.record_optimization("avg_response_time_ms", duration_ms)

    def get_optimization_status(self) -> dict[str, Any]:
        """Get optimization status."""
        return {
            "cache_enabled": True,
            "cache_stats": self._cache.get_stats(),
            "db_optimization_enabled": True,
            "db_stats": self._db_optimizer.get_stats(),
            "concurrency_control_enabled": True,
            "concurrency_stats": self._concurrency_limiter.get_stats(),
            "error_recovery_enabled": True,
            "error_stats": self._error_recovery.get_stats(),
            "performance_monitoring_enabled": True,
            "performance_score": self._optimization_tracker.get_performance_score(),
        }


# Global performance optimization manager instance
_performance_manager: PerformanceOptimizationManager | None = None


def get_performance_manager() -> PerformanceOptimizationManager:
    """Get global performance optimization manager."""
    global _performance_manager
    if _performance_manager is None:
        _performance_manager = PerformanceOptimizationManager()
    return _performance_manager


def initialize_performance_optimization(
    database_url: str = "sqlite:///./data/xagent.db",
    enable_redis_cache: bool = False,
    redis_url: str = "redis://localhost:6379",
    initial_concurrency_limit: int = 10,
) -> PerformanceOptimizationManager:
    """Initialize performance optimization system."""
    global _performance_manager
    _performance_manager = PerformanceOptimizationManager(
        database_url=database_url,
        enable_redis_cache=enable_redis_cache,
        redis_url=redis_url,
        initial_concurrency_limit=initial_concurrency_limit,
    )
    logger.info("Performance optimization system initialized")
    return _performance_manager
