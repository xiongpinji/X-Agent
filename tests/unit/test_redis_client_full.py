"""Full-coverage unit tests for backend.app.core.redis_client.

Covers:
- InMemoryFallback: get, set, setex, delete, exists, incr, expire, ttl, keys,
  zadd, zremrangebyscore, zcard, pipeline, ping, close
- InMemoryPipeline: zadd, zremrangebyscore, zcard, expire, execute, context manager
- RedisClient: initialize, all operations with fallback, pipeline, ping, close
- Global singleton: get_redis, init_redis, close_redis
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.core.redis_client import (
    InMemoryFallback,
    InMemoryPipeline,
    RedisClient,
    RedisNotAvailable,
    close_redis,
    get_redis,
    init_redis,
)


# ---------------------------------------------------------------------------
# InMemoryFallback
# ---------------------------------------------------------------------------

class TestInMemoryFallback:
    async def test_get_set(self):
        store = InMemoryFallback()
        assert await store.get("key") is None
        await store.set("key", "value")
        assert await store.get("key") == "value"

    async def test_setex_and_ttl(self):
        store = InMemoryFallback()
        await store.setex("key", 100, "value")
        assert await store.get("key") == "value"
        ttl = await store.ttl("key")
        assert 90 <= ttl <= 100

    async def test_setex_expiry(self):
        store = InMemoryFallback()
        await store.setex("key", 0, "value")  # expires immediately
        # TTL 0 means expiry = time.time() + 0, which is now
        # After a tiny sleep it should be expired
        await asyncio.sleep(0.01)
        assert await store.get("key") is None

    async def test_delete(self):
        store = InMemoryFallback()
        await store.set("a", "1")
        await store.set("b", "2")
        count = await store.delete("a", "b", "c")
        assert count == 2
        assert await store.get("a") is None

    async def test_exists(self):
        store = InMemoryFallback()
        assert await store.exists("key") is False
        await store.set("key", "val")
        assert await store.exists("key") is True

    async def test_exists_expired(self):
        store = InMemoryFallback()
        await store.setex("key", 0, "val")
        await asyncio.sleep(0.01)
        assert await store.exists("key") is False

    async def test_incr(self):
        store = InMemoryFallback()
        assert await store.incr("counter") == 1
        assert await store.incr("counter") == 2
        assert await store.incr("counter") == 3

    async def test_incr_expired(self):
        store = InMemoryFallback()
        await store.setex("counter", 0, "5")
        await asyncio.sleep(0.01)
        assert await store.incr("counter") == 1  # reset after expiry

    async def test_expire(self):
        store = InMemoryFallback()
        await store.set("key", "val")
        assert await store.expire("key", 100) is True
        ttl = await store.ttl("key")
        assert ttl > 0
        assert await store.expire("nonexistent", 100) is False

    async def test_ttl_no_key(self):
        store = InMemoryFallback()
        assert await store.ttl("nonexistent") == -2

    async def test_ttl_no_expiry(self):
        store = InMemoryFallback()
        await store.set("key", "val")
        assert await store.ttl("key") == -1

    async def test_keys_pattern(self):
        store = InMemoryFallback()
        await store.set("user:1", "a")
        await store.set("user:2", "b")
        await store.set("session:1", "c")
        result = await store.keys("user:*")
        assert sorted(result) == ["user:1", "user:2"]

    async def test_keys_cleans_expired(self):
        store = InMemoryFallback()
        await store.setex("expired", 0, "x")
        await store.set("alive", "y")
        await asyncio.sleep(0.01)
        result = await store.keys("*")
        assert "expired" not in result
        assert "alive" in result

    async def test_zadd(self):
        store = InMemoryFallback()
        count = await store.zadd("zset", {"member1": 1.0, "member2": 2.0})
        assert count == 2

    async def test_zadd_update_existing(self):
        store = InMemoryFallback()
        await store.zadd("zset", {"m1": 1.0})
        await store.zadd("zset", {"m1": 5.0, "m2": 2.0})
        assert await store.zcard("zset") == 2

    async def test_zremrangebyscore(self):
        store = InMemoryFallback()
        await store.zadd("zset", {"a": 1.0, "b": 5.0, "c": 10.0})
        removed = await store.zremrangebyscore("zset", 0, 6)
        assert removed == 2  # a and b removed
        assert await store.zcard("zset") == 1

    async def test_zremrangebyscore_no_key(self):
        store = InMemoryFallback()
        assert await store.zremrangebyscore("nonexistent", 0, 100) == 0

    async def test_zremrangebyscore_invalid_data(self):
        store = InMemoryFallback()
        await store.set("zset", "not json")
        assert await store.zremrangebyscore("zset", 0, 100) == 0

    async def test_zcard(self):
        store = InMemoryFallback()
        assert await store.zcard("nonexistent") == 0
        await store.zadd("zset", {"a": 1.0, "b": 2.0})
        assert await store.zcard("zset") == 2

    async def test_zcard_invalid_data(self):
        store = InMemoryFallback()
        await store.set("zset", "not json")
        assert await store.zcard("zset") == 0

    async def test_pipeline(self):
        store = InMemoryFallback()
        pipe = store.pipeline()
        assert isinstance(pipe, InMemoryPipeline)

    async def test_ping(self):
        store = InMemoryFallback()
        assert await store.ping() is True

    async def test_close(self):
        store = InMemoryFallback()
        await store.close()  # should not raise


# ---------------------------------------------------------------------------
# InMemoryPipeline
# ---------------------------------------------------------------------------

class TestInMemoryPipeline:
    async def test_pipeline_execute(self):
        store = InMemoryFallback()
        pipe = InMemoryPipeline(store)
        pipe.zadd("zset", {"a": 1.0, "b": 2.0})
        pipe.zcard("zset")
        pipe.expire("zset", 100)
        results = await pipe.execute()
        assert results[0] == 2  # zadd returns count
        assert results[1] == 2  # zcard
        assert results[2] is True  # expire

    async def test_pipeline_zremrangebyscore(self):
        store = InMemoryFallback()
        await store.zadd("zset", {"a": 1.0, "b": 5.0})
        pipe = InMemoryPipeline(store)
        pipe.zremrangebyscore("zset", 0, 3)
        results = await pipe.execute()
        assert results[0] == 1  # removed "a"

    async def test_pipeline_context_manager(self):
        store = InMemoryFallback()
        pipe = InMemoryPipeline(store)
        async with pipe as p:
            p.zadd("z", {"x": 1.0})
            await p.execute()
        assert await store.zcard("z") == 1

    async def test_pipeline_chaining(self):
        store = InMemoryFallback()
        pipe = InMemoryPipeline(store)
        result = pipe.zadd("z", {"a": 1.0}).zcard("z").expire("z", 60)
        assert result is pipe  # chaining returns self


# ---------------------------------------------------------------------------
# RedisClient
# ---------------------------------------------------------------------------

class TestRedisClient:
    async def test_initialize_no_url(self):
        client = RedisClient()
        await client.initialize(redis_url=None)
        assert client.is_available is False

    async def test_initialize_empty_url(self):
        client = RedisClient()
        await client.initialize(redis_url="")
        assert client.is_available is False

    async def test_initialize_already_initialized(self):
        client = RedisClient()
        await client.initialize(redis_url="")
        # Second call should be no-op
        await client.initialize(redis_url="redis://localhost:6379")
        assert client.is_available is False

    async def test_initialize_connection_failure(self):
        client = RedisClient()
        await client.initialize(redis_url="redis://localhost:9999")
        assert client.is_available is False

    async def test_get_set_fallback(self):
        client = RedisClient()
        await client.initialize(redis_url="")
        await client.set("key", "value")
        assert await client.get("key") == "value"

    async def test_setex_fallback(self):
        client = RedisClient()
        await client.initialize(redis_url="")
        await client.setex("key", 100, "value")
        assert await client.get("key") == "value"

    async def test_delete_fallback(self):
        client = RedisClient()
        await client.initialize(redis_url="")
        await client.set("key", "value")
        count = await client.delete("key")
        assert count == 1

    async def test_exists_fallback(self):
        client = RedisClient()
        await client.initialize(redis_url="")
        await client.set("key", "value")
        assert await client.exists("key") is True
        assert await client.exists("other") is False

    async def test_incr_fallback(self):
        client = RedisClient()
        await client.initialize(redis_url="")
        assert await client.incr("counter") == 1
        assert await client.incr("counter") == 2

    async def test_expire_fallback(self):
        client = RedisClient()
        await client.initialize(redis_url="")
        await client.set("key", "val")
        assert await client.expire("key", 100) is True

    async def test_ttl_fallback(self):
        client = RedisClient()
        await client.initialize(redis_url="")
        await client.setex("key", 100, "val")
        ttl = await client.ttl("key")
        assert ttl > 0

    async def test_keys_fallback(self):
        client = RedisClient()
        await client.initialize(redis_url="")
        await client.set("prefix:a", "1")
        await client.set("prefix:b", "2")
        result = await client.keys("prefix:*")
        assert len(result) == 2

    async def test_zadd_fallback(self):
        client = RedisClient()
        await client.initialize(redis_url="")
        count = await client.zadd("zset", {"m": 1.0})
        assert count == 1

    async def test_zremrangebyscore_fallback(self):
        client = RedisClient()
        await client.initialize(redis_url="")
        await client.zadd("zset", {"a": 1.0, "b": 5.0})
        removed = await client.zremrangebyscore("zset", 0, 3)
        assert removed == 1

    async def test_zcard_fallback(self):
        client = RedisClient()
        await client.initialize(redis_url="")
        await client.zadd("zset", {"a": 1.0})
        assert await client.zcard("zset") == 1

    async def test_pipeline_fallback(self):
        client = RedisClient()
        await client.initialize(redis_url="")
        pipe = client.pipeline()
        assert isinstance(pipe, InMemoryPipeline)

    async def test_ping_not_available(self):
        client = RedisClient()
        await client.initialize(redis_url="")
        assert await client.ping() is False

    async def test_close(self):
        client = RedisClient()
        await client.initialize(redis_url="")
        await client.close()
        assert client.is_available is False

    async def test_close_with_redis_mock(self):
        client = RedisClient()
        client._redis = AsyncMock()
        client._available = True
        await client.close()
        assert client._redis is None
        assert client.is_available is False

    async def test_close_exception(self):
        client = RedisClient()
        mock_redis = AsyncMock()
        mock_redis.close.side_effect = Exception("close error")
        client._redis = mock_redis
        client._available = True
        await client.close()  # should not raise
        assert client._redis is None

    async def test_get_backend_auto_init(self):
        client = RedisClient()
        # Not initialized yet - _get_backend should auto-init
        backend = await client._get_backend()
        assert backend is client._fallback

    async def test_get_fallback_on_error(self):
        client = RedisClient()
        await client.initialize(redis_url="")
        # Simulate redis error by making fallback the backend but patching to raise
        client._available = True
        client._redis = AsyncMock()
        client._redis.get.side_effect = Exception("connection lost")
        result = await client.get("key")
        assert result is None  # falls back to in-memory

    async def test_set_fallback_on_error(self):
        client = RedisClient()
        await client.initialize(redis_url="")
        client._available = True
        client._redis = AsyncMock()
        client._redis.set.side_effect = Exception("connection lost")
        await client.set("key", "value")
        # Should have fallen back to in-memory
        assert await client._fallback.get("key") == "value"


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

class TestGlobalSingleton:
    def test_get_redis_singleton(self):
        import backend.app.core.redis_client as mod
        old = mod._redis_client
        mod._redis_client = None
        try:
            client1 = get_redis()
            client2 = get_redis()
            assert client1 is client2
        finally:
            mod._redis_client = old

    async def test_init_redis(self):
        import backend.app.core.redis_client as mod
        old = mod._redis_client
        mod._redis_client = None
        try:
            client = await init_redis()
            assert isinstance(client, RedisClient)
        finally:
            mod._redis_client = old

    async def test_close_redis(self):
        import backend.app.core.redis_client as mod
        old = mod._redis_client
        mod._redis_client = RedisClient()
        try:
            await close_redis()
            assert mod._redis_client is None
        finally:
            mod._redis_client = old

    async def test_close_redis_none(self):
        import backend.app.core.redis_client as mod
        old = mod._redis_client
        mod._redis_client = None
        try:
            await close_redis()  # should not raise
        finally:
            mod._redis_client = old


# ---------------------------------------------------------------------------
# RedisNotAvailable exception
# ---------------------------------------------------------------------------

class TestRedisNotAvailable:
    def test_exception(self):
        with pytest.raises(RedisNotAvailable):
            raise RedisNotAvailable("Redis is down")
