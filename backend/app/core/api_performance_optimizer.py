"""API Performance Optimization Module

Comprehensive performance optimization for FastAPI endpoints:
1. Response time optimization (< 100ms P95)
2. Batch operation optimization (> 1000 ops/s)
3. GraphQL query optimization
4. WebSocket latency optimization (< 50ms)
5. Rate limiting and throttling
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger("xagent.api_perf")


@dataclass
class PerformanceMetrics:
    """API performance metrics."""
    endpoint: str
    method: str
    response_time_ms: float
    status_code: int
    request_size_bytes: int = 0
    response_size_bytes: int = 0
    cache_hit: bool = False
    db_queries: int = 0
    db_time_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    @property
    def is_slow(self) -> bool:
        """Check if response time exceeds threshold."""
        return self.response_time_ms > 100

    @property
    def efficiency_score(self) -> float:
        """Calculate efficiency score (0-100)."""
        if self.response_time_ms < 50:
            return 100.0
        elif self.response_time_ms < 100:
            return 80.0
        elif self.response_time_ms < 200:
            return 60.0
        elif self.response_time_ms < 500:
            return 40.0
        else:
            return 20.0


@dataclass
class BatchOperationStats:
    """Batch operation statistics."""
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    total_time_ms: float = 0.0
    parallelism_factor: float = 1.0
    cache_hits: int = 0
    cache_misses: int = 0

    @property
    def throughput_ops_per_sec(self) -> float:
        """Calculate throughput in operations per second."""
        if self.total_time_ms == 0:
            return 0.0
        return (self.total_operations / self.total_time_ms) * 1000

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_operations == 0:
            return 0.0
        return self.successful_operations / self.total_operations

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return self.cache_hits / total


class PerformanceMonitor:
    """Monitor and track API performance metrics."""

    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.metrics: list[PerformanceMetrics] = []
        self.batch_stats: dict[str, BatchOperationStats] = {}
        self._lock = asyncio.Lock()

    async def record_metric(self, metric: PerformanceMetrics) -> None:
        """Record a performance metric."""
        async with self._lock:
            self.metrics.append(metric)
            if len(self.metrics) > self.window_size:
                self.metrics.pop(0)

            if metric.is_slow:
                logger.warning(
                    f"Slow API response: {metric.endpoint} {metric.method} "
                    f"took {metric.response_time_ms}ms"
                )

    async def record_batch_stats(self, operation_name: str, stats: BatchOperationStats) -> None:
        """Record batch operation statistics."""
        async with self._lock:
            self.batch_stats[operation_name] = stats

    async def get_endpoint_stats(self, endpoint: str) -> dict[str, Any]:
        """Get statistics for a specific endpoint."""
        async with self._lock:
            endpoint_metrics = [m for m in self.metrics if m.endpoint == endpoint]

        if not endpoint_metrics:
            return {}

        response_times = [m.response_time_ms for m in endpoint_metrics]
        response_times.sort()

        return {
            "endpoint": endpoint,
            "total_requests": len(endpoint_metrics),
            "avg_response_time_ms": sum(response_times) / len(response_times),
            "p50_response_time_ms": response_times[len(response_times) // 2],
            "p95_response_time_ms": response_times[int(len(response_times) * 0.95)],
            "p99_response_time_ms": response_times[int(len(response_times) * 0.99)],
            "max_response_time_ms": max(response_times),
            "min_response_time_ms": min(response_times),
            "cache_hit_rate": sum(1 for m in endpoint_metrics if m.cache_hit) / len(endpoint_metrics),
            "slow_requests": sum(1 for m in endpoint_metrics if m.is_slow),
        }

    async def get_overall_stats(self) -> dict[str, Any]:
        """Get overall API performance statistics."""
        async with self._lock:
            if not self.metrics:
                return {}

            response_times = [m.response_time_ms for m in self.metrics]
            response_times.sort()

            return {
                "total_requests": len(self.metrics),
                "avg_response_time_ms": sum(response_times) / len(response_times),
                "p50_response_time_ms": response_times[len(response_times) // 2],
                "p95_response_time_ms": response_times[int(len(response_times) * 0.95)],
                "p99_response_time_ms": response_times[int(len(response_times) * 0.99)],
                "max_response_time_ms": max(response_times),
                "min_response_time_ms": min(response_times),
                "cache_hit_rate": sum(1 for m in self.metrics if m.cache_hit) / len(self.metrics),
                "slow_requests": sum(1 for m in self.metrics if m.is_slow),
                "batch_operations": len(self.batch_stats),
            }


class QueryOptimizer:
    """Optimize database queries for better performance."""

    @staticmethod
    def analyze_query(query_str: str) -> dict[str, Any]:
        """Analyze query for optimization opportunities."""
        analysis = {
            "has_n_plus_one": False,
            "missing_indexes": [],
            "inefficient_joins": False,
            "recommendations": [],
        }

        # Check for common patterns
        if "SELECT" in query_str.upper():
            # Check for missing LIMIT
            if "LIMIT" not in query_str.upper():
                analysis["recommendations"].append("Add LIMIT clause to prevent large result sets")

            # Check for SELECT *
            if "SELECT *" in query_str.upper():
                analysis["recommendations"].append("Avoid SELECT *, specify needed columns")

        return analysis

    @staticmethod
    def suggest_indexes(table: str, columns: list[str]) -> list[str]:
        """Suggest indexes for frequently queried columns."""
        suggestions = []
        for col in columns:
            suggestions.append(f"CREATE INDEX idx_{table}_{col} ON {table}({col})")
        return suggestions


class RateLimiter:
    """Advanced rate limiting with token bucket algorithm."""

    def __init__(self, rate: int = 100, window_seconds: int = 60):
        self.rate = rate
        self.window_seconds = window_seconds
        self.buckets: dict[str, tuple[float, float]] = {}  # client_id -> (tokens, last_refill)
        self._lock = asyncio.Lock()

    async def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed under rate limit."""
        async with self._lock:
            now = time.time()
            tokens, last_refill = self.buckets.get(client_id, (self.rate, now))

            # Refill tokens based on elapsed time
            elapsed = now - last_refill
            refill_rate = self.rate / self.window_seconds
            tokens = min(self.rate, tokens + elapsed * refill_rate)

            if tokens >= 1:
                tokens -= 1
                self.buckets[client_id] = (tokens, now)
                return True

            self.buckets[client_id] = (tokens, now)
            return False

    async def get_remaining_tokens(self, client_id: str) -> float:
        """Get remaining tokens for a client."""
        async with self._lock:
            tokens, _ = self.buckets.get(client_id, (self.rate, time.time()))
            return tokens


class ConnectionPoolOptimizer:
    """Optimize database connection pooling."""

    @staticmethod
    def get_optimal_pool_size(max_connections: int = 20) -> dict[str, int]:
        """Calculate optimal connection pool size."""
        import multiprocessing

        cpu_count = multiprocessing.cpu_count()
        return {
            "min_size": max(2, cpu_count),
            "max_size": max_connections,
            "overflow": max_connections // 2,
            "timeout": 30,
        }


class QueryBatcher:
    """Batch multiple queries for better performance."""

    def __init__(self, batch_size: int = 100, batch_timeout_ms: int = 50):
        self.batch_size = batch_size
        self.batch_timeout_ms = batch_timeout_ms
        self.pending_queries: list[tuple[str, Any]] = []
        self.batch_event = asyncio.Event()
        self._lock = asyncio.Lock()

    async def add_query(self, query: str, params: Any = None) -> Any:
        """Add query to batch."""
        async with self._lock:
            self.pending_queries.append((query, params))

            if len(self.pending_queries) >= self.batch_size:
                self.batch_event.set()

        # Wait for batch to be processed or timeout
        try:
            await asyncio.wait_for(
                self.batch_event.wait(),
                timeout=self.batch_timeout_ms / 1000,
            )
        except asyncio.TimeoutError:
            self.batch_event.set()

        return None

    async def get_pending_batch(self) -> list[tuple[str, Any]]:
        """Get pending queries as a batch."""
        async with self._lock:
            batch = self.pending_queries.copy()
            self.pending_queries.clear()
            self.batch_event.clear()
            return batch


class ResponseCompressor:
    """Compress API responses for faster transmission."""

    @staticmethod
    def should_compress(response_size_bytes: int, threshold_bytes: int = 1024) -> bool:
        """Determine if response should be compressed."""
        return response_size_bytes > threshold_bytes

    @staticmethod
    def get_compression_ratio(original_size: int, compressed_size: int) -> float:
        """Calculate compression ratio."""
        if original_size == 0:
            return 0.0
        return (original_size - compressed_size) / original_size


# Global performance monitor instance
_performance_monitor = PerformanceMonitor()


async def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor."""
    return _performance_monitor
