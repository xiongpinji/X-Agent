from fastapi.testclient import TestClient

from backend.app.main import app


def test_workflow_schedule_detail_and_correlation_views() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    workflow = client.post(
        "/api/v1/workflows",
        json={
            "name": "Schedule detail flow",
            "nodes": [
                {"id": "input_1", "type": "input", "config": {"key": "name"}},
                {"id": "output_1", "type": "output", "config": {"from": "input_1"}},
            ],
            "edges": [{"source": "input_1", "target": "output_1"}],
        },
    ).json()
    schedule = client.post(
        f"/api/v1/workflows/{workflow['id']}/schedule",
        json={"inputs": {"name": "schedule"}, "delay_seconds": 0},
    ).json()

    detail = client.get(f"/api/v1/workflows/schedules/{schedule['schedule_id']}")
    correlation = client.get(f"/api/v1/workflows/schedules/{schedule['schedule_id']}/correlation")

    assert detail.status_code == 200
    assert correlation.status_code == 200
    assert detail.json()["schedule_id"] == schedule["schedule_id"]
    assert correlation.json()["schedule_id"] == schedule["schedule_id"]
    assert correlation.json()["workflow_id"] == workflow["id"]
    assert correlation.json()["trace_summary"]["trace_id"] == correlation.json()["trace_id"]
    assert correlation.json()["snapshot"]["schedule_id"] == schedule["schedule_id"]
