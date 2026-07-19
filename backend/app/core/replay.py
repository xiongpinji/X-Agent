from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.core.runs import RunStore
from backend.app.core.tracing import TraceStore


@dataclass
class ReplayFrame:
    trace_id: str
    task: str = ""
    stage: str = ""
    events: list[dict[str, Any]] = field(default_factory=list)
    execution_summary: dict[str, Any] = field(default_factory=dict)
    resumed_from: str | None = None
    previous_stage: str | None = None
    subtasks: list[str] = field(default_factory=list)
    subtask_status: dict[str, str] = field(default_factory=dict)
    current_subtask_index: int = 0


class ReplayEngine:
    """Build a continuous replay view across resumed runs."""

    def __init__(self, run_store: RunStore | None = None, trace_store: TraceStore | None = None) -> None:
        self.run_store = run_store
        self.trace_store = trace_store

    def build(self, trace_id: str) -> ReplayFrame:
        run = self.run_store.get(trace_id) if self.run_store is not None else None
        trace_events = self.trace_store.list_events(trace_id) if self.trace_store is not None else []
        execution_summary = run.execution_summary if run is not None else {}
        resumed_from = execution_summary.get("resumed_from") if isinstance(execution_summary, dict) else None
        previous_stage = execution_summary.get("previous_stage") if isinstance(execution_summary, dict) else None
        subtasks = execution_summary.get("subtasks", []) if isinstance(execution_summary, dict) else []
        subtask_status = execution_summary.get("subtask_status", {}) if isinstance(execution_summary, dict) else {}
        current_subtask_index = int(execution_summary.get("current_subtask_index", 0) or 0) if isinstance(execution_summary, dict) else 0
        return ReplayFrame(
            trace_id=trace_id,
            task=run.task if run is not None else "",
            stage=run.stage if run is not None else "",
            events=[event.model_dump(mode="json") for event in trace_events],
            execution_summary=execution_summary,
            resumed_from=str(resumed_from) if resumed_from else None,
            previous_stage=str(previous_stage) if previous_stage else None,
            subtasks=list(subtasks) if isinstance(subtasks, list) else [],
            subtask_status=dict(subtask_status) if isinstance(subtask_status, dict) else {},
            current_subtask_index=current_subtask_index,
        )

    def build_continuous(self, trace_id: str) -> dict[str, Any]:
        frame = self.build(trace_id)
        return {
            "trace_id": frame.trace_id,
            "task": frame.task,
            "stage": frame.stage,
            "resumed_from": frame.resumed_from,
            "previous_stage": frame.previous_stage,
            "event_count": len(frame.events),
            "events": frame.events,
            "execution_summary": frame.execution_summary,
        }


replay_engine = ReplayEngine()
