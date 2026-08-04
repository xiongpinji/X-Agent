"""Unit tests for Redis cache layer."""

from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.core.cache import (
    CacheManager,
    CacheStats,
    async_cached,
    cached,
    get_cache_manager,
    get_cache_stats,
    record_cache_error,
    record_cache_hit,
    record_cache_miss,
)


class TestCacheStats:
    """Test cache statistics tracking."""

    def test_cache_stats_initialization(self) -> None:
        stats = CacheStats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.errors == 0
        assert stats.hit_rate == 0.0

    def test_cache_stats_hit_rate(self) -> None:
        stats = CacheStats()
        stats.record_hit()
        stats.record_hit()
        stats.record_miss()
        assert stats.hit_rate == pytest.approx(2 / 3)

    def test_cache_stats_to_dict(self) -> None:
        stats = CacheStats()
        stats.record_hit()
        stats.record_miss()
        stats.record_error()
        result = stats.to_dict()
        assert result["hits"] == 1
        assert result["misses"] == 1
        assert result["errors"] == 1
        assert "hit_rate" in result
        assert "uptime_seconds" in result


class TestCacheManager:
    """Test cache manager functionality."""

    @pytest.mark.asyncio
    async def test_cache_manager_get_set(self) -> None:
        manager = CacheManager()
        await manager.set("test_key", {"data": "value"}, ttl=60)
        result = await manager.get("test_key")
        assert result == {"data": "value"}

    @pytest.mark.asyncio
    async def test_cache_manager_ttl_expiry(self) -> None:
        manager = CacheManager()
        await manager.set("test_key", "value", ttl=1)
        await asyncio.sleep(1.1)
        result = await manager.get("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_manager_delete(self) -> None:
        manager = CacheManager()
        await manager.set("test_key", "value")
        await manager.delete("test_key")
        result = await manager.get("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_manager_exists(self) -> None:
        manager = CacheManager()
        await manager.set("test_key", "value")
        assert await manager.get("test_key") is not None
        await manager.delete("test_key")
        assert await manager.get("test_key") is None

    @pytest.mark.asyncio
    async def test_cache_manager_clear(self) -> None:
        manager = CacheManager()
        await manager.set("key1", "value1")
        await manager.set("key2", "value2")
        await manager.invalidate_pattern("*")
        assert await manager.get("key1") is None
        assert await manager.get("key2") is None

    @pytest.mark.asyncio
    async def test_cache_manager_in_memory_fallback(self) -> None:
        """Test in-memory fallback when Redis is unavailable."""
        manager = CacheManager(redis_url=None)
        await manager.set("test_key", {"data": "value"}, ttl=60)
        result = await manager.get("test_key")
        assert result == {"data": "value"}


class TestCacheDecorators:
    """Test cache decorators."""

    @pytest.mark.asyncio
    async def test_async_cached_decorator(self) -> None:
        call_count = 0

        @async_cached(ttl_seconds=60, key_prefix="test")
        async def expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call should execute function
        result1 = await expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # Second call should use cache
        result2 = await expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Function not called again

        # Different argument should execute function
        result3 = await expensive_function(10)
        assert result3 == 20
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_cached_decorator(self) -> None:
        call_count = 0

        @cached(ttl_seconds=60, key_prefix="test")
        def expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call should execute function
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # Second call should use cache
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Function not called again


class TestCacheStatistics:
    """Test cache statistics tracking."""

    def test_record_cache_hit(self) -> None:
        record_cache_hit()
        stats = get_cache_stats()
        assert stats["hits"] >= 1

    def test_record_cache_miss(self) -> None:
        record_cache_miss()
        stats = get_cache_stats()
        assert stats["misses"] >= 1

    def test_record_cache_error(self) -> None:
        record_cache_error()
        stats = get_cache_stats()
        assert stats["errors"] >= 1


class TestCacheIntegration:
    """Integration tests for cache layer."""

    @pytest.mark.asyncio
    async def test_multi_layer_cache_hit(self) -> None:
        """Test L1 and L2 cache layers."""
        manager = CacheManager()
        test_data = {"key": "value", "nested": {"data": 123}}

        # Set in both layers
        await manager.set("test_key", test_data, ttl=60)

        # Get should return from cache
        result = await manager.get("test_key")
        assert result == test_data

    @pytest.mark.asyncio
    async def test_cache_serialization(self) -> None:
        """Test JSON serialization of complex objects."""
        manager = CacheManager()
        complex_data = {
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
            "string": "test",
            "number": 42,
            "float": 3.14,
            "bool": True,
            "null": None,
        }

        await manager.set("complex", complex_data)
        result = await manager.get("complex")
        assert result == complex_data

    @pytest.mark.asyncio
    async def test_cache_performance(self) -> None:
        """Test cache performance improvement."""
        manager = CacheManager()
        test_data = {"data": "x" * 1000}

        # Measure cache hit time
        await manager.set("perf_test", test_data)
        start = time.time()
        for _ in range(100):
            await manager.get("perf_test")
        cache_time = time.time() - start

        # Cache should be very fast (< 100ms for 100 operations)
        assert cache_time < 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
