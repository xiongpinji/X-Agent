from __future__ import annotations

from typing import Any


def build_workflow_shell(
    run: Any,
    failure_chain: list[dict[str, object]],
    compensation_chain: list[dict[str, object]],
    trace_ids: list[str],
) -> dict[str, object]:
    """Build a lightweight workflow shell for overview/draft use."""
    snapshot = getattr(run, "snapshot", {}) or {}
    if not isinstance(snapshot, dict):
        snapshot = {}
    return {
        "workflow_id": getattr(run, "workflow_id", None),
        "workflow_name": getattr(run, "workflow_name", None),
        "status": getattr(getattr(run, "status", None), "value", None),
        "recovery_branch": snapshot.get("last_agent_recovery_branch"),
        "trace_ids": trace_ids,
        "trace_count": len(trace_ids),
        "failure_count": len(failure_chain),
        "compensation_count": len(compensation_chain),
    }
