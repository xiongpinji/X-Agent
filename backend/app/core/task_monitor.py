"""
Task monitoring module for X-Agent.

Monitors task execution and queue metrics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC, timedelta
from typing import Optional, Any, Dict, List
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class TaskMetrics:
    """Metrics for a task."""

    task_id: str
    name: str
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_duration_seconds: float = 0.0
    avg_duration_seconds: float = 0.0
    min_duration_seconds: float = float("inf")
    max_duration_seconds: float = 0.0
    last_execution_at: Optional[datetime] = None
    last_error: Optional[str] = None
    success_rate: float = 0.0


@dataclass
class QueueMetrics:
    """Metrics for a task queue."""

    queue_size: int = 0
    max_queue_size: int = 0
    total_enqueued: int = 0
    total_dequeued: int = 0
    total_failed: int = 0
    avg_wait_time_seconds: float = 0.0
    avg_processing_time_seconds: float = 0.0
    throughput_per_minute: float = 0.0


class TaskMonitor:
    """
    Monitors task execution and queue metrics.

    Tracks performance, errors, and queue health.
    """

    def __init__(self, retention_hours: int = 24):
        """
        Initialize the task monitor.

        Args:
            retention_hours: How long to retain metrics
        """
        self.retention_hours = retention_hours
        self.task_metrics: Dict[str, TaskMetrics] = {}
        self.execution_times: Dict[str, List[float]] = defaultdict(list)
        self.execution_errors: Dict[str, List[str]] = defaultdict(list)
        self.queue_history: List[Dict[str, Any]] = []
        self.logger = logger

    def record_task_execution(
        self,
        task_id: str,
        name: str,
        duration_seconds: float,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """
        Record a task execution.

        Args:
            task_id: ID of task
            name: Name of task
            duration_seconds: Execution duration
            success: Whether execution succeeded
            error: Error message if failed
        """
        # Initialize metrics if needed
        if task_id not in self.task_metrics:
            self.task_metrics[task_id] = TaskMetrics(task_id=task_id, name=name)

        metrics = self.task_metrics[task_id]

        # Update metrics
        metrics.total_executions += 1
        metrics.total_duration_seconds += duration_seconds
        metrics.avg_duration_seconds = (
            metrics.total_duration_seconds / metrics.total_executions
        )
        metrics.min_duration_seconds = min(
            metrics.min_duration_seconds,
            duration_seconds,
        )
        metrics.max_duration_seconds = max(
            metrics.max_duration_seconds,
            duration_seconds,
        )
        metrics.last_execution_at = datetime.now(UTC)

        if success:
            metrics.successful_executions += 1
        else:
            metrics.failed_executions += 1
            metrics.last_error = error

        metrics.success_rate = (
            metrics.successful_executions / metrics.total_executions
        )

        # Store execution time
        self.execution_times[task_id].append(duration_seconds)

        # Store error if any
        if error:
            self.execution_errors[task_id].append(error)

        self.logger.debug(
            f"Recorded execution for task {task_id}: "
            f"duration={duration_seconds:.2f}s, success={success}"
        )

    def record_queue_metrics(
        self,
        queue_size: int,
        max_queue_size: int,
        total_enqueued: int,
        total_dequeued: int,
        total_failed: int,
    ) -> None:
        """
        Record queue metrics.

        Args:
            queue_size: Current queue size
            max_queue_size: Maximum queue size
            total_enqueued: Total tasks enqueued
            total_dequeued: Total tasks dequeued
            total_failed: Total tasks failed
        """
        metrics = {
            "timestamp": datetime.now(UTC).isoformat(),
            "queue_size": queue_size,
            "max_queue_size": max_queue_size,
            "total_enqueued": total_enqueued,
            "total_dequeued": total_dequeued,
            "total_failed": total_failed,
        }

        self.queue_history.append(metrics)

        # Clean up old history
        self._cleanup_old_history()

        self.logger.debug(f"Recorded queue metrics: size={queue_size}")

    def get_task_metrics(self, task_id: str) -> Optional[TaskMetrics]:
        """
        Get metrics for a task.

        Args:
            task_id: ID of task

        Returns:
            Task metrics or None
        """
        return self.task_metrics.get(task_id)

    def get_queue_metrics(self) -> QueueMetrics:
        """
        Get current queue metrics.

        Returns:
            Queue metrics
        """
        if not self.queue_history:
            return QueueMetrics()

        latest = self.queue_history[-1]

        # Calculate throughput
        if len(self.queue_history) > 1:
            prev = self.queue_history[-2]
            time_diff = (
                datetime.fromisoformat(latest["timestamp"]) -
                datetime.fromisoformat(prev["timestamp"])
            ).total_seconds()

            if time_diff > 0:
                dequeued_diff = latest["total_dequeued"] - prev["total_dequeued"]
                throughput = (dequeued_diff / time_diff) * 60  # per minute
            else:
                throughput = 0.0
        else:
            throughput = 0.0

        return QueueMetrics(
            queue_size=latest["queue_size"],
            max_queue_size=latest["max_queue_size"],
            total_enqueued=latest["total_enqueued"],
            total_dequeued=latest["total_dequeued"],
            total_failed=latest["total_failed"],
            throughput_per_minute=throughput,
        )

    def get_all_task_metrics(self) -> List[TaskMetrics]:
        """
        Get metrics for all tasks.

        Returns:
            List of task metrics
        """
        return list(self.task_metrics.values())

    def get_top_tasks_by_duration(self, limit: int = 10) -> List[TaskMetrics]:
        """
        Get top tasks by average duration.

        Args:
            limit: Maximum number of tasks

        Returns:
            List of task metrics sorted by duration
        """
        tasks = sorted(
            self.task_metrics.values(),
            key=lambda m: m.avg_duration_seconds,
            reverse=True,
        )

        return tasks[:limit]

    def get_top_tasks_by_failures(self, limit: int = 10) -> List[TaskMetrics]:
        """
        Get top tasks by failure count.

        Args:
            limit: Maximum number of tasks

        Returns:
            List of task metrics sorted by failures
        """
        tasks = sorted(
            self.task_metrics.values(),
            key=lambda m: m.failed_executions,
            reverse=True,
        )

        return tasks[:limit]

    def get_task_execution_history(
        self,
        task_id: str,
        limit: int = 100,
    ) -> List[float]:
        """
        Get execution time history for a task.

        Args:
            task_id: ID of task
            limit: Maximum number of records

        Returns:
            List of execution times
        """
        if task_id not in self.execution_times:
            return []

        return self.execution_times[task_id][-limit:]

    def get_task_error_history(
        self,
        task_id: str,
        limit: int = 100,
    ) -> List[str]:
        """
        Get error history for a task.

        Args:
            task_id: ID of task
            limit: Maximum number of records

        Returns:
            List of error messages
        """
        if task_id not in self.execution_errors:
            return []

        return self.execution_errors[task_id][-limit:]

    def get_queue_history(
        self,
        hours: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Get queue metrics history.

        Args:
            hours: Look back period in hours

        Returns:
            List of queue metrics
        """
        cutoff = datetime.now(UTC) - timedelta(hours=hours)

        return [
            m for m in self.queue_history
            if datetime.fromisoformat(m["timestamp"]) >= cutoff
        ]

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get overall health status.

        Returns:
            Health status dict
        """
        if not self.task_metrics:
            return {"status": "healthy", "message": "No tasks monitored"}

        # Calculate overall success rate
        total_executions = sum(m.total_executions for m in self.task_metrics.values())
        total_successful = sum(
            m.successful_executions for m in self.task_metrics.values()
        )

        if total_executions == 0:
            success_rate = 1.0
        else:
            success_rate = total_successful / total_executions

        # Determine health status
        if success_rate >= 0.95:
            status = "healthy"
        elif success_rate >= 0.80:
            status = "degraded"
        else:
            status = "unhealthy"

        # Find problematic tasks
        problematic_tasks = [
            m.task_id for m in self.task_metrics.values()
            if m.success_rate < 0.80
        ]

        return {
            "status": status,
            "overall_success_rate": success_rate,
            "total_tasks": len(self.task_metrics),
            "total_executions": total_executions,
            "problematic_tasks": problematic_tasks,
        }

    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get performance summary.

        Returns:
            Performance summary dict
        """
        if not self.task_metrics:
            return {}

        total_duration = sum(m.total_duration_seconds for m in self.task_metrics.values())
        avg_duration = total_duration / len(self.task_metrics)

        return {
            "total_tasks": len(self.task_metrics),
            "total_executions": sum(m.total_executions for m in self.task_metrics.values()),
            "total_duration_seconds": total_duration,
            "avg_task_duration_seconds": avg_duration,
            "slowest_task": max(
                self.task_metrics.values(),
                key=lambda m: m.avg_duration_seconds,
            ).task_id if self.task_metrics else None,
            "fastest_task": min(
                self.task_metrics.values(),
                key=lambda m: m.avg_duration_seconds,
            ).task_id if self.task_metrics else None,
        }

    def _cleanup_old_history(self) -> None:
        """Clean up old history records."""
        cutoff = datetime.now(UTC) - timedelta(hours=self.retention_hours)

        self.queue_history = [
            m for m in self.queue_history
            if datetime.fromisoformat(m["timestamp"]) >= cutoff
        ]

    def reset_metrics(self, task_id: Optional[str] = None) -> None:
        """
        Reset metrics.

        Args:
            task_id: ID of task to reset (None for all)
        """
        if task_id:
            if task_id in self.task_metrics:
                del self.task_metrics[task_id]
            if task_id in self.execution_times:
                del self.execution_times[task_id]
            if task_id in self.execution_errors:
                del self.execution_errors[task_id]
            self.logger.info(f"Reset metrics for task {task_id}")
        else:
            self.task_metrics.clear()
            self.execution_times.clear()
            self.execution_errors.clear()
            self.queue_history.clear()
            self.logger.info("Reset all metrics")


# Global instance
task_monitor = TaskMonitor()
