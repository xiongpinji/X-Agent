"""Unified Redis client with connection pooling for X-Agent.

Provides a singleton async Redis client that gracefully degrades to
in-memory storage when Redis is unavailable (development mode).

Usage:
    from backend.app.core.redis_client import get_redis, RedisNotAvailable

    redis = get_redis()
    if redis.is_available:
        await redis.setex("key", 3600, "value")
        value = await redis.get("key")
    else:
        # Fallback to in-memory
        ...
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from threading import Lock
from typing import Any

logger = logging.getLogger("xagent.redis")


class RedisNotAvailable(Exception):
    """Raised when Redis operations are attempted but Redis is not connected."""


class InMemoryFallback:
    """In-memory fallback storage that mimics Redis API for development.

    Thread-safe with TTL support. Used when Redis is not configured or unavailable.
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float | None]] = {}  # key -> (value, expiry_ts)
        self._lock = Lock()

    def _is_expired(self, key: str) -> bool:
        if key not in self._store:
            return True
        _, expiry = self._store[key]
        if expiry is not None and time.time() > expiry:
            del self._store[key]
            return True
        return False

    async def get(self, key: str) -> str | None:
        with self._lock:
            if self._is_expired(key):
                return None
            return self._store[key][0]

    async def set(self, key: str, value: str) -> None:
        with self._lock:
            self._store[key] = (value, None)

    async def setex(self, key: str, ttl_seconds: int, value: str) -> None:
        with self._lock:
            self._store[key] = (value, time.time() + ttl_seconds)

    async def delete(self, *keys: str) -> int:
        count = 0
        with self._lock:
            for key in keys:
                if key in self._store:
                    del self._store[key]
                    count += 1
        return count

    async def exists(self, key: str) -> bool:
        with self._lock:
            return not self._is_expired(key)

    async def incr(self, key: str) -> int:
        with self._lock:
            if self._is_expired(key):
                self._store[key] = ("1", None)
                return 1
            current = int(self._store[key][0])
            new_val = current + 1
            self._store[key] = (str(new_val), self._store[key][1])
            return new_val

    async def expire(self, key: str, ttl_seconds: int) -> bool:
        with self._lock:
            if key in self._store:
                value, _ = self._store[key]
                self._store[key] = (value, time.time() + ttl_seconds)
                return True
            return False

    async def ttl(self, key: str) -> int:
        with self._lock:
            if key not in self._store:
                return -2
            _, expiry = self._store[key]
            if expiry is None:
                return -1
            remaining = int(expiry - time.time())
            return max(0, remaining)

    async def keys(self, pattern: str) -> list[str]:
        """Return keys matching pattern (simple glob support)."""
        import fnmatch
        with self._lock:
            # Clean expired first (iterate over a snapshot to avoid mutation during iteration)
            expired = [k for k in list(self._store.keys()) if self._is_expired(k)]
            for k in expired:
                self._store.pop(k, None)
            return [k for k in self._store if fnmatch.fnmatch(k, pattern)]

    async def zadd(self, key: str, mapping: dict[str, float]) -> int:
        """Sorted set add (simplified for rate limiting)."""
        with self._lock:
            if key not in self._store:
                self._store[key] = ("{}", None)
            import json
            try:
                data = json.loads(self._store[key][0])
            except (json.JSONDecodeError, TypeError):
                data = {}
            data.update(mapping)
            self._store[key] = (json.dumps(data), self._store[key][1])
            return len(mapping)

    async def zremrangebyscore(self, key: str, min_score: float, max_score: float) -> int:
        """Remove sorted set members by score range."""
        with self._lock:
            if key not in self._store:
                return 0
            import json
            try:
                data = json.loads(self._store[key][0])
            except (json.JSONDecodeError, TypeError):
                return 0
            to_remove = [k for k, v in data.items() if min_score <= v <= max_score]
            for k in to_remove:
                del data[k]
            self._store[key] = (json.dumps(data), self._store[key][1])
            return len(to_remove)

    async def zcard(self, key: str) -> int:
        """Count sorted set members."""
        with self._lock:
            if key not in self._store:
                return 0
            import json
            try:
                data = json.loads(self._store[key][0])
                return len(data)
            except (json.JSONDecodeError, TypeError):
                return 0

    def pipeline(self) -> InMemoryPipeline:
        return InMemoryPipeline(self)

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        pass


class InMemoryPipeline:
    """Pipeline for in-memory fallback (executes immediately)."""

    def __init__(self, store: InMemoryFallback) -> None:
        self._store = store
        self._commands: list[tuple[str, tuple]] = []

    def zadd(self, key: str, mapping: dict[str, float]) -> InMemoryPipeline:
        self._commands.append(("zadd", (key, mapping)))
        return self

    def zremrangebyscore(self, key: str, min_score: float, max_score: float) -> InMemoryPipeline:
        self._commands.append(("zremrangebyscore", (key, min_score, max_score)))
        return self

    def zcard(self, key: str) -> InMemoryPipeline:
        self._commands.append(("zcard", (key,)))
        return self

    def expire(self, key: str, ttl_seconds: int) -> InMemoryPipeline:
        self._commands.append(("expire", (key, ttl_seconds)))
        return self

    async def execute(self) -> list[Any]:
        results = []
        for cmd, args in self._commands:
            method = getattr(self._store, cmd)
            results.append(await method(*args))
        self._commands.clear()
        return results

    async def __aenter__(self) -> InMemoryPipeline:
        return self

    async def __aexit__(self, *args) -> None:
        pass


class RedisClient:
    """Unified Redis client with automatic fallback to in-memory storage.

    Provides a consistent async interface whether Redis is available or not.
    All operations are async and thread-safe.
    """

    def __init__(self) -> None:
        self._redis: Any = None
        self._fallback = InMemoryFallback()
        self._available = False
        self._initialized = False
        self._lock = asyncio.Lock()

    @property
    def is_available(self) -> bool:
        """Whether real Redis is connected (vs in-memory fallback)."""
        return self._available

    async def initialize(self, redis_url: str | None = None) -> None:
        """Initialize Redis connection from URL.

        Args:
            redis_url: Redis connection URL. If None, reads from settings.
        """
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            if redis_url is None:
                try:
                    from backend.app.settings import get_settings
                    settings = get_settings()
                    redis_url = settings.redis_url
                except Exception:
                    redis_url = None

            if not redis_url:
                logger.info("Redis URL not configured, using in-memory fallback")
                self._available = False
                self._initialized = True
                return

            try:
                import redis.asyncio as aioredis

                self._redis = aioredis.from_url(
                    redis_url,
                    decode_responses=True,
                    max_connections=50,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                )
                await self._redis.ping()
                self._available = True
                logger.info("Redis connected successfully (pool: max_connections=50)")
            except ImportError:
                logger.warning("redis package not installed, using in-memory fallback")
                self._available = False
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}. Using in-memory fallback.")
                self._available = False

            self._initialized = True

    async def _get_backend(self) -> Any:
        """Get the active backend (Redis or fallback)."""
        if not self._initialized:
            await self.initialize()
        return self._redis if self._available else self._fallback

    async def get(self, key: str) -> str | None:
        backend = await self._get_backend()
        try:
            return await backend.get(key)
        except Exception as e:
            logger.warning(f"Redis GET failed: {e}. Using fallback.")
            return await self._fallback.get(key)

    async def set(self, key: str, value: str) -> None:
        backend = await self._get_backend()
        try:
            await backend.set(key, value)
        except Exception as e:
            logger.warning(f"Redis SET failed: {e}. Using fallback.")
            await self._fallback.set(key, value)

    async def setex(self, key: str, ttl_seconds: int, value: str) -> None:
        backend = await self._get_backend()
        try:
            await backend.setex(key, ttl_seconds, value)
        except Exception as e:
            logger.warning(f"Redis SETEX failed: {e}. Using fallback.")
            await self._fallback.setex(key, ttl_seconds, value)

    async def delete(self, *keys: str) -> int:
        backend = await self._get_backend()
        try:
            return await backend.delete(*keys)
        except Exception as e:
            logger.warning(f"Redis DELETE failed: {e}. Using fallback.")
            return await self._fallback.delete(*keys)

    async def exists(self, key: str) -> bool:
        backend = await self._get_backend()
        try:
            result = await backend.exists(key)
            return bool(result)
        except Exception as e:
            logger.warning(f"Redis EXISTS failed: {e}. Using fallback.")
            return await self._fallback.exists(key)

    async def incr(self, key: str) -> int:
        backend = await self._get_backend()
        try:
            return await backend.incr(key)
        except Exception as e:
            logger.warning(f"Redis INCR failed: {e}. Using fallback.")
            return await self._fallback.incr(key)

    async def expire(self, key: str, ttl_seconds: int) -> bool:
        backend = await self._get_backend()
        try:
            return await backend.expire(key, ttl_seconds)
        except Exception as e:
            logger.warning(f"Redis EXPIRE failed: {e}. Using fallback.")
            return await self._fallback.expire(key, ttl_seconds)

    async def ttl(self, key: str) -> int:
        backend = await self._get_backend()
        try:
            return await backend.ttl(key)
        except Exception as e:
            logger.warning(f"Redis TTL failed: {e}. Using fallback.")
            return await self._fallback.ttl(key)

    async def keys(self, pattern: str) -> list[str]:
        backend = await self._get_backend()
        try:
            return await backend.keys(pattern)
        except Exception as e:
            logger.warning(f"Redis KEYS failed: {e}. Using fallback.")
            return await self._fallback.keys(pattern)

    async def zadd(self, key: str, mapping: dict[str, float]) -> int:
        backend = await self._get_backend()
        try:
            return await backend.zadd(key, mapping)
        except Exception as e:
            logger.warning(f"Redis ZADD failed: {e}. Using fallback.")
            return await self._fallback.zadd(key, mapping)

    async def zremrangebyscore(self, key: str, min_score: float, max_score: float) -> int:
        backend = await self._get_backend()
        try:
            return await backend.zremrangebyscore(key, min_score, max_score)
        except Exception as e:
            logger.warning(f"Redis ZREMRANGEBYSCORE failed: {e}. Using fallback.")
            return await self._fallback.zremrangebyscore(key, min_score, max_score)

    async def zcard(self, key: str) -> int:
        backend = await self._get_backend()
        try:
            return await backend.zcard(key)
        except Exception as e:
            logger.warning(f"Redis ZCARD failed: {e}. Using fallback.")
            return await self._fallback.zcard(key)

    def pipeline(self) -> Any:
        """Get a pipeline for batch operations."""
        if self._available and self._redis:
            return self._redis.pipeline()
        return self._fallback.pipeline()

    async def ping(self) -> bool:
        """Check if Redis is reachable."""
        if not self._available:
            return False
        try:
            await self._redis.ping()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            with contextlib.suppress(Exception):
                await self._redis.close()
            self._redis = None
            self._available = False
            logger.info("Redis connection closed")


# Global singleton
_redis_client: RedisClient | None = None
_client_lock = Lock()


def get_redis() -> RedisClient:
    """Get the global Redis client singleton.

    Returns:
        RedisClient instance (may be using in-memory fallback if Redis unavailable)
    """
    global _redis_client
    if _redis_client is None:
        with _client_lock:
            if _redis_client is None:
                _redis_client = RedisClient()
    return _redis_client


async def init_redis() -> RedisClient:
    """Initialize the global Redis client.

    Call this during application startup.
    """
    client = get_redis()
    await client.initialize()
    return client


async def close_redis() -> None:
    """Close the global Redis client.

    Call this during application shutdown.
    """
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
