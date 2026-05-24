from __future__ import annotations

from backend.app.api.workflow_compensation_helpers import build_compensation_bucket
from backend.app.api.workflow_failure_helpers import build_failure_bucket
from backend.app.api.workflow_helpers import build_workflow_shell
from backend.app.api.workflow_node_helpers import build_node_bucket
from backend.app.api.workflow_timeline_helpers import build_timeline_bucket


class DummyRun:
    workflow_id = "wf-1"
    workflow_name = "demo"
    status = type("S", (), {"value": "completed"})()
    node_results = []


def test_workflow_shell_summary_shape() -> None:
    payload = build_workflow_shell(DummyRun(), [{"x": 1}], [{"y": 2}], ["trace-1"])

    assert payload["workflow_id"] == "wf-1"
    assert payload["failure_count"] == 1
    assert payload["compensation_count"] == 1
    assert payload["trace_count"] == 1


def test_timeline_bucket_shape() -> None:
    bucket = build_timeline_bucket([{"kind": "run.started"}])

    assert bucket["title"] == "Timeline"
    assert bucket["count"] == 1


def test_node_bucket_shape() -> None:
    bucket = build_node_bucket([{"node_id": "n1", "status": "ok"}])

    assert bucket["title"] == "Nodes"
    assert bucket["count"] == 1


def test_failure_and_compensation_buckets_shape() -> None:
    failure = build_failure_bucket([{"node_id": "n1"}])
    compensation = build_compensation_bucket([{"node_id": "n1"}])

    assert failure["count"] == 1
    assert compensation["count"] == 1
