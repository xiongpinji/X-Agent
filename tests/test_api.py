from fastapi.testclient import TestClient

from backend.app.main import app


def _client() -> TestClient:
    return TestClient(app, headers={"x-api-key": "bootstrap"})


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_request_logging_middleware_adds_request_id_header() -> None:
    client = TestClient(app)
    response = client.get("/health", headers={"x-request-id": "request-123"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "request-123"


def test_ready_endpoint_checks_components() -> None:
    client = TestClient(app)
    response = client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    for component in ["memory", "trace", "runs", "workflows", "audit"]:
        assert body["components"][component] == "ok"


def test_run_agent() -> None:
    client = _client()
    response = client.post("/api/v1/agents/run", json={"task": "hello"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["trace_id"]


def test_trace_history_endpoint() -> None:
    client = _client()
    run = client.post("/api/v1/agents/run", json={"task": "echo: history check"}).json()

    history = client.get("/api/v1/traces?limit=5").json()
    detail = client.get(f"/api/v1/traces/{run['trace_id']}").json()

    assert any(item["trace_id"] == run["trace_id"] for item in history)
    assert len(history) <= 5
    assert detail["summary"]["trace_id"] == run["trace_id"]
    assert detail["summary"]["event_count"] == len(detail["events"])
    assert detail["summary"]["task"] == "echo: history check"
    assert len(detail["events"]) >= 1


def test_trace_detail_404() -> None:
    client = _client()
    response = client.get("/api/v1/traces/not-found")

    assert response.status_code == 404
    assert response.json()["code"] == "trace_not_found"
    assert response.json()["trace_id"] == "not-found"


def test_run_history_endpoint() -> None:
    client = _client()
    run = client.post("/api/v1/agents/run", json={"task": "echo: run history"}).json()

    history = client.get("/api/v1/runs?limit=5").json()
    detail = client.get(f"/api/v1/runs/{run['trace_id']}").json()

    assert any(item["trace_id"] == run["trace_id"] for item in history)
    assert detail["task"] == "echo: run history"
    assert detail["status"] == "completed"


def test_run_replay_endpoint() -> None:
    client = _client()
    run = client.post("/api/v1/agents/run", json={"task": "echo: replay me"}).json()

    response = client.post(f"/api/v1/runs/{run['trace_id']}/replay")

    assert response.status_code == 200
    body = response.json()
    assert body["task"] == "echo: replay me"
    assert body["trace_id"] != run["trace_id"]


def test_run_detail_404() -> None:
    client = _client()
    response = client.get("/api/v1/runs/not-found")

    assert response.status_code == 404
    assert response.json()["code"] == "run_not_found"


def test_validation_error_contract() -> None:
    client = _client()
    response = client.post("/api/v1/agents/run", json={"task": ""})

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert "errors" in response.json()["details"]


def test_tool_manifest_endpoint() -> None:
    client = _client()
    response = client.get("/api/v1/tools")

    assert response.status_code == 200
    tools = response.json()
    assert {item["name"] for item in tools} >= {"echo", "summarize_text"}
    assert all("required_scope" in item for item in tools)


def test_metrics_summary_endpoint() -> None:
    client = _client()
    client.post("/api/v1/agents/run", json={"task": "echo: metrics"})

    response = client.get("/api/v1/metrics/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["runs"] >= 1
    assert body["traces"] >= 1
    assert body["trace_events"] >= 1
    assert body["memories"] >= 1
    assert body["audit_logs"] >= 1
    assert "api_keys" in body
    assert "active_api_keys" in body
    assert "approvals" in body
    assert "pending_approvals" in body


def test_prometheus_metrics_endpoint() -> None:
    client = _client()
    response = client.get("/api/v1/metrics/prometheus")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "# TYPE xagent_runs_total gauge" in response.text
    assert "xagent_trace_events_total" in response.text
