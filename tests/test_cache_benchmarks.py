"""Performance benchmarks for Redis cache layer.

Run with: pytest tests/test_cache_benchmarks.py -v --benchmark-only
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from backend.app.core.cache import get_cache_manager
from backend.app.core.db_cache import cache_query, get_cached_query
from backend.app.core.llm_cache import cache_embedding, get_cached_embedding
from backend.app.core.memory_cache import (
    cache_memory_item,
    cache_search_results,
    get_cached_memory_item,
    get_cached_search_results,
)


class TestCacheBenchmarks:
    """Performance benchmarks for cache operations."""

    @pytest.mark.asyncio
    async def test_cache_set_performance(self, benchmark) -> None:
        """Benchmark cache set operation."""
        cache = get_cache_manager()
        test_data = {"key": "value", "nested": {"data": list(range(100))}}

        async def set_operation() -> None:
            await cache.set("bench_key", test_data, ttl=3600)

        # Run benchmark
        result = benchmark(lambda: asyncio.run(set_operation()))

    @pytest.mark.asyncio
    async def test_cache_get_performance(self, benchmark) -> None:
        """Benchmark cache get operation."""
        cache = get_cache_manager()
        test_data = {"key": "value", "nested": {"data": list(range(100))}}

        async def setup() -> None:
            await cache.set("bench_key", test_data, ttl=3600)

        async def get_operation() -> None:
            await cache.get("bench_key")

        asyncio.run(setup())
        result = benchmark(lambda: asyncio.run(get_operation()))

    @pytest.mark.asyncio
    async def test_cache_hit_rate_performance(self, benchmark) -> None:
        """Benchmark cache hit rate with repeated gets."""
        cache = get_cache_manager()
        test_data = {"key": "value"}

        async def setup() -> None:
            await cache.set("bench_key", test_data, ttl=3600)

        async def repeated_gets() -> None:
            for _ in range(100):
                await cache.get("bench_key")

        asyncio.run(setup())
        result = benchmark(lambda: asyncio.run(repeated_gets()))

    @pytest.mark.asyncio
    async def test_memory_item_cache_performance(self, benchmark) -> None:
        """Benchmark memory item caching."""
        from backend.app.core.memory import MemoryItem

        item = MemoryItem(
            tenant_id="bench_tenant",
            content="x" * 1000,
            layer=3,
        )

        async def cache_operation() -> None:
            await cache_memory_item(item)
            await get_cached_memory_item(item.id)

        result = benchmark(lambda: asyncio.run(cache_operation()))

    @pytest.mark.asyncio
    async def test_search_results_cache_performance(self, benchmark) -> None:
        """Benchmark search results caching."""
        from backend.app.core.memory import MemoryItem, MemorySearchHit

        items = [
            MemorySearchHit(
                item=MemoryItem(
                    tenant_id="bench_tenant",
                    content=f"Memory {i}",
                    layer=3,
                ),
                score=0.9 - (i * 0.01),
            )
            for i in range(10)
        ]

        async def cache_operation() -> None:
            await cache_search_results("bench_tenant", "test query", items)
            await get_cached_search_results("bench_tenant", "test query")

        result = benchmark(lambda: asyncio.run(cache_operation()))

    @pytest.mark.asyncio
    async def test_embedding_cache_performance(self, benchmark) -> None:
        """Benchmark embedding caching."""
        embedding = [0.1 * i for i in range(1536)]  # text-embedding-3-small size

        async def cache_operation() -> None:
            await cache_embedding("test text", embedding, "text-embedding-3-small")
            await get_cached_embedding("test text", "text-embedding-3-small")

        result = benchmark(lambda: asyncio.run(cache_operation()))

    @pytest.mark.asyncio
    async def test_query_cache_performance(self, benchmark) -> None:
        """Benchmark database query caching."""
        query_result = {
            "id": "user1",
            "email": "test@example.com",
            "name": "Test User",
            "metadata": {"key": "value"},
        }

        async def cache_operation() -> None:
            await cache_query("user", query_result, ttl=3600, user_id="user1")
            await get_cached_query("user", user_id="user1")

        result = benchmark(lambda: asyncio.run(cache_operation()))


class TestCacheScalability:
    """Test cache scalability with large datasets."""

    @pytest.mark.asyncio
    async def test_large_dataset_caching(self) -> None:
        """Test caching of large datasets."""
        cache = get_cache_manager()
        large_data = {
            "items": [{"id": i, "data": f"item_{i}" * 10} for i in range(1000)],
            "metadata": {"count": 1000, "size": "large"},
        }

        start = time.time()
        await cache.set("large_dataset", large_data, ttl=3600)
        set_time = time.time() - start

        start = time.time()
        result = await cache.get("large_dataset")
        get_time = time.time() - start

        assert result is not None
        assert len(result["items"]) == 1000
        print(f"Large dataset set time: {set_time*1000:.2f}ms")
        print(f"Large dataset get time: {get_time*1000:.2f}ms")

    @pytest.mark.asyncio
    async def test_many_keys_performance(self) -> None:
        """Test performance with many cache keys."""
        cache = get_cache_manager()
        num_keys = 1000

        # Set many keys
        start = time.time()
        for i in range(num_keys):
            await cache.set(f"key_{i}", {"value": i}, ttl=3600)
        set_time = time.time() - start

        # Get many keys
        start = time.time()
        for i in range(num_keys):
            await cache.get(f"key_{i}")
        get_time = time.time() - start

        print(f"Set {num_keys} keys: {set_time:.2f}s ({num_keys/set_time:.0f} ops/sec)")
        print(f"Get {num_keys} keys: {get_time:.2f}s ({num_keys/get_time:.0f} ops/sec)")

    @pytest.mark.asyncio
    async def test_concurrent_access(self) -> None:
        """Test concurrent cache access."""
        cache = get_cache_manager()
        num_tasks = 100

        async def concurrent_operation(task_id: int) -> None:
            for i in range(10):
                key = f"concurrent_{task_id}_{i}"
                await cache.set(key, {"task": task_id, "iter": i}, ttl=3600)
                await cache.get(key)

        start = time.time()
        await asyncio.gather(*[concurrent_operation(i) for i in range(num_tasks)])
        elapsed = time.time() - start

        total_ops = num_tasks * 10 * 2  # 10 iterations, 2 ops per iteration
        print(f"Concurrent operations: {total_ops} ops in {elapsed:.2f}s ({total_ops/elapsed:.0f} ops/sec)")


class TestCacheMemoryUsage:
    """Test cache memory usage."""

    @pytest.mark.asyncio
    async def test_memory_usage_with_ttl(self) -> None:
        """Test that TTL properly expires entries."""
        cache = get_cache_manager()

        # Set entries with short TTL
        for i in range(100):
            await cache.set(f"ttl_key_{i}", {"data": "x" * 1000}, ttl=1)

        # Verify entries exist
        exists_before = sum(
            1 for i in range(100) if await cache.exists(f"ttl_key_{i}")
        )
        print(f"Entries before expiry: {exists_before}")

        # Wait for expiry
        await asyncio.sleep(1.1)

        # Verify entries are expired
        exists_after = sum(
            1 for i in range(100) if await cache.exists(f"ttl_key_{i}")
        )
        print(f"Entries after expiry: {exists_after}")
        assert exists_after == 0


class TestCacheComparison:
    """Compare cache performance with and without caching."""

    @pytest.mark.asyncio
    async def test_cache_speedup(self) -> None:
        """Measure cache speedup factor."""
        cache = get_cache_manager()
        test_data = {"data": "x" * 10000}

        # Simulate expensive operation
        async def expensive_operation() -> dict[str, Any]:
            await asyncio.sleep(0.1)  # Simulate 100ms operation
            return test_data

        # Without cache
        start = time.time()
        for _ in range(10):
            await expensive_operation()
        without_cache_time = time.time() - start

        # With cache
        await cache.set("speedup_test", test_data, ttl=3600)
        start = time.time()
        for _ in range(10):
            await cache.get("speedup_test")
        with_cache_time = time.time() - start

        speedup = without_cache_time / with_cache_time
        print(f"Without cache: {without_cache_time:.2f}s")
        print(f"With cache: {with_cache_time:.2f}s")
        print(f"Speedup: {speedup:.0f}x")
        assert speedup > 100  # Should be at least 100x faster


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--benchmark-only"])
