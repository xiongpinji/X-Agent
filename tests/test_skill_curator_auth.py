from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api import skill_curator
from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler
from backend.app.core.security import Principal, ROLE_SCOPES
from backend.app.dependencies import get_current_principal


def _principal(role: str, authenticated: bool = True) -> Principal:
    return Principal(
        tenant_id="tenant-a",
        user_id=f"{role}-user",
        role=role,
        scopes=list(ROLE_SCOPES.get(role, [])),
        authenticated=authenticated,
    )


def _app(principal: Principal | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(skill_curator.router)
    app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
    if principal is not None:
        app.dependency_overrides[get_current_principal] = lambda: principal
    return app


def test_skill_curator_requires_auth_when_api_key_required(monkeypatch) -> None:
    monkeypatch.setattr(
        skill_curator,
        "get_settings",
        lambda: SimpleNamespace(require_api_key=True, app_mode="development"),
    )
    client = TestClient(_app())

    response = client.post("/api/v1/skill-curator/analyze", json={"evidence": []})

    assert response.status_code == 401


def test_skill_curator_rejects_viewer_without_install_scope(monkeypatch) -> None:
    monkeypatch.setattr(
        skill_curator,
        "get_settings",
        lambda: SimpleNamespace(require_api_key=True, app_mode="development"),
    )
    monkeypatch.setattr(skill_curator, "get_current_principal", lambda request: _principal("viewer"))
    client = TestClient(_app(_principal("viewer")))

    response = client.post("/api/v1/skill-curator/analyze", json={"evidence": []})

    assert response.status_code == 403


def test_skill_curator_allows_local_dev_anonymous_exception(monkeypatch) -> None:
    monkeypatch.setattr(
        skill_curator,
        "get_settings",
        lambda: SimpleNamespace(require_api_key=False, app_mode="development"),
    )
    monkeypatch.delenv("XAGENT_REQUIRE_API_KEY", raising=False)
    client = TestClient(_app())

    response = client.post("/api/v1/skill-curator/analyze", json={"evidence": []})

    assert response.status_code == 200
    assert response.json()["evidence_count"] == 0
