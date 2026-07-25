"""
Unified connection pool management for X-Agent.

Implements:
- PostgreSQL connection pool (asyncpg)
- Redis connection pool
- HTTP connection pool (httpx)
- Unified pool configuration and monitoring
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class PoolConfig:
    """Configuration for connection pools."""

    min_size: int = 5
    max_size: int = 20
    timeout: float = 30.0
    health_check_interval: float = 60.0
    idle_timeout: float = 300.0  # 5 minutes
    max_overflow: int = 10


@dataclass
class PoolStats:
    """Statistics for a connection pool."""

    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    waiting_tasks: int = 0
    total_acquired: int = 0
    total_released: int = 0
    peak_active: int = 0
    errors: int = 0
    last_error: str | None = None
    created_at: float = field(default_factory=time.time)


class ConnectionPool(Generic[T]):
    """
    Generic async connection pool with configurable size and timeout.

    Features:
    - Automatic connection creation and cleanup
    - Timeout handling
    - Statistics tracking
    - Health checking
    - Idle connection cleanup
    """

    def __init__(
        self,
        factory: Callable[[], Any],
        config: PoolConfig | None = None,
        name: str = "pool",
    ) -> None:
        self._factory = factory
        self._config = config or PoolConfig()
        self._name = name

        self._available: asyncio.Queue[T] = asyncio.Queue()
        self._all_connections: set[T] = set()
        self._active_connections: set[T] = set()
        self._connection_created_at: dict[T, float] = {}
        self._lock = asyncio.Lock()
        self._stats = PoolStats()
        self._initialized = False
        self._health_check_task: asyncio.Task | None = None

    async def initialize(self) -> None:
        """Initialize the pool with minimum connections."""
        if self._initialized:
            return

        async with self._lock:
            for _ in range(self._config.min_size):
                try:
                    conn = await self._create_connection()
                    if conn is not None:
                        self._all_connections.add(conn)
                        await self._available.put(conn)
                        self._stats.total_connections += 1
                except Exception as e:
                    logger.error(f"[{self._name}] Failed to create connection: {e}")
                    self._stats.errors += 1

        self._initialized = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info(
            f"[{self._name}] Pool initialized with {self._stats.total_connections} connections"
        )

    async def acquire(self) -> T:
        """Acquire a connection from the pool."""
        await self.initialize()

        try:
            # Try to get an available connection
            conn = self._available.get_nowait()
            self._active_connections.add(conn)
            self._stats.active_connections = len(self._active_connections)
            self._stats.total_acquired += 1
            self._stats.peak_active = max(self._stats.peak_active, self._stats.active_connections)
            return conn
        except asyncio.QueueEmpty:
            pass

        # Create a new connection if under max_size
        async with self._lock:
            if self._stats.total_connections < self._config.max_size:
                try:
                    conn = await self._create_connection()
                    if conn is not None:
                        self._all_connections.add(conn)
                        self._active_connections.add(conn)
                        self._stats.total_connections += 1
                        self._stats.active_connections = len(self._active_connections)
                        self._stats.total_acquired += 1
                        self._stats.peak_active = max(
                            self._stats.peak_active, self._stats.active_connections
                        )
                        return conn
                except Exception as e:
                    logger.error(f"[{self._name}] Failed to create connection: {e}")
                    self._stats.errors += 1
                    self._stats.last_error = str(e)
                    raise

        # Wait for an available connection
        try:
            self._stats.waiting_tasks += 1
            conn = await asyncio.wait_for(self._available.get(), timeout=self._config.timeout)
            self._active_connections.add(conn)
            self._stats.active_connections = len(self._active_connections)
            self._stats.total_acquired += 1
            self._stats.peak_active = max(self._stats.peak_active, self._stats.active_connections)
            return conn
        except TimeoutError:
            logger.error(f"[{self._name}] Timeout waiting for available connection")
            self._stats.errors += 1
            self._stats.last_error = "Timeout waiting for connection"
            raise
        finally:
            self._stats.waiting_tasks = max(0, self._stats.waiting_tasks - 1)

    async def release(self, conn: T) -> None:
        """Release a connection back to the pool."""
        if conn in self._active_connections:
            self._active_connections.remove(conn)

        self._stats.active_connections = len(self._active_connections)
        self._stats.idle_connections = self._available.qsize()
        self._stats.total_released += 1

        await self._available.put(conn)

    async def close(self) -> None:
        """Close all connections in the pool."""
        if self._health_check_task:
            self._health_check_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._health_check_task

        async with self._lock:
            for conn in self._all_connections:
                try:
                    await self._close_connection(conn)
                except Exception as e:
                    logger.error(f"[{self._name}] Error closing connection: {e}")

            self._all_connections.clear()
            self._active_connections.clear()
            self._connection_created_at.clear()
            self._initialized = False

        logger.info(f"[{self._name}] Pool closed")

    async def _create_connection(self) -> T:
        """Create a new connection."""
        conn = await self._factory()
        self._connection_created_at[conn] = time.time()
        return conn

    async def _close_connection(self, conn: T) -> None:
        """Close a connection."""
        if hasattr(conn, "close"):
            close_method = conn.close
            if asyncio.iscoroutinefunction(close_method):
                await close_method()
            else:
                close_method()

    async def _health_check_loop(self) -> None:
        """Periodically check and clean up idle connections."""
        while self._initialized:
            try:
                await asyncio.sleep(self._config.health_check_interval)

                async with self._lock:
                    now = time.time()
                    idle_conns = []

                    # Find idle connections that exceed idle_timeout
                    while not self._available.empty():
                        try:
                            conn = self._available.get_nowait()
                            created_at = self._connection_created_at.get(conn, now)
                            if now - created_at > self._config.idle_timeout:
                                idle_conns.append(conn)
                            else:
                                await self._available.put(conn)
                        except asyncio.QueueEmpty:
                            break

                    # Close idle connections
                    for conn in idle_conns:
                        try:
                            await self._close_connection(conn)
                            self._all_connections.discard(conn)
                            self._connection_created_at.pop(conn, None)
                            self._stats.total_connections = max(
                                0, self._stats.total_connections - 1
                            )
                            logger.debug(f"[{self._name}] Closed idle connection")
                        except Exception as e:
                            logger.error(f"[{self._name}] Error closing idle connection: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self._name}] Health check error: {e}")

    def get_stats(self) -> PoolStats:
        """Get pool statistics."""
        return self._stats

    async def __aenter__(self) -> ConnectionPool[T]:
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()


class PostgresPool:
    """PostgreSQL connection pool using asyncpg native pooling.

    Uses asyncpg.create_pool() for optimal connection management with
    built-in health checks, statement timeout, and connection recycling.
    """

    def __init__(self, database_url: str, config: PoolConfig | None = None) -> None:
        # Strip SQLAlchemy driver prefix for raw asyncpg
        self._database_url = database_url.replace("+asyncpg", "").replace("+psycopg", "")
        self._config = config or PoolConfig()
        self._pool: Any | None = None  # asyncpg.Pool
        self._stats = PoolStats()

    async def initialize(self) -> None:
        """Initialize the PostgreSQL pool using asyncpg.create_pool."""
        if self._pool is not None:
            return

        try:
            import asyncpg

            self._pool = await asyncpg.create_pool(
                self._database_url,
                min_size=self._config.min_size,
                max_size=self._config.max_size,
                command_timeout=self._config.timeout,
                max_inactive_connection_lifetime=self._config.idle_timeout,
            )
            self._stats.total_connections = self._pool.get_min_size()
            logger.info(
                f"[postgres] Native asyncpg pool initialized "
                f"(min={self._config.min_size}, max={self._config.max_size})"
            )
        except ImportError:
            # Fallback to generic pool if asyncpg not available
            logger.warning("[postgres] asyncpg not available, using generic pool")

            async def create_pg_connection():
                import asyncpg as _asyncpg
                return await _asyncpg.connect(self._database_url)

            self._pool = ConnectionPool(create_pg_connection, self._config, name="postgres")
            await self._pool.initialize()
        except Exception as e:
            logger.error(f"[postgres] Failed to create pool: {e}")
            self._stats.errors += 1
            self._stats.last_error = str(e)
            raise

    async def acquire(self):
        """Acquire a connection from the pool."""
        if self._pool is None:
            await self.initialize()

        if hasattr(self._pool, 'acquire'):
            # Native asyncpg pool
            conn = await self._pool.acquire()
            self._stats.total_acquired += 1
            self._stats.active_connections += 1
            self._stats.peak_active = max(self._stats.peak_active, self._stats.active_connections)
            return conn
        else:
            # Generic ConnectionPool fallback
            return await self._pool.acquire()

    async def release(self, conn) -> None:
        """Release a connection back to the pool."""
        if self._pool is None:
            return

        if hasattr(self._pool, 'release'):
            await self._pool.release(conn)
            self._stats.active_connections = max(0, self._stats.active_connections - 1)
            self._stats.total_released += 1
        else:
            await self._pool.release(conn)

    async def execute(self, query: str, *args) -> str:
        """Execute a query directly using a pooled connection."""
        if self._pool is None:
            await self.initialize()
        if hasattr(self._pool, 'execute'):
            return await self._pool.execute(query, *args)
        conn = await self.acquire()
        try:
            return await conn.execute(query, *args)
        finally:
            await self.release(conn)

    async def fetch(self, query: str, *args) -> list:
        """Fetch rows directly using a pooled connection."""
        if self._pool is None:
            await self.initialize()
        if hasattr(self._pool, 'fetch'):
            return await self._pool.fetch(query, *args)
        conn = await self.acquire()
        try:
            return await conn.fetch(query, *args)
        finally:
            await self.release(conn)

    async def fetchrow(self, query: str, *args):
        """Fetch a single row directly using a pooled connection."""
        if self._pool is None:
            await self.initialize()
        if hasattr(self._pool, 'fetchrow'):
            return await self._pool.fetchrow(query, *args)
        conn = await self.acquire()
        try:
            return await conn.fetchrow(query, *args)
        finally:
            await self.release(conn)

    async def close(self) -> None:
        """Close the pool."""
        if self._pool is not None:
            if hasattr(self._pool, 'close'):
                await self._pool.close()
            self._pool = None
            logger.info("[postgres] Pool closed")

    def get_stats(self) -> PoolStats:
        """Get pool statistics."""
        if self._pool is not None and hasattr(self._pool, 'get_size'):
            self._stats.total_connections = self._pool.get_size()
            self._stats.idle_connections = self._pool.get_idle_size()
            self._stats.active_connections = self._stats.total_connections - self._stats.idle_connections
        return self._stats


class RedisPool:
    """Redis connection pool using redis-py."""

    def __init__(self, redis_url: str, config: PoolConfig | None = None) -> None:
        self._redis_url = redis_url
        self._config = config or PoolConfig()
        self._pool: ConnectionPool | None = None

    async def initialize(self) -> None:
        """Initialize the Redis pool."""
        if self._pool is not None:
            return

        async def create_redis_connection():
            import redis.asyncio as redis

            return await redis.from_url(self._redis_url)

        self._pool = ConnectionPool(create_redis_connection, self._config, name="redis")
        await self._pool.initialize()

    async def acquire(self):
        """Acquire a connection."""
        if self._pool is None:
            await self.initialize()
        return await self._pool.acquire()

    async def release(self, conn) -> None:
        """Release a connection."""
        if self._pool is not None:
            await self._pool.release(conn)

    async def close(self) -> None:
        """Close the pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    def get_stats(self) -> PoolStats:
        """Get pool statistics."""
        if self._pool is None:
            return PoolStats()
        return self._pool.get_stats()


class HTTPClientPool:
    """HTTP client pool using httpx."""

    def __init__(self, config: PoolConfig | None = None) -> None:
        self._config = config or PoolConfig()
        self._client: Any | None = None

    async def initialize(self) -> None:
        """Initialize the HTTP client."""
        if self._client is not None:
            return

        import httpx

        limits = httpx.Limits(
            max_connections=self._config.max_size,
            max_keepalive_connections=self._config.max_size,
        )
        self._client = httpx.AsyncClient(limits=limits, timeout=self._config.timeout)
        logger.info("[httpx] HTTP client initialized")

    async def get_client(self) -> Any:
        """Get the HTTP client."""
        if self._client is None:
            await self.initialize()
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("[httpx] HTTP client closed")

    def get_stats(self) -> dict[str, Any]:
        """Get HTTP client statistics."""
        if self._client is None:
            return {}
        return {
            "max_connections": self._config.max_size,
            "timeout": self._config.timeout,
        }


# Global pool instances
_postgres_pool: PostgresPool | None = None
_redis_pool: RedisPool | None = None
_http_pool: HTTPClientPool | None = None


def get_postgres_pool(database_url: str, config: PoolConfig | None = None) -> PostgresPool:
    """Get or create the global PostgreSQL pool."""
    global _postgres_pool
    if _postgres_pool is None:
        _postgres_pool = PostgresPool(database_url, config)
    return _postgres_pool


def get_redis_pool(redis_url: str, config: PoolConfig | None = None) -> RedisPool:
    """Get or create the global Redis pool."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = RedisPool(redis_url, config)
    return _redis_pool


def get_http_pool(config: PoolConfig | None = None) -> HTTPClientPool:
    """Get or create the global HTTP client pool."""
    global _http_pool
    if _http_pool is None:
        _http_pool = HTTPClientPool(config)
    return _http_pool


async def close_all_pools() -> None:
    """Close all global pools."""
    global _postgres_pool, _redis_pool, _http_pool

    if _postgres_pool is not None:
        await _postgres_pool.close()
        _postgres_pool = None

    if _redis_pool is not None:
        await _redis_pool.close()
        _redis_pool = None

    if _http_pool is not None:
        await _http_pool.close()
        _http_pool = None

    logger.info("All connection pools closed")
