"""Agent state management for execution lifecycle.

This module provides state machine functionality for tracking agent execution
through different phases (initialization, planning, execution, recovery, completion).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Optional


class AgentState(str, Enum):
    """Agent execution states."""

    IDLE = "idle"
    INITIALIZING = "initializing"
    PLANNING = "planning"
    EXECUTING = "executing"
    RECOVERING = "recovering"
    COMPLETING = "completing"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class InvalidStateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, from_state: AgentState, to_state: AgentState) -> None:
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"Cannot transition from {from_state.value} to {to_state.value}"
        )


class AgentStateManager:
    """Manages agent execution state and state transitions.

    Implements a state machine with clear transition rules:
    - IDLE -> INITIALIZING -> PLANNING -> EXECUTING -> COMPLETING -> COMPLETED
    - EXECUTING <-> RECOVERING (if failures occur)
    - Any state -> PAUSED (can pause)
    - PAUSED -> previous state (can resume)
    """

    # Valid state transitions
    _TRANSITIONS = {
        AgentState.IDLE: {AgentState.INITIALIZING, AgentState.PAUSED},
        AgentState.INITIALIZING: {AgentState.PLANNING, AgentState.FAILED, AgentState.PAUSED},
        AgentState.PLANNING: {AgentState.EXECUTING, AgentState.FAILED, AgentState.PAUSED},
        AgentState.EXECUTING: {
            AgentState.RECOVERING,
            AgentState.COMPLETING,
            AgentState.FAILED,
            AgentState.PAUSED,
        },
        AgentState.RECOVERING: {
            AgentState.EXECUTING,
            AgentState.COMPLETING,
            AgentState.FAILED,
            AgentState.PAUSED,
        },
        AgentState.COMPLETING: {AgentState.COMPLETED, AgentState.FAILED, AgentState.PAUSED},
        AgentState.COMPLETED: {AgentState.PAUSED},
        AgentState.FAILED: {AgentState.PAUSED},
        AgentState.PAUSED: {
            AgentState.INITIALIZING,
            AgentState.PLANNING,
            AgentState.EXECUTING,
            AgentState.RECOVERING,
            AgentState.COMPLETING,
            AgentState.COMPLETED,
            AgentState.FAILED,
        },
    }

    def __init__(self) -> None:
        """Initialize state manager with IDLE state."""
        self.current_state = AgentState.IDLE
        self.state_history: list[tuple[AgentState, datetime]] = [
            (AgentState.IDLE, datetime.now(UTC))
        ]
        self._paused_state: Optional[AgentState] = None

    def transition_to(self, new_state: AgentState) -> None:
        """Transition to a new state.

        Args:
            new_state: Target state to transition to.

        Raises:
            InvalidStateTransitionError: If transition is not allowed.
        """
        if not self._can_transition(self.current_state, new_state):
            raise InvalidStateTransitionError(self.current_state, new_state)

        # Handle pause/resume
        if new_state == AgentState.PAUSED:
            self._paused_state = self.current_state
        elif self._paused_state is not None:
            self._paused_state = None

        self.state_history.append((self.current_state, datetime.now(UTC)))
        self.current_state = new_state

    def _can_transition(self, from_state: AgentState, to_state: AgentState) -> bool:
        """Check if transition is allowed.

        Args:
            from_state: Current state.
            to_state: Target state.

        Returns:
            True if transition is allowed, False otherwise.
        """
        return to_state in self._TRANSITIONS.get(from_state, set())

    def get_state(self) -> AgentState:
        """Get current state.

        Returns:
            Current agent state.
        """
        return self.current_state

    def get_history(self) -> list[tuple[AgentState, datetime]]:
        """Get state transition history.

        Returns:
            List of (state, timestamp) tuples in chronological order.
        """
        return self.state_history.copy()

    def is_terminal_state(self) -> bool:
        """Check if current state is terminal.

        Terminal states are COMPLETED and FAILED.

        Returns:
            True if in terminal state, False otherwise.
        """
        return self.current_state in {AgentState.COMPLETED, AgentState.FAILED}

    def is_paused(self) -> bool:
        """Check if execution is paused.

        Returns:
            True if paused, False otherwise.
        """
        return self.current_state == AgentState.PAUSED

    def get_paused_state(self) -> Optional[AgentState]:
        """Get the state before pause.

        Returns:
            The state before pause, or None if not paused.
        """
        return self._paused_state

    def reset(self) -> None:
        """Reset state manager to initial state.

        Clears history and returns to IDLE state.
        """
        self.current_state = AgentState.IDLE
        self.state_history = [(AgentState.IDLE, datetime.now(UTC))]
        self._paused_state = None
