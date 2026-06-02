from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app, headers={"x-api-key": "bootstrap"})


def test_replay_api_returns_payload(tmp_path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "app.py").write_text("print('hello')", encoding="utf-8")

    response = client.post("/api/v1/replay/draft", json={"task": "inspect app", "root": str(root), "limit": 10})
    assert response.status_code == 200
    payload = response.json()
    # draft_replay returns a build_linked_summary envelope; the primary draft
    # payload lives under linked_summaries.primary.data (not at the top level).
    data = payload["linked_summaries"]["primary"]["data"]
    assert data["task"] == "inspect app"
    assert "code_index" in data
    assert "execution_plan" in data
    assert "verification" in data
