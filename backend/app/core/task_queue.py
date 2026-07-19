"""
Task queue module for X-Agent.

Implements priority-based task queue for task management.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Optional, Any, Dict, List
import heapq
import uuid

logger = logging.getLogger(__name__)


class TaskPriority(int, Enum):
    """Task priority levels."""

    LOWEST = 5
    LOW = 4
    NORMAL = 3
    HIGH = 2
    CRITICAL = 1


class TaskQueueStatus(str, Enum):
    """Status of task queue."""

    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


@dataclass
class QueuedTask:
    """Represents a task in the queue."""

    task_id: str
    name: str
    payload: Dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    enqueued_at: Optional[datetime] = None
    dequeued_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __lt__(self, other: QueuedTask) -> bool:
        """Compare tasks by priority (for heap)."""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        return self.created_at < other.created_at


class TaskQueue:
    """
    Priority-based task queue.

    Manages task queuing with priority support and metrics.
    """

    def __init__(self, max_size: int = 10000):
        """
        Initialize the task queue.

        Args:
            max_size: Maximum queue size
        """
        self.max_size = max_size
        self.queue: List[QueuedTask] = []
        self.task_map: Dict[str, QueuedTask] = {}
        self.status = TaskQueueStatus.RUNNING
        self.lock = asyncio.Lock()
        self.not_empty = asyncio.Condition(self.lock)
        self.logger = logger
        self.stats = {
            "total_enqueued": 0,
            "total_dequeued": 0,
            "total_retried": 0,
        }

    async def enqueue(
        self,
        name: str,
        payload: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        **kwargs,
    ) -> str:
        """
        Add a task to the queue.

        Args:
            name: Name of the task
            payload: Task payload
            priority: Task priority
            **kwargs: Additional options

        Returns:
            Task ID

        Raises:
            RuntimeError: If queue is full or stopped
        """
        async with self.not_empty:
            if self.status == TaskQueueStatus.STOPPED:
                raise RuntimeError("Queue is stopped")

            if len(self.queue) >= self.max_size:
                raise RuntimeError(f"Queue is full (max: {self.max_size})")

            task_id = f"task_{uuid.uuid4().hex[:12]}"
            task = QueuedTask(
                task_id=task_id,
                name=name,
                payload=payload,
                priority=priority,
                enqueued_at=datetime.now(UTC),
                max_retries=kwargs.get("max_retries", 3),
                metadata=kwargs.get("metadata", {}),
            )

            heapq.heappush(self.queue, task)
            self.task_map[task_id] = task
            self.stats["total_enqueued"] += 1

            self.logger.debug(
                f"Task {task_id} ({name}) enqueued with priority {priority.name}"
            )

            self.not_empty.notify()
            return task_id

    async def dequeue(self, timeout_seconds: Optional[int] = None) -> Optional[QueuedTask]:
        """
        Remove and return highest priority task.

        Args:
            timeout_seconds: Timeout in seconds

        Returns:
            Task or None if timeout

        Raises:
            RuntimeError: If queue is stopped
        """
        async with self.not_empty:
            if self.status == TaskQueueStatus.STOPPED:
                raise RuntimeError("Queue is stopped")

            # Wait for task if queue is empty
            start_time = datetime.now(UTC)

            while not self.queue:
                if self.status == TaskQueueStatus.PAUSED:
                    await asyncio.sleep(1)
                    continue

                if timeout_seconds:
                    elapsed = (datetime.now(UTC) - start_time).total_seconds()
                    if elapsed > timeout_seconds:
                        return None

                    remaining = timeout_seconds - elapsed
                    try:
                        await asyncio.wait_for(
                            self.not_empty.wait(),
                            timeout=remaining,
                        )
                    except asyncio.TimeoutError:
                        return None
                else:
                    await self.not_empty.wait()

            task = heapq.heappop(self.queue)
            task.dequeued_at = datetime.now(UTC)
            self.stats["total_dequeued"] += 1

            self.logger.debug(f"Task {task.task_id} ({task.name}) dequeued")

            return task

    async def peek(self) -> Optional[QueuedTask]:
        """
        View highest priority task without removing.

        Returns:
            Task or None if queue is empty
        """
        async with self.lock:
            if self.queue:
                return self.queue[0]
            return None

    async def size(self) -> int:
        """
        Get queue size.

        Returns:
            Number of tasks in queue
        """
        async with self.lock:
            return len(self.queue)

    async def clear(self) -> int:
        """
        Clear all tasks from queue.

        Returns:
            Number of tasks cleared
        """
        async with self.lock:
            count = len(self.queue)
            self.queue.clear()
            self.task_map.clear()
            self.logger.info(f"Cleared {count} tasks from queue")
            return count

    async def remove_task(self, task_id: str) -> bool:
        """
        Remove a specific task from queue.

        Args:
            task_id: ID of task to remove

        Returns:
            True if removed
        """
        async with self.lock:
            if task_id not in self.task_map:
                return False

            task = self.task_map[task_id]
            self.queue.remove(task)
            heapq.heapify(self.queue)
            del self.task_map[task_id]

            self.logger.debug(f"Task {task_id} removed from queue")
            return True

    async def requeue_task(
        self,
        task_id: str,
        priority: Optional[TaskPriority] = None,
    ) -> bool:
        """
        Re-queue a task (for retries).

        Args:
            task_id: ID of task to re-queue
            priority: New priority (optional)

        Returns:
            True if re-queued
        """
        async with self.not_empty:
            if task_id not in self.task_map:
                return False

            task = self.task_map[task_id]

            if task.retry_count >= task.max_retries:
                self.logger.warning(
                    f"Task {task_id} exceeded max retries ({task.max_retries})"
                )
                return False

            # Remove from queue if still present. A task being re-queued for
            # retry has typically already been dequeued for execution, so it
            # won't be in self.queue (only in task_map). Guard the remove to
            # avoid ValueError: list.remove(x): x not in list.
            if task in self.queue:
                self.queue.remove(task)
                heapq.heapify(self.queue)

            # Update task
            task.retry_count += 1
            if priority:
                task.priority = priority

            # Re-add to queue
            heapq.heappush(self.queue, task)
            self.stats["total_retried"] += 1

            self.logger.info(
                f"Task {task_id} re-queued (retry {task.retry_count}/{task.max_retries})"
            )

            self.not_empty.notify()
            return True

    async def pause(self) -> None:
        """Pause the queue."""
        async with self.lock:
            self.status = TaskQueueStatus.PAUSED
            self.logger.info("Queue paused")

    async def resume(self) -> None:
        """Resume the queue."""
        async with self.not_empty:
            self.status = TaskQueueStatus.RUNNING
            self.logger.info("Queue resumed")
            self.not_empty.notify_all()

    async def stop(self) -> None:
        """Stop the queue."""
        async with self.not_empty:
            self.status = TaskQueueStatus.STOPPED
            self.logger.info("Queue stopped")
            self.not_empty.notify_all()

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a task.

        Args:
            task_id: ID of task

        Returns:
            Task status dict or None
        """
        async with self.lock:
            if task_id not in self.task_map:
                return None

            task = self.task_map[task_id]

            return {
                "task_id": task_id,
                "name": task.name,
                "priority": task.priority.name,
                "created_at": task.created_at.isoformat(),
                "enqueued_at": task.enqueued_at.isoformat() if task.enqueued_at else None,
                "dequeued_at": task.dequeued_at.isoformat() if task.dequeued_at else None,
                "retry_count": task.retry_count,
                "max_retries": task.max_retries,
            }

    async def list_tasks(
        self,
        priority: Optional[TaskPriority] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        List tasks in queue.

        Args:
            priority: Filter by priority
            limit: Maximum number of tasks

        Returns:
            List of task dicts
        """
        async with self.lock:
            tasks = []

            for task in self.queue[:limit]:
                if priority and task.priority != priority:
                    continue

                tasks.append({
                    "task_id": task.task_id,
                    "name": task.name,
                    "priority": task.priority.name,
                    "created_at": task.created_at.isoformat(),
                    "retry_count": task.retry_count,
                })

            return tasks

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics.

        Returns:
            Statistics dict
        """
        async with self.lock:
            priority_breakdown = {}
            for task in self.queue:
                priority = task.priority.name
                priority_breakdown[priority] = priority_breakdown.get(priority, 0) + 1

            return {
                "queue_size": len(self.queue),
                "max_size": self.max_size,
                "status": self.status.value,
                "priority_breakdown": priority_breakdown,
                "total_enqueued": self.stats["total_enqueued"],
                "total_dequeued": self.stats["total_dequeued"],
                "total_retried": self.stats["total_retried"],
            }


# Global instance
task_queue = TaskQueue()
