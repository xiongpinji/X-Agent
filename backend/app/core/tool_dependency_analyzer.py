"""Tool dependency analysis and execution planning."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionLayer:
    """A layer of tool calls that can execute in parallel."""

    layer_id: int
    call_ids: set[str] = field(default_factory=set)
    dependencies: set[int] = field(default_factory=set)  # Layer IDs this depends on


@dataclass
class ExecutionPlan:
    """Plan for executing tool calls in layers."""

    layers: list[ExecutionLayer] = field(default_factory=list)
    total_calls: int = 0
    max_parallelism: int = 1


@dataclass
class DependencyGraph:
    """Graph representing dependencies between tool calls."""

    nodes: dict[str, Any] = field(default_factory=dict)  # call_id -> ToolCall
    edges: dict[str, set[str]] = field(default_factory=dict)  # call_id -> set of dependent call_ids
    reverse_edges: dict[str, set[str]] = field(default_factory=dict)  # call_id -> set of dependency call_ids


class ToolDependencyAnalyzer:
    """Analyzes dependencies between tool calls and builds execution plans."""

    def analyze_dependencies(self, tool_calls: list[Any]) -> DependencyGraph:
        """Analyze dependencies between tool calls.

        Args:
            tool_calls: List of ToolCall objects

        Returns:
            DependencyGraph representing the dependencies
        """
        graph = DependencyGraph()

        # Add all nodes
        for call in tool_calls:
            graph.nodes[call.call_id] = call
            graph.edges[call.call_id] = set()
            graph.reverse_edges[call.call_id] = set()

        # Analyze dependencies by looking for variable references
        for call in tool_calls:
            dependencies = self._extract_dependencies(call)
            for dep_call_id in dependencies:
                if dep_call_id in graph.nodes:
                    # call depends on dep_call_id
                    graph.reverse_edges[call.call_id].add(dep_call_id)
                    graph.edges[dep_call_id].add(call.call_id)

        return graph

    def build_execution_plan(self, graph: DependencyGraph) -> ExecutionPlan:
        """Build an execution plan from the dependency graph.

        Uses topological sorting to determine execution layers.

        Args:
            graph: DependencyGraph

        Returns:
            ExecutionPlan with layers
        """
        plan = ExecutionPlan(total_calls=len(graph.nodes))

        # Calculate in-degree for each node
        in_degree = {call_id: len(deps) for call_id, deps in graph.reverse_edges.items()}

        # Track which layer each call belongs to
        call_to_layer: dict[str, int] = {}
        layer_calls: dict[int, set[str]] = {}
        current_layer = 0

        # Process nodes layer by layer
        remaining = set(graph.nodes.keys())

        while remaining:
            # Find all nodes with no dependencies in remaining set
            current_layer_calls = set()
            for call_id in remaining:
                # Check if all dependencies are already processed
                unprocessed_deps = graph.reverse_edges[call_id] & remaining
                if not unprocessed_deps:
                    current_layer_calls.add(call_id)

            if not current_layer_calls:
                # Should not happen if graph is acyclic
                break

            # Add layer
            layer = ExecutionLayer(layer_id=current_layer)
            layer.call_ids = current_layer_calls

            # Determine layer dependencies
            for call_id in current_layer_calls:
                for dep_call_id in graph.reverse_edges[call_id]:
                    dep_layer = call_to_layer.get(dep_call_id)
                    if dep_layer is not None:
                        layer.dependencies.add(dep_layer)

            plan.layers.append(layer)
            layer_calls[current_layer] = current_layer_calls

            # Update call_to_layer mapping
            for call_id in current_layer_calls:
                call_to_layer[call_id] = current_layer

            # Remove processed calls
            remaining -= current_layer_calls
            current_layer += 1

        # Calculate max parallelism
        plan.max_parallelism = max(len(layer.call_ids) for layer in plan.layers) if plan.layers else 1

        return plan

    def detect_cycles(self, graph: DependencyGraph) -> list[list[str]]:
        """Detect circular dependencies in the graph.

        Args:
            graph: DependencyGraph

        Returns:
            List of cycles (each cycle is a list of call_ids)
        """
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: list[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.edges.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor, path[:])
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)

            rec_stack.discard(node)

        for node in graph.nodes:
            if node not in visited:
                dfs(node, [])

        return cycles

    def calculate_parallelism(self, plan: ExecutionPlan) -> float:
        """Calculate the parallelism factor of the execution plan.

        Args:
            plan: ExecutionPlan

        Returns:
            Parallelism factor (speedup ratio if perfectly parallel)
        """
        if not plan.layers or plan.total_calls == 0:
            return 1.0

        # Parallelism = total_calls / number_of_layers
        # This represents the average parallelism across all layers
        return plan.total_calls / len(plan.layers)

    def _extract_dependencies(self, call: Any) -> set[str]:
        """Extract call IDs that this call depends on.

        Looks for variable references in the form ${call_id.output} or ${call_id.error}

        Args:
            call: ToolCall object

        Returns:
            Set of call_ids this call depends on
        """
        dependencies = set()

        def extract_from_value(value: Any) -> None:
            if isinstance(value, str):
                if value.startswith("${") and value.endswith("}"):
                    ref = value[2:-1]  # Remove ${ and }
                    if "." in ref:
                        call_id = ref.split(".")[0]
                        dependencies.add(call_id)
            elif isinstance(value, dict):
                for v in value.values():
                    extract_from_value(v)
            elif isinstance(value, list):
                for v in value:
                    extract_from_value(v)

        # Check arguments
        if hasattr(call, "arguments") and isinstance(call.arguments, dict):
            for arg_value in call.arguments.values():
                extract_from_value(arg_value)

        return dependencies
