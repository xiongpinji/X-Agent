from fastapi.testclient import TestClient

from backend.app.main import app


def test_workflow_run_observability_cross_links_detail_trace_and_audit() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    workflow = client.post(
        "/api/v1/workflows",
        json={
            "name": "Observability flow",
            "nodes": [
                {"id": "input_1", "type": "input", "config": {"key": "name"}},
                {"id": "output_1", "type": "output", "config": {"from": "input_1"}},
            ],
            "edges": [{"source": "input_1", "target": "output_1"}],
        },
    ).json()
    run = client.post(
        f"/api/v1/workflows/{workflow['id']}/run",
        json={"inputs": {"name": "observe"}},
    ).json()

    detail = client.get(f"/api/v1/workflows/runs/{run['run_id']}")
    trace_detail = client.get(f"/api/v1/traces/{run['run_id']}")
    audit_logs = client.get(
        "/api/v1/audit-logs",
        params={"workflow_id": workflow["id"], "run_id": run["run_id"]},
    )

    assert detail.status_code == 200
    assert trace_detail.status_code in {200, 404}
    assert audit_logs.status_code == 200
    assert any(item["run_id"] == run["run_id"] for item in audit_logs.json())
    assert detail.json()["run"]["run_id"] == run["run_id"]
