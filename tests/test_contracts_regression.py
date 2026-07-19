from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.core.open_source_api import (
    OpenSourceCandidateRecord,
    OpenSourceDiscoveryStore,
    OpenSourceStatus,
)
from backend.app.main import app, require_api_key_header
from backend.app.services.desktop.ui_tars_client import UiTarsDesktopClient


def test_api_key_guard_blocks_protected_routes_when_enabled(monkeypatch) -> None:
    # Do NOT send x-api-key header — the guard checks for its presence.
    client = TestClient(app)
    monkeypatch.setattr("backend.app.main.settings.require_api_key", True)

    response = client.get("/api/v1/overview")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing API key"


def test_api_key_guard_allows_health_and_ready(monkeypatch) -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    monkeypatch.setattr("backend.app.main.settings.require_api_key", True)

    health = client.get("/health")
    ready = client.get("/ready")

    assert health.status_code == 200
    assert ready.status_code in {200, 503}


def test_api_key_status_endpoint_reports_state(monkeypatch) -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    monkeypatch.setattr("backend.app.main.settings.require_api_key", False)

    response = client.get("/api-key/status")

    assert response.status_code == 200
    assert response.json()["require_api_key"] is False


def test_workflow_view_model_has_mantine_shapes() -> None:
    response = TestClient(app).get("/api/v1/workflows/runs?limit=1")

    assert response.status_code in {200, 401}
    if response.status_code == 200:
        payload = response.json()
        assert "layout" in payload
        assert payload["layout"]["ui_kit"] == "mantine"
        assert "components" in payload
        assert "workflow_shell" in payload["components"]
        assert "timeline_panel" in payload["components"]
        assert "node_list" in payload["components"]


def test_desktop_sequence_actions_are_supported() -> None:
    client = UiTarsDesktopClient()
    session = client.create_session()

    result = client.send_action(session.session_id, "shortcut_sequence", value="ControlOrMeta+a;ControlOrMeta+c")

    assert result.ok is True
    assert client.get_session(session.session_id) is not None


def test_desktop_ime_and_clipboard_sequences_record_actions() -> None:
    client = UiTarsDesktopClient()
    session = client.create_session()

    clipboard_result = client.send_action(session.session_id, "clipboard_sequence", value="clipboard_write;clipboard_clear")
    ime_result = client.send_action(session.session_id, "ime_candidate_sequence", value="ime_next_candidate;ime_confirm_candidate")

    assert clipboard_result.ok is True
    assert ime_result.ok is True
    assert any(item.action == "clipboard_sequence" for item in session.actions)
    assert any(item.action == "ime_candidate_sequence" for item in session.actions)


def test_open_source_discovery_dedupes_and_sorts() -> None:
    class StubProvider:
        def __init__(self, name: str, items: list[OpenSourceCandidateRecord]) -> None:
            self.name = name
            self._items = items

        def search(self, query: str, limit: int = 10):
            return self._items[:limit]

    low = OpenSourceCandidateRecord(name="low", source="stub", url="https://example.com/low", score=0.2, status=OpenSourceStatus.CANDIDATE)
    high = OpenSourceCandidateRecord(name="high", source="stub", url="https://example.com/high", score=0.9, status=OpenSourceStatus.SHORTLISTED)
    dup = OpenSourceCandidateRecord(name="dup", source="stub", url="https://example.com/high", score=0.5, status=OpenSourceStatus.CANDIDATE)

    store = OpenSourceDiscoveryStore(providers=[StubProvider("a", [low, high]), StubProvider("b", [dup])])
    report = store.build_report("stub", limit=10)

    assert len(report.candidates) == 2
    assert report.candidates[0].name == "high"
    assert report.candidates[1].name == "low"
    assert report.snapshot["provider_count"] == 2


def test_open_source_candidate_detail_round_trip() -> None:
    store = OpenSourceDiscoveryStore(providers=[])
    candidate = OpenSourceCandidateRecord(name="tool", source="custom", url="https://example.com/tool", summary="demo", score=0.7)
    stored = store.add_candidate(candidate)

    details = store.build_candidate_details(stored.candidate_id)

    assert details is not None
    assert details["candidate_id"] == stored.candidate_id
    assert details["name"] == "tool"
    assert details["summary"] == "demo"
