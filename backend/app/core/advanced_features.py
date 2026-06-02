"""
Advanced features for X-Agent.
Implements multi-agent collaboration, task scheduling, resource management, and learning.
"""

from __future__ import annotations

import asyncio
import heapq
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional, List, Dict, Set
import uuid


class TaskPriority(int, Enum):
    """Task priority levels."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    DEFERRED = 4


class TaskState(str, Enum):
    """Task execution state."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Represents a task in the system."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    priority: TaskPriority = TaskPriority.NORMAL
    state: TaskState = TaskState.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    timeout: float = 300.0
    max_retries: int = 3
    retry_count: int = 0
    dependencies: List[str] = field(default_factory=list)
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __lt__(self, other: Task) -> bool:
        """Compare tasks for priority queue."""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.created_at < other.created_at

    def get_duration(self) -> Optional[float]:
        """Get task execution duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class TaskScheduler:
    """Schedules and manages task execution."""

    def __init__(self, max_concurrent: int = 10):
        self.max_concurrent = max_concurrent
        self.queue: List[Task] = []
        self.running: Set[str] = set()
        self.completed: Dict[str, Task] = {}
        self.failed: Dict[str, Task] = {}
        self.lock = asyncio.Lock()

    async def submit(self, task: Task) -> str:
        """Submit a task for execution."""
        async with self.lock:
            task.state = TaskState.QUEUED
            heapq.heappush(self.queue, task)
        return task.id

    async def get_next_task(self) -> Optional[Task]:
        """Get next task to execute."""
        async with self.lock:
            # Check dependencies
            while self.queue:
                task = heapq.heappop(self.queue)

                # Check if dependencies are met
                if task.dependencies:
                    deps_met = all(dep_id in self.completed for dep_id in task.dependencies)
                    if not deps_met:
                        # Re-queue task
                        heapq.heappush(self.queue, task)
                        continue

                if len(self.running) < self.max_concurrent:
                    task.state = TaskState.RUNNING
                    task.started_at = datetime.utcnow()
                    self.running.add(task.id)
                    return task
                else:
                    # Re-queue task
                    heapq.heappush(self.queue, task)
                    break

            return None

    async def complete_task(self, task_id: str, result: Any) -> bool:
        """Mark task as completed."""
        async with self.lock:
            self.running.discard(task_id)
            # Find task in completed
            for task in self.completed.values():
                if task.id == task_id:
                    task.state = TaskState.COMPLETED
                    task.result = result
                    task.completed_at = datetime.utcnow()
                    return True
            return False

    async def fail_task(self, task_id: str, error: str) -> bool:
        """Mark task as failed."""
        async with self.lock:
            self.running.discard(task_id)
            # Find task
            for task in list(self.queue) + list(self.completed.values()):
                if task.id == task_id:
                    if task.retry_count < task.max_retries:
                        task.retry_count += 1
                        task.state = TaskState.QUEUED
                        heapq.heappush(self.queue, task)
                    else:
                        task.state = TaskState.FAILED
                        task.error = error
                        task.completed_at = datetime.utcnow()
                        self.failed[task_id] = task
                    return True
            return False

    async def get_queue_size(self) -> int:
        """Get queue size."""
        async with self.lock:
            return len(self.queue)

    async def get_running_count(self) -> int:
        """Get running task count."""
        async with self.lock:
            return len(self.running)


class ResourceQuota:
    """Manages resource quotas."""

    def __init__(self, cpu_limit: float = 100.0, memory_limit: float = 1024.0,
                 network_limit: float = 1000.0):
        self.cpu_limit = cpu_limit
        self.memory_limit = memory_limit
        self.network_limit = network_limit
        self.cpu_used = 0.0
        self.memory_used = 0.0
        self.network_used = 0.0

    def can_allocate(self, cpu: float, memory: float, network: float) -> bool:
        """Check if resources can be allocated."""
        return (
            self.cpu_used + cpu <= self.cpu_limit and
            self.memory_used + memory <= self.memory_limit and
            self.network_used + network <= self.network_limit
        )

    def allocate(self, cpu: float, memory: float, network: float) -> bool:
        """Allocate resources."""
        if not self.can_allocate(cpu, memory, network):
            return False

        self.cpu_used += cpu
        self.memory_used += memory
        self.network_used += network
        return True

    def release(self, cpu: float, memory: float, network: float) -> None:
        """Release resources."""
        self.cpu_used = max(0, self.cpu_used - cpu)
        self.memory_used = max(0, self.memory_used - memory)
        self.network_used = max(0, self.network_used - network)

    def get_usage(self) -> Dict[str, float]:
        """Get resource usage."""
        return {
            "cpu": self.cpu_used / self.cpu_limit,
            "memory": self.memory_used / self.memory_limit,
            "network": self.network_used / self.network_limit,
        }


class TaskRouter:
    """Routes tasks to appropriate agents."""

    def __init__(self):
        self.agents: Dict[str, Dict[str, Any]] = {}
        self.routing_rules: List[Callable] = []

    def register_agent(self, agent_id: str, capabilities: List[str],
                      load: float = 0.0) -> None:
        """Register an agent."""
        self.agents[agent_id] = {
            "capabilities": capabilities,
            "load": load,
            "tasks": [],
        }

    def add_routing_rule(self, rule: Callable) -> None:
        """Add routing rule."""
        self.routing_rules.append(rule)

    async def route_task(self, task: Task) -> Optional[str]:
        """Route task to agent."""
        # Apply custom routing rules
        for rule in self.routing_rules:
            agent_id = await rule(task, self.agents)
            if agent_id:
                return agent_id

        # Default: route to least loaded agent with capability
        required_capability = task.metadata.get("capability", "general")
        best_agent = None
        best_load = float('inf')

        for agent_id, agent_info in self.agents.items():
            if required_capability in agent_info["capabilities"]:
                if agent_info["load"] < best_load:
                    best_agent = agent_id
                    best_load = agent_info["load"]

        return best_agent

    def update_agent_load(self, agent_id: str, load: float) -> None:
        """Update agent load."""
        if agent_id in self.agents:
            self.agents[agent_id]["load"] = load


class AdaptivePlanner:
    """Adaptive planning based on execution history."""

    def __init__(self):
        self.execution_history: List[Dict[str, Any]] = []
        self.patterns: Dict[str, Dict[str, Any]] = {}

    def record_execution(self, task_name: str, duration: float, success: bool,
                        resource_usage: Dict[str, float]) -> None:
        """Record task execution."""
        self.execution_history.append({
            "task": task_name,
            "duration": duration,
            "success": success,
            "resources": resource_usage,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Update patterns
        if task_name not in self.patterns:
            self.patterns[task_name] = {
                "avg_duration": 0,
                "success_rate": 0,
                "avg_resources": {},
            }

        pattern = self.patterns[task_name]
        pattern["avg_duration"] = (pattern["avg_duration"] + duration) / 2
        pattern["success_rate"] = (pattern["success_rate"] + (1 if success else 0)) / 2

    def predict_duration(self, task_name: str) -> Optional[float]:
        """Predict task duration."""
        if task_name in self.patterns:
            return self.patterns[task_name]["avg_duration"]
        return None

    def predict_success_rate(self, task_name: str) -> Optional[float]:
        """Predict task success rate."""
        if task_name in self.patterns:
            return self.patterns[task_name]["success_rate"]
        return None

    def get_recommendations(self, task_name: str) -> Dict[str, Any]:
        """Get execution recommendations."""
        if task_name not in self.patterns:
            return {}

        pattern = self.patterns[task_name]
        return {
            "estimated_duration": pattern["avg_duration"],
            "success_probability": pattern["success_rate"],
            "recommended_priority": (
                TaskPriority.HIGH if pattern["success_rate"] > 0.9
                else TaskPriority.NORMAL
            ),
        }


class MultiAgentCoordinator:
    """Coordinates multi-agent collaboration."""

    def __init__(self):
        self.agents: Dict[str, Dict[str, Any]] = {}
        self.task_scheduler = TaskScheduler()
        self.resource_quota = ResourceQuota()
        self.task_router = TaskRouter()
        self.adaptive_planner = AdaptivePlanner()

    def register_agent(self, agent_id: str, capabilities: List[str]) -> None:
        """Register an agent."""
        self.agents[agent_id] = {
            "id": agent_id,
            "capabilities": capabilities,
            "status": "idle",
            "current_task": None,
        }
        self.task_router.register_agent(agent_id, capabilities)

    async def submit_task(self, task: Task) -> str:
        """Submit task for execution."""
        return await self.task_scheduler.submit(task)

    async def execute_task(self, task: Task) -> Any:
        """Execute task with coordination."""
        # Route task to agent
        agent_id = await self.task_router.route_task(task)
        if not agent_id:
            raise RuntimeError("No suitable agent found for task")

        # Check resource availability
        required_resources = task.metadata.get("resources", {})
        if not self.resource_quota.can_allocate(
            required_resources.get("cpu", 0),
            required_resources.get("memory", 0),
            required_resources.get("network", 0),
        ):
            raise RuntimeError("Insufficient resources")

        # Allocate resources
        self.resource_quota.allocate(
            required_resources.get("cpu", 0),
            required_resources.get("memory", 0),
            required_resources.get("network", 0),
        )

        try:
            # Execute task
            result = await asyncio.wait_for(
                self._execute_on_agent(agent_id, task),
                timeout=task.timeout
            )

            # Record execution
            self.adaptive_planner.record_execution(
                task.name,
                (datetime.utcnow() - task.started_at).total_seconds(),
                True,
                required_resources
            )

            return result
        except Exception as e:
            # Record failure
            self.adaptive_planner.record_execution(
                task.name,
                (datetime.utcnow() - task.started_at).total_seconds(),
                False,
                required_resources
            )
            raise
        finally:
            # Release resources
            self.resource_quota.release(
                required_resources.get("cpu", 0),
                required_resources.get("memory", 0),
                required_resources.get("network", 0),
            )

    async def _execute_on_agent(self, agent_id: str, task: Task) -> Any:
        """Execute task on specific agent."""
        # Placeholder for actual agent execution
        await asyncio.sleep(0.1)
        return {"status": "completed", "agent": agent_id, "task": task.id}

    def get_system_status(self) -> Dict[str, Any]:
        """Get system status."""
        return {
            "agents": len(self.agents),
            "resource_usage": self.resource_quota.get_usage(),
            "queue_size": asyncio.run(self.task_scheduler.get_queue_size()),
            "running_tasks": asyncio.run(self.task_scheduler.get_running_count()),
        }


class LearningEngine:
    """Learns from execution history to improve performance."""

    def __init__(self):
        self.execution_history: List[Dict[str, Any]] = []
        self.learned_patterns: Dict[str, Dict[str, Any]] = {}

    def record_execution(self, execution_data: Dict[str, Any]) -> None:
        """Record execution for learning."""
        self.execution_history.append(execution_data)
        self._update_patterns()

    def _update_patterns(self) -> None:
        """Update learned patterns."""
        # Analyze execution history
        for execution in self.execution_history[-10:]:  # Look at recent executions
            task_type = execution.get("task_type", "unknown")

            if task_type not in self.learned_patterns:
                self.learned_patterns[task_type] = {
                    "success_count": 0,
                    "failure_count": 0,
                    "avg_duration": 0,
                    "optimal_params": {},
                }

            pattern = self.learned_patterns[task_type]
            if execution.get("success"):
                pattern["success_count"] += 1
            else:
                pattern["failure_count"] += 1

            pattern["avg_duration"] = (
                (pattern["avg_duration"] + execution.get("duration", 0)) / 2
            )

    def get_recommendations(self, task_type: str) -> Dict[str, Any]:
        """Get recommendations based on learned patterns."""
        if task_type not in self.learned_patterns:
            return {}

        pattern = self.learned_patterns[task_type]
        total = pattern["success_count"] + pattern["failure_count"]

        return {
            "success_rate": pattern["success_count"] / total if total > 0 else 0,
            "estimated_duration": pattern["avg_duration"],
            "optimal_params": pattern["optimal_params"],
        }
