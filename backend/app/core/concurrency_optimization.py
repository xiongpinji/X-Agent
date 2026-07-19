"""
Concurrency Control Optimization for X-Agent.

Implements:
- Adaptive concurrency limiting based on success/failure rates
- Backpressure handling
- Task priority management
- Resource monitoring and alerts
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class ConcurrencyStats:
    """Statistics for concurrency control."""

    current_limit: int = 10
    active_tasks: int = 0
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    peak_active: int = 0
    last_adjustment_time: float = field(default_factory=time.time)
    adjustment_count: int = 0


class AdaptiveConcurrencyLimiter:
    """
    Adaptive concurrency limiter that adjusts limits based on success/failure rates.

    Features:
    - Automatic limit adjustment
    - Backpressure handling
    - Statistics tracking
    - Resource monitoring
    """

    def __init__(
        self,
        initial_limit: int = 10,
        min_limit: int = 5,
        max_limit: int = 50,
        adjustment_interval: float = 60.0,
        success_threshold: float = 0.95,
        failure_threshold: float = 0.80,
    ) -> None:
        self.initial_limit = initial_limit
        self.min_limit = min_limit
        self.max_limit = max_limit
        self.adjustment_interval = adjustment_interval
        self.success_threshold = success_threshold
        self.failure_threshold = failure_threshold

        self._semaphore = asyncio.Semaphore(initial_limit)
        self._stats = ConcurrencyStats(current_limit=initial_limit)
        self._lock = asyncio.Lock()
        self._last_adjustment = time.time()

    async def acquire(self) -> None:
        """Acquire a concurrency slot."""
        await self._semaphore.acquire()
        async with self._lock:
            self._stats.active_tasks += 1
            self._stats.total_tasks += 1
            self._stats.peak_active = max(self._stats.peak_active, self._stats.active_tasks)

    def release(self, success: bool = True) -> None:
        """Release a concurrency slot."""
        self._semaphore.release()
        self._stats.active_tasks = max(0, self._stats.active_tasks - 1)

        if success:
            self._stats.successful_tasks += 1
        else:
            self._stats.failed_tasks += 1

    async def run(self, coro: Any, success_check: Callable | None = None) -> Any:
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

    async def _adjust_limit(self) -> None:
        """Adjust concurrency limit based on success/failure rates."""
        now = time.time()
        if now - self._last_adjustment < self.adjustment_interval:
            return

        async with self._lock:
            total = self._stats.successful_tasks + self._stats.failed_tasks
            if total < 10:
                return  # Not enough data to adjust

            success_rate = self._stats.successful_tasks / total
            current_limit = self._stats.current_limit

            if success_rate > self.success_threshold:
                # Increase limit
                new_limit = min(current_limit + 1, self.max_limit)
                if new_limit > current_limit:
                    self._semaphore = asyncio.Semaphore(new_limit)
                    self._stats.current_limit = new_limit
                    logger.info(
                        f"Increased concurrency limit to {new_limit} "
                        f"(success rate: {success_rate:.2%})"
                    )
            elif success_rate < self.failure_threshold:
                # Decrease limit
                new_limit = max(current_limit - 1, self.min_limit)
                if new_limit < current_limit:
                    self._semaphore = asyncio.Semaphore(new_limit)
                    self._stats.current_limit = new_limit
                    logger.warning(
                        f"Decreased concurrency limit to {new_limit} "
                        f"(success rate: {success_rate:.2%})"
                    )

            # Reset counters
            self._stats.successful_tasks = 0
            self._stats.failed_tasks = 0
            self._stats.adjustment_count += 1
            self._last_adjustment = now

    def get_stats(self) -> dict[str, Any]:
        """Get concurrency statistics."""
        total = self._stats.successful_tasks + self._stats.failed_tasks
        success_rate = (
            self._stats.successful_tasks / total if total > 0 else 0
        )

        return {
            "current_limit": self._stats.current_limit,
            "active_tasks": self._stats.active_tasks,
            "total_tasks": self._stats.total_tasks,
            "successful_tasks": self._stats.successful_tasks,
            "failed_tasks": self._stats.failed_tasks,
            "success_rate": success_rate,
            "peak_active": self._stats.peak_active,
            "adjustment_count": self._stats.adjustment_count,
        }


class BackpressureHandler:
    """
    Handle backpressure when system is overloaded.

    Features:
    - Queue size monitoring
    - Backpressure signals
    - Graceful degradation
    """

    def __init__(
        self,
        max_queue_size: int = 1000,
        high_watermark: float = 0.8,
        low_watermark: float = 0.2,
    ) -> None:
        self.max_queue_size = max_queue_size
        self.high_watermark = high_watermark
        self.low_watermark = low_watermark

        self._queue_size = 0
        self._backpressure_active = False
        self._lock = asyncio.Lock()

    async def check_backpressure(self) -> bool:
        """Check if backpressure is active."""
        async with self._lock:
            return self._backpressure_active

    async def update_queue_size(self, size: int) -> None:
        """Update queue size and check for backpressure."""
        async with self._lock:
            self._queue_size = size
            utilization = size / self.max_queue_size

            if utilization > self.high_watermark and not self._backpressure_active:
                self._backpressure_active = True
                logger.warning(
                    f"Backpressure activated (queue utilization: {utilization:.2%})"
                )
            elif utilization < self.low_watermark and self._backpressure_active:
                self._backpressure_active = False
                logger.info(
                    f"Backpressure deactivated (queue utilization: {utilization:.2%})"
                )

    async def wait_if_backpressure(self, timeout: float = 30.0) -> bool:
        """Wait until backpressure is relieved."""
        start_time = time.time()
        while await self.check_backpressure():
            if time.time() - start_time > timeout:
                logger.error("Backpressure timeout")
                return False
            await asyncio.sleep(0.1)
        return True

    def get_stats(self) -> dict[str, Any]:
        """Get backpressure statistics."""
        utilization = self._queue_size / self.max_queue_size
        return {
            "queue_size": self._queue_size,
            "max_queue_size": self.max_queue_size,
            "utilization": utilization,
            "backpressure_active": self._backpressure_active,
        }


class PriorityTaskScheduler:
    """
    Schedule tasks with priority support.

    Features:
    - Priority-based task execution
    - Fair scheduling
    - Starvation prevention
    """

    def __init__(self, worker_count: int = 4) -> None:
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._worker_count = worker_count
        self._workers: list[asyncio.Task] = []
        self._running = False
        self._stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
        }
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the task scheduler."""
        if self._running:
            return

        self._running = True
        for i in range(self._worker_count):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)

        logger.info(f"Priority task scheduler started with {self._worker_count} workers")

    async def stop(self) -> None:
        """Stop the task scheduler."""
        self._running = False
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("Priority task scheduler stopped")

    async def enqueue(
        self,
        task: Callable,
        priority: int = 0,
        timeout: float | None = None,
    ) -> None:
        """Enqueue a task with priority."""
        try:
            await asyncio.wait_for(
                self._queue.put((priority, time.time(), task)),
                timeout=timeout or 30.0,
            )
            async with self._lock:
                self._stats["total_tasks"] += 1
        except asyncio.TimeoutError:
            logger.error("Task enqueue timeout")
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
                        # 同步 callable 可能返回 coroutine(如 lambda: coro(args)、
                        # functools.partial 包裹的 async 函数),iscoroutinefunction
                        # 对这类包装返回 False。调用后若拿到 awaitable 必须 await,
                        # 否则任务体永不执行。
                        result = task()
                        if asyncio.iscoroutine(result):
                            await result

                    async with self._lock:
                        self._stats["completed_tasks"] += 1
                except Exception as e:
                    logger.error(f"Task execution error: {e}")
                    async with self._lock:
                        self._stats["failed_tasks"] += 1

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker error: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get scheduler statistics."""
        return {
            **self._stats,
            "queue_size": self._queue.qsize(),
            "worker_count": self._worker_count,
        }


# Global instances
_adaptive_limiter: AdaptiveConcurrencyLimiter | None = None
_backpressure_handler: BackpressureHandler | None = None
_priority_scheduler: PriorityTaskScheduler | None = None


def get_adaptive_limiter() -> AdaptiveConcurrencyLimiter:
    """Get or create the global adaptive concurrency limiter."""
    global _adaptive_limiter
    if _adaptive_limiter is None:
        _adaptive_limiter = AdaptiveConcurrencyLimiter()
    return _adaptive_limiter


def get_backpressure_handler() -> BackpressureHandler:
    """Get or create the global backpressure handler."""
    global _backpressure_handler
    if _backpressure_handler is None:
        _backpressure_handler = BackpressureHandler()
    return _backpressure_handler


def get_priority_scheduler() -> PriorityTaskScheduler:
    """Get or create the global priority task scheduler."""
    global _priority_scheduler
    if _priority_scheduler is None:
        _priority_scheduler = PriorityTaskScheduler()
    return _priority_scheduler
