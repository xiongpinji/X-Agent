"""Performance benchmarking for X-Agent.

Provides benchmarking utilities for:
- API response time measurement
- Database query performance
- Concurrent request handling
- Memory usage profiling
"""

from __future__ import annotations

import asyncio
import time
import logging
import statistics
from typing import Any, Callable, Coroutine, TypeVar
from dataclasses import dataclass, field
from datetime import datetime, UTC
from collections import defaultdict

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class BenchmarkResult:
    """Result of a benchmark run."""

    name: str
    iterations: int
    total_time: float
    min_time: float
    max_time: float
    mean_time: float
    median_time: float
    stddev_time: float
    throughput: float  # operations per second
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __str__(self) -> str:
        """Format benchmark result as string."""
        return (
            f"{self.name}:\n"
            f"  Iterations: {self.iterations}\n"
            f"  Total Time: {self.total_time:.3f}s\n"
            f"  Min: {self.min_time*1000:.2f}ms\n"
            f"  Max: {self.max_time*1000:.2f}ms\n"
            f"  Mean: {self.mean_time*1000:.2f}ms\n"
            f"  Median: {self.median_time*1000:.2f}ms\n"
            f"  StdDev: {self.stddev_time*1000:.2f}ms\n"
            f"  Throughput: {self.throughput:.2f} ops/sec"
        )


class Benchmark:
    """Synchronous benchmark runner."""

    @staticmethod
    def run(
        func: Callable[[], T],
        iterations: int = 100,
        name: str | None = None,
    ) -> BenchmarkResult:
        """Run synchronous benchmark.

        Args:
            func: Function to benchmark
            iterations: Number of iterations
            name: Benchmark name

        Returns:
            Benchmark result
        """
        name = name or func.__name__
        times = []

        start_total = time.perf_counter()

        for _ in range(iterations):
            start = time.perf_counter()
            func()
            end = time.perf_counter()
            times.append(end - start)

        end_total = time.perf_counter()
        total_time = end_total - start_total

        return BenchmarkResult(
            name=name,
            iterations=iterations,
            total_time=total_time,
            min_time=min(times),
            max_time=max(times),
            mean_time=statistics.mean(times),
            median_time=statistics.median(times),
            stddev_time=statistics.stdev(times) if len(times) > 1 else 0,
            throughput=iterations / total_time,
        )


class AsyncBenchmark:
    """Asynchronous benchmark runner."""

    @staticmethod
    async def run(
        func: Callable[[], Coroutine[Any, Any, T]],
        iterations: int = 100,
        name: str | None = None,
    ) -> BenchmarkResult:
        """Run asynchronous benchmark.

        Args:
            func: Async function to benchmark
            iterations: Number of iterations
            name: Benchmark name

        Returns:
            Benchmark result
        """
        name = name or func.__name__
        times = []

        start_total = time.perf_counter()

        for _ in range(iterations):
            start = time.perf_counter()
            await func()
            end = time.perf_counter()
            times.append(end - start)

        end_total = time.perf_counter()
        total_time = end_total - start_total

        return BenchmarkResult(
            name=name,
            iterations=iterations,
            total_time=total_time,
            min_time=min(times),
            max_time=max(times),
            mean_time=statistics.mean(times),
            median_time=statistics.median(times),
            stddev_time=statistics.stdev(times) if len(times) > 1 else 0,
            throughput=iterations / total_time,
        )

    @staticmethod
    async def run_concurrent(
        func: Callable[[], Coroutine[Any, Any, T]],
        iterations: int = 100,
        concurrency: int = 10,
        name: str | None = None,
    ) -> BenchmarkResult:
        """Run concurrent asynchronous benchmark.

        Args:
            func: Async function to benchmark
            iterations: Total number of iterations
            concurrency: Number of concurrent tasks
            name: Benchmark name

        Returns:
            Benchmark result
        """
        name = name or f"{func.__name__} (concurrent={concurrency})"
        times = []

        start_total = time.perf_counter()

        # Create tasks
        tasks = [func() for _ in range(iterations)]

        # Run with concurrency limit
        semaphore = asyncio.Semaphore(concurrency)

        async def bounded_task():
            async with semaphore:
                start = time.perf_counter()
                await func()
                end = time.perf_counter()
                times.append(end - start)

        await asyncio.gather(*[bounded_task() for _ in range(iterations)])

        end_total = time.perf_counter()
        total_time = end_total - start_total

        return BenchmarkResult(
            name=name,
            iterations=iterations,
            total_time=total_time,
            min_time=min(times),
            max_time=max(times),
            mean_time=statistics.mean(times),
            median_time=statistics.median(times),
            stddev_time=statistics.stdev(times) if len(times) > 1 else 0,
            throughput=iterations / total_time,
        )


class LoadTester:
    """Load testing utility."""

    def __init__(self):
        """Initialize load tester."""
        self.results: dict[str, list[BenchmarkResult]] = defaultdict(list)

    async def run_load_test(
        self,
        func: Callable[[], Coroutine[Any, Any, T]],
        duration: float = 60.0,
        concurrency: int = 10,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Run load test for specified duration.

        Args:
            func: Async function to test
            duration: Test duration in seconds
            concurrency: Number of concurrent tasks
            name: Test name

        Returns:
            Load test results
        """
        name = name or func.__name__
        times = []
        errors = 0
        start_time = time.perf_counter()

        semaphore = asyncio.Semaphore(concurrency)

        async def bounded_task():
            nonlocal errors
            async with semaphore:
                try:
                    start = time.perf_counter()
                    await func()
                    end = time.perf_counter()
                    times.append(end - start)
                except Exception as e:
                    errors += 1
                    logger.error(f"Load test error: {e}")

        # Run tasks until duration exceeded
        tasks = []
        while time.perf_counter() - start_time < duration:
            task = asyncio.create_task(bounded_task())
            tasks.append(task)

            # Limit pending tasks
            if len(tasks) >= concurrency * 2:
                await asyncio.gather(*tasks[:concurrency])
                tasks = tasks[concurrency:]

        # Wait for remaining tasks
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.perf_counter()
        total_time = end_time - start_time

        results = {
            "name": name,
            "duration": total_time,
            "concurrency": concurrency,
            "total_requests": len(times) + errors,
            "successful_requests": len(times),
            "failed_requests": errors,
            "error_rate": errors / (len(times) + errors) if (len(times) + errors) > 0 else 0,
            "throughput": (len(times) + errors) / total_time,
            "min_time": min(times) if times else 0,
            "max_time": max(times) if times else 0,
            "mean_time": statistics.mean(times) if times else 0,
            "median_time": statistics.median(times) if times else 0,
            "p95_time": self._percentile(times, 0.95) if times else 0,
            "p99_time": self._percentile(times, 0.99) if times else 0,
        }

        self.results[name].append(results)
        return results

    @staticmethod
    def _percentile(data: list[float], percentile: float) -> float:
        """Calculate percentile.

        Args:
            data: List of values
            percentile: Percentile (0-1)

        Returns:
            Percentile value
        """
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile)
        return sorted_data[min(index, len(sorted_data) - 1)]


class PerformanceProfiler:
    """Profiles performance metrics."""

    def __init__(self):
        """Initialize profiler."""
        self.metrics: dict[str, list[float]] = defaultdict(list)

    def record_metric(self, name: str, value: float) -> None:
        """Record performance metric.

        Args:
            name: Metric name
            value: Metric value
        """
        self.metrics[name].append(value)

    def get_stats(self, name: str) -> dict[str, float] | None:
        """Get statistics for metric.

        Args:
            name: Metric name

        Returns:
            Statistics dictionary or None
        """
        if name not in self.metrics or not self.metrics[name]:
            return None

        values = self.metrics[name]
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "stddev": statistics.stdev(values) if len(values) > 1 else 0,
        }

    def get_all_stats(self) -> dict[str, dict[str, float]]:
        """Get statistics for all metrics.

        Returns:
            Dictionary of all statistics
        """
        return {name: self.get_stats(name) for name in self.metrics}

    def clear(self) -> None:
        """Clear all metrics."""
        self.metrics.clear()


class PerformanceComparison:
    """Compares performance between implementations."""

    @staticmethod
    async def compare(
        implementations: dict[str, Callable[[], Coroutine[Any, Any, T]]],
        iterations: int = 100,
    ) -> dict[str, BenchmarkResult]:
        """Compare performance of multiple implementations.

        Args:
            implementations: Dictionary of name -> async function
            iterations: Number of iterations per implementation

        Returns:
            Dictionary of results
        """
        results = {}

        for name, func in implementations.items():
            result = await AsyncBenchmark.run(func, iterations=iterations, name=name)
            results[name] = result
            logger.info(f"Benchmark {name}: {result.mean_time*1000:.2f}ms")

        return results

    @staticmethod
    def print_comparison(results: dict[str, BenchmarkResult]) -> None:
        """Print comparison results.

        Args:
            results: Benchmark results
        """
        print("\n" + "="*60)
        print("PERFORMANCE COMPARISON")
        print("="*60)

        for name, result in results.items():
            print(f"\n{result}")

        # Find fastest
        fastest = min(results.items(), key=lambda x: x[1].mean_time)
        print(f"\nFastest: {fastest[0]} ({fastest[1].mean_time*1000:.2f}ms)")
