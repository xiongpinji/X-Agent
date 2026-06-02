from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.core.security import Principal, ROLE_SCOPES
from backend.app.dependencies import get_current_principal
from backend.app.main import app


def _admin_principal() -> Principal:
    return Principal(
        tenant_id="default",
        user_id="test-admin",
        agent_id="test-agent",
        request_id="test-request",
        trace_id="test-trace",
        permission_scope=list(ROLE_SCOPES["admin"]),
        role="admin",
        scopes=list(ROLE_SCOPES["admin"]),
        authenticated=True,
    )


@pytest.fixture
def _admin_client():
    app.dependency_overrides[get_current_principal] = _admin_principal
    yield TestClient(app, headers={"x-api-key": "bootstrap"})
    app.dependency_overrides.pop(get_current_principal, None)


def test_browser_api_session_lifecycle(_admin_client: TestClient) -> None:
    client = _admin_client
    created = client.post("/api/v1/browser/sessions", json={"trace_id": "trace-1", "run_id": "run-1"})
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    fetched = client.get(f"/api/v1/browser/sessions/{session_id}")
    assert fetched.status_code == 200
    assert fetched.json()["session_id"] == session_id

    correlation = client.get(f"/api/v1/browser/sessions/{session_id}/correlation")
    assert correlation.status_code == 200
    assert correlation.json()["resource_id"] == session_id


def test_desktop_api_session_lifecycle(_admin_client: TestClient) -> None:
    client = _admin_client
    created = client.post("/api/v1/desktop/sessions", json={"trace_id": "trace-2", "run_id": "run-2"})
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    fetched = client.get(f"/api/v1/desktop/sessions/{session_id}")
    assert fetched.status_code == 200
    assert fetched.json()["session_id"] == session_id

    correlation = client.get(f"/api/v1/desktop/sessions/{session_id}")
    assert correlation.status_code == 200
    assert fetched.json()["session_id"] == session_id


def test_memory_api_store_search_and_count(_admin_client: TestClient) -> None:
    client = _admin_client
    stored = client.post("/api/v1/memory", json={"content": "hello unified memory", "layer": 3, "importance": 0.8, "tags": ["test"]})
    assert stored.status_code == 200
    memory_id = stored.json()["id"]

    count = client.get("/api/v1/memory/count")
    assert count.status_code == 200
    assert count.json()["count"] >= 1

    search = client.post("/api/v1/memory/search", json={"query": "unified memory", "top_k": 5, "include_scores": True})
    assert search.status_code == 200
    body = search.json()
    assert any(item["id"] == memory_id for item in body["items"])

    correlation = client.get(f"/api/v1/memory/{memory_id}/correlation")
    assert correlation.status_code == 200
    assert correlation.json()["memory_id"] == memory_id
