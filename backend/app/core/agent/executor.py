"""
Tool execution engine - handles tool invocation and result processing.

Extracted from AgentLoop to reduce coupling and improve testability.
Responsibilities:
  - Execute tools with proper context
  - Verify write operations
  - Handle repair suggestions
  - Track execution metrics
"""

from typing import Any
import json
from dataclasses import dataclass

from backend.app.core.contracts import RunContext, ToolCallRecord
from backend.app.core.repair_loop import RepairLoop
from backend.app.core.agent.protocols import ExecutionResult


@dataclass
class ToolExecutionConfig:
    """Configuration for tool execution."""
    max_retries: int = 3
    verify_writes: bool = True
    track_metrics: bool = True


class ToolExecutor:
    """Executes tools and manages their lifecycle."""

    def __init__(
        self,
        tool_registry: Any,  # ToolRegistry
        repair_loop: RepairLoop | None = None,
        config: ToolExecutionConfig | None = None,
    ):
        self.tools = tool_registry
        self.repair_loop = repair_loop or RepairLoop(None)
        self.config = config or ToolExecutionConfig()
        self._execution_history: list[dict[str, Any]] = []

    async def execute(
        self,
        context: RunContext,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ExecutionResult:
        """
        Execute a tool with given arguments.

        Args:
            context: Execution context
            tool_name: Name of tool to execute
            arguments: Tool arguments

        Returns:
            ExecutionResult with success status and output
        """
        try:
            record = await self.tools.execute(context, tool_name, arguments)

            result = ExecutionResult(
                success=record.success,
                output=record.output,
                error=record.error,
                latency_ms=record.latency_ms,
            )

            self._execution_history.append({
                "tool_name": tool_name,
                "success": record.success,
                "latency_ms": record.latency_ms,
                "error": record.error,
            })

            return result
        except Exception as e:
            return ExecutionResult(
                success=False,
                output=None,
                error=str(e),
                latency_ms=0,
            )

    async def verify_write(
        self,
        context: RunContext,
        tool_name: str,
        output: Any,
        arguments: dict[str, Any],
    ) -> bool:
        """
        Verify that a write operation succeeded.

        Args:
            context: Execution context
            tool_name: Name of write tool
            output: Tool output to verify
            arguments: Original tool arguments

        Returns:
            True if write verified, False otherwise
        """
        if not self.config.verify_writes:
            return True

        if tool_name not in {"apply_text_patch", "write_file"}:
            return True

        payload = output if isinstance(output, dict) else {}

        # Check explicit verification flag
        if payload.get("verified") is True:
            return True

        # Verify by re-reading file
        file_path = str(payload.get("path") or arguments.get("path") or "")
        if not file_path:
            return False

        try:
            read_tool = self.tools.get("read_file")
            if read_tool is None:
                return False

            reread_result = await self.tools.execute(
                context,
                "read_file",
                {"path": file_path, "limit": 8000},
            )

            if not reread_result.success or not isinstance(reread_result.output, str):
                return False

            reread_content = reread_result.output
            expected = str(
                arguments.get("new_text")
                or arguments.get("replacement")
                or arguments.get("content")
                or ""
            )

            return expected in reread_content if expected else True
        except Exception:
            return False

    async def repair_failed_step(
        self,
        context: RunContext,
        tool_name: str,
        error: str,
        original_arguments: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Suggest repair for failed tool execution.

        Args:
            context: Execution context
            tool_name: Name of failed tool
            error: Error message
            original_arguments: Original arguments

        Returns:
            Repair suggestion or None
        """
        if self.repair_loop is None:
            return None

        try:
            # Create a mock ToolCallRecord for repair analysis
            mock_record = type('MockRecord', (), {
                'tool_name': tool_name,
                'error': error,
                'success': False,
                'output': None,
            })()

            verification_result, repair_suggestion = self.repair_loop.analyze(mock_record)

            if repair_suggestion and repair_suggestion.should_retry:
                return {
                    "should_retry": True,
                    "tool_name": repair_suggestion.tool_name,
                    "arguments": repair_suggestion.arguments,
                    "reason": repair_suggestion.reason,
                    "error_type": repair_suggestion.error_type,
                    "confidence": repair_suggestion.confidence,
                    "follow_up": repair_suggestion.follow_up,
                }
            return None
        except Exception:
            return None

    def get_execution_history(self) -> list[dict[str, Any]]:
        """Get history of tool executions."""
        return self._execution_history.copy()

    def get_success_rate(self) -> float:
        """Calculate tool execution success rate."""
        if not self._execution_history:
            return 0.0
        successful = sum(1 for e in self._execution_history if e["success"])
        return successful / len(self._execution_history)

    def get_average_latency(self) -> float:
        """Calculate average tool execution latency."""
        if not self._execution_history:
            return 0.0
        total_latency = sum(e["latency_ms"] for e in self._execution_history)
        return total_latency / len(self._execution_history)

    def clear_history(self) -> None:
        """Clear execution history."""
        self._execution_history.clear()
