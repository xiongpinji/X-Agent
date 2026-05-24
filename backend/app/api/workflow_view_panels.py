from __future__ import annotations

from backend.app.api.recovery_helpers import build_recovery_payload
from backend.app.api.workflow_compensation_helpers import build_compensation_bucket
from backend.app.api.workflow_failure_helpers import build_failure_bucket
from backend.app.api.workflow_node_helpers import build_node_bucket
from backend.app.api.workflow_timeline_helpers import build_timeline_bucket
from backend.app.core.workflows import WorkflowRunRecord


def build_workflow_panels(run: WorkflowRunRecord, timeline: list[dict[str, object]], node_results: list[dict[str, object]], failure_chain: list[dict[str, object]], compensation_chain: list[dict[str, object]], trace_ids: list[str]) -> dict[str, object]:
    failure_count = len(failure_chain)
    compensation_count = len(compensation_chain)
    recovery_context = build_recovery_payload(
        status=run.status.value,
        resource_type="workflow_run",
        resource_id=run.run_id,
        next_actions=((run.snapshot.get("last_agent_execution_summary", {}).get("recovery_plan", {}).get("next_actions", []) if isinstance(run.snapshot, dict) else []) if hasattr(run, "snapshot") else []),
        recovery_plan=((run.snapshot.get("last_agent_execution_summary", {}).get("recovery_plan", {}) if isinstance(run.snapshot, dict) else {}) if hasattr(run, "snapshot") else {}),
        branch=((run.snapshot.get("last_agent_recovery_branch") if isinstance(run.snapshot, dict) else None) if hasattr(run, "snapshot") else None),
        retryable=run.status.value != "completed",
        confidence=0.95 if run.status.value == "completed" else 0.7,
        tool_name="workflow_panels",
        follow_up=["inspect timeline", "review failures", "inspect compensations"],
        status_detail=f"workflow panels {run.status.value}",
        remediation="inspect panels and continue workflow recovery",
    )
    return {"resource_type": "workflow_run", "overview": {"title": run.workflow_name, "status": run.status.value, "subtitle": f"{failure_count} failures / {compensation_count} compensations", "trace_count": len(trace_ids), "node_count": len(run.node_results), "badges": [run.status.value, f"nodes:{len(run.node_results)}", f"traces:{len(trace_ids)}"], "run_id": run.run_id, "workflow_id": run.workflow_id, "recovery_branch": recovery_context.get("branch")}, "recovery": recovery_context, "timeline": build_timeline_bucket(timeline), "nodes": build_node_bucket(node_results), "failures": build_failure_bucket(failure_chain), "compensations": build_compensation_bucket(compensation_chain), "traces": {"items": trace_ids, "count": len(trace_ids), "ui": {"title": "Traces", "component": "Group"}}}
