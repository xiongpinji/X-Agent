"""Monitoring and performance tracking for multi-agent collaboration."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TaskMetrics:
    """Metrics for a single task."""

    task_id: str
    agent_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: float = 0.0
    status: str = "running"  # running, completed, failed
    error: Optional[str] = None
    retries: int = 0
    result_size: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_duration(self) -> float:
        """Get task duration in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.now(UTC) - self.start_time).total_seconds()


@dataclass
class AgentMetrics:
    """Metrics for an agent."""

    agent_id: str
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_execution_time: float = 0.0
    average_execution_time: float = 0.0
    peak_load: int = 0
    current_load: int = 0
    uptime: float = 0.0
    last_activity: datetime = field(default_factory=lambda: datetime.now(UTC))
    error_rate: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_success_rate(self) -> float:
        """Get success rate as percentage."""
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100


@dataclass
class CollaborationMetrics:
    """Metrics for overall collaboration."""

    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    end_time: Optional[datetime] = None
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_agents: int = 0
    active_agents: int = 0
    total_execution_time: float = 0.0
    average_task_time: float = 0.0
    bottleneck_agent: Optional[str] = None
    bottleneck_duration: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_duration(self) -> float:
        """Get collaboration duration in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.now(UTC) - self.start_time).total_seconds()

    def get_success_rate(self) -> float:
        """Get success rate as percentage."""
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100


class CollaborationMonitor:
    """Monitors and tracks collaboration metrics."""

    def __init__(self, window_size: int = 100) -> None:
        self._task_metrics: dict[str, TaskMetrics] = {}
        self._agent_metrics: dict[str, AgentMetrics] = {}
        self._collaboration_metrics: Optional[CollaborationMetrics] = None
        self._lock = asyncio.Lock()
        self._window_size = window_size
        self._metric_history: list[dict[str, Any]] = []

    async def start_collaboration(self) -> None:
        """Start monitoring collaboration."""
        async with self._lock:
            self._collaboration_metrics = CollaborationMetrics()
            logger.info("Started collaboration monitoring")

    async def end_collaboration(self) -> Optional[CollaborationMetrics]:
        """End monitoring collaboration."""
        async with self._lock:
            if self._collaboration_metrics:
                self._collaboration_metrics.end_time = datetime.now(UTC)
                self._collaboration_metrics.total_execution_time = (
                    self._collaboration_metrics.get_duration()
                )
                logger.info("Ended collaboration monitoring")
                return self._collaboration_metrics
        return None

    async def start_task(self, task_id: str, agent_id: str) -> TaskMetrics:
        """Start tracking a task.

        Args:
            task_id: ID of the task
            agent_id: ID of the agent

        Returns:
            TaskMetrics object
        """
        metrics = TaskMetrics(
            task_id=task_id,
            agent_id=agent_id,
            start_time=datetime.now(UTC),
        )

        async with self._lock:
            self._task_metrics[task_id] = metrics
            if agent_id not in self._agent_metrics:
                self._agent_metrics[agent_id] = AgentMetrics(agent_id=agent_id)
            self._agent_metrics[agent_id].total_tasks += 1
            self._agent_metrics[agent_id].current_load += 1

            if self._collaboration_metrics:
                self._collaboration_metrics.total_tasks += 1

        logger.debug(f"Started tracking task {task_id} on agent {agent_id}")
        return metrics

    async def end_task(
        self,
        task_id: str,
        status: str = "completed",
        error: Optional[str] = None,
        result_size: int = 0,
    ) -> Optional[TaskMetrics]:
        """End tracking a task.

        Args:
            task_id: ID of the task
            status: Final status
            error: Error message if any
            result_size: Size of result in bytes

        Returns:
            TaskMetrics object or None if not found
        """
        async with self._lock:
            if task_id not in self._task_metrics:
                return None

            metrics = self._task_metrics[task_id]
            metrics.end_time = datetime.now(UTC)
            metrics.duration = metrics.get_duration()
            metrics.status = status
            metrics.error = error
            metrics.result_size = result_size

            agent_id = metrics.agent_id
            if agent_id in self._agent_metrics:
                agent_metrics = self._agent_metrics[agent_id]
                agent_metrics.current_load = max(0, agent_metrics.current_load - 1)
                agent_metrics.total_execution_time += metrics.duration

                if status == "completed":
                    agent_metrics.completed_tasks += 1
                elif status == "failed":
                    agent_metrics.failed_tasks += 1

                if agent_metrics.total_tasks > 0:
                    agent_metrics.average_execution_time = (
                        agent_metrics.total_execution_time / agent_metrics.total_tasks
                    )
                    agent_metrics.error_rate = (
                        agent_metrics.failed_tasks / agent_metrics.total_tasks
                    )

                agent_metrics.last_activity = datetime.now(UTC)

            if self._collaboration_metrics:
                if status == "completed":
                    self._collaboration_metrics.completed_tasks += 1
                elif status == "failed":
                    self._collaboration_metrics.failed_tasks += 1

        logger.debug(f"Ended tracking task {task_id} with status {status}")
        return metrics

    async def record_retry(self, task_id: str) -> None:
        """Record a task retry.

        Args:
            task_id: ID of the task
        """
        async with self._lock:
            if task_id in self._task_metrics:
                self._task_metrics[task_id].retries += 1

    async def get_task_metrics(self, task_id: str) -> Optional[TaskMetrics]:
        """Get metrics for a task.

        Args:
            task_id: ID of the task

        Returns:
            TaskMetrics or None if not found
        """
        return self._task_metrics.get(task_id)

    async def get_agent_metrics(self, agent_id: str) -> Optional[AgentMetrics]:
        """Get metrics for an agent.

        Args:
            agent_id: ID of the agent

        Returns:
            AgentMetrics or None if not found
        """
        return self._agent_metrics.get(agent_id)

    async def get_collaboration_metrics(self) -> Optional[CollaborationMetrics]:
        """Get overall collaboration metrics.

        Returns:
            CollaborationMetrics or None if not started
        """
        return self._collaboration_metrics

    async def get_all_agent_metrics(self) -> list[AgentMetrics]:
        """Get metrics for all agents.

        Returns:
            List of AgentMetrics
        """
        return list(self._agent_metrics.values())

    async def get_bottleneck_analysis(self) -> dict[str, Any]:
        """Analyze bottlenecks in collaboration.

        Returns:
            Dictionary with bottleneck information
        """
        async with self._lock:
            if not self._agent_metrics:
                return {}

            agent_metrics_list = list(self._agent_metrics.values())
            slowest_agent = max(
                agent_metrics_list,
                key=lambda m: m.average_execution_time,
                default=None,
            )

            most_loaded_agent = max(
                agent_metrics_list,
                key=lambda m: m.peak_load,
                default=None,
            )

            highest_error_rate_agent = max(
                agent_metrics_list,
                key=lambda m: m.error_rate,
                default=None,
            )

            return {
                "slowest_agent": {
                    "agent_id": slowest_agent.agent_id if slowest_agent else None,
                    "avg_time": slowest_agent.average_execution_time if slowest_agent else 0,
                },
                "most_loaded_agent": {
                    "agent_id": most_loaded_agent.agent_id if most_loaded_agent else None,
                    "peak_load": most_loaded_agent.peak_load if most_loaded_agent else 0,
                },
                "highest_error_rate_agent": {
                    "agent_id": highest_error_rate_agent.agent_id if highest_error_rate_agent else None,
                    "error_rate": highest_error_rate_agent.error_rate if highest_error_rate_agent else 0,
                },
            }

    async def get_performance_summary(self) -> dict[str, Any]:
        """Get performance summary.

        Returns:
            Dictionary with performance metrics
        """
        async with self._lock:
            collab_metrics = self._collaboration_metrics
            if not collab_metrics:
                return {}

            agent_metrics_list = list(self._agent_metrics.values())
            total_agents = len(agent_metrics_list)
            active_agents = len([m for m in agent_metrics_list if m.current_load > 0])

            return {
                "duration": collab_metrics.get_duration(),
                "total_tasks": collab_metrics.total_tasks,
                "completed_tasks": collab_metrics.completed_tasks,
                "failed_tasks": collab_metrics.failed_tasks,
                "success_rate": collab_metrics.get_success_rate(),
                "total_agents": total_agents,
                "active_agents": active_agents,
                "average_task_time": (
                    collab_metrics.total_execution_time / collab_metrics.total_tasks
                    if collab_metrics.total_tasks > 0
                    else 0
                ),
            }

    async def export_metrics(self) -> dict[str, Any]:
        """Export all metrics.

        Returns:
            Dictionary with all metrics
        """
        async with self._lock:
            return {
                "collaboration": self._collaboration_metrics,
                "agents": self._agent_metrics,
                "tasks": self._task_metrics,
            }
