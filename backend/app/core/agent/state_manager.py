"""
State management engine - handles agent execution state tracking.

Extracted from AgentLoop to reduce coupling and improve testability.
Responsibilities:
  - Create and manage execution state
  - Track recovery information
  - Update state snapshots
  - Manage state transitions
"""

from typing import Any
from dataclasses import dataclass, field

from backend.app.core.contracts import RunContext, ExecutionFrame, RecoveryFrame, TaskFrame


@dataclass
class ExecutionState:
    """Complete execution state snapshot."""
    context: RunContext
    task_frame: TaskFrame
    execution_frame: ExecutionFrame
    recovery_frame: RecoveryFrame | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    iterations: int = 0
    observations: list[str] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    reflections: list[str] = field(default_factory=list)


class StateManager:
    """Manages agent execution state."""

    def __init__(self):
        self._state_history: list[ExecutionState] = []

    def create_initial_state(
        self,
        context: RunContext,
        task_frame: TaskFrame,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionState:
        """
        Create initial execution state.

        Args:
            context: Execution context
            task_frame: Task frame
            metadata: Additional metadata

        Returns:
            Initial ExecutionState
        """
        execution_frame = ExecutionFrame(
            trace_id=context.trace_id,
            agent_id=context.agent_id,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            request_id=context.request_id,
            task=task_frame,
            session_id=context.session_id,
            metadata=metadata or {},
        )

        state = ExecutionState(
            context=context,
            task_frame=task_frame,
            execution_frame=execution_frame,
            metadata=metadata or {},
        )

        self._state_history.append(state)
        return state

    def update_state(
        self,
        state: ExecutionState,
        **updates: Any,
    ) -> ExecutionState:
        """
        Update state with new values.

        Args:
            state: Current state
            **updates: Fields to update

        Returns:
            Updated state
        """
        for key, value in updates.items():
            if hasattr(state, key):
                setattr(state, key, value)

        self._state_history.append(state)
        return state

    def get_state(self, state: ExecutionState) -> dict[str, Any]:
        """
        Get state as dictionary.

        Args:
            state: State to serialize

        Returns:
            State dictionary
        """
        return {
            "context": {
                "trace_id": state.context.trace_id,
                "agent_id": state.context.agent_id,
                "tenant_id": state.context.tenant_id,
                "user_id": state.context.user_id,
                "request_id": state.context.request_id,
            },
            "task": {
                "goal": state.task_frame.goal,
                "description": state.task_frame.description,
                "risk_level": state.task_frame.risk_level,
            },
            "execution": {
                "iterations": state.iterations,
                "observations": len(state.observations),
                "tool_results": len(state.tool_results),
                "reflections": len(state.reflections),
            },
            "recovery": {
                "branch": state.recovery_frame.branch if state.recovery_frame else None,
                "retryable": state.recovery_frame.retryable if state.recovery_frame else False,
            },
            "metadata": state.metadata,
        }

    def set_recovery_frame(
        self,
        state: ExecutionState,
        recovery_frame: RecoveryFrame,
    ) -> ExecutionState:
        """
        Set recovery frame in state.

        Args:
            state: Current state
            recovery_frame: Recovery frame to set

        Returns:
            Updated state
        """
        state.recovery_frame = recovery_frame
        self._state_history.append(state)
        return state

    def apply_recovery_update(
        self,
        state: ExecutionState,
        retry_tool: str | None = None,
        confidence: float | None = None,
        follow_up: list[str] | None = None,
        remediation: str | None = None,
        status_detail: str | None = None,
        retryable: bool = False,
    ) -> ExecutionState:
        """
        Apply recovery update to state.

        Args:
            state: Current state
            retry_tool: Tool to retry
            confidence: Confidence score
            follow_up: Follow-up actions
            remediation: Remediation strategy
            status_detail: Status detail
            retryable: Whether retryable

        Returns:
            Updated state
        """
        if state.recovery_frame is None:
            state.recovery_frame = RecoveryFrame(
                branch="continue",
                retryable=retryable,
                confidence=confidence or 0.5,
                tool_name=retry_tool,
                follow_up=follow_up or [],
                status_detail=status_detail or "",
                remediation=remediation or "",
            )
        else:
            if retry_tool:
                state.recovery_frame.tool_name = retry_tool
            if confidence is not None:
                state.recovery_frame.confidence = max(
                    float(state.recovery_frame.confidence or 0.5),
                    confidence,
                )
            if follow_up:
                existing = list(state.recovery_frame.follow_up or [])
                state.recovery_frame.follow_up = list(dict.fromkeys(existing + follow_up))
            if remediation:
                state.recovery_frame.remediation = remediation
            if status_detail:
                state.recovery_frame.status_detail = status_detail
            state.recovery_frame.retryable = retryable

        self._state_history.append(state)
        return state

    def attach_execution_frame(
        self,
        state: ExecutionState,
        execution_frame: ExecutionFrame,
    ) -> ExecutionState:
        """
        Attach execution frame to state.

        Args:
            state: Current state
            execution_frame: Frame to attach

        Returns:
            Updated state
        """
        state.execution_frame = execution_frame
        self._state_history.append(state)
        return state

    def attach_plan_frame(
        self,
        state: ExecutionState,
        plan_frame: Any,  # PlanFrame
    ) -> ExecutionState:
        """
        Attach plan frame to state.

        Args:
            state: Current state
            plan_frame: Frame to attach

        Returns:
            Updated state
        """
        state.execution_frame.plan = plan_frame
        self._state_history.append(state)
        return state

    def apply_state_snapshot(
        self,
        state: ExecutionState,
        workflow_state: dict[str, Any] | None = None,
        approval_state: dict[str, Any] | None = None,
        browser_state: dict[str, Any] | None = None,
        desktop_state: dict[str, Any] | None = None,
    ) -> ExecutionState:
        """
        Apply state snapshot.

        Args:
            state: Current state
            workflow_state: Workflow state
            approval_state: Approval state
            browser_state: Browser state
            desktop_state: Desktop state

        Returns:
            Updated state
        """
        if workflow_state:
            state.execution_frame.workflow_state = workflow_state
        if approval_state:
            state.execution_frame.approval_state = approval_state
        if browser_state:
            state.execution_frame.browser_state = browser_state
        if desktop_state:
            state.execution_frame.desktop_state = desktop_state

        self._state_history.append(state)
        return state

    def get_state_history(self) -> list[ExecutionState]:
        """Get state history."""
        return self._state_history.copy()

    def get_latest_state(self) -> ExecutionState | None:
        """Get latest state."""
        return self._state_history[-1] if self._state_history else None

    def clear_history(self) -> None:
        """Clear state history."""
        self._state_history.clear()
