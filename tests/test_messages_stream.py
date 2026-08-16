from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from backend.app.api.auth import _issue_token, _store_token_user
from backend.app.api.messages import (
    MessageStreamCapacityError,
    UnifiedMessageEvent,
    build_channel_key,
    message_event_bus,
)
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


def _publish_event(channel_key: str, event: UnifiedMessageEvent) -> None:
    asyncio.run(message_event_bus.publish(channel_key, event))


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
    _publish_event(channel_key, historical_event)

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


def test_messages_stream_ephemeral_connect_notice_does_not_replace_replay_anchor() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    _set_principal_override()
    _clear_event_bus()
    channel_key = build_channel_key(
        tenant_id="tenant-1",
        agent_id="agent-1",
        user_id="user-1",
        trace_id="trace-1",
    )
    _publish_event(
        channel_key,
        UnifiedMessageEvent(
            event_id="durable-anchor",
            event_type="message.created",
            tenant_id="tenant-1",
            agent_id="agent-1",
            user_id="user-1",
            trace_id="trace-1",
        ),
    )

    try:
        stream_text = _read_stream_history(client, {})
        connect_notice, durable_event = stream_text.split("\n\n", 2)[:2]
        assert "event: system.notification" in connect_notice
        assert "id:" not in connect_notice
        assert "id: durable-anchor" in durable_event
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

    _publish_event(
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


def test_tenant_stream_applies_only_explicit_room_and_trace_filters() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    _set_principal_override()
    _clear_event_bus()
    matching_channel = build_channel_key(
        tenant_id="tenant-1",
        room_id="room-match",
        trace_id="trace-match",
    )
    other_channel = build_channel_key(
        tenant_id="tenant-1",
        room_id="room-other",
        trace_id="trace-other",
    )
    _publish_event(
        matching_channel,
        UnifiedMessageEvent(
            event_id="explicit-filter-match",
            event_type="room.created",
            tenant_id="tenant-1",
            room_id="room-match",
            trace_id="trace-match",
            payload={"room": {"name": "Matching Room"}},
        ),
    )
    _publish_event(
        other_channel,
        UnifiedMessageEvent(
            event_id="explicit-filter-other",
            event_type="room.created",
            tenant_id="tenant-1",
            room_id="room-other",
            trace_id="trace-other",
            payload={"room": {"name": "Other Room"}},
        ),
    )

    try:
        response = client.get(
            "/api/v1/messages/stream",
            params={
                "room_id": "room-match",
                "trace_id": "trace-match",
                "replay_only": "true",
            },
        )

        assert response.status_code == 200
        assert "Matching Room" in response.text
        assert "Other Room" not in response.text
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
    _publish_event(channel_key, older_event)
    _publish_event(channel_key, newer_event)

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


def _install_real_tenant_api_keys(monkeypatch) -> tuple[str, str]:
    api_keys = APIKeyStore()
    tenant_a_key = api_keys.create(
        APIKeyCreateRequest(
            name="messages-tenant-a",
            tenant_id="tenant-a",
            user_id="user-a",
            role="developer",
        )
    ).key
    tenant_b_key = api_keys.create(
        APIKeyCreateRequest(
            name="messages-tenant-b",
            tenant_id="tenant-b",
            user_id="user-b",
            role="developer",
        )
    ).key
    monkeypatch.setattr("backend.app.dependencies.get_api_key_store", lambda: api_keys)
    return tenant_a_key, tenant_b_key


def test_tenant_console_stream_receives_separate_authenticated_publish(monkeypatch) -> None:
    tenant_a_key, tenant_b_key = _install_real_tenant_api_keys(monkeypatch)
    client = TestClient(app)
    _clear_event_bus()
    tenant_a_channel = build_channel_key(tenant_id="tenant-a")
    tenant_b_channel = build_channel_key(tenant_id="tenant-b")
    tenant_a_live = message_event_bus.subscribe(tenant_a_channel, tenant_id="tenant-a")
    tenant_b_live = message_event_bus.subscribe(tenant_b_channel, tenant_id="tenant-b")

    try:
        publish_response = client.post(
            "/api/v1/messages/publish-test",
            headers={"x-api-key": tenant_a_key},
            json={
                "event_type": "room.created",
                "room_id": "browser-acceptance-room",
                "channel_type": "room",
                "room": {"name": "Browser Acceptance Room"},
            },
        )
        tenant_a_stream = client.get(
            "/api/v1/messages/stream",
            headers={"x-api-key": tenant_a_key},
            params={"replay_only": "true"},
        )
        tenant_b_stream = client.get(
            "/api/v1/messages/stream",
            headers={"x-api-key": tenant_b_key},
            params={"replay_only": "true"},
        )

        assert publish_response.status_code == 200
        assert tenant_a_live.get_nowait().event_type == "room.created"
        assert tenant_b_live.empty()
        assert tenant_a_stream.status_code == 200
        assert "room.created" in tenant_a_stream.text
        assert "Browser Acceptance Room" in tenant_a_stream.text
        assert tenant_b_stream.status_code == 200
        assert "Browser Acceptance Room" not in tenant_b_stream.text
    finally:
        message_event_bus.unsubscribe(tenant_a_channel, tenant_a_live)
        message_event_bus.unsubscribe(tenant_b_channel, tenant_b_live)
        _clear_event_bus()


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
    _publish_event(
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
    _publish_event(
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
        _publish_event(
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


def test_messages_stream_rejects_new_active_channel_at_tenant_capacity(
    monkeypatch,
) -> None:
    monkeypatch.setattr("backend.app.api.messages.MAX_ACTIVE_CHANNELS_PER_TENANT", 1)
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    _set_principal_override()
    _clear_event_bus()
    held_channel = build_channel_key(tenant_id="tenant-1", room_id="held")
    message_event_bus.record(
        held_channel,
        UnifiedMessageEvent(
            event_id="held-anchor",
            event_type="message.created",
            tenant_id="tenant-1",
        ),
    )
    held_queue = message_event_bus.subscribe(held_channel)
    foreign_channel = build_channel_key(tenant_id="tenant-2", room_id="foreign-active")
    message_event_bus.record(
        foreign_channel,
        UnifiedMessageEvent(
            event_id="foreign-anchor",
            event_type="message.created",
            tenant_id="tenant-2",
        ),
    )
    foreign_queue = message_event_bus.subscribe(foreign_channel)
    blocked_channel = build_channel_key(
        tenant_id="tenant-1",
        room_id="blocked",
        agent_id="agent-1",
        user_id="user-1",
        trace_id="trace-1",
    )

    try:
        blocked = client.get(
            "/api/v1/messages/stream",
            params={"room_id": "blocked", "replay_only": "true"},
        )
        assert blocked.status_code == 429
        assert blocked.json()["detail"] == {
            "code": "message_stream_capacity_exceeded",
            "message": "Message stream capacity is temporarily exhausted.",
        }
        assert message_event_bus.get_channel_snapshot(blocked_channel)["subscriber_count"] == 0
        assert message_event_bus.get_history(blocked_channel) == []
        assert message_event_bus.get_channel_snapshot(foreign_channel)["subscriber_count"] == 1

        message_event_bus.unsubscribe(held_channel, held_queue)
        accepted = client.get(
            "/api/v1/messages/stream",
            params={"room_id": "blocked", "replay_only": "true"},
        )
        assert accepted.status_code == 200
    finally:
        message_event_bus.unsubscribe(held_channel, held_queue)
        message_event_bus.unsubscribe(foreign_channel, foreign_queue)
        _clear_principal_override()
        _clear_event_bus()


def test_messages_stream_rejects_subscriber_when_tenant_channel_is_full(
    monkeypatch,
) -> None:
    monkeypatch.setattr("backend.app.api.messages.MAX_SUBSCRIBERS_PER_CHANNEL", 2)
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    _set_principal_override()
    _clear_event_bus()
    tenant_channel = build_channel_key(tenant_id="tenant-1")
    held_queue = message_event_bus.subscribe(tenant_channel, tenant_id="tenant-1")
    strict_mode_queue = message_event_bus.subscribe(
        tenant_channel,
        tenant_id="tenant-1",
    )

    try:
        blocked = client.get(
            "/api/v1/messages/stream",
            params={"replay_only": "true"},
        )

        assert blocked.status_code == 429
        assert blocked.json()["detail"]["code"] == "message_stream_capacity_exceeded"
        assert message_event_bus.get_channel_snapshot(tenant_channel)[
            "subscriber_count"
        ] == 2

        message_event_bus.unsubscribe(tenant_channel, strict_mode_queue)
        accepted = client.get(
            "/api/v1/messages/stream",
            params={"replay_only": "true"},
        )
        assert accepted.status_code == 200
    finally:
        message_event_bus.unsubscribe(tenant_channel, held_queue)
        message_event_bus.unsubscribe(tenant_channel, strict_mode_queue)
        _clear_principal_override()
        _clear_event_bus()


def test_publish_test_fails_closed_when_history_cannot_record(
    monkeypatch,
) -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    _set_principal_override()
    _clear_event_bus()
    channel_key = build_channel_key(
        tenant_id="tenant-1",
        room_id="delivery-failure",
        agent_id="agent-1",
        user_id="user-1",
        trace_id="trace-1",
    )
    queue = message_event_bus.subscribe(channel_key, tenant_id="tenant-1")
    monkeypatch.setattr(message_event_bus, "record", lambda *_args, **_kwargs: False)

    try:
        response = client.post(
            "/api/v1/messages/publish-test",
            json={
                "room_id": "delivery-failure",
                "event_type": "message.created",
            },
        )
        assert response.status_code == 503
        assert response.json()["detail"] == {
            "code": "message_delivery_unavailable",
            "message": "Message delivery could not be recorded.",
            "delivery_status": "not_delivered",
        }
        assert queue.empty()
    finally:
        message_event_bus.unsubscribe(channel_key, queue)
        _clear_principal_override()
        _clear_event_bus()


def test_message_bus_dual_channel_publish_fails_without_partial_history(
    monkeypatch,
) -> None:
    monkeypatch.setattr("backend.app.api.messages.MAX_HISTORY_CHANNELS_PER_TENANT", 1)
    _clear_event_bus()
    tenant_channel = build_channel_key(tenant_id="tenant-1")
    exact_channel = build_channel_key(tenant_id="tenant-1", room_id="room-1")
    event = UnifiedMessageEvent(
        event_id="dual-channel-capacity",
        event_type="room.created",
        tenant_id="tenant-1",
        room_id="room-1",
    )

    try:
        with pytest.raises(MessageStreamCapacityError):
            asyncio.run(message_event_bus.publish(exact_channel, event))

        assert message_event_bus.get_history(tenant_channel) == []
        assert message_event_bus.get_history(exact_channel) == []
        assert message_event_bus.record(
            build_channel_key(tenant_id="tenant-1", room_id="reuse"),
            event.model_copy(update={"payload": {"reused": True}}),
        ) is True
    finally:
        _clear_event_bus()


def test_message_bus_rolls_back_first_record_before_fanout_when_second_fails(
    monkeypatch,
) -> None:
    _clear_event_bus()
    tenant_channel = build_channel_key(tenant_id="tenant-1")
    exact_channel = build_channel_key(tenant_id="tenant-1", room_id="room-1")
    tenant_queue = message_event_bus.subscribe(tenant_channel, tenant_id="tenant-1")
    exact_queue = message_event_bus.subscribe(exact_channel, tenant_id="tenant-1")
    event = UnifiedMessageEvent(
        event_id="dual-channel-rollback",
        event_type="room.created",
        tenant_id="tenant-1",
        room_id="room-1",
    )
    original_record = message_event_bus.record

    def fail_exact_record(channel_key, candidate, **kwargs):
        if channel_key == exact_channel:
            return False
        return original_record(channel_key, candidate, **kwargs)

    monkeypatch.setattr(message_event_bus, "record", fail_exact_record)

    try:
        with pytest.raises(MessageStreamCapacityError):
            asyncio.run(message_event_bus.publish(exact_channel, event))

        assert message_event_bus.get_history(tenant_channel) == []
        assert message_event_bus.get_history(exact_channel) == []
        assert tenant_queue.empty()
        assert exact_queue.empty()
        assert original_record(
            build_channel_key(tenant_id="tenant-1", room_id="reuse"),
            event.model_copy(update={"payload": {"reused": True}}),
        ) is True
    finally:
        message_event_bus.unsubscribe(tenant_channel, tenant_queue)
        message_event_bus.unsubscribe(exact_channel, exact_queue)
        _clear_event_bus()


def test_message_bus_converts_second_record_exception_after_atomic_rollback(
    monkeypatch,
) -> None:
    _clear_event_bus()
    tenant_channel = build_channel_key(tenant_id="tenant-1")
    exact_channel = build_channel_key(tenant_id="tenant-1", room_id="room-1")
    tenant_queue = message_event_bus.subscribe(tenant_channel, tenant_id="tenant-1")
    event = UnifiedMessageEvent(
        event_id="dual-channel-exception",
        event_type="room.created",
        tenant_id="tenant-1",
        room_id="room-1",
    )
    original_record = message_event_bus.record

    def raise_for_exact(channel_key, candidate, **kwargs):
        if channel_key == exact_channel:
            original_record(channel_key, candidate, **kwargs)
            raise OSError("injected record failure")
        return original_record(channel_key, candidate, **kwargs)

    monkeypatch.setattr(message_event_bus, "record", raise_for_exact)

    try:
        with pytest.raises(
            MessageStreamCapacityError,
            match="message_history_capacity_exceeded",
        ):
            asyncio.run(message_event_bus.publish(exact_channel, event))

        assert message_event_bus.get_history(tenant_channel) == []
        assert message_event_bus.get_history(exact_channel) == []
        assert tenant_queue.empty()
    finally:
        message_event_bus.unsubscribe(tenant_channel, tenant_queue)
        _clear_event_bus()


def test_message_bus_rollback_restores_history_entry_evicted_by_first_record(
    monkeypatch,
) -> None:
    monkeypatch.setattr("backend.app.api.messages.HISTORY_LIMIT", 1)
    _clear_event_bus()
    tenant_channel = build_channel_key(tenant_id="tenant-1")
    exact_channel = build_channel_key(tenant_id="tenant-1", room_id="room-1")
    original_record = message_event_bus.record
    original_record(
        tenant_channel,
        UnifiedMessageEvent(
            event_id="existing-anchor",
            event_type="message.created",
            tenant_id="tenant-1",
        ),
    )

    def raise_for_exact(channel_key, candidate, **kwargs):
        if channel_key == exact_channel:
            raise OSError("injected record failure")
        return original_record(channel_key, candidate, **kwargs)

    monkeypatch.setattr(message_event_bus, "record", raise_for_exact)

    try:
        with pytest.raises(MessageStreamCapacityError):
            asyncio.run(
                message_event_bus.publish(
                    exact_channel,
                    UnifiedMessageEvent(
                        event_id="new-event",
                        event_type="room.created",
                        tenant_id="tenant-1",
                        room_id="room-1",
                    ),
                )
            )

        assert [
            event.event_id for event in message_event_bus.get_history(tenant_channel)
        ] == ["existing-anchor"]
        assert message_event_bus.get_history(exact_channel) == []
    finally:
        _clear_event_bus()


def test_message_bus_rollback_restores_inactive_channel_evicted_during_publish(
    monkeypatch,
) -> None:
    monkeypatch.setattr("backend.app.api.messages.MAX_HISTORY_CHANNELS_PER_TENANT", 2)
    _clear_event_bus()
    first_old_channel = build_channel_key(tenant_id="tenant-1", room_id="old-1")
    second_old_channel = build_channel_key(tenant_id="tenant-1", room_id="old-2")
    exact_channel = build_channel_key(tenant_id="tenant-1", room_id="new")
    original_record = message_event_bus.record
    for channel_key, event_id in (
        (first_old_channel, "old-1"),
        (second_old_channel, "old-2"),
    ):
        original_record(
            channel_key,
            UnifiedMessageEvent(
                event_id=event_id,
                event_type="message.created",
                tenant_id="tenant-1",
            ),
        )

    def raise_for_exact(channel_key, candidate, **kwargs):
        if channel_key == exact_channel:
            raise OSError("injected record failure")
        return original_record(channel_key, candidate, **kwargs)

    monkeypatch.setattr(message_event_bus, "record", raise_for_exact)

    try:
        with pytest.raises(MessageStreamCapacityError):
            asyncio.run(
                message_event_bus.publish(
                    exact_channel,
                    UnifiedMessageEvent(
                        event_id="new-event",
                        event_type="room.created",
                        tenant_id="tenant-1",
                        room_id="new",
                    ),
                )
            )

        assert [
            event.event_id
            for event in message_event_bus.get_history(first_old_channel)
        ] == ["old-1"]
        assert [
            event.event_id
            for event in message_event_bus.get_history(second_old_channel)
        ] == ["old-2"]
    finally:
        _clear_event_bus()


def test_message_bus_overflow_emits_private_gap_and_keeps_authoritative_history() -> None:
    _clear_event_bus()
    channel_key = build_channel_key(tenant_id="tenant-1")
    foreign_channel = build_channel_key(tenant_id="tenant-2")
    queue = message_event_bus.subscribe(channel_key)
    foreign_queue = message_event_bus.subscribe(foreign_channel)

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
        assert queue.qsize() == 1
        gap = queue.get_nowait()
        assert gap.event_type == "stream.gap"
        assert gap.tenant_id == "tenant-1"
        assert gap.payload == {"reason": "subscriber_overflow"}
        history = message_event_bus.get_history(channel_key)
        assert history[-1].event_id == "queue-256"
        assert all(event.event_type != "stream.gap" for event in history)
        assert foreign_queue.empty()
        asyncio.run(
            message_event_bus.publish(
                foreign_channel,
                UnifiedMessageEvent(
                    event_id="foreign-event",
                    event_type="message.created",
                    tenant_id="tenant-2",
                ),
            )
        )
        assert foreign_queue.get_nowait().event_id == "foreign-event"
    finally:
        message_event_bus.unsubscribe(channel_key, queue)
        message_event_bus.unsubscribe(foreign_channel, foreign_queue)
        _clear_event_bus()


def test_message_bus_lru_preserves_active_history_and_evicts_inactive_history(
    monkeypatch,
) -> None:
    monkeypatch.setattr("backend.app.api.messages.MAX_HISTORY_CHANNELS_PER_TENANT", 2)
    _clear_event_bus()
    active_channel = build_channel_key(tenant_id="tenant-1", room_id="active-oldest")
    inactive_channel = build_channel_key(tenant_id="tenant-1", room_id="inactive")
    newcomer_channel = build_channel_key(tenant_id="tenant-1", room_id="newcomer")
    rejected_channel = build_channel_key(tenant_id="tenant-1", room_id="rejected")
    reuse_channel = build_channel_key(tenant_id="tenant-1", room_id="reuse")
    foreign_channel = build_channel_key(tenant_id="tenant-2", room_id="foreign")
    message_event_bus.record(
        active_channel,
        UnifiedMessageEvent(
            event_id="active-anchor",
            event_type="message.created",
            tenant_id="tenant-1",
            payload={"generation": 1},
        ),
    )
    active_queue = message_event_bus.subscribe(active_channel)
    newcomer_queue = None
    for channel_key, event_id, tenant_id in (
        (inactive_channel, "inactive-event", "tenant-1"),
        (foreign_channel, "foreign-event", "tenant-2"),
        (newcomer_channel, "newcomer-event", "tenant-1"),
    ):
        message_event_bus.record(
            channel_key,
            UnifiedMessageEvent(
                event_id=event_id,
                event_type="message.created",
                tenant_id=tenant_id,
            ),
        )

    try:
        assert [event.event_id for event in message_event_bus.get_history(active_channel)] == [
            "active-anchor"
        ]
        assert message_event_bus.get_history(inactive_channel) == []
        assert [event.event_id for event in message_event_bus.get_history(foreign_channel)] == [
            "foreign-event"
        ]
        message_event_bus.record(
            reuse_channel,
            UnifiedMessageEvent(
                event_id="active-anchor",
                event_type="message.created",
                tenant_id="tenant-1",
                payload={"generation": 2},
            ),
        )
        assert message_event_bus.get_history(reuse_channel) == []
        newcomer_queue = message_event_bus.subscribe(newcomer_channel)
        assert message_event_bus.record(
            rejected_channel,
            UnifiedMessageEvent(
                event_id="rejected-event",
                event_type="message.created",
                tenant_id="tenant-1",
            ),
        ) is False
        assert message_event_bus.get_history(rejected_channel) == []
        assert [event.event_id for event in message_event_bus.get_history(active_channel)] == [
            "active-anchor"
        ]
        assert [event.event_id for event in message_event_bus.get_history(newcomer_channel)] == [
            "newcomer-event"
        ]
    finally:
        message_event_bus.unsubscribe(active_channel, active_queue)
        if newcomer_queue is not None:
            message_event_bus.unsubscribe(newcomer_channel, newcomer_queue)
        _clear_event_bus()


def test_message_bus_records_business_events_with_full_active_capacity_and_history_headroom(
    monkeypatch,
) -> None:
    monkeypatch.setattr("backend.app.api.messages.MAX_ACTIVE_CHANNELS_PER_TENANT", 2)
    monkeypatch.setattr("backend.app.api.messages.MAX_HISTORY_CHANNELS_PER_TENANT", 4)
    _clear_event_bus()
    active_channels = [
        build_channel_key(tenant_id="tenant-1", room_id=f"active-{index}")
        for index in range(2)
    ]
    inactive_channel = build_channel_key(tenant_id="tenant-1", room_id="inactive-oldest")
    newcomer_channel = build_channel_key(tenant_id="tenant-1", room_id="newcomer")
    queues = []
    for index, channel_key in enumerate(active_channels):
        assert message_event_bus.record(
            channel_key,
            UnifiedMessageEvent(
                event_id=f"active-anchor-{index}",
                event_type="message.created",
                tenant_id="tenant-1",
            ),
        ) is True
        queues.append(message_event_bus.subscribe(channel_key, tenant_id="tenant-1"))
    assert message_event_bus.record(
        inactive_channel,
        UnifiedMessageEvent(
            event_id="inactive-anchor",
            event_type="message.created",
            tenant_id="tenant-1",
        ),
    ) is True

    try:
        asyncio.run(
            message_event_bus.publish(
                active_channels[0],
                UnifiedMessageEvent(
                    event_id="active-business-event",
                    event_type="message.created",
                    tenant_id="tenant-1",
                ),
            )
        )
        asyncio.run(
            message_event_bus.publish(
                newcomer_channel,
                UnifiedMessageEvent(
                    event_id="newcomer-business-event",
                    event_type="message.created",
                    tenant_id="tenant-1",
                ),
            )
        )

        assert queues[0].get_nowait().event_id == "active-business-event"
        assert message_event_bus.get_history(inactive_channel) == []
        assert [event.event_id for event in message_event_bus.get_history(newcomer_channel)] == [
            "newcomer-business-event"
        ]
        for index, channel_key in enumerate(active_channels):
            assert message_event_bus.get_history(channel_key)[0].event_id == (
                f"active-anchor-{index}"
            )
    finally:
        for channel_key, queue in zip(active_channels, queues, strict=True):
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


def test_message_bus_keeps_event_id_until_every_channel_reference_is_removed() -> None:
    _clear_event_bus()
    first_channel = build_channel_key(tenant_id="tenant-1", room_id="room-1")
    second_channel = build_channel_key(tenant_id="tenant-1", room_id="room-2")
    reuse_channel = build_channel_key(tenant_id="tenant-1", room_id="room-reuse")
    shared = UnifiedMessageEvent(
        event_id="shared-event",
        event_type="message.created",
        tenant_id="tenant-1",
        payload={"generation": 1},
    )

    try:
        message_event_bus.record(first_channel, shared)
        message_event_bus.record(second_channel, shared)
        assert [event.event_id for event in message_event_bus.get_history(first_channel)] == [
            "shared-event"
        ]
        assert [event.event_id for event in message_event_bus.get_history(second_channel)] == [
            "shared-event"
        ]

        message_event_bus.clear_channel(first_channel)
        message_event_bus.record(
            reuse_channel,
            UnifiedMessageEvent(
                event_id="shared-event",
                event_type="message.created",
                tenant_id="tenant-1",
                payload={"generation": 2},
            ),
        )
        assert message_event_bus.get_history(reuse_channel) == []

        message_event_bus.clear_channel(second_channel)
        message_event_bus.record(
            reuse_channel,
            UnifiedMessageEvent(
                event_id="shared-event",
                event_type="message.created",
                tenant_id="tenant-1",
                payload={"generation": 2},
            ),
        )
        assert message_event_bus.get_history(reuse_channel)[0].payload == {"generation": 2}
    finally:
        _clear_event_bus()


def test_message_bus_unsubscribe_removes_only_the_empty_channel_entry() -> None:
    _clear_event_bus()
    first_channel = build_channel_key(tenant_id="tenant-1", room_id="room-1")
    second_channel = build_channel_key(tenant_id="tenant-1", room_id="room-2")
    first_queue = message_event_bus.subscribe(first_channel)
    second_queue = message_event_bus.subscribe(second_channel)

    try:
        message_event_bus.unsubscribe(first_channel, first_queue)
        assert message_event_bus.get_channel_snapshot(first_channel)["subscriber_count"] == 0
        assert message_event_bus.get_channel_snapshot(second_channel)["subscriber_count"] == 1
    finally:
        message_event_bus.unsubscribe(second_channel, second_queue)
        _clear_event_bus()


def test_replay_event_id_dedupe_has_a_fixed_capacity() -> None:
    from backend.app.api.messages import _BoundedEventIds

    event_ids = _BoundedEventIds(maxlen=2, values=["one", "two"])

    assert event_ids.remember("two") is False
    assert event_ids.remember("three") is True
    assert event_ids.remember("one") is True
    assert len(event_ids) == 2
