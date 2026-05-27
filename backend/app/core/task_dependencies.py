"""
Task dependency management module for X-Agent.

Manages task dependencies and execution order.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Set
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


@dataclass
class TaskDependency:
    """Represents a task dependency."""

    task_id: str
    depends_on: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)


class TaskDependencyManager:
    """
    Manages task dependencies and execution order.

    Handles dependency tracking, cycle detection, and topological sorting.
    """

    def __init__(self):
        """Initialize the dependency manager."""
        self.dependencies: Dict[str, TaskDependency] = {}
        self.logger = logger

    def add_task(self, task_id: str) -> None:
        """
        Add a task to the dependency graph.

        Args:
            task_id: ID of task to add
        """
        if task_id not in self.dependencies:
            self.dependencies[task_id] = TaskDependency(task_id=task_id)
            self.logger.debug(f"Added task {task_id} to dependency graph")

    def add_dependency(
        self,
        task_id: str,
        depends_on: str,
    ) -> bool:
        """
        Add a dependency between tasks.

        Args:
            task_id: ID of task that depends
            depends_on: ID of task it depends on

        Returns:
            True if added, False if would create cycle
        """
        # Ensure both tasks exist
        self.add_task(task_id)
        self.add_task(depends_on)

        # Check for cycle
        if self._would_create_cycle(task_id, depends_on):
            self.logger.warning(
                f"Cannot add dependency: {task_id} -> {depends_on} would create cycle"
            )
            return False

        # Add dependency
        if depends_on not in self.dependencies[task_id].depends_on:
            self.dependencies[task_id].depends_on.append(depends_on)
            self.dependencies[depends_on].dependents.append(task_id)

            self.logger.debug(f"Added dependency: {task_id} depends on {depends_on}")

        return True

    def add_dependencies(
        self,
        task_id: str,
        depends_on: List[str],
    ) -> bool:
        """
        Add multiple dependencies for a task.

        Args:
            task_id: ID of task
            depends_on: List of task IDs it depends on

        Returns:
            True if all added successfully
        """
        all_added = True

        for dep_id in depends_on:
            if not self.add_dependency(task_id, dep_id):
                all_added = False

        return all_added

    def remove_dependency(
        self,
        task_id: str,
        depends_on: str,
    ) -> bool:
        """
        Remove a dependency between tasks.

        Args:
            task_id: ID of task
            depends_on: ID of task to remove dependency on

        Returns:
            True if removed
        """
        if task_id not in self.dependencies or depends_on not in self.dependencies:
            return False

        if depends_on in self.dependencies[task_id].depends_on:
            self.dependencies[task_id].depends_on.remove(depends_on)
            self.dependencies[depends_on].dependents.remove(task_id)

            self.logger.debug(f"Removed dependency: {task_id} no longer depends on {depends_on}")
            return True

        return False

    def resolve_dependencies(self, task_id: str) -> List[str]:
        """
        Get all dependencies for a task (transitive closure).

        Args:
            task_id: ID of task

        Returns:
            List of all task IDs this task depends on
        """
        if task_id not in self.dependencies:
            return []

        visited = set()
        stack = [task_id]
        all_deps = []

        while stack:
            current = stack.pop()

            if current in visited:
                continue

            visited.add(current)

            if current != task_id:
                all_deps.append(current)

            for dep in self.dependencies[current].depends_on:
                if dep not in visited:
                    stack.append(dep)

        return all_deps

    def get_execution_order(self, task_ids: List[str]) -> List[str]:
        """
        Get execution order for tasks (topological sort).

        Args:
            task_ids: List of task IDs

        Returns:
            Ordered list of task IDs

        Raises:
            ValueError: If cycle detected
        """
        # Check for cycles
        if self._has_cycle(task_ids):
            raise ValueError("Circular dependency detected")

        # Topological sort using Kahn's algorithm
        in_degree = defaultdict(int)
        graph = defaultdict(list)

        # Build graph
        for task_id in task_ids:
            if task_id not in in_degree:
                in_degree[task_id] = 0

            for dep in self.dependencies[task_id].depends_on:
                if dep in task_ids:
                    graph[dep].append(task_id)
                    in_degree[task_id] += 1

        # Find all nodes with no incoming edges
        queue = deque([task_id for task_id in task_ids if in_degree[task_id] == 0])
        result = []

        while queue:
            node = queue.popleft()
            result.append(node)

            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(task_ids):
            raise ValueError("Circular dependency detected")

        return result

    def get_ready_tasks(self, task_ids: List[str], completed_tasks: Set[str]) -> List[str]:
        """
        Get tasks that are ready to execute.

        Args:
            task_ids: List of task IDs to check
            completed_tasks: Set of completed task IDs

        Returns:
            List of task IDs that are ready
        """
        ready = []

        for task_id in task_ids:
            if task_id in completed_tasks:
                continue

            # Check if all dependencies are completed
            deps = self.dependencies[task_id].depends_on
            if all(dep in completed_tasks for dep in deps):
                ready.append(task_id)

        return ready

    def get_blocked_tasks(self, task_ids: List[str], completed_tasks: Set[str]) -> List[str]:
        """
        Get tasks that are blocked by incomplete dependencies.

        Args:
            task_ids: List of task IDs to check
            completed_tasks: Set of completed task IDs

        Returns:
            List of blocked task IDs
        """
        blocked = []

        for task_id in task_ids:
            if task_id in completed_tasks:
                continue

            # Check if any dependencies are incomplete
            deps = self.dependencies[task_id].depends_on
            if any(dep not in completed_tasks for dep in deps):
                blocked.append(task_id)

        return blocked

    def get_dependents(self, task_id: str) -> List[str]:
        """
        Get all tasks that depend on this task.

        Args:
            task_id: ID of task

        Returns:
            List of dependent task IDs
        """
        if task_id not in self.dependencies:
            return []

        return self.dependencies[task_id].dependents.copy()

    def get_dependencies(self, task_id: str) -> List[str]:
        """
        Get direct dependencies for a task.

        Args:
            task_id: ID of task

        Returns:
            List of dependency task IDs
        """
        if task_id not in self.dependencies:
            return []

        return self.dependencies[task_id].depends_on.copy()

    def remove_task(self, task_id: str) -> bool:
        """
        Remove a task from the dependency graph.

        Args:
            task_id: ID of task to remove

        Returns:
            True if removed
        """
        if task_id not in self.dependencies:
            return False

        # Remove all dependencies
        for dep in self.dependencies[task_id].depends_on:
            self.dependencies[dep].dependents.remove(task_id)

        # Remove all dependents
        for dependent in self.dependencies[task_id].dependents:
            self.dependencies[dependent].depends_on.remove(task_id)

        del self.dependencies[task_id]

        self.logger.debug(f"Removed task {task_id} from dependency graph")
        return True

    def _would_create_cycle(self, task_id: str, depends_on: str) -> bool:
        """
        Check if adding a dependency would create a cycle.

        Args:
            task_id: ID of task that would depend
            depends_on: ID of task it would depend on

        Returns:
            True if would create cycle
        """
        # Check if depends_on already depends on task_id
        visited = set()
        stack = [depends_on]

        while stack:
            current = stack.pop()

            if current in visited:
                continue

            visited.add(current)

            if current == task_id:
                return True

            for dep in self.dependencies[current].depends_on:
                if dep not in visited:
                    stack.append(dep)

        return False

    def _has_cycle(self, task_ids: List[str]) -> bool:
        """
        Check if there's a cycle in the dependency graph.

        Args:
            task_ids: List of task IDs to check

        Returns:
            True if cycle detected
        """
        visited = set()
        rec_stack = set()

        def visit(node: str) -> bool:
            if node not in task_ids:
                return False

            visited.add(node)
            rec_stack.add(node)

            for neighbor in self.dependencies[node].depends_on:
                if neighbor not in visited:
                    if visit(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for node in task_ids:
            if node not in visited:
                if visit(node):
                    return True

        return False

    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """
        Get the complete dependency graph.

        Returns:
            Dict mapping task IDs to their dependencies
        """
        return {
            task_id: dep.depends_on.copy()
            for task_id, dep in self.dependencies.items()
        }

    def get_stats(self) -> Dict[str, int]:
        """
        Get dependency graph statistics.

        Returns:
            Statistics dict
        """
        total_tasks = len(self.dependencies)
        total_dependencies = sum(
            len(dep.depends_on) for dep in self.dependencies.values()
        )

        return {
            "total_tasks": total_tasks,
            "total_dependencies": total_dependencies,
            "avg_dependencies_per_task": (
                total_dependencies / total_tasks if total_tasks > 0 else 0
            ),
        }


# Global instance
task_dependency_manager = TaskDependencyManager()
