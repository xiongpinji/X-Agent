from __future__ import annotations

from backend.app.api.workflow_view_components import build_workflow_components
from backend.app.api.workflow_view_header import build_workflow_header
from backend.app.api.workflow_view_panels import build_workflow_panels
from backend.app.api.workflow_view_summary import build_workflow_summary
from backend.app.api.workflow_view_model import build_workflow_run_view_model


class DummyRun:
    workflow_id = "wf-1"
    workflow_name = "demo"
    status = type("S", (), {"value": "completed"})()
    run_id = "run-1"
    node_results = []


def test_workflow_end_to_end_compose_contract() -> None:
    run = DummyRun()
    header = build_workflow_header(run, 0, 0)
    summary = build_workflow_summary(run, [], [], [])
    panels = build_workflow_panels(run, [], [], [], [], [])
    components = build_workflow_components()
    view = build_workflow_run_view_model(run, [], [], [], [], [])

    assert header["title"] == "demo"
    assert summary["workflow_id"] == "wf-1"
    assert "overview" in panels
    assert "workflow_shell" in components
    assert view["panels"]["overview"]["title"] == "demo"
