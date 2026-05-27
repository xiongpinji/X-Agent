"""
Cache Optimization and Monitoring Module.

Implements advanced caching strategies:
- Cache warming
- Cache invalidation strategies
- Cache statistics and monitoring
- Multi-level caching
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheWarmer:
    """Warms cache with frequently accessed data."""

    def __init__(self, cache_manager: Any) -> None:
        self.cache_manager = cache_manager
        self._warming_tasks: dict[str, asyncio.Task[Any]] = {}

    async def warm_cache(
        self,
        key: str,
        loader: Callable[[], Any],
        ttl: int = 3600,
    ) -> None:
        """Warm cache with data from loader."""
        try:
            data = await loader() if asyncio.iscoroutinefunction(loader) else loader()
            await self.cache_manager.set(key, data, ttl=ttl)
            logger.info(f"Cache warmed for key: {key}")
        except Exception as e:
            logger.error(f"Error warming cache for key {key}: {e}")

    async def schedule_cache_warming(
        self,
        key: str,
        loader: Callable[[], Any],
        interval: int = 3600,
        ttl: int = 3600,
    ) -> None:
        """Schedule periodic cache warming."""
        async def warming_loop() -> None:
            while True:
                await self.warm_cache(key, loader, ttl)
                await asyncio.sleep(interval)

        task = asyncio.create_task(warming_loop())
        self._warming_tasks[key] = task
        logger.info(f"Scheduled cache warming for key: {key} (interval: {interval}s)")

    async def stop_warming(self, key: str) -> None:
        """Stop cache warming for key."""
        if key in self._warming_tasks:
            self._warming_tasks[key].cancel()
            del self._warming_tasks[key]
            logger.info(f"Stopped cache warming for key: {key}")

    async def stop_all_warming(self) -> None:
        """Stop all cache warming tasks."""
        for task in self._warming_tasks.values():
            task.cancel()
        self._warming_tasks.clear()
        logger.info("Stopped all cache warming tasks")


class CacheInvalidationStrategy:
    """Manages cache invalidation strategies."""

    @staticmethod
    async def invalidate_on_update(
        cache_manager: Any,
        resource_type: str,
        resource_id: str,
    ) -> None:
        """Invalidate cache when resource is updated."""
        pattern = f"{resource_type}:{resource_id}:*"
        await cache_manager.invalidate_pattern(pattern)
        logger.info(f"Invalidated cache for {resource_type}:{resource_id}")

    @staticmethod
    async def invalidate_related(
        cache_manager: Any,
        resource_type: str,
        related_types: list[str],
    ) -> None:
        """Invalidate related cache entries."""
        for related_type in related_types:
            pattern = f"{related_type}:*"
            await cache_manager.invalidate_pattern(pattern)
        logger.info(f"Invalidated related cache for {resource_type}")

    @staticmethod
    async def ttl_based_invalidation(
        cache_manager: Any,
        key: str,
        ttl: int,
    ) -> None:
        """Invalidate cache after TTL expires."""
        await asyncio.sleep(ttl)
        await cache_manager.delete(key)
        logger.info(f"TTL-based invalidation for key: {key}")


class CacheStatistics:
    """Tracks cache statistics and performance."""

    def __init__(self) -> None:
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0
        self.evictions = 0
        self.start_time = time.time()

    def record_hit(self) -> None:
        """Record cache hit."""
        self.hits += 1

    def record_miss(self) -> None:
        """Record cache miss."""
        self.misses += 1

    def record_set(self) -> None:
        """Record cache set."""
        self.sets += 1

    def record_delete(self) -> None:
        """Record cache delete."""
        self.deletes += 1

    def record_eviction(self) -> None:
        """Record cache eviction."""
        self.evictions += 1

    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return (self.hits / total) * 100

    def uptime(self) -> float:
        """Get cache uptime in seconds."""
        return time.time() - self.start_time

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{self.hit_rate():.2f}%",
            "sets": self.sets,
            "deletes": self.deletes,
            "evictions": self.evictions,
            "uptime_seconds": f"{self.uptime():.2f}",
        }


class MultiLevelCache:
    """Implements multi-level caching (L1: memory, L2: Redis)."""

    def __init__(
        self,
        l1_cache: dict[str, Any] | None = None,
        l2_cache: Any | None = None,
    ) -> None:
        self.l1_cache = l1_cache or {}  # In-memory cache
        self.l2_cache = l2_cache  # Redis cache
        self.stats = CacheStatistics()

    async def get(self, key: str) -> Any | None:
        """Get value from cache (L1 first, then L2)."""
        # Check L1 cache
        if key in self.l1_cache:
            self.stats.record_hit()
            return self.l1_cache[key]

        # Check L2 cache
        if self.l2_cache:
            value = await self.l2_cache.get(key)
            if value is not None:
                self.l1_cache[key] = value  # Populate L1
                self.stats.record_hit()
                return value

        self.stats.record_miss()
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """Set value in cache (both L1 and L2)."""
        self.l1_cache[key] = value
        self.stats.record_set()

        if self.l2_cache:
            await self.l2_cache.set(key, value, ttl=ttl)

    async def delete(self, key: str) -> None:
        """Delete value from cache (both L1 and L2)."""
        if key in self.l1_cache:
            del self.l1_cache[key]
        self.stats.record_delete()

        if self.l2_cache:
            await self.l2_cache.delete(key)

    async def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate cache entries matching pattern."""
        # Invalidate L1
        keys_to_delete = [k for k in self.l1_cache if pattern in k]
        for k in keys_to_delete:
            del self.l1_cache[k]

        # Invalidate L2
        if self.l2_cache:
            await self.l2_cache.invalidate_pattern(pattern)

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return self.stats.get_stats()

    def clear(self) -> None:
        """Clear all caches."""
        self.l1_cache.clear()
        logger.info("Cleared all caches")


class CachePreloader:
    """Preloads cache with critical data on startup."""

    def __init__(self, cache: MultiLevelCache) -> None:
        self.cache = cache

    async def preload_workflows(self, workflow_loader: Callable) -> None:
        """Preload workflows into cache."""
        try:
            workflows = await workflow_loader()
            for workflow in workflows:
                key = f"workflow:{workflow.get('id')}"
                await self.cache.set(key, workflow, ttl=3600)
            logger.info(f"Preloaded {len(workflows)} workflows into cache")
        except Exception as e:
            logger.error(f"Error preloading workflows: {e}")

    async def preload_agents(self, agent_loader: Callable) -> None:
        """Preload agents into cache."""
        try:
            agents = await agent_loader()
            for agent in agents:
                key = f"agent:{agent.get('id')}"
                await self.cache.set(key, agent, ttl=3600)
            logger.info(f"Preloaded {len(agents)} agents into cache")
        except Exception as e:
            logger.error(f"Error preloading agents: {e}")

    async def preload_tools(self, tool_loader: Callable) -> None:
        """Preload tools into cache."""
        try:
            tools = await tool_loader()
            for tool in tools:
                key = f"tool:{tool.get('name')}"
                await self.cache.set(key, tool, ttl=7200)
            logger.info(f"Preloaded {len(tools)} tools into cache")
        except Exception as e:
            logger.error(f"Error preloading tools: {e}")
