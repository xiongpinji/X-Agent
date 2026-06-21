from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler
from backend.app.api.rag_governance import router
from backend.app.core.audit import AuditStore
from backend.app.core.security import Principal, ROLE_SCOPES
from backend.app.dependencies import get_audit_store, get_current_principal


def _principal(role: str = "developer", scopes: list[str] | None = None, tenant_id: str = "tenant-1") -> Principal:
    return Principal(
        tenant_id=tenant_id,
        user_id="user-1",
        role=role,
        authenticated=True,
        api_key_id="test-key",
        permission_scope=scopes or list(ROLE_SCOPES[role]),
        scopes=scopes or list(ROLE_SCOPES[role]),
    )


def _app(principal: Principal | None, *, audit_store: AuditStore | None = None) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
    app.include_router(router)
    if principal is not None:
        app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_audit_store] = lambda: audit_store or AuditStore()
    return app


def test_rag_providers_requires_memory_read_scope() -> None:
    client = TestClient(_app(_principal(role="user", scopes=["agent:run"])))

    response = client.get("/api/v1/rag/providers")

    assert response.status_code == 403
    assert "memory:read" in response.text


def test_rag_providers_report_api_only_surface() -> None:
    client = TestClient(_app(_principal()))

    response = client.get("/api/v1/rag/providers")

    assert response.status_code == 200
    data = response.json()
    assert {item["provider"] for item in data["providers"]} == {"openai-search", "tavily", "mock"}
    assert all(item["api_only"] for item in data["providers"])
    assert all(item["local"] is False for item in data["providers"])
    assert "qdrant" in data["local_providers_blocked"]


def test_rag_query_rejects_local_provider_and_records_audit() -> None:
    audit = AuditStore()
    client = TestClient(_app(_principal(), audit_store=audit))

    response = client.post(
        "/api/v1/rag/query",
        json={"provider": "qdrant", "query": "governance"},
    )

    assert response.status_code == 400
    assert "Local retrieval providers" in response.text
    records = audit.list(limit=10, action="rag.query", resource_type="rag_provider")
    assert len(records) == 1
    assert records[0].resource_id == "qdrant"
    assert records[0].details["error_code"] == "provider_rejected"


def test_rag_query_blocks_estimated_budget_before_provider_use() -> None:
    audit = AuditStore()
    client = TestClient(_app(_principal(), audit_store=audit))

    response = client.post(
        "/api/v1/rag/query",
        json={
            "provider": "tavily",
            "query": "governance",
            "top_k": 10,
            "max_results": 20,
            "max_estimated_cost_usd": 0,
        },
    )

    assert response.status_code == 429
    assert "cost budget" in response.text
    records = audit.list(limit=10, action="rag.query", resource_type="rag_provider")
    assert len(records) == 1
    assert records[0].resource_id == "tavily"
    assert records[0].details["error_code"] == "budget_guard_rejected"


def test_rag_query_rejects_cross_tenant_scope() -> None:
    audit = AuditStore()
    client = TestClient(_app(_principal(tenant_id="tenant-1"), audit_store=audit))

    response = client.post(
        "/api/v1/rag/query",
        json={
            "provider": "mock",
            "query": "private deployment",
            "tenant_scope": "tenant-2",
        },
    )

    assert response.status_code == 403
    assert "tenant scope" in response.text
    records = audit.list(limit=10, action="rag.query", resource_type="rag_provider")
    assert len(records) == 1
    assert records[0].tenant_id == "tenant-1"
    assert records[0].details["error_code"] == "tenant_scope_rejected"


def test_rag_query_returns_tenant_scoped_mock_results_and_records_audit() -> None:
    audit = AuditStore()
    client = TestClient(_app(_principal(tenant_id="tenant-1"), audit_store=audit))

    response = client.post(
        "/api/v1/rag/query",
        json={
            "provider": "mock",
            "query": "api governance",
            "top_k": 3,
            "max_results": 5,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "mock"
    assert data["governance"]["api_only"] is True
    assert data["governance"]["tenant_scoped"] is True
    assert data["governance"]["budget_checked"] is True
    assert data["results"]
    assert {item["tenant_id"] for item in data["results"]} == {"tenant-1"}
    assert all("tenant-2" not in item["snippet"].lower() for item in data["results"])
    records = audit.list(limit=10, action="rag.query", resource_type="rag_provider")
    assert len(records) == 1
    assert records[0].outcome == "success"
    assert records[0].details["result_count"] == len(data["results"])
