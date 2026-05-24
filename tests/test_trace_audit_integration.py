from fastapi.testclient import TestClient

from backend.app.main import app


def test_trace_and_audit_cross_reference_for_agent_run() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    run = client.post("/api/v1/agents/run", json={"task": "cross reference"}).json()

    traces = client.get("/api/v1/traces", params={"trace_id": run["trace_id"]})
    trace_detail = client.get(f"/api/v1/traces/{run['trace_id']}")
    audit_logs = client.get("/api/v1/audit-logs", params={"trace_id": run["trace_id"]})

    assert traces.status_code == 200
    assert any(item["trace_id"] == run["trace_id"] for item in traces.json())
    assert trace_detail.status_code == 200
    assert trace_detail.json()["summary"]["trace_id"] == run["trace_id"]
    assert audit_logs.status_code == 200
    assert any(item["trace_id"] == run["trace_id"] for item in audit_logs.json())


def test_trace_and_audit_cross_reference_for_workflow_run() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    workflow = client.post(
        "/api/v1/workflows",
        json={
            "name": "Trace audit workflow",
            "nodes": [
                {"id": "input_1", "type": "input", "config": {"key": "name"}},
                {"id": "output_1", "type": "output", "config": {"from": "input_1"}},
            ],
            "edges": [{"source": "input_1", "target": "output_1"}],
        },
    ).json()
    run = client.post(
        f"/api/v1/workflows/{workflow['id']}/run",
        json={"inputs": {"name": "trace"}},
    ).json()

    traces = client.get("/api/v1/traces", params={"workflow_id": workflow["id"]})
    audit_logs = client.get("/api/v1/audit-logs", params={"workflow_id": workflow["id"]})

    assert run["status"] == "completed"
    assert traces.status_code == 200
    assert audit_logs.status_code == 200
    assert any(item["workflow_id"] == workflow["id"] for item in audit_logs.json())
