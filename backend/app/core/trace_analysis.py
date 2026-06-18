from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Iterable

from pydantic import BaseModel, Field

from backend.app.core.contracts import TraceEvent


class TraceStageSpan(BaseModel):
    name: str
    started_at: datetime
    ended_at: datetime
    duration_ms: float
    event_count: int


class TraceAnalysisReport(BaseModel):
    trace_id: str
    status: str
    event_count: int
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: float = 0.0
    first_event: str | None = None
    last_event: str | None = None
    event_counts: dict[str, int] = Field(default_factory=dict)
    error_events: list[dict[str, Any]] = Field(default_factory=list)
    stage_spans: list[TraceStageSpan] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    snapshot: dict[str, Any] = Field(default_factory=dict)


def analyze_trace_events(
    trace_id: str,
    events: Iterable[TraceEvent | dict[str, Any]],
) -> TraceAnalysisReport:
    normalized = [_coerce_trace_event(event) for event in events]
    normalized = [event for event in normalized if event is not None and event.trace_id == trace_id]
    normalized.sort(key=lambda event: event.timestamp)
    if not normalized:
        return TraceAnalysisReport(
            trace_id=trace_id,
            status="empty",
            event_count=0,
            warnings=["trace_has_no_events"],
            snapshot={"trace_id": trace_id, "event_count": 0},
        )

    started_at = normalized[0].timestamp
    ended_at = normalized[-1].timestamp
    event_counts = Counter(event.event for event in normalized)
    error_events = [_error_event_payload(event) for event in normalized if _is_error_event(event)]
    stage_spans = build_trace_stage_spans(normalized)
    warnings = build_trace_warnings(normalized, error_events=error_events)
    status = "failed" if error_events or normalized[-1].event.endswith(".failed") else "completed"
    duration_ms = _duration_ms(started_at, ended_at)
    return TraceAnalysisReport(
        trace_id=trace_id,
        status=status,
        event_count=len(normalized),
        started_at=started_at,
        ended_at=ended_at,
        duration_ms=duration_ms,
        first_event=normalized[0].event,
        last_event=normalized[-1].event,
        event_counts=dict(sorted(event_counts.items())),
        error_events=error_events,
        stage_spans=stage_spans,
        warnings=warnings,
        snapshot={
            "trace_id": trace_id,
            "status": status,
            "event_count": len(normalized),
            "duration_ms": duration_ms,
            "error_count": len(error_events),
            "stage_count": len(stage_spans),
            "last_event": normalized[-1].event,
        },
    )


def build_trace_stage_spans(events: Iterable[TraceEvent]) -> list[TraceStageSpan]:
    normalized = sorted(events, key=lambda event: event.timestamp)
    starts: dict[str, TraceEvent] = {}
    spans: list[TraceStageSpan] = []
    counts_by_stage: dict[str, int] = {}
    for event in normalized:
        stage = _stage_name(event)
        if not stage:
            continue
        counts_by_stage[stage] = counts_by_stage.get(stage, 0) + 1
        if event.event.endswith(".started") or event.event.endswith(".start"):
            starts[stage] = event
            continue
        if event.event.endswith((".completed", ".failed", ".end")) and stage in starts:
            started = starts.pop(stage)
            spans.append(
                TraceStageSpan(
                    name=stage,
                    started_at=started.timestamp,
                    ended_at=event.timestamp,
                    duration_ms=_duration_ms(started.timestamp, event.timestamp),
                    event_count=counts_by_stage.get(stage, 0),
                )
            )
    return spans


def build_trace_warnings(
    events: Iterable[TraceEvent],
    *,
    error_events: list[dict[str, Any]] | None = None,
) -> list[str]:
    normalized = sorted(events, key=lambda event: event.timestamp)
    warnings: list[str] = []
    if not normalized:
        return ["trace_has_no_events"]
    event_names = [event.event for event in normalized]
    if normalized[-1].event.endswith(".started"):
        warnings.append("trace_ends_with_started_event")
    if any(event.event == "agent.started" for event in normalized) and not any(
        event.event in {"agent.completed", "agent.failed"} for event in normalized
    ):
        warnings.append("agent_trace_missing_terminal_event")
    if error_events:
        warnings.append("trace_contains_error_events")
    if len(set(event_names)) != len(event_names):
        warnings.append("trace_contains_repeated_event_names")
    return warnings


def _coerce_trace_event(event: TraceEvent | dict[str, Any]) -> TraceEvent | None:
    if isinstance(event, TraceEvent):
        return event
    if isinstance(event, dict):
        try:
            return TraceEvent.model_validate(event)
        except Exception:
            return None
    return None


def _stage_name(event: TraceEvent) -> str:
    if "." not in event.event:
        return ""
    return event.event.rsplit(".", 1)[0]


def _is_error_event(event: TraceEvent) -> bool:
    if event.event.endswith(".failed") or event.event.endswith(".error"):
        return True
    return bool(event.data.get("error") or event.data.get("exception"))


def _error_event_payload(event: TraceEvent) -> dict[str, Any]:
    return {
        "event": event.event,
        "timestamp": event.timestamp.isoformat(),
        "error": str(event.data.get("error") or event.data.get("exception") or ""),
        "data": event.data,
    }


def _duration_ms(started_at: datetime, ended_at: datetime) -> float:
    return round(max((ended_at - started_at).total_seconds() * 1000, 0.0), 3)
