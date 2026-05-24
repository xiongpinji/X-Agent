from __future__ import annotations

from backend.app.api.recovery_helpers import build_recovery_payload
from backend.app.core.workflows import WorkflowRunRecord


def build_workflow_summary(run: WorkflowRunRecord, failure_chain: list[dict[str, object]], compensation_chain: list[dict[str, object]], trace_ids: list[str]) -> dict[str, object]:
    recovery = build_recovery_payload(
        status=run.status.value,
        resource_type="workflow_run",
        resource_id=run.run_id,
        branch=(run.snapshot.get("last_agent_recovery_branch") if isinstance(run.snapshot, dict) else None) if hasattr(run, "snapshot") else None,
        recovery_plan=(run.snapshot.get("last_agent_execution_summary", {}).get("recovery_plan", {}) if isinstance(run.snapshot, dict) else {}) if hasattr(run, "snapshot") else {},
        next_actions=(run.snapshot.get("last_agent_execution_summary", {}).get("next_actions", []) if isinstance(run.snapshot, dict) else []) if hasattr(run, "snapshot") else [],
        retryable=run.status.value != "completed",
        confidence=0.95 if run.status.value == "completed" else 0.7,
        tool_name="workflow_summary",
        follow_up=["inspect workflow panels", "review run timeline"],
        status_detail=f"workflow {run.status.value}",
        remediation="inspect workflow summary and continue according to recovery plan",
    )
    return {
        "resource_type": "workflow_run",
        "workflow_id": run.workflow_id,
        "workflow_name": run.workflow_name,
        "status": run.status.value,
        "node_count": len(run.node_results),
        "failure_count": len(failure_chain),
        "compensation_count": len(compensation_chain),
        "trace_count": len(trace_ids),
        "run_id": run.run_id,
        "latest_branch": recovery.get("branch"),
        "recovery_plan": recovery.get("plan", {}),
        "next_actions": recovery.get("next_actions", []),
    }
