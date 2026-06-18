from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api import browser_advanced
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


@pytest.fixture
def app_factory():
    def make_app(principal: Principal) -> FastAPI:
        app = FastAPI()
        app.include_router(browser_advanced.router)
        app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
        app.dependency_overrides[get_current_principal] = lambda: principal
        return app

    return make_app


def test_browser_advanced_read_rejects_viewer_without_tools_read(app_factory) -> None:
    client = TestClient(app_factory(_principal("viewer")))

    response = client.post("/api/v1/browser/advanced/network/summary", json={"session_id": "s1"})

    assert response.status_code == 403


def test_browser_advanced_read_allows_developer_scope(app_factory, monkeypatch) -> None:
    async def fake_summary(session_id: str) -> dict[str, float | int]:
        assert session_id == "s1"
        return {
            "total_requests": 1,
            "total_responses": 1,
            "failed_responses": 0,
            "total_duration_ms": 5.0,
            "average_response_time_ms": 5.0,
        }

    monkeypatch.setattr(
        browser_advanced.advanced_browser_monitoring,
        "get_network_summary",
        fake_summary,
    )
    client = TestClient(app_factory(_principal("developer")))

    response = client.post("/api/v1/browser/advanced/network/summary", json={"session_id": "s1"})

    assert response.status_code == 200
    assert response.json()["total_requests"] == 1


def test_browser_advanced_operation_requires_agent_run(app_factory) -> None:
    client = TestClient(app_factory(_principal("viewer")))

    response = client.post("/api/v1/browser/advanced/elements/ref-1/click?session_id=s1")

    assert response.status_code == 403
