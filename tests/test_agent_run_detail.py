from fastapi.testclient import TestClient

from backend.app.main import app


def test_agent_run_detail_and_correlation_views() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    run = client.post(
        "/api/v1/agents/run",
        json={"task": "detail test", "context": {}},
    ).json()

    detail = client.get(f"/api/v1/agents/runs/{run['trace_id']}")
    correlation = client.get(f"/api/v1/agents/runs/{run['trace_id']}/correlation")

    assert detail.status_code == 200
    assert correlation.status_code == 200
    assert detail.json()["trace_id"] == run["trace_id"]
    assert correlation.json()["trace_id"] == run["trace_id"]
    assert correlation.json()["trace_summary"]["trace_id"] == run["trace_id"]
