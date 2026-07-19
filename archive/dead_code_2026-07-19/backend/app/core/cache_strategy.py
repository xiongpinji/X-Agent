"""
Unified cache strategy for X-Agent performance optimization.

Implements:
- Consistent cache key generation with versioning
- Event-driven cache invalidation
- Cache warming for hot data
- Cache statistics and monitoring
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CacheKeyConfig:
    """Configuration for cache key generation."""
    version: str = "v1"
    separator: str = ":"


class CacheKeyBuilder:
    """Unified cache key generation with versioning."""

    VERSION = "v1"
    SEPARATOR = ":"

    @staticmethod
    def _hash_query(query: str, length: int = 8) -> str:
        """Generate hash of query string."""
        return hashlib.md5(query.encode()).hexdigest()[:length]

    @staticmethod
    def memory_search(
        tenant_id: str,
        query: str,
        layers: list[int] | None = None,
        top_k: int = 10,
        page: int = 1,
    ) -> str:
        """Generate cache key for memory search.

        Args:
            tenant_id: Tenant identifier
            query: Search query string
            layers: Memory layers to search (default: [1, 2, 3, 4])
            top_k: Number of results to return
            page: Page number for pagination

        Returns:
            Cache key string
        """
        layers = layers or [1, 2, 3, 4]
        layers_str = ",".join(map(str, sorted(layers)))
        query_hash = CacheKeyBuilder._hash_query(query)
        return (
            f"{CacheKeyBuilder.VERSION}{CacheKeyBuilder.SEPARATOR}memory"
            f"{CacheKeyBuilder.SEPARATOR}search{CacheKeyBuilder.SEPARATOR}{tenant_id}"
            f"{CacheKeyBuilder.SEPARATOR}{query_hash}{CacheKeyBuilder.SEPARATOR}{layers_str}"
            f"{CacheKeyBuilder.SEPARATOR}{top_k}{CacheKeyBuilder.SEPARATOR}{page}"
        )

    @staticmethod
    def memory_layer(tenant_id: str, layer: int) -> str:
        """Generate cache key for memory layer.

        Args:
            tenant_id: Tenant identifier
            layer: Memory layer number (1-4)

        Returns:
            Cache key string
        """
        return (
            f"{CacheKeyBuilder.VERSION}{CacheKeyBuilder.SEPARATOR}memory"
            f"{CacheKeyBuilder.SEPARATOR}layer{CacheKeyBuilder.SEPARATOR}{tenant_id}"
            f"{CacheKeyBuilder.SEPARATOR}{layer}"
        )

    @staticmethod
    def memory_item(memory_id: str) -> str:
        """Generate cache key for individual memory item.

        Args:
            memory_id: Memory item identifier

        Returns:
            Cache key string
        """
        return (
            f"{CacheKeyBuilder.VERSION}{CacheKeyBuilder.SEPARATOR}memory"
            f"{CacheKeyBuilder.SEPARATOR}item{CacheKeyBuilder.SEPARATOR}{memory_id}"
        )

    @staticmethod
    def run_detail(trace_id: str) -> str:
        """Generate cache key for run detail.

        Args:
            trace_id: Run trace identifier

        Returns:
            Cache key string
        """
        return (
            f"{CacheKeyBuilder.VERSION}{CacheKeyBuilder.SEPARATOR}run"
            f"{CacheKeyBuilder.SEPARATOR}detail{CacheKeyBuilder.SEPARATOR}{trace_id}"
        )

    @staticmethod
    def run_list(
        tenant_id: str,
        status: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> str:
        """Generate cache key for run list.

        Args:
            tenant_id: Tenant identifier
            status: Run status filter (optional)
            page: Page number for pagination
            limit: Number of items per page

        Returns:
            Cache key string
        """
        status_str = status or "all"
        return (
            f"{CacheKeyBuilder.VERSION}{CacheKeyBuilder.SEPARATOR}run"
            f"{CacheKeyBuilder.SEPARATOR}list{CacheKeyBuilder.SEPARATOR}{tenant_id}"
            f"{CacheKeyBuilder.SEPARATOR}{status_str}{CacheKeyBuilder.SEPARATOR}{page}"
            f"{CacheKeyBuilder.SEPARATOR}{limit}"
        )

    @staticmethod
    def audit_logs(
        tenant_id: str,
        action: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> str:
        """Generate cache key for audit logs.

        Args:
            tenant_id: Tenant identifier
            action: Action type filter (optional)
            page: Page number for pagination
            limit: Number of items per page

        Returns:
            Cache key string
        """
        action_str = action or "all"
        return (
            f"{CacheKeyBuilder.VERSION}{CacheKeyBuilder.SEPARATOR}audit"
            f"{CacheKeyBuilder.SEPARATOR}logs{CacheKeyBuilder.SEPARATOR}{tenant_id}"
            f"{CacheKeyBuilder.SEPARATOR}{action_str}{CacheKeyBuilder.SEPARATOR}{page}"
            f"{CacheKeyBuilder.SEPARATOR}{limit}"
        )

    @staticmethod
    def agent_state(agent_id: str) -> str:
        """Generate cache key for agent state.

        Args:
            agent_id: Agent identifier

        Returns:
            Cache key string
        """
        return (
            f"{CacheKeyBuilder.VERSION}{CacheKeyBuilder.SEPARATOR}agent"
            f"{CacheKeyBuilder.SEPARATOR}state{CacheKeyBuilder.SEPARATOR}{agent_id}"
        )

    @staticmethod
    def workflow_detail(workflow_id: str) -> str:
        """Generate cache key for workflow detail.

        Args:
            workflow_id: Workflow identifier

        Returns:
            Cache key string
        """
        return (
            f"{CacheKeyBuilder.VERSION}{CacheKeyBuilder.SEPARATOR}workflow"
            f"{CacheKeyBuilder.SEPARATOR}detail{CacheKeyBuilder.SEPARATOR}{workflow_id}"
        )

    @staticmethod
    def workflow_list(tenant_id: str, page: int = 1, limit: int = 20) -> str:
        """Generate cache key for workflow list.

        Args:
            tenant_id: Tenant identifier
            page: Page number for pagination
            limit: Number of items per page

        Returns:
            Cache key string
        """
        return (
            f"{CacheKeyBuilder.VERSION}{CacheKeyBuilder.SEPARATOR}workflow"
            f"{CacheKeyBuilder.SEPARATOR}list{CacheKeyBuilder.SEPARATOR}{tenant_id}"
            f"{CacheKeyBuilder.SEPARATOR}{page}{CacheKeyBuilder.SEPARATOR}{limit}"
        )


class CacheInvalidationManager:
    """Manages cache invalidation across the system using event-based patterns."""

    def __init__(self, cache_backend: Any) -> None:
        """Initialize cache invalidation manager.

        Args:
            cache_backend: Cache backend instance (Redis or in-memory)
        """
        self.cache = cache_backend
        self.invalidation_patterns: dict[str, list[str]] = {
            "memory.store": [
                "memory:search:*",
                "memory:layer:*",
            ],
            "memory.consolidate": [
                "memory:layer:*",
                "memory:search:*",
            ],
            "memory.delete": [
                "memory:item:*",
                "memory:search:*",
                "memory:layer:*",
            ],
            "run.create": [
                "run:list:*",
            ],
            "run.update": [
                "run:detail:*",
                "run:list:*",
            ],
            "run.complete": [
                "run:detail:*",
                "run:list:*",
            ],
            "audit.record": [
                "audit:logs:*",
            ],
            "agent.update": [
                "agent:state:*",
            ],
            "workflow.update": [
                "workflow:detail:*",
                "workflow:list:*",
            ],
        }

    async def invalidate_by_pattern(self, pattern: str) -> int:
        """Invalidate all cache keys matching pattern.

        Args:
            pattern: Cache key pattern (supports wildcards)

        Returns:
            Number of keys invalidated
        """
        count = 0
        try:
            # For Redis backend
            if hasattr(self.cache, "redis"):
                redis_client = self.cache.redis
                cursor = 0
                while True:
                    cursor, keys = await redis_client.scan(
                        cursor,
                        match=pattern,
                        count=100,
                    )
                    if keys:
                        await redis_client.delete(*keys)
                        count += len(keys)
                    if cursor == 0:
                        break
            # For in-memory backend
            elif hasattr(self.cache, "_cache"):
                import fnmatch
                keys_to_delete = [
                    k for k in self.cache._cache.keys()
                    if fnmatch.fnmatch(k, pattern)
                ]
                for key in keys_to_delete:
                    await self.cache.delete(key)
                count = len(keys_to_delete)
        except Exception as e:
            logger.error(f"Error invalidating cache pattern {pattern}: {e}")

        return count

    async def invalidate_on_event(self, event_type: str, context: dict) -> None:
        """Invalidate cache based on event.

        Args:
            event_type: Type of event (e.g., 'memory.store', 'run.update')
            context: Event context with tenant_id, agent_id, etc.
        """
        patterns = self.invalidation_patterns.get(event_type, [])
        for pattern in patterns:
            # Expand pattern with context if needed
            expanded_pattern = pattern
            if "{tenant_id}" in pattern and "tenant_id" in context:
                expanded_pattern = expanded_pattern.replace(
                    "{tenant_id}",
                    context["tenant_id"],
                )
            if "{agent_id}" in pattern and "agent_id" in context:
                expanded_pattern = expanded_pattern.replace(
                    "{agent_id}",
                    context["agent_id"],
                )

            count = await self.invalidate_by_pattern(expanded_pattern)
            if count > 0:
                logger.info(
                    f"Invalidated {count} cache keys for event {event_type} "
                    f"with pattern {expanded_pattern}"
                )

    async def invalidate_tenant_cache(self, tenant_id: str) -> int:
        """Invalidate all cache for a specific tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Number of keys invalidated
        """
        pattern = f"*{CacheKeyBuilder.SEPARATOR}{tenant_id}*"
        return await self.invalidate_by_pattern(pattern)

    async def invalidate_agent_cache(self, agent_id: str) -> int:
        """Invalidate all cache for a specific agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Number of keys invalidated
        """
        pattern = f"*{CacheKeyBuilder.SEPARATOR}{agent_id}*"
        return await self.invalidate_by_pattern(pattern)


class CacheWarmer:
    """Warms cache with frequently accessed data."""

    def __init__(self, cache_backend: Any) -> None:
        """Initialize cache warmer.

        Args:
            cache_backend: Cache backend instance
        """
        self.cache = cache_backend

    async def warm_memory_layers(
        self,
        memory_system: Any,
        tenant_id: str,
        ttl: int = 3600,
    ) -> dict[str, int]:
        """Pre-load memory layers for tenant.

        Args:
            memory_system: Memory system instance
            tenant_id: Tenant identifier
            ttl: Time-to-live for cache entries

        Returns:
            Dictionary with warming results
        """
        results = {}
        try:
            for layer in [1, 2, 3, 4]:
                cache_key = CacheKeyBuilder.memory_layer(tenant_id, layer)
                # Fetch layer items from memory system
                items = await memory_system.layer_items(layer)
                await self.cache.set(cache_key, items, ttl=ttl)
                results[f"layer_{layer}"] = len(items) if items else 0
        except Exception as e:
            logger.error(f"Error warming memory layers: {e}")

        return results

    async def warm_recent_runs(
        self,
        run_store: Any,
        tenant_id: str,
        limit: int = 50,
        ttl: int = 1800,
    ) -> dict[str, int]:
        """Pre-load recent runs.

        Args:
            run_store: Run store instance
            tenant_id: Tenant identifier
            limit: Number of recent runs to cache
            ttl: Time-to-live for cache entries

        Returns:
            Dictionary with warming results
        """
        results = {}
        try:
            recent_runs = await run_store.list_recent(tenant_id, limit=limit)
            for run in recent_runs:
                cache_key = CacheKeyBuilder.run_detail(run.trace_id)
                await self.cache.set(
                    cache_key,
                    run.model_dump() if hasattr(run, "model_dump") else run.__dict__,
                    ttl=ttl,
                )
            results["recent_runs"] = len(recent_runs)
        except Exception as e:
            logger.error(f"Error warming recent runs: {e}")

        return results

    async def warm_all(
        self,
        tenant_id: str,
        memory_system: Any | None = None,
        run_store: Any | None = None,
    ) -> dict[str, Any]:
        """Warm all critical caches.

        Args:
            tenant_id: Tenant identifier
            memory_system: Memory system instance (optional)
            run_store: Run store instance (optional)

        Returns:
            Dictionary with all warming results
        """
        results = {
            "tenant_id": tenant_id,
            "memory_layers": {},
            "recent_runs": {},
            "timestamp": None,
        }

        if memory_system:
            try:
                results["memory_layers"] = await self.warm_memory_layers(
                    memory_system,
                    tenant_id,
                )
            except Exception as e:
                logger.error(f"Failed to warm memory layers: {e}")

        if run_store:
            try:
                results["recent_runs"] = await self.warm_recent_runs(
                    run_store,
                    tenant_id,
                )
            except Exception as e:
                logger.error(f"Failed to warm recent runs: {e}")

        from datetime import datetime, timezone
        results["timestamp"] = datetime.now(timezone.utc).isoformat()

        return results


class CacheStatistics:
    """Tracks cache statistics and performance metrics."""

    def __init__(self) -> None:
        """Initialize cache statistics tracker."""
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0
        self.evictions = 0

    def record_hit(self) -> None:
        """Record cache hit."""
        self.hits += 1

    def record_miss(self) -> None:
        """Record cache miss."""
        self.misses += 1

    def record_set(self) -> None:
        """Record cache set operation."""
        self.sets += 1

    def record_delete(self) -> None:
        """Record cache delete operation."""
        self.deletes += 1

    def record_eviction(self) -> None:
        """Record cache eviction."""
        self.evictions += 1

    def get_hit_rate(self) -> float:
        """Get cache hit rate as percentage.

        Returns:
            Hit rate (0-100)
        """
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return (self.hits / total) * 100

    def get_stats(self) -> dict[str, Any]:
        """Get all cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "evictions": self.evictions,
            "hit_rate_percent": self.get_hit_rate(),
            "total_operations": self.hits + self.misses + self.sets,
        }

    def reset(self) -> None:
        """Reset all statistics."""
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0
        self.evictions = 0
