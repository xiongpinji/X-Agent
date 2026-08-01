"""Agent execution coordinator for orchestrating execution phases.

This module provides the main execution coordinator that manages the lifecycle
of agent execution across multiple phases (initialization, planning, execution,
recovery, completion).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.app.core.agent_v2.state_manager import AgentState, AgentStateManager
from backend.app.core.contracts import AgentRunResponse, RunContext, RunStatus

if TYPE_CHECKING:
    from backend.app.core.agent_phases import (
        PhaseContext,
    )

logger = logging.getLogger(__name__)


class AgentExecutor:
    """Coordinates execution of agent across multiple phases.

    Manages the lifecycle of agent execution by orchestrating phases:
    1. Initialization - Setup execution context
    2. Planning - Generate execution plan
    3. Execution - Execute plan steps
    4. Recovery - Handle failures (optional)
    5. Completion - Finalize and store results

    Attributes:
        state_manager: Manages execution state transitions.
        max_iterations: Maximum iterations for execution phase.
    """

    def __init__(
        self,
        max_iterations: int = 20,
    ) -> None:
        """Initialize agent executor.

        Args:
            max_iterations: Maximum iterations for execution phase.
        """
        self.state_manager = AgentStateManager()
        self.max_iterations = max_iterations
        self._phases: dict[AgentState, object] = {}

    def register_phase(self, state: AgentState, phase: object) -> None:
        """Register a phase for a specific state.

        Args:
            state: State associated with the phase.
            phase: Phase executor object.
        """
        self._phases[state] = phase

    async def execute(
        self,
        context: RunContext,
        task: str,
        phase_context: PhaseContext,
        phases: list[tuple[AgentState, object]],
    ) -> AgentRunResponse:
        """Execute complete agent workflow.

        Orchestrates execution through all phases with proper state management
        and error handling.

        Args:
            context: Execution context with trace/auth info.
            task: Task description.
            phase_context: Shared context across phases.
            phases: List of (state, phase_executor) tuples in execution order.

        Returns:
            AgentRunResponse with execution results.

        Raises:
            Exception: Re-raised after error handling if execution fails.
        """
        try:
            # Transition to initializing
            self.state_manager.transition_to(AgentState.INITIALIZING)
            logger.debug(
                "Starting agent execution",
                extra={
                    "trace_id": context.trace_id,
                    "task": task[:100],
                },
            )

            # Execute each phase
            for state, phase in phases:
                if self.state_manager.is_terminal_state():
                    logger.info(
                        "Terminal state reached, stopping execution",
                        extra={"state": self.state_manager.current_state.value},
                    )
                    break

                # Check if phase can be skipped
                if hasattr(phase, "can_skip") and phase.can_skip(phase_context):
                    logger.debug(
                        f"Skipping phase {state.value}",
                        extra={"trace_id": context.trace_id},
                    )
                    continue

                # Transition to phase state
                self.state_manager.transition_to(state)
                logger.debug(
                    f"Executing phase {state.value}",
                    extra={"trace_id": context.trace_id},
                )

                # Execute phase
                await phase.execute(phase_context)

            # Mark as completed
            self.state_manager.transition_to(AgentState.COMPLETING)
            self.state_manager.transition_to(AgentState.COMPLETED)

            logger.info(
                "Agent execution completed successfully",
                extra={
                    "trace_id": context.trace_id,
                    "iterations": getattr(phase_context, "iteration", 0),
                },
            )

            # Return response from phase context
            if hasattr(phase_context, "response"):
                return phase_context.response

            # Fallback response if not set by phases
            return self._build_fallback_response(context, phase_context)

        except Exception as e:
            # Handle execution error
            self.state_manager.transition_to(AgentState.FAILED)
            logger.error(
                f"Agent execution failed: {e!s}",
                extra={
                    "trace_id": context.trace_id,
                    "state": self.state_manager.current_state.value,
                },
                exc_info=True,
            )

            # Build error response
            return self._build_error_response(context, e, phase_context)

    def get_state(self) -> AgentState:
        """Get current execution state.

        Returns:
            Current agent state.
        """
        return self.state_manager.get_state()

    def get_state_history(self) -> list[tuple[str, str]]:
        """Get state transition history.

        Returns:
            List of (state, timestamp) tuples as strings.
        """
        history = self.state_manager.get_history()
        return [
            (state.value, timestamp.isoformat())
            for state, timestamp in history
        ]

    def is_completed(self) -> bool:
        """Check if execution is completed.

        Returns:
            True if in COMPLETED or FAILED state.
        """
        return self.state_manager.is_terminal_state()

    def pause(self) -> None:
        """Pause execution.

        Transitions to PAUSED state, preserving current state for resume.
        """
        if not self.state_manager.is_terminal_state():
            self.state_manager.transition_to(AgentState.PAUSED)
            logger.info("Agent execution paused")

    def resume(self) -> None:
        """Resume execution from pause.

        Transitions back to the state before pause.
        """
        if self.state_manager.is_paused():
            paused_state = self.state_manager.get_paused_state()
            if paused_state:
                self.state_manager.transition_to(paused_state)
                logger.info(f"Agent execution resumed from {paused_state.value}")

    def reset(self) -> None:
        """Reset executor to initial state.

        Clears state history and returns to IDLE.
        """
        self.state_manager.reset()
        logger.debug("Agent executor reset to initial state")

    def _build_fallback_response(
        self,
        context: RunContext,
        phase_context: PhaseContext,
    ) -> AgentRunResponse:
        """Build fallback response when phases don't set response.

        Args:
            context: Execution context.
            phase_context: Phase context with execution data.

        Returns:
            AgentRunResponse with available data.
        """
        answer = getattr(phase_context, "answer", "Execution completed")
        tool_calls = getattr(phase_context, "tool_calls", [])

        return AgentRunResponse(
            trace_id=context.trace_id,
            agent_id=context.agent_id,
            status=RunStatus.COMPLETED,
            answer=answer,
            iterations=getattr(phase_context, "iteration", 0),
            memory_hits=len(getattr(phase_context, "observations", [])),
            tool_calls=tool_calls,
            events=[],
            plan=[],
            execution_summary={},
            snapshot={},
        )

    def _build_error_response(
        self,
        context: RunContext,
        error: Exception,
        phase_context: PhaseContext | None = None,
    ) -> AgentRunResponse:
        """Build error response.

        Args:
            context: Execution context.
            error: Exception that occurred.
            phase_context: Optional phase context with partial data.

        Returns:
            AgentRunResponse with error status.
        """
        error_msg = str(error)
        answer = f"Execution failed: {error_msg}"

        if phase_context:
            answer = getattr(phase_context, "answer", answer)

        return AgentRunResponse(
            trace_id=context.trace_id,
            agent_id=context.agent_id,
            status=RunStatus.FAILED,
            answer=answer,
            error=error_msg,
            iterations=getattr(phase_context, "iteration", 0) if phase_context else 0,
            memory_hits=0,
            tool_calls=getattr(phase_context, "tool_calls", []) if phase_context else [],
            events=[],
            plan=[],
            execution_summary={
                "error": error_msg,
                "state": self.state_manager.current_state.value,
            },
            snapshot={},
        )
