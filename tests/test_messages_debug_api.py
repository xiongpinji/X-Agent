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
        index = index_response.json()

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
