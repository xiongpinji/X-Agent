from __future__ import annotations

from backend.app.api.workflow_view_header import build_workflow_header
from backend.app.api.workflow_view_helpers import build_timeline_sections
from backend.app.api.workflow_view_model import build_workflow_run_view_model
from backend.app.api.workflow_view_panels import build_workflow_panels
from backend.app.api.workflow_view_summary import build_workflow_summary


def test_workflow_compose_only_uses_top_level_builders() -> None:
    class DummyRun:
        workflow_id = "wf-1"
        workflow_name = "demo"
        status = type("S", (), {"value": "completed"})()
        run_id = "run-1"
        node_results = []

    run = DummyRun()
    header = build_workflow_header(run, 0, 0)
    summary = build_workflow_summary(run, [], [], [])
    panels = build_workflow_panels(run, [], [], [], [], [])
    sections = build_timeline_sections(run, [], [], [])
    view = build_workflow_run_view_model(run, [], [], [], [], [])

    assert header["title"] == "demo"
    assert summary["workflow_id"] == "wf-1"
    assert "overview" in panels
    assert sections
    assert view["header"]["title"] == "demo"
