from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.core.contracts import (
    ExecutionFrame,
    PlanFrame,
    RecoveryFrame,
    RunContext,
    TaskFrame,
)


@dataclass
class AgentRunState:
    context: RunContext
    task_frame: TaskFrame
    execution_frame: ExecutionFrame | None = None
    plan_frame: PlanFrame | None = None
    recovery_frame: RecoveryFrame | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentStateManager:
    def create_initial_state(self, context: RunContext, task_frame: TaskFrame, metadata: dict[str, Any] | None = None) -> AgentRunState:
        return AgentRunState(context=context, task_frame=task_frame, metadata=metadata or {})

    def attach_execution_frame(self, state: AgentRunState, execution_frame: ExecutionFrame) -> AgentRunState:
        state.execution_frame = execution_frame
        return state

    def attach_plan_frame(self, state: AgentRunState, plan_frame: PlanFrame) -> AgentRunState:
        state.plan_frame = plan_frame
        return state

    def set_recovery_frame(self, state: AgentRunState, recovery_frame: RecoveryFrame) -> AgentRunState:
        state.recovery_frame = recovery_frame
        return state

    def apply_repair_update(
        self,
        state: AgentRunState,
        *,
        retry_tool: str | None = None,
        confidence: float | None = None,
        follow_up: list[str] | None = None,
        remediation: str | None = None,
        status_detail: str | None = None,
        retryable: bool = True,
    ) -> AgentRunState:
        recovery = state.recovery_frame or self.build_initial_recovery(tool_name=retry_tool)
        recovery.tool_name = retry_tool or recovery.tool_name
        if confidence is not None:
            recovery.confidence = confidence
        if follow_up is not None:
            recovery.follow_up = follow_up
        if remediation is not None:
            recovery.remediation = remediation
        if status_detail is not None:
            recovery.status_detail = status_detail
        recovery.retryable = retryable
        state.recovery_frame = recovery
        return state

    def apply_state_snapshot(
        self,
        state: AgentRunState,
        *,
        workflow_state: dict[str, Any] | None = None,
        approval_state: dict[str, Any] | None = None,
        browser_state: dict[str, Any] | None = None,
        desktop_state: dict[str, Any] | None = None,
    ) -> AgentRunState:
        if state.execution_frame is not None:
            summary = state.execution_frame.execution_summary
            if workflow_state:
                summary.setdefault("workflow_state", {}).update(workflow_state)
            if approval_state:
                summary.setdefault("approval_state", {}).update(approval_state)
            if browser_state:
                summary.setdefault("browser_state", {}).update(browser_state)
            if desktop_state:
                summary.setdefault("desktop_state", {}).update(desktop_state)
        return state

    def build_initial_recovery(self, tool_name: str | None = None) -> RecoveryFrame:
        return RecoveryFrame(
            branch="continue",
            retryable=False,
            confidence=0.5,
            tool_name=tool_name,
            follow_up=["continue planning", "execute selected tool"],
            status_detail="initial agent recovery frame",
            remediation="continue with plan execution",
        )
