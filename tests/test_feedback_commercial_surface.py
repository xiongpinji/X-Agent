from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler
from backend.app.core.feedback_store_file import FeedbackStoreFile
from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal


def _principal(*, tenant_id: str = "tenant-a", user_id: str = "user-a", scopes: list[str] | None = None) -> Principal:
    return Principal(
        tenant_id=tenant_id,
        user_id=user_id,
        role="user",
        authenticated=True,
        scopes=scopes if scopes is not None else ["feedback:read", "feedback:write"],
    )


def _analysis(priority: float = 0.8) -> dict[str, object]:
    return {
        "sentiment_type": "negative",
        "sentiment_score": -0.5,
        "category": "product",
        "tags": ["commercial"],
        "priority_score": priority,
        "urgency_score": 0.7,
        "impact_score": 0.9,
        "keywords": ["failure"],
        "entities": {},
    }


@pytest.fixture
def feedback_client(tmp_path):
    import backend.app.api.feedback as feedback_api

    current = {"principal": _principal()}
    app = FastAPI()
    app.include_router(feedback_api.router)
    app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
    app.dependency_overrides[get_current_principal] = lambda: current["principal"]

    store = FeedbackStoreFile(tmp_path / "feedback.json")
    previous_store = feedback_api._feedback_store
    previous_backend = feedback_api._feedback_store_backend
    feedback_api._feedback_store = store
    feedback_api._feedback_store_backend = "file"
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, current
    finally:
        feedback_api._feedback_store = previous_store
        feedback_api._feedback_store_backend = previous_backend


def _create(client: TestClient, *, feedback_type: str = "bug", title: str = "Broken login"):
    with patch(
        "backend.app.api.feedback.feedback_analyzer.analyze_feedback",
        new=AsyncMock(return_value=_analysis()),
    ):
        return client.post(
            "/api/v1/feedback/",
            json={
                "feedback_type": feedback_type,
                "title": title,
                "description": "A real customer cannot complete the workflow.",
                "severity": "high",
            },
        )


def test_feedback_router_is_mounted_in_the_commercial_app() -> None:
    from backend.app import main

    assert "feedback" in main._KEPT_ROUTER_MODULES


def test_feedback_dashboard_has_an_authenticated_route_and_navigation() -> None:
    root = Path(__file__).resolve().parents[1]
    app_source = (root / "frontend/src/App.tsx").read_text(encoding="utf-8")
    layout_source = (root / "frontend/src/components/Layout.tsx").read_text(encoding="utf-8")

    assert "@/pages/FeedbackDashboard" in app_source
    assert 'path="/feedback"' in app_source
    assert "href: '/feedback'" in layout_source


def test_feedback_endpoints_require_explicit_scopes(feedback_client) -> None:
    client, current = feedback_client
    current["principal"] = _principal(scopes=[])

    assert _create(client).status_code == 403
    assert client.get("/api/v1/feedback/").status_code == 403
    assert client.get("/api/v1/feedback/stats/summary").status_code == 403


def test_feedback_is_user_and_tenant_scoped_with_real_statistics(feedback_client) -> None:
    client, current = feedback_client
    first = _create(client, feedback_type="bug", title="Broken login")
    second = _create(client, feedback_type="feature", title="Need export")
    assert first.status_code == 201
    assert second.status_code == 201
    feedback_id = first.json()["id"]

    stats = client.get("/api/v1/feedback/stats/summary")
    assert stats.status_code == 200
    assert stats.json()["total"] == 2
    assert stats.json()["by_type"]["bug"] == 1
    assert stats.json()["by_type"]["feature"] == 1
    assert stats.json()["average_priority_score"] == pytest.approx(0.8)

    current["principal"] = _principal(user_id="user-b")
    own_list = client.get("/api/v1/feedback/")
    assert own_list.status_code == 200
    assert own_list.json()["total"] == 0
    assert own_list.json()["items"] == []
    assert client.get("/api/v1/feedback/trends").json()["data_points"] == []
    assert client.get("/api/v1/feedback/sentiment-analysis").json()["total"] == 0
    assert client.get("/api/v1/feedback/category-distribution").json()["total"] == 0
    assert client.get(f"/api/v1/feedback/{feedback_id}/analysis").status_code == 403

    current["principal"] = _principal(tenant_id="tenant-b", user_id="user-b")
    assert client.get(f"/api/v1/feedback/{feedback_id}").status_code == 404
    assert client.get(f"/api/v1/feedback/{feedback_id}/analysis").status_code == 404


def test_feedback_file_storage_fails_closed_in_production(monkeypatch) -> None:
    import backend.app.api.feedback as feedback_api

    previous_store = feedback_api._feedback_store
    previous_backend = feedback_api._feedback_store_backend
    monkeypatch.setenv("XAGENT_FEEDBACK_STORE_BACKEND", "file")
    feedback_api._feedback_store = None
    feedback_api._feedback_store_backend = None
    try:
        with (
            patch(
                "backend.app.api.feedback.get_settings",
                return_value=SimpleNamespace(app_mode="production"),
            ),
            pytest.raises(RuntimeError, match="Postgres"),
        ):
            feedback_api.get_feedback_store()
    finally:
        feedback_api._feedback_store = previous_store
        feedback_api._feedback_store_backend = previous_backend
