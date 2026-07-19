from fastapi.testclient import TestClient

from backend.app.main import app


def test_trace_correlation_view() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    run_response = client.post(
        "/api/v1/agents/run",
        json={"task": "trace correlation test", "context": {}},
    )
    assert run_response.status_code == 200, f"Agent run failed: {run_response.text}"
    run = run_response.json()
    assert "trace_id" in run, f"No trace_id in response: {run}"

    correlation = client.get(f"/api/v1/traces/{run['trace_id']}/correlation")
    trace = client.get(f"/api/v1/traces/{run['trace_id']}")

    assert trace.status_code == 200
    assert correlation.status_code == 200
    correlation_data = correlation.json()
    # Correlation endpoint should include trace_id at top level
    assert correlation_data.get("trace_id") == run["trace_id"]
    # trace_summary should also contain the trace_id
    if "trace_summary" in correlation_data:
        assert correlation_data["trace_summary"].get("trace_id") == run["trace_id"]
