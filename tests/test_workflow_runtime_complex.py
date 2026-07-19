from __future__ import annotations

from backend.app.api.workflow_compensation_helpers import build_compensation_bucket
from backend.app.api.workflow_failure_helpers import build_failure_bucket
from backend.app.api.workflow_node_helpers import build_node_bucket
from backend.app.api.workflow_timeline_helpers import build_timeline_bucket


def test_workflow_helper_buckets_support_runtime_shapes() -> None:
    timeline = build_timeline_bucket([{"kind": "run.started"}, {"kind": "node.started", "node_id": "n1"}, {"kind": "node.completed", "node_id": "n1"}])
    nodes = build_node_bucket([{"node_id": "n1", "status": "completed", "node_type": "transform"}, {"node_id": "n2", "status": "failed", "node_type": "wait", "error": "boom"}])
    failures = build_failure_bucket([{"node_id": "n2", "error": "boom"}])
    compensations = build_compensation_bucket([{"node_id": "n2", "compensation_output": "rollback"}])

    assert timeline["count"] == 3
    assert nodes["summary"]["total"] == 2
    assert nodes["summary"]["failure_nodes"] == ["n2"]
    assert failures["items"][0]["error"] == "boom"
    assert compensations["items"][0]["compensation_output"] == "rollback"
