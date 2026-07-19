from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app, headers={"x-api-key": "bootstrap"})


def test_planning_api_returns_execution_plan(tmp_path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "app.py").write_text("print('hello')", encoding="utf-8")
    (root / "test_app.py").write_text("def test_app():\n    assert True", encoding="utf-8")

    response = client.post("/api/v1/planning/draft", json={"task": "update app", "root": str(root), "limit": 20})
    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_plan"]["steps"]
    assert payload["test_mapping"]["test_files"]


def test_verification_api_returns_summary(tmp_path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "app.py").write_text("print('hello')", encoding="utf-8")
    (root / "test_app.py").write_text("def test_app():\n    assert True", encoding="utf-8")

    response = client.post("/api/v1/verification/draft", json={"task": "update app", "root": str(root), "limit": 20})
    assert response.status_code == 200
    payload = response.json()
    assert "verification" in payload
    assert "test_mapping" in payload
    assert payload["verification"]["suggested_test_commands"]
