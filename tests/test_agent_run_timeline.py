from fastapi.testclient import TestClient

from backend.app.main import app


def test_agent_run_timeline_and_stream_observability() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    run = client.post(
        "/api/v1/agents/run",
        json={"task": "timeline test", "context": {}},
    ).json()

    detail = client.get(f"/api/v1/agents/runs/{run['trace_id']}")
    correlation = client.get(f"/api/v1/agents/runs/{run['trace_id']}/correlation")
    timeline = client.get(f"/api/v1/agents/runs/{run['trace_id']}/timeline")

    assert detail.status_code == 200
    assert correlation.status_code == 200
    assert timeline.status_code == 200
    assert detail.json()["trace_id"] == run["trace_id"]
    assert correlation.json()["trace_id"] == run["trace_id"]
    assert correlation.json()["trace_summary"]["trace_id"] == run["trace_id"]
    assert timeline.json()["trace_id"] == run["trace_id"]
    assert timeline.json()["snapshot"]["timeline_events"] >= 1
