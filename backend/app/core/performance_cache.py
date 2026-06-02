"""Multi-layer caching system for X-Agent performance optimization.

Implements L1 (in-memory) and L2 (Redis) caching with automatic invalidation,
TTL management, and cache warming strategies.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Generic, TypeVar

import redis.asyncio as redis
from pydantic import BaseModel

logger = logging.getLogger("xagent.cache")

T = TypeVar("T")


class CacheEntry(BaseModel):
    """Cache entry with metadata."""

    key: str
    value: Any
    ttl_seconds: int
    created_at: datetime
    accessed_at: datetime
    hit_count: int = 0


class CacheStats(BaseModel):
    """Cache performance statistics."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    avg_hit_latency_ms: float = 0.0
    avg_miss_latency_ms: float = 0.0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class CacheBackend(ABC, Generic[T]):
    """Abstract cache backend."""

    @abstractmethod
    async def get(self, key: str) -> T | None:
        """Get value from cache."""
        pass

    @abstractmethod
    async def set(self, key: str, value: T, ttl_seconds: int = 3600) -> None:
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

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        pass


class MemoryCacheBackend(CacheBackend[T]):
    """In-memory cache backend with LRU eviction."""

    def __init__(self, max_size: int = 10000, default_ttl: int = 3600):
        self._cache: dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._stats = CacheStats()
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> T | None:
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._stats.misses += 1
                return None

            # Check TTL
            if datetime.now(UTC) > entry.created_at + timedelta(seconds=entry.ttl_seconds):
                del self._cache[key]
                self._stats.misses += 1
                return None

            # Update access metadata
            entry.accessed_at = datetime.now(UTC)
            entry.hit_count += 1
            self._stats.hits += 1
            return entry.value

    async def set(self, key: str, value: T, ttl_seconds: int | None = None) -> None:
        async with self._lock:
            ttl = ttl_seconds or self._default_ttl

            # Evict LRU entry if cache is full
            if len(self._cache) >= self._max_size and key not in self._cache:
                lru_key = min(
                    self._cache.keys(),
                    key=lambda k: self._cache[k].accessed_at,
                )
                del self._cache[lru_key]
                self._stats.evictions += 1

            self._cache[key] = CacheEntry(
                key=key,
                value=value,
                ttl_seconds=ttl,
                created_at=datetime.now(UTC),
                accessed_at=datetime.now(UTC),
            )

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._cache.pop(key, None)

    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()

    async def exists(self, key: str) -> bool:
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if datetime.now(UTC) > entry.created_at + timedelta(seconds=entry.ttl_seconds):
                del self._cache[key]
                return False
            return True

    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats.model_copy()


class RedisCacheBackend(CacheBackend[T]):
    """Redis-backed distributed cache."""

    def __init__(self, redis_url: str = "redis://localhost:6379", default_ttl: int = 3600):
        self._redis_url = redis_url
        self._redis: redis.Redis | None = None
        self._default_ttl = default_ttl
        self._stats = CacheStats()

    async def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = await redis.from_url(self._redis_url, decode_responses=True)
        return self._redis

    async def get(self, key: str) -> T | None:
        try:
            redis_client = await self._get_redis()
            value = await redis_client.get(key)
            if value is None:
                self._stats.misses += 1
                return None
            self._stats.hits += 1
            return json.loads(value)
        except Exception as e:
            logger.warning(f"Redis get error for key {key}: {e}")
            self._stats.misses += 1
            return None

    async def set(self, key: str, value: T, ttl_seconds: int | None = None) -> None:
        try:
            redis_client = await self._get_redis()
            ttl = ttl_seconds or self._default_ttl
            await redis_client.setex(key, ttl, json.dumps(value))
        except Exception as e:
            logger.warning(f"Redis set error for key {key}: {e}")

    async def delete(self, key: str) -> None:
        try:
            redis_client = await self._get_redis()
            await redis_client.delete(key)
        except Exception as e:
            logger.warning(f"Redis delete error for key {key}: {e}")

    async def clear(self) -> None:
        try:
            redis_client = await self._get_redis()
            await redis_client.flushdb()
        except Exception as e:
            logger.warning(f"Redis clear error: {e}")

    async def exists(self, key: str) -> bool:
        try:
            redis_client = await self._get_redis()
            return await redis_client.exists(key) > 0
        except Exception as e:
            logger.warning(f"Redis exists error for key {key}: {e}")
            return False

    async def close(self) -> None:
        if self._redis:
            await self._redis.close()

    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats.model_copy()


class MultiLayerCache:
    """Multi-layer cache with L1 (memory) and L2 (Redis) backends."""

    def __init__(
        self,
        l1_backend: MemoryCacheBackend | None = None,
        l2_backend: RedisCacheBackend | None = None,
        enable_l2: bool = False,
    ):
        self._l1 = l1_backend or MemoryCacheBackend()
        self._l2 = l2_backend if enable_l2 else None
        self._enable_l2 = enable_l2

    async def get(self, key: str) -> Any | None:
        """Get value from cache (L1 first, then L2)."""
        # Try L1 first
        value = await self._l1.get(key)
        if value is not None:
            return value

        # Try L2 if enabled
        if self._enable_l2 and self._l2:
            value = await self._l2.get(key)
            if value is not None:
                # Populate L1 for future hits
                await self._l1.set(key, value)
                return value

        return None

    async def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        """Set value in cache (both L1 and L2)."""
        await self._l1.set(key, value, ttl_seconds)
        if self._enable_l2 and self._l2:
            await self._l2.set(key, value, ttl_seconds)

    async def delete(self, key: str) -> None:
        """Delete value from cache (both L1 and L2)."""
        await self._l1.delete(key)
        if self._enable_l2 and self._l2:
            await self._l2.delete(key)

    async def clear(self) -> None:
        """Clear all cache entries."""
        await self._l1.clear()
        if self._enable_l2 and self._l2:
            await self._l2.clear()

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if await self._l1.exists(key):
            return True
        if self._enable_l2 and self._l2:
            return await self._l2.exists(key)
        return False

    def get_cache_key(self, prefix: str, *args: Any, **kwargs: Any) -> str:
        """Generate cache key from prefix and arguments."""
        key_parts = [prefix]
        for arg in args:
            key_parts.append(str(arg))
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
        key_str = ":".join(key_parts)
        return hashlib.md5(key_str.encode()).hexdigest()

    def get_stats(self) -> dict[str, CacheStats]:
        """Get cache statistics."""
        stats = {"l1": self._l1.get_stats()}
        if self._enable_l2 and self._l2:
            stats["l2"] = self._l2.get_stats()
        return stats


def cached(
    cache: MultiLayerCache,
    ttl_seconds: int = 3600,
    key_prefix: str = "",
) -> Callable:
    """Decorator for caching async function results."""

    def decorator(func: Callable) -> Callable:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Generate cache key
            cache_key = cache.get_cache_key(key_prefix or func.__name__, *args, **kwargs)

            # Try to get from cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Call function and cache result
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl_seconds)
            return result

        return wrapper

    return decorator
