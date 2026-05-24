from __future__ import annotations

from typing import Any

from backend.app.core.agent_state_manager import AgentRunState
from backend.app.core.run_view import RunView


class AgentRuntimeAdapter:
    def __init__(self, state_manager: Any) -> None:
        self.state_manager = state_manager

    def build_recovery_view(self, state: AgentRunState) -> dict[str, Any]:
        recovery_frame = getattr(state, 'recovery_frame', None)
        if recovery_frame is None:
            return {}
        if hasattr(recovery_frame, 'model_dump'):
            dumped = recovery_frame.model_dump(mode='json')
            return dumped if isinstance(dumped, dict) else {'value': dumped}
        return dict(getattr(recovery_frame, '__dict__', {}))

    def build_snapshot(self, state: AgentRunState) -> dict[str, Any]:
        task_frame = getattr(state, 'task_frame', None)
        execution_frame = getattr(state, 'execution_frame', None)
        plan_frame = getattr(state, 'plan_frame', None)
        return {
            'task': task_frame.model_dump(mode='json') if hasattr(task_frame, 'model_dump') else {},
            'execution_frame': execution_frame.model_dump(mode='json') if hasattr(execution_frame, 'model_dump') else {},
            'plan': plan_frame.model_dump(mode='json') if hasattr(plan_frame, 'model_dump') else {},
        }

    def build_summary(self, state: AgentRunState) -> dict[str, Any]:
        execution_frame = getattr(state, 'execution_frame', None)
        return {
            'trace_id': state.context.trace_id,
            'agent_id': state.context.agent_id,
            'metadata': state.metadata,
            'execution_summary': execution_frame.execution_summary if hasattr(execution_frame, 'execution_summary') else {},
        }

    def build_run_view(self, state: AgentRunState, *, status: str, answer: str | None = None) -> RunView:
        return RunView(
            trace_id=state.context.trace_id,
            status=status,
            answer=answer,
            recovery=self.build_recovery_view(state),
            snapshot=self.build_snapshot(state),
            summary=self.build_summary(state),
            metadata=state.metadata or {},
        )

    def normalize_run(self, state: AgentRunState, *, status: str, answer: str | None = None) -> dict[str, Any]:
        return self.build_run_view(state, status=status, answer=answer).model_dump()
