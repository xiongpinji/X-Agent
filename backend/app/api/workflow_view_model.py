from __future__ import annotations

from backend.app.api.recovery_helpers import build_recovery_payload
from backend.app.api.workflow_view_components import build_workflow_components
from backend.app.api.workflow_view_header import build_workflow_header
from backend.app.api.workflow_view_panels import build_workflow_panels
from backend.app.api.workflow_view_summary import build_workflow_summary
from backend.app.core.workflows import WorkflowRunRecord


def build_workflow_run_view_model(run: WorkflowRunRecord, timeline: list[dict[str, object]], node_results: list[dict[str, object]], failure_chain: list[dict[str, object]], compensation_chain: list[dict[str, object]], trace_ids: list[str]) -> dict[str, object]:
    header = build_workflow_header(run, len(failure_chain), len(compensation_chain))
    summary = build_workflow_summary(run, failure_chain, compensation_chain, trace_ids)
    metrics = _build_workflow_metrics(run, timeline, node_results, failure_chain, compensation_chain)
    snapshot = run.snapshot if hasattr(run, "snapshot") and isinstance(run.snapshot, dict) else {}
    execution_summary = snapshot.get("last_agent_execution_summary", {}) if isinstance(snapshot, dict) else {}
    recovery_plan = execution_summary.get("recovery_plan", {}) if isinstance(execution_summary, dict) else {}
    return {
        "resource_type": "workflow_run",
        "run_id": run.run_id,
        "workflow_id": run.workflow_id,
        "header": header,
        "summary": summary,
        "recovery": build_recovery_payload(
            status=run.status.value,
            resource_type="workflow_run",
            resource_id=run.run_id,
            next_actions=execution_summary.get("next_actions", []) if isinstance(execution_summary, dict) else [],
            recovery_plan=recovery_plan,
            branch=snapshot.get("last_agent_recovery_branch") if isinstance(snapshot, dict) else None,
            retryable=run.status.value != "completed",
            confidence=0.95 if run.status.value == "completed" else 0.7,
            tool_name=str((execution_summary.get("orchestrator_tool_decision", {}) or {}).get("preferred_tool") or "") or None,
            follow_up=list((execution_summary.get("repair_summary", {}) or {}).get("follow_up", [])) if isinstance(execution_summary, dict) and isinstance(execution_summary.get("repair_summary", {}), dict) else [],
            status_detail=str(execution_summary.get("branch_note") or execution_summary.get("status") or run.status.value),
            remediation=str(execution_summary.get("next_action") or execution_summary.get("reason") or "continue execution"),
        ),
        "metrics": metrics,
        "layout": {
            "framework": "React",
            "ui_kit": "mantine",
            "primary": "overview",
            "secondary": ["timeline", "nodes"],
            "tertiary": ["failures", "compensations", "traces"],
        },
        "slots": {
            "topbar": {"component": "Group", "props": ["children", "position", "spacing"], "ui_kit": "mantine"},
            "content": {"component": "SimpleGrid", "props": ["cols", "spacing", "children"], "ui_kit": "mantine"},
            "inspector": {"component": "Drawer", "props": ["opened", "title", "children"], "ui_kit": "mantine"},
        },
        "panels": build_workflow_panels(run, timeline, node_results, failure_chain, compensation_chain, trace_ids),
        "components": build_workflow_components(),
    }


def _build_workflow_metrics(run: WorkflowRunRecord, timeline: list[dict[str, object]], node_results: list[dict[str, object]], failure_chain: list[dict[str, object]], compensation_chain: list[dict[str, object]]) -> dict[str, object]:
    completed_nodes = sum(1 for item in node_results if str(item.get("status")) == "completed")
    duration_seconds = None
    started_at = getattr(run, "started_at", None)
    completed_at = getattr(run, "completed_at", None)
    if started_at and completed_at:
        duration_seconds = max((completed_at - started_at).total_seconds(), 0)
    total_attempts = sum(int(item.get("attempts") or 0) for item in node_results)
    average_attempts = round(total_attempts / len(node_results), 3) if node_results else 0.0
    success_rate = round(completed_nodes / len(node_results), 3) if node_results else 0.0
    return {
        "event_count": len(timeline),
        "node_count": len(node_results),
        "failure_count": len(failure_chain),
        "compensation_count": len(compensation_chain),
        "duration_seconds": duration_seconds,
        "node_success_rate": success_rate,
        "average_attempts": average_attempts,
    }
