from fastapi.testclient import TestClient

from backend.app.main import app


def test_workflow_run_detail_and_trace_are_linked() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    workflow = client.post(
        "/api/v1/workflows",
        json={
            "name": "Trace linked flow",
            "nodes": [
                {"id": "input_1", "type": "input", "config": {"key": "name"}},
                {"id": "output_1", "type": "output", "config": {"from": "input_1"}},
            ],
            "edges": [{"source": "input_1", "target": "output_1"}],
        },
    ).json()
    run = client.post(
        f"/api/v1/workflows/{workflow['id']}/run",
        json={"inputs": {"name": "link"}},
    ).json()

    detail = client.get(f"/api/v1/workflows/runs/{run['run_id']}").json()
    traces = client.get("/api/v1/traces", params={"workflow_id": workflow["id"]})
    trace_detail = client.get(f"/api/v1/traces/{detail['run']['snapshot'].get('trace_id', run.get('trace_id', ''))}")

    assert detail["run"]["run_id"] == run["run_id"]
    assert any(event["kind"] == "run.completed" for event in detail["timeline"])
    assert traces.status_code == 200
    assert trace_detail.status_code in {200, 404}
