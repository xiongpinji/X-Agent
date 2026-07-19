from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.api.messages import message_event_bus
from backend.app.dependencies import get_current_principal
from backend.app.main import app


class _FakePrincipal:
    tenant_id = "tenant-1"
    org_id = "org-1"
    agent_id = "agent-1"
    user_id = "user-1"
    trace_id = "trace-1"
    request_id = "req-1"
    permission_scope: list[str] = []
    role = "developer"
    scopes: list[str] = [
        "agent:run",
        "agent:read",
        "tools:read",
        "memory:read",
        "memory:write",
        "workflow:create",
        "workflow:run",
        "audit:read",
    ]
    authenticated = True


class _OverridePrincipal:
    def __call__(self):
        return _FakePrincipal()


def _set_principal_override() -> None:
    app.dependency_overrides[get_current_principal] = _OverridePrincipal()


def _clear_principal_override() -> None:
    app.dependency_overrides.pop(get_current_principal, None)


def _clear_event_bus() -> None:
    message_event_bus.clear()


def test_messages_end_to_end_publish_stream_snapshot_and_clear() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    _set_principal_override()
    _clear_event_bus()

    try:
        publish_response = client.post(
            "/api/v1/messages/publish-test",
            json={
                "tenant_id": "tenant-1",
                "org_id": "org-1",
                "room_id": "room-e2e",
                "conversation_id": "conv-e2e",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "channel_type": "room",
                "trace_id": "trace-e2e",
                "event_type": "room.created",
                "payload": {"room": {"name": "E2E room"}},
            },
        )
        assert publish_response.status_code == 200

        # /api/v1/messages/stream is an infinite SSE stream by default (live
        # heartbeat loop). Tests pass replay_only=true so the endpoint returns the
        # connect notice + replayed history then ends — a finite body a plain
        # blocking get can read without hanging.
        stream_response = client.get(
            "/api/v1/messages/stream",
            params={
                "tenant_id": "tenant-1",
                "org_id": "org-1",
                "room_id": "room-e2e",
                "conversation_id": "conv-e2e",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "channel_type": "room",
                "trace_id": "trace-e2e",
                "last_event_id": "evt-missing",
                "replay_only": "true",
            },
        )
        assert stream_response.status_code == 200
        assert "system.notification" in stream_response.text
        assert "room.created" in stream_response.text
        assert "E2E room" in stream_response.text

        snapshot_response = client.get(
            "/api/v1/messages/debug/channel-snapshot",
            params={
                "tenant_id": "tenant-1",
                "org_id": "org-1",
                "room_id": "room-e2e",
                "conversation_id": "conv-e2e",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "channel_type": "room",
                "trace_id": "trace-e2e",
            },
        )
        assert snapshot_response.status_code == 200
        snapshot = snapshot_response.json()
        assert snapshot["history_count"] == 1
        assert snapshot["last_event_type"] == "room.created"

        clear_response = client.delete(
            "/api/v1/messages/debug/channel",
            params={
                "tenant_id": "tenant-1",
                "org_id": "org-1",
                "room_id": "room-e2e",
                "conversation_id": "conv-e2e",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "channel_type": "room",
                "trace_id": "trace-e2e",
            },
        )
        assert clear_response.status_code == 200
        assert clear_response.json()["cleared"] is True

        cleared_snapshot = client.get(
            "/api/v1/messages/debug/channel-snapshot",
            params={
                "tenant_id": "tenant-1",
                "org_id": "org-1",
                "room_id": "room-e2e",
                "conversation_id": "conv-e2e",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "channel_type": "room",
                "trace_id": "trace-e2e",
            },
        )
        assert cleared_snapshot.status_code == 200
        assert cleared_snapshot.json()["history_count"] == 0
    finally:
        _clear_principal_override()
        _clear_event_bus()
