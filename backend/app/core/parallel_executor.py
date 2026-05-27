"""
Parallel executor module for X-Agent.

Handles parallel execution of tasks with support for dependencies
and concurrent execution limits.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Optional, Any, Dict, List, Callable, Coroutine

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Status of a task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Task:
    """Represents a task to be executed."""

    task_id: str
    name: str
    coroutine: Callable[[], Coroutine[Any, Any, Any]]
    priority: int = 0
    timeout_seconds: Optional[int] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResult:
    """Result of a task execution."""

    task_id: str
    name: str
    status: TaskStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    attempts: int = 1


class ParallelExecutor:
    """
    Executes tasks in parallel with dependency support.

    Handles concurrent execution, dependency resolution, and error handling.
    """

    def __init__(self, max_concurrent: int = 5):
        """
        Initialize the parallel executor.

        Args:
            max_concurrent: Maximum number of concurrent tasks
        """
        self.max_concurrent = max_concurrent
        self.logger = logger

    async def execute_parallel(
        self,
        tasks: List[Task],
        max_concurrent: Optional[int] = None,
    ) -> List[TaskResult]:
        """
        Execute multiple tasks in parallel.

        Args:
            tasks: List of tasks to execute
            max_concurrent: Override max concurrent limit

        Returns:
            List of task results
        """
        max_concurrent = max_concurrent or self.max_concurrent
        results: Dict[str, TaskResult] = {}
        semaphore = asyncio.Semaphore(max_concurrent)

        async def execute_with_semaphore(task: Task) -> TaskResult:
            async with semaphore:
                return await self._execute_task(task)

        # Sort by priority (higher priority first)
        sorted_tasks = sorted(tasks, key=lambda t: t.priority, reverse=True)

        # Execute all tasks concurrently
        task_coros = [execute_with_semaphore(task) for task in sorted_tasks]
        task_results = await asyncio.gather(*task_coros, return_exceptions=False)

        # Store results
        for result in task_results:
            results[result.task_id] = result

        self.logger.info(
            f"Executed {len(tasks)} tasks in parallel: "
            f"{sum(1 for r in results.values() if r.status == TaskStatus.COMPLETED)} completed, "
            f"{sum(1 for r in results.values() if r.status == TaskStatus.FAILED)} failed"
        )

        return list(results.values())

    async def execute_with_dependencies(
        self,
        tasks: List[Task],
        dependencies: Dict[str, List[str]],
        max_concurrent: Optional[int] = None,
    ) -> List[TaskResult]:
        """
        Execute tasks considering dependencies.

        Args:
            tasks: List of tasks to execute
            dependencies: Dict mapping task_id to list of task_ids it depends on
            max_concurrent: Override max concurrent limit

        Returns:
            List of task results
        """
        max_concurrent = max_concurrent or self.max_concurrent
        results: Dict[str, TaskResult] = {}
        task_map = {task.task_id: task for task in tasks}
        semaphore = asyncio.Semaphore(max_concurrent)

        # Validate dependencies
        for task_id, deps in dependencies.items():
            if task_id not in task_map:
                raise ValueError(f"Task {task_id} not found")
            for dep_id in deps:
                if dep_id not in task_map:
                    raise ValueError(f"Dependency {dep_id} not found")

        # Detect cycles
        if self._has_cycle(dependencies):
            raise ValueError("Circular dependency detected")

        async def execute_with_deps(task_id: str) -> TaskResult:
            # Wait for dependencies
            deps = dependencies.get(task_id, [])
            for dep_id in deps:
                while dep_id not in results:
                    await asyncio.sleep(0.01)

                # Check if dependency failed
                if results[dep_id].status == TaskStatus.FAILED:
                    return TaskResult(
                        task_id=task_id,
                        name=task_map[task_id].name,
                        status=TaskStatus.SKIPPED,
                        error="Dependency failed",
                    )

            # Execute task
            async with semaphore:
                result = await self._execute_task(task_map[task_id])
                results[task_id] = result
                return result

        # Execute all tasks
        task_coros = [execute_with_deps(task.task_id) for task in tasks]
        await asyncio.gather(*task_coros, return_exceptions=False)

        self.logger.info(
            f"Executed {len(tasks)} tasks with dependencies: "
            f"{sum(1 for r in results.values() if r.status == TaskStatus.COMPLETED)} completed, "
            f"{sum(1 for r in results.values() if r.status == TaskStatus.FAILED)} failed"
        )

        return list(results.values())

    async def _execute_task(self, task: Task) -> TaskResult:
        """
        Execute a single task with retry logic.

        Args:
            task: Task to execute

        Returns:
            Task result
        """
        result = TaskResult(
            task_id=task.task_id,
            name=task.name,
            status=TaskStatus.PENDING,
        )

        for attempt in range(task.retry_count + 1):
            try:
                result.started_at = datetime.now(UTC)
                result.status = TaskStatus.RUNNING
                result.attempts = attempt + 1

                # Execute with timeout
                if task.timeout_seconds:
                    task_result = await asyncio.wait_for(
                        task.coroutine(),
                        timeout=task.timeout_seconds,
                    )
                else:
                    task_result = await task.coroutine()

                result.status = TaskStatus.COMPLETED
                result.result = task_result
                result.completed_at = datetime.now(UTC)

                if result.started_at:
                    result.duration_seconds = (
                        result.completed_at - result.started_at
                    ).total_seconds()

                self.logger.info(
                    f"Task {task.task_id} ({task.name}) completed in "
                    f"{result.duration_seconds:.2f}s"
                )
                return result

            except asyncio.TimeoutError:
                result.error = f"Timeout after {task.timeout_seconds}s"
                if attempt < task.retry_count:
                    self.logger.warning(
                        f"Task {task.task_id} timed out, retrying "
                        f"({attempt + 1}/{task.retry_count})"
                    )
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    result.status = TaskStatus.FAILED
                    result.completed_at = datetime.now(UTC)
                    if result.started_at:
                        result.duration_seconds = (
                            result.completed_at - result.started_at
                        ).total_seconds()
                    self.logger.error(f"Task {task.task_id} failed after timeout")

            except Exception as e:
                result.error = str(e)
                if attempt < task.retry_count:
                    self.logger.warning(
                        f"Task {task.task_id} failed: {e}, retrying "
                        f"({attempt + 1}/{task.retry_count})"
                    )
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    result.status = TaskStatus.FAILED
                    result.completed_at = datetime.now(UTC)
                    if result.started_at:
                        result.duration_seconds = (
                            result.completed_at - result.started_at
                        ).total_seconds()
                    self.logger.error(f"Task {task.task_id} failed: {e}")

        return result

    def _has_cycle(self, dependencies: Dict[str, List[str]]) -> bool:
        """
        Detect if there's a cycle in dependencies.

        Args:
            dependencies: Dependency graph

        Returns:
            True if cycle detected
        """
        visited = set()
        rec_stack = set()

        def visit(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in dependencies.get(node, []):
                if neighbor not in visited:
                    if visit(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for node in dependencies:
            if node not in visited:
                if visit(node):
                    return True

        return False

    async def execute_batch(
        self,
        task_batches: List[List[Task]],
        max_concurrent: Optional[int] = None,
    ) -> List[List[TaskResult]]:
        """
        Execute tasks in sequential batches.

        Args:
            task_batches: List of task batches
            max_concurrent: Override max concurrent limit

        Returns:
            List of result batches
        """
        all_results = []

        for batch in task_batches:
            results = await self.execute_parallel(batch, max_concurrent)
            all_results.append(results)

        return all_results

    def get_execution_stats(
        self,
        results: List[TaskResult],
    ) -> Dict[str, Any]:
        """
        Get statistics about task execution.

        Args:
            results: List of task results

        Returns:
            Statistics dict
        """
        total_duration = sum(r.duration_seconds for r in results)
        completed = sum(1 for r in results if r.status == TaskStatus.COMPLETED)
        failed = sum(1 for r in results if r.status == TaskStatus.FAILED)
        skipped = sum(1 for r in results if r.status == TaskStatus.SKIPPED)

        return {
            "total_tasks": len(results),
            "completed": completed,
            "failed": failed,
            "skipped": skipped,
            "total_duration_seconds": total_duration,
            "avg_duration_seconds": total_duration / len(results) if results else 0,
            "success_rate": completed / len(results) if results else 0,
        }


# Global instance
parallel_executor = ParallelExecutor()
