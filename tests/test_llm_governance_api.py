from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler
from backend.app.api.llm_governance import router
from backend.app.core.audit import AuditStore
from backend.app.core.llm.cost_optimizer import CostTracker
from backend.app.core.security import Principal, ROLE_SCOPES
from backend.app.dependencies import (
    get_audit_store,
    get_current_principal,
    get_llm_cost_tracker,
)
from backend.app.settings import get_settings


def _principal(role: str = "developer", scopes: list[str] | None = None) -> Principal:
    return Principal(
        tenant_id="tenant-1",
        user_id="user-1",
        role=role,
        authenticated=True,
        api_key_id="test-key",
        permission_scope=scopes or list(ROLE_SCOPES[role]),
        scopes=scopes or list(ROLE_SCOPES[role]),
    )


def _app(
    principal: Principal | None,
    *,
    cost_tracker: CostTracker | None = None,
    audit_store: AuditStore | None = None,
) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
    app.include_router(router)
    if principal is not None:
        app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_llm_cost_tracker] = lambda: cost_tracker or CostTracker()
    app.dependency_overrides[get_audit_store] = lambda: audit_store or AuditStore()
    return app


def test_llm_providers_requires_agent_run_scope() -> None:
    client = TestClient(_app(_principal(role="viewer", scopes=["audit:read"])))

    response = client.get("/api/v1/llm/providers")

    assert response.status_code == 403
    assert "agent:run" in response.text


def test_llm_providers_reports_api_only_external_surface(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_LLM_BACKEND", "mock")
    client = TestClient(_app(_principal()))

    response = client.get("/api/v1/llm/providers")

    assert response.status_code == 200
    data = response.json()
    assert data["default_provider"] in {"openai", "deepseek", "mock", "auto"}
    assert "ollama" in data["local_providers_blocked"]
    assert all(provider["api_only"] for provider in data["providers"])
    assert all(provider["local"] is False for provider in data["providers"])


def test_llm_complete_rejects_local_provider(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_LLM_BACKEND", "mock")
    tracker = CostTracker()
    audit = AuditStore()
    client = TestClient(_app(_principal(), cost_tracker=tracker, audit_store=audit))

    response = client.post(
        "/api/v1/llm/complete",
        json={
            "provider": "ollama",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 400
    assert "Local model providers" in response.text
    assert len(tracker.records) == 1
    assert tracker.records[0].provider == "ollama"
    assert tracker.records[0].success is False
    records = audit.list(limit=10, action="llm.completion", resource_type="llm_provider")
    assert len(records) == 1
    assert records[0].outcome == "failure"
    assert records[0].details["error_code"] == "provider_rejected"


def test_llm_complete_rejects_auto_provider_before_routing(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_LLM_BACKEND", "mock")
    tracker = CostTracker()
    audit = AuditStore()
    client = TestClient(_app(_principal(), cost_tracker=tracker, audit_store=audit))

    response = client.post(
        "/api/v1/llm/complete",
        json={
            "provider": "auto",
            "messages": [{"role": "user", "content": "hello"}],
            "max_estimated_cost_usd": 0,
        },
    )

    assert response.status_code == 400
    assert "Auto provider routing is not enabled" in response.text
    assert len(tracker.records) == 1
    assert tracker.records[0].provider == "auto"
    assert tracker.records[0].success is False
    records = audit.list(limit=10, action="llm.completion", resource_type="llm_provider")
    assert len(records) == 1
    assert records[0].details["error_code"] == "provider_rejected"


def test_llm_complete_rejects_deepseek_local_base_url(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_LLM_BACKEND", "mock")
    monkeypatch.setenv("XAGENT_DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("XAGENT_DEEPSEEK_BASE_URL", "http://localhost:11434/v1")
    get_settings.cache_clear()
    tracker = CostTracker()
    audit = AuditStore()
    client = TestClient(_app(_principal(), cost_tracker=tracker, audit_store=audit))

    try:
        response = client.post(
            "/api/v1/llm/complete",
            json={
                "provider": "deepseek",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 400
    assert "external HTTPS endpoint" in response.text
    assert "localhost:11434" not in response.text
    assert len(tracker.records) == 1
    assert tracker.records[0].provider == "deepseek"
    assert tracker.records[0].success is False
    records = audit.list(limit=10, action="llm.completion", resource_type="llm_provider")
    assert len(records) == 1
    assert records[0].details["error_code"] == "provider_base_url_rejected"


def test_llm_complete_rejects_deepseek_non_official_base_url(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_LLM_BACKEND", "mock")
    monkeypatch.setenv("XAGENT_DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("XAGENT_DEEPSEEK_BASE_URL", "https://openrouter.ai/api/v1")
    get_settings.cache_clear()
    tracker = CostTracker()
    audit = AuditStore()
    client = TestClient(_app(_principal(), cost_tracker=tracker, audit_store=audit))

    try:
        response = client.post(
            "/api/v1/llm/complete",
            json={
                "provider": "deepseek",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 400
    assert "official DeepSeek API host" in response.text
    assert "openrouter.ai" not in response.text
    assert len(tracker.records) == 1
    assert tracker.records[0].provider == "deepseek"
    assert tracker.records[0].success is False
    records = audit.list(limit=10, action="llm.completion", resource_type="llm_provider")
    assert len(records) == 1
    assert records[0].details["error_code"] == "provider_base_url_rejected"


def test_llm_complete_blocks_estimated_token_budget(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_LLM_BACKEND", "mock")
    tracker = CostTracker()
    audit = AuditStore()
    client = TestClient(_app(_principal(), cost_tracker=tracker, audit_store=audit))

    response = client.post(
        "/api/v1/llm/complete",
        json={
            "provider": "mock",
            "messages": [{"role": "user", "content": "x" * 200}],
            "max_input_tokens": 2,
        },
    )

    assert response.status_code == 429
    assert "token budget" in response.text
    assert len(tracker.records) == 1
    assert tracker.records[0].success is False
    records = audit.list(limit=10, action="llm.completion", resource_type="llm_provider")
    assert len(records) == 1
    assert records[0].details["error_code"] == "budget_guard_rejected"


def test_llm_complete_records_cost_and_audit_for_mock(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_LLM_BACKEND", "mock")
    tracker = CostTracker()
    audit = AuditStore()
    client = TestClient(_app(_principal(), cost_tracker=tracker, audit_store=audit))

    response = client.post(
        "/api/v1/llm/complete",
        json={
            "provider": "mock",
            "messages": [{"role": "user", "content": "Summarize API routing"}],
            "task_type": "analysis",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "mock"
    assert data["model"] == "mock"
    assert data["governance"]["budget_checked"] is True
    assert data["governance"]["api_only"] is True
    assert data["usage"]["tokens_used"] > 0
    assert len(tracker.records) == 1
    assert tracker.records[0].provider == "mock"
    assert tracker.records[0].success is True
    records = audit.list(limit=10, action="llm.completion", resource_type="llm_provider")
    assert len(records) == 1
    assert records[0].outcome == "success"
    assert records[0].details["provider"] == "mock"


def test_llm_stats_requires_audit_read_scope(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_LLM_BACKEND", "mock")
    tracker = CostTracker()
    client = TestClient(
        _app(
            _principal(role="user", scopes=["agent:run"]),
            cost_tracker=tracker,
        )
    )

    response = client.get("/api/v1/llm/stats")

    assert response.status_code == 403
    assert "audit:read" in response.text


def test_llm_stats_reports_tracker(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_LLM_BACKEND", "mock")
    tracker = CostTracker()
    tracker.record_call(
        model="mock",
        provider="mock",
        input_tokens=2,
        output_tokens=4,
        cost_usd=0.0,
        success=True,
        latency_ms=12.5,
        task_type="analysis",
        user_id="user-1",
    )
    client = TestClient(_app(_principal(role="admin"), cost_tracker=tracker))

    response = client.get("/api/v1/llm/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["api_only"] is True
    assert data["cost_by_provider"] == {"mock": 0.0}
    assert data["success_rate"] == 1.0
    assert "local" in data["local_providers_blocked"]
