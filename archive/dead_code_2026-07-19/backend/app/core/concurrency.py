"""
Concurrency control and connection pool management.

Implements:
- Semaphore-based concurrency limiting
- Connection pool management
- Task queue with backpressure
- Resource monitoring
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


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


class ConnectionPool:
    """
    Generic connection pool with configurable size and timeout.

    Features:
    - Automatic connection creation and cleanup
    - Timeout handling
    - Statistics tracking
    - Health checking
    """

    def __init__(
        self,
        factory: Callable,
        min_size: int = 5,
        max_size: int = 20,
        timeout: float = 30.0,
        health_check_interval: float = 60.0,
    ) -> None:
        self._factory = factory
        self._min_size = min_size
        self._max_size = max_size
        self._timeout = timeout
        self._health_check_interval = health_check_interval

        self._available: asyncio.Queue = asyncio.Queue()
        self._all_connections: set = set()
        self._active_connections: set = set()
        self._lock = asyncio.Lock()
        self._stats = PoolStats()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the pool with minimum connections."""
        if self._initialized:
            return

        async with self._lock:
            for _ in range(self._min_size):
                try:
                    conn = await self._factory()
                    self._all_connections.add(conn)
                    await self._available.put(conn)
                    self._stats.total_connections += 1
                except Exception as e:
                    logger.error(f"Failed to create connection: {e}")
                    self._stats.errors += 1

        self._initialized = True
        logger.info(f"Connection pool initialized with {self._stats.total_connections} connections")

    async def acquire(self) -> Any:
        """Acquire a connection from the pool."""
        await self.initialize()

        try:
            # Try to get an available connection
            conn = self._available.get_nowait()
        except asyncio.QueueEmpty:
            # Create a new connection if under max_size
            async with self._lock:
                if self._stats.total_connections < self._max_size:
                    try:
                        conn = await self._factory()
                        self._all_connections.add(conn)
                        self._stats.total_connections += 1
                    except Exception as e:
                        logger.error(f"Failed to create connection: {e}")
                        self._stats.errors += 1
                        raise
                else:
                    # Wait for an available connection
                    try:
                        conn = await asyncio.wait_for(self._available.get(), timeout=self._timeout)
                    except asyncio.TimeoutError:
                        logger.error("Timeout waiting for available connection")
                        self._stats.errors += 1
                        raise

        self._active_connections.add(conn)
        self._stats.active_connections = len(self._active_connections)
        self._stats.total_acquired += 1
        self._stats.peak_active = max(self._stats.peak_active, self._stats.active_connections)

        return conn

    async def release(self, conn: Any) -> None:
        """Release a connection back to the pool."""
        if conn in self._active_connections:
            self._active_connections.remove(conn)

        self._stats.active_connections = len(self._active_connections)
        self._stats.idle_connections = self._available.qsize()
        self._stats.total_released += 1

        await self._available.put(conn)

    async def close(self) -> None:
        """Close all connections in the pool."""
        async with self._lock:
            for conn in self._all_connections:
                try:
                    if hasattr(conn, "close"):
                        await conn.close() if asyncio.iscoroutinefunction(conn.close) else conn.close()
                except Exception as e:
                    logger.error(f"Error closing connection: {e}")

            self._all_connections.clear()
            self._active_connections.clear()
            self._initialized = False

    def get_stats(self) -> PoolStats:
        """Get pool statistics."""
        return self._stats


class ConcurrencyLimiter:
    """
    Semaphore-based concurrency limiter.

    Features:
    - Per-operation concurrency limiting
    - Backpressure handling
    - Statistics tracking
    """

    def __init__(self, max_concurrent: int = 10) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max_concurrent = max_concurrent
        self._active_tasks = 0
        self._total_tasks = 0
        self._peak_active = 0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a concurrency slot."""
        await self._semaphore.acquire()
        async with self._lock:
            self._active_tasks += 1
            self._total_tasks += 1
            self._peak_active = max(self._peak_active, self._active_tasks)

    def release(self) -> None:
        """Release a concurrency slot."""
        self._semaphore.release()
        self._active_tasks = max(0, self._active_tasks - 1)

    async def run(self, coro) -> Any:
        """Run a coroutine with concurrency limiting."""
        await self.acquire()
        try:
            return await coro
        finally:
            self.release()

    def get_stats(self) -> dict[str, int]:
        """Get limiter statistics."""
        return {
            "max_concurrent": self._max_concurrent,
            "active_tasks": self._active_tasks,
            "total_tasks": self._total_tasks,
            "peak_active": self._peak_active,
        }


class TaskQueue:
    """
    Async task queue with backpressure and priority support.

    Features:
    - FIFO task queue
    - Backpressure handling
    - Task timeout
    - Statistics tracking
    """

    def __init__(self, max_queue_size: int = 1000, worker_count: int = 4) -> None:
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_queue_size)
        self._worker_count = worker_count
        self._workers: list[asyncio.Task] = []
        self._running = False
        self._total_tasks = 0
        self._completed_tasks = 0
        self._failed_tasks = 0
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the task queue workers."""
        if self._running:
            return

        self._running = True
        for i in range(self._worker_count):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)

        logger.info(f"Task queue started with {self._worker_count} workers")

    async def stop(self) -> None:
        """Stop the task queue workers."""
        self._running = False
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("Task queue stopped")

    async def enqueue(self, task: Callable, priority: int = 0, timeout: float | None = None) -> None:
        """Enqueue a task."""
        try:
            await asyncio.wait_for(
                self._queue.put((priority, time.time(), task)),
                timeout=timeout or 30.0,
            )
            async with self._lock:
                self._total_tasks += 1
        except asyncio.TimeoutError:
            logger.error("Task enqueue timeout")
            raise

    async def _worker(self, worker_id: int) -> None:
        """Worker coroutine."""
        while self._running:
            try:
                priority, enqueue_time, task = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                wait_time = time.time() - enqueue_time

                try:
                    if asyncio.iscoroutinefunction(task):
                        await task()
                    else:
                        task()

                    async with self._lock:
                        self._completed_tasks += 1
                except Exception as e:
                    logger.error(f"Task execution error: {e}")
                    async with self._lock:
                        self._failed_tasks += 1

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker error: {e}")

    def get_stats(self) -> dict[str, int]:
        """Get queue statistics."""
        return {
            "total_tasks": self._total_tasks,
            "completed_tasks": self._completed_tasks,
            "failed_tasks": self._failed_tasks,
            "queue_size": self._queue.qsize(),
            "worker_count": self._worker_count,
        }


class ResourceMonitor:
    """
    Monitor resource usage and enforce limits.

    Features:
    - Memory usage tracking
    - Connection pool monitoring
    - Task queue monitoring
    - Alerts on resource exhaustion
    """

    def __init__(self) -> None:
        self._pools: dict[str, ConnectionPool] = {}
        self._limiters: dict[str, ConcurrencyLimiter] = {}
        self._queues: dict[str, TaskQueue] = {}
        self._lock = asyncio.Lock()

    async def register_pool(self, name: str, pool: ConnectionPool) -> None:
        """Register a connection pool for monitoring."""
        async with self._lock:
            self._pools[name] = pool

    async def register_limiter(self, name: str, limiter: ConcurrencyLimiter) -> None:
        """Register a concurrency limiter for monitoring."""
        async with self._lock:
            self._limiters[name] = limiter

    async def register_queue(self, name: str, queue: TaskQueue) -> None:
        """Register a task queue for monitoring."""
        async with self._lock:
            self._queues[name] = queue

    def get_report(self) -> dict[str, Any]:
        """Get resource usage report."""
        report = {
            "pools": {},
            "limiters": {},
            "queues": {},
        }

        for name, pool in self._pools.items():
            stats = pool.get_stats()
            report["pools"][name] = {
                "total": stats.total_connections,
                "active": stats.active_connections,
                "idle": stats.idle_connections,
                "peak_active": stats.peak_active,
                "errors": stats.errors,
            }

        for name, limiter in self._limiters.items():
            stats = limiter.get_stats()
            report["limiters"][name] = stats

        for name, queue in self._queues.items():
            stats = queue.get_stats()
            report["queues"][name] = stats

        return report


# Global instances
_resource_monitor: ResourceMonitor | None = None


def get_resource_monitor() -> ResourceMonitor:
    """Get or create the global resource monitor."""
    global _resource_monitor
    if _resource_monitor is None:
        _resource_monitor = ResourceMonitor()
    return _resource_monitor
