"""
Multi-layer caching system for X-Agent.

Implements:
- In-memory LRU cache for frequently accessed data
- Redis cache for distributed deployments
- Cache invalidation strategies (TTL, active invalidation)
- Cache warming
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from functools import wraps
from typing import Any, Generic, TypeVar

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
        """Clear all cache."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        pass


class MemoryCacheBackend(CacheBackend[T]):
    """In-memory LRU cache backend."""

    def __init__(self, max_size: int = 1000) -> None:
        self._cache: dict[str, tuple[T, float | None]] = {}
        self._access_times: dict[str, float] = {}
        self._max_size = max_size
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> T | None:
        """Get value from cache."""
        async with self._lock:
            if key not in self._cache:
                return None

            value, expiry = self._cache[key]

            # Check if expired
            if expiry is not None and time.time() > expiry:
                del self._cache[key]
                del self._access_times[key]
                return None

            # Update access time for LRU
            self._access_times[key] = time.time()
            return value

    async def set(self, key: str, value: T, ttl: int | None = None) -> None:
        """Set value in cache."""
        async with self._lock:
            # Evict LRU item if cache is full
            if len(self._cache) >= self._max_size and key not in self._cache:
                lru_key = min(self._access_times, key=self._access_times.get)
                del self._cache[lru_key]
                del self._access_times[lru_key]

            expiry = time.time() + ttl if ttl else None
            self._cache[key] = (value, expiry)
            self._access_times[key] = time.time()

    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        async with self._lock:
            self._cache.pop(key, None)
            self._access_times.pop(key, None)

    async def clear(self) -> None:
        """Clear all cache."""
        async with self._lock:
            self._cache.clear()
            self._access_times.clear()

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        async with self._lock:
            if key not in self._cache:
                return False
            _value, expiry = self._cache[key]
            if expiry is not None and time.time() > expiry:
                del self._cache[key]
                del self._access_times[key]
                return False
            return True


class RedisCacheBackend(CacheBackend[T]):
    """Redis cache backend for distributed deployments."""

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._redis = None
        self._initialized = False

    async def _ensure_connected(self) -> None:
        """Ensure Redis connection is established."""
        if self._initialized:
            return

        try:
            import aioredis

            self._redis = await aioredis.from_url(self._redis_url, decode_responses=True)
            self._initialized = True
            logger.info("Redis cache backend initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Redis cache: {e}")
            self._redis = None

    async def get(self, key: str) -> T | None:
        """Get value from cache."""
        await self._ensure_connected()
        if self._redis is None:
            return None

        try:
            value = await self._redis.get(key)
            if value is None:
                return None
            return json.loads(value)
        except Exception as e:
            logger.error(f"Error getting from Redis cache: {e}")
            return None

    async def set(self, key: str, value: T, ttl: int | None = None) -> None:
        """Set value in cache."""
        await self._ensure_connected()
        if self._redis is None:
            return

        try:
            serialized = json.dumps(value)
            if ttl:
                await self._redis.setex(key, ttl, serialized)
            else:
                await self._redis.set(key, serialized)
        except Exception as e:
            logger.error(f"Error setting Redis cache: {e}")

    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        await self._ensure_connected()
        if self._redis is None:
            return

        try:
            await self._redis.delete(key)
        except Exception as e:
            logger.error(f"Error deleting from Redis cache: {e}")

    async def clear(self) -> None:
        """Clear all cache."""
        await self._ensure_connected()
        if self._redis is None:
            return

        try:
            await self._redis.flushdb()
        except Exception as e:
            logger.error(f"Error clearing Redis cache: {e}")

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        await self._ensure_connected()
        if self._redis is None:
            return False

        try:
            return await self._redis.exists(key) > 0
        except Exception as e:
            logger.error(f"Error checking Redis cache: {e}")
            return False


class CacheManager:
    """
    Multi-layer cache manager.

    Implements:
    - L1: In-memory cache (fast, local)
    - L2: Redis cache (distributed, persistent)
    - Cache invalidation strategies
    - Cache warming
    """

    def __init__(self, redis_url: str | None = None, memory_cache_size: int = 1000) -> None:
        self._l1_cache = MemoryCacheBackend(max_size=memory_cache_size)
        self._l2_cache = RedisCacheBackend(redis_url) if redis_url else None
        self._invalidation_callbacks: dict[str, list[Callable]] = {}

    async def get(self, key: str) -> Any | None:
        """Get value from cache (L1 -> L2)."""
        # Try L1 cache first
        value = await self._l1_cache.get(key)
        if value is not None:
            logger.debug(f"Cache hit (L1): {key}")
            return value

        # Try L2 cache
        if self._l2_cache:
            value = await self._l2_cache.get(key)
            if value is not None:
                logger.debug(f"Cache hit (L2): {key}")
                # Populate L1 cache
                await self._l1_cache.set(key, value)
                return value

        logger.debug(f"Cache miss: {key}")
        return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value in cache (L1 + L2)."""
        await self._l1_cache.set(key, value, ttl)
        if self._l2_cache:
            await self._l2_cache.set(key, value, ttl)
        logger.debug(f"Cache set: {key} (ttl={ttl})")

    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        await self._l1_cache.delete(key)
        if self._l2_cache:
            await self._l2_cache.delete(key)
        logger.debug(f"Cache deleted: {key}")

    async def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate all keys matching a pattern."""
        # For now, just clear all cache
        # In production, implement pattern-based invalidation
        await self._l1_cache.clear()
        if self._l2_cache:
            await self._l2_cache.clear()
        logger.debug(f"Cache invalidated (pattern: {pattern})")

    def register_invalidation_callback(self, pattern: str, callback: Callable) -> None:
        """Register a callback for cache invalidation."""
        if pattern not in self._invalidation_callbacks:
            self._invalidation_callbacks[pattern] = []
        self._invalidation_callbacks[pattern].append(callback)

    async def trigger_invalidation(self, pattern: str) -> None:
        """Trigger invalidation callbacks for a pattern."""
        callbacks = self._invalidation_callbacks.get(pattern, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                logger.error(f"Error in invalidation callback: {e}")


def cache_key(*args: Any, **kwargs: Any) -> str:
    """Generate a cache key from function arguments."""
    key_parts = [str(arg) for arg in args]
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    key_str = "|".join(key_parts)
    return hashlib.md5(key_str.encode()).hexdigest()


def cached(ttl_seconds: int | None = None, key_prefix: str | None = None):
    """
    Decorator for caching *synchronous* function results in-process.

    Uses a per-wrapper in-memory dict with optional TTL. Suitable for
    standalone functions called synchronously (no event loop required).

    Args:
        ttl_seconds: Time to live in seconds (None = never expires)
        key_prefix: Optional prefix for the cache key namespace
    """

    def decorator(func: Callable) -> Callable:
        _local_cache: dict[str, tuple[Any, float]] = {}

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            prefix = key_prefix or func.__module__
            key = f"{prefix}:{func.__name__}:{cache_key(*args, **kwargs)}"
            now = time.time()

            if key in _local_cache:
                value, expires_at = _local_cache[key]
                if ttl_seconds is None or now < expires_at:
                    return value
                del _local_cache[key]

            result = func(*args, **kwargs)
            expires_at = now + ttl_seconds if ttl_seconds is not None else float("inf")
            _local_cache[key] = (result, expires_at)
            return result

        return wrapper

    return decorator


def async_cached(ttl_seconds: int | None = None, key_prefix: str | None = None):
    """
    Decorator for caching *async* function results via the global cache manager.

    Args:
        ttl_seconds: Time to live in seconds
        key_prefix: Optional prefix for the cache key namespace
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache_manager = get_cache_manager()
            prefix = key_prefix or func.__module__
            key = f"{prefix}:{func.__name__}:{cache_key(*args, **kwargs)}"

            cached_value = await cache_manager.get(key)
            if cached_value is not None:
                return cached_value

            result = await func(*args, **kwargs)
            await cache_manager.set(key, result, ttl_seconds)
            return result

        return wrapper

    return decorator


# Global cache manager instance
_cache_manager: CacheManager | None = None


def get_cache_manager(redis_url: str | None = None) -> CacheManager:
    """Get or create the global cache manager."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager(redis_url=redis_url)
    return _cache_manager


class CacheStats:
    """Track cache performance metrics."""

    def __init__(self) -> None:
        self.hits: int = 0
        self.misses: int = 0
        self.errors: int = 0
        self.start_time: float = time.time()

    def record_hit(self) -> None:
        self.hits += 1

    def record_miss(self) -> None:
        self.misses += 1

    def record_error(self) -> None:
        self.errors += 1

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.start_time

    def to_dict(self) -> dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "errors": self.errors,
            "hit_rate": self.hit_rate,
            "uptime_seconds": self.uptime_seconds,
        }


# Add statistics tracking to CacheManager
_cache_stats = CacheStats()


def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics."""
    return _cache_stats.to_dict()


def record_cache_hit() -> None:
    """Record a cache hit."""
    _cache_stats.record_hit()


def record_cache_miss() -> None:
    """Record a cache miss."""
    _cache_stats.record_miss()


def record_cache_error() -> None:
    """Record a cache error."""
    _cache_stats.record_error()
