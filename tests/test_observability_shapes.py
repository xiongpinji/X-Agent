from fastapi.testclient import TestClient

from backend.app.main import app


def test_observability_shapes_across_core_domains() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})

    run = client.post("/api/v1/agents/run", json={"task": "shape test", "context": {}}).json()
    trace_id = run["trace_id"]

    run_detail = client.get(f"/api/v1/agents/runs/{trace_id}")
    run_correlation = client.get(f"/api/v1/agents/runs/{trace_id}/correlation")
    trace_correlation = client.get(f"/api/v1/traces/{trace_id}/correlation")
    overview = client.get("/api/v1/overview")

    assert run_detail.status_code == 200
    assert run_correlation.status_code == 200
    assert trace_correlation.status_code == 200
    assert overview.status_code == 200

    run_corr_json = run_correlation.json()
    trace_corr_json = trace_correlation.json()
    overview_json = overview.json()

    assert run_corr_json["trace_id"] == trace_id
    assert run_corr_json["resource_type"] == "agent_run"
    assert run_corr_json["resource_id"] == trace_id
    assert run_corr_json["trace_summary"]["trace_id"] == trace_id
    assert run_corr_json["trace_summary"]["snapshot"]["resource_type"] == "agent_run"

    assert trace_corr_json["trace_id"] == trace_id
    assert trace_corr_json["resource_type"] == "trace"
    assert trace_corr_json["resource_id"] == trace_id
    assert trace_corr_json["trace_summary"]["trace_id"] == trace_id
    assert trace_corr_json["snapshot"]["resource_type"] == "trace"

    assert "traces" in overview_json
    assert "runs" in overview_json
    assert "approvals" in overview_json
    assert "workflows" in overview_json
    assert "memory" in overview_json
    assert "tools" in overview_json
