"""Tool call batching and optimization."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Batch:
    """A batch of tool calls to execute together."""

    batch_id: str
    tool_name: str
    calls: list[Any] = field(default_factory=list)
    priority: int = 0  # Higher priority executes first
    optimized: bool = False


class ToolCallBatcher:
    """Batches and optimizes tool calls for efficient execution."""

    def __init__(self, max_batch_size: int = 50) -> None:
        """Initialize the batcher.

        Args:
            max_batch_size: Maximum number of calls per batch
        """
        self._max_batch_size = max_batch_size

    def batch_tool_calls(self, calls: list[Any]) -> list[Batch]:
        """Group tool calls into batches.

        Calls to the same tool are grouped together.

        Args:
            calls: List of ToolCall objects

        Returns:
            List of Batch objects
        """
        # Group by tool name
        by_tool: dict[str, list[Any]] = {}
        for call in calls:
            tool_name = call.tool_name
            if tool_name not in by_tool:
                by_tool[tool_name] = []
            by_tool[tool_name].append(call)

        # Create batches
        batches = []
        batch_counter = 0

        for tool_name, tool_calls in by_tool.items():
            # Split into chunks if needed
            for i in range(0, len(tool_calls), self._max_batch_size):
                chunk = tool_calls[i : i + self._max_batch_size]
                batch = Batch(
                    batch_id=f"batch_{batch_counter}",
                    tool_name=tool_name,
                    calls=chunk,
                    priority=self._calculate_priority(tool_name),
                )
                batches.append(batch)
                batch_counter += 1

        return batches

    def optimize_batches(self, batches: list[Batch]) -> list[Batch]:
        """Optimize batches for execution.

        Applies various optimization strategies:
        - Merge similar calls
        - Reorder by priority
        - Deduplicate

        Args:
            batches: List of Batch objects

        Returns:
            Optimized list of Batch objects
        """
        optimized = []

        for batch in batches:
            # Merge similar calls
            merged_calls = self._merge_similar_calls(batch.calls)

            # Create optimized batch
            opt_batch = Batch(
                batch_id=batch.batch_id,
                tool_name=batch.tool_name,
                calls=merged_calls,
                priority=batch.priority,
                optimized=True,
            )
            optimized.append(opt_batch)

        # Sort by priority (higher first)
        optimized.sort(key=lambda b: (-b.priority, b.batch_id))

        return optimized

    def merge_similar_calls(self, calls: list[Any]) -> list[Any]:
        """Merge similar tool calls.

        Identifies calls with identical arguments and merges them.

        Args:
            calls: List of ToolCall objects

        Returns:
            Deduplicated list of ToolCall objects
        """
        return self._merge_similar_calls(calls)

    def _merge_similar_calls(self, calls: list[Any]) -> list[Any]:
        """Internal method to merge similar calls."""
        if not calls:
            return []

        # Group by arguments
        by_args: dict[str, list[Any]] = {}

        for call in calls:
            # Create a hashable representation of arguments
            args_key = self._make_args_key(call.arguments)

            if args_key not in by_args:
                by_args[args_key] = []
            by_args[args_key].append(call)

        # For each group, keep only one representative
        merged = []
        for _args_key, group in by_args.items():
            # Keep the first call in the group
            merged.append(group[0])

        return merged

    def _make_args_key(self, arguments: dict[str, Any]) -> str:
        """Create a hashable key from arguments.

        Args:
            arguments: Arguments dictionary

        Returns:
            Hashable key
        """
        import json

        try:
            return json.dumps(arguments, sort_keys=True, default=str)
        except Exception:
            # Fallback for non-serializable objects
            return str(sorted(arguments.items()))

    def _calculate_priority(self, tool_name: str) -> int:
        """Calculate priority for a tool.

        Higher priority tools execute first.

        Args:
            tool_name: Name of the tool

        Returns:
            Priority value (0-100)
        """
        # Read operations have higher priority
        if any(token in tool_name.lower() for token in ["read", "list", "search", "inspect"]):
            return 80

        # Write operations have lower priority
        if any(token in tool_name.lower() for token in ["write", "edit", "update", "patch", "apply"]):
            return 20

        # Utility operations have medium priority
        return 50
