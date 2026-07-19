"""Performance benchmark tests for X-Agent.

Tests API response time, database queries, LLM calls, and throughput.
"""

from __future__ import annotations

import asyncio
import pytest
from typing import Any


class PerformanceBenchmarks:
    """Performance benchmark test suite."""

    @pytest.mark.benchmark
    async def test_api_response_time(self, client: Any, benchmark: Any) -> None:
        """Test API response time - Target: <200ms."""
        async def run():
            response = await client.get("/api/v1/runs?limit=20")
            return response

        result = benchmark(run)
        assert result.status_code == 200

    @pytest.mark.benchmark
    async def test_database_query_time(self, db_pool: Any, benchmark: Any) -> None:
        """Test database query time - Target: <50ms."""
        async def run():
            async with db_pool.acquire() as conn:
                return await conn.fetch(
                    "SELECT * FROM memories WHERE tenant_id = $1 LIMIT 20",
                    "test-tenant"
                )

        result = benchmark(run)
        assert isinstance(result, list)

    @pytest.mark.benchmark
    async def test_memory_retrieval_time(
        self,
        memory_system: Any,
        benchmark: Any
    ) -> None:
        """Test memory retrieval time - Target: <100ms."""
        async def run():
            return await memory_system.search(
                query="test query",
                top_k=5
            )

        result = benchmark(run)
        assert isinstance(result, list)

    @pytest.mark.benchmark
    async def test_cache_hit_performance(
        self,
        cache_manager: Any,
        benchmark: Any
    ) -> None:
        """Test cache hit performance - Target: <5ms."""
        # Warm up cache
        await cache_manager.set("test:key", {"data": "value"})

        async def run():
            return await cache_manager.get("test:key")

        result = benchmark(run)
        assert result is not None

    @pytest.mark.benchmark
    async def test_concurrent_requests(
        self,
        client: Any,
        benchmark: Any
    ) -> None:
        """Test concurrent request handling - Target: >100 RPS."""
        async def run():
            tasks = [
                client.get("/api/v1/runs?limit=20")
                for _ in range(100)
            ]
            return await asyncio.gather(*tasks)

        result = benchmark(run)
        assert len(result) == 100

    @pytest.mark.benchmark
    async def test_batch_operations(
        self,
        async_optimizer: Any,
        benchmark: Any
    ) -> None:
        """Test batch operation performance."""
        async def dummy_operation(item):
            await asyncio.sleep(0.001)
            return item * 2

        items = list(range(100))

        async def run():
            return await async_optimizer.batch_async_operations(
                items,
                dummy_operation,
                batch_size=10
            )

        result = benchmark(run)
        assert len(result) == 100

    @pytest.mark.benchmark
    async def test_serialization_performance(
        self,
        benchmark: Any
    ) -> None:
        """Test JSON serialization performance."""
        import json

        data = {
            "id": "test-id",
            "name": "test",
            "data": [{"key": "value"} for _ in range(100)]
        }

        def run():
            return json.dumps(data)

        result = benchmark(run)
        assert isinstance(result, str)

    @pytest.mark.benchmark
    async def test_list_filtering_performance(
        self,
        benchmark: Any
    ) -> None:
        """Test list filtering performance."""
        items = [
            {"id": i, "status": "active" if i % 2 == 0 else "inactive"}
            for i in range(1000)
        ]

        def run():
            return [item for item in items if item["status"] == "active"]

        result = benchmark(run)
        assert len(result) == 500


class PerformanceLoadTests:
    """Load testing for performance validation."""

    @pytest.mark.load
    async def test_sustained_load(
        self,
        client: Any,
        duration_seconds: int = 60
    ) -> None:
        """Test sustained load performance."""
        import time

        start_time = time.time()
        request_count = 0
        error_count = 0

        while time.time() - start_time < duration_seconds:
            try:
                response = await client.get("/api/v1/runs?limit=20")
                if response.status_code == 200:
                    request_count += 1
                else:
                    error_count += 1
            except Exception:
                error_count += 1

        elapsed = time.time() - start_time
        rps = request_count / elapsed
        error_rate = error_count / (request_count + error_count) if (request_count + error_count) > 0 else 0

        assert rps > 50, f"Throughput {rps} RPS below target 50 RPS"
        assert error_rate < 0.01, f"Error rate {error_rate} above target 1%"

    @pytest.mark.load
    async def test_spike_load(
        self,
        client: Any,
        spike_size: int = 1000
    ) -> None:
        """Test spike load handling."""
        tasks = [
            client.get("/api/v1/runs?limit=20")
            for _ in range(spike_size)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        successful = sum(1 for r in results if not isinstance(r, Exception))
        success_rate = successful / len(results)

        assert success_rate > 0.95, f"Success rate {success_rate} below target 95%"


class PerformanceRegressionTests:
    """Regression tests to prevent performance degradation."""

    @pytest.mark.regression
    async def test_api_response_time_regression(
        self,
        client: Any,
        baseline_ms: float = 200
    ) -> None:
        """Ensure API response time doesn't regress."""
        import time

        start = time.time()
        response = await client.get("/api/v1/runs?limit=20")
        duration_ms = (time.time() - start) * 1000

        assert response.status_code == 200
        assert duration_ms < baseline_ms, \
            f"Response time {duration_ms}ms exceeds baseline {baseline_ms}ms"

    @pytest.mark.regression
    async def test_cache_hit_rate_regression(
        self,
        cache_manager: Any,
        baseline_hit_rate: float = 0.7
    ) -> None:
        """Ensure cache hit rate doesn't regress."""
        # Warm up cache
        for i in range(100):
            await cache_manager.set(f"test:key:{i}", {"data": i})

        # Test hits
        for i in range(100):
            await cache_manager.get(f"test:key:{i}")

        stats = cache_manager.get_stats()
        hit_rate = stats['memory_cache']['hit_rate']

        assert hit_rate >= baseline_hit_rate, \
            f"Cache hit rate {hit_rate} below baseline {baseline_hit_rate}"

    @pytest.mark.regression
    async def test_memory_usage_regression(
        self,
        cache_manager: Any,
        baseline_mb: float = 100
    ) -> None:
        """Ensure memory usage doesn't regress."""
        import sys

        # Get memory usage
        stats = cache_manager.get_stats()
        cache_size = stats['memory_cache']['size']

        # Rough estimate: assume ~1KB per cache entry
        estimated_mb = (cache_size * 1024) / (1024 * 1024)

        assert estimated_mb < baseline_mb, \
            f"Memory usage {estimated_mb}MB exceeds baseline {baseline_mb}MB"
