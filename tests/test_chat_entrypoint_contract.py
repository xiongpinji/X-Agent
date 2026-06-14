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


def test_workbench_home_returns_panda_dashboard_contract() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/workbench/home")

    assert response.status_code == 200
    payload = response.json()
    assert payload["brand"]["product_name"] == "Panda Agent"
    assert payload["brand"]["platform_name"]
    assert payload["brand"]["subtitle"] == "Powered by X-Agent Autonomous Framework"
    assert payload["summary"]
    assert payload["metrics"]["active_agents"] >= 1
    assert payload["metrics"]["running_workflows"] >= 1
    assert isinstance(payload["agent_activity"], list)
    assert isinstance(payload["workflow_runs"], list)
    control_summary = payload["control_summary"]
    assert control_summary["source"] == "control_mode_store"
    assert control_summary["read_only"] is True
    assert control_summary["execute_enabled"] is False
    assert isinstance(control_summary["plan_count"], int)
    assert isinstance(control_summary["goal_count"], int)

    runtime_summary = payload["runtime_capability_summary"]
    assert runtime_summary["source"] == "current-mainline-runtime-vs-detached-candidates"
    assert runtime_summary["read_only"] is True
    assert runtime_summary["execute_enabled"] is False
    assert runtime_summary["ok"] is False
    assert runtime_summary["status"] in {"needs_review", "unknown"}
    assert runtime_summary["status"] != "ready"
    assert "runtime_capability" in " ".join(runtime_summary["issue_codes"])
    assert "detached" in runtime_summary["boundary"]
    assert {item["tone"] for item in payload["agent_activity"]} <= {
        "success",
        "warning",
        "danger",
        "neutral",
    }
    assert all(0 <= item["progress"] <= 100 for item in payload["workflow_runs"])
