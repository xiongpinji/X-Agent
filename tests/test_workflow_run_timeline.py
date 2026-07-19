from fastapi.testclient import TestClient

from backend.app.main import app


def test_workflow_run_timeline_includes_node_compensation_and_types() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    workflow = client.post(
        "/api/v1/workflows",
        json={
            "name": "Timeline flow",
            "nodes": [
                {"id": "input_1", "type": "input", "config": {"key": "name"}},
                {
                    "id": "wait_1",
                    "type": "wait",
                    "config": {"delay_ms": 0, "on_failure": {"type": "transform", "template": "rollback {input_name}"}},
                },
            ],
            "edges": [{"source": "input_1", "target": "wait_1"}],
        },
    ).json()

    run = client.post(
        f"/api/v1/workflows/{workflow['id']}/run",
        json={"inputs": {"name": "timeline"}},
    ).json()
    detail = client.get(f"/api/v1/workflows/runs/{run['run_id']}")

    assert detail.status_code == 200
    timeline = detail.json()["timeline"]
    assert any(event["kind"] == "run.started" for event in timeline)
    assert any(event["kind"] == "node.started" for event in timeline)
    assert any(event["kind"] == "node.completed" for event in timeline)
    assert any(event["kind"] == "run.completed" for event in timeline)
    assert all("node_type" in event or event["kind"].startswith("run.") for event in timeline)
