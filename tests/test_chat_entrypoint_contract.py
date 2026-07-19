from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.settings import get_settings


def test_chat_static_entrypoint_serves_first_run_html() -> None:
    client = TestClient(app)

    response = client.get("/chat")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "X-Agent" in response.text


def test_workflow_chat_create_returns_first_run_contract() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/workflows/create/chat",
        json={"request": "summarize the current workspace", "agent_id": "default-agent"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"]
    assert payload["status"] in {"accepted", "running", "completed"}
    assert payload["message"]
    assert payload["approval_required"] is False
    assert isinstance(payload["events"], list)
    assert isinstance(payload["next_actions"], list)
    assert payload["agent_id"] == "default-agent"
    assert payload["resource_type"] == "workflow_chat"


def test_workflow_chat_bootstrap_rejects_anonymous_when_api_key_required(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_REQUIRE_API_KEY", "true")
    get_settings.cache_clear()
    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/workflows/create/chat",
            json={"request": "summarize the current workspace"},
        )

        assert response.status_code == 401
    finally:
        get_settings.cache_clear()


def test_workbench_bootstrap_includes_first_run_identity_fields() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/workbench")

    assert response.status_code == 200
    payload = response.json()
    console = payload["console"]
    assert console["tenant_id"] == "default"
    assert console["agent_id"]
    assert console["session_id"]
    assert console["user_id"]
    assert console["created_at"]
    assert payload["entries"][0]["path"] == "/chat"
