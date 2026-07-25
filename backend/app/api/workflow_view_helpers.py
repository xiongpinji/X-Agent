from __future__ import annotations

from typing import Any

from backend.app.api.workflow_view_components import (
    build_workflow_components as _build_workflow_components,
)
from backend.app.api.workflow_view_header import build_workflow_header
from backend.app.api.workflow_view_panels import build_workflow_panels
from backend.app.core.workflows import WorkflowRunRecord


def build_overview_panel(run: WorkflowRunRecord, failure_count: int, compensation_count: int, trace_ids: list[str]) -> dict[str, object]:
    overview = build_workflow_panels(run, [], [], [], [], trace_ids)["overview"]
    overview["recovery_branch"] = run.snapshot.get("last_agent_recovery_branch") if isinstance(run.snapshot, dict) else None
    overview["recovery_plan"] = run.snapshot.get("last_agent_execution_summary", {}).get("recovery_plan", {}) if isinstance(run.snapshot, dict) else {}
    overview["next_actions"] = overview.get("recovery", {}).get("next_actions", []) if isinstance(overview.get("recovery", {}), dict) else []
    return overview


def build_header_view(run: WorkflowRunRecord, failure_count: int, compensation_count: int) -> dict[str, object]:
    return build_workflow_header(run, failure_count, compensation_count)


def build_metrics_view(run: WorkflowRunRecord, timeline: list[dict[str, object]], node_results: list[dict[str, object]], failure_count: int, compensation_count: int) -> dict[str, object]:
    completed_nodes = sum(1 for item in node_results if str(item.get("status")) == "completed")
    duration_seconds = None
    if run.started_at and run.completed_at:
        duration_seconds = max((run.completed_at - run.started_at).total_seconds(), 0)
    total_attempts = sum(int(item.get("attempts") or 0) for item in node_results)
    average_attempts = round(total_attempts / len(node_results), 3) if node_results else 0.0
    success_rate = round(completed_nodes / len(node_results), 3) if node_results else 0.0
    return {"event_count": len(timeline), "node_count": len(node_results), "failure_count": failure_count, "compensation_count": compensation_count, "duration_seconds": duration_seconds, "node_success_rate": success_rate, "average_attempts": average_attempts}


def build_node_result_summary(node_results: list[dict[str, object]]) -> dict[str, object]:
    by_status: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for item in node_results:
        status = str(item.get("status") or "unknown")
        node_type = str(item.get("node_type") or "unknown")
        by_status[status] = by_status.get(status, 0) + 1
        by_type[node_type] = by_type.get(node_type, 0) + 1
    return {"total": len(node_results), "by_status": by_status, "by_type": by_type, "failure_nodes": [item["node_id"] for item in node_results if item.get("error")], "ui": {"cards": [{"label": status, "value": count} for status, count in by_status.items()]}}


def build_timeline_sections(timeline: list[dict[str, object]], *args: Any, **kwargs: Any) -> list[dict[str, object]]:
    return [{"title": "Run", "events": timeline}]


def build_failure_view(failure_events: list[dict[str, object]]) -> list[dict[str, object]]:
    return failure_events


def build_compensation_view(compensation_events: list[dict[str, object]]) -> list[dict[str, object]]:
    return compensation_events


def build_workflow_components() -> dict[str, dict[str, object]]:
    return _build_workflow_components()
