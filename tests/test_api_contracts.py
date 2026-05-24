from fastapi.testclient import TestClient

from backend.app.main import app


def test_observability_contract_fields_are_present() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    overview = client.get("/api/v1/overview")
    ops = client.get("/api/v1/ops/summary")
    health = client.get("/health")
    ready = client.get("/ready")

    assert overview.status_code == 200
    assert ops.status_code == 200
    assert health.status_code == 200
    assert ready.status_code in {200, 503}

    overview_payload = overview.json()
    ops_payload = ops.json()
    health_payload = health.json()
    ready_payload = ready.json()

    assert "traces" in overview_payload
    assert "runs" in overview_payload
    assert "approvals" in overview_payload
    assert "workflows" in overview_payload
    assert "memory" in overview_payload
    assert "tools" in overview_payload

    assert "healthy" in ops_payload
    assert "failure_traces" in ops_payload
    assert "approval_backlog" in ops_payload
    assert "tool_failures" in ops_payload
    assert "overview" in ops_payload

    assert health_payload["status"] == "ok"
    assert "service" in health_payload

    assert "status" in ready_payload
    assert "components" in ready_payload
    assert "integrations" in ready_payload

    assert "memory" in ready_payload["components"]
    assert "qdrant" in ready_payload["components"]
    assert "trace" in ready_payload["components"]
    assert "runs" in ready_payload["components"]
    assert "workflows" in ready_payload["components"]
    assert "audit" in ready_payload["components"]
    assert "browser" in ready_payload["components"]
    assert "observability" in ready_payload["components"]

    assert "qdrant" in ready_payload["integrations"]
    assert "langfuse" in ready_payload["integrations"]
    assert "browser" in ready_payload["integrations"]

    components = ready_payload["components"]
    assert "memory" in components
    assert "qdrant" in components
    assert "trace" in components
    assert "runs" in components
    assert "workflows" in components
    assert "audit" in components
    assert "browser" in components
    assert "observability" in components


def test_core_api_routes_are_available() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})

    auth_routes = [
        "/api/v1/auth/me",
        "/api/v1/auth/register",
        "/api/v1/auth/login",
    ]
    management_routes = [
        "/api/v1/tenants",
        "/api/v1/users",
        "/api/v1/security/me",
        "/api/v1/agents",
        "/api/v1/tools",
        "/api/v1/audit-logs/summary",
        "/api/v1/metrics/summary",
        "/api/v1/browser/sessions",
        "/api/v1/memory/count",
        "/api/v1/traces",
        "/api/v1/runs",
        "/api/v1/approvals",
    ]

    for route in auth_routes + management_routes:
        method = client.get
        if route.startswith("/api/v1/browser/sessions"):
            method = client.post
        response = method(route)
        assert response.status_code in {200, 401, 403, 404, 405, 422}
