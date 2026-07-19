"""Concurrency optimization for X-Agent.

Implements strategies for:
- Connection pool optimization
- Batch task execution
- Lock contention reduction
- Async/await optimization
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, TypeVar, Coroutine
from dataclasses import dataclass
from datetime import datetime, UTC

import asyncpg

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class ConnectionPoolConfig:
    """Configuration for database connection pool."""

    pool_size: int = 20
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600
    min_cached_statement_lifetime: int = 300
    max_cached_statement_lifetime: int = 3600


class ConcurrencyOptimizer:
    """Optimizes concurrent execution and resource management."""

    @staticmethod
    def get_optimal_pool_config(
        expected_concurrent_requests: int = 100,
    ) -> ConnectionPoolConfig:
        """Calculate optimal connection pool configuration.

        Args:
            expected_concurrent_requests: Expected concurrent requests

        Returns:
            Optimized connection pool configuration
        """
        # Rule of thumb: pool_size = (core_count * 2) + effective_spindle_count
        # For web apps: typically 20-40 connections
        pool_size = min(max(20, expected_concurrent_requests // 5), 50)
        max_overflow = pool_size // 2

        return ConnectionPoolConfig(
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=30,
            pool_recycle=3600,
        )

    @staticmethod
    async def create_optimized_pool(
        database_url: str,
        config: ConnectionPoolConfig | None = None,
    ) -> asyncpg.Pool:
        """Create optimized AsyncPG connection pool.

        Args:
            database_url: Database connection URL
            config: Connection pool configuration

        Returns:
            Configured AsyncPG pool
        """
        config = config or ConcurrencyOptimizer.get_optimal_pool_config()

        pool = await asyncpg.create_pool(
            database_url,
            min_size=config.pool_size // 2,
            max_size=config.pool_size,
            max_queries=50000,
            max_inactive_connection_lifetime=config.pool_recycle,
            command_timeout=config.pool_timeout,
        )

        logger.info(
            f"Created optimized connection pool: "
            f"size={config.pool_size}, overflow={config.max_overflow}"
        )

        return pool

    @staticmethod
    async def batch_execute(
        tasks: list[Coroutine[Any, Any, T]],
        batch_size: int = 10,
        return_exceptions: bool = False,
    ) -> list[T]:
        """Execute tasks in batches to control concurrency.

        Args:
            tasks: List of coroutines to execute
            batch_size: Number of tasks per batch
            return_exceptions: Whether to return exceptions or raise

        Returns:
            List of results
        """
        results = []

        for i in range(0, len(tasks), batch_size):
            batch = tasks[i : i + batch_size]
            batch_results = await asyncio.gather(*batch, return_exceptions=return_exceptions)
            results.extend(batch_results)

        return results

    @staticmethod
    async def batch_execute_with_timeout(
        tasks: list[Coroutine[Any, Any, T]],
        batch_size: int = 10,
        timeout: float = 30.0,
    ) -> list[T]:
        """Execute tasks in batches with timeout.

        Args:
            tasks: List of coroutines to execute
            batch_size: Number of tasks per batch
            timeout: Timeout per batch in seconds

        Returns:
            List of results
        """
        results = []

        for i in range(0, len(tasks), batch_size):
            batch = tasks[i : i + batch_size]
            try:
                batch_results = await asyncio.wait_for(
                    asyncio.gather(*batch, return_exceptions=True),
                    timeout=timeout,
                )
                results.extend(batch_results)
            except asyncio.TimeoutError:
                logger.error(f"Batch execution timeout at index {i}")
                results.extend([None] * len(batch))

        return results

    @staticmethod
    async def semaphore_limited_execution(
        tasks: list[Coroutine[Any, Any, T]],
        max_concurrent: int = 10,
    ) -> list[T]:
        """Execute tasks with semaphore-based concurrency limit.

        Args:
            tasks: List of coroutines to execute
            max_concurrent: Maximum concurrent tasks

        Returns:
            List of results
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def bounded_task(task: Coroutine[Any, Any, T]) -> T:
            async with semaphore:
                return await task

        return await asyncio.gather(*[bounded_task(task) for task in tasks])


class RateLimiter:
    """Token bucket rate limiter for request throttling."""

    def __init__(self, rate: int, per: float = 1.0):
        """Initialize rate limiter.

        Args:
            rate: Number of tokens
            per: Time period in seconds
        """
        self.rate = rate
        self.per = per
        self.allowance = rate
        self.last_check = datetime.now(UTC)
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> bool:
        """Acquire tokens from rate limiter.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if tokens acquired, False otherwise
        """
        async with self._lock:
            now = datetime.now(UTC)
            time_passed = (now - self.last_check).total_seconds()
            self.last_check = now

            # Replenish tokens
            self.allowance += time_passed * (self.rate / self.per)
            if self.allowance > self.rate:
                self.allowance = self.rate

            if self.allowance >= tokens:
                self.allowance -= tokens
                return True

            return False

    async def wait_for_token(self, tokens: int = 1) -> None:
        """Wait until tokens are available.

        Args:
            tokens: Number of tokens to wait for
        """
        while not await self.acquire(tokens):
            await asyncio.sleep(0.01)


class TaskQueue:
    """Async task queue with priority support."""

    def __init__(self, max_workers: int = 10):
        """Initialize task queue.

        Args:
            max_workers: Maximum concurrent workers
        """
        self.max_workers = max_workers
        self.queue: asyncio.PriorityQueue[tuple[int, Coroutine]] = asyncio.PriorityQueue()
        self.workers: list[asyncio.Task] = []
        self.results: dict[str, Any] = {}

    async def start(self) -> None:
        """Start task queue workers."""
        for _ in range(self.max_workers):
            worker = asyncio.create_task(self._worker())
            self.workers.append(worker)

    async def stop(self) -> None:
        """Stop task queue workers."""
        # Send stop signals
        for _ in range(self.max_workers):
            await self.queue.put((999, None))

        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)

    async def submit(
        self,
        task: Coroutine[Any, Any, T],
        priority: int = 0,
        task_id: str | None = None,
    ) -> str:
        """Submit task to queue.

        Args:
            task: Coroutine to execute
            priority: Task priority (lower = higher priority)
            task_id: Optional task identifier

        Returns:
            Task ID
        """
        task_id = task_id or f"task_{len(self.results)}"
        await self.queue.put((priority, (task_id, task)))
        return task_id

    async def _worker(self) -> None:
        """Worker coroutine."""
        while True:
            priority, item = await self.queue.get()

            if item is None:  # Stop signal
                break

            task_id, task = item
            try:
                result = await task
                self.results[task_id] = {"status": "completed", "result": result}
            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}")
                self.results[task_id] = {"status": "failed", "error": str(e)}

    def get_result(self, task_id: str) -> Any | None:
        """Get task result.

        Args:
            task_id: Task identifier

        Returns:
            Task result or None
        """
        return self.results.get(task_id)

    def stats(self) -> dict[str, Any]:
        """Get queue statistics.

        Returns:
            Queue statistics
        """
        completed = sum(1 for r in self.results.values() if r["status"] == "completed")
        failed = sum(1 for r in self.results.values() if r["status"] == "failed")

        return {
            "queue_size": self.queue.qsize(),
            "workers": self.max_workers,
            "completed_tasks": completed,
            "failed_tasks": failed,
            "total_tasks": len(self.results),
        }


class DeadlockDetector:
    """Detects potential deadlocks in concurrent operations."""

    def __init__(self, timeout: float = 30.0):
        """Initialize deadlock detector.

        Args:
            timeout: Timeout for detecting deadlocks
        """
        self.timeout = timeout
        self.active_tasks: dict[str, datetime] = {}

    async def monitor_task(
        self,
        task_id: str,
        task: Coroutine[Any, Any, T],
    ) -> T:
        """Monitor task for deadlock.

        Args:
            task_id: Task identifier
            task: Coroutine to execute

        Returns:
            Task result
        """
        self.active_tasks[task_id] = datetime.now(UTC)

        try:
            result = await asyncio.wait_for(task, timeout=self.timeout)
            return result
        except asyncio.TimeoutError:
            logger.error(f"Potential deadlock detected in task {task_id}")
            raise
        finally:
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]

    def get_stuck_tasks(self, threshold: float = 60.0) -> list[str]:
        """Get tasks that appear stuck.

        Args:
            threshold: Time threshold in seconds

        Returns:
            List of stuck task IDs
        """
        now = datetime.now(UTC)
        stuck = []

        for task_id, start_time in self.active_tasks.items():
            elapsed = (now - start_time).total_seconds()
            if elapsed > threshold:
                stuck.append(task_id)

        return stuck
