"""
Performance Analysis and Profiling Tools.

Identifies performance bottlenecks using cProfile and custom metrics.
Generates detailed performance reports.
"""

from __future__ import annotations

import cProfile
import io
import logging
import pstats
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""

    endpoint: str
    method: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_time: float = 0.0
    min_time: float = float("inf")
    max_time: float = 0.0
    avg_time: float = 0.0
    p95_time: float = 0.0
    p99_time: float = 0.0
    response_times: list[float] = field(default_factory=list)
    error_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    db_queries: int = 0
    db_query_time: float = 0.0

    def update(self, response_time: float, success: bool = True) -> None:
        """Update metrics with new response."""
        self.total_requests += 1
        self.response_times.append(response_time)
        self.total_time += response_time

        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
            self.error_count += 1

        self.min_time = min(self.min_time, response_time)
        self.max_time = max(self.max_time, response_time)
        self.avg_time = self.total_time / self.total_requests

    def calculate_percentiles(self) -> None:
        """Calculate P95 and P99 percentiles."""
        if not self.response_times:
            return

        sorted_times = sorted(self.response_times)
        p95_idx = int(len(sorted_times) * 0.95)
        p99_idx = int(len(sorted_times) * 0.99)

        self.p95_time = sorted_times[p95_idx] if p95_idx < len(sorted_times) else 0.0
        self.p99_time = sorted_times[p99_idx] if p99_idx < len(sorted_times) else 0.0

    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100

    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total_cache_ops = self.cache_hits + self.cache_misses
        if total_cache_ops == 0:
            return 0.0
        return (self.cache_hits / total_cache_ops) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "endpoint": self.endpoint,
            "method": self.method,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": f"{self.success_rate():.2f}%",
            "total_time": f"{self.total_time:.2f}s",
            "min_time": f"{self.min_time:.4f}s",
            "max_time": f"{self.max_time:.4f}s",
            "avg_time": f"{self.avg_time:.4f}s",
            "p95_time": f"{self.p95_time:.4f}s",
            "p99_time": f"{self.p99_time:.4f}s",
            "cache_hit_rate": f"{self.cache_hit_rate():.2f}%",
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "db_queries": self.db_queries,
            "db_query_time": f"{self.db_query_time:.2f}s",
        }


class PerformanceProfiler:
    """Profiles code execution to identify bottlenecks."""

    def __init__(self) -> None:
        self.metrics: dict[str, PerformanceMetrics] = {}
        self.profiler: cProfile.Profile | None = None

    @contextmanager
    def profile_endpoint(self, endpoint: str, method: str = "GET"):
        """Context manager for profiling endpoint calls."""
        if endpoint not in self.metrics:
            self.metrics[endpoint] = PerformanceMetrics(endpoint=endpoint, method=method)

        start_time = time.time()
        try:
            yield
            response_time = time.time() - start_time
            self.metrics[endpoint].update(response_time, success=True)
        except Exception as e:
            response_time = time.time() - start_time
            self.metrics[endpoint].update(response_time, success=False)
            logger.error(f"Error profiling {endpoint}: {e}")
            raise

    def start_profiling(self) -> None:
        """Start cProfile profiling."""
        self.profiler = cProfile.Profile()
        self.profiler.enable()

    def stop_profiling(self) -> str:
        """Stop profiling and return stats."""
        if not self.profiler:
            return ""

        self.profiler.disable()
        s = io.StringIO()
        ps = pstats.Stats(self.profiler, stream=s).sort_stats("cumulative")
        ps.print_stats(20)  # Print top 20 functions
        return s.getvalue()

    def get_metrics(self, endpoint: str | None = None) -> dict[str, Any]:
        """Get metrics for endpoint(s)."""
        if endpoint:
            if endpoint in self.metrics:
                self.metrics[endpoint].calculate_percentiles()
                return self.metrics[endpoint].to_dict()
            return {}

        result = {}
        for ep, metrics in self.metrics.items():
            metrics.calculate_percentiles()
            result[ep] = metrics.to_dict()
        return result

    def generate_report(self) -> str:
        """Generate performance report."""
        report = "=" * 80 + "\n"
        report += "PERFORMANCE ANALYSIS REPORT\n"
        report += "=" * 80 + "\n\n"

        for endpoint, metrics in self.metrics.items():
            metrics.calculate_percentiles()
            report += f"Endpoint: {metrics.method} {endpoint}\n"
            report += "-" * 80 + "\n"
            report += f"  Total Requests:      {metrics.total_requests}\n"
            report += f"  Successful:          {metrics.successful_requests}\n"
            report += f"  Failed:              {metrics.failed_requests}\n"
            report += f"  Success Rate:        {metrics.success_rate():.2f}%\n"
            report += f"  Total Time:          {metrics.total_time:.2f}s\n"
            report += f"  Min Response Time:   {metrics.min_time:.4f}s\n"
            report += f"  Max Response Time:   {metrics.max_time:.4f}s\n"
            report += f"  Avg Response Time:   {metrics.avg_time:.4f}s\n"
            report += f"  P95 Response Time:   {metrics.p95_time:.4f}s\n"
            report += f"  P99 Response Time:   {metrics.p99_time:.4f}s\n"
            report += f"  Cache Hit Rate:      {metrics.cache_hit_rate():.2f}%\n"
            report += f"  DB Queries:          {metrics.db_queries}\n"
            report += f"  DB Query Time:       {metrics.db_query_time:.2f}s\n"
            report += "\n"

        return report


# Global profiler instance
_profiler = PerformanceProfiler()


def get_profiler() -> PerformanceProfiler:
    """Get global profiler instance."""
    return _profiler


def profile_endpoint(endpoint: str, method: str = "GET"):
    """Decorator for profiling endpoint calls."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            with _profiler.profile_endpoint(endpoint, method):
                return await func(*args, **kwargs)

        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            with _profiler.profile_endpoint(endpoint, method):
                return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


import asyncio
