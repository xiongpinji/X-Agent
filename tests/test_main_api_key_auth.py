from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler
from backend.app.api.skill_curator import get_skill_curator_principal
from backend.app.dependencies import get_current_principal
from backend.app.main import app, request_logging_middleware, tenant_isolation_middleware


def _set_bootstrap_key(monkeypatch, value: str = "bootstrap") -> None:
    """Keep bootstrap-key tests independent from the caller's local .env."""
    from backend.app.settings import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "bootstrap_api_key", value)
    monkeypatch.setattr(settings, "bootstrap_api_key_sha256", None)


def test_global_api_key_gate_rejects_invalid_key(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr("backend.app.main.settings.require_api_key", True)

    response = client.get("/api/v1/overview", headers={"x-api-key": "not-bootstrap"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"


def test_get_current_principal_stores_principal_in_request_scope(monkeypatch) -> None:
    _set_bootstrap_key(monkeypatch)
    test_app = FastAPI()

    @test_app.get("/scope-principal")
    async def scope_principal(request: Request) -> dict[str, object]:
        principal = get_current_principal(request)
        return {
            "same_object": request.scope["principal"] is principal,
            "authenticated": principal.authenticated,
            "role": principal.role,
        }

    test_app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
    client = TestClient(test_app)

    response = client.get("/scope-principal", headers={"x-api-key": "bootstrap"})

    assert response.status_code == 200
    assert response.json() == {
        "same_object": True,
        "authenticated": True,
        "role": "admin",
    }


def test_tenant_middleware_uses_principal_from_api_key_gate(monkeypatch) -> None:
    _set_bootstrap_key(monkeypatch)
    test_app = FastAPI()

    @test_app.middleware("http")
    async def api_key_gate(request: Request, call_next):
        return await request_logging_middleware(request, call_next)

    @test_app.middleware("http")
    async def tenant_gate(request: Request, call_next):
        return await tenant_isolation_middleware(request, call_next)

    @test_app.get("/api/protected")
    async def protected() -> dict[str, bool]:
        return {"ok": True}

    monkeypatch.setattr("backend.app.main.settings.require_api_key", True)
    client = TestClient(test_app)

    response = client.get(
        "/api/protected?tenant_id=other-tenant",
        headers={"x-api-key": "bootstrap"},
    )

    assert response.status_code == 200


def test_owned_mounted_routes_have_auth_or_signature_strategy() -> None:
    owned_prefixes = (
        "/api/v1/memory",
        "/api/v1/browser/advanced",
        "/api/v1/skill-curator",
        "/api/v1/channels",
        "/api/v1/sandbox",
    )
    signature_routes = {
        "/api/v1/channels/telegram/webhook",
        "/api/v1/sandbox/webhook/github",
    }
    failures: list[str] = []

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        path = route.path
        if not path.startswith(owned_prefixes):
            continue
        if path in signature_routes:
            continue

        dependant = route.dependant
        dependency_calls = {dependency.call for dependency in dependant.dependencies}
        uses_principal = bool(
            {get_current_principal, get_skill_curator_principal} & dependency_calls
        )
        endpoint_globals = set(getattr(route.endpoint, "__globals__", {}))
        uses_scope_guard = (
            "enforce_scope" in endpoint_globals
            or "_require_memory_read" in endpoint_globals
            or "_require_memory_write" in endpoint_globals
            or "_require_browser_read" in endpoint_globals
            or "_require_browser_operation" in endpoint_globals
            or "_enforce_skill_curator_access" in endpoint_globals
        )
        if not uses_principal or not uses_scope_guard:
            failures.append(f"{','.join(route.methods or [])} {path}")

    assert failures == []
