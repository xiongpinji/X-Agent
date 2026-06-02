from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app, headers={"x-api-key": "bootstrap"})


def test_overview_api_returns_full_payload(tmp_path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "app.py").write_text("print('hello')", encoding="utf-8")
    (root / "test_app.py").write_text("def test_app():\n    assert True", encoding="utf-8")

    response = client.post("/api/v1/overview/draft", json={"task": "update app", "root": str(root), "limit": 10})
    assert response.status_code == 200
    payload = response.json()
    # draft_overview returns a build_linked_summary envelope; the primary draft
    # payload lives under linked_summaries.primary.data (not at the top level).
    data = payload["linked_summaries"]["primary"]["data"]
    assert data["code_index"]
    assert data["test_mapping"]
    assert data["execution_plan"]
    assert data["verification"]
    assert data["summary"]
