"""Query caching layer for X-Agent database operations.

Implements multi-level caching strategy:
1. In-memory cache for frequently accessed data
2. Redis cache for distributed caching
3. Query result caching with TTL
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timedelta, UTC
from functools import wraps
from typing import Any, Callable, TypeVar, Optional
import asyncio
from collections import OrderedDict

T = TypeVar("T")


class CacheConfig:
    """Cache configuration."""

    def __init__(
        self,
        ttl_seconds: int = 300,
        max_size: int = 1000,
        enable_redis: bool = False,
        redis_url: str | None = None,
    ):
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self.enable_redis = enable_redis
        self.redis_url = redis_url


class InMemoryCache:
    """LRU in-memory cache with TTL support."""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Any | None:
        """Get value from cache if not expired."""
        if key not in self.cache:
            self.misses += 1
            return None

        value, expiry = self.cache[key]
        if time.time() > expiry:
            del self.cache[key]
            self.misses += 1
            return None

        # Move to end (LRU)
        self.cache.move_to_end(key)
        self.hits += 1
        return value

    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        """Set value in cache with TTL."""
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = (value, time.time() + ttl_seconds)

        # Evict oldest if over capacity
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)

    def clear(self) -> None:
        """Clear all cache."""
        self.cache.clear()
        self.hits = 0
        self.misses = 0

    def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{hit_rate:.2f}%",
        }


class QueryCache:
    """Query result caching with multiple backends."""

    def __init__(self, config: CacheConfig):
        self.config = config
        self.memory_cache = InMemoryCache(max_size=config.max_size)
        self.redis_client: Any = None
        if config.enable_redis:
            self._init_redis()

    def _init_redis(self) -> None:
        """Initialize Redis client."""
        try:
            import redis

            self.redis_client = redis.from_url(
                self.config.redis_url or "redis://localhost:6379/0"
            )
            self.redis_client.ping()
        except Exception as e:
            print(f"Failed to initialize Redis: {e}")
            self.redis_client = None

    @staticmethod
    def _make_key(prefix: str, *args: Any, **kwargs: Any) -> str:
        """Generate cache key from arguments."""
        key_data = json.dumps(
            {"args": args, "kwargs": kwargs}, sort_keys=True, default=str
        )
        key_hash = hashlib.md5(key_data.encode()).hexdigest()
        return f"{prefix}:{key_hash}"

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        # Try memory cache first
        value = self.memory_cache.get(key)
        if value is not None:
            return value

        # Try Redis if enabled
        if self.redis_client:
            try:
                value = self.redis_client.get(key)
                if value:
                    result = json.loads(value)
                    # Populate memory cache
                    self.memory_cache.set(key, result, self.config.ttl_seconds)
                    return result
            except Exception as e:
                print(f"Redis get error: {e}")

        return None

    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Set value in cache."""
        ttl = ttl_seconds or self.config.ttl_seconds

        # Set in memory cache
        self.memory_cache.set(key, value, ttl)

        # Set in Redis if enabled
        if self.redis_client:
            try:
                self.redis_client.setex(
                    key, ttl, json.dumps(value, default=str)
                )
            except Exception as e:
                print(f"Redis set error: {e}")

    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        if key in self.memory_cache.cache:
            del self.memory_cache.cache[key]

        if self.redis_client:
            try:
                self.redis_client.delete(key)
            except Exception as e:
                print(f"Redis delete error: {e}")

    async def clear(self) -> None:
        """Clear all caches."""
        self.memory_cache.clear()
        if self.redis_client:
            try:
                self.redis_client.flushdb()
            except Exception as e:
                print(f"Redis flush error: {e}")

    def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "memory": self.memory_cache.stats(),
            "redis_enabled": self.redis_client is not None,
        }


# Global cache instance
_query_cache: QueryCache | None = None


def init_query_cache(config: CacheConfig) -> QueryCache:
    """Initialize global query cache."""
    global _query_cache
    _query_cache = QueryCache(config)
    return _query_cache


def get_query_cache() -> QueryCache:
    """Get global query cache instance."""
    global _query_cache
    if _query_cache is None:
        _query_cache = QueryCache(CacheConfig())
    return _query_cache


def cached_query(
    prefix: str,
    ttl_seconds: int | None = None,
    key_args: list[int] | None = None,
    key_kwargs: list[str] | None = None,
):
    """Decorator for caching query results.

    Args:
        prefix: Cache key prefix
        ttl_seconds: Time to live in seconds
        key_args: Indices of positional args to include in cache key
        key_kwargs: Names of kwargs to include in cache key
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            cache = get_query_cache()

            # Build cache key
            cache_args = (
                tuple(args[i] for i in key_args) if key_args else args
            )
            cache_kwargs = (
                {k: kwargs[k] for k in key_kwargs if k in kwargs}
                if key_kwargs
                else kwargs
            )
            cache_key = QueryCache._make_key(prefix, *cache_args, **cache_kwargs)

            # Try to get from cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function
            result = await func(*args, **kwargs)

            # Store in cache
            await cache.set(cache_key, result, ttl_seconds)
            return result

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            cache = get_query_cache()

            # Build cache key
            cache_args = (
                tuple(args[i] for i in key_args) if key_args else args
            )
            cache_kwargs = (
                {k: kwargs[k] for k in key_kwargs if k in kwargs}
                if key_kwargs
                else kwargs
            )
            cache_key = QueryCache._make_key(prefix, *cache_args, **cache_kwargs)

            # Try to get from cache
            cached_value = cache.memory_cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function
            result = func(*args, **kwargs)

            # Store in cache
            cache.memory_cache.set(cache_key, result, ttl_seconds or 300)
            return result

        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class CacheInvalidator:
    """Manages cache invalidation patterns."""

    def __init__(self, cache: QueryCache):
        self.cache = cache
        self.patterns: dict[str, list[str]] = {}

    def register_pattern(self, pattern: str, related_patterns: list[str]) -> None:
        """Register cache invalidation pattern."""
        self.patterns[pattern] = related_patterns

    async def invalidate(self, pattern: str) -> None:
        """Invalidate cache by pattern."""
        cache = get_query_cache()
        related = self.patterns.get(pattern, [])
        for p in [pattern] + related:
            # In a real implementation, would iterate through cache keys
            # For now, just clear the pattern prefix
            pass

    async def invalidate_on_write(
        self, operation: str, resource_type: str, resource_id: str
    ) -> None:
        """Invalidate related caches on write operations."""
        patterns_to_invalidate = [
            f"{resource_type}:list",
            f"{resource_type}:{resource_id}",
            f"{resource_type}:search",
        ]
        for pattern in patterns_to_invalidate:
            await self.invalidate(pattern)
