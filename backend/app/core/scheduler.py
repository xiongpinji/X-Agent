"""
Scheduler module for X-Agent.

Implements cron-based and interval-based task scheduling.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class ScheduleType(StrEnum):
    """Types of schedules."""

    CRON = "cron"
    INTERVAL = "interval"
    ONCE = "once"


class ScheduleStatus(StrEnum):
    """Status of a scheduled task."""

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    DISABLED = "disabled"


@dataclass
class ScheduledTask:
    """Represents a scheduled task."""

    task_id: str
    name: str
    coroutine: Callable[[], Coroutine[Any, Any, Any]]
    schedule_type: ScheduleType
    cron_expression: str | None = None
    interval_seconds: int | None = None
    run_at: datetime | None = None
    status: ScheduleStatus = ScheduleStatus.ACTIVE
    max_runs: int | None = None
    run_count: int = 0
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScheduleExecution:
    """Record of a schedule execution."""

    execution_id: str
    task_id: str
    started_at: datetime
    completed_at: datetime | None = None
    status: str = "running"
    result: Any | None = None
    error: str | None = None
    duration_seconds: float = 0.0


class CronScheduler:
    """
    Manages cron-based and interval-based task scheduling.

    Supports cron expressions, fixed intervals, and one-time schedules.
    """

    def __init__(self):
        """Initialize the scheduler."""
        self.scheduled_tasks: dict[str, ScheduledTask] = {}
        self.execution_history: dict[str, list[ScheduleExecution]] = {}
        self.running_tasks: dict[str, asyncio.Task] = {}
        self.logger = logger

    def schedule_cron(
        self,
        name: str,
        coroutine: Callable[[], Coroutine[Any, Any, Any]],
        cron_expression: str,
        **kwargs,
    ) -> str:
        """
        Schedule a task using cron expression.

        Args:
            name: Name of the task
            coroutine: Coroutine to execute
            cron_expression: Cron expression (e.g., "0 9 * * *" for 9am daily)
            **kwargs: Additional options

        Returns:
            Task ID
        """
        task_id = f"task_{uuid.uuid4().hex[:12]}"

        task = ScheduledTask(
            task_id=task_id,
            name=name,
            coroutine=coroutine,
            schedule_type=ScheduleType.CRON,
            cron_expression=cron_expression,
            max_runs=kwargs.get("max_runs"),
            metadata=kwargs.get("metadata", {}),
        )

        self.scheduled_tasks[task_id] = task
        self.execution_history[task_id] = []

        # Calculate next run time
        task.next_run_at = self._calculate_next_cron_time(cron_expression)

        self.logger.info(
            f"Scheduled cron task {task_id} ({name}) with expression: {cron_expression}"
        )

        return task_id

    def schedule_interval(
        self,
        name: str,
        coroutine: Callable[[], Coroutine[Any, Any, Any]],
        interval_seconds: int,
        **kwargs,
    ) -> str:
        """
        Schedule a task with fixed interval.

        Args:
            name: Name of the task
            coroutine: Coroutine to execute
            interval_seconds: Interval in seconds
            **kwargs: Additional options

        Returns:
            Task ID
        """
        task_id = f"task_{uuid.uuid4().hex[:12]}"

        task = ScheduledTask(
            task_id=task_id,
            name=name,
            coroutine=coroutine,
            schedule_type=ScheduleType.INTERVAL,
            interval_seconds=interval_seconds,
            max_runs=kwargs.get("max_runs"),
            metadata=kwargs.get("metadata", {}),
        )

        self.scheduled_tasks[task_id] = task
        self.execution_history[task_id] = []

        # Calculate next run time
        task.next_run_at = datetime.now(UTC) + timedelta(seconds=interval_seconds)

        self.logger.info(
            f"Scheduled interval task {task_id} ({name}) with interval: {interval_seconds}s"
        )

        return task_id

    def schedule_once(
        self,
        name: str,
        coroutine: Callable[[], Coroutine[Any, Any, Any]],
        run_at: datetime,
        **kwargs,
    ) -> str:
        """
        Schedule a one-time task.

        Args:
            name: Name of the task
            coroutine: Coroutine to execute
            run_at: When to run the task
            **kwargs: Additional options

        Returns:
            Task ID
        """
        task_id = f"task_{uuid.uuid4().hex[:12]}"

        task = ScheduledTask(
            task_id=task_id,
            name=name,
            coroutine=coroutine,
            schedule_type=ScheduleType.ONCE,
            run_at=run_at,
            max_runs=1,
            metadata=kwargs.get("metadata", {}),
        )

        self.scheduled_tasks[task_id] = task
        self.execution_history[task_id] = []
        task.next_run_at = run_at

        self.logger.info(
            f"Scheduled one-time task {task_id} ({name}) to run at: {run_at}"
        )

        return task_id

    async def start(self) -> None:
        """Start the scheduler."""
        self.logger.info("Starting scheduler")

        while True:
            try:
                now = datetime.now(UTC)

                # Check all scheduled tasks (snapshot: 迭代期间 _execute_task/取消可能改字典，B5)
                for _task_id, task in list(self.scheduled_tasks.items()):
                    if task.status != ScheduleStatus.ACTIVE:
                        continue

                    # Check if max runs reached
                    if task.max_runs and task.run_count >= task.max_runs:
                        task.status = ScheduleStatus.COMPLETED
                        continue

                    # Check if it's time to run
                    if task.next_run_at and now >= task.next_run_at:
                        # Execute task
                        asyncio.create_task(self._execute_task(task))

                        # Calculate next run time
                        if task.schedule_type == ScheduleType.CRON:
                            task.next_run_at = self._calculate_next_cron_time(
                                task.cron_expression
                            )
                        elif task.schedule_type == ScheduleType.INTERVAL:
                            task.next_run_at = now + timedelta(
                                seconds=task.interval_seconds
                            )
                        elif task.schedule_type == ScheduleType.ONCE:
                            task.status = ScheduleStatus.COMPLETED

                await asyncio.sleep(1)  # Check every second

            except Exception as e:
                self.logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(5)

    async def _execute_task(self, task: ScheduledTask) -> None:
        """
        Execute a scheduled task.

        Args:
            task: Task to execute
        """
        execution_id = f"exec_{uuid.uuid4().hex[:12]}"
        execution = ScheduleExecution(
            execution_id=execution_id,
            task_id=task.task_id,
            started_at=datetime.now(UTC),
        )

        try:
            self.logger.info(f"Executing scheduled task {task.task_id} ({task.name})")

            # Execute coroutine
            result = await task.coroutine()

            execution.status = "completed"
            execution.result = result
            execution.completed_at = datetime.now(UTC)

            task.run_count += 1
            task.last_run_at = execution.completed_at

            self.logger.info(
                f"Task {task.task_id} completed (run #{task.run_count})"
            )

        except Exception as e:
            execution.status = "failed"
            execution.error = str(e)
            execution.completed_at = datetime.now(UTC)

            task.run_count += 1
            task.last_run_at = execution.completed_at

            self.logger.error(f"Task {task.task_id} failed: {e}")

        finally:
            execution.duration_seconds = (
                execution.completed_at - execution.started_at
            ).total_seconds()

            if task.task_id not in self.execution_history:
                self.execution_history[task.task_id] = []

            self.execution_history[task.task_id].append(execution)

    def pause_task(self, task_id: str) -> bool:
        """
        Pause a scheduled task.

        Args:
            task_id: ID of task to pause

        Returns:
            True if paused
        """
        if task_id not in self.scheduled_tasks:
            return False

        task = self.scheduled_tasks[task_id]
        task.status = ScheduleStatus.PAUSED

        self.logger.info(f"Task {task_id} paused")
        return True

    def resume_task(self, task_id: str) -> bool:
        """
        Resume a paused task.

        Args:
            task_id: ID of task to resume

        Returns:
            True if resumed
        """
        if task_id not in self.scheduled_tasks:
            return False

        task = self.scheduled_tasks[task_id]
        task.status = ScheduleStatus.ACTIVE

        self.logger.info(f"Task {task_id} resumed")
        return True

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a scheduled task.

        Args:
            task_id: ID of task to cancel

        Returns:
            True if cancelled
        """
        if task_id not in self.scheduled_tasks:
            return False

        task = self.scheduled_tasks[task_id]
        task.status = ScheduleStatus.DISABLED

        self.logger.info(f"Task {task_id} cancelled")
        return True

    def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """
        Get status of a scheduled task.

        Args:
            task_id: ID of task

        Returns:
            Task status dict or None
        """
        if task_id not in self.scheduled_tasks:
            return None

        task = self.scheduled_tasks[task_id]

        return {
            "task_id": task_id,
            "name": task.name,
            "status": task.status.value,
            "schedule_type": task.schedule_type.value,
            "cron_expression": task.cron_expression,
            "interval_seconds": task.interval_seconds,
            "run_count": task.run_count,
            "max_runs": task.max_runs,
            "last_run_at": task.last_run_at.isoformat() if task.last_run_at else None,
            "next_run_at": task.next_run_at.isoformat() if task.next_run_at else None,
            "created_at": task.created_at.isoformat(),
        }

    def list_tasks(self, status: str | None = None) -> list[dict[str, Any]]:
        """
        List scheduled tasks.

        Args:
            status: Filter by status

        Returns:
            List of task status dicts
        """
        tasks = []

        for task_id, task in self.scheduled_tasks.items():
            if status and task.status.value != status:
                continue

            tasks.append(self.get_task_status(task_id))

        return tasks

    def get_execution_history(
        self,
        task_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get execution history for a task.

        Args:
            task_id: ID of task
            limit: Maximum number of records

        Returns:
            List of execution records
        """
        if task_id not in self.execution_history:
            return []

        executions = self.execution_history[task_id][-limit:]

        return [
            {
                "execution_id": e.execution_id,
                "started_at": e.started_at.isoformat(),
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                "status": e.status,
                "duration_seconds": e.duration_seconds,
                "error": e.error,
            }
            for e in executions
        ]

    def _calculate_next_cron_time(self, cron_expression: str) -> datetime:
        """
        Calculate next run time for cron expression.

        Args:
            cron_expression: Cron expression

        Returns:
            Next run time
        """
        # Simplified: just add 1 day for now
        # In production, use croniter library
        return datetime.now(UTC) + timedelta(days=1)

    def get_scheduler_stats(self) -> dict[str, Any]:
        """
        Get scheduler statistics.

        Returns:
            Statistics dict
        """
        statuses = {}
        for task in self.scheduled_tasks.values():
            status = task.status.value
            statuses[status] = statuses.get(status, 0) + 1

        total_executions = sum(len(execs) for execs in self.execution_history.values())

        return {
            "total_tasks": len(self.scheduled_tasks),
            "status_breakdown": statuses,
            "total_executions": total_executions,
        }


# Global instance
cron_scheduler = CronScheduler()
