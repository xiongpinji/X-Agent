"""
Advanced concurrency control and rate limiting for X-Agent.

Implements:
- Semaphore-based concurrency limiting
- Adaptive concurrency adjustment
- Rate limiting with token bucket
- Priority queue management
- Backpressure handling
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """Task priority levels."""

    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class ConcurrencyStats:
    """Statistics for concurrency control."""

    current_limit: int = 10
    active_tasks: int = 0
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    peak_active: int = 0
    total_wait_time: float = 0.0
    last_adjustment_time: float = field(default_factory=time.time)
    adjustment_count: int = 0


class ConcurrencyLimiter:
    """
    Semaphore-based concurrency limiter with statistics.

    Features:
    - Fixed concurrency limiting
    - Statistics tracking
    - Context manager support
    """

    def __init__(self, max_concurrent: int = 10, name: str = "limiter") -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max_concurrent = max_concurrent
        self._name = name
        self._stats = ConcurrencyStats(current_limit=max_concurrent)
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a concurrency slot."""
        start_time = time.time()
        await self._semaphore.acquire()
        wait_time = time.time() - start_time

        async with self._lock:
            self._stats.active_tasks += 1
            self._stats.total_tasks += 1
            self._stats.total_wait_time += wait_time
            self._stats.peak_active = max(self._stats.peak_active, self._stats.active_tasks)

    def release(self, success: bool = True) -> None:
        """Release a concurrency slot."""
        self._semaphore.release()
        self._stats.active_tasks = max(0, self._stats.active_tasks - 1)

        if success:
            self._stats.successful_tasks += 1
        else:
            self._stats.failed_tasks += 1

    async def run(self, coro: Any, success_check: Optional[Callable] = None) -> Any:
        """Run a coroutine with concurrency limiting."""
        await self.acquire()
        try:
            result = await coro
            success = True
            if success_check:
                success = success_check(result)
            self.release(success=success)
            return result
        except Exception as e:
            self.release(success=False)
            raise

    def get_stats(self) -> dict[str, Any]:
        """Get limiter statistics."""
        total = self._stats.successful_tasks + self._stats.failed_tasks
        success_rate = self._stats.successful_tasks / total if total > 0 else 0
        avg_wait_time = (
            self._stats.total_wait_time / self._stats.total_tasks
            if self._stats.total_tasks > 0
            else 0
        )

        return {
            "name": self._name,
            "max_concurrent": self._max_concurrent,
            "active_tasks": self._stats.active_tasks,
            "total_tasks": self._stats.total_tasks,
            "successful_tasks": self._stats.successful_tasks,
            "failed_tasks": self._stats.failed_tasks,
            "peak_active": self._stats.peak_active,
            "success_rate": success_rate,
            "avg_wait_time": avg_wait_time,
        }

    async def __aenter__(self):
        """Async context manager entry."""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self.release(success=exc_type is None)


class AdaptiveConcurrencyLimiter:
    """
    Adaptive concurrency limiter that adjusts limits based on success/failure rates.

    Features:
    - Automatic limit adjustment
    - Backpressure handling
    - Statistics tracking
    """

    def __init__(
        self,
        initial_limit: int = 10,
        min_limit: int = 5,
        max_limit: int = 50,
        adjustment_interval: float = 60.0,
        success_threshold: float = 0.95,
        failure_threshold: float = 0.80,
        name: str = "adaptive_limiter",
    ) -> None:
        self._initial_limit = initial_limit
        self._min_limit = min_limit
        self._max_limit = max_limit
        self._adjustment_interval = adjustment_interval
        self._success_threshold = success_threshold
        self._failure_threshold = failure_threshold
        self._name = name

        self._semaphore = asyncio.Semaphore(initial_limit)
        self._stats = ConcurrencyStats(current_limit=initial_limit)
        self._lock = asyncio.Lock()
        self._last_adjustment = time.time()
        self._adjustment_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """Start the adaptive adjustment task."""
        if self._adjustment_task is None:
            self._adjustment_task = asyncio.create_task(self._adjustment_loop())

    async def acquire(self) -> None:
        """Acquire a concurrency slot."""
        start_time = time.time()
        await self._semaphore.acquire()
        wait_time = time.time() - start_time

        async with self._lock:
            self._stats.active_tasks += 1
            self._stats.total_tasks += 1
            self._stats.total_wait_time += wait_time
            self._stats.peak_active = max(self._stats.peak_active, self._stats.active_tasks)

    def release(self, success: bool = True) -> None:
        """Release a concurrency slot."""
        self._semaphore.release()
        self._stats.active_tasks = max(0, self._stats.active_tasks - 1)

        if success:
            self._stats.successful_tasks += 1
        else:
            self._stats.failed_tasks += 1

    async def run(self, coro: Any, success_check: Optional[Callable] = None) -> Any:
        """Run a coroutine with concurrency limiting and auto-adjustment."""
        await self.acquire()
        try:
            result = await coro
            success = True
            if success_check:
                success = success_check(result)
            self.release(success=success)
            return result
        except Exception as e:
            self.release(success=False)
            raise

    async def _adjustment_loop(self) -> None:
        """Periodically adjust concurrency limit based on success/failure rates."""
        while True:
            try:
                await asyncio.sleep(self._adjustment_interval)
                await self._adjust_limit()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self._name}] Adjustment loop error: {e}")

    async def _adjust_limit(self) -> None:
        """Adjust concurrency limit based on success/failure rates."""
        async with self._lock:
            total = self._stats.successful_tasks + self._stats.failed_tasks
            if total < 10:
                return  # Not enough data to adjust

            success_rate = self._stats.successful_tasks / total
            current_limit = self._stats.current_limit

            if success_rate > self._success_threshold:
                # Increase limit
                new_limit = min(current_limit + 1, self._max_limit)
                if new_limit > current_limit:
                    self._semaphore = asyncio.Semaphore(new_limit)
                    self._stats.current_limit = new_limit
                    self._stats.adjustment_count += 1
                    logger.info(
                        f"[{self._name}] Increased limit to {new_limit} "
                        f"(success rate: {success_rate:.2%})"
                    )
            elif success_rate < self._failure_threshold:
                # Decrease limit
                new_limit = max(current_limit - 1, self._min_limit)
                if new_limit < current_limit:
                    self._semaphore = asyncio.Semaphore(new_limit)
                    self._stats.current_limit = new_limit
                    self._stats.adjustment_count += 1
                    logger.warning(
                        f"[{self._name}] Decreased limit to {new_limit} "
                        f"(success rate: {success_rate:.2%})"
                    )

            # Reset counters
            self._stats.successful_tasks = 0
            self._stats.failed_tasks = 0
            self._stats.last_adjustment_time = time.time()

    def get_stats(self) -> dict[str, Any]:
        """Get concurrency statistics."""
        total = self._stats.successful_tasks + self._stats.failed_tasks
        success_rate = self._stats.successful_tasks / total if total > 0 else 0
        avg_wait_time = (
            self._stats.total_wait_time / self._stats.total_tasks
            if self._stats.total_tasks > 0
            else 0
        )

        return {
            "name": self._name,
            "current_limit": self._stats.current_limit,
            "active_tasks": self._stats.active_tasks,
            "total_tasks": self._stats.total_tasks,
            "successful_tasks": self._stats.successful_tasks,
            "failed_tasks": self._stats.failed_tasks,
            "peak_active": self._stats.peak_active,
            "success_rate": success_rate,
            "avg_wait_time": avg_wait_time,
            "adjustment_count": self._stats.adjustment_count,
        }

    async def close(self) -> None:
        """Close the limiter."""
        if self._adjustment_task:
            self._adjustment_task.cancel()
            try:
                await self._adjustment_task
            except asyncio.CancelledError:
                pass


class RateLimiter:
    """
    Token bucket rate limiter.

    Features:
    - Token bucket algorithm
    - Configurable rate and burst
    - Statistics tracking
    """

    def __init__(
        self,
        rate: float = 100.0,
        burst: int = 100,
        name: str = "rate_limiter",
    ) -> None:
        self._rate = rate  # tokens per second
        self._burst = burst  # max tokens
        self._tokens = float(burst)
        self._name = name
        self._last_update = time.time()
        self._lock = asyncio.Lock()
        self._total_requests = 0
        self._rejected_requests = 0

    async def acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens. Returns True if successful."""
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_update
            self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
            self._last_update = now

            self._total_requests += 1

            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            else:
                self._rejected_requests += 1
                return False

    async def wait_for_token(self, tokens: int = 1) -> None:
        """Wait until tokens are available."""
        while not await self.acquire(tokens):
            await asyncio.sleep(0.01)

    def get_stats(self) -> dict[str, Any]:
        """Get rate limiter statistics."""
        total = self._total_requests
        rejection_rate = self._rejected_requests / total if total > 0 else 0

        return {
            "name": self._name,
            "rate": self._rate,
            "burst": self._burst,
            "current_tokens": self._tokens,
            "total_requests": self._total_requests,
            "rejected_requests": self._rejected_requests,
            "rejection_rate": rejection_rate,
        }


class PriorityTaskQueue:
    """
    Async task queue with priority support and backpressure.

    Features:
    - Priority-based task execution
    - Backpressure handling
    - Task timeout
    - Statistics tracking
    """

    def __init__(
        self,
        max_queue_size: int = 1000,
        worker_count: int = 4,
        name: str = "task_queue",
    ) -> None:
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_queue_size)
        self._worker_count = worker_count
        self._workers: list[asyncio.Task] = []
        self._running = False
        self._name = name
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

        logger.info(f"[{self._name}] Started with {self._worker_count} workers")

    async def stop(self) -> None:
        """Stop the task queue workers."""
        self._running = False
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info(f"[{self._name}] Stopped")

    async def enqueue(
        self,
        task: Callable,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: Optional[float] = None,
    ) -> None:
        """Enqueue a task."""
        try:
            await asyncio.wait_for(
                self._queue.put((priority.value, time.time(), task)),
                timeout=timeout or 30.0,
            )
            async with self._lock:
                self._total_tasks += 1
        except asyncio.TimeoutError:
            logger.error(f"[{self._name}] Task enqueue timeout")
            raise

    async def _worker(self, worker_id: int) -> None:
        """Worker coroutine."""
        while self._running:
            try:
                priority, enqueue_time, task = await asyncio.wait_for(
                    self._queue.get(), timeout=1.0
                )
                wait_time = time.time() - enqueue_time

                try:
                    if asyncio.iscoroutinefunction(task):
                        await task()
                    else:
                        task()

                    async with self._lock:
                        self._completed_tasks += 1
                except Exception as e:
                    logger.error(f"[{self._name}] Task execution error: {e}")
                    async with self._lock:
                        self._failed_tasks += 1

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self._name}] Worker error: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get queue statistics."""
        return {
            "name": self._name,
            "total_tasks": self._total_tasks,
            "completed_tasks": self._completed_tasks,
            "failed_tasks": self._failed_tasks,
            "queue_size": self._queue.qsize(),
            "worker_count": self._worker_count,
        }


# Global limiter instances
_limiters: dict[str, ConcurrencyLimiter] = {}
_adaptive_limiters: dict[str, AdaptiveConcurrencyLimiter] = {}
_rate_limiters: dict[str, RateLimiter] = {}
_task_queues: dict[str, PriorityTaskQueue] = {}


def get_limiter(name: str, max_concurrent: int = 10) -> ConcurrencyLimiter:
    """Get or create a concurrency limiter."""
    if name not in _limiters:
        _limiters[name] = ConcurrencyLimiter(max_concurrent, name)
    return _limiters[name]


def get_adaptive_limiter(
    name: str,
    initial_limit: int = 10,
    min_limit: int = 5,
    max_limit: int = 50,
) -> AdaptiveConcurrencyLimiter:
    """Get or create an adaptive concurrency limiter."""
    if name not in _adaptive_limiters:
        _adaptive_limiters[name] = AdaptiveConcurrencyLimiter(
            initial_limit=initial_limit,
            min_limit=min_limit,
            max_limit=max_limit,
            name=name,
        )
    return _adaptive_limiters[name]


def get_rate_limiter(name: str, rate: float = 100.0, burst: int = 100) -> RateLimiter:
    """Get or create a rate limiter."""
    if name not in _rate_limiters:
        _rate_limiters[name] = RateLimiter(rate=rate, burst=burst, name=name)
    return _rate_limiters[name]


def get_task_queue(
    name: str, max_queue_size: int = 1000, worker_count: int = 4
) -> PriorityTaskQueue:
    """Get or create a task queue."""
    if name not in _task_queues:
        _task_queues[name] = PriorityTaskQueue(
            max_queue_size=max_queue_size, worker_count=worker_count, name=name
        )
    return _task_queues[name]


async def close_all_limiters() -> None:
    """Close all global limiters."""
    global _adaptive_limiters

    for limiter in _adaptive_limiters.values():
        await limiter.close()

    _adaptive_limiters.clear()
    logger.info("All limiters closed")


async def close_all_queues() -> None:
    """Close all global task queues."""
    global _task_queues

    for queue in _task_queues.values():
        await queue.stop()

    _task_queues.clear()
    logger.info("All task queues closed")
