from fastapi.testclient import TestClient

from backend.app.main import app


def test_overview_includes_recent_activity_and_summary_metrics() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    response = client.get("/api/v1/overview")

    assert response.status_code == 200
    payload = response.json()

    assert payload["traces"]["count"] >= 0
    assert payload["traces"]["latest_count"] <= 10
    assert "last_event" in payload["traces"]
    assert payload["runs"]["count"] >= 0
    assert payload["runs"]["recent_count"] <= 10
    assert payload["approvals"]["count"] >= 0
    assert payload["approvals"]["pending"] >= 0
    assert payload["approvals"]["recent_count"] <= 10
    assert payload["workflows"]["count"] >= 0
    assert payload["workflows"]["runs"] >= 0
    assert payload["memory"]["count"] >= 0
    assert payload["tools"]["count"] >= 0
