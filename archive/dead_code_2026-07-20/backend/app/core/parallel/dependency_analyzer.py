"""Task dependency analysis and DAG construction for parallel execution."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional
from collections import defaultdict, deque


@dataclass
class DAGNode:
    """Represents a node in the task dependency graph."""

    node_id: str
    task_type: str  # "tool" | "agent" | "decision"
    task_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    timeout_seconds: float = 30.0
    retry_count: int = 0
    max_retries: int = 3
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __hash__(self) -> int:
        return hash(self.node_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DAGNode):
            return False
        return self.node_id == other.node_id


@dataclass
class ExecutionLayer:
    """Represents a layer of tasks that can be executed in parallel."""

    layer_id: int
    nodes: list[DAGNode] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.nodes)


@dataclass
class DependencyGraph:
    """Represents the complete dependency graph."""

    nodes: dict[str, DAGNode] = field(default_factory=dict)
    edges: dict[str, list[str]] = field(default_factory=dict)  # node_id -> [dependent_node_ids]
    reverse_edges: dict[str, list[str]] = field(default_factory=dict)  # node_id -> [dependency_node_ids]

    def add_node(self, node: DAGNode) -> None:
        """Add a node to the graph."""
        self.nodes[node.node_id] = node
        if node.node_id not in self.edges:
            self.edges[node.node_id] = []
        if node.node_id not in self.reverse_edges:
            self.reverse_edges[node.node_id] = []

    def add_edge(self, from_node_id: str, to_node_id: str) -> None:
        """Add an edge from from_node to to_node."""
        if from_node_id not in self.edges:
            self.edges[from_node_id] = []
        if to_node_id not in self.reverse_edges:
            self.reverse_edges[to_node_id] = []

        self.edges[from_node_id].append(to_node_id)
        self.reverse_edges[to_node_id].append(from_node_id)

    def get_in_degree(self, node_id: str) -> int:
        """Get the in-degree of a node."""
        return len(self.reverse_edges.get(node_id, []))

    def get_out_degree(self, node_id: str) -> int:
        """Get the out-degree of a node."""
        return len(self.edges.get(node_id, []))


@dataclass
class ExecutionPlan:
    """Represents the execution plan with layers."""

    layers: list[ExecutionLayer] = field(default_factory=list)
    total_nodes: int = 0
    critical_path_length: int = 0

    def add_layer(self, layer: ExecutionLayer) -> None:
        """Add a layer to the plan."""
        self.layers.append(layer)


class ToolDependencyAnalyzer:
    """Analyzes dependencies between tool calls and builds execution plans."""

    def __init__(self) -> None:
        """Initialize the analyzer."""
        self._graph: Optional[DependencyGraph] = None

    def analyze_dependencies(self, tool_calls: list[Any]) -> DependencyGraph:
        """Analyze dependencies between tool calls.

        Args:
            tool_calls: List of tool calls to analyze

        Returns:
            DependencyGraph with all dependencies identified
        """
        graph = DependencyGraph()

        # Create nodes for each tool call
        for i, call in enumerate(tool_calls):
            node_id = getattr(call, 'call_id', f"tool_{i}")
            tool_name = getattr(call, 'tool_name', f"tool_{i}")
            arguments = getattr(call, 'arguments', {})

            node = DAGNode(
                node_id=node_id,
                task_type="tool",
                task_name=tool_name,
                arguments=arguments,
                timeout_seconds=getattr(call, 'timeout_seconds', 30.0),
                retry_count=getattr(call, 'retry_count', 0),
            )
            graph.add_node(node)

        # Analyze parameter dependencies
        for i, call in enumerate(tool_calls):
            from_node_id = getattr(call, 'call_id', f"tool_{i}")
            arguments = getattr(call, 'arguments', {})

            # Check if any argument references output from other tools
            for j, other_call in enumerate(tool_calls):
                if i == j:
                    continue

                to_node_id = getattr(other_call, 'call_id', f"tool_{j}")
                other_tool_name = getattr(other_call, 'tool_name', f"tool_{j}")

                # Check for references like "${tool_j.output}" or "tool_j.result"
                if self._has_dependency(arguments, to_node_id, other_tool_name):
                    graph.add_edge(to_node_id, from_node_id)

        self._graph = graph
        return graph

    def _has_dependency(self, arguments: dict[str, Any], node_id: str, tool_name: str) -> bool:
        """Check if arguments reference a specific node or tool.

        Args:
            arguments: Arguments dictionary to check
            node_id: Node ID to look for
            tool_name: Tool name to look for

        Returns:
            True if dependency found
        """
        args_str = str(arguments).lower()

        # Check for node_id references
        if node_id.lower() in args_str:
            return True

        # Check for tool_name references
        if tool_name.lower() in args_str:
            return True

        # Check for common patterns like "${tool_name.output}"
        patterns = [
            rf"\${{{tool_name}\..*?\}}",
            rf"{tool_name}\.output",
            rf"{tool_name}\.result",
            rf"output_of_{tool_name}",
        ]

        for pattern in patterns:
            if re.search(pattern, args_str, re.IGNORECASE):
                return True

        return False

    def detect_cycles(self, graph: DependencyGraph) -> list[list[str]]:
        """Detect cycles in the dependency graph.

        Args:
            graph: DependencyGraph to check

        Returns:
            List of cycles (each cycle is a list of node IDs)
        """
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node_id: str, path: list[str]) -> None:
            visited.add(node_id)
            rec_stack.add(node_id)
            path.append(node_id)

            for neighbor in graph.edges.get(node_id, []):
                if neighbor not in visited:
                    dfs(neighbor, path[:])
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)

            rec_stack.remove(node_id)

        for node_id in graph.nodes:
            if node_id not in visited:
                dfs(node_id, [])

        return cycles

    def build_execution_plan(self, graph: DependencyGraph) -> ExecutionPlan:
        """Build an execution plan using topological sort.

        Args:
            graph: DependencyGraph to plan

        Returns:
            ExecutionPlan with layers
        """
        plan = ExecutionPlan(total_nodes=len(graph.nodes))

        # Calculate in-degrees
        in_degree = {node_id: graph.get_in_degree(node_id) for node_id in graph.nodes}

        # Find all nodes with in-degree 0
        queue = deque([node_id for node_id in graph.nodes if in_degree[node_id] == 0])

        layer_id = 0
        processed = set()

        while queue:
            # Create a layer with all nodes that can be executed now
            layer_nodes = []
            next_queue = deque()

            while queue:
                node_id = queue.popleft()
                layer_nodes.append(graph.nodes[node_id])
                processed.add(node_id)

                # Update in-degrees for dependent nodes
                for dependent_id in graph.edges.get(node_id, []):
                    in_degree[dependent_id] -= 1
                    if in_degree[dependent_id] == 0:
                        next_queue.append(dependent_id)

            if layer_nodes:
                layer = ExecutionLayer(layer_id=layer_id, nodes=layer_nodes)
                plan.add_layer(layer)
                layer_id += 1

            queue = next_queue

        # Calculate critical path length
        plan.critical_path_length = len(plan.layers)

        return plan

    def calculate_parallelism_factor(self, total_tasks: int, total_time_ms: float, avg_task_time_ms: float = 1000) -> float:
        """Calculate the parallelism factor.

        Args:
            total_tasks: Total number of tasks
            total_time_ms: Total execution time in milliseconds
            avg_task_time_ms: Average task execution time in milliseconds

        Returns:
            Parallelism factor (1.0 = sequential, N = perfect parallelism)
        """
        if total_time_ms == 0:
            return 1.0

        sequential_time = total_tasks * avg_task_time_ms
        parallelism = sequential_time / total_time_ms

        return min(parallelism, float(total_tasks))
