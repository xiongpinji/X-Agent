"""
Performance benchmarking for X-Agent optimization validation.

Measures:
- Memory search performance
- Run list performance
- API response times
- Cache effectiveness
- Database query performance
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""

    operation: str
    iterations: int
    min_ms: float
    max_ms: float
    avg_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    total_ms: float
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "operation": self.operation,
            "iterations": self.iterations,
            "min_ms": round(self.min_ms, 2),
            "max_ms": round(self.max_ms, 2),
            "avg_ms": round(self.avg_ms, 2),
            "p50_ms": round(self.p50_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "p99_ms": round(self.p99_ms, 2),
            "total_ms": round(self.total_ms, 2),
            "timestamp": self.timestamp,
        }


class PerformanceBenchmark:
    """Performance benchmarking utilities."""

    @staticmethod
    async def measure_endpoint(
        endpoint_func: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Measure endpoint performance.

        Args:
            endpoint_func: Async endpoint function
            *args: Positional arguments for endpoint
            **kwargs: Keyword arguments for endpoint

        Returns:
            Dictionary with performance metrics
        """
        start = time.perf_counter()
        result = await endpoint_func(*args, **kwargs)
        duration = time.perf_counter() - start

        return {
            "duration_ms": duration * 1000,
            "result_size": len(str(result)) if result else 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    async def benchmark_operation(
        operation_func: Callable[..., Coroutine[Any, Any, Any]],
        iterations: int = 100,
        operation_name: str = "operation",
        *args: Any,
        **kwargs: Any,
    ) -> BenchmarkResult:
        """Benchmark an operation multiple times.

        Args:
            operation_func: Async function to benchmark
            iterations: Number of iterations to run
            operation_name: Name of operation for reporting
            *args: Positional arguments for operation
            **kwargs: Keyword arguments for operation

        Returns:
            BenchmarkResult with statistics
        """
        durations = []
        total_start = time.perf_counter()

        for _ in range(iterations):
            start = time.perf_counter()
            try:
                await operation_func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Benchmark iteration failed: {e}")
            duration = time.perf_counter() - start
            durations.append(duration * 1000)

        total_duration = time.perf_counter() - total_start

        # Calculate statistics
        durations.sort()
        min_ms = min(durations)
        max_ms = max(durations)
        avg_ms = sum(durations) / len(durations)
        p50_ms = durations[int(len(durations) * 0.50)]
        p95_ms = durations[int(len(durations) * 0.95)]
        p99_ms = durations[int(len(durations) * 0.99)]

        return BenchmarkResult(
            operation=operation_name,
            iterations=iterations,
            min_ms=min_ms,
            max_ms=max_ms,
            avg_ms=avg_ms,
            p50_ms=p50_ms,
            p95_ms=p95_ms,
            p99_ms=p99_ms,
            total_ms=total_duration * 1000,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    async def benchmark_memory_search(
        memory_system: Any,
        context: Any,
        query: str = "test query",
        iterations: int = 100,
    ) -> BenchmarkResult:
        """Benchmark memory search performance.

        Args:
            memory_system: Memory system instance
            context: Run context
            query: Search query
            iterations: Number of iterations

        Returns:
            BenchmarkResult with search performance
        """
        async def search_op():
            await memory_system.search(
                context,
                query=query,
                top_k=10,
            )

        return await PerformanceBenchmark.benchmark_operation(
            search_op,
            iterations=iterations,
            operation_name="memory_search",
        )

    @staticmethod
    async def benchmark_run_list(
        run_store: Any,
        iterations: int = 100,
        limit: int = 20,
    ) -> BenchmarkResult:
        """Benchmark run list performance.

        Args:
            run_store: Run store instance
            iterations: Number of iterations
            limit: Number of runs to fetch

        Returns:
            BenchmarkResult with list performance
        """
        async def list_op():
            await run_store.list(limit=limit)

        return await PerformanceBenchmark.benchmark_operation(
            list_op,
            iterations=iterations,
            operation_name="run_list",
        )

    @staticmethod
    async def benchmark_cache_operations(
        cache_backend: Any,
        iterations: int = 1000,
    ) -> dict[str, BenchmarkResult]:
        """Benchmark cache operations.

        Args:
            cache_backend: Cache backend instance
            iterations: Number of iterations per operation

        Returns:
            Dictionary with results for each operation
        """
        results = {}

        # Benchmark cache set
        async def cache_set():
            await cache_backend.set(f"key_{time.time()}", "value", ttl=3600)

        results["cache_set"] = await PerformanceBenchmark.benchmark_operation(
            cache_set,
            iterations=iterations,
            operation_name="cache_set",
        )

        # Benchmark cache get
        test_key = "benchmark_test_key"
        await cache_backend.set(test_key, "test_value", ttl=3600)

        async def cache_get():
            await cache_backend.get(test_key)

        results["cache_get"] = await PerformanceBenchmark.benchmark_operation(
            cache_get,
            iterations=iterations,
            operation_name="cache_get",
        )

        return results

    @staticmethod
    async def benchmark_database_queries(
        pool: Any,
        iterations: int = 100,
    ) -> dict[str, BenchmarkResult]:
        """Benchmark database query performance.

        Args:
            pool: AsyncPG connection pool
            iterations: Number of iterations per query

        Returns:
            Dictionary with results for each query type
        """
        results = {}

        # Benchmark simple select
        async def simple_select():
            await pool.fetchval("SELECT 1")

        results["simple_select"] = await PerformanceBenchmark.benchmark_operation(
            simple_select,
            iterations=iterations,
            operation_name="simple_select",
        )

        # Benchmark table scan (if memories table exists)
        async def table_scan():
            try:
                await pool.fetch("SELECT id FROM memories LIMIT 100")
            except Exception:
                pass

        results["table_scan"] = await PerformanceBenchmark.benchmark_operation(
            table_scan,
            iterations=min(iterations, 10),  # Fewer iterations for heavier query
            operation_name="table_scan",
        )

        return results


class PerformanceComparison:
    """Compares performance before and after optimization."""

    def __init__(self) -> None:
        """Initialize performance comparison."""
        self.baseline: dict[str, BenchmarkResult] = {}
        self.optimized: dict[str, BenchmarkResult] = {}

    def add_baseline(self, name: str, result: BenchmarkResult) -> None:
        """Add baseline measurement.

        Args:
            name: Name of measurement
            result: BenchmarkResult
        """
        self.baseline[name] = result

    def add_optimized(self, name: str, result: BenchmarkResult) -> None:
        """Add optimized measurement.

        Args:
            name: Name of measurement
            result: BenchmarkResult
        """
        self.optimized[name] = result

    def get_improvement(self, name: str) -> dict[str, Any]:
        """Get improvement for a specific measurement.

        Args:
            name: Name of measurement

        Returns:
            Dictionary with improvement metrics
        """
        if name not in self.baseline or name not in self.optimized:
            return {}

        baseline = self.baseline[name]
        optimized = self.optimized[name]

        improvement_percent = (
            (baseline.avg_ms - optimized.avg_ms) / baseline.avg_ms * 100
        )

        return {
            "measurement": name,
            "baseline_avg_ms": round(baseline.avg_ms, 2),
            "optimized_avg_ms": round(optimized.avg_ms, 2),
            "improvement_percent": round(improvement_percent, 2),
            "improvement_ms": round(baseline.avg_ms - optimized.avg_ms, 2),
            "baseline_p95_ms": round(baseline.p95_ms, 2),
            "optimized_p95_ms": round(optimized.p95_ms, 2),
            "p95_improvement_percent": round(
                (baseline.p95_ms - optimized.p95_ms) / baseline.p95_ms * 100, 2
            ),
        }

    def get_all_improvements(self) -> dict[str, Any]:
        """Get improvements for all measurements.

        Returns:
            Dictionary with all improvements
        """
        improvements = {}
        for name in self.baseline.keys():
            if name in self.optimized:
                improvements[name] = self.get_improvement(name)

        return improvements

    def get_summary(self) -> dict[str, Any]:
        """Get summary of all improvements.

        Returns:
            Dictionary with summary statistics
        """
        improvements = self.get_all_improvements()

        if not improvements:
            return {}

        avg_improvements = [
            imp["improvement_percent"] for imp in improvements.values()
        ]
        overall_improvement = sum(avg_improvements) / len(avg_improvements)

        return {
            "total_measurements": len(improvements),
            "overall_improvement_percent": round(overall_improvement, 2),
            "measurements": improvements,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class PerformanceReporter:
    """Generates performance reports."""

    @staticmethod
    def format_result(result: BenchmarkResult) -> str:
        """Format benchmark result as string.

        Args:
            result: BenchmarkResult

        Returns:
            Formatted string
        """
        return (
            f"{result.operation}:\n"
            f"  Iterations: {result.iterations}\n"
            f"  Min: {result.min_ms:.2f}ms\n"
            f"  Max: {result.max_ms:.2f}ms\n"
            f"  Avg: {result.avg_ms:.2f}ms\n"
            f"  P50: {result.p50_ms:.2f}ms\n"
            f"  P95: {result.p95_ms:.2f}ms\n"
            f"  P99: {result.p99_ms:.2f}ms\n"
            f"  Total: {result.total_ms:.2f}ms"
        )

    @staticmethod
    def format_comparison(comparison: PerformanceComparison) -> str:
        """Format performance comparison as string.

        Args:
            comparison: PerformanceComparison

        Returns:
            Formatted string
        """
        summary = comparison.get_summary()
        if not summary:
            return "No comparison data available"

        lines = [
            "Performance Optimization Results",
            "=" * 50,
            f"Overall Improvement: {summary['overall_improvement_percent']:.2f}%",
            f"Measurements: {summary['total_measurements']}",
            "",
        ]

        for name, imp in summary["measurements"].items():
            lines.append(
                f"{name}: {imp['improvement_percent']:.2f}% "
                f"({imp['baseline_avg_ms']:.2f}ms -> {imp['optimized_avg_ms']:.2f}ms)"
            )

        return "\n".join(lines)
