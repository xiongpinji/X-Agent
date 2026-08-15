from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_chat_static_entrypoint_serves_first_run_html() -> None:
    client = TestClient(app)

    response = client.get("/chat")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "X-Agent" in response.text


def test_default_chat_uses_the_real_agent_post_sse_entrypoint() -> None:
    chat_source = (PROJECT_ROOT / "frontend/src/pages/ChatPage.tsx").read_text(encoding="utf-8")
    api_source = (PROJECT_ROOT / "frontend/src/services/api.ts").read_text(encoding="utf-8")

    assert "useAgentStream" in chat_source
    assert "startStream" in chat_source
    assert "apiClient.sendMessage" not in chat_source
    assert "new SSEClient" not in chat_source
    assert "sseClient.connect" not in chat_source
    assert "/workflows/create/chat" not in api_source
    assert "Task completed (demo mode)" not in chat_source
    assert "setTimeout" not in chat_source


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
