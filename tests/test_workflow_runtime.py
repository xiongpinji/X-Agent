from __future__ import annotations

from backend.app.api.workflow_compensation_helpers import build_compensation_bucket
from backend.app.api.workflow_failure_helpers import build_failure_bucket
from backend.app.api.workflow_node_helpers import build_node_bucket
from backend.app.api.workflow_timeline_helpers import build_timeline_bucket


def test_workflow_runtime_buckets_shape() -> None:
    timeline = build_timeline_bucket([{"kind": "run.started"}, {"kind": "node.started", "node_id": "n1"}])
    nodes = build_node_bucket([{"node_id": "n1", "status": "completed"}])
    failures = build_failure_bucket([])
    compensations = build_compensation_bucket([])

    assert timeline["count"] == 2
    assert nodes["summary"]["total"] == 1
    assert failures["count"] == 0
    assert compensations["count"] == 0
