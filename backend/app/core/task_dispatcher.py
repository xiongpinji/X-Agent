"""
Task dispatcher module for X-Agent.

Implements task decomposition, intelligent allocation, and load balancing
for multi-agent collaboration.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task status enumeration."""

    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(int, Enum):
    """Task priority levels."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Task:
    """Represents a task."""

    id: str
    name: str
    description: str
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_duration_seconds: int = 0
    actual_duration_seconds: int = 0
    dependencies: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    result: Optional[dict] = None
    error: Optional[str] = None


@dataclass
class AgentCapacity:
    """Represents agent capacity and load."""

    agent_id: str
    max_concurrent_tasks: int = 5
    current_tasks: int = 0
    total_completed: int = 0
    avg_task_duration: float = 0.0
    success_rate: float = 1.0
    capabilities: list[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)

    def available_capacity(self) -> int:
        """Get available capacity."""
        return max(0, self.max_concurrent_tasks - self.current_tasks)

    def is_available(self) -> bool:
        """Check if agent has available capacity."""
        return self.available_capacity() > 0

    def load_percentage(self) -> float:
        """Get load percentage."""
        return (self.current_tasks / self.max_concurrent_tasks * 100
                if self.max_concurrent_tasks > 0 else 0)


@dataclass
class AllocationResult:
    """Result of task allocation."""

    task_id: str
    assigned_agent_id: Optional[str]
    allocation_score: float
    reason: str
    metadata: dict = field(default_factory=dict)


class TaskDispatcher:
    """
    Manages task decomposition and allocation across agents.

    Decomposes complex tasks into subtasks and intelligently allocates
    them to available agents based on capacity and capabilities.
    """

    def __init__(self, enable_load_balancing: bool = True):
        """
        Initialize the task dispatcher.

        Args:
            enable_load_balancing: Whether to enable load balancing
        """
        self.enable_load_balancing = enable_load_balancing
        self.tasks: dict[str, Task] = {}
        self.agent_capacities: dict[str, AgentCapacity] = {}
        self.logger = logger

    def register_agent(
        self,
        agent_id: str,
        max_concurrent_tasks: int = 5,
        capabilities: Optional[list[str]] = None,
    ) -> None:
        """
        Register an agent with the dispatcher.

        Args:
            agent_id: ID of the agent
            max_concurrent_tasks: Maximum concurrent tasks
            capabilities: List of agent capabilities
        """
        self.agent_capacities[agent_id] = AgentCapacity(
            agent_id=agent_id,
            max_concurrent_tasks=max_concurrent_tasks,
            capabilities=capabilities or [],
        )
        self.logger.debug(f"Registered agent: {agent_id}")

    def decompose_task(
        self,
        main_task: Task,
        max_subtasks: int = 5,
    ) -> list[Task]:
        """
        Decompose a complex task into subtasks.

        Args:
            main_task: Main task to decompose
            max_subtasks: Maximum number of subtasks

        Returns:
            List of subtasks
        """
        subtasks = []

        # Simple decomposition strategy based on task description
        description_parts = main_task.description.split(";")
        subtask_count = min(len(description_parts), max_subtasks)

        for i in range(subtask_count):
            subtask_id = f"{main_task.id}_subtask_{i}"
            subtask_description = (
                description_parts[i] if i < len(description_parts)
                else main_task.description
            )

            subtask = Task(
                id=subtask_id,
                name=f"{main_task.name} - Part {i + 1}",
                description=subtask_description,
                priority=main_task.priority,
                dependencies=[main_task.id] if i > 0 else [],
                metadata={
                    "parent_task_id": main_task.id,
                    "subtask_index": i,
                },
            )

            subtasks.append(subtask)
            self.tasks[subtask_id] = subtask

        self.logger.info(
            f"Decomposed task {main_task.id} into {len(subtasks)} subtasks"
        )

        return subtasks

    def allocate_tasks(
        self,
        tasks: list[Task],
        available_agents: Optional[list[str]] = None,
    ) -> list[AllocationResult]:
        """
        Allocate tasks to available agents.

        Args:
            tasks: List of tasks to allocate
            available_agents: List of available agent IDs

        Returns:
            List of allocation results
        """
        if available_agents is None:
            available_agents = list(self.agent_capacities.keys())

        results = []

        for task in tasks:
            # Find best agent for this task
            best_agent_id = self._find_best_agent(task, available_agents)

            if best_agent_id:
                allocation_score = self._calculate_allocation_score(
                    task, best_agent_id
                )
                result = AllocationResult(
                    task_id=task.id,
                    assigned_agent_id=best_agent_id,
                    allocation_score=allocation_score,
                    reason=f"Allocated to {best_agent_id} based on capacity and capabilities",
                )

                # Update task and agent
                task.assigned_agent_id = best_agent_id
                task.status = TaskStatus.ASSIGNED
                self.agent_capacities[best_agent_id].current_tasks += 1

                self.logger.debug(
                    f"Allocated task {task.id} to agent {best_agent_id}"
                )
            else:
                result = AllocationResult(
                    task_id=task.id,
                    assigned_agent_id=None,
                    allocation_score=0.0,
                    reason="No available agents with sufficient capacity",
                )

                self.logger.warning(f"Failed to allocate task {task.id}")

            results.append(result)

        return results

    def _find_best_agent(
        self,
        task: Task,
        available_agents: list[str],
    ) -> Optional[str]:
        """Find the best agent for a task."""
        best_agent_id = None
        best_score = -1.0

        for agent_id in available_agents:
            if agent_id not in self.agent_capacities:
                continue

            capacity = self.agent_capacities[agent_id]

            # Check if agent has capacity
            if not capacity.is_available():
                continue

            # Calculate score
            score = self._calculate_allocation_score(task, agent_id)

            if score > best_score:
                best_score = score
                best_agent_id = agent_id

        return best_agent_id

    def _calculate_allocation_score(self, task: Task, agent_id: str) -> float:
        """Calculate allocation score for a task-agent pair."""
        if agent_id not in self.agent_capacities:
            return 0.0

        capacity = self.agent_capacities[agent_id]

        # Base score from available capacity
        capacity_score = capacity.available_capacity() / capacity.max_concurrent_tasks

        # Capability match score
        capability_score = 0.0
        if task.metadata.get("required_capabilities"):
            required = set(task.metadata["required_capabilities"])
            agent_caps = set(capacity.capabilities)
            if required:
                capability_score = len(required & agent_caps) / len(required)

        # Success rate score
        success_score = capacity.success_rate

        # Priority boost
        priority_boost = task.priority.value / 4.0

        # Combined score
        score = (
            0.4 * capacity_score +
            0.3 * capability_score +
            0.2 * success_score +
            0.1 * priority_boost
        )

        return score

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        result: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> bool:
        """
        Update task status.

        Args:
            task_id: ID of task
            status: New status
            result: Task result
            error: Error message if failed

        Returns:
            True if successful
        """
        if task_id not in self.tasks:
            self.logger.warning(f"Task not found: {task_id}")
            return False

        task = self.tasks[task_id]
        old_status = task.status

        task.status = status
        task.result = result
        task.error = error

        if status == TaskStatus.IN_PROGRESS and not task.started_at:
            task.started_at = datetime.now()

        if status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            task.completed_at = datetime.now()
            if task.started_at:
                task.actual_duration_seconds = int(
                    (task.completed_at - task.started_at).total_seconds()
                )

            # Update agent capacity
            if task.assigned_agent_id:
                capacity = self.agent_capacities.get(task.assigned_agent_id)
                if capacity:
                    capacity.current_tasks = max(0, capacity.current_tasks - 1)
                    capacity.total_completed += 1

                    if status == TaskStatus.COMPLETED:
                        # Update success rate
                        total = capacity.total_completed
                        capacity.success_rate = (
                            (capacity.success_rate * (total - 1) + 1) / total
                        )

        self.logger.debug(
            f"Task {task_id} status changed: {old_status.value} -> {status.value}"
        )

        return True

    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get task status."""
        if task_id in self.tasks:
            return self.tasks[task_id].status
        return None

    def get_agent_load(self, agent_id: str) -> Optional[float]:
        """Get agent load percentage."""
        if agent_id in self.agent_capacities:
            return self.agent_capacities[agent_id].load_percentage()
        return None

    def get_dispatcher_stats(self) -> dict:
        """Get dispatcher statistics."""
        total_tasks = len(self.tasks)
        completed_tasks = sum(
            1 for t in self.tasks.values()
            if t.status == TaskStatus.COMPLETED
        )
        failed_tasks = sum(
            1 for t in self.tasks.values()
            if t.status == TaskStatus.FAILED
        )

        total_agents = len(self.agent_capacities)
        total_capacity = sum(
            c.max_concurrent_tasks for c in self.agent_capacities.values()
        )
        used_capacity = sum(
            c.current_tasks for c in self.agent_capacities.values()
        )

        return {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "pending_tasks": total_tasks - completed_tasks - failed_tasks,
            "total_agents": total_agents,
            "total_capacity": total_capacity,
            "used_capacity": used_capacity,
            "available_capacity": total_capacity - used_capacity,
            "utilization_rate": (
                used_capacity / total_capacity * 100
                if total_capacity > 0 else 0
            ),
        }

    def export_tasks(self) -> dict:
        """Export all tasks."""
        return {
            task_id: {
                "id": task.id,
                "name": task.name,
                "description": task.description,
                "priority": task.priority.value,
                "status": task.status.value,
                "assigned_agent_id": task.assigned_agent_id,
                "created_at": task.created_at.isoformat(),
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "estimated_duration_seconds": task.estimated_duration_seconds,
                "actual_duration_seconds": task.actual_duration_seconds,
                "dependencies": task.dependencies,
                "metadata": task.metadata,
                "result": task.result,
                "error": task.error,
            }
            for task_id, task in self.tasks.items()
        }


# Global instance
task_dispatcher = TaskDispatcher()
