"""Parallel agent executor for multi-agent coordination and execution."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import StrEnum
from typing import Any, Callable, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class IsolationMode(StrEnum):
    """Isolation modes for parallel agent execution."""

    PROCESS = "process"
    THREAD = "thread"
    WORKTREE = "worktree"


class AgentTaskStatus(StrEnum):
    """Status of an agent task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class CollaborationMode(StrEnum):
    """Agent collaboration modes."""

    MASTER_SLAVE = "master_slave"
    PEER_TO_PEER = "peer_to_peer"
    HIERARCHICAL = "hierarchical"


@dataclass
class AgentTask:
    """Represents a task to be executed by an agent."""

    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    goal: str = ""
    description: str = ""
    constraints: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    timeout_seconds: int = 300
    retry_count: int = 0
    max_retries: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.task_id:
            self.task_id = str(uuid.uuid4())


@dataclass
class AgentResult:
    """Result from an agent execution."""

    task_id: str
    agent_id: str
    status: AgentTaskStatus
    output: Any = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    retry_attempts: int = 0
    context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "error_type": self.error_type,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "retry_attempts": self.retry_attempts,
            "context": self.context,
            "metadata": self.metadata,
        }


@dataclass
class BatchExecutionResult:
    """Result of batch parallel execution."""

    batch_id: str
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    cancelled_tasks: int
    timeout_tasks: int
    results: list[AgentResult] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: Optional[datetime] = None
    total_duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "batch_id": self.batch_id,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "cancelled_tasks": self.cancelled_tasks,
            "timeout_tasks": self.timeout_tasks,
            "results": [r.to_dict() for r in self.results],
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_duration_seconds": self.total_duration_seconds,
            "errors": self.errors,
            "metadata": self.metadata,
        }


class AgentPool:
    """Manages a pool of agents for parallel execution."""

    def __init__(self, max_agents: int = 10) -> None:
        """Initialize the agent pool.

        Args:
            max_agents: Maximum number of agents in the pool
        """
        self._max_agents = max_agents
        self._agents: dict[str, Any] = {}
        self._available_agents: asyncio.Queue = asyncio.Queue(maxsize=max_agents)
        self._lock = asyncio.Lock()

    async def acquire_agent(self, timeout_seconds: float = 5.0) -> Optional[Any]:
        """Acquire an agent from the pool.

        Args:
            timeout_seconds: Timeout for acquiring an agent

        Returns:
            Agent or None if timeout
        """
        try:
            agent = await asyncio.wait_for(
                self._available_agents.get(),
                timeout=timeout_seconds,
            )
            return agent
        except asyncio.TimeoutError:
            return None

    async def release_agent(self, agent: Any) -> None:
        """Release an agent back to the pool.

        Args:
            agent: Agent to release
        """
        try:
            self._available_agents.put_nowait(agent)
        except asyncio.QueueFull:
            logger.warning("Agent pool is full, discarding agent")

    async def add_agent(self, agent: Any) -> None:
        """Add an agent to the pool.

        Args:
            agent: Agent to add
        """
        async with self._lock:
            if len(self._agents) < self._max_agents:
                agent_id = str(uuid.uuid4())
                self._agents[agent_id] = agent
                await self._available_agents.put(agent)

    def get_pool_stats(self) -> dict[str, Any]:
        """Get pool statistics.

        Returns:
            Dictionary with pool stats
        """
        return {
            "total_agents": len(self._agents),
            "available_agents": self._available_agents.qsize(),
            "max_agents": self._max_agents,
        }


class ParallelAgentExecutor:
    """Manages parallel execution of multiple agents with configurable isolation."""

    def __init__(
        self,
        max_workers: int = 3,
        default_isolation: IsolationMode = IsolationMode.THREAD,
        collaboration_mode: CollaborationMode = CollaborationMode.MASTER_SLAVE,
    ) -> None:
        """Initialize the parallel agent executor.

        Args:
            max_workers: Maximum number of concurrent agents
            default_isolation: Default isolation mode
            collaboration_mode: Agent collaboration mode
        """
        self._max_workers = max_workers
        self._default_isolation = default_isolation
        self._collaboration_mode = collaboration_mode
        self._agent_pool = AgentPool(max_agents=max_workers)
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._results: dict[str, AgentResult] = {}
        self._lock = asyncio.Lock()

    async def execute_tasks(
        self,
        tasks: list[AgentTask],
        agent_factory: Callable[[], Any],
        allow_partial_failure: bool = True,
    ) -> BatchExecutionResult:
        """Execute multiple tasks in parallel using agents.

        Args:
            tasks: List of tasks to execute
            agent_factory: Factory function to create agents
            allow_partial_failure: If False, stop on first failure

        Returns:
            BatchExecutionResult with all results
        """
        batch_id = str(uuid.uuid4())
        started_at = datetime.now(UTC)

        # Initialize agent pool
        for _ in range(self._max_workers):
            agent = agent_factory()
            await self._agent_pool.add_agent(agent)

        # Execute tasks
        results = []
        failed_count = 0
        cancelled_count = 0
        timeout_count = 0

        semaphore = asyncio.Semaphore(self._max_workers)

        async def execute_task_with_semaphore(task: AgentTask) -> AgentResult:
            async with semaphore:
                return await self._execute_single_task(task, agent_factory)

        # Create tasks
        execution_tasks = [execute_task_with_semaphore(task) for task in tasks]

        # Execute with gather
        try:
            results = await asyncio.gather(*execution_tasks, return_exceptions=False)
        except Exception as e:
            logger.error(f"Error during batch execution: {e}")
            if not allow_partial_failure:
                raise

        # Count results
        completed_count = 0
        for result in results:
            if result.status == AgentTaskStatus.COMPLETED:
                completed_count += 1
            elif result.status == AgentTaskStatus.FAILED:
                failed_count += 1
            elif result.status == AgentTaskStatus.CANCELLED:
                cancelled_count += 1
            elif result.status == AgentTaskStatus.TIMEOUT:
                timeout_count += 1

        completed_at = datetime.now(UTC)
        total_duration = (completed_at - started_at).total_seconds()

        return BatchExecutionResult(
            batch_id=batch_id,
            total_tasks=len(tasks),
            completed_tasks=completed_count,
            failed_tasks=failed_count,
            cancelled_tasks=cancelled_count,
            timeout_tasks=timeout_count,
            results=results,
            started_at=started_at,
            completed_at=completed_at,
            total_duration_seconds=total_duration,
            metadata={"isolation_mode": self._default_isolation.value},
        )

    async def _execute_single_task(
        self,
        task: AgentTask,
        agent_factory: Callable[[], Any],
    ) -> AgentResult:
        """Execute a single task with an agent.

        Args:
            task: Task to execute
            agent_factory: Factory function to create agents

        Returns:
            AgentResult with execution result
        """
        agent = await self._agent_pool.acquire_agent()
        if not agent:
            agent = agent_factory()

        started_at = datetime.now(UTC)
        result = AgentResult(
            task_id=task.task_id,
            agent_id=str(uuid.uuid4()),
            status=AgentTaskStatus.RUNNING,
            started_at=started_at,
        )

        try:
            # Execute task with timeout
            output = await asyncio.wait_for(
                self._run_agent_task(agent, task),
                timeout=task.timeout_seconds,
            )

            completed_at = datetime.now(UTC)
            result.status = AgentTaskStatus.COMPLETED
            result.output = output
            result.completed_at = completed_at
            result.duration_seconds = (completed_at - started_at).total_seconds()

        except asyncio.TimeoutError:
            completed_at = datetime.now(UTC)
            result.status = AgentTaskStatus.TIMEOUT
            result.error = f"Task timed out after {task.timeout_seconds}s"
            result.completed_at = completed_at
            result.duration_seconds = (completed_at - started_at).total_seconds()

        except Exception as e:
            completed_at = datetime.now(UTC)
            result.status = AgentTaskStatus.FAILED
            result.error = str(e)
            result.error_type = type(e).__name__
            result.completed_at = completed_at
            result.duration_seconds = (completed_at - started_at).total_seconds()

        finally:
            # Release agent back to pool
            await self._agent_pool.release_agent(agent)

        return result

    async def _run_agent_task(self, agent: Any, task: AgentTask) -> Any:
        """Run a task using an agent.

        Args:
            agent: Agent to use
            task: Task to execute

        Returns:
            Task output
        """
        # Check if agent has async run method
        if hasattr(agent, "run_async"):
            return await agent.run_async(task.goal, task.metadata)
        elif hasattr(agent, "run"):
            # Run sync method in executor
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                agent.run,
                task.goal,
                task.metadata,
            )
        else:
            raise ValueError(f"Agent {agent} does not have run or run_async method")

    async def execute_with_coordination(
        self,
        tasks: list[AgentTask],
        agent_factory: Callable[[], Any],
        coordination_callback: Optional[Callable[[dict[str, Any]], Any]] = None,
    ) -> BatchExecutionResult:
        """Execute tasks with inter-agent coordination.

        Args:
            tasks: List of tasks to execute
            agent_factory: Factory function to create agents
            coordination_callback: Optional callback for coordination

        Returns:
            BatchExecutionResult with all results
        """
        batch_id = str(uuid.uuid4())
        started_at = datetime.now(UTC)

        # Build dependency graph
        task_map = {task.task_id: task for task in tasks}
        dependency_graph = self._build_dependency_graph(tasks)

        # Execute tasks layer by layer
        results: dict[str, AgentResult] = {}
        completed_count = 0
        failed_count = 0

        for layer in self._topological_sort(dependency_graph):
            # Execute all tasks in this layer in parallel
            layer_tasks = [task_map[task_id] for task_id in layer]

            semaphore = asyncio.Semaphore(self._max_workers)

            async def execute_task_with_semaphore(task: AgentTask) -> AgentResult:
                async with semaphore:
                    return await self._execute_single_task(task, agent_factory)

            layer_results = await asyncio.gather(
                *[execute_task_with_semaphore(task) for task in layer_tasks],
                return_exceptions=False,
            )

            for result in layer_results:
                results[result.task_id] = result
                if result.status == AgentTaskStatus.COMPLETED:
                    completed_count += 1
                else:
                    failed_count += 1

            # Call coordination callback
            if coordination_callback:
                await coordination_callback(
                    {
                        "layer": layer,
                        "results": {r.task_id: r.to_dict() for r in layer_results},
                    }
                )

        completed_at = datetime.now(UTC)
        total_duration = (completed_at - started_at).total_seconds()

        result_list = list(results.values())
        return BatchExecutionResult(
            batch_id=batch_id,
            total_tasks=len(tasks),
            completed_tasks=completed_count,
            failed_tasks=failed_count,
            cancelled_tasks=0,
            timeout_tasks=0,
            results=result_list,
            started_at=started_at,
            completed_at=completed_at,
            total_duration_seconds=total_duration,
            metadata={
                "collaboration_mode": self._collaboration_mode.value,
                "layers": len(list(self._topological_sort(dependency_graph))),
            },
        )

    def _build_dependency_graph(self, tasks: list[AgentTask]) -> dict[str, list[str]]:
        """Build a dependency graph from tasks.

        Args:
            tasks: List of tasks

        Returns:
            Dictionary mapping task_id to list of dependent task_ids
        """
        graph: dict[str, list[str]] = defaultdict(list)

        for task in tasks:
            if task.task_id not in graph:
                graph[task.task_id] = []

            for dep_id in task.dependencies:
                graph[dep_id].append(task.task_id)

        return graph

    def _topological_sort(self, graph: dict[str, list[str]]) -> list[list[str]]:
        """Perform topological sort on the dependency graph.

        Args:
            graph: Dependency graph

        Returns:
            List of layers, each layer is a list of task_ids
        """
        # Calculate in-degrees
        in_degree = defaultdict(int)
        all_nodes = set(graph.keys())

        for node in graph:
            for neighbor in graph[node]:
                in_degree[neighbor] += 1
                all_nodes.add(neighbor)

        # Find nodes with in-degree 0
        queue = [node for node in all_nodes if in_degree[node] == 0]
        layers = []

        while queue:
            layer = queue[:]
            layers.append(layer)
            queue = []

            for node in layer:
                for neighbor in graph.get(node, []):
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)

        return layers

    def get_pool_stats(self) -> dict[str, Any]:
        """Get agent pool statistics.

        Returns:
            Dictionary with pool stats
        """
        return self._agent_pool.get_pool_stats()
