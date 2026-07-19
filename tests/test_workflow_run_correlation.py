from fastapi.testclient import TestClient

from backend.app.main import app


def test_workflow_run_correlation_links_run_trace_and_audit_anchors() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    workflow = client.post(
        "/api/v1/workflows",
        json={
            "name": "Correlation flow",
            "nodes": [
                {"id": "input_1", "type": "input", "config": {"key": "name"}},
                {"id": "output_1", "type": "output", "config": {"from": "input_1"}},
            ],
            "edges": [{"source": "input_1", "target": "output_1"}],
        },
    ).json()
    run = client.post(
        f"/api/v1/workflows/{workflow['id']}/run",
        json={"inputs": {"name": "correlation"}},
    ).json()

    correlation = client.get(f"/api/v1/workflows/runs/{run['run_id']}/correlation")

    assert correlation.status_code == 200
    body = correlation.json()
    assert body["run_id"] == run["run_id"]
    assert body["workflow_id"] == workflow["id"]
    assert body["trace_id"] == run["run_id"]
    assert body["trace_summary"]["trace_id"] == run["run_id"]
    assert body["trace_summary"]["snapshot"]["run_id"] == run["run_id"]
    assert "snapshot" in body
    assert body["snapshot"]["run_id"] == run["run_id"]
    assert body["audit_anchors"]
