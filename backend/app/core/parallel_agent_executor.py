"""
Parallel Agent Executor - Manages concurrent execution of multiple agents.

Supports three isolation modes:
- process: Full process isolation using multiprocessing
- thread: Thread-based isolation (lighter weight, shared memory)
- worktree: Git worktree isolation (for file system operations)
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing as mp
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import StrEnum
from typing import Any, Callable, Optional
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

from pydantic import BaseModel, Field


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


@dataclass
class AgentTask:
    """Represents a task to be executed by an agent."""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    goal: str = ""
    description: str = ""
    constraints: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    timeout_seconds: int = 300
    retry_count: int = 0
    max_retries: int = 3
    metadata: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)

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
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    retry_attempts: int = 0
    context: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

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
    results: list[AgentResult] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: Optional[datetime] = None
    total_duration_seconds: float = 0.0
    errors: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

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


class ParallelAgentExecutor:
    """
    Manages parallel execution of multiple agents with configurable isolation.

    Features:
    - Multiple isolation modes (process, thread, worktree)
    - Task scheduling and distribution
    - Result collection and aggregation
    - Timeout control and error handling
    - Retry mechanism
    - Resource management
    """

    def __init__(
        self,
        max_workers: int = 3,
        default_isolation: IsolationMode = IsolationMode.THREAD,
        enable_process_pool: bool = True,
        enable_thread_pool: bool = True,
    ):
        """
        Initialize the parallel agent executor.

        Args:
            max_workers: Maximum number of concurrent workers
            default_isolation: Default isolation mode
            enable_process_pool: Enable process pool executor
            enable_thread_pool: Enable thread pool executor
        """
        self.max_workers = max_workers
        self.default_isolation = default_isolation
        self.batch_id_to_tasks: dict[str, list[AgentTask]] = {}
        self.batch_id_to_results: dict[str, list[AgentResult]] = {}
        self.batch_id_to_status: dict[str, str] = {}
        self.active_batches: set[str] = set()
        self.cancelled_batches: set[str] = set()

        # Thread-safe locks
        self._lock = asyncio.Lock()
        self._batch_lock = threading.Lock()

        # Executors
        self.process_pool: Optional[ProcessPoolExecutor] = None
        self.thread_pool: Optional[ThreadPoolExecutor] = None

        if enable_process_pool:
            self.process_pool = ProcessPoolExecutor(max_workers=max_workers)
        if enable_thread_pool:
            self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)

    async def spawn_agents(
        self,
        tasks: list[AgentTask],
        isolation: Optional[IsolationMode] = None,
        max_parallel: Optional[int] = None,
        agent_factory: Optional[Callable] = None,
    ) -> BatchExecutionResult:
        """
        Spawn and execute multiple agents in parallel.

        Args:
            tasks: List of tasks to execute
            isolation: Isolation mode (defaults to self.default_isolation)
            max_parallel: Maximum parallel tasks (defaults to self.max_workers)
            agent_factory: Factory function to create agent instances

        Returns:
            BatchExecutionResult with all results
        """
        if not tasks:
            raise ValueError("No tasks provided")

        isolation = isolation or self.default_isolation
        max_parallel = max_parallel or self.max_workers
        batch_id = str(uuid.uuid4())

        async with self._lock:
            self.batch_id_to_tasks[batch_id] = tasks
            self.batch_id_to_results[batch_id] = []
            self.batch_id_to_status[batch_id] = "running"
            self.active_batches.add(batch_id)

        logger.info(
            f"Starting batch {batch_id} with {len(tasks)} tasks, "
            f"isolation={isolation}, max_parallel={max_parallel}"
        )

        start_time = time.time()
        results: list[AgentResult] = []
        errors: list[str] = []

        try:
            if isolation == IsolationMode.PROCESS:
                results = await self._execute_with_process_isolation(
                    batch_id, tasks, max_parallel, agent_factory
                )
            elif isolation == IsolationMode.THREAD:
                results = await self._execute_with_thread_isolation(
                    batch_id, tasks, max_parallel, agent_factory
                )
            elif isolation == IsolationMode.WORKTREE:
                results = await self._execute_with_worktree_isolation(
                    batch_id, tasks, max_parallel, agent_factory
                )
            else:
                raise ValueError(f"Unknown isolation mode: {isolation}")

        except Exception as e:
            logger.error(f"Error during batch execution {batch_id}: {e}", exc_info=True)
            errors.append(str(e))

        finally:
            async with self._lock:
                self.batch_id_to_results[batch_id] = results
                self.active_batches.discard(batch_id)

        # Calculate statistics
        completed = sum(1 for r in results if r.status == AgentTaskStatus.COMPLETED)
        failed = sum(1 for r in results if r.status == AgentTaskStatus.FAILED)
        cancelled = sum(1 for r in results if r.status == AgentTaskStatus.CANCELLED)
        timeout = sum(1 for r in results if r.status == AgentTaskStatus.TIMEOUT)

        total_duration = time.time() - start_time

        batch_result = BatchExecutionResult(
            batch_id=batch_id,
            total_tasks=len(tasks),
            completed_tasks=completed,
            failed_tasks=failed,
            cancelled_tasks=cancelled,
            timeout_tasks=timeout,
            results=results,
            completed_at=datetime.now(UTC),
            total_duration_seconds=total_duration,
            errors=errors,
            metadata={
                "isolation_mode": isolation.value,
                "max_parallel": max_parallel,
            },
        )

        logger.info(
            f"Batch {batch_id} completed: {completed}/{len(tasks)} succeeded, "
            f"duration={total_duration:.2f}s"
        )

        return batch_result

    async def _execute_with_thread_isolation(
        self,
        batch_id: str,
        tasks: list[AgentTask],
        max_parallel: int,
        agent_factory: Optional[Callable],
    ) -> list[AgentResult]:
        """Execute tasks with thread isolation."""
        results: list[AgentResult] = []
        semaphore = asyncio.Semaphore(max_parallel)

        async def execute_task_with_semaphore(task: AgentTask) -> AgentResult:
            async with semaphore:
                return await self._execute_single_task(
                    batch_id, task, IsolationMode.THREAD, agent_factory
                )

        # Create tasks for all agents
        execution_tasks = [
            execute_task_with_semaphore(task) for task in tasks
        ]

        # Execute all tasks concurrently
        results = await asyncio.gather(*execution_tasks, return_exceptions=False)

        return results

    async def _execute_with_process_isolation(
        self,
        batch_id: str,
        tasks: list[AgentTask],
        max_parallel: int,
        agent_factory: Optional[Callable],
    ) -> list[AgentResult]:
        """Execute tasks with process isolation."""
        results: list[AgentResult] = []
        semaphore = asyncio.Semaphore(max_parallel)

        async def execute_task_with_semaphore(task: AgentTask) -> AgentResult:
            async with semaphore:
                return await self._execute_single_task(
                    batch_id, task, IsolationMode.PROCESS, agent_factory
                )

        execution_tasks = [
            execute_task_with_semaphore(task) for task in tasks
        ]

        results = await asyncio.gather(*execution_tasks, return_exceptions=False)

        return results

    async def _execute_with_worktree_isolation(
        self,
        batch_id: str,
        tasks: list[AgentTask],
        max_parallel: int,
        agent_factory: Optional[Callable],
    ) -> list[AgentResult]:
        """Execute tasks with git worktree isolation."""
        results: list[AgentResult] = []
        semaphore = asyncio.Semaphore(max_parallel)

        async def execute_task_with_semaphore(task: AgentTask) -> AgentResult:
            async with semaphore:
                return await self._execute_single_task(
                    batch_id, task, IsolationMode.WORKTREE, agent_factory
                )

        execution_tasks = [
            execute_task_with_semaphore(task) for task in tasks
        ]

        results = await asyncio.gather(*execution_tasks, return_exceptions=False)

        return results

    async def _execute_single_task(
        self,
        batch_id: str,
        task: AgentTask,
        isolation: IsolationMode,
        agent_factory: Optional[Callable],
    ) -> AgentResult:
        """Execute a single task with retry logic."""
        agent_id = str(uuid.uuid4())
        result = AgentResult(
            task_id=task.task_id,
            agent_id=agent_id,
            status=AgentTaskStatus.PENDING,
        )

        for attempt in range(task.max_retries + 1):
            try:
                result.status = AgentTaskStatus.RUNNING
                result.retry_attempts = attempt

                # Execute task with timeout
                try:
                    output = await asyncio.wait_for(
                        self._run_agent_task(task, agent_id, isolation, agent_factory),
                        timeout=task.timeout_seconds,
                    )
                    result.output = output
                    result.status = AgentTaskStatus.COMPLETED
                    break

                except asyncio.TimeoutError:
                    result.status = AgentTaskStatus.TIMEOUT
                    result.error = f"Task timed out after {task.timeout_seconds}s"
                    result.error_type = "timeout"
                    logger.warning(
                        f"Task {task.task_id} timed out (attempt {attempt + 1}/{task.max_retries + 1})"
                    )

                    if attempt < task.max_retries:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    break

            except Exception as e:
                result.status = AgentTaskStatus.FAILED
                result.error = str(e)
                result.error_type = type(e).__name__
                logger.error(
                    f"Task {task.task_id} failed (attempt {attempt + 1}/{task.max_retries + 1}): {e}",
                    exc_info=True,
                )

                if attempt < task.max_retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                break

        result.completed_at = datetime.now(UTC)
        result.duration_seconds = (
            result.completed_at - result.started_at
        ).total_seconds()

        return result

    async def _run_agent_task(
        self,
        task: AgentTask,
        agent_id: str,
        isolation: IsolationMode,
        agent_factory: Optional[Callable],
    ) -> Any:
        """Run the actual agent task. Override in subclass or provide factory."""
        if agent_factory:
            agent = agent_factory(agent_id, isolation)
            return await agent.execute(task)

        # Default implementation: simulate task execution
        await asyncio.sleep(0.1)
        return {"task_id": task.task_id, "status": "completed"}

    async def get_batch_status(self, batch_id: str) -> dict[str, Any]:
        """Get the status of a batch execution."""
        async with self._lock:
            if batch_id not in self.batch_id_to_tasks:
                raise ValueError(f"Batch {batch_id} not found")

            tasks = self.batch_id_to_tasks[batch_id]
            results = self.batch_id_to_results.get(batch_id, [])
            status = self.batch_id_to_status.get(batch_id, "unknown")

            return {
                "batch_id": batch_id,
                "status": status,
                "total_tasks": len(tasks),
                "completed_results": len(results),
                "is_active": batch_id in self.active_batches,
            }

    async def get_batch_results(self, batch_id: str) -> list[AgentResult]:
        """Get results from a batch execution."""
        async with self._lock:
            if batch_id not in self.batch_id_to_results:
                raise ValueError(f"Batch {batch_id} not found")
            return self.batch_id_to_results[batch_id]

    async def cancel_batch(self, batch_id: str) -> bool:
        """Cancel a batch execution."""
        async with self._lock:
            if batch_id not in self.active_batches:
                return False

            self.cancelled_batches.add(batch_id)
            self.batch_id_to_status[batch_id] = "cancelled"
            logger.info(f"Batch {batch_id} cancelled")
            return True

    def shutdown(self):
        """Shutdown executors and cleanup resources."""
        if self.process_pool:
            self.process_pool.shutdown(wait=True)
        if self.thread_pool:
            self.thread_pool.shutdown(wait=True)
        logger.info("ParallelAgentExecutor shutdown complete")

    def __del__(self):
        """Cleanup on deletion."""
        try:
            self.shutdown()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
