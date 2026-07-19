"""
从 tests/test_performance_optimization.py 移除的 cache_optimization 相关测试（2026-07-19 归档）。

被测对象 backend/app/core/cache_optimization.py 为死代码，已归档至
archive/dead_code_2026-07-19/backend/app/core/cache_optimization.py。
移除内容：TestCacheStatistics、TestMultiLevelCache 两个测试类，
以及 TestPerformanceOptimizationIntegration 中的
test_cache_warming / test_cache_invalidation 两个方法。
原文件其余测试（db_optimization / api_optimization / performance_monitor）
仍在原位运行，不受影响。
"""

import pytest

from backend.app.core.cache_optimization import (
    CacheWarmer,
    CacheInvalidationStrategy,
    CacheStatistics,
    MultiLevelCache,
)


class TestCacheStatistics:
    """Tests for cache statistics."""

    def test_statistics(self) -> None:
        """Test cache statistics."""
        stats = CacheStatistics()

        # Record operations
        stats.record_hit()
        stats.record_hit()
        stats.record_miss()
        stats.record_set()
        stats.record_delete()

        assert stats.hits == 2
        assert stats.misses == 1
        assert stats.sets == 1
        assert stats.deletes == 1
        assert stats.hit_rate() == pytest.approx(66.67, rel=0.01)


class TestMultiLevelCache:
    """Tests for multi-level cache."""

    @pytest.mark.asyncio
    async def test_get_set(self) -> None:
        """Test cache get/set."""
        cache = MultiLevelCache(l1_cache={}, l2_cache=None)

        # Set value
        await cache.set("key1", {"data": "value"})
        assert "key1" in cache.l1_cache

        # Get value
        result = await cache.get("key1")
        assert result == {"data": "value"}

    @pytest.mark.asyncio
    async def test_delete(self) -> None:
        """Test cache delete."""
        cache = MultiLevelCache(l1_cache={}, l2_cache=None)

        await cache.set("key1", {"data": "value"})
        await cache.delete("key1")

        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_invalidate_pattern(self) -> None:
        """Test pattern invalidation."""
        cache = MultiLevelCache(l1_cache={}, l2_cache=None)

        await cache.set("workflow:1", {"data": "value1"})
        await cache.set("workflow:2", {"data": "value2"})
        await cache.set("agent:1", {"data": "value3"})

        await cache.invalidate_pattern("workflow:")

        assert await cache.get("workflow:1") is None
        assert await cache.get("workflow:2") is None
        assert await cache.get("agent:1") == {"data": "value3"}


class TestCacheOptimizationIntegration:
    """Integration tests for cache optimizations (removed from TestPerformanceOptimizationIntegration)."""

    @pytest.mark.asyncio
    async def test_cache_warming(self) -> None:
        """Test cache warming."""
        cache = MultiLevelCache(l1_cache={}, l2_cache=None)
        warmer = CacheWarmer(cache)

        async def loader() -> dict[str, str]:
            return {"key1": "value1", "key2": "value2"}

        await warmer.warm_cache("test", loader, ttl=60)

        result = await cache.get("test")
        assert result is not None

    @pytest.mark.asyncio
    async def test_cache_invalidation(self) -> None:
        """Test cache invalidation."""
        cache = MultiLevelCache(l1_cache={}, l2_cache=None)

        await cache.set("workflow:1", {"data": "value"})
        await cache.set("workflow:2", {"data": "value"})

        await CacheInvalidationStrategy.invalidate_on_update(
            cache,
            "workflow",
            "1",
        )

        assert await cache.get("workflow:1") is None
        assert await cache.get("workflow:2") == {"data": "value"}
