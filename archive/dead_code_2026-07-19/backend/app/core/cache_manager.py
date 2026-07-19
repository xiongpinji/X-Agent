"""Cache management system for X-Agent.

Implements multi-level caching strategy:
- Local in-memory cache for hot data
- Redis distributed cache for shared data
- TTL-based expiration
- Cache invalidation strategies
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, UTC
from typing import Any, Callable, TypeVar, Generic, Optional
from abc import ABC, abstractmethod

import redis.asyncio as redis

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheBackend(ABC, Generic[T]):
    """Abstract base class for cache backends."""

    @abstractmethod
    async def get(self, key: str) -> T | None:
        """Get value from cache."""
        pass

    @abstractmethod
    async def set(self, key: str, value: T, ttl: int | None = None) -> None:
        """Set value in cache."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cache entries."""
        pass


class LocalMemoryCache(CacheBackend[T]):
    """In-memory cache for local data."""

    def __init__(self, max_size: int = 1000):
        """Initialize local memory cache.

        Args:
            max_size: Maximum number of entries
        """
        self.max_size = max_size
        self._cache: dict[str, tuple[T, datetime | None]] = {}
        self._access_times: dict[str, datetime] = {}

    async def get(self, key: str) -> T | None:
        """Get value from cache."""
        if key not in self._cache:
            return None

        value, expiry = self._cache[key]

        # Check expiration
        if expiry and datetime.now(UTC) > expiry:
            del self._cache[key]
            if key in self._access_times:
                del self._access_times[key]
            return None

        # Update access time for LRU
        self._access_times[key] = datetime.now(UTC)
        return value

    async def set(self, key: str, value: T, ttl: int | None = None) -> None:
        """Set value in cache."""
        # Evict LRU entry if cache is full
        if len(self._cache) >= self.max_size and key not in self._cache:
            lru_key = min(self._access_times.keys(), key=lambda k: self._access_times[k])
            del self._cache[lru_key]
            del self._access_times[lru_key]

        expiry = datetime.now(UTC) + timedelta(seconds=ttl) if ttl else None
        self._cache[key] = (value, expiry)
        self._access_times[key] = datetime.now(UTC)

    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        if key in self._cache:
            del self._cache[key]
        if key in self._access_times:
            del self._access_times[key]

    async def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._access_times.clear()

    def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "utilization": len(self._cache) / self.max_size,
        }


class RedisCache(CacheBackend[T]):
    """Redis-backed distributed cache."""

    def __init__(self, redis_client: redis.Redis):
        """Initialize Redis cache.

        Args:
            redis_client: Redis async client
        """
        self.redis_client = redis_client

    async def get(self, key: str) -> T | None:
        """Get value from cache."""
        try:
            value = await self.redis_client.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.error(f"Redis get error: {e}")
        return None

    async def set(self, key: str, value: T, ttl: int | None = None) -> None:
        """Set value in cache."""
        try:
            serialized = json.dumps(value, default=str)
            if ttl:
                await self.redis_client.setex(key, ttl, serialized)
            else:
                await self.redis_client.set(key, serialized)
        except Exception as e:
            logger.error(f"Redis set error: {e}")

    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        try:
            await self.redis_client.delete(key)
        except Exception as e:
            logger.error(f"Redis delete error: {e}")

    async def clear(self) -> None:
        """Clear all cache entries."""
        try:
            await self.redis_client.flushdb()
        except Exception as e:
            logger.error(f"Redis clear error: {e}")

    async def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        try:
            info = await self.redis_client.info()
            return {
                "used_memory": info.get("used_memory", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "connected_clients": info.get("connected_clients", 0),
            }
        except Exception as e:
            logger.error(f"Redis stats error: {e}")
            return {}


class CacheManager:
    """Multi-level cache manager combining local and distributed caches."""

    def __init__(
        self,
        redis_client: redis.Redis | None = None,
        local_cache_size: int = 1000,
        default_ttl: int = 300,
    ):
        """Initialize cache manager.

        Args:
            redis_client: Optional Redis client for distributed caching
            local_cache_size: Size of local memory cache
            default_ttl: Default TTL in seconds
        """
        self.local_cache: LocalMemoryCache[Any] = LocalMemoryCache(max_size=local_cache_size)
        self.redis_cache: RedisCache[Any] | None = (
            RedisCache(redis_client) if redis_client else None
        )
        self.default_ttl = default_ttl

    async def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], Any],
        ttl: int | None = None,
    ) -> Any:
        """Get value from cache or compute if missing.

        Implements two-level cache strategy:
        1. Check local memory cache
        2. Check Redis cache
        3. Compute and cache result

        Args:
            key: Cache key
            compute_fn: Async function to compute value if not cached
            ttl: Time-to-live in seconds

        Returns:
            Cached or computed value
        """
        ttl = ttl or self.default_ttl

        # 1. Check local cache
        local_value = await self.local_cache.get(key)
        if local_value is not None:
            logger.debug(f"Cache hit (local): {key}")
            return local_value

        # 2. Check Redis cache
        if self.redis_cache:
            redis_value = await self.redis_cache.get(key)
            if redis_value is not None:
                logger.debug(f"Cache hit (redis): {key}")
                # Populate local cache
                await self.local_cache.set(key, redis_value, ttl)
                return redis_value

        # 3. Compute value
        logger.debug(f"Cache miss: {key}, computing...")
        if asyncio.iscoroutinefunction(compute_fn):
            value = await compute_fn()
        else:
            value = compute_fn()

        # Cache result
        await self.local_cache.set(key, value, ttl)
        if self.redis_cache:
            await self.redis_cache.set(key, value, ttl)

        return value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds
        """
        ttl = ttl or self.default_ttl
        await self.local_cache.set(key, value, ttl)
        if self.redis_cache:
            await self.redis_cache.set(key, value, ttl)

    async def get(self, key: str) -> Any | None:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        # Check local cache first
        local_value = await self.local_cache.get(key)
        if local_value is not None:
            return local_value

        # Check Redis cache
        if self.redis_cache:
            redis_value = await self.redis_cache.get(key)
            if redis_value is not None:
                # Populate local cache
                await self.local_cache.set(key, redis_value, self.default_ttl)
                return redis_value

        return None

    async def delete(self, key: str) -> None:
        """Delete value from cache.

        Args:
            key: Cache key
        """
        await self.local_cache.delete(key)
        if self.redis_cache:
            await self.redis_cache.delete(key)

    async def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate cache entries matching pattern.

        Args:
            pattern: Pattern to match keys
        """
        # Local cache invalidation
        keys_to_delete = [k for k in self.local_cache._cache.keys() if pattern in k]
        for key in keys_to_delete:
            await self.local_cache.delete(key)

        # Redis cache invalidation
        if self.redis_cache:
            try:
                cursor = 0
                while True:
                    cursor, keys = await self.redis_cache.redis_client.scan(
                        cursor, match=f"*{pattern}*"
                    )
                    for key in keys:
                        await self.redis_cache.delete(key.decode() if isinstance(key, bytes) else key)
                    if cursor == 0:
                        break
            except Exception as e:
                logger.error(f"Pattern invalidation error: {e}")

    async def clear(self) -> None:
        """Clear all cache entries."""
        await self.local_cache.clear()
        if self.redis_cache:
            await self.redis_cache.clear()

    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Cache statistics
        """
        stats = {
            "local": self.local_cache.stats(),
        }

        if self.redis_cache:
            # Note: stats() is async for Redis, so we return a placeholder
            stats["redis"] = "Use async stats() method for Redis stats"

        return stats


class CacheDecorator:
    """Decorator for caching function results."""

    def __init__(self, cache_manager: CacheManager, ttl: int | None = None):
        """Initialize cache decorator.

        Args:
            cache_manager: Cache manager instance
            ttl: Time-to-live in seconds
        """
        self.cache_manager = cache_manager
        self.ttl = ttl

    def __call__(self, func: Callable) -> Callable:
        """Decorate function with caching.

        Args:
            func: Function to decorate

        Returns:
            Decorated function
        """
        async def wrapper(*args, **kwargs) -> Any:
            # Generate cache key from function name and arguments
            cache_key = f"{func.__name__}:{json.dumps([args, kwargs], default=str)}"

            # Try to get from cache
            cached = await self.cache_manager.get(cache_key)
            if cached is not None:
                return cached

            # Compute and cache
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            await self.cache_manager.set(cache_key, result, self.ttl)
            return result

        return wrapper
