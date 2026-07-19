from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.api.workflow_helpers import build_workflow_shell
from backend.app.core.open_source_wiring import build_default_open_source_store
from backend.app.core.open_source_api import OpenSourceCandidateRecord
from backend.app.main import app
from backend.app.services.desktop.ui_tars_client import UiTarsDesktopClient


class StubProvider:
    def __init__(self, name: str, items: list[OpenSourceCandidateRecord]) -> None:
        self.name = name
        self._items = items

    def search(self, query: str, limit: int = 10):
        return self._items[:limit]


def test_open_source_store_end_to_end_smoke() -> None:
    store = build_default_open_source_store()
    report = store.build_report("playwright", limit=5)

    assert report.query == "playwright"
    assert report.snapshot["provider_count"] >= 5


def test_workflow_helpers_end_to_end_smoke() -> None:
    class DummyRun:
        workflow_id = "wf-1"
        workflow_name = "demo"
        status = type("S", (), {"value": "completed"})()
        node_results = []

    payload = build_workflow_shell(DummyRun(), [{"node_id": "n1"}], [{"node_id": "n1"}], ["trace-1"])

    assert payload["workflow_id"] == "wf-1"
    assert payload["failure_count"] == 1


def test_desktop_complex_macro_chain_smoke() -> None:
    client = UiTarsDesktopClient()
    session = client.create_session()
    result = client.run_macro(session.session_id, "shortcut:ControlOrMeta+a;ControlOrMeta+c|clipboard:clipboard_write;clipboard_clear|ime:ime_next_candidate;ime_confirm_candidate")

    assert len(result) >= 3
    assert session.actions


def test_api_health_and_ready_end_to_end() -> None:
    client = TestClient(app)
    health = client.get("/health")
    ready = client.get("/ready")

    assert health.status_code == 200
    assert ready.status_code in {200, 503}
