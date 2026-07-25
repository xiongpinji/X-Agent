"""Phase execution context - shared state across all execution phases.

This module defines PhaseContext, a dataclass that encapsulates all shared state
needed by different execution phases. It serves as the primary communication
mechanism between phases, reducing coupling and improving testability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from backend.app.core.contracts import (
    ExecutionFrame,
    PlanFrame,
    RunContext,
    TaskFrame,
    ToolCallRecord,
)

if TYPE_CHECKING:
    from backend.app.core.agent import AgentLoop, AgentTrajectory


@dataclass
class PhaseContext:
    """Shared execution context across all phases.

    This dataclass encapsulates all state needed by initialization, planning,
    execution, and completion phases. It reduces parameter passing and provides
    a clear contract for phase interactions.

    Attributes:
        loop: Reference to the AgentLoop instance
        context: RunContext with trace, tenant, user, and budget info
        task: The original task string
        trajectory: AgentTrajectory tracking task decomposition and progress
        extra_context: Additional context passed by caller
        execution_frame: ExecutionFrame for tracing and state management
        task_frame: TaskFrame with goal, description, and risk level
        plan_frame: PlanFrame with steps and status
        compact_context: Compressed context for LLM and orchestration
        tool_calls: List of executed tool calls
        observations: List of observations from memory and tools
        answer: Final answer (populated during execution)
        iteration: Current iteration count (populated during execution)
    """

    loop: AgentLoop
    context: RunContext
    task: str
    trajectory: AgentTrajectory
    extra_context: dict[str, object]
    execution_frame: ExecutionFrame
    task_frame: TaskFrame
    plan_frame: PlanFrame
    compact_context: dict[str, object]
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)
    answer: str = ""
    iteration: int = 0

    def get_session_id(self) -> str | None:
        """Get session ID from context or extra_context.

        Returns:
            Session ID if available, None otherwise.
        """
        return self.context.session_id or str(
            self.extra_context.get("session_id") or ""
        ) or None

    def get_resume_trace_id(self) -> str:
        """Get resume trace ID from extra_context.

        Returns:
            Resume trace ID if available, empty string otherwise.
        """
        return str(self.extra_context.get("resume_trace_id") or "")

    def is_resuming(self) -> bool:
        """Check if this is a resumed execution.

        Returns:
            True if resume_trace_id is present and non-empty.
        """
        return bool(self.get_resume_trace_id())
