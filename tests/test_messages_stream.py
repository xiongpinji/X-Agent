from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from backend.app.api.auth import _issue_token, _store_token_user
from backend.app.api.messages import UnifiedMessageEvent, build_channel_key, message_event_bus
from backend.app.core.admin import UserCreateRequest, UserStore
from backend.app.core.security import APIKeyCreateRequest, APIKeyStore
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


def _install_real_header_credentials(monkeypatch) -> tuple[str, str]:
    api_keys = APIKeyStore()
    raw_key = api_keys.create(
        APIKeyCreateRequest(
            name="messages-test",
            tenant_id="tenant-a",
            user_id="user-a",
            role="developer",
        )
    ).key
    monkeypatch.setattr("backend.app.dependencies.get_api_key_store", lambda: api_keys)

    users = UserStore()
    user = users.create(
        UserCreateRequest(
            email="messages-user@example.com",
            display_name="Messages User",
            role="developer",
            tenant_id="tenant-a",
        )
    )
    monkeypatch.setattr("backend.app.core.admin.user_store", users)
    token = _issue_token()
    _store_token_user(token, user.id)
    return raw_key, token


def test_messages_stream_accepts_bearer_and_api_key_headers(monkeypatch) -> None:
    api_key, bearer = _install_real_header_credentials(monkeypatch)
    client = TestClient(app)
    params = {"replay_only": "true", "trace_id": "trace-header-auth"}

    api_key_response = client.get(
        "/api/v1/messages/stream", params=params, headers={"x-api-key": api_key}
    )
    bearer_response = client.get(
        "/api/v1/messages/stream",
        params=params,
        headers={"Authorization": f"Bearer {bearer}"},
    )

    assert api_key_response.status_code == 200
    assert bearer_response.status_code == 200
    assert "event: system.notification" in api_key_response.text
    assert "event: system.notification" in bearer_response.text


def test_messages_stream_query_tenant_cannot_override_principal(monkeypatch) -> None:
    api_key, _ = _install_real_header_credentials(monkeypatch)
    _clear_event_bus()
    principal_channel = build_channel_key(
        tenant_id="tenant-a",
        agent_id="default-agent",
        user_id="user-a",
        channel_type="room",
        trace_id="trace-tenant-scope",
    )
    foreign_channel = build_channel_key(
        tenant_id="tenant-b",
        agent_id="default-agent",
        user_id="user-a",
        channel_type="room",
        trace_id="trace-tenant-scope",
    )
    message_event_bus.record(
        principal_channel,
        UnifiedMessageEvent(
            event_id="evt-tenant-a",
            event_type="message.created",
            tenant_id="tenant-a",
            agent_id="default-agent",
            user_id="user-a",
            channel_type="room",
            trace_id="trace-tenant-scope",
            payload={"content": "tenant-a-event"},
        ),
    )
    message_event_bus.record(
        foreign_channel,
        UnifiedMessageEvent(
            event_id="evt-tenant-b",
            event_type="message.created",
            tenant_id="tenant-b",
            agent_id="default-agent",
            user_id="user-a",
            channel_type="room",
            trace_id="trace-tenant-scope",
            payload={"content": "tenant-b-event"},
        ),
    )

    try:
        response = TestClient(app).get(
            "/api/v1/messages/stream",
            params={
                "tenant_id": "tenant-b",
                "channel_type": "room",
                "trace_id": "trace-tenant-scope",
                "replay_only": "true",
            },
            headers={"x-api-key": api_key},
        )

        assert response.status_code == 200
        assert "event: message.created" in response.text
        assert "tenant-a-event" in response.text
        assert "tenant-b-event" not in response.text
    finally:
        _clear_event_bus()


def test_messages_stream_prefers_last_event_id_header(monkeypatch) -> None:
    api_key, _ = _install_real_header_credentials(monkeypatch)
    _clear_event_bus()
    channel_key = build_channel_key(
        tenant_id="tenant-a",
        agent_id="default-agent",
        user_id="user-a",
        channel_type="room",
        trace_id="trace-header-resume",
    )
    for event_id in ("evt-header-1", "evt-header-2"):
        message_event_bus.record(
            channel_key,
            UnifiedMessageEvent(
                event_id=event_id,
                event_type="message.created",
                tenant_id="tenant-a",
                agent_id="default-agent",
                user_id="user-a",
                channel_type="room",
                trace_id="trace-header-resume",
                payload={"event": event_id},
            ),
        )

    try:
        response = TestClient(app).get(
            "/api/v1/messages/stream",
            params={
                "channel_type": "room",
                "trace_id": "trace-header-resume",
                "replay_only": "true",
            },
            headers={"x-api-key": api_key, "Last-Event-ID": "evt-header-1"},
        )

        assert response.status_code == 200
        assert "id: evt-header-1\n" not in response.text
        assert "evt-header-2" in response.text
    finally:
        _clear_event_bus()


def test_message_bus_bounds_slow_subscriber_and_keeps_latest_event() -> None:
    _clear_event_bus()
    channel_key = build_channel_key(tenant_id="tenant-1", trace_id="bounded-queue")
    queue = message_event_bus.subscribe(channel_key)

    try:
        async def publish_all() -> None:
            for index in range(257):
                await message_event_bus.publish(
                    channel_key,
                    UnifiedMessageEvent(
                        event_id=f"queue-{index}",
                        event_type="message.created",
                        tenant_id="tenant-1",
                    ),
                )

        asyncio.run(asyncio.wait_for(publish_all(), timeout=1))

        assert queue.maxsize == 256
        assert queue.qsize() == 256
        assert queue.get_nowait().event_id == "queue-1"
        latest = None
        while not queue.empty():
            latest = queue.get_nowait()
        assert latest is not None
        assert latest.event_id == "queue-256"
    finally:
        message_event_bus.unsubscribe(channel_key, queue)
        _clear_event_bus()


def test_message_bus_prunes_evicted_history_ids(monkeypatch) -> None:
    monkeypatch.setattr("backend.app.api.messages.HISTORY_LIMIT", 2)
    _clear_event_bus()
    channel_key = build_channel_key(tenant_id="tenant-1", trace_id="bounded-history")

    try:
        for event_id in ("reused", "middle", "latest"):
            message_event_bus.record(
                channel_key,
                UnifiedMessageEvent(
                    event_id=event_id,
                    event_type="message.created",
                    tenant_id="tenant-1",
                ),
            )
        message_event_bus.record(
            channel_key,
            UnifiedMessageEvent(
                event_id="reused",
                event_type="message.created",
                tenant_id="tenant-1",
                payload={"generation": 2},
            ),
        )

        assert [event.event_id for event in message_event_bus.get_history(channel_key)] == [
            "latest",
            "reused",
        ]
        assert message_event_bus.get_history(channel_key)[-1].payload == {"generation": 2}
    finally:
        _clear_event_bus()


def test_replay_event_id_dedupe_has_a_fixed_capacity() -> None:
    from backend.app.api.messages import _BoundedEventIds

    event_ids = _BoundedEventIds(maxlen=2, values=["one", "two"])

    assert event_ids.remember("two") is False
    assert event_ids.remember("three") is True
    assert event_ids.remember("one") is True
    assert len(event_ids) == 2
