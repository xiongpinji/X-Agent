from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.app.core.contracts import TraceEvent
from backend.app.core.trace_analysis import analyze_trace_events, build_trace_stage_spans


def _event(trace_id: str, name: str, offset_ms: int, **data: object) -> TraceEvent:
    return TraceEvent(
        trace_id=trace_id,
        event=name,
        timestamp=datetime(2026, 6, 9, 12, 0, tzinfo=UTC) + timedelta(milliseconds=offset_ms),
        data=dict(data),
    )


def test_analyze_trace_events_builds_completed_snapshot() -> None:
    events = [
        _event("trace-1", "agent.started", 0, task="write tests"),
        _event("trace-1", "tool.started", 20, tool="pytest"),
        _event("trace-1", "tool.completed", 80, tool="pytest"),
        _event("trace-1", "agent.completed", 120),
    ]

    report = analyze_trace_events("trace-1", events)

    assert report.status == "completed"
    assert report.event_count == 4
    assert report.duration_ms == 120
    assert report.first_event == "agent.started"
    assert report.last_event == "agent.completed"
    assert report.event_counts["tool.started"] == 1
    assert report.snapshot == {
        "trace_id": "trace-1",
        "status": "completed",
        "event_count": 4,
        "duration_ms": 120,
        "error_count": 0,
        "stage_count": 2,
        "last_event": "agent.completed",
    }


def test_analyze_trace_events_detects_failed_trace_and_errors() -> None:
    events = [
        _event("trace-1", "agent.started", 0),
        _event("trace-1", "tool.failed", 25, error="pytest failed"),
        _event("trace-1", "agent.failed", 30, exception="validation failed"),
    ]

    report = analyze_trace_events("trace-1", events)

    assert report.status == "failed"
    assert [item["event"] for item in report.error_events] == ["tool.failed", "agent.failed"]
    assert "trace_contains_error_events" in report.warnings
    assert report.snapshot["error_count"] == 2


def test_analyze_trace_events_filters_foreign_or_invalid_events() -> None:
    events = [
        _event("trace-2", "agent.started", 0),
        {"trace_id": "trace-1", "event": "agent.started", "timestamp": "2026-06-09T12:00:00+00:00"},
        {"not": "a trace event"},
        _event("trace-1", "agent.completed", 10),
    ]

    report = analyze_trace_events("trace-1", events)

    assert report.event_count == 2
    assert report.status == "completed"
    assert report.warnings == []


def test_analyze_trace_events_reports_empty_trace() -> None:
    report = analyze_trace_events("trace-empty", [])

    assert report.status == "empty"
    assert report.event_count == 0
    assert report.warnings == ["trace_has_no_events"]
    assert report.snapshot == {"trace_id": "trace-empty", "event_count": 0}


def test_trace_stage_spans_pair_started_and_terminal_events() -> None:
    spans = build_trace_stage_spans(
        [
            _event("trace-1", "agent.started", 0),
            _event("trace-1", "agent.step", 10),
            _event("trace-1", "agent.completed", 30),
            _event("trace-1", "tool.started", 40),
            _event("trace-1", "tool.failed", 55),
        ]
    )

    assert [(span.name, span.duration_ms, span.event_count) for span in spans] == [
        ("agent", 30, 3),
        ("tool", 15, 2),
    ]


def test_analyze_trace_events_warns_for_missing_terminal_agent_event() -> None:
    report = analyze_trace_events(
        "trace-1",
        [
            _event("trace-1", "agent.started", 0),
            _event("trace-1", "tool.started", 10),
        ],
    )

    assert report.status == "completed"
    assert "agent_trace_missing_terminal_event" in report.warnings
    assert "trace_ends_with_started_event" in report.warnings
