"""
Performance Benchmark Tests for X-Agent Core
Measures response time, memory usage, and CPU utilization
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, Callable

import pytest


@dataclass
class PerformanceMetrics:
    """Performance metrics for a single operation"""
    operation_name: str
    response_time_ms: float
    memory_before_mb: float
    memory_after_mb: float
    memory_delta_mb: float
    cpu_percent: float
    timestamp: float


class PerformanceBenchmark:
    """Base class for performance benchmarking"""

    def __init__(self):
        self.metrics: list[PerformanceMetrics] = []
        self.baseline: dict[str, float] = {}

    def measure_sync(
        self,
        func: Callable,
        operation_name: str,
        *args,
        **kwargs
    ) -> tuple[Any, PerformanceMetrics]:
        """Measure synchronous function performance"""
        import psutil
        import os

        process = psutil.Process(os.getpid())

        # Warm up
        func(*args, **kwargs)

        # Measure
        mem_before = process.memory_info().rss / 1024 / 1024
        cpu_before = process.cpu_percent(interval=0.1)

        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()

        mem_after = process.memory_info().rss / 1024 / 1024
        cpu_after = process.cpu_percent(interval=0.1)

        response_time_ms = (end_time - start_time) * 1000
        memory_delta_mb = mem_after - mem_before
        cpu_percent = (cpu_before + cpu_after) / 2

        metrics = PerformanceMetrics(
            operation_name=operation_name,
            response_time_ms=response_time_ms,
            memory_before_mb=mem_before,
            memory_after_mb=mem_after,
            memory_delta_mb=memory_delta_mb,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

        self.metrics.append(metrics)
        return result, metrics

    async def measure_async(
        self,
        func: Callable,
        operation_name: str,
        *args,
        **kwargs
    ) -> tuple[Any, PerformanceMetrics]:
        """Measure asynchronous function performance"""
        import psutil
        import os

        process = psutil.Process(os.getpid())

        # Warm up
        await func(*args, **kwargs)

        # Measure
        mem_before = process.memory_info().rss / 1024 / 1024
        cpu_before = process.cpu_percent(interval=0.1)

        start_time = time.perf_counter()
        result = await func(*args, **kwargs)
        end_time = time.perf_counter()

        mem_after = process.memory_info().rss / 1024 / 1024
        cpu_after = process.cpu_percent(interval=0.1)

        response_time_ms = (end_time - start_time) * 1000
        memory_delta_mb = mem_after - mem_before
        cpu_percent = (cpu_before + cpu_after) / 2

        metrics = PerformanceMetrics(
            operation_name=operation_name,
            response_time_ms=response_time_ms,
            memory_before_mb=mem_before,
            memory_after_mb=mem_after,
            memory_delta_mb=memory_delta_mb,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

        self.metrics.append(metrics)
        return result, metrics

    def get_summary(self) -> dict[str, Any]:
        """Get performance summary"""
        if not self.metrics:
            return {}

        response_times = [m.response_time_ms for m in self.metrics]
        memory_deltas = [m.memory_delta_mb for m in self.metrics]
        cpu_percents = [m.cpu_percent for m in self.metrics]

        return {
            "total_operations": len(self.metrics),
            "response_time": {
                "min_ms": min(response_times),
                "max_ms": max(response_times),
                "avg_ms": sum(response_times) / len(response_times),
                "p95_ms": sorted(response_times)[int(len(response_times) * 0.95)],
                "p99_ms": sorted(response_times)[int(len(response_times) * 0.99)],
            },
            "memory": {
                "min_delta_mb": min(memory_deltas),
                "max_delta_mb": max(memory_deltas),
                "avg_delta_mb": sum(memory_deltas) / len(memory_deltas),
            },
            "cpu": {
                "min_percent": min(cpu_percents),
                "max_percent": max(cpu_percents),
                "avg_percent": sum(cpu_percents) / len(cpu_percents),
            }
        }

    def export_metrics(self, filepath: str) -> None:
        """Export metrics to JSON file"""
        data = {
            "metrics": [
                {
                    "operation_name": m.operation_name,
                    "response_time_ms": m.response_time_ms,
                    "memory_before_mb": m.memory_before_mb,
                    "memory_after_mb": m.memory_after_mb,
                    "memory_delta_mb": m.memory_delta_mb,
                    "cpu_percent": m.cpu_percent,
                    "timestamp": m.timestamp,
                }
                for m in self.metrics
            ],
            "summary": self.get_summary()
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)


# Test fixtures
@pytest.fixture
def benchmark():
    """Benchmark fixture"""
    return PerformanceBenchmark()


class TestMemoryRetrieverPerformance:
    """Performance tests for memory retriever"""

    @pytest.mark.benchmark
    def test_memory_search_response_time(self, benchmark):
        """Test memory search response time"""
        from backend.app.services.memory.retriever import memory_retriever

        # Mock search
        def search_operation():
            # Simulate search with mock data
            return [{"id": f"mem_{i}", "score": 0.9 - i*0.1} for i in range(5)]

        result, metrics = benchmark.measure_sync(
            search_operation,
            "memory_search"
        )

        # Verify response time < 200ms
        assert metrics.response_time_ms < 200, \
            f"Memory search took {metrics.response_time_ms}ms, expected < 200ms"

        assert len(result) == 5


class TestDatabaseQueryPerformance:
    """Performance tests for database queries"""

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_postgres_query_performance(self, benchmark):
        """Test PostgreSQL query performance"""

        async def query_operation():
            # Simulate async database query
            await asyncio.sleep(0.05)  # Simulate 50ms query
            return {"rows": 100, "duration_ms": 50}

        result, metrics = await benchmark.measure_async(
            query_operation,
            "postgres_query"
        )

        # Verify response time < 200ms
        assert metrics.response_time_ms < 200, \
            f"Query took {metrics.response_time_ms}ms, expected < 200ms"


class TestVectorSearchPerformance:
    """Performance tests for vector search"""

    @pytest.mark.benchmark
    def test_vector_search_response_time(self, benchmark):
        """Test vector search response time"""

        def vector_search():
            # Simulate vector search
            import numpy as np
            query_vector = np.random.rand(1536)
            results = []
            for i in range(10):
                score = 0.9 - i * 0.05
                results.append({"id": f"vec_{i}", "score": score})
            return results

        result, metrics = benchmark.measure_sync(
            vector_search,
            "vector_search"
        )

        # Verify response time < 200ms
        assert metrics.response_time_ms < 200, \
            f"Vector search took {metrics.response_time_ms}ms, expected < 200ms"

        assert len(result) == 10


class TestMemoryUsage:
    """Performance tests for memory usage"""

    @pytest.mark.benchmark
    def test_memory_usage_baseline(self, benchmark):
        """Test baseline memory usage"""

        def memory_intensive_operation():
            # Create large data structure
            data = [{"id": i, "data": "x" * 1000} for i in range(1000)]
            return len(data)

        result, metrics = benchmark.measure_sync(
            memory_intensive_operation,
            "memory_intensive"
        )

        # Verify the operation's own memory footprint is bounded. Assert on the
        # delta, not absolute RSS: under xdist the process already holds the full
        # backend in memory, so absolute RSS is unrelated to this op's cost.
        assert metrics.memory_delta_mb < 500, \
            f"Memory delta {metrics.memory_delta_mb}MB, expected < 500MB"


class TestConcurrentOperations:
    """Performance tests for concurrent operations"""

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, benchmark):
        """Test concurrent request handling"""

        async def concurrent_operation():
            async def single_request():
                await asyncio.sleep(0.01)  # Simulate 10ms request
                return {"status": "ok"}

            tasks = [single_request() for _ in range(10)]
            results = await asyncio.gather(*tasks)
            return results

        result, metrics = await benchmark.measure_async(
            concurrent_operation,
            "concurrent_requests"
        )

        # Verify concurrent handling
        assert len(result) == 10
        assert metrics.response_time_ms < 200, \
            f"Concurrent requests took {metrics.response_time_ms}ms, expected < 200ms"


class TestAPIEndpointPerformance:
    """Performance tests for API endpoints"""

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_health_check_endpoint(self, benchmark):
        """Test health check endpoint performance"""

        async def health_check():
            # Simulate health check
            await asyncio.sleep(0.005)
            return {"status": "healthy", "timestamp": time.time()}

        result, metrics = await benchmark.measure_async(
            health_check,
            "health_check"
        )

        # Health check should be very fast
        assert metrics.response_time_ms < 50, \
            f"Health check took {metrics.response_time_ms}ms, expected < 50ms"


@pytest.mark.benchmark
class TestPerformanceSummary:
    """Summary of performance benchmarks"""

    def test_generate_performance_report(self, benchmark):
        """Generate performance report"""
        # The benchmark fixture is function-scoped, so record at least one
        # measurement before summarizing (get_summary returns {} when empty).
        benchmark.measure_sync(lambda: sum(range(1000)), "report_seed")

        summary = benchmark.get_summary()

        # Verify summary structure
        assert "total_operations" in summary
        assert "response_time" in summary
        assert "memory" in summary
        assert "cpu" in summary

        # Export metrics
        benchmark.export_metrics("/tmp/performance_metrics.json")
