"""
Cache Integration for X-Agent.

Provides cache decorators and utilities for:
- Database query caching
- API response caching
- Memory system caching
- Cache warming and invalidation
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from functools import wraps
from typing import Any, Callable, TypeVar

from backend.app.core.cache import CacheManager, get_cache_manager

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheIntegration:
    """
    Centralized cache integration for X-Agent.

    Provides methods to cache database queries, API responses, and other operations.
    """

    def __init__(self, cache_manager: CacheManager | None = None) -> None:
        self.cache_manager = cache_manager or get_cache_manager()

    def _generate_cache_key(self, prefix: str, *args: Any, **kwargs: Any) -> str:
        """Generate a cache key from function arguments."""
        key_parts = [prefix]
        key_parts.extend(str(arg) for arg in args)
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        key_str = "|".join(key_parts)
        return hashlib.md5(key_str.encode()).hexdigest()

    async def cache_get(self, key: str) -> Any | None:
        """Get value from cache."""
        return await self.cache_manager.get(key)

    async def cache_set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value in cache."""
        await self.cache_manager.set(key, value, ttl)

    async def cache_delete(self, key: str) -> None:
        """Delete value from cache."""
        await self.cache_manager.delete(key)

    async def cache_invalidate_pattern(self, pattern: str) -> None:
        """Invalidate all keys matching a pattern."""
        await self.cache_manager.invalidate_pattern(pattern)

    # Database Query Caching
    async def cache_user_query(self, user_id: str, ttl: int = 3600) -> str:
        """Generate cache key for user query."""
        return self._generate_cache_key("user", user_id)

    async def cache_workflow_query(self, workflow_id: str, ttl: int = 3600) -> str:
        """Generate cache key for workflow query."""
        return self._generate_cache_key("workflow", workflow_id)

    async def cache_agent_query(self, agent_id: str, ttl: int = 3600) -> str:
        """Generate cache key for agent query."""
        return self._generate_cache_key("agent", agent_id)

    async def cache_memory_query(self, memory_id: str, query: str, ttl: int = 1800) -> str:
        """Generate cache key for memory query."""
        return self._generate_cache_key("memory", memory_id, query)

    async def cache_tool_query(self, tool_name: str, ttl: int = 7200) -> str:
        """Generate cache key for tool query."""
        return self._generate_cache_key("tool", tool_name)

    # Cache Warming
    async def warm_cache(self, data_loader: Callable, prefix: str, ttl: int = 3600) -> None:
        """Warm cache with data from a loader function."""
        try:
            data = await data_loader() if asyncio.iscoroutinefunction(data_loader) else data_loader()
            if isinstance(data, dict):
                for key, value in data.items():
                    cache_key = self._generate_cache_key(prefix, key)
                    await self.cache_manager.set(cache_key, value, ttl)
                logger.info(f"Warmed cache with {len(data)} items for prefix {prefix}")
            else:
                logger.warning(f"Cache warming data is not a dict for prefix {prefix}")
        except Exception as e:
            logger.error(f"Error warming cache for prefix {prefix}: {e}")

    # Cache Invalidation
    async def invalidate_user_cache(self, user_id: str) -> None:
        """Invalidate user-related cache."""
        await self.cache_manager.invalidate_pattern(f"user:{user_id}:*")
        logger.debug(f"Invalidated cache for user {user_id}")

    async def invalidate_workflow_cache(self, workflow_id: str) -> None:
        """Invalidate workflow-related cache."""
        await self.cache_manager.invalidate_pattern(f"workflow:{workflow_id}:*")
        logger.debug(f"Invalidated cache for workflow {workflow_id}")

    async def invalidate_agent_cache(self, agent_id: str) -> None:
        """Invalidate agent-related cache."""
        await self.cache_manager.invalidate_pattern(f"agent:{agent_id}:*")
        logger.debug(f"Invalidated cache for agent {agent_id}")

    async def invalidate_memory_cache(self, memory_id: str) -> None:
        """Invalidate memory-related cache."""
        await self.cache_manager.invalidate_pattern(f"memory:{memory_id}:*")
        logger.debug(f"Invalidated cache for memory {memory_id}")

    async def invalidate_tool_cache(self, tool_name: str) -> None:
        """Invalidate tool-related cache."""
        await self.cache_manager.invalidate_pattern(f"tool:{tool_name}:*")
        logger.debug(f"Invalidated cache for tool {tool_name}")


def cached_query(ttl: int = 3600, prefix: str = "query"):
    """
    Decorator for caching async database query results.

    Args:
        ttl: Time to live in seconds
        prefix: Cache key prefix
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get cache integration from first argument (self)
            if not args or not hasattr(args[0], "_cache_integration"):
                return await func(*args, **kwargs)

            cache_integration = args[0]._cache_integration
            if cache_integration is None:
                return await func(*args, **kwargs)

            # Generate cache key
            key_parts = [prefix]
            key_parts.extend(str(arg) for arg in args[1:])
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            key_str = "|".join(key_parts)
            cache_key = hashlib.md5(key_str.encode()).hexdigest()

            # Try to get from cache
            cached_value = await cache_integration.cache_get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for {func.__name__}: {cache_key}")
                return cached_value

            # Call function and cache result
            result = await func(*args, **kwargs)
            await cache_integration.cache_set(cache_key, result, ttl)
            logger.debug(f"Cached result for {func.__name__}: {cache_key}")
            return result

        return wrapper

    return decorator


def cache_invalidate_on_write(invalidation_patterns: list[str]):
    """
    Decorator for invalidating cache on write operations.

    Args:
        invalidation_patterns: List of cache key patterns to invalidate
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Call the function
            result = await func(*args, **kwargs)

            # Invalidate cache patterns
            if args and hasattr(args[0], "_cache_integration"):
                cache_integration = args[0]._cache_integration
                if cache_integration is not None:
                    for pattern in invalidation_patterns:
                        await cache_integration.cache_invalidate_pattern(pattern)
                    logger.debug(f"Invalidated cache patterns: {invalidation_patterns}")

            return result

        return wrapper

    return decorator


# Global cache integration instance
_cache_integration: CacheIntegration | None = None


def get_cache_integration() -> CacheIntegration:
    """Get or create the global cache integration."""
    global _cache_integration
    if _cache_integration is None:
        _cache_integration = CacheIntegration()
    return _cache_integration
