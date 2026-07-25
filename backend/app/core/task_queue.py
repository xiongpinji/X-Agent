"""Redis-based async task queue for X-Agent.

Provides a distributed task queue backed by Redis, replacing in-memory
task tracking. Supports priority queues, retries, dead-letter queue,
and task status tracking.

Usage:
    from backend.app.core.task_queue import task_queue, TaskPriority

    # Enqueue a task
    task_id = await task_queue.enqueue(
        "workflow.run",
        payload={"workflow_id": "wf-123", "input": {...}},
        priority=TaskPriority.HIGH,
    )

    # Check task status
    status = await task_queue.get_status(task_id)

    # Worker loop (in background)
    await task_queue.start_worker(concurrency=4)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

logger = logging.getLogger("xagent.task_queue")


class TaskPriority(IntEnum):
    """Task priority levels. Lower number = higher priority."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


class TaskStatus:
    """Task status constants."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD = "dead"  # In dead-letter queue


@dataclass
class Task:
    """Represents a queued task."""
    id: str
    name: str
    payload: dict[str, Any]
    priority: int = TaskPriority.NORMAL
    status: str = TaskStatus.PENDING
    retries: int = 0
    max_retries: int = 3
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    error: str | None = None
    result: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "payload": self.payload,
            "priority": self.priority,
            "status": self.status,
            "retries": self.retries,
            "max_retries": self.max_retries,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# Type for task handler functions
TaskHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, Any]]


class RedisTaskQueue:
    """Distributed task queue backed by Redis.

    Features:
    - Priority-based scheduling (sorted sets)
    - Automatic retries with exponential backoff
    - Dead-letter queue for permanently failed tasks
    - Task status tracking with TTL
    - Graceful shutdown

    Falls back to in-memory queue when Redis is unavailable.
    """

    # Redis key prefixes
    QUEUE_KEY = "xagent:task_queue"
    STATUS_PREFIX = "xagent:task_status:"
    DEAD_LETTER_KEY = "xagent:task_dlq"
    RESULT_PREFIX = "xagent:task_result:"

    def __init__(
        self,
        max_retries: int = 3,
        retry_backoff: float = 2.0,
        result_ttl: int = 3600,
        status_ttl: int = 86400,
    ) -> None:
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.result_ttl = result_ttl
        self.status_ttl = status_ttl

        self._handlers: dict[str, TaskHandler] = {}
        self._running = False
        self._workers: list[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()

        # In-memory fallback
        self._memory_queue: list[tuple[float, Task]] = []
        self._memory_status: dict[str, Task] = {}

    def register_handler(self, task_name: str, handler: TaskHandler) -> None:
        """Register a handler for a task type.

        Args:
            task_name: Task type identifier (e.g., "workflow.run").
            handler: Async function that processes the task payload.
        """
        self._handlers[task_name] = handler
        logger.info(f"Registered task handler: {task_name}")

    async def enqueue(
        self,
        task_name: str,
        payload: dict[str, Any] | None = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        max_retries: int | None = None,
        task_id: str | None = None,
    ) -> str:
        """Add a task to the queue.

        Args:
            task_name: Registered task type.
            payload: Task input data.
            priority: Task priority level.
            max_retries: Override default max retries.
            task_id: Custom task ID (auto-generated if None).

        Returns:
            Task ID for tracking.
        """
        task = Task(
            id=task_id or f"task-{uuid.uuid4().hex[:12]}",
            name=task_name,
            payload=payload or {},
            priority=int(priority),
            max_retries=max_retries if max_retries is not None else self.max_retries,
        )

        redis = await self._get_redis()
        if redis and redis.is_available:
            # Use Redis sorted set (score = priority * 1000000 + timestamp for FIFO within priority)
            score = task.priority * 1_000_000 + time.time()
            await redis.zadd(self.QUEUE_KEY, {json.dumps(task.to_dict()): score})
            await self._set_status(redis, task)
        else:
            # In-memory fallback
            score = task.priority * 1_000_000 + time.time()
            self._memory_queue.append((score, task))
            self._memory_queue.sort(key=lambda x: x[0])
            self._memory_status[task.id] = task

        logger.debug(f"Task enqueued: {task.id} ({task_name}, priority={priority.name})")
        return task.id

    async def get_status(self, task_id: str) -> dict[str, Any] | None:
        """Get task status.

        Args:
            task_id: Task identifier.

        Returns:
            Task status dict or None if not found.
        """
        redis = await self._get_redis()
        if redis and redis.is_available:
            raw = await redis.get(f"{self.STATUS_PREFIX}{task_id}")
            if raw:
                return json.loads(raw)
            return None
        else:
            task = self._memory_status.get(task_id)
            return task.to_dict() if task else None

    async def get_result(self, task_id: str) -> Any | None:
        """Get task result (available after completion)."""
        redis = await self._get_redis()
        if redis and redis.is_available:
            raw = await redis.get(f"{self.RESULT_PREFIX}{task_id}")
            if raw:
                return json.loads(raw)
            return None
        else:
            task = self._memory_status.get(task_id)
            return task.result if task and task.status == TaskStatus.COMPLETED else None

    async def cancel(self, task_id: str) -> bool:
        """Cancel a pending task.

        Returns:
            True if task was cancelled, False if already running/completed.
        """
        status = await self.get_status(task_id)
        if not status or status["status"] not in (TaskStatus.PENDING, TaskStatus.RETRYING):
            return False

        status["status"] = "cancelled"
        redis = await self._get_redis()
        if redis and redis.is_available:
            await redis.set(
                f"{self.STATUS_PREFIX}{task_id}",
                json.dumps(status),
                ex=self.status_ttl,
            )
        else:
            if task_id in self._memory_status:
                self._memory_status[task_id].status = "cancelled"
        return True

    async def start_worker(self, concurrency: int = 4) -> None:
        """Start background worker tasks.

        Args:
            concurrency: Number of concurrent task processors.
        """
        if self._running:
            logger.warning("Task queue worker already running")
            return

        self._running = True
        self._shutdown_event.clear()

        for i in range(concurrency):
            worker = asyncio.create_task(self._worker_loop(i))
            self._workers.append(worker)

        logger.info(f"Task queue started with {concurrency} workers")

    async def stop_worker(self, timeout: float = 30.0) -> None:
        """Gracefully stop workers.

        Args:
            timeout: Seconds to wait for workers to finish current tasks.
        """
        self._running = False
        self._shutdown_event.set()

        if self._workers:
            await asyncio.wait(self._workers, timeout=timeout)
            for worker in self._workers:
                if not worker.done():
                    worker.cancel()
            self._workers.clear()

        logger.info("Task queue workers stopped")

    async def get_queue_depth(self) -> int:
        """Get number of pending tasks in queue."""
        redis = await self._get_redis()
        if redis and redis.is_available:
            return await redis.zcard(self.QUEUE_KEY)
        return len(self._memory_queue)

    async def get_dead_letter_count(self) -> int:
        """Get number of tasks in dead-letter queue."""
        redis = await self._get_redis()
        if redis and redis.is_available:
            return await redis.zcard(self.DEAD_LETTER_KEY)
        return 0

    async def get_metrics(self) -> dict[str, Any]:
        """Get queue metrics for monitoring."""
        return {
            "queue_depth": await self.get_queue_depth(),
            "dead_letter_count": await self.get_dead_letter_count(),
            "registered_handlers": list(self._handlers.keys()),
            "workers_active": len([w for w in self._workers if not w.done()]),
            "running": self._running,
        }

    # ─── Internal ────────────────────────────────────────────────────────────────

    async def _worker_loop(self, worker_id: int) -> None:
        """Main worker loop: dequeue and process tasks."""
        logger.debug(f"Worker-{worker_id} started")

        while self._running:
            try:
                task = await self._dequeue()
                if task is None:
                    # No tasks available, wait before polling again
                    await asyncio.sleep(0.5)
                    continue

                await self._process_task(task, worker_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker-{worker_id} error: {e}", exc_info=True)
                await asyncio.sleep(1.0)

        logger.debug(f"Worker-{worker_id} stopped")

    async def _dequeue(self) -> Task | None:
        """Get next task from queue (highest priority, FIFO)."""
        redis = await self._get_redis()

        if redis and redis.is_available:
            # Pop lowest score (highest priority) from sorted set
            results = await redis.zrange(self.QUEUE_KEY, 0, 0)
            if not results:
                return None
            raw = results[0]
            await redis.zrem(self.QUEUE_KEY, raw)
            try:
                data = json.loads(raw)
                return Task.from_dict(data)
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(f"Failed to parse task from queue: {e}")
                return None
        else:
            if not self._memory_queue:
                return None
            _, task = self._memory_queue.pop(0)
            return task

    async def _process_task(self, task: Task, worker_id: int) -> None:
        """Process a single task with retry logic."""
        handler = self._handlers.get(task.name)
        if not handler:
            logger.error(f"No handler registered for task type: {task.name}")
            task.status = TaskStatus.FAILED
            task.error = f"No handler for task type: {task.name}"
            await self._update_status(task)
            return

        task.status = TaskStatus.RUNNING
        task.started_at = time.time()
        await self._update_status(task)

        try:
            result = await handler(task.payload)
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            task.result = result
            await self._update_status(task)
            await self._store_result(task)
            logger.debug(
                f"Task completed: {task.id} ({task.name}) "
                f"in {task.completed_at - task.started_at:.2f}s"
            )
        except Exception as e:
            task.retries += 1
            task.error = str(e)

            if task.retries < task.max_retries:
                # Retry with exponential backoff
                task.status = TaskStatus.RETRYING
                backoff = self.retry_backoff ** task.retries
                logger.warning(
                    f"Task {task.id} failed (attempt {task.retries}/{task.max_retries}), "
                    f"retrying in {backoff:.1f}s: {e}"
                )
                await self._update_status(task)
                await asyncio.sleep(backoff)
                # Re-enqueue
                await self.enqueue(
                    task.name,
                    task.payload,
                    priority=TaskPriority(task.priority),
                    max_retries=task.max_retries,
                    task_id=task.id,
                )
            else:
                # Move to dead-letter queue
                task.status = TaskStatus.DEAD
                task.completed_at = time.time()
                await self._update_status(task)
                await self._move_to_dlq(task)
                logger.error(
                    f"Task {task.id} permanently failed after {task.retries} attempts: {e}"
                )

    async def _move_to_dlq(self, task: Task) -> None:
        """Move failed task to dead-letter queue."""
        redis = await self._get_redis()
        if redis and redis.is_available:
            await redis.zadd(self.DEAD_LETTER_KEY, {json.dumps(task.to_dict()): time.time()})
        # In-memory DLQ not implemented (tasks just stay in status)

    async def _update_status(self, task: Task) -> None:
        """Persist task status."""
        redis = await self._get_redis()
        if redis and redis.is_available:
            await redis.set(
                f"{self.STATUS_PREFIX}{task.id}",
                json.dumps(task.to_dict()),
                ex=self.status_ttl,
            )
        else:
            self._memory_status[task.id] = task

    async def _store_result(self, task: Task) -> None:
        """Store task result with TTL."""
        redis = await self._get_redis()
        if redis and redis.is_available:
            result_data = json.dumps(task.result) if task.result is not None else "null"
            await redis.set(
                f"{self.RESULT_PREFIX}{task.id}",
                result_data,
                ex=self.result_ttl,
            )

    async def _set_status(self, redis: Any, task: Task) -> None:
        """Set initial task status in Redis."""
        await redis.set(
            f"{self.STATUS_PREFIX}{task.id}",
            json.dumps(task.to_dict()),
            ex=self.status_ttl,
        )

    async def _get_redis(self) -> Any:
        """Get Redis client (may be InMemoryFallback)."""
        try:
            from backend.app.core.redis_client import get_redis
            return get_redis()
        except Exception:
            return None


# Global task queue instance
task_queue = RedisTaskQueue()


# ─── Backward compatibility aliases ────────────────────────────────────────────
# The sandbox orchestrator and older tests import QueuedTask / TaskQueue from
# this module. Provide thin aliases so those imports keep working.

QueuedTask = Task


class TaskQueue:
    """Legacy in-memory task queue (backward compat wrapper around RedisTaskQueue)."""

    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._queue = RedisTaskQueue()

    async def enqueue(self, name: str, payload: dict[str, Any], priority: TaskPriority = TaskPriority.NORMAL, **kwargs) -> str:
        return await self._queue.enqueue(name, payload, priority=priority)

    async def dequeue(self, timeout_seconds: int | None = None) -> Task | None:
        return await self._queue._dequeue()

    async def size(self) -> int:
        return await self._queue.get_queue_depth()

    async def clear(self) -> int:
        count = await self._queue.get_queue_depth()
        self._queue._memory_queue.clear()
        return count


async def init_task_queue(concurrency: int = 4) -> RedisTaskQueue:
    """Initialize and start the global task queue.

    Call during application startup.
    """
    await task_queue.start_worker(concurrency=concurrency)
    return task_queue


async def shutdown_task_queue() -> None:
    """Gracefully shutdown the global task queue.

    Call during application shutdown.
    """
    await task_queue.stop_worker()
