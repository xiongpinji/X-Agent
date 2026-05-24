from fastapi.testclient import TestClient

from backend.app.main import app


def test_ops_summary_reports_health_and_backlog() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    response = client.get("/api/v1/ops/summary")

    assert response.status_code == 200
    payload = response.json()

    assert "healthy" in payload
    assert "failure_traces" in payload
    assert "approval_backlog" in payload
    assert "tool_failures" in payload
    assert "overview" in payload
    assert isinstance(payload["failure_traces"], list)
    assert payload["approval_backlog"] >= 0
    assert payload["tool_failures"] >= 0
