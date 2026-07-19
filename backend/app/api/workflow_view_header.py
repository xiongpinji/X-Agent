from __future__ import annotations

from backend.app.api.recovery_helpers import build_recovery_payload
from backend.app.core.workflows import WorkflowRunRecord


def build_workflow_header(run: WorkflowRunRecord, failure_count: int, compensation_count: int) -> dict[str, object]:
    recovery = build_recovery_payload(
        status=run.status.value,
        resource_type="workflow_run",
        resource_id=run.run_id,
        branch=(run.snapshot.get("last_agent_recovery_branch") if isinstance(run.snapshot, dict) else None) if hasattr(run, "snapshot") else None,
        recovery_plan=(run.snapshot.get("last_agent_execution_summary", {}).get("recovery_plan", {}) if isinstance(run.snapshot, dict) else {}) if hasattr(run, "snapshot") else {},
        next_actions=(run.snapshot.get("last_agent_execution_summary", {}).get("next_actions", []) if isinstance(run.snapshot, dict) else []) if hasattr(run, "snapshot") else [],
        retryable=run.status.value != "completed",
        confidence=0.95 if run.status.value == "completed" else 0.7,
        tool_name="workflow_header",
        follow_up=["inspect workflow summary", "open workflow panels"],
        status_detail=f"workflow header {run.status.value}",
        remediation="inspect workflow header and follow the recovery plan",
    )
    return {
        "resource_type": "workflow_run",
        "title": run.workflow_name,
        "status": run.status.value,
        "subtitle": f"{failure_count} failures / {compensation_count} compensations",
        "badges": [run.status.value, f"nodes:{len(run.node_results)}", f"trace:{run.run_id[:8]}", *( [f"branch:{recovery.get('branch')}"] if recovery.get("branch") else [] )],
        "run_id": run.run_id,
        "workflow_id": run.workflow_id,
        "recovery_branch": recovery.get("branch"),
        "recovery": recovery,
    }
