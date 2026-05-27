"""Task dispatcher for distributing work across agents."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Status of a task."""

    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DispatchStrategy(str, Enum):
    """Strategy for dispatching tasks to agents."""

    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    CAPABILITY_MATCH = "capability_match"
    PRIORITY_QUEUE = "priority_queue"
    RANDOM = "random"


@dataclass
class Task:
    """Represents a task to be executed by an agent."""

    task_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    action: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    required_capability: str = ""
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent_id: Optional[str] = None
    priority: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    timeout: float = 30.0
    retry_count: int = 0
    max_retries: int = 3
    result: Any = None
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    parent_task_id: Optional[str] = None
    subtasks: list[str] = field(default_factory=list)

    def get_execution_time(self) -> Optional[float]:
        """Get execution time in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def is_retryable(self) -> bool:
        """Check if task can be retried."""
        return self.retry_count < self.max_retries and self.status == TaskStatus.FAILED

    def mark_started(self) -> None:
        """Mark task as started."""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now(UTC)

    def mark_completed(self, result: Any) -> None:
        """Mark task as completed."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now(UTC)
        self.result = result

    def mark_failed(self, error: str) -> None:
        """Mark task as failed."""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now(UTC)
        self.error = error


class TaskDispatcher:
    """Dispatches tasks to agents based on strategy."""

    def __init__(self, strategy: DispatchStrategy = DispatchStrategy.LEAST_LOADED) -> None:
        self._tasks: dict[str, Task] = {}
        self._task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._strategy = strategy
        self._lock = asyncio.Lock()
        self._agent_tasks: dict[str, list[str]] = {}
        self._round_robin_index = 0

    async def submit_task(
        self,
        name: str,
        action: str,
        parameters: dict[str, Any],
        required_capability: str = "",
        priority: int = 0,
        timeout: float = 30.0,
        parent_task_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Task:
        """Submit a new task.

        Args:
            name: Task name
            action: Action to perform
            parameters: Action parameters
            required_capability: Required agent capability
            priority: Task priority (higher = more urgent)
            timeout: Task timeout in seconds
            parent_task_id: Parent task ID for subtasks
            metadata: Additional metadata

        Returns:
            Task object
        """
        task = Task(
            name=name,
            description=f"Execute {action}",
            action=action,
            parameters=parameters,
            required_capability=required_capability,
            priority=priority,
            timeout=timeout,
            parent_task_id=parent_task_id,
            metadata=metadata or {},
        )

        async with self._lock:
            self._tasks[task.task_id] = task
            await self._task_queue.put((-priority, task.task_id))

            if parent_task_id and parent_task_id in self._tasks:
                self._tasks[parent_task_id].subtasks.append(task.task_id)

        logger.info(f"Submitted task {task.task_id} ({name})")
        return task

    async def get_next_task(self) -> Optional[Task]:
        """Get next task from queue."""
        try:
            _, task_id = await asyncio.wait_for(self._task_queue.get(), timeout=1.0)
            return self._tasks.get(task_id)
        except asyncio.TimeoutError:
            return None

    async def assign_task(
        self,
        task_id: str,
        agent_id: str,
        agents: dict[str, Any],
    ) -> bool:
        """Assign a task to an agent.

        Args:
            task_id: ID of the task
            agent_id: ID of the agent
            agents: Dictionary of available agents

        Returns:
            True if assigned, False otherwise
        """
        async with self._lock:
            if task_id not in self._tasks:
                return False

            task = self._tasks[task_id]
            task.assigned_agent_id = agent_id
            task.status = TaskStatus.ASSIGNED

            if agent_id not in self._agent_tasks:
                self._agent_tasks[agent_id] = []
            self._agent_tasks[agent_id].append(task_id)

        logger.info(f"Assigned task {task_id} to agent {agent_id}")
        return True

    async def dispatch_task(
        self,
        task_id: str,
        agents: dict[str, Any],
    ) -> Optional[str]:
        """Dispatch a task to an appropriate agent.

        Args:
            task_id: ID of the task
            agents: Dictionary of available agents

        Returns:
            Agent ID if dispatched, None otherwise
        """
        if task_id not in self._tasks:
            return None

        task = self._tasks[task_id]
        agent_id = None

        if self._strategy == DispatchStrategy.ROUND_ROBIN:
            agent_id = self._dispatch_round_robin(agents)
        elif self._strategy == DispatchStrategy.LEAST_LOADED:
            agent_id = self._dispatch_least_loaded(agents)
        elif self._strategy == DispatchStrategy.CAPABILITY_MATCH:
            agent_id = self._dispatch_capability_match(task, agents)
        elif self._strategy == DispatchStrategy.PRIORITY_QUEUE:
            agent_id = self._dispatch_priority(task, agents)
        elif self._strategy == DispatchStrategy.RANDOM:
            import random
            agent_id = random.choice(list(agents.keys())) if agents else None

        if agent_id:
            await self.assign_task(task_id, agent_id, agents)

        return agent_id

    def _dispatch_round_robin(self, agents: dict[str, Any]) -> Optional[str]:
        """Round-robin dispatch strategy."""
        if not agents:
            return None

        agent_ids = list(agents.keys())
        agent_id = agent_ids[self._round_robin_index % len(agent_ids)]
        self._round_robin_index += 1
        return agent_id

    def _dispatch_least_loaded(self, agents: dict[str, Any]) -> Optional[str]:
        """Least-loaded dispatch strategy."""
        if not agents:
            return None

        return min(agents.keys(), key=lambda aid: agents[aid].get("load", 0))

    def _dispatch_capability_match(
        self,
        task: Task,
        agents: dict[str, Any],
    ) -> Optional[str]:
        """Capability-match dispatch strategy."""
        if not task.required_capability or not agents:
            return self._dispatch_least_loaded(agents)

        matching_agents = [
            aid for aid, agent in agents.items()
            if task.required_capability in agent.get("capabilities", [])
        ]

        if not matching_agents:
            return self._dispatch_least_loaded(agents)

        return min(matching_agents, key=lambda aid: agents[aid].get("load", 0))

    def _dispatch_priority(
        self,
        task: Task,
        agents: dict[str, Any],
    ) -> Optional[str]:
        """Priority-based dispatch strategy."""
        if not agents:
            return None

        def agent_score(agent_id: str) -> float:
            agent = agents[agent_id]
            load = agent.get("load", 0)
            capability_match = 1.0 if task.required_capability in agent.get("capabilities", []) else 0.5
            return load / capability_match

        return min(agents.keys(), key=agent_score)

    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        return self._tasks.get(task_id)

    async def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        agent_id: Optional[str] = None,
    ) -> list[Task]:
        """List tasks with optional filtering."""
        tasks = list(self._tasks.values())

        if status:
            tasks = [t for t in tasks if t.status == status]

        if agent_id:
            tasks = [t for t in tasks if t.assigned_agent_id == agent_id]

        return tasks

    async def get_dispatcher_stats(self) -> dict[str, Any]:
        """Get dispatcher statistics."""
        tasks = list(self._tasks.values())
        return {
            "total_tasks": len(tasks),
            "pending_tasks": len([t for t in tasks if t.status == TaskStatus.PENDING]),
            "running_tasks": len([t for t in tasks if t.status == TaskStatus.RUNNING]),
            "completed_tasks": len([t for t in tasks if t.status == TaskStatus.COMPLETED]),
            "failed_tasks": len([t for t in tasks if t.status == TaskStatus.FAILED]),
            "queue_size": self._task_queue.qsize(),
            "strategy": self._strategy.value,
        }
