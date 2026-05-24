from __future__ import annotations

from backend.app.api.workflow_view_helpers import build_timeline_sections, build_workflow_components


def test_workflow_component_map_contains_core_mantine_nodes() -> None:
    components = build_workflow_components()

    assert components["workflow_shell"]["component"] == "AppShell"
    assert components["workflow_page"]["component"] == "Container"
    assert components["timeline_panel"]["component"] == "Timeline"
    assert components["node_list"]["component"] == "List"
    assert components["trace_chips"]["component"] == "Group"


def test_timeline_sections_keep_run_bucket() -> None:
    timeline = [{"kind": "run.started"}, {"kind": "node.started", "node_id": "n1"}]
    sections = build_timeline_sections(timeline)

    assert sections[0]["title"] == "Run"
    assert sections[0]["events"] == timeline
