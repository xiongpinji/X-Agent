"""
从 tests/enterprise/test_architecture_optimization.py 移除的 cache_integration /
concurrency_optimization 相关测试（2026-07-19 归档）。

被测对象 backend/app/core/cache_integration.py 与
backend/app/core/concurrency_optimization.py 为死代码，已归档至
archive/dead_code_2026-07-19/backend/app/core/。
移除内容：TestCacheIntegration、TestConcurrencyOptimization 两个测试类，
以及 TestArchitectureIntegration（其两个方法均依赖 cache_integration）。
原文件其余测试（event_bus / config_hot_reload / error_handling）
仍在原位运行，不受影响。
"""

import asyncio
import pytest

from backend.app.core.cache import CacheManager
from backend.app.core.cache_integration import CacheIntegration, get_cache_integration
from backend.app.core.concurrency_optimization import (
    AdaptiveConcurrencyLimiter,
    BackpressureHandler,
    PriorityTaskScheduler,
)
from backend.app.core.event_bus import Event, EventType, get_event_bus


class TestCacheIntegration:
    """Test cache integration."""

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self):
        """Test cache set and get operations."""
        cache_manager = CacheManager()
        integration = CacheIntegration(cache_manager)

        key = "test_key"
        value = {"data": "test_value"}

        await integration.cache_set(key, value, ttl=3600)
        cached_value = await integration.cache_get(key)

        assert cached_value == value

    @pytest.mark.asyncio
    async def test_cache_invalidation(self):
        """Test cache invalidation."""
        cache_manager = CacheManager()
        integration = CacheIntegration(cache_manager)

        key = "test_key"
        value = {"data": "test_value"}

        await integration.cache_set(key, value)
        await integration.cache_delete(key)
        cached_value = await integration.cache_get(key)

        assert cached_value is None

    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self):
        """Test cache TTL expiration."""
        cache_manager = CacheManager()
        integration = CacheIntegration(cache_manager)

        key = "test_key"
        value = {"data": "test_value"}

        await integration.cache_set(key, value, ttl=1)
        await asyncio.sleep(1.1)
        cached_value = await integration.cache_get(key)

        assert cached_value is None


class TestConcurrencyOptimization:
    """Test concurrency optimization."""

    @pytest.mark.asyncio
    async def test_adaptive_limiter_basic(self):
        """Test basic adaptive concurrency limiter."""
        limiter = AdaptiveConcurrencyLimiter(initial_limit=5)

        await limiter.acquire()
        assert limiter._stats.active_tasks == 1

        limiter.release(success=True)
        assert limiter._stats.active_tasks == 0

    @pytest.mark.asyncio
    async def test_adaptive_limiter_success_rate(self):
        """Test adaptive limiter adjusts based on success rate."""
        limiter = AdaptiveConcurrencyLimiter(
            initial_limit=10,
            adjustment_interval=0.1,
            success_threshold=0.95,
        )

        # Simulate successful tasks
        for _ in range(20):
            await limiter.acquire()
            limiter.release(success=True)

        stats = limiter.get_stats()
        assert stats["success_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_backpressure_handler(self):
        """Test backpressure handler."""
        handler = BackpressureHandler(max_queue_size=100)

        await handler.update_queue_size(50)
        assert not await handler.check_backpressure()

        await handler.update_queue_size(85)
        assert await handler.check_backpressure()

        await handler.update_queue_size(15)
        assert not await handler.check_backpressure()

    @pytest.mark.asyncio
    async def test_priority_scheduler(self):
        """Test priority task scheduler."""
        scheduler = PriorityTaskScheduler(worker_count=2)
        await scheduler.start()

        executed_tasks = []

        async def task(task_id: int):
            executed_tasks.append(task_id)

        await scheduler.enqueue(lambda: task(1), priority=1)
        await scheduler.enqueue(lambda: task(2), priority=0)

        await asyncio.sleep(0.5)
        await scheduler.stop()

        assert len(executed_tasks) >= 1


class TestArchitectureIntegration:
    """Integration tests for architecture optimization."""

    @pytest.mark.asyncio
    async def test_event_bus_with_cache_invalidation(self):
        """Test event bus triggering cache invalidation."""
        event_bus = get_event_bus()
        cache_integration = get_cache_integration()

        # Set up cache
        await cache_integration.cache_set("user:123", {"name": "John"})

        # Publish event that should invalidate cache
        event = Event(
            event_type=EventType.MEMORY_UPDATED,
            source="memory",
            data={"memory_id": "user:123"},
        )

        # In real scenario, this would trigger cache invalidation
        await event_bus.publish(event)

        # Cache should still exist (no automatic invalidation in this test)
        cached = await cache_integration.cache_get("user:123")
        assert cached is not None

    @pytest.mark.asyncio
    async def test_concurrent_cache_operations(self):
        """Test concurrent cache operations."""
        cache_manager = CacheManager()
        integration = CacheIntegration(cache_manager)

        async def cache_operation(key: str, value: str):
            await integration.cache_set(key, value)
            await asyncio.sleep(0.01)
            return await integration.cache_get(key)

        tasks = [
            cache_operation(f"key_{i}", f"value_{i}") for i in range(10)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert all(r is not None for r in results)
