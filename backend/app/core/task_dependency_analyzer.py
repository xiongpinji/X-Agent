"""
Task Dependency Analyzer - Analyzes task dependencies and optimizes execution.

Features:
- Build dependency graphs (DAG)
- Topological sorting
- Cycle detection
- Execution planning
- Parallelism optimization
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Set, List, Dict
from collections import defaultdict, deque


logger = logging.getLogger(__name__)


@dataclass
class Task:
    """Represents a task in the dependency graph."""
    task_id: str
    name: str = ""
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        return hash(self.task_id)

    def __eq__(self, other):
        if isinstance(other, Task):
            return self.task_id == other.task_id
        return False


@dataclass
class Cycle:
    """Represents a cycle in the dependency graph."""
    tasks: List[str]
    path: List[str] = field(default_factory=list)

    def __str__(self):
        return f"Cycle: {' -> '.join(self.path)}"


@dataclass
class ExecutionPlan:
    """Represents an execution plan with task layers."""
    layers: List[List[str]] = field(default_factory=list)
    total_tasks: int = 0
    critical_path_length: int = 0
    parallelism_factor: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "layers": self.layers,
            "total_tasks": self.total_tasks,
            "critical_path_length": self.critical_path_length,
            "parallelism_factor": self.parallelism_factor,
            "metadata": self.metadata,
        }


class DAG:
    """Directed Acyclic Graph for task dependencies."""

    def __init__(self):
        """Initialize the DAG."""
        self.nodes: Dict[str, Task] = {}
        self.edges: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_edges: Dict[str, Set[str]] = defaultdict(set)

    def add_task(self, task: Task) -> None:
        """Add a task to the graph."""
        self.nodes[task.task_id] = task

    def add_dependency(self, from_task: str, to_task: str) -> None:
        """
        Add a dependency edge.

        Args:
            from_task: Task that depends on to_task
            to_task: Task that from_task depends on
        """
        self.edges[from_task].add(to_task)
        self.reverse_edges[to_task].add(from_task)

    def get_dependencies(self, task_id: str) -> Set[str]:
        """Get all dependencies of a task."""
        return self.edges.get(task_id, set()).copy()

    def get_dependents(self, task_id: str) -> Set[str]:
        """Get all tasks that depend on this task."""
        return self.reverse_edges.get(task_id, set()).copy()

    def get_all_tasks(self) -> List[Task]:
        """Get all tasks in the graph."""
        return list(self.nodes.values())

    def size(self) -> int:
        """Get number of tasks in the graph."""
        return len(self.nodes)


class TaskDependencyAnalyzer:
    """
    Analyzes task dependencies and optimizes execution.

    Features:
    - Build dependency graphs
    - Detect cycles
    - Topological sorting
    - Execution planning
    - Parallelism analysis
    """

    def __init__(self):
        """Initialize the analyzer."""
        self.dag: Optional[DAG] = None
        self.cycles: List[Cycle] = []
        self.execution_plan: Optional[ExecutionPlan] = None

    def build_dependency_graph(self, tasks: List[Task]) -> DAG:
        """
        Build a dependency graph from tasks.

        Args:
            tasks: List of tasks with dependencies

        Returns:
            DAG representing the dependencies
        """
        dag = DAG()

        # Add all tasks
        for task in tasks:
            dag.add_task(task)

        # Add dependencies
        for task in tasks:
            for dep_id in task.dependencies:
                dag.add_dependency(task.task_id, dep_id)

        self.dag = dag
        logger.info(f"Built dependency graph with {dag.size()} tasks")

        return dag

    def detect_cycles(self, dag: Optional[DAG] = None) -> List[Cycle]:
        """
        Detect cycles in the dependency graph.

        Args:
            dag: DAG to analyze (uses self.dag if not provided)

        Returns:
            List of detected cycles
        """
        dag = dag or self.dag
        if not dag:
            return []

        cycles: List[Cycle] = []
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        path: List[str] = []

        def dfs(node: str) -> None:
            """Depth-first search to detect cycles."""
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in dag.get_dependencies(node):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    cycle_path = path[cycle_start:] + [neighbor]
                    cycle_tasks = cycle_path[:-1]
                    cycles.append(Cycle(tasks=cycle_tasks, path=cycle_path))

            path.pop()
            rec_stack.remove(node)

        # Run DFS from all unvisited nodes
        for task_id in dag.nodes:
            if task_id not in visited:
                dfs(task_id)

        self.cycles = cycles

        if cycles:
            logger.warning(f"Detected {len(cycles)} cycles in dependency graph")
            for cycle in cycles:
                logger.warning(f"  {cycle}")

        return cycles

    def topological_sort(self, dag: Optional[DAG] = None) -> List[str]:
        """
        Perform topological sort on the DAG.

        Args:
            dag: DAG to sort (uses self.dag if not provided)

        Returns:
            List of task IDs in topological order
        """
        dag = dag or self.dag
        if not dag:
            return []

        # Check for cycles first
        if self.detect_cycles(dag):
            raise ValueError("Cannot perform topological sort on graph with cycles")

        # Kahn's algorithm
        in_degree: Dict[str, int] = defaultdict(int)
        queue: deque[str] = deque()

        # Calculate in-degrees
        for task_id in dag.nodes:
            in_degree[task_id] = len(dag.get_dependencies(task_id))

        # Add nodes with no dependencies to queue
        for task_id, degree in in_degree.items():
            if degree == 0:
                queue.append(task_id)

        sorted_tasks: List[str] = []

        while queue:
            node = queue.popleft()
            sorted_tasks.append(node)

            # Reduce in-degree for dependents
            for dependent in dag.get_dependents(node):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(sorted_tasks) != len(dag.nodes):
            raise ValueError("Topological sort failed - graph may contain cycles")

        logger.info(f"Topological sort completed: {len(sorted_tasks)} tasks")

        return sorted_tasks

    def build_execution_plan(
        self,
        tasks: List[Task],
        max_parallel: Optional[int] = None,
    ) -> ExecutionPlan:
        """
        Build an execution plan with task layers.

        Args:
            tasks: List of tasks
            max_parallel: Maximum parallel tasks per layer

        Returns:
            ExecutionPlan with layers
        """
        # Build DAG
        dag = self.build_dependency_graph(tasks)

        # Check for cycles
        cycles = self.detect_cycles(dag)
        if cycles:
            raise ValueError(f"Cannot build execution plan: {len(cycles)} cycles detected")

        # Build layers
        layers: List[List[str]] = []
        completed: Set[str] = set()
        remaining: Set[str] = set(dag.nodes.keys())

        while remaining:
            # Find tasks with all dependencies satisfied
            current_layer: List[str] = []

            for task_id in remaining:
                task = dag.nodes[task_id]
                deps = dag.get_dependencies(task_id)

                if all(dep in completed for dep in deps):
                    current_layer.append(task_id)

            if not current_layer:
                # This shouldn't happen if cycle detection worked
                raise ValueError("Deadlock: no tasks can be executed")

            # Limit layer size if max_parallel is set
            if max_parallel and len(current_layer) > max_parallel:
                current_layer = current_layer[:max_parallel]

            layers.append(current_layer)
            completed.update(current_layer)
            remaining -= set(current_layer)

        # Calculate metrics
        critical_path_length = len(layers)
        total_tasks = len(tasks)
        parallelism_factor = total_tasks / critical_path_length if critical_path_length > 0 else 1.0

        plan = ExecutionPlan(
            layers=layers,
            total_tasks=total_tasks,
            critical_path_length=critical_path_length,
            parallelism_factor=parallelism_factor,
            metadata={
                "num_layers": len(layers),
                "max_layer_size": max(len(layer) for layer in layers) if layers else 0,
                "min_layer_size": min(len(layer) for layer in layers) if layers else 0,
            },
        )

        self.execution_plan = plan
        logger.info(
            f"Built execution plan: {len(layers)} layers, "
            f"parallelism factor: {parallelism_factor:.2f}"
        )

        return plan

    def get_critical_path(self, dag: Optional[DAG] = None) -> List[str]:
        """
        Get the critical path (longest dependency chain).

        Args:
            dag: DAG to analyze (uses self.dag if not provided)

        Returns:
            List of task IDs in the critical path
        """
        dag = dag or self.dag
        if not dag:
            return []

        # Find longest path using dynamic programming
        memo: Dict[str, int] = {}

        def longest_path_length(task_id: str) -> int:
            """Calculate longest path from this task."""
            if task_id in memo:
                return memo[task_id]

            deps = dag.get_dependencies(task_id)
            if not deps:
                memo[task_id] = 1
                return 1

            max_length = 1 + max(longest_path_length(dep) for dep in deps)
            memo[task_id] = max_length
            return max_length

        # Find task with longest path
        max_length = 0
        critical_task = None

        for task_id in dag.nodes:
            length = longest_path_length(task_id)
            if length > max_length:
                max_length = length
                critical_task = task_id

        # Reconstruct path
        path: List[str] = []
        current = critical_task

        while current:
            path.append(current)
            deps = dag.get_dependencies(current)

            if not deps:
                break

            # Find dependency with longest path
            current = max(deps, key=longest_path_length)

        return list(reversed(path))

    def analyze_parallelism(self, dag: Optional[DAG] = None) -> Dict[str, Any]:
        """
        Analyze parallelism opportunities.

        Args:
            dag: DAG to analyze (uses self.dag if not provided)

        Returns:
            Parallelism analysis
        """
        dag = dag or self.dag
        if not dag:
            return {}

        # Build execution plan to get layers
        tasks = dag.get_all_tasks()
        plan = self.build_execution_plan(tasks)

        # Calculate statistics
        layer_sizes = [len(layer) for layer in plan.layers]
        avg_layer_size = sum(layer_sizes) / len(layer_sizes) if layer_sizes else 0
        max_layer_size = max(layer_sizes) if layer_sizes else 0
        min_layer_size = min(layer_sizes) if layer_sizes else 0

        # Calculate speedup potential
        sequential_time = len(tasks)
        parallel_time = len(plan.layers)
        speedup = sequential_time / parallel_time if parallel_time > 0 else 1.0

        return {
            "total_tasks": len(tasks),
            "num_layers": len(plan.layers),
            "critical_path_length": plan.critical_path_length,
            "parallelism_factor": plan.parallelism_factor,
            "avg_layer_size": avg_layer_size,
            "max_layer_size": max_layer_size,
            "min_layer_size": min_layer_size,
            "sequential_time": sequential_time,
            "parallel_time": parallel_time,
            "speedup_potential": speedup,
        }

    def optimize_execution_order(
        self,
        tasks: List[Task],
        strategy: str = "greedy",
    ) -> List[str]:
        """
        Optimize task execution order.

        Args:
            tasks: List of tasks
            strategy: Optimization strategy (greedy, balanced, etc.)

        Returns:
            Optimized task order
        """
        dag = self.build_dependency_graph(tasks)

        if strategy == "greedy":
            # Greedy: prioritize tasks with most dependents
            sorted_tasks = self.topological_sort(dag)
            dependents_count = {
                task_id: len(dag.get_dependents(task_id))
                for task_id in sorted_tasks
            }
            return sorted(sorted_tasks, key=lambda t: dependents_count[t], reverse=True)

        elif strategy == "balanced":
            # Balanced: try to keep layers balanced
            plan = self.build_execution_plan(tasks)
            return [task for layer in plan.layers for task in layer]

        elif strategy == "critical_path":
            # Critical path first
            critical = self.get_critical_path(dag)
            remaining = [t for t in self.topological_sort(dag) if t not in critical]
            return critical + remaining

        else:
            # Default: topological sort
            return self.topological_sort(dag)

    def validate_dependencies(self, tasks: List[Task]) -> List[str]:
        """
        Validate task dependencies.

        Args:
            tasks: List of tasks

        Returns:
            List of validation errors
        """
        errors: List[str] = []
        task_ids = {t.task_id for t in tasks}

        for task in tasks:
            # Check for missing dependencies
            for dep_id in task.dependencies:
                if dep_id not in task_ids:
                    errors.append(
                        f"Task {task.task_id} depends on non-existent task {dep_id}"
                    )

            # Check for self-dependencies
            if task.task_id in task.dependencies:
                errors.append(f"Task {task.task_id} has self-dependency")

        # Check for cycles
        dag = self.build_dependency_graph(tasks)
        cycles = self.detect_cycles(dag)
        for cycle in cycles:
            errors.append(f"Cycle detected: {' -> '.join(cycle.path)}")

        return errors
