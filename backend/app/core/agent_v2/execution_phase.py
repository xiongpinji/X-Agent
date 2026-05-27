"""Base execution phase class for agent execution pipeline.

This module defines the ExecutionPhase abstract base class that all concrete
phases inherit from. It establishes the interface and lifecycle for phase execution.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.core.agent_v2.phase_context import PhaseContext


class ExecutionPhase(ABC):
    """Abstract base class for agent execution phases.

    Each phase in the agent execution pipeline (initialization, planning,
    execution, completion) inherits from this class and implements the
    execute() method to perform its specific responsibilities.

    The phase-based architecture decomposes the monolithic AgentLoop.run()
    method into focused, testable, and composable units.
    """

    @abstractmethod
    async def execute(self, phase_ctx: PhaseContext) -> object:
        """Execute this phase.

        Args:
            phase_ctx: Shared execution context containing all state needed
                      by this phase and subsequent phases.

        Returns:
            Phase-specific result. The return type depends on the concrete
            phase implementation:
            - InitializationPhase: None (modifies phase_ctx in-place)
            - PlanningPhase: list[AgentPlanStep]
            - ExecutionPhase: tuple[str, list[ToolCallRecord]]
            - CompletionPhase: AgentRunResponse

        Raises:
            Exception: Any errors during phase execution are propagated
                      to the caller for handling.
        """
        pass

    def _validate_context(self, phase_ctx: PhaseContext) -> None:
        """Validate that phase_ctx has required attributes.

        Args:
            phase_ctx: Context to validate.

        Raises:
            ValueError: If required attributes are missing or invalid.
        """
        if not phase_ctx.loop:
            raise ValueError("PhaseContext.loop is required")
        if not phase_ctx.context:
            raise ValueError("PhaseContext.context is required")
        if not phase_ctx.task:
            raise ValueError("PhaseContext.task is required")
        if not phase_ctx.trajectory:
            raise ValueError("PhaseContext.trajectory is required")
