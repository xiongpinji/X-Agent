from fastapi.testclient import TestClient

from backend.app.main import app


def test_trace_correlation_view() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    run = client.post(
        "/api/v1/agents/run",
        json={"task": "trace correlation test", "context": {}},
    ).json()

    correlation = client.get(f"/api/v1/traces/{run['trace_id']}/correlation")
    trace = client.get(f"/api/v1/traces/{run['trace_id']}")

    assert trace.status_code == 200
    assert correlation.status_code == 200
    assert correlation.json()["trace_id"] == run["trace_id"]
    assert correlation.json()["trace_summary"]["trace_id"] == run["trace_id"]
