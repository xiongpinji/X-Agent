"""
Performance Benchmarking and Optimization Report for X-Agent.

This module provides comprehensive performance analysis and optimization
recommendations based on actual system metrics.
"""

from __future__ import annotations

import asyncio
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any, Callable, Optional
import json

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Result of a performance benchmark."""

    name: str
    duration_ms: float
    iterations: int
    avg_time_ms: float = field(init=False)
    min_time_ms: float = field(init=False)
    max_time_ms: float = field(init=False)
    throughput: float = field(init=False)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.avg_time_ms = self.duration_ms / self.iterations
        self.throughput = (self.iterations / self.duration_ms) * 1000

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "duration_ms": self.duration_ms,
            "iterations": self.iterations,
            "avg_time_ms": round(self.avg_time_ms, 2),
            "throughput": round(self.throughput, 2),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics."""

    query_cache_hit_rate: float = 0.0
    avg_query_time_ms: float = 0.0
    p95_query_time_ms: float = 0.0
    p99_query_time_ms: float = 0.0
    connection_pool_utilization: float = 0.0
    memory_usage_mb: float = 0.0
    vector_search_time_ms: float = 0.0
    n_plus_one_queries_detected: int = 0
    slow_queries: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_cache_hit_rate": round(self.query_cache_hit_rate, 2),
            "avg_query_time_ms": round(self.avg_query_time_ms, 2),
            "p95_query_time_ms": round(self.p95_query_time_ms, 2),
            "p99_query_time_ms": round(self.p99_query_time_ms, 2),
            "connection_pool_utilization": round(self.connection_pool_utilization, 2),
            "memory_usage_mb": round(self.memory_usage_mb, 2),
            "vector_search_time_ms": round(self.vector_search_time_ms, 2),
            "n_plus_one_queries_detected": self.n_plus_one_queries_detected,
            "slow_queries": self.slow_queries,
            "timestamp": self.timestamp.isoformat(),
        }


class PerformanceBenchmark:
    """Benchmarking suite for X-Agent performance."""

    def __init__(self) -> None:
        self.results: list[BenchmarkResult] = []
        self.metrics: list[PerformanceMetrics] = []

    async def benchmark_async_function(
        self,
        name: str,
        func: Callable,
        iterations: int = 100,
        *args: Any,
        **kwargs: Any,
    ) -> BenchmarkResult:
        """Benchmark an async function."""
        start_time = time.time()

        for _ in range(iterations):
            await func(*args, **kwargs)

        duration = (time.time() - start_time) * 1000  # Convert to ms
        result = BenchmarkResult(
            name=name,
            duration_ms=duration,
            iterations=iterations,
        )
        self.results.append(result)
        logger.info(f"Benchmark {name}: {result.avg_time_ms:.2f}ms avg")
        return result

    async def benchmark_query_performance(
        self,
        query_func: Callable,
        iterations: int = 100,
    ) -> dict[str, Any]:
        """Benchmark query performance with caching."""
        times = []

        # Warm up
        await query_func()

        # Measure with cache
        for _ in range(iterations):
            start = time.time()
            await query_func()
            times.append((time.time() - start) * 1000)

        return {
            "avg_ms": sum(times) / len(times),
            "min_ms": min(times),
            "max_ms": max(times),
            "p95_ms": sorted(times)[int(len(times) * 0.95)],
            "p99_ms": sorted(times)[int(len(times) * 0.99)],
        }

    def generate_report(self) -> str:
        """Generate performance report."""
        report = []
        report.append("=" * 80)
        report.append("X-AGENT PERFORMANCE OPTIMIZATION REPORT")
        report.append("=" * 80)
        report.append("")

        # Benchmark results
        if self.results:
            report.append("BENCHMARK RESULTS")
            report.append("-" * 80)
            for result in self.results:
                report.append(f"{result.name}:")
                report.append(f"  Average: {result.avg_time_ms:.2f}ms")
                report.append(f"  Throughput: {result.throughput:.2f} ops/sec")
                report.append(f"  Total Duration: {result.duration_ms:.2f}ms")
            report.append("")

        # Performance metrics
        if self.metrics:
            report.append("PERFORMANCE METRICS")
            report.append("-" * 80)
            latest = self.metrics[-1]
            report.append(f"Query Cache Hit Rate: {latest.query_cache_hit_rate:.1f}%")
            report.append(f"Average Query Time: {latest.avg_query_time_ms:.2f}ms")
            report.append(f"P95 Query Time: {latest.p95_query_time_ms:.2f}ms")
            report.append(f"P99 Query Time: {latest.p99_query_time_ms:.2f}ms")
            report.append(
                f"Connection Pool Utilization: {latest.connection_pool_utilization:.1f}%"
            )
            report.append(f"Memory Usage: {latest.memory_usage_mb:.2f}MB")
            report.append(f"Vector Search Time: {latest.vector_search_time_ms:.2f}ms")
            report.append(f"N+1 Queries Detected: {latest.n_plus_one_queries_detected}")
            report.append(f"Slow Queries: {latest.slow_queries}")
            report.append("")

        # Optimization recommendations
        report.append("OPTIMIZATION RECOMMENDATIONS")
        report.append("-" * 80)
        if self.metrics:
            latest = self.metrics[-1]
            if latest.query_cache_hit_rate < 50:
                report.append("- Increase cache TTL or cache more queries")
            if latest.avg_query_time_ms > 100:
                report.append("- Add database indexes for slow queries")
            if latest.connection_pool_utilization > 80:
                report.append("- Increase connection pool size")
            if latest.n_plus_one_queries_detected > 0:
                report.append("- Implement batch queries or eager loading")
            if latest.slow_queries > 10:
                report.append("- Profile and optimize slow queries")

        report.append("")
        report.append("=" * 80)

        return "\n".join(report)

    def to_json(self) -> str:
        """Export results as JSON."""
        return json.dumps(
            {
                "results": [r.to_dict() for r in self.results],
                "metrics": [m.to_dict() for m in self.metrics],
            },
            indent=2,
        )


# Global benchmark instance
_benchmark: Optional[PerformanceBenchmark] = None


def get_benchmark() -> PerformanceBenchmark:
    """Get global benchmark instance."""
    global _benchmark
    if _benchmark is None:
        _benchmark = PerformanceBenchmark()
    return _benchmark
