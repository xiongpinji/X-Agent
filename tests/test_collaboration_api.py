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


class _OverridePrincipal:
    def __call__(self):
        return _FakePrincipal()


def _set_principal_override() -> None:
    app.dependency_overrides[get_current_principal] = _OverridePrincipal()


def _clear_principal_override() -> None:
    app.dependency_overrides.pop(get_current_principal, None)


def _clear_event_bus() -> None:
    message_event_bus.clear()


def test_collaboration_room_events_are_published_to_event_bus() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    _set_principal_override()
    _clear_event_bus()

    try:
        create_response = client.post(
            "/api/v1/collaboration/rooms",
            json={"topic": "Realtime room", "tenant_id": "tenant-1", "members": ["agent-2"], "invited_role_template_ids": ["role-1"]},
        )
        assert create_response.status_code == 200
        room = create_response.json()
        room_id = room["room_id"]

        add_member_response = client.post(f"/api/v1/collaboration/rooms/{room_id}/members", json={"member_id": "agent-3"})
        assert add_member_response.status_code == 200

        message_response = client.post(
            f"/api/v1/collaboration/rooms/{room_id}/messages",
            json={
                "sender_id": "agent-1",
                "sender_type": "agent",
                "content": "hello",
                "message_type": "text",
                "metadata": {"conversation_id": "conv-1"},
            },
        )
        assert message_response.status_code == 200

        workflow_response = client.post(f"/api/v1/collaboration/rooms/{room_id}/workflow-suggestion")
        assert workflow_response.status_code == 200

        close_response = client.post(f"/api/v1/collaboration/rooms/{room_id}/close")
        assert close_response.status_code == 200

        channel_key = f"tenant:tenant-1|org:*|room:{room_id}|conv:*|agent:agent-1|user:user-1|channel:*|trace:trace-1"
        history = message_event_bus.get_history(channel_key)
        event_types = [event.event_type for event in history]

        assert "room.created" in event_types
        assert "room.member_added" in event_types
        assert "message.created" in event_types
        assert "workflow.updated" in event_types
        assert "room.closed" in event_types
        assert message_event_bus.get_event_types(channel_key) == event_types
        assert message_event_bus.get_domain_counts(channel_key) == {"room": 4, "workflow": 1}

        room_created = next(event for event in history if event.event_type == "room.created")
        assert room_created.payload["room"]["topic"] == "Realtime room"
        assert room_created.channel_type == "room"

        member_added = next(event for event in history if event.event_type == "room.member_added")
        assert member_added.payload["member_id"] == "agent-3"

        message_created = next(event for event in history if event.event_type == "message.created")
        assert message_created.payload["message"]["content"] == "hello"
        assert message_created.payload["room"]["room_id"] == room_id

        workflow_updated = next(event for event in history if event.event_type == "workflow.updated")
        assert workflow_updated.payload["workflow_suggestion"]["room_id"] == room_id
        assert workflow_updated.payload["workflow_suggestion"]["topic"] == "Realtime room"

        room_closed = next(event for event in history if event.event_type == "room.closed")
        assert room_closed.payload["room"]["status"] == "closed"
    finally:
        _clear_principal_override()
        _clear_event_bus()
