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


class _ManagePrincipal(_FakePrincipal):
    role = "admin"
    scopes = [*_FakePrincipal.scopes, "security:manage"]


class _OverrideManagePrincipal:
    def __call__(self):
        return _ManagePrincipal()


def _set_principal_override() -> None:
    app.dependency_overrides[get_current_principal] = _OverridePrincipal()


def _set_manage_principal_override() -> None:
    app.dependency_overrides[get_current_principal] = _OverrideManagePrincipal()


def _clear_principal_override() -> None:
    app.dependency_overrides.pop(get_current_principal, None)


def _clear_event_bus() -> None:
    message_event_bus.clear()


def test_messages_debug_channel_snapshot_returns_channel_state() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    _set_principal_override()
    _clear_event_bus()

    try:
        publish_response = client.post(
            "/api/v1/messages/publish-test",
            json={
                "tenant_id": "tenant-1",
                "org_id": "org-1",
                "room_id": "room-1",
                "conversation_id": "conv-1",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "channel_type": "room",
                "trace_id": "trace-1",
                "event_type": "room.created",
                "payload": {"hello": True},
            },
        )
        assert publish_response.status_code == 200

        snapshot_response = client.get(
            "/api/v1/messages/debug/channel-snapshot",
            params={
                "tenant_id": "tenant-1",
                "org_id": "org-1",
                "room_id": "room-1",
                "conversation_id": "conv-1",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "channel_type": "room",
                "trace_id": "trace-1",
            },
        )
        assert snapshot_response.status_code == 200
        snapshot = snapshot_response.json()

        assert snapshot["history_count"] == 1
        assert snapshot["subscriber_count"] == 0
        assert snapshot["event_types"] == ["room.created"]
        assert snapshot["domain_counts"] == {"room": 1}
        assert snapshot["last_event_type"] == "room.created"
        assert snapshot["last_event_id"]
    finally:
        _clear_principal_override()
        _clear_event_bus()


def test_messages_debug_channel_index_returns_all_channels() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    _set_principal_override()
    _clear_event_bus()

    try:
        client.post(
            "/api/v1/messages/publish-test",
            json={
                "tenant_id": "tenant-1",
                "org_id": "org-1",
                "room_id": "room-1",
                "conversation_id": "conv-1",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "channel_type": "room",
                "trace_id": "trace-1",
                "event_type": "room.created",
                "payload": {"hello": True},
            },
        )
        client.post(
            "/api/v1/messages/publish-test",
            json={
                "tenant_id": "tenant-1",
                "org_id": "org-1",
                "room_id": "room-2",
                "conversation_id": "conv-2",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "channel_type": "room",
                "trace_id": "trace-1",
                "event_type": "workflow.updated",
                "payload": {"hello": False},
            },
        )

        index_response = client.get("/api/v1/messages/debug/channel-index")
        assert index_response.status_code == 200
        payload = index_response.json()
        index = payload["items"]

        assert payload == {"items": index, "total": 2, "truncated": False}
        assert len(index) == 2
        assert {item["last_event_type"] for item in index} == {"room.created", "workflow.updated"}
        assert {tuple(item["event_types"]) for item in index} == {("room.created",), ("workflow.updated",)}
    finally:
        _clear_principal_override()
        _clear_event_bus()


def test_messages_debug_trace_index_returns_events_for_trace() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    _set_principal_override()
    _clear_event_bus()

    try:
        client.post(
            "/api/v1/messages/publish-test",
            json={
                "tenant_id": "tenant-1",
                "org_id": "org-1",
                "room_id": "room-1",
                "conversation_id": "conv-1",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "channel_type": "room",
                "trace_id": "trace-1",
                "event_type": "room.created",
                "payload": {"hello": True},
            },
        )
        client.post(
            "/api/v1/messages/publish-test",
            json={
                "tenant_id": "tenant-1",
                "org_id": "org-1",
                "room_id": "room-2",
                "conversation_id": "conv-2",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "channel_type": "room",
                "trace_id": "trace-1",
                "event_type": "workflow.updated",
                "payload": {"hello": False},
            },
        )

        trace_response = client.get(
            "/api/v1/messages/debug/trace-events",
            params={"trace_id": "trace-1"},
        )
        assert trace_response.status_code == 200
        trace_events = trace_response.json()

        assert len(trace_events) == 2
        assert {item["event_type"] for item in trace_events} == {"room.created", "workflow.updated"}
    finally:
        _clear_principal_override()
        _clear_event_bus()


def test_messages_debug_domain_events_returns_events_for_domain() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    _set_principal_override()
    _clear_event_bus()

    try:
        client.post(
            "/api/v1/messages/publish-test",
            json={
                "tenant_id": "tenant-1",
                "org_id": "org-1",
                "room_id": "room-1",
                "conversation_id": "conv-1",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "channel_type": "room",
                "trace_id": "trace-1",
                "event_type": "room.created",
                "payload": {"hello": True},
            },
        )
        client.post(
            "/api/v1/messages/publish-test",
            json={
                "tenant_id": "tenant-1",
                "org_id": "org-1",
                "room_id": "room-2",
                "conversation_id": "conv-2",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "channel_type": "room",
                "trace_id": "trace-1",
                "event_type": "workflow.updated",
                "payload": {"hello": False},
            },
        )

        domain_response = client.get(
            "/api/v1/messages/debug/domain-events",
            params={"domain": "workflow"},
        )
        assert domain_response.status_code == 200
        domain_events = domain_response.json()

        assert len(domain_events) == 1
        assert domain_events[0]["event_type"] == "workflow.updated"
    finally:
        _clear_principal_override()
        _clear_event_bus()


def test_messages_debug_clear_channel_removes_channel_state() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    _set_manage_principal_override()
    _clear_event_bus()

    try:
        client.post(
            "/api/v1/messages/publish-test",
            json={
                "tenant_id": "tenant-1",
                "org_id": "org-1",
                "room_id": "room-1",
                "conversation_id": "conv-1",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "channel_type": "room",
                "trace_id": "trace-1",
                "event_type": "room.created",
                "payload": {"hello": True},
            },
        )

        delete_response = client.delete(
            "/api/v1/messages/debug/channel",
            params={
                "tenant_id": "tenant-1",
                "org_id": "org-1",
                "room_id": "room-1",
                "conversation_id": "conv-1",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "channel_type": "room",
                "trace_id": "trace-1",
            },
        )
        assert delete_response.status_code == 200
        payload = delete_response.json()
        assert payload["cleared"] is True

        snapshot_response = client.get(
            "/api/v1/messages/debug/channel-snapshot",
            params={
                "tenant_id": "tenant-1",
                "org_id": "org-1",
                "room_id": "room-1",
                "conversation_id": "conv-1",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "channel_type": "room",
                "trace_id": "trace-1",
            },
        )
        assert snapshot_response.status_code == 200
        snapshot = snapshot_response.json()
        assert snapshot["history_count"] == 0
        assert snapshot["event_types"] == []
    finally:
        _clear_principal_override()
        _clear_event_bus()


def test_messages_debug_clear_trace_removes_trace_state() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    _set_manage_principal_override()
    _clear_event_bus()

    try:
        client.post(
            "/api/v1/messages/publish-test",
            json={
                "tenant_id": "tenant-1",
                "org_id": "org-1",
                "room_id": "room-1",
                "conversation_id": "conv-1",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "channel_type": "room",
                "trace_id": "trace-1",
                "event_type": "room.created",
                "payload": {"hello": True},
            },
        )

        clear_response = client.delete(
            "/api/v1/messages/debug/trace",
            params={"trace_id": "trace-1"},
        )
        assert clear_response.status_code == 200
        payload = clear_response.json()
        assert payload["trace_id"] == "trace-1"
        assert payload["removed_count"] == 1

        trace_response = client.get(
            "/api/v1/messages/debug/trace-events",
            params={"trace_id": "trace-1"},
        )
        assert trace_response.status_code == 200
        assert trace_response.json() == []
    finally:
        _clear_principal_override()
        _clear_event_bus()


def test_messages_debug_clear_domain_removes_domain_state() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    _set_manage_principal_override()
    _clear_event_bus()

    try:
        client.post(
            "/api/v1/messages/publish-test",
            json={
                "tenant_id": "tenant-1",
                "org_id": "org-1",
                "room_id": "room-1",
                "conversation_id": "conv-1",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "channel_type": "room",
                "trace_id": "trace-1",
                "event_type": "room.created",
                "payload": {"hello": True},
            },
        )
        client.post(
            "/api/v1/messages/publish-test",
            json={
                "tenant_id": "tenant-1",
                "org_id": "org-1",
                "room_id": "room-2",
                "conversation_id": "conv-2",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "channel_type": "room",
                "trace_id": "trace-1",
                "event_type": "workflow.updated",
                "payload": {"hello": False},
            },
        )

        clear_response = client.delete(
            "/api/v1/messages/debug/domain",
            params={"domain": "workflow"},
        )
        assert clear_response.status_code == 200
        payload = clear_response.json()
        assert payload["domain"] == "workflow"
        assert payload["removed_count"] == 1

        domain_response = client.get(
            "/api/v1/messages/debug/domain-events",
            params={"domain": "workflow"},
        )
        assert domain_response.status_code == 200
        assert domain_response.json() == []
    finally:
        _clear_principal_override()
        _clear_event_bus()


def test_messages_debug_reads_and_clears_only_principal_tenant() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    _set_principal_override()
    _clear_event_bus()
    tenant_a_channel = build_channel_key(
        tenant_id="tenant-1",
        agent_id="agent-1",
        user_id="user-1",
        channel_type="room",
        trace_id="shared-trace",
    )
    tenant_b_channel = build_channel_key(
        tenant_id="tenant-2",
        agent_id="agent-2",
        user_id="user-2",
        channel_type="room",
        trace_id="shared-trace",
    )
    for tenant_id, channel_key, event_id in (
        ("tenant-1", tenant_a_channel, "event-a"),
        ("tenant-2", tenant_b_channel, "event-b"),
    ):
        message_event_bus.record(
            channel_key,
            UnifiedMessageEvent(
                event_id=event_id,
                event_type="message.created",
                tenant_id=tenant_id,
                trace_id="shared-trace",
                channel_type="room",
                payload={"content": f"secret-{tenant_id}"},
            ),
        )

    try:
        index = client.get("/api/v1/messages/debug/channel-index")
        trace = client.get(
            "/api/v1/messages/debug/trace-events",
            params={"trace_id": "shared-trace"},
        )
        domain = client.get(
            "/api/v1/messages/debug/domain-events",
            params={"domain": "room"},
        )

        assert index.status_code == 200
        assert [item["channel_key"] for item in index.json()["items"]] == [tenant_a_channel]
        assert [item["event_id"] for item in trace.json()] == ["event-a"]
        assert [item["event_id"] for item in domain.json()] == ["event-a"]
        assert "secret-tenant-2" not in trace.text + domain.text

        _set_manage_principal_override()
        clear_trace = client.delete(
            "/api/v1/messages/debug/trace",
            params={"trace_id": "shared-trace"},
        )
        assert clear_trace.status_code == 200
        assert clear_trace.json()["removed_count"] == 1
        assert [event.event_id for event in message_event_bus.get_history(tenant_b_channel)] == [
            "event-b"
        ]

        message_event_bus.record(
            tenant_a_channel,
            UnifiedMessageEvent(
                event_id="event-a-domain",
                event_type="message.created",
                tenant_id="tenant-1",
                trace_id="domain-trace",
                channel_type="room",
            ),
        )
        clear_domain = client.delete(
            "/api/v1/messages/debug/domain",
            params={"domain": "room"},
        )
        assert clear_domain.status_code == 200
        assert clear_domain.json()["removed_count"] == 1
        assert [event.event_id for event in message_event_bus.get_history(tenant_b_channel)] == [
            "event-b"
        ]
    finally:
        _clear_principal_override()
        _clear_event_bus()


def test_messages_debug_destructive_clear_requires_manage_scope_and_stays_tenant_scoped() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    _set_principal_override()
    _clear_event_bus()
    tenant_a_channel = build_channel_key(
        tenant_id="tenant-1",
        agent_id="agent-1",
        user_id="user-1",
        trace_id="managed-trace",
    )
    tenant_b_channel = build_channel_key(tenant_id="tenant-2", trace_id="managed-trace")
    for tenant_id, channel_key, event_id in (
        ("tenant-1", tenant_a_channel, "managed-a"),
        ("tenant-2", tenant_b_channel, "managed-b"),
    ):
        message_event_bus.record(
            channel_key,
            UnifiedMessageEvent(
                event_id=event_id,
                event_type="message.created",
                tenant_id=tenant_id,
                trace_id="managed-trace",
            ),
        )

    try:
        denied_trace = client.delete(
            "/api/v1/messages/debug/trace",
            params={"trace_id": "managed-trace"},
        )
        denied_domain = client.delete(
            "/api/v1/messages/debug/domain",
            params={"domain": "room"},
        )
        denied_channel = client.delete(
            "/api/v1/messages/debug/channel",
            params={"trace_id": "managed-trace"},
        )
        assert denied_trace.status_code == 403
        assert denied_domain.status_code == 403
        assert denied_channel.status_code == 403
        assert [event.event_id for event in message_event_bus.get_history(tenant_a_channel)] == [
            "managed-a"
        ]
        assert [event.event_id for event in message_event_bus.get_history(tenant_b_channel)] == [
            "managed-b"
        ]

        _set_manage_principal_override()
        cleared_channel = client.delete(
            "/api/v1/messages/debug/channel",
            params={"trace_id": "managed-trace"},
        )
        assert cleared_channel.status_code == 200
        assert cleared_channel.json()["cleared"] is True
        assert message_event_bus.get_history(tenant_a_channel) == []
        assert [event.event_id for event in message_event_bus.get_history(tenant_b_channel)] == [
            "managed-b"
        ]
        message_event_bus.record(
            tenant_a_channel,
            UnifiedMessageEvent(
                event_id="managed-a-restored",
                event_type="message.created",
                tenant_id="tenant-1",
                trace_id="managed-trace",
            ),
        )
        cleared = client.delete(
            "/api/v1/messages/debug/trace",
            params={"trace_id": "managed-trace"},
        )
        assert cleared.status_code == 200
        assert cleared.json()["removed_count"] == 1
        assert message_event_bus.get_history(tenant_a_channel) == []
        assert [event.event_id for event in message_event_bus.get_history(tenant_b_channel)] == [
            "managed-b"
        ]
    finally:
        _clear_principal_override()
        _clear_event_bus()


def test_messages_channel_registry_evicts_oldest_per_tenant_and_caps_debug_index(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "backend.app.api.messages.MAX_HISTORY_CHANNELS_PER_TENANT",
        3,
        raising=False,
    )
    monkeypatch.setattr(
        "backend.app.api.messages.MAX_CHANNEL_INDEX_RESULTS",
        2,
        raising=False,
    )
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    _set_principal_override()
    _clear_event_bus()
    tenant_a_channels = [
        build_channel_key(tenant_id="tenant-1", room_id=f"room-{index}")
        for index in range(4)
    ]
    tenant_b_channel = build_channel_key(tenant_id="tenant-2", room_id="room-b")
    for index, channel_key in enumerate(tenant_a_channels):
        message_event_bus.record(
            channel_key,
            UnifiedMessageEvent(
                event_id=f"tenant-a-{index}",
                event_type="message.created",
                tenant_id="tenant-1",
            ),
        )
    message_event_bus.record(
        tenant_b_channel,
        UnifiedMessageEvent(
            event_id="tenant-b",
            event_type="message.created",
            tenant_id="tenant-2",
        ),
    )

    try:
        assert message_event_bus.get_history(tenant_a_channels[0]) == []
        assert [event.event_id for event in message_event_bus.get_history(tenant_b_channel)] == [
            "tenant-b"
        ]
        index = client.get("/api/v1/messages/debug/channel-index")
        assert index.status_code == 200
        payload = index.json()
        assert payload["total"] == 3
        assert payload["truncated"] is True
        assert len(payload["items"]) == 2
        assert all("tenant:tenant-1" in item["channel_key"] for item in payload["items"])

        reuse_channel = build_channel_key(tenant_id="tenant-1", room_id="room-reuse")
        message_event_bus.record(
            reuse_channel,
            UnifiedMessageEvent(
                event_id="tenant-a-0",
                event_type="message.created",
                tenant_id="tenant-1",
            ),
        )
        assert [event.event_id for event in message_event_bus.get_history(reuse_channel)] == [
            "tenant-a-0"
        ]
    finally:
        _clear_principal_override()
        _clear_event_bus()
