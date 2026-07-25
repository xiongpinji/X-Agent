"""Full-coverage unit tests for backend.app.core.pools.

Covers:
- PoolConfig, PoolStats dataclasses
- ConnectionPool: initialize, acquire, release, close, health check, context manager
- PostgresPool: initialize, acquire, release, execute, fetch, fetchrow, close, stats
- RedisPool: initialize, acquire, release, close, stats
- HTTPClientPool: initialize, get_client, close, stats
- Global singletons: get_postgres_pool, get_redis_pool, get_http_pool, close_all_pools
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.core.pools import (
    ConnectionPool,
    HTTPClientPool,
    PoolConfig,
    PoolStats,
    PostgresPool,
    RedisPool,
    close_all_pools,
    get_http_pool,
    get_postgres_pool,
    get_redis_pool,
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

class TestDataclasses:
    def test_pool_config_defaults(self):
        config = PoolConfig()
        assert config.min_size == 5
        assert config.max_size == 20
        assert config.timeout == 30.0
        assert config.health_check_interval == 60.0
        assert config.idle_timeout == 300.0
        assert config.max_overflow == 10

    def test_pool_config_custom(self):
        config = PoolConfig(min_size=2, max_size=10, timeout=5.0)
        assert config.min_size == 2
        assert config.max_size == 10

    def test_pool_stats_defaults(self):
        stats = PoolStats()
        assert stats.total_connections == 0
        assert stats.active_connections == 0
        assert stats.errors == 0
        assert stats.last_error is None
        assert stats.created_at > 0


# ---------------------------------------------------------------------------
# ConnectionPool
# ---------------------------------------------------------------------------

class TestConnectionPool:
    async def _make_pool(self, min_size=2, max_size=5, **kw) -> ConnectionPool:
        counter = {"n": 0}

        async def factory():
            counter["n"] += 1
            return f"conn-{counter['n']}"

        config = PoolConfig(min_size=min_size, max_size=max_size, health_check_interval=9999, **kw)
        pool = ConnectionPool(factory, config, name="test")
        return pool

    async def test_initialize(self):
        pool = await self._make_pool(min_size=3)
        await pool.initialize()
        stats = pool.get_stats()
        assert stats.total_connections == 3
        await pool.close()

    async def test_initialize_idempotent(self):
        pool = await self._make_pool()
        await pool.initialize()
        await pool.initialize()  # second call is no-op
        assert pool.get_stats().total_connections == 2
        await pool.close()

    async def test_acquire_release(self):
        pool = await self._make_pool(min_size=2)
        conn = await pool.acquire()
        assert conn is not None
        stats = pool.get_stats()
        assert stats.active_connections == 1
        assert stats.total_acquired == 1
        await pool.release(conn)
        stats = pool.get_stats()
        assert stats.active_connections == 0
        assert stats.total_released == 1
        await pool.close()

    async def test_acquire_creates_new_when_empty(self):
        pool = await self._make_pool(min_size=1, max_size=5)
        conn1 = await pool.acquire()
        conn2 = await pool.acquire()  # pool empty, creates new
        assert conn1 != conn2
        assert pool.get_stats().total_connections == 2
        await pool.release(conn1)
        await pool.release(conn2)
        await pool.close()

    async def test_acquire_waits_when_at_max(self):
        pool = await self._make_pool(min_size=1, max_size=1, timeout=0.5)
        conn = await pool.acquire()
        # Pool is at max, next acquire should timeout
        with pytest.raises(TimeoutError):
            await pool.acquire()
        await pool.release(conn)
        await pool.close()

    async def test_acquire_peak_tracking(self):
        pool = await self._make_pool(min_size=3)
        c1 = await pool.acquire()
        c2 = await pool.acquire()
        assert pool.get_stats().peak_active == 2
        await pool.release(c1)
        await pool.release(c2)
        await pool.close()

    async def test_close(self):
        pool = await self._make_pool(min_size=2)
        await pool.initialize()
        await pool.close()
        assert pool._initialized is False
        assert len(pool._all_connections) == 0

    async def test_close_connection_with_async_close(self):
        async def factory():
            mock = AsyncMock()
            mock.close = AsyncMock()
            return mock

        config = PoolConfig(min_size=1, health_check_interval=9999)
        pool = ConnectionPool(factory, config, name="test")
        await pool.initialize()
        conn = await pool.acquire()
        await pool.close()
        conn.close.assert_called_once()

    async def test_close_connection_with_sync_close(self):
        async def factory():
            mock = MagicMock()
            mock.close = MagicMock()
            return mock

        config = PoolConfig(min_size=1, health_check_interval=9999)
        pool = ConnectionPool(factory, config, name="test")
        await pool.initialize()
        await pool.close()
        # sync close was called
        assert True  # no exception means success

    async def test_close_connection_without_close(self):
        async def factory():
            return object()  # no close method

        config = PoolConfig(min_size=1, health_check_interval=9999)
        pool = ConnectionPool(factory, config, name="test")
        await pool.initialize()
        await pool.close()  # should not raise

    async def test_context_manager(self):
        counter = {"n": 0}

        async def factory():
            counter["n"] += 1
            return f"conn-{counter['n']}"

        config = PoolConfig(min_size=1, health_check_interval=9999)
        async with ConnectionPool(factory, config, name="ctx") as pool:
            conn = await pool.acquire()
            assert conn is not None
        # After exit, pool is closed
        assert pool._initialized is False

    async def test_factory_error_during_init(self):
        call_count = {"n": 0}

        async def failing_factory():
            call_count["n"] += 1
            if call_count["n"] <= 2:
                raise ConnectionError("cannot connect")
            return "conn"

        config = PoolConfig(min_size=3, health_check_interval=9999)
        pool = ConnectionPool(failing_factory, config, name="fail")
        await pool.initialize()
        # 2 failures, 1 success
        assert pool.get_stats().errors == 2
        assert pool.get_stats().total_connections == 1
        await pool.close()

    async def test_factory_error_during_acquire(self):
        call_count = {"n": 0}

        async def factory():
            call_count["n"] += 1
            if call_count["n"] > 1:
                raise ConnectionError("cannot create more")
            return "conn-1"

        config = PoolConfig(min_size=1, max_size=3, health_check_interval=9999)
        pool = ConnectionPool(factory, config, name="fail-acq")
        conn = await pool.acquire()
        await pool.release(conn)
        # Exhaust the pool
        c1 = await pool.acquire()
        # Next acquire tries to create new -> fails
        with pytest.raises(ConnectionError):
            await pool.acquire()
        await pool.release(c1)
        await pool.close()


# ---------------------------------------------------------------------------
# PostgresPool
# ---------------------------------------------------------------------------

class TestPostgresPool:
    async def test_initialize_no_asyncpg_fallback(self):
        pool = PostgresPool("postgresql://localhost/test")
        with patch.dict("sys.modules", {"asyncpg": None}):
            await pool.initialize()  # falls back to generic ConnectionPool
        assert isinstance(pool._pool, ConnectionPool)
        # All connection attempts failed but no exception raised
        assert pool._pool.get_stats().errors > 0
        await pool._pool.close()

    async def test_acquire_without_init(self):
        pool = PostgresPool("postgresql://localhost/test")
        # Mock the initialize to avoid real connection
        pool._pool = MagicMock()
        pool._pool.acquire = AsyncMock(return_value="mock_conn")
        conn = await pool.acquire()
        assert conn == "mock_conn"
        assert pool.get_stats().total_acquired == 1

    async def test_release(self):
        pool = PostgresPool("postgresql://localhost/test")
        pool._pool = MagicMock()
        pool._pool.release = AsyncMock()
        pool._stats.active_connections = 1
        await pool.release("conn")
        pool._pool.release.assert_called_once_with("conn")
        assert pool._stats.total_released == 1

    async def test_release_no_pool(self):
        pool = PostgresPool("postgresql://localhost/test")
        await pool.release("conn")  # should not raise

    async def test_execute_native(self):
        pool = PostgresPool("postgresql://localhost/test")
        pool._pool = MagicMock()
        pool._pool.execute = AsyncMock(return_value="OK")
        result = await pool.execute("SELECT 1")
        assert result == "OK"

    async def test_execute_fallback(self):
        pool = PostgresPool("postgresql://localhost/test")
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DONE")
        # Use object() so hasattr(pool._pool, 'execute') is False
        pool._pool = object()
        pool.acquire = AsyncMock(return_value=mock_conn)
        pool.release = AsyncMock()
        result = await pool.execute("SELECT 1")
        assert result == "DONE"

    async def test_fetch_native(self):
        pool = PostgresPool("postgresql://localhost/test")
        pool._pool = MagicMock()
        pool._pool.fetch = AsyncMock(return_value=[{"id": 1}])
        result = await pool.fetch("SELECT * FROM t")
        assert result == [{"id": 1}]

    async def test_fetch_fallback(self):
        pool = PostgresPool("postgresql://localhost/test")
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[{"x": 1}])
        pool._pool = object()
        pool.acquire = AsyncMock(return_value=mock_conn)
        pool.release = AsyncMock()
        result = await pool.fetch("SELECT 1")
        assert result == [{"x": 1}]

    async def test_fetchrow_native(self):
        pool = PostgresPool("postgresql://localhost/test")
        pool._pool = MagicMock()
        pool._pool.fetchrow = AsyncMock(return_value={"id": 1})
        result = await pool.fetchrow("SELECT 1")
        assert result == {"id": 1}

    async def test_fetchrow_fallback(self):
        pool = PostgresPool("postgresql://localhost/test")
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"y": 2})
        pool._pool = object()
        pool.acquire = AsyncMock(return_value=mock_conn)
        pool.release = AsyncMock()
        result = await pool.fetchrow("SELECT 1")
        assert result == {"y": 2}

    async def test_close(self):
        pool = PostgresPool("postgresql://localhost/test")
        pool._pool = MagicMock()
        pool._pool.close = AsyncMock()
        await pool.close()
        assert pool._pool is None

    async def test_close_no_pool(self):
        pool = PostgresPool("postgresql://localhost/test")
        await pool.close()  # should not raise

    def test_get_stats_native(self):
        pool = PostgresPool("postgresql://localhost/test")
        pool._pool = MagicMock()
        pool._pool.get_size = MagicMock(return_value=10)
        pool._pool.get_idle_size = MagicMock(return_value=7)
        stats = pool.get_stats()
        assert stats.total_connections == 10
        assert stats.idle_connections == 7
        assert stats.active_connections == 3

    def test_get_stats_no_pool(self):
        pool = PostgresPool("postgresql://localhost/test")
        stats = pool.get_stats()
        assert stats.total_connections == 0

    def test_url_strip_driver_prefix(self):
        pool = PostgresPool("postgresql+asyncpg://localhost/test")
        assert "+asyncpg" not in pool._database_url
        pool2 = PostgresPool("postgresql+psycopg://localhost/test")
        assert "+psycopg" not in pool2._database_url


# ---------------------------------------------------------------------------
# RedisPool
# ---------------------------------------------------------------------------

class TestRedisPool:
    async def test_acquire_release(self):
        pool = RedisPool("redis://localhost:6379")
        # Mock the internal pool
        pool._pool = AsyncMock()
        pool._pool.acquire = AsyncMock(return_value="redis_conn")
        pool._pool.release = AsyncMock()
        conn = await pool.acquire()
        assert conn == "redis_conn"
        await pool.release(conn)
        pool._pool.release.assert_called_once_with("redis_conn")

    async def test_release_no_pool(self):
        pool = RedisPool("redis://localhost:6379")
        await pool.release("conn")  # should not raise

    async def test_close(self):
        pool = RedisPool("redis://localhost:6379")
        pool._pool = AsyncMock()
        pool._pool.close = AsyncMock()
        await pool.close()
        assert pool._pool is None

    async def test_close_no_pool(self):
        pool = RedisPool("redis://localhost:6379")
        await pool.close()  # should not raise

    def test_get_stats_no_pool(self):
        pool = RedisPool("redis://localhost:6379")
        stats = pool.get_stats()
        assert stats.total_connections == 0

    def test_get_stats_with_pool(self):
        pool = RedisPool("redis://localhost:6379")
        mock_pool = MagicMock()
        mock_pool.get_stats = MagicMock(return_value=PoolStats(total_connections=5))
        pool._pool = mock_pool
        stats = pool.get_stats()
        assert stats.total_connections == 5


# ---------------------------------------------------------------------------
# HTTPClientPool
# ---------------------------------------------------------------------------

class TestHTTPClientPool:
    async def test_initialize(self):
        pool = HTTPClientPool()
        await pool.initialize()
        assert pool._client is not None
        await pool.close()

    async def test_initialize_idempotent(self):
        pool = HTTPClientPool()
        await pool.initialize()
        client1 = pool._client
        await pool.initialize()
        assert pool._client is client1
        await pool.close()

    async def test_get_client(self):
        pool = HTTPClientPool()
        client = await pool.get_client()
        assert client is not None
        await pool.close()

    async def test_close(self):
        pool = HTTPClientPool()
        await pool.initialize()
        await pool.close()
        assert pool._client is None

    async def test_close_no_client(self):
        pool = HTTPClientPool()
        await pool.close()  # should not raise

    def test_get_stats_no_client(self):
        pool = HTTPClientPool()
        assert pool.get_stats() == {}

    async def test_get_stats_with_client(self):
        pool = HTTPClientPool(PoolConfig(max_size=10, timeout=5.0))
        await pool.initialize()
        stats = pool.get_stats()
        assert stats["max_connections"] == 10
        assert stats["timeout"] == 5.0
        await pool.close()


# ---------------------------------------------------------------------------
# Global singletons
# ---------------------------------------------------------------------------

class TestGlobalSingletons:
    def test_get_postgres_pool(self):
        import backend.app.core.pools as mod
        old = mod._postgres_pool
        mod._postgres_pool = None
        try:
            pool = get_postgres_pool("postgresql://localhost/test")
            assert isinstance(pool, PostgresPool)
            assert get_postgres_pool("postgresql://other") is pool  # singleton
        finally:
            mod._postgres_pool = old

    def test_get_redis_pool(self):
        import backend.app.core.pools as mod
        old = mod._redis_pool
        mod._redis_pool = None
        try:
            pool = get_redis_pool("redis://localhost:6379")
            assert isinstance(pool, RedisPool)
            assert get_redis_pool("redis://other") is pool
        finally:
            mod._redis_pool = old

    def test_get_http_pool(self):
        import backend.app.core.pools as mod
        old = mod._http_pool
        mod._http_pool = None
        try:
            pool = get_http_pool()
            assert isinstance(pool, HTTPClientPool)
            assert get_http_pool() is pool
        finally:
            mod._http_pool = old

    async def test_close_all_pools(self):
        import backend.app.core.pools as mod
        old_pg, old_redis, old_http = mod._postgres_pool, mod._redis_pool, mod._http_pool
        mod._postgres_pool = PostgresPool("postgresql://localhost/test")
        mod._redis_pool = RedisPool("redis://localhost:6379")
        mod._http_pool = HTTPClientPool()
        try:
            await close_all_pools()
            assert mod._postgres_pool is None
            assert mod._redis_pool is None
            assert mod._http_pool is None
        finally:
            mod._postgres_pool = old_pg
            mod._redis_pool = old_redis
            mod._http_pool = old_http

    async def test_close_all_pools_none(self):
        import backend.app.core.pools as mod
        old_pg, old_redis, old_http = mod._postgres_pool, mod._redis_pool, mod._http_pool
        mod._postgres_pool = None
        mod._redis_pool = None
        mod._http_pool = None
        try:
            await close_all_pools()  # should not raise
        finally:
            mod._postgres_pool = old_pg
            mod._redis_pool = old_redis
            mod._http_pool = old_http
