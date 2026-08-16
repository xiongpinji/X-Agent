from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.api.messages import build_channel_key, message_event_bus
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

        tenant_channel = build_channel_key(tenant_id="tenant-1")
        tenant_event_types = [
            event.event_type for event in message_event_bus.get_history(tenant_channel)
        ]

        assert "room.created" in event_types
        assert "room.member_added" in event_types
        assert "message.created" in event_types
        assert "workflow.updated" in event_types
        assert "room.closed" in event_types
        assert message_event_bus.get_event_types(channel_key) == event_types
        assert message_event_bus.get_domain_counts(channel_key) == {"room": 4, "workflow": 1}
        assert tenant_event_types == event_types

        console_stream = client.get(
            "/api/v1/messages/stream",
            params={"replay_only": "true"},
        )
        assert console_stream.status_code == 200
        for event_type in event_types:
            assert f"event: {event_type}" in console_stream.text

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


def test_collaboration_reports_applied_change_when_event_delivery_fails(
    monkeypatch,
) -> None:
    client = TestClient(
        app,
        headers={"x-api-key": "bootstrap"},
        raise_server_exceptions=False,
    )
    _set_principal_override()
    _clear_event_bus()

    try:
        room_response = client.post(
            "/api/v1/collaboration/rooms",
            json={"topic": "Delivery failure room", "tenant_id": "tenant-1"},
        )
        assert room_response.status_code == 200
        room_id = room_response.json()["room_id"]
        record_calls = 0

        def reject_record(*_args, **_kwargs):
            nonlocal record_calls
            record_calls += 1
            return False

        monkeypatch.setattr(message_event_bus, "record", reject_record)
        response = client.post(
            f"/api/v1/collaboration/rooms/{room_id}/messages",
            json={
                "sender_id": "agent-1",
                "content": "applied once",
            },
        )

        assert response.status_code == 503
        assert response.json() == {
            "code": "internal_error",
            "message": (
                "Collaboration operation completed, but realtime event delivery failed. "
                "Reconcile before retrying."
            ),
            "request_id": None,
            "trace_id": "trace-1",
            "details": {
                "delivery_status": "failed",
                "operation_status": "completed",
                "retry_safe": False,
            },
        }
        assert record_calls == 1
        persisted_room = client.get(f"/api/v1/collaboration/rooms/{room_id}")
        assert persisted_room.status_code == 200
        assert [message["content"] for message in persisted_room.json()["messages"]] == [
            "applied once"
        ]
    finally:
        _clear_principal_override()
        _clear_event_bus()
