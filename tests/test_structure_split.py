from __future__ import annotations

from backend.app.api.workflow_view_model import build_workflow_run_view_model
from backend.app.core.open_source_api import OpenSourceCandidateRecord, OpenSourceDiscoveryStore, OpenSourceStatus


class DummyRun:
    workflow_name = "demo"
    workflow_id = "wf-1"
    run_id = "run-1"
    status = type("S", (), {"value": "completed"})()
    started_at = None
    completed_at = None
    tenant_id = "default"
    user_id = "user-1"
    node_results = []


def test_workflow_view_model_builder_returns_mantine_schema() -> None:
    run = DummyRun()
    payload = build_workflow_run_view_model(run, [], [], [], [], [])

    assert payload["layout"]["ui_kit"] == "mantine"
    assert payload["components"]["workflow_shell"]["component"] == "AppShell"
    assert payload["components"]["timeline_panel"]["component"] == "Timeline"
    assert payload["panels"]["overview"]["title"] == "demo"


def test_open_source_store_discovers_sorted_and_deduped() -> None:
    class Provider:
        def __init__(self, name: str, items: list[OpenSourceCandidateRecord]) -> None:
            self.name = name
            self._items = items

        def search(self, query: str, limit: int = 10):
            q = query.lower()
            matched = [x for x in self._items if q in x.name.lower()]
            return matched[:limit]

    high = OpenSourceCandidateRecord(name="alpha", source="p1", url="https://example.com/a", score=0.9, status=OpenSourceStatus.SHORTLISTED)
    dup = OpenSourceCandidateRecord(name="alpha-dup", source="p2", url="https://example.com/a", score=0.4)
    low = OpenSourceCandidateRecord(name="beta", source="p1", url="https://example.com/b", score=0.2)

    store = OpenSourceDiscoveryStore(providers=[Provider("b", [low]), Provider("a", [high, dup])])
    report = store.build_report("alpha", limit=10)

    assert len(report.candidates) == 1
    assert report.candidates[0].url == "https://example.com/a"
    assert report.shortlist[0].status == OpenSourceStatus.SHORTLISTED
    assert report.snapshot["provider_count"] == 2
