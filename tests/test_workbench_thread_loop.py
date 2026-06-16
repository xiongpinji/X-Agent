from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app


def test_workbench_thread_loop_links_console_to_workflow_chat() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})

    workbench = client.get("/api/v1/workbench")

    assert workbench.status_code == 200
    workbench_payload = workbench.json()
    console = workbench_payload["console"]
    entries = {entry["id"]: entry for entry in workbench_payload["entries"]}

    assert console["tenant_id"] == "default"
    assert console["agent_id"]
    assert console["session_id"]
    assert entries["chat"]["path"] == "/chat"
    assert entries["workbench"]["path"] == "/api/v1/workbench"
    assert workbench_payload["permissions"]["can_trigger_execution"] is True
    assert workbench_payload["permissions"]["can_audit"] is True
    assert "active_threads" in workbench_payload["collaboration"]

    chat = client.post(
        "/api/v1/workflows/create/chat",
        json={
            "request": "commercial pilot workbench thread smoke",
            "agent_id": console["agent_id"],
        },
    )

    assert chat.status_code == 200
    chat_payload = chat.json()
    assert chat_payload["resource_type"] == "workflow_chat"
    assert chat_payload["status"] == "accepted"
    assert chat_payload["run_id"]
    assert chat_payload["trace_id"] == chat_payload["run_id"]
    assert chat_payload["agent_id"] == console["agent_id"]
    assert chat_payload["approval_required"] is False
    assert chat_payload["snapshot"]["run_id"] == chat_payload["run_id"]
    assert chat_payload["snapshot"]["tenant_id"] == console["tenant_id"]
    assert any(action["path"] == "/api/v1/workbench" for action in chat_payload["next_actions"])
    assert any(
        action["path"] == f"/api/v1/workflows/runs/{chat_payload['run_id']}"
        for action in chat_payload["next_actions"]
    )
