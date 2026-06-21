from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler
from backend.app.api.provider_preflight import router
from backend.app.core.security import Principal, ROLE_SCOPES
from backend.app.dependencies import get_current_principal
from backend.app.main import app as main_app


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


def _app(principal: Principal | None) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
    app.include_router(router)
    if principal is not None:
        app.dependency_overrides[get_current_principal] = lambda: principal
    return app


def test_provider_preflight_requires_audit_read_scope() -> None:
    client = TestClient(_app(_principal(role="user", scopes=["agent:run"])))

    response = client.get("/api/v1/providers/preflight")

    assert response.status_code == 403
    assert "audit:read" in response.text


def test_provider_preflight_returns_redacted_dry_run_status(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_DEEPSEEK_API_KEY", "secret-deepseek-key")
    monkeypatch.setenv("XAGENT_PROTOCOL_LLM_API_KEY", "secret-protocol-llm-key")
    monkeypatch.setenv("XAGENT_PROTOCOL_LLM_BASE_URL", "https://llm-gateway.x-agent.dev/v1")
    client = TestClient(_app(_principal()))

    response = client.get("/api/v1/providers/preflight")

    assert response.status_code == 200
    payload = response.json()
    serialized = json.dumps(payload, ensure_ascii=False)
    assert payload["status"] == "passed"
    assert payload["dry_run"] is True
    assert payload["network_mutation_performed"] is False
    assert "secret-deepseek-key" not in serialized
    assert "secret-protocol-llm-key" not in serialized
    providers = {item["provider"]: item for item in payload["providers"]}
    assert providers["deepseek"]["status"] == "ready_to_call"
    assert providers["protocol-llm"]["status"] == "ready_to_call"
    assert providers["mock"]["status"] == "verification_only"
    assert all(item["network_call_attempted"] is False for item in payload["providers"])


def test_main_app_mounts_provider_preflight_route() -> None:
    routes = {
        getattr(route, "path", "")
        for route in main_app.routes
        if hasattr(route, "path")
    }

    assert "/api/v1/providers/preflight" in routes
