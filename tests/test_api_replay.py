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
    assert payload["task"] == "inspect app"
    assert "code_index" in payload
    assert "execution_plan" in payload
    assert "verification" in payload
