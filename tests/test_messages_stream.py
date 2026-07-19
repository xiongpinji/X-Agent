from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.api.messages import UnifiedMessageEvent, build_channel_key, message_event_bus
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


def _read_stream_history(client, params: dict) -> str:
    """Read an SSE /messages/stream response containing only the replayed history.

    The endpoint streams an infinite live heartbeat loop by default, which a
    blocking client.get() can never finish reading (hang). Passing replay_only=true
    makes the server return the connect notice + replayed history then end, giving a
    finite body. Returns the SSE text for assertions.
    """
    request_params = {**params, "replay_only": "true"}
    response = client.get("/api/v1/messages/stream", params=request_params)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    return response.text


def test_messages_stream_replays_history_and_sets_sse_ids() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    _set_principal_override()
    _clear_event_bus()

    channel_key = build_channel_key(
        tenant_id="tenant-1",
        org_id="org-1",
        room_id="room-1",
        conversation_id="conv-1",
        agent_id="agent-1",
        user_id="user-1",
        channel_type="room",
        trace_id="trace-1",
    )

    historical_event = UnifiedMessageEvent(
        event_id="evt-1",
        event_type="room.created",
        tenant_id="tenant-1",
        org_id="org-1",
        room_id="room-1",
        conversation_id="conv-1",
        agent_id="agent-1",
        user_id="user-1",
        channel_type="room",
        trace_id="trace-1",
        payload={"ok": True},
    )
    message_event_bus.record(channel_key, historical_event)

    try:
        stream_text = _read_stream_history(
            client,
            {
                "tenant_id": "tenant-1",
                "org_id": "org-1",
                "room_id": "room-1",
                "conversation_id": "conv-1",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "channel_type": "room",
                "trace_id": "trace-1",
                "last_event_id": "evt-0",
            },
        )

        assert "event: system.notification" in stream_text
        assert "id: evt-1" in stream_text
        assert '\"event_type\":\"room.created\"' in stream_text
        assert message_event_bus.get_event_types(channel_key) == ["room.created"]
        assert message_event_bus.get_domain_counts(channel_key) == {"room": 1}
        assert [event.event_type for event in message_event_bus.get_history_by_domain(channel_key, "room")] == ["room.created"]
    finally:
        _clear_principal_override()
        _clear_event_bus()


def test_messages_stream_honors_domain_filters() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    _set_principal_override()
    _clear_event_bus()

    channel_key = build_channel_key(
        tenant_id="tenant-1",
        org_id="org-1",
        room_id="room-2",
        conversation_id="conv-2",
        agent_id="agent-1",
        user_id="user-1",
        channel_type="room",
        trace_id="trace-1",
    )

    message_event_bus.record(
        channel_key,
        UnifiedMessageEvent(
            event_id="evt-2",
            event_type="audit.created",
            tenant_id="tenant-1",
            org_id="org-1",
            room_id="room-2",
            conversation_id="conv-2",
            agent_id="agent-1",
            user_id="user-1",
            channel_type="room",
            payload={"audit": True},
        ),
    )

    try:
        stream_text = _read_stream_history(
            client,
            {
                "tenant_id": "tenant-1",
                "org_id": "org-1",
                "room_id": "room-2",
                "conversation_id": "conv-2",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "channel_type": "room",
                "trace_id": "trace-1",
                "include_audit": "false",
            },
        )

        assert "event: system.notification" in stream_text
        assert '\"event_type\":\"audit.created\"' not in stream_text
        assert message_event_bus.get_domain_counts(channel_key) == {"audit": 1}
    finally:
        _clear_principal_override()
        _clear_event_bus()


def test_messages_stream_uses_last_event_id_as_continuation_anchor() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    _set_principal_override()
    _clear_event_bus()

    channel_key = build_channel_key(
        tenant_id="tenant-1",
        org_id="org-1",
        room_id="room-3",
        conversation_id="conv-3",
        agent_id="agent-1",
        user_id="user-1",
        channel_type="room",
        trace_id="trace-1",
    )

    older_event = UnifiedMessageEvent(
        event_id="evt-10",
        event_type="room.created",
        tenant_id="tenant-1",
        org_id="org-1",
        room_id="room-3",
        conversation_id="conv-3",
        agent_id="agent-1",
        user_id="user-1",
        channel_type="room",
        trace_id="trace-1",
        payload={"step": 1},
    )
    newer_event = UnifiedMessageEvent(
        event_id="evt-11",
        event_type="room.member_added",
        tenant_id="tenant-1",
        org_id="org-1",
        room_id="room-3",
        conversation_id="conv-3",
        agent_id="agent-1",
        user_id="user-1",
        channel_type="room",
        trace_id="trace-1",
        payload={"step": 2},
    )
    message_event_bus.record(channel_key, older_event)
    message_event_bus.record(channel_key, newer_event)

    try:
        stream_text = _read_stream_history(
            client,
            {
                "tenant_id": "tenant-1",
                "org_id": "org-1",
                "room_id": "room-3",
                "conversation_id": "conv-3",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "channel_type": "room",
                "trace_id": "trace-1",
                "last_event_id": "evt-10",
            },
        )

        assert '\"event_id\":\"evt-10\"' not in stream_text
        assert '\"event_type\":\"room.member_added\"' in stream_text
        assert '\"event_type\":\"room.created\"' not in stream_text
        assert message_event_bus.get_event_types(channel_key) == ["room.created", "room.member_added"]
        assert message_event_bus.get_domain_counts(channel_key) == {"room": 2}
    finally:
        _clear_principal_override()
        _clear_event_bus()
