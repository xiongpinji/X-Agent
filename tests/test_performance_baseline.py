"""
Performance Baseline Tests for X-Agent Core
Establishes baseline metrics for response time, memory usage, and throughput
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import pytest


@dataclass
class PerformanceMetrics:
    """Performance measurement results"""
    operation: str
    duration_ms: float
    memory_mb: float
    throughput: float  # ops/sec
    p50_ms: float
    p95_ms: float
    p99_ms: float


class PerformanceBenchmark:
    """Base class for performance benchmarking"""

    def __init__(self, name: str):
        self.name = name
        self.measurements: list[float] = []

    def record(self, duration_ms: float):
        """Record a measurement"""
        self.measurements.append(duration_ms)

    def get_percentile(self, percentile: float) -> float:
        """Calculate percentile from measurements"""
        if not self.measurements:
            return 0.0
        sorted_measurements = sorted(self.measurements)
        index = int(len(sorted_measurements) * percentile / 100)
        return sorted_measurements[min(index, len(sorted_measurements) - 1)]

    def get_stats(self) -> dict[str, float]:
        """Get performance statistics"""
        if not self.measurements:
            return {}

        measurements = self.measurements
        avg_ms = sum(measurements) / len(measurements)
        return {
            "count": len(measurements),
            "min_ms": min(measurements),
            "max_ms": max(measurements),
            "avg_ms": avg_ms,
            "p50_ms": self.get_percentile(50),
            "p95_ms": self.get_percentile(95),
            "p99_ms": self.get_percentile(99),
            "throughput_ops_sec": 1000 / avg_ms if avg_ms > 0 else 0,
        }


@pytest.mark.benchmark
class TestAPIResponseTimeBaseline:
    """Baseline tests for API response times"""

    def test_simple_endpoint_latency(self):
        """Measure baseline latency for simple operations"""
        benchmark = PerformanceBenchmark("simple_endpoint")

        # Simulate 100 simple operations
        for _ in range(100):
            start = time.perf_counter()
            # Simulate minimal work
            _ = sum(range(1000))
            duration = (time.perf_counter() - start) * 1000
            benchmark.record(duration)

        stats = benchmark.get_stats()
        assert stats["p95_ms"] < 1.0, f"P95 latency {stats['p95_ms']}ms exceeds baseline"
        print(f"\nSimple endpoint baseline: {stats}")

    def test_json_serialization_latency(self):
        """Measure JSON serialization performance"""
        import json

        benchmark = PerformanceBenchmark("json_serialization")
        test_data = {
            "id": "test-123",
            "name": "Test Item",
            "metadata": {"key": "value", "nested": {"data": [1, 2, 3]}},
            "items": [{"id": i, "value": f"item_{i}"} for i in range(100)],
        }

        for _ in range(1000):
            start = time.perf_counter()
            json_str = json.dumps(test_data)
            _ = json.loads(json_str)
            duration = (time.perf_counter() - start) * 1000
            benchmark.record(duration)

        stats = benchmark.get_stats()
        assert stats["p95_ms"] < 5.0, f"P95 JSON latency {stats['p95_ms']}ms exceeds target"
        print(f"\nJSON serialization baseline: {stats}")

    def test_list_filtering_latency(self):
        """Measure list filtering performance"""
        benchmark = PerformanceBenchmark("list_filtering")
        test_list = [{"id": i, "status": "active" if i % 2 == 0 else "inactive"} for i in range(1000)]

        for _ in range(100):
            start = time.perf_counter()
            filtered = [item for item in test_list if item["status"] == "active"]
            duration = (time.perf_counter() - start) * 1000
            benchmark.record(duration)

        stats = benchmark.get_stats()
        assert stats["p95_ms"] < 1.0, f"P95 filtering latency {stats['p95_ms']}ms exceeds target"
        print(f"\nList filtering baseline: {stats}")


@pytest.mark.benchmark
class TestMemoryUsageBaseline:
    """Baseline tests for memory usage"""

    def test_list_memory_usage(self):
        """Measure memory usage for list operations"""
        import tracemalloc

        tracemalloc.start()

        # Create large list
        large_list = [{"id": i, "data": f"item_{i}" * 10} for i in range(10000)]

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak / 1024 / 1024
        assert peak_mb < 100, f"Peak memory {peak_mb}MB exceeds baseline"
        print(f"\nList memory usage: {peak_mb:.2f}MB")

    def test_dict_memory_usage(self):
        """Measure memory usage for dict operations"""
        import tracemalloc

        tracemalloc.start()

        # Create large dict
        large_dict = {f"key_{i}": {"value": f"data_{i}" * 5} for i in range(10000)}

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak / 1024 / 1024
        assert peak_mb < 100, f"Peak memory {peak_mb}MB exceeds baseline"
        print(f"\nDict memory usage: {peak_mb:.2f}MB")


@pytest.mark.benchmark
class TestConcurrencyBaseline:
    """Baseline tests for concurrent operations"""

    @pytest.mark.asyncio
    async def test_concurrent_task_execution(self):
        """Measure concurrent task execution performance"""
        benchmark = PerformanceBenchmark("concurrent_tasks")

        async def dummy_task(duration_ms: float):
            await asyncio.sleep(duration_ms / 1000)

        # Run 100 concurrent tasks
        start = time.perf_counter()
        tasks = [dummy_task(10) for _ in range(100)]
        await asyncio.gather(*tasks)
        total_duration = (time.perf_counter() - start) * 1000

        # Should complete in ~10ms (concurrent), not 1000ms (sequential)
        assert total_duration < 100, f"Concurrent execution took {total_duration}ms"
        print(f"\nConcurrent task execution: {total_duration:.2f}ms for 100 tasks")

    @pytest.mark.asyncio
    async def test_async_context_switching(self):
        """Measure async context switching overhead"""
        benchmark = PerformanceBenchmark("context_switching")

        async def minimal_task():
            await asyncio.sleep(0)

        start = time.perf_counter()
        tasks = [minimal_task() for _ in range(1000)]
        await asyncio.gather(*tasks)
        total_duration = (time.perf_counter() - start) * 1000

        avg_per_task = total_duration / 1000
        assert avg_per_task < 1.0, f"Average context switch {avg_per_task}ms exceeds target"
        print(f"\nContext switching overhead: {avg_per_task:.4f}ms per task")


@pytest.mark.benchmark
class TestDatabaseBaseline:
    """Baseline tests for database operations"""

    def test_query_parsing_latency(self):
        """Measure SQL query parsing latency"""
        benchmark = PerformanceBenchmark("query_parsing")

        queries = [
            "SELECT * FROM users WHERE id = $1",
            "SELECT id, name, email FROM users WHERE status = $1 AND created_at > $2",
            "INSERT INTO logs (user_id, action, timestamp) VALUES ($1, $2, $3)",
        ]

        for _ in range(1000):
            for query in queries:
                start = time.perf_counter()
                # Simulate query parsing
                _ = query.split()
                duration = (time.perf_counter() - start) * 1000
                benchmark.record(duration)

        stats = benchmark.get_stats()
        assert stats["p95_ms"] < 0.1, f"P95 query parsing {stats['p95_ms']}ms exceeds target"
        print(f"\nQuery parsing baseline: {stats}")


@pytest.mark.benchmark
class TestCachingBaseline:
    """Baseline tests for caching effectiveness"""

    def test_dict_lookup_performance(self):
        """Measure dict lookup performance"""
        benchmark = PerformanceBenchmark("dict_lookup")

        cache = {f"key_{i}": f"value_{i}" for i in range(10000)}

        for _ in range(10000):
            start = time.perf_counter()
            _ = cache.get("key_5000")
            duration = (time.perf_counter() - start) * 1000
            benchmark.record(duration)

        stats = benchmark.get_stats()
        assert stats["p95_ms"] < 0.01, f"P95 dict lookup {stats['p95_ms']}ms exceeds target"
        print(f"\nDict lookup baseline: {stats}")

    def test_lru_cache_performance(self):
        """Measure LRU cache performance"""
        from functools import lru_cache

        benchmark = PerformanceBenchmark("lru_cache")

        @lru_cache(maxsize=128)
        def expensive_function(x: int) -> int:
            return x * x

        # Warm up cache
        for i in range(128):
            expensive_function(i)

        # Measure cache hits
        for _ in range(10000):
            start = time.perf_counter()
            _ = expensive_function(50)
            duration = (time.perf_counter() - start) * 1000
            benchmark.record(duration)

        stats = benchmark.get_stats()
        assert stats["p95_ms"] < 0.01, f"P95 cache hit {stats['p95_ms']}ms exceeds target"
        print(f"\nLRU cache baseline: {stats}")


def generate_baseline_report(benchmarks: dict[str, PerformanceBenchmark]) -> str:
    """Generate a baseline performance report"""
    report = "# X-Agent Performance Baseline Report\n\n"

    for name, benchmark in benchmarks.items():
        stats = benchmark.get_stats()
        if not stats:
            continue

        report += f"## {name}\n"
        report += f"- Operations: {int(stats['count'])}\n"
        report += f"- Min: {stats['min_ms']:.4f}ms\n"
        report += f"- Max: {stats['max_ms']:.4f}ms\n"
        report += f"- Avg: {stats['avg_ms']:.4f}ms\n"
        report += f"- P50: {stats['p50_ms']:.4f}ms\n"
        report += f"- P95: {stats['p95_ms']:.4f}ms\n"
        report += f"- P99: {stats['p99_ms']:.4f}ms\n"
        report += f"- Throughput: {stats['throughput_ops_sec']:.2f} ops/sec\n\n"

    return report
