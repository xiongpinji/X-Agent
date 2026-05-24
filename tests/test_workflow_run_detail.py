from fastapi.testclient import TestClient

from backend.app.main import app


def test_workflow_run_detail_returns_timeline() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    workflow = client.post(
        "/api/v1/workflows",
        json={
            "name": "Detail flow",
            "nodes": [
                {"id": "input_1", "type": "input", "config": {"key": "name"}},
                {"id": "output_1", "type": "output", "config": {"from": "input_1"}},
            ],
            "edges": [{"source": "input_1", "target": "output_1"}],
        },
    ).json()
    run = client.post(
        f"/api/v1/workflows/{workflow['id']}/run",
        json={"inputs": {"name": "timeline"}},
    ).json()

    detail = client.get(f"/api/v1/workflows/runs/{run['run_id']}")

    assert detail.status_code == 200
    body = detail.json()
    assert body["run"]["run_id"] == run["run_id"]
    assert body["snapshot"]["run_id"] == run["run_id"]
    assert len(body["timeline"]) >= 3
    assert any(event["kind"] == "run.started" for event in body["timeline"])
    assert any(event["kind"] == "run.completed" for event in body["timeline"])
