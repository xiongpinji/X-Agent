from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api import memory_enhanced
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
        app.include_router(memory_enhanced.router)
        app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
        app.dependency_overrides[get_current_principal] = lambda: principal
        return app

    return make_app


def test_memory_enhanced_write_requires_authenticated_principal(app_factory) -> None:
    anonymous = Principal(authenticated=False, scopes=[])
    client = TestClient(app_factory(anonymous))

    response = client.post("/api/v1/memory/store", json={"content": "secret"})

    assert response.status_code == 401


def test_memory_enhanced_read_allows_viewer_scope(app_factory) -> None:
    class FakeMemory:
        async def get_stats(self):
            return type(
                "Stats",
                (),
                {
                    "hot_count": 1,
                    "cold_count": 2,
                    "graph_count": 3,
                    "total_count": 6,
                    "avg_importance": 0.5,
                    "last_sync": None,
                },
            )()

    app = app_factory(_principal("viewer"))
    app.dependency_overrides[memory_enhanced.get_hybrid_memory_system] = lambda: FakeMemory()
    client = TestClient(app)

    response = client.get("/api/v1/memory/stats")

    assert response.status_code == 200
    assert response.json()["total_count"] == 6


def test_memory_enhanced_viewer_cannot_write(app_factory) -> None:
    client = TestClient(app_factory(_principal("viewer")))

    response = client.post("/api/v1/memory/sync")

    assert response.status_code == 403
