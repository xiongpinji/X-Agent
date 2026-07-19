from __future__ import annotations

from backend.app.api.workflow_compensation_helpers import build_compensation_bucket
from backend.app.api.workflow_failure_helpers import build_failure_bucket
from backend.app.api.workflow_node_helpers import build_node_bucket
from backend.app.api.workflow_timeline_helpers import build_timeline_bucket
from backend.app.core.workflows import WorkflowRunRecord


def build_workflow_panels(run: WorkflowRunRecord, timeline: list[dict[str, object]], node_results: list[dict[str, object]], failure_chain: list[dict[str, object]], compensation_chain: list[dict[str, object]], trace_ids: list[str]) -> dict[str, object]:
    failure_count = len(failure_chain)
    compensation_count = len(compensation_chain)
    return {"overview": {"title": run.workflow_name, "status": run.status.value, "subtitle": f"{failure_count} failures / {compensation_count} compensations", "trace_count": len(trace_ids), "node_count": len(run.node_results), "badges": [run.status.value, f"nodes:{len(run.node_results)}", f"traces:{len(trace_ids)}"]}, "timeline": build_timeline_bucket(timeline), "nodes": build_node_bucket(node_results), "failures": build_failure_bucket(failure_chain), "compensations": build_compensation_bucket(compensation_chain), "traces": {"items": trace_ids, "count": len(trace_ids), "ui": {"title": "Traces", "component": "Group"}}}
