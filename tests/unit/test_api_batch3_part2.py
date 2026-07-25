"""Batch 3 Part 2: collaboration / browser / feedback / files_v2 全覆盖测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime, UTC
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ─── helpers ───────────────────────────────────────────────────────────────────

def _make_principal(role="user", tenant_id="t1", user_id="u1"):
    from backend.app.core.security import Principal
    return Principal(
        user_id=user_id,
        tenant_id=tenant_id,
        role=role,
        agent_id="agent-1",
        trace_id="trace-1",
        request_id="req-1",
        authenticated=True,
        scopes=["*", "agent:run", "agent:read", "tools:read", "memory:write", "workflow:create", "files:read", "files:write"],
        permission_scope=["*"],
    )


def _make_test_app(router):
    """Create a minimal FastAPI app with just the given router and auth override."""
    from backend.app.dependencies import get_current_principal
    from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler
    app = FastAPI()
    app.include_router(router)
    app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
    app.dependency_overrides[get_current_principal] = lambda: _make_principal()
    return app


# ═══════════════════════════════════════════════════════════════════════════════
# COLLABORATION MODULE
# ═══════════════════════════════════════════════════════════════════════════════

class TestResolveTenant:
    def test_none_returns_principal_tenant(self):
        from backend.app.api.collaboration import _resolve_tenant
        p = _make_principal()
        assert _resolve_tenant(p, None) == "t1"

    def test_empty_string_returns_principal_tenant(self):
        from backend.app.api.collaboration import _resolve_tenant
        p = _make_principal()
        assert _resolve_tenant(p, "") == "t1"

    def test_same_tenant_ok(self):
        from backend.app.api.collaboration import _resolve_tenant
        p = _make_principal()
        assert _resolve_tenant(p, "t1") == "t1"

    def test_non_admin_different_tenant_raises(self):
        from backend.app.api.collaboration import _resolve_tenant
        p = _make_principal(role="user")
        with pytest.raises(Exception) as exc_info:
            _resolve_tenant(p, "other-tenant")
        assert "403" in str(exc_info.value.status_code) or exc_info.value.status_code == 403

    def test_admin_different_tenant_ok(self):
        from backend.app.api.collaboration import _resolve_tenant
        p = _make_principal(role="admin")
        assert _resolve_tenant(p, "other-tenant") == "other-tenant"


class TestGetRoomForPrincipal:
    def test_room_not_found_raises_404(self):
        from backend.app.api.collaboration import _get_room_for_principal
        with patch("backend.app.api.collaboration.collaboration_store") as mock_store:
            mock_store.get_room.return_value = None
            p = _make_principal()
            with pytest.raises(Exception) as exc_info:
                _get_room_for_principal("room-1", p)
            assert exc_info.value.status_code == 404

    def test_cross_tenant_non_admin_raises_404(self):
        from backend.app.api.collaboration import _get_room_for_principal
        room = MagicMock()
        room.tenant_id = "other-tenant"
        with patch("backend.app.api.collaboration.collaboration_store") as mock_store:
            mock_store.get_room.return_value = room
            p = _make_principal(role="user", tenant_id="t1")
            with pytest.raises(Exception) as exc_info:
                _get_room_for_principal("room-1", p)
            assert exc_info.value.status_code == 404

    def test_same_tenant_returns_room(self):
        from backend.app.api.collaboration import _get_room_for_principal
        room = MagicMock()
        room.tenant_id = "t1"
        with patch("backend.app.api.collaboration.collaboration_store") as mock_store:
            mock_store.get_room.return_value = room
            p = _make_principal()
            assert _get_room_for_principal("room-1", p) is room

    def test_admin_cross_tenant_ok(self):
        from backend.app.api.collaboration import _get_room_for_principal
        room = MagicMock()
        room.tenant_id = "other-tenant"
        with patch("backend.app.api.collaboration.collaboration_store") as mock_store:
            mock_store.get_room.return_value = room
            p = _make_principal(role="admin")
            assert _get_room_for_principal("room-1", p) is room


class TestBuildWorkflowSuggestion:
    def test_approval_keywords(self):
        from backend.app.api.collaboration import _build_workflow_suggestion
        result = _build_workflow_suggestion("需要审批这个流程")
        node_ids = [n["id"] for n in result["nodes"]]
        assert "approval" in node_ids

    def test_browser_keywords(self):
        from backend.app.api.collaboration import _build_workflow_suggestion
        result = _build_workflow_suggestion("打开浏览器搜索")
        node_ids = [n["id"] for n in result["nodes"]]
        assert "browser" in node_ids

    def test_collaboration_keywords(self):
        from backend.app.api.collaboration import _build_workflow_suggestion
        result = _build_workflow_suggestion("多智能体协作任务")
        node_ids = [n["id"] for n in result["nodes"]]
        assert "collaboration" in node_ids

    def test_default_branch(self):
        from backend.app.api.collaboration import _build_workflow_suggestion
        result = _build_workflow_suggestion("普通任务处理")
        node_ids = [n["id"] for n in result["nodes"]]
        assert "agent_plan" in node_ids
        assert "output" in node_ids


class TestMemoryContextFromPrincipal:
    def test_creates_context_object(self):
        from backend.app.api.collaboration import _memory_context_from_principal
        p = _make_principal()
        ctx = _memory_context_from_principal(p)
        assert ctx.tenant_id == "t1"
        assert ctx.user_id == "u1"
        assert ctx.agent_id == "agent-1"
        assert ctx.request_id == "req-1"
        assert ctx.trace_id == "trace-1"


class TestCollaborationEndpoints:
    @pytest.fixture
    def client(self):
        from backend.app.api.collaboration import router
        app = _make_test_app(router)
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    def test_create_room(self, client):
        with patch("backend.app.api.collaboration.collaboration_store") as mock_store, \
             patch("backend.app.api.collaboration.message_event_bus") as mock_bus:
            room = MagicMock()
            room.tenant_id = "t1"
            room.room_id = "room-1"
            room.model_dump.return_value = {"room_id": "room-1", "topic": "test"}
            mock_store.create_room.return_value = room
            mock_bus.publish = AsyncMock()
            resp = client.post("/api/v1/collaboration/rooms", json={"topic": "test topic"})
            assert resp.status_code == 200
            assert resp.json()["room_id"] == "room-1"

    def test_list_rooms(self, client):
        with patch("backend.app.api.collaboration.collaboration_store") as mock_store:
            room = MagicMock()
            room.model_dump.return_value = {"room_id": "r1"}
            mock_store.list_rooms.return_value = [room]
            resp = client.get("/api/v1/collaboration/rooms")
            assert resp.status_code == 200
            assert len(resp.json()) == 1

    def test_list_rooms_admin_with_tenant(self, client):
        from backend.app.api.collaboration import router
        from backend.app.dependencies import get_current_principal
        app = _make_test_app(router)
        app.dependency_overrides[get_current_principal] = lambda: _make_principal(role="admin")
        with TestClient(app, raise_server_exceptions=False) as c2:
            with patch("backend.app.api.collaboration.collaboration_store") as mock_store:
                mock_store.list_rooms.return_value = []
                resp = c2.get("/api/v1/collaboration/rooms?tenant_id=other")
                assert resp.status_code == 200

    def test_get_room(self, client):
        with patch("backend.app.api.collaboration.collaboration_store") as mock_store:
            room = MagicMock()
            room.tenant_id = "t1"
            room.model_dump.return_value = {"room_id": "r1"}
            mock_store.get_room.return_value = room
            resp = client.get("/api/v1/collaboration/rooms/r1")
            assert resp.status_code == 200

    def test_get_room_correlation(self, client):
        with patch("backend.app.api.collaboration.collaboration_store") as mock_store:
            room = MagicMock()
            room.tenant_id = "t1"
            room.room_id = "r1"
            room.status = "active"
            room.topic = "test"
            room.messages = []
            room.members = ["m1"]
            room.created_at = "2024-01-01"
            room.updated_at = "2024-01-02"
            mock_store.get_room.return_value = room
            resp = client.get("/api/v1/collaboration/rooms/r1/correlation")
            assert resp.status_code == 200
            data = resp.json()
            assert data["room_id"] == "r1"
            assert "trace_summary" in data

    def test_get_room_correlation_with_messages(self, client):
        with patch("backend.app.api.collaboration.collaboration_store") as mock_store:
            room = MagicMock()
            room.tenant_id = "t1"
            room.room_id = "r1"
            room.status = "closed"
            room.topic = "test"
            msg = MagicMock()
            msg.content = "hello"
            room.messages = [msg]
            room.members = ["m1"]
            room.created_at = "2024-01-01"
            room.updated_at = "2024-01-02"
            mock_store.get_room.return_value = room
            resp = client.get("/api/v1/collaboration/rooms/r1/correlation")
            assert resp.status_code == 200
            assert resp.json()["trace_summary"]["last_event"] == "hello"

    def test_get_room_workflow_suggestion_approval(self, client):
        with patch("backend.app.api.collaboration.collaboration_store") as mock_store:
            room = MagicMock()
            room.tenant_id = "t1"
            room.room_id = "r1"
            room.topic = "审批流程"
            room.messages = []
            mock_store.get_room.return_value = room
            resp = client.get("/api/v1/collaboration/rooms/r1/workflow-suggestion")
            assert resp.status_code == 200
            node_ids = [n["id"] for n in resp.json()["suggested_nodes"]]
            assert "approval" in node_ids

    def test_get_room_workflow_suggestion_browser(self, client):
        with patch("backend.app.api.collaboration.collaboration_store") as mock_store:
            room = MagicMock()
            room.tenant_id = "t1"
            room.room_id = "r1"
            room.topic = "网页浏览"
            room.messages = []
            mock_store.get_room.return_value = room
            resp = client.get("/api/v1/collaboration/rooms/r1/workflow-suggestion")
            assert resp.status_code == 200
            node_ids = [n["id"] for n in resp.json()["suggested_nodes"]]
            assert "browser" in node_ids

    def test_get_room_workflow_suggestion_default(self, client):
        with patch("backend.app.api.collaboration.collaboration_store") as mock_store:
            room = MagicMock()
            room.tenant_id = "t1"
            room.room_id = "r1"
            room.topic = "普通任务"
            room.messages = []
            mock_store.get_room.return_value = room
            resp = client.get("/api/v1/collaboration/rooms/r1/workflow-suggestion")
            assert resp.status_code == 200

    def test_add_member(self, client):
        with patch("backend.app.api.collaboration.collaboration_store") as mock_store, \
             patch("backend.app.api.collaboration.message_event_bus") as mock_bus:
            room = MagicMock()
            room.tenant_id = "t1"
            room.room_id = "r1"
            room.model_dump.return_value = {"room_id": "r1"}
            mock_store.get_room.return_value = room
            mock_store.add_member.return_value = room
            mock_bus.publish = AsyncMock()
            resp = client.post("/api/v1/collaboration/rooms/r1/members", json={"member_id": "m2"})
            assert resp.status_code == 200

    def test_add_member_no_member_id(self, client):
        with patch("backend.app.api.collaboration.collaboration_store") as mock_store:
            room = MagicMock()
            room.tenant_id = "t1"
            mock_store.get_room.return_value = room
            resp = client.post("/api/v1/collaboration/rooms/r1/members", json={})
            assert resp.status_code == 400

    def test_add_member_room_not_found_in_store(self, client):
        with patch("backend.app.api.collaboration.collaboration_store") as mock_store:
            room = MagicMock()
            room.tenant_id = "t1"
            mock_store.get_room.return_value = room
            mock_store.add_member.side_effect = KeyError("not found")
            resp = client.post("/api/v1/collaboration/rooms/r1/members", json={"member_id": "m2"})
            assert resp.status_code == 404

    def test_post_message(self, client):
        with patch("backend.app.api.collaboration.collaboration_store") as mock_store, \
             patch("backend.app.api.collaboration.message_event_bus") as mock_bus:
            room = MagicMock()
            room.tenant_id = "t1"
            room.room_id = "r1"
            room.model_dump.return_value = {"room_id": "r1"}
            msg = MagicMock()
            msg.model_dump.return_value = {"content": "hi"}
            mock_store.get_room.return_value = room
            mock_store.post_message.return_value = msg
            mock_bus.publish = AsyncMock()
            resp = client.post("/api/v1/collaboration/rooms/r1/messages", json={
                "sender_id": "s1", "content": "hi"
            })
            assert resp.status_code == 200

    def test_post_message_room_gone_after_post(self, client):
        with patch("backend.app.api.collaboration.collaboration_store") as mock_store, \
             patch("backend.app.api.collaboration.message_event_bus") as mock_bus:
            room = MagicMock()
            room.tenant_id = "t1"
            msg = MagicMock()
            msg.model_dump.return_value = {"content": "hi"}
            # first call for _get_room_for_principal, second after post returns None
            mock_store.get_room.side_effect = [room, None]
            mock_store.post_message.return_value = msg
            mock_bus.publish = AsyncMock()
            resp = client.post("/api/v1/collaboration/rooms/r1/messages", json={
                "sender_id": "s1", "content": "hi"
            })
            assert resp.status_code == 200

    def test_post_message_store_error(self, client):
        with patch("backend.app.api.collaboration.collaboration_store") as mock_store:
            room = MagicMock()
            room.tenant_id = "t1"
            mock_store.get_room.return_value = room
            mock_store.post_message.side_effect = ValueError("bad")
            resp = client.post("/api/v1/collaboration/rooms/r1/messages", json={
                "sender_id": "s1", "content": "hi"
            })
            assert resp.status_code == 404

    def test_suggest_workflow_from_room(self, client):
        with patch("backend.app.api.collaboration.collaboration_store") as mock_store, \
             patch("backend.app.api.collaboration.message_event_bus") as mock_bus:
            room = MagicMock()
            room.tenant_id = "t1"
            room.room_id = "r1"
            room.topic = "审批任务"
            room.members = ["m1"]
            msg = MagicMock()
            msg.content = "需要审批"
            room.messages = [msg]
            mock_store.get_room.return_value = room
            mock_bus.publish = AsyncMock()
            resp = client.post("/api/v1/collaboration/rooms/r1/workflow-suggestion")
            assert resp.status_code == 200
            assert "suggested_nodes" in resp.json()

    def test_close_room(self, client):
        with patch("backend.app.api.collaboration.collaboration_store") as mock_store, \
             patch("backend.app.api.collaboration.message_event_bus") as mock_bus:
            room = MagicMock()
            room.tenant_id = "t1"
            room.room_id = "r1"
            room.model_dump.return_value = {"room_id": "r1", "status": "closed"}
            mock_store.get_room.return_value = room
            mock_store.close_room.return_value = room
            mock_bus.publish = AsyncMock()
            resp = client.post("/api/v1/collaboration/rooms/r1/close")
            assert resp.status_code == 200
            assert resp.json()["closed"] is True

    def test_close_room_not_found(self, client):
        with patch("backend.app.api.collaboration.collaboration_store") as mock_store:
            room = MagicMock()
            room.tenant_id = "t1"
            mock_store.get_room.return_value = room
            mock_store.close_room.side_effect = KeyError("gone")
            resp = client.post("/api/v1/collaboration/rooms/r1/close")
            assert resp.status_code == 404

    def test_delegate_task_no_capable_agent(self, client):
        from backend.app.core.collaboration.delegation import NoCapableAgentError
        with patch("backend.app.api.collaboration.get_delegator") as mock_get_del:
            delegator = MagicMock()
            delegator.delegate = AsyncMock(side_effect=NoCapableAgentError(["cap1"], []))
            mock_get_del.return_value = delegator
            resp = client.post("/api/v1/collaboration/delegate", json={
                "task": "do something", "required_capabilities": ["x"]
            })
            assert resp.status_code == 422

    def test_delegate_task_value_error(self, client):
        with patch("backend.app.api.collaboration.get_delegator") as mock_get_del:
            delegator = MagicMock()
            delegator.delegate = AsyncMock(side_effect=ValueError("bad isolation"))
            mock_get_del.return_value = delegator
            resp = client.post("/api/v1/collaboration/delegate", json={
                "task": "do something", "isolation": "bad"
            })
            assert resp.status_code == 400

    def test_delegate_task_runtime_error(self, client):
        with patch("backend.app.api.collaboration.get_delegator") as mock_get_del:
            delegator = MagicMock()
            delegator.delegate = AsyncMock(side_effect=RuntimeError("concurrency cap"))
            mock_get_del.return_value = delegator
            resp = client.post("/api/v1/collaboration/delegate", json={"task": "do it"})
            assert resp.status_code == 429

    def test_delegate_task_success(self, client):
        with patch("backend.app.api.collaboration.get_delegator") as mock_get_del:
            delegator = MagicMock()
            result = MagicMock()
            result.model_dump.return_value = {"delegation_id": "d1", "status": "completed"}
            delegator.delegate = AsyncMock(return_value=result)
            mock_get_del.return_value = delegator
            resp = client.post("/api/v1/collaboration/delegate", json={
                "task": "do it",
                "candidates": [{"agent_id": "a1", "capabilities": ["code"]}],
            })
            assert resp.status_code == 200
            assert resp.json()["delegation_id"] == "d1"

    def test_delegate_task_with_room(self, client):
        with patch("backend.app.api.collaboration.get_delegator") as mock_get_del, \
             patch("backend.app.api.collaboration.collaboration_store") as mock_store:
            room = MagicMock()
            room.tenant_id = "t1"
            mock_store.get_room.return_value = room
            delegator = MagicMock()
            result = MagicMock()
            result.model_dump.return_value = {"delegation_id": "d2"}
            delegator.delegate = AsyncMock(return_value=result)
            mock_get_del.return_value = delegator
            resp = client.post("/api/v1/collaboration/delegate", json={
                "task": "do it", "room_id": "r1"
            })
            assert resp.status_code == 200

    def test_list_delegations(self, client):
        with patch("backend.app.api.collaboration.get_delegator") as mock_get_del:
            delegator = MagicMock()
            item = MagicMock()
            item.model_dump.return_value = {"id": "d1"}
            delegator.list_delegations.return_value = [item]
            mock_get_del.return_value = delegator
            resp = client.get("/api/v1/collaboration/delegations")
            assert resp.status_code == 200
            assert len(resp.json()) == 1

    def test_list_delegations_admin(self, client):
        from backend.app.api.collaboration import router
        from backend.app.dependencies import get_current_principal
        app = _make_test_app(router)
        app.dependency_overrides[get_current_principal] = lambda: _make_principal(role="admin")
        with TestClient(app, raise_server_exceptions=False) as c2:
            with patch("backend.app.api.collaboration.get_delegator") as mock_get_del:
                delegator = MagicMock()
                delegator.list_delegations.return_value = []
                mock_get_del.return_value = delegator
                resp = c2.get("/api/v1/collaboration/delegations?tenant_id=x")
                assert resp.status_code == 200

    def test_get_delegation_found(self, client):
        with patch("backend.app.api.collaboration.get_delegator") as mock_get_del:
            delegator = MagicMock()
            result = MagicMock()
            result.tenant_id = "t1"
            result.model_dump.return_value = {"id": "d1"}
            delegator.get_delegation.return_value = result
            mock_get_del.return_value = delegator
            resp = client.get("/api/v1/collaboration/delegations/d1")
            assert resp.status_code == 200

    def test_get_delegation_not_found(self, client):
        with patch("backend.app.api.collaboration.get_delegator") as mock_get_del:
            delegator = MagicMock()
            delegator.get_delegation.return_value = None
            mock_get_del.return_value = delegator
            resp = client.get("/api/v1/collaboration/delegations/d1")
            assert resp.status_code == 404

    def test_get_delegation_cross_tenant(self, client):
        with patch("backend.app.api.collaboration.get_delegator") as mock_get_del:
            delegator = MagicMock()
            result = MagicMock()
            result.tenant_id = "other"
            delegator.get_delegation.return_value = result
            mock_get_del.return_value = delegator
            resp = client.get("/api/v1/collaboration/delegations/d1")
            assert resp.status_code == 404

    def test_sync_room_memory_no_store_attr(self, client):
        from backend.app.api.collaboration import router
        from backend.app.dependencies import get_current_principal, get_memory
        app = _make_test_app(router)
        app.dependency_overrides[get_memory] = lambda: object()  # no .store attr
        with TestClient(app, raise_server_exceptions=False) as c2:
            with patch("backend.app.api.collaboration.collaboration_store") as mock_store:
                room = MagicMock()
                room.tenant_id = "t1"
                room.room_id = "r1"
                mock_store.get_room.return_value = room
                resp = c2.post("/api/v1/collaboration/rooms/r1/memory-sync")
                assert resp.status_code == 400

    def test_sync_room_memory_success(self, client):
        from backend.app.api.collaboration import router
        from backend.app.dependencies import get_current_principal, get_memory
        memory_mock = MagicMock()
        memory_mock.store = AsyncMock(return_value="mem-1")
        memory_mock.route_shared_memory = MagicMock()
        app = _make_test_app(router)
        app.dependency_overrides[get_memory] = lambda: memory_mock
        with TestClient(app, raise_server_exceptions=False) as c2:
            with patch("backend.app.api.collaboration.collaboration_store") as mock_store:
                room = MagicMock()
                room.tenant_id = "t1"
                room.room_id = "r1"
                room.topic = "test"
                msg = MagicMock()
                msg.content = "hello"
                msg.metadata = {"agent_id": "a1", "department_id": "dept1"}
                msg.message_id = "msg-1"
                msg.sender_id = "s1"
                msg.sender_type = "agent"
                room.messages = [msg]
                room.memory_refs = {"mem-1"}
                room.agent_memory_refs = {"a1": {"mem-1"}}
                room.department_memory_refs = {"dept1": {"mem-1"}}
                mock_store.get_room.return_value = room
                mock_store.add_memory_ref = MagicMock()
                mock_store.add_agent_memory_ref = MagicMock()
                mock_store.add_department_memory_ref = MagicMock()
                resp = c2.post("/api/v1/collaboration/rooms/r1/memory-sync")
                assert resp.status_code == 200
                data = resp.json()
                assert data["synced_count"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# BROWSER MODULE
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsUrlAllowed:
    def test_valid_https(self):
        from backend.app.api.browser import _is_url_allowed
        assert _is_url_allowed("https://example.com/page") is True

    def test_valid_http(self):
        from backend.app.api.browser import _is_url_allowed
        assert _is_url_allowed("http://example.com") is True

    def test_file_protocol_blocked(self):
        from backend.app.api.browser import _is_url_allowed
        assert _is_url_allowed("file:///etc/passwd") is False

    def test_localhost_blocked(self):
        from backend.app.api.browser import _is_url_allowed
        assert _is_url_allowed("http://localhost/admin") is False

    def test_127_blocked(self):
        from backend.app.api.browser import _is_url_allowed
        assert _is_url_allowed("http://127.0.0.1/admin") is False

    def test_ipv6_loopback_blocked(self):
        from backend.app.api.browser import _is_url_allowed
        assert _is_url_allowed("http://[::1]/admin") is False

    def test_metadata_endpoint_blocked(self):
        from backend.app.api.browser import _is_url_allowed
        assert _is_url_allowed("http://169.254.169.254/latest/meta-data/") is False

    def test_private_ip_blocked(self):
        from backend.app.api.browser import _is_url_allowed
        assert _is_url_allowed("http://192.168.1.1/") is False
        assert _is_url_allowed("http://10.0.0.1/") is False

    def test_0000_blocked(self):
        from backend.app.api.browser import _is_url_allowed
        assert _is_url_allowed("http://0.0.0.0/") is False


class TestSanitizeScreenshotPath:
    def test_relative_path_ok(self):
        from backend.app.api.browser import _sanitize_screenshot_path
        result = _sanitize_screenshot_path("screenshots/shot.png")
        assert "shot.png" in result

    def test_traversal_blocked(self):
        from backend.app.api.browser import _sanitize_screenshot_path
        with pytest.raises(Exception) as exc_info:
            _sanitize_screenshot_path("../../etc/passwd")
        assert exc_info.value.status_code == 400

    def test_windows_drive_blocked(self):
        from backend.app.api.browser import _sanitize_screenshot_path
        with pytest.raises(Exception) as exc_info:
            _sanitize_screenshot_path("C:/Windows/system32/cmd.exe")
        assert exc_info.value.status_code == 400

    def test_unc_path_blocked(self):
        from backend.app.api.browser import _sanitize_screenshot_path
        with pytest.raises(Exception) as exc_info:
            _sanitize_screenshot_path("\\\\server\\share\\file.txt")
        assert exc_info.value.status_code == 400

    def test_tmp_path_allowed(self):
        """On Linux /tmp is allowed; on Windows normpath converts to \tmp which fails the check."""
        import sys
        from backend.app.api.browser import _sanitize_screenshot_path
        if sys.platform == "win32":
            # On Windows, /tmp normalizes to \tmp which doesn't match "/tmp" prefix
            with pytest.raises(Exception):
                _sanitize_screenshot_path("/tmp/screenshot.png")
        else:
            result = _sanitize_screenshot_path("/tmp/screenshot.png")
            assert "screenshot.png" in result

    def test_absolute_non_tmp_blocked(self):
        from backend.app.api.browser import _sanitize_screenshot_path
        with pytest.raises(Exception) as exc_info:
            _sanitize_screenshot_path("/etc/passwd")
        assert exc_info.value.status_code == 400

    def test_whitespace_stripped(self):
        from backend.app.api.browser import _sanitize_screenshot_path
        with pytest.raises(Exception):
            _sanitize_screenshot_path("  C:/Windows/test.png")


class TestCanAccessSession:
    def test_admin_always_access(self):
        from backend.app.api.browser import _can_access_session
        session = MagicMock()
        session.tenant_id = "other"
        session.user_id = "other-user"
        p = _make_principal(role="admin")
        assert _can_access_session(session, p) is True

    def test_same_tenant_user_access(self):
        from backend.app.api.browser import _can_access_session
        session = MagicMock()
        session.tenant_id = "t1"
        session.user_id = "u1"
        p = _make_principal()
        assert _can_access_session(session, p) is True

    def test_different_tenant_denied(self):
        from backend.app.api.browser import _can_access_session
        session = MagicMock()
        session.tenant_id = "other"
        session.user_id = "u1"
        p = _make_principal()
        assert _can_access_session(session, p) is False

    def test_different_user_denied(self):
        from backend.app.api.browser import _can_access_session
        session = MagicMock()
        session.tenant_id = "t1"
        session.user_id = "other-user"
        p = _make_principal()
        assert _can_access_session(session, p) is False


class TestBrowserHelpers:
    def test_action_response(self):
        from backend.app.api.browser import _action_response
        result = MagicMock()
        result.action = "goto"
        result.ok = True
        result.detail = "navigated"
        result.data = {"url": "http://x.com"}
        resp = _action_response(result)
        assert resp.action == "goto"
        assert resp.ok is True

    def test_session_response(self):
        from backend.app.api.browser import _session_response
        session = MagicMock()
        session.session_id = "s1"
        session.trace_id = "t1"
        session.run_id = "r1"
        session.tenant_id = "ten1"
        session.user_id = "u1"
        session.current_url = "http://x.com"
        session.active = True
        action = MagicMock()
        action.action = "goto"
        action.ok = True
        action.detail = ""
        action.data = {}
        session.actions = [action]
        resp = _session_response(session)
        assert resp.session_id == "s1"
        assert len(resp.actions) == 1


class TestBrowserEndpoints:
    @pytest.fixture
    def client(self):
        from backend.app.api.browser import router
        app = _make_test_app(router)
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    def _mock_session(self, **kwargs):
        s = MagicMock()
        s.session_id = kwargs.get("session_id", "s1")
        s.trace_id = kwargs.get("trace_id", "tr1")
        s.run_id = kwargs.get("run_id", "r1")
        s.tenant_id = kwargs.get("tenant_id", "t1")
        s.user_id = kwargs.get("user_id", "u1")
        s.current_url = kwargs.get("current_url", "http://x.com")
        s.active = kwargs.get("active", True)
        s.actions = kwargs.get("actions", [])
        return s

    def test_list_sessions(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.list_sessions.return_value = [self._mock_session()]
            resp = client.get("/api/v1/browser/sessions")
            assert resp.status_code == 200
            assert len(resp.json()) == 1

    def test_list_sessions_filters_non_admin(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.list_sessions.return_value = [
                self._mock_session(user_id="u1"),
                self._mock_session(session_id="s2", user_id="other"),
            ]
            resp = client.get("/api/v1/browser/sessions")
            assert resp.status_code == 200
            assert len(resp.json()) == 1

    def test_get_session_found(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.get_session.return_value = self._mock_session()
            resp = client.get("/api/v1/browser/sessions/s1")
            assert resp.status_code == 200

    def test_get_session_not_found(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.get_session.return_value = None
            resp = client.get("/api/v1/browser/sessions/s1")
            assert resp.status_code == 404

    def test_get_session_access_denied(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.get_session.return_value = self._mock_session(user_id="other")
            resp = client.get("/api/v1/browser/sessions/s1")
            assert resp.status_code == 403

    def test_session_correlation_active(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.get_session.return_value = self._mock_session(active=True)
            resp = client.get("/api/v1/browser/sessions/s1/correlation")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "active"
            assert "recovery" in data

    def test_session_correlation_closed(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            s = self._mock_session(active=False, trace_id=None, run_id=None)
            action = MagicMock()
            action.action = "click"
            s.actions = [action]
            mock_ba.get_session.return_value = s
            resp = client.get("/api/v1/browser/sessions/s1/correlation")
            assert resp.status_code == 200
            assert resp.json()["status"] == "closed"

    def test_session_correlation_not_found(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.get_session.return_value = None
            resp = client.get("/api/v1/browser/sessions/s1/correlation")
            assert resp.status_code == 404

    def test_create_session_success(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.create_session = AsyncMock(return_value=self._mock_session())
            resp = client.post("/api/v1/browser/sessions", json={"tenant_id": "t1"})
            assert resp.status_code == 200

    def test_create_session_tenant_mismatch(self, client):
        resp = client.post("/api/v1/browser/sessions", json={"tenant_id": "other"})
        assert resp.status_code == 403

    def test_create_session_browser_unavailable(self, client):
        from backend.app.services.browser.automation import BrowserUnavailableError
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.create_session = AsyncMock(side_effect=BrowserUnavailableError("no browser"))
            resp = client.post("/api/v1/browser/sessions", json={"tenant_id": "t1"})
            assert resp.status_code == 503

    def test_goto_success(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.get_session.return_value = self._mock_session()
            action_result = MagicMock()
            action_result.action = "goto"
            action_result.ok = True
            action_result.detail = ""
            action_result.data = {}
            mock_ba.goto = AsyncMock(return_value=action_result)
            resp = client.post("/api/v1/browser/sessions/s1/goto", json={"url": "https://example.com"})
            assert resp.status_code == 200

    def test_goto_no_url(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.get_session.return_value = self._mock_session()
            resp = client.post("/api/v1/browser/sessions/s1/goto", json={})
            assert resp.status_code == 400

    def test_goto_disallowed_url(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.get_session.return_value = self._mock_session()
            resp = client.post("/api/v1/browser/sessions/s1/goto", json={"url": "http://localhost/admin"})
            assert resp.status_code == 400

    def test_goto_session_not_found(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.get_session.return_value = None
            resp = client.post("/api/v1/browser/sessions/s1/goto", json={"url": "https://x.com"})
            assert resp.status_code == 404

    def test_click_success(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.get_session.return_value = self._mock_session()
            r = MagicMock(); r.action = "click"; r.ok = True; r.detail = ""; r.data = {}
            mock_ba.click = AsyncMock(return_value=r)
            resp = client.post("/api/v1/browser/sessions/s1/click", json={"selector": "#btn"})
            assert resp.status_code == 200

    def test_click_no_selector(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.get_session.return_value = self._mock_session()
            resp = client.post("/api/v1/browser/sessions/s1/click", json={})
            assert resp.status_code == 400

    def test_fill_success(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.get_session.return_value = self._mock_session()
            r = MagicMock(); r.action = "fill"; r.ok = True; r.detail = ""; r.data = {}
            mock_ba.fill = AsyncMock(return_value=r)
            resp = client.post("/api/v1/browser/sessions/s1/fill", json={"selector": "#input", "value": "test"})
            assert resp.status_code == 200

    def test_fill_missing_value(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.get_session.return_value = self._mock_session()
            resp = client.post("/api/v1/browser/sessions/s1/fill", json={"selector": "#input"})
            assert resp.status_code == 400

    def test_extract_text_success(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.get_session.return_value = self._mock_session()
            r = MagicMock(); r.action = "extract_text"; r.ok = True; r.detail = ""; r.data = {}
            mock_ba.extract_text = AsyncMock(return_value=r)
            resp = client.post("/api/v1/browser/sessions/s1/extract-text", json={"selector": "p"})
            assert resp.status_code == 200

    def test_extract_text_uses_text_field(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.get_session.return_value = self._mock_session()
            r = MagicMock(); r.action = "extract_text"; r.ok = True; r.detail = ""; r.data = {}
            mock_ba.extract_text = AsyncMock(return_value=r)
            resp = client.post("/api/v1/browser/sessions/s1/extract-text", json={"text": "h1"})
            assert resp.status_code == 200

    def test_extract_text_no_selector(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.get_session.return_value = self._mock_session()
            resp = client.post("/api/v1/browser/sessions/s1/extract-text", json={})
            assert resp.status_code == 400

    def test_wait_for_success(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.get_session.return_value = self._mock_session()
            r = MagicMock(); r.action = "wait_for"; r.ok = True; r.detail = ""; r.data = {}
            mock_ba.wait_for = AsyncMock(return_value=r)
            resp = client.post("/api/v1/browser/sessions/s1/wait-for", json={"selector": ".loaded"})
            assert resp.status_code == 200

    def test_wait_for_no_selector(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.get_session.return_value = self._mock_session()
            resp = client.post("/api/v1/browser/sessions/s1/wait-for", json={})
            assert resp.status_code == 400

    def test_screenshot_success(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba, \
             patch("backend.app.api.browser._sanitize_screenshot_path", return_value="shot.png"):
            mock_ba.get_session.return_value = self._mock_session()
            r = MagicMock(); r.action = "screenshot"; r.ok = True; r.detail = ""; r.data = {}
            mock_ba.screenshot = AsyncMock(return_value=r)
            resp = client.post("/api/v1/browser/sessions/s1/screenshot", json={"path": "shot.png"})
            assert resp.status_code == 200

    def test_screenshot_no_path(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.get_session.return_value = self._mock_session()
            resp = client.post("/api/v1/browser/sessions/s1/screenshot", json={})
            assert resp.status_code == 400

    def test_close_session(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.get_session.return_value = self._mock_session()
            mock_ba.close = AsyncMock(return_value=True)
            resp = client.post("/api/v1/browser/sessions/s1/close")
            assert resp.status_code == 200
            assert resp.json()["closed"] is True

    def test_close_session_none(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.get_session.return_value = None
            mock_ba.close = AsyncMock(return_value=False)
            resp = client.post("/api/v1/browser/sessions/s1/close")
            assert resp.status_code == 200

    def test_delete_session(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.get_session.return_value = self._mock_session()
            mock_ba.close = AsyncMock(return_value=True)
            resp = client.delete("/api/v1/browser/sessions/s1")
            assert resp.status_code == 200
            assert resp.json()["deleted"] is True

    def test_delete_session_access_denied(self, client):
        with patch("backend.app.api.browser.browser_automation") as mock_ba:
            mock_ba.get_session.return_value = self._mock_session(user_id="other")
            resp = client.delete("/api/v1/browser/sessions/s1")
            assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# FEEDBACK MODULE
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeedbackStore:
    def test_get_feedback_store_singleton(self):
        import backend.app.api.feedback as fb_mod
        fb_mod._feedback_store = None
        with patch("backend.app.api.feedback.FeedbackStorePostgres") as MockStore:
            instance = MockStore.return_value
            s1 = fb_mod.get_feedback_store()
            s2 = fb_mod.get_feedback_store()
            assert s1 is s2
            MockStore.assert_called_once()
        fb_mod._feedback_store = None


def _mock_feedback_obj(**kwargs):
    fb = MagicMock()
    fb.id = kwargs.get("id", "fb-1")
    fb.user_id = kwargs.get("user_id", "u1")
    fb.feedback_type = kwargs.get("feedback_type", "bug")
    fb.title = kwargs.get("title", "Test Bug")
    fb.description = kwargs.get("description", "desc")
    fb.severity = kwargs.get("severity", "high")
    fb.status = kwargs.get("status", "new")
    fb.sentiment = kwargs.get("sentiment", "negative")
    fb.sentiment_score = kwargs.get("sentiment_score", 0.8)
    fb.priority_score = kwargs.get("priority_score", 0.9)
    fb.category = kwargs.get("category", "ui")
    fb.tags = kwargs.get("tags", ["bug"])
    fb.created_at = kwargs.get("created_at", datetime(2024, 1, 1, tzinfo=UTC))
    fb.updated_at = kwargs.get("updated_at", datetime(2024, 1, 1, tzinfo=UTC))
    fb.resolved_at = kwargs.get("resolved_at", None)
    return fb


class TestFeedbackEndpoints:
    @pytest.fixture
    def client(self):
        from backend.app.api.feedback import router
        app = _make_test_app(router)
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    def test_create_feedback_success(self, client):
        import backend.app.api.feedback as fb_mod
        fb_mod._feedback_store = None
        mock_store = MagicMock()
        mock_store.create_feedback = AsyncMock(return_value=_mock_feedback_obj())
        mock_store.update_feedback = AsyncMock(return_value=_mock_feedback_obj())
        mock_store.create_analysis = AsyncMock()
        mock_store.get_feedback_by_id = AsyncMock(return_value=_mock_feedback_obj())
        with patch("backend.app.api.feedback.get_feedback_store", return_value=mock_store), \
             patch("backend.app.api.feedback.feedback_analyzer") as mock_analyzer:
            mock_analyzer.analyze_feedback = AsyncMock(return_value={
                "sentiment_type": "negative",
                "sentiment_score": 0.8,
                "category": "ui",
                "tags": ["bug"],
                "priority_score": 0.9,
                "urgency_score": 0.7,
                "impact_score": 0.6,
                "keywords": ["crash"],
                "entities": {},
            })
            resp = client.post("/api/v1/feedback/", json={
                "feedback_type": "bug",
                "title": "Crash on login",
                "description": "App crashes when clicking login",
                "severity": "high",
            })
            assert resp.status_code == 201
            assert resp.json()["id"] == "fb-1"
        fb_mod._feedback_store = None

    def test_create_feedback_invalid_type(self, client):
        resp = client.post("/api/v1/feedback/", json={
            "feedback_type": "invalid_type",
            "title": "Test",
            "description": "desc",
            "severity": "high",
        })
        assert resp.status_code == 400

    def test_create_feedback_invalid_severity(self, client):
        resp = client.post("/api/v1/feedback/", json={
            "feedback_type": "bug",
            "title": "Test",
            "description": "desc",
            "severity": "extreme",
        })
        assert resp.status_code == 400

    def test_create_feedback_analysis_failure_still_succeeds(self, client):
        import backend.app.api.feedback as fb_mod
        fb_mod._feedback_store = None
        mock_store = MagicMock()
        mock_store.create_feedback = AsyncMock(return_value=_mock_feedback_obj())
        mock_store.get_feedback_by_id = AsyncMock(return_value=_mock_feedback_obj())
        with patch("backend.app.api.feedback.get_feedback_store", return_value=mock_store), \
             patch("backend.app.api.feedback.feedback_analyzer") as mock_analyzer:
            mock_analyzer.analyze_feedback = AsyncMock(side_effect=Exception("LLM error"))
            resp = client.post("/api/v1/feedback/", json={
                "feedback_type": "bug",
                "title": "Test",
                "description": "desc",
                "severity": "high",
            })
            assert resp.status_code == 201
        fb_mod._feedback_store = None

    def test_create_feedback_store_error(self, client):
        import backend.app.api.feedback as fb_mod
        fb_mod._feedback_store = None
        mock_store = MagicMock()
        mock_store.create_feedback = AsyncMock(side_effect=Exception("DB error"))
        with patch("backend.app.api.feedback.get_feedback_store", return_value=mock_store):
            resp = client.post("/api/v1/feedback/", json={
                "feedback_type": "bug",
                "title": "Test",
                "description": "desc",
                "severity": "high",
            })
            assert resp.status_code == 500
        fb_mod._feedback_store = None

    def test_get_feedback_found(self, client):
        mock_store = MagicMock()
        mock_store.get_feedback_by_id = AsyncMock(return_value=_mock_feedback_obj())
        with patch("backend.app.api.feedback.get_feedback_store", return_value=mock_store):
            resp = client.get("/api/v1/feedback/fb-1")
            assert resp.status_code == 200
            assert resp.json()["id"] == "fb-1"

    def test_get_feedback_not_found(self, client):
        mock_store = MagicMock()
        mock_store.get_feedback_by_id = AsyncMock(return_value=None)
        with patch("backend.app.api.feedback.get_feedback_store", return_value=mock_store):
            resp = client.get("/api/v1/feedback/fb-1")
            assert resp.status_code == 404

    def test_get_feedback_access_denied(self, client):
        mock_store = MagicMock()
        mock_store.get_feedback_by_id = AsyncMock(return_value=_mock_feedback_obj(user_id="other-user"))
        with patch("backend.app.api.feedback.get_feedback_store", return_value=mock_store):
            resp = client.get("/api/v1/feedback/fb-1")
            assert resp.status_code == 403

    def test_get_feedback_admin_access(self, client):
        from backend.app.api.feedback import router
        from backend.app.dependencies import get_current_principal
        app = _make_test_app(router)
        app.dependency_overrides[get_current_principal] = lambda: _make_principal(role="admin")
        mock_store = MagicMock()
        mock_store.get_feedback_by_id = AsyncMock(return_value=_mock_feedback_obj(user_id="other"))
        with TestClient(app, raise_server_exceptions=False) as c2:
            with patch("backend.app.api.feedback.get_feedback_store", return_value=mock_store):
                resp = c2.get("/api/v1/feedback/fb-1")
                assert resp.status_code == 200

    def test_list_feedback(self, client):
        mock_store = MagicMock()
        mock_store.list_feedback = AsyncMock(return_value=[_mock_feedback_obj()])
        mock_store.count_feedback = AsyncMock(return_value=1)
        with patch("backend.app.api.feedback.get_feedback_store", return_value=mock_store):
            resp = client.get("/api/v1/feedback/")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 1
            assert len(data["items"]) == 1

    def test_list_feedback_with_filters(self, client):
        mock_store = MagicMock()
        mock_store.list_feedback = AsyncMock(return_value=[])
        mock_store.count_feedback = AsyncMock(return_value=0)
        with patch("backend.app.api.feedback.get_feedback_store", return_value=mock_store):
            resp = client.get("/api/v1/feedback/?feedback_type=bug&status=new&severity=high&skip=0&limit=10")
            assert resp.status_code == 200

    def test_get_feedback_analysis_found(self, client):
        mock_store = MagicMock()
        analysis = MagicMock()
        analysis.feedback_id = "fb-1"
        analysis.sentiment_type = "negative"
        analysis.sentiment_score = 0.8
        analysis.category = "ui"
        analysis.subcategory = "button"
        analysis.tags = ["crash"]
        analysis.priority_score = 0.9
        analysis.urgency_score = 0.7
        analysis.impact_score = 0.6
        analysis.keywords = ["crash"]
        analysis.entities = {"component": "login"}
        mock_store.get_analysis_by_feedback_id = AsyncMock(return_value=analysis)
        with patch("backend.app.api.feedback.get_feedback_store", return_value=mock_store):
            resp = client.get("/api/v1/feedback/fb-1/analysis")
            assert resp.status_code == 200
            assert resp.json()["feedback_id"] == "fb-1"

    def test_get_feedback_analysis_not_found(self, client):
        mock_store = MagicMock()
        mock_store.get_analysis_by_feedback_id = AsyncMock(return_value=None)
        with patch("backend.app.api.feedback.get_feedback_store", return_value=mock_store):
            resp = client.get("/api/v1/feedback/fb-1/analysis")
            assert resp.status_code == 404

    def test_update_feedback_status(self, client):
        mock_store = MagicMock()
        fb = _mock_feedback_obj()
        updated_fb = _mock_feedback_obj(status="resolved", resolved_at=datetime(2024, 1, 2, tzinfo=UTC))
        mock_store.get_feedback_by_id = AsyncMock(return_value=fb)
        mock_store.update_feedback = AsyncMock(return_value=updated_fb)
        with patch("backend.app.api.feedback.get_feedback_store", return_value=mock_store):
            resp = client.patch("/api/v1/feedback/fb-1?status=resolved")
            assert resp.status_code == 200

    def test_update_feedback_invalid_status(self, client):
        resp = client.patch("/api/v1/feedback/fb-1?status=invalid_status")
        assert resp.status_code == 400

    def test_update_feedback_not_found(self, client):
        mock_store = MagicMock()
        mock_store.get_feedback_by_id = AsyncMock(return_value=None)
        with patch("backend.app.api.feedback.get_feedback_store", return_value=mock_store):
            resp = client.patch("/api/v1/feedback/fb-1?status=resolved")
            assert resp.status_code == 404

    def test_update_feedback_access_denied(self, client):
        mock_store = MagicMock()
        mock_store.get_feedback_by_id = AsyncMock(return_value=_mock_feedback_obj(user_id="other"))
        with patch("backend.app.api.feedback.get_feedback_store", return_value=mock_store):
            resp = client.patch("/api/v1/feedback/fb-1?status=resolved")
            assert resp.status_code == 403

    def test_get_feedback_stats(self, client):
        mock_store = MagicMock()
        mock_store.count_feedback = AsyncMock(return_value=5)
        with patch("backend.app.api.feedback.get_feedback_store", return_value=mock_store):
            resp = client.get("/api/v1/feedback/stats/summary")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 5
            assert "by_status" in data
            assert "by_severity" in data


# ═══════════════════════════════════════════════════════════════════════════════
# FILES_V2 MODULE
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateAndResolvePath:
    def test_empty_path_raises(self):
        from backend.app.api.files_v2 import _validate_and_resolve_path
        with pytest.raises(ValueError, match="cannot be empty"):
            _validate_and_resolve_path("", "u1")

    def test_valid_path(self):
        from backend.app.api.files_v2 import _validate_and_resolve_path
        with patch("backend.app.api.files_v2._path_mapper") as mock_mapper:
            from pathlib import Path
            mock_mapper.map_virtual_to_real.return_value = Path("/workspace/test.txt")
            result = _validate_and_resolve_path("test.txt", "u1")
            assert result == Path("/workspace/test.txt")

    def test_permission_error_propagates(self):
        from backend.app.api.files_v2 import _validate_and_resolve_path
        with patch("backend.app.api.files_v2._path_mapper") as mock_mapper:
            mock_mapper.map_virtual_to_real.side_effect = PermissionError("denied")
            with pytest.raises(PermissionError):
                _validate_and_resolve_path("secret.txt", "u1")

    def test_value_error_propagates(self):
        from backend.app.api.files_v2 import _validate_and_resolve_path
        with patch("backend.app.api.files_v2._path_mapper") as mock_mapper:
            mock_mapper.map_virtual_to_real.side_effect = ValueError("invalid")
            with pytest.raises(ValueError):
                _validate_and_resolve_path("../etc/passwd", "u1")


class TestFilesEndpoints:
    @pytest.fixture
    def client(self):
        from backend.app.api.files_v2 import router
        app = _make_test_app(router)
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    def test_process_file_success(self, client):
        with patch("backend.app.api.files_v2._validate_and_resolve_path") as mock_vrp, \
             patch("backend.app.api.files_v2._document_processor") as mock_dp:
            from pathlib import Path
            mock_vrp.return_value = Path("/workspace/doc.pdf")
            mock_dp.process = AsyncMock(return_value={"text": "content"})
            resp = client.post("/api/v1/files/process", json={
                "file_path": "doc.pdf", "operation": "extract_text"
            })
            assert resp.status_code == 200
            assert resp.json()["text"] == "content"

    def test_process_file_missing_params(self, client):
        resp = client.post("/api/v1/files/process", json={"file_path": "doc.pdf"})
        assert resp.status_code == 400

    def test_process_file_access_denied(self, client):
        with patch("backend.app.api.files_v2._validate_and_resolve_path") as mock_vrp:
            mock_vrp.side_effect = PermissionError("denied")
            resp = client.post("/api/v1/files/process", json={
                "file_path": "secret.pdf", "operation": "read"
            })
            assert resp.status_code == 403

    def test_process_file_internal_error(self, client):
        with patch("backend.app.api.files_v2._validate_and_resolve_path") as mock_vrp, \
             patch("backend.app.api.files_v2._document_processor") as mock_dp:
            from pathlib import Path
            mock_vrp.return_value = Path("/workspace/doc.pdf")
            mock_dp.process = AsyncMock(side_effect=RuntimeError("unexpected"))
            resp = client.post("/api/v1/files/process", json={
                "file_path": "doc.pdf", "operation": "extract_text"
            })
            assert resp.status_code == 500

    def test_process_image_success(self, client):
        with patch("backend.app.api.files_v2._validate_and_resolve_path") as mock_vrp, \
             patch("backend.app.api.files_v2._image_processor") as mock_ip:
            from pathlib import Path
            mock_vrp.return_value = Path("/workspace/img.png")
            mock_ip.process = AsyncMock(return_value={"width": 100})
            resp = client.post("/api/v1/files/image/process", json={
                "image_path": "img.png", "operation": "resize"
            })
            assert resp.status_code == 200

    def test_process_image_missing_params(self, client):
        resp = client.post("/api/v1/files/image/process", json={"image_path": "img.png"})
        assert resp.status_code == 400

    def test_process_image_access_denied(self, client):
        with patch("backend.app.api.files_v2._validate_and_resolve_path") as mock_vrp:
            mock_vrp.side_effect = ValueError("invalid path")
            resp = client.post("/api/v1/files/image/process", json={
                "image_path": "../../etc/passwd", "operation": "read"
            })
            assert resp.status_code == 403

    def test_process_image_internal_error(self, client):
        with patch("backend.app.api.files_v2._validate_and_resolve_path") as mock_vrp, \
             patch("backend.app.api.files_v2._image_processor") as mock_ip:
            from pathlib import Path
            mock_vrp.return_value = Path("/workspace/img.png")
            mock_ip.process = AsyncMock(side_effect=RuntimeError("fail"))
            resp = client.post("/api/v1/files/image/process", json={
                "image_path": "img.png", "operation": "resize"
            })
            assert resp.status_code == 500

    def test_convert_file_success(self, client):
        with patch("backend.app.api.files_v2._validate_and_resolve_path") as mock_vrp, \
             patch("backend.app.api.files_v2._file_converter") as mock_fc:
            from pathlib import Path
            mock_vrp.return_value = Path("/workspace/doc.docx")
            mock_fc.convert = AsyncMock(return_value={"output": "doc.pdf"})
            resp = client.post("/api/v1/files/convert", json={
                "input_path": "doc.docx", "output_format": "pdf"
            })
            assert resp.status_code == 200

    def test_convert_file_missing_params(self, client):
        resp = client.post("/api/v1/files/convert", json={"input_path": "doc.docx"})
        assert resp.status_code == 400

    def test_convert_file_access_denied(self, client):
        with patch("backend.app.api.files_v2._validate_and_resolve_path") as mock_vrp:
            mock_vrp.side_effect = PermissionError("no")
            resp = client.post("/api/v1/files/convert", json={
                "input_path": "secret.docx", "output_format": "pdf"
            })
            assert resp.status_code == 403

    def test_convert_file_internal_error(self, client):
        with patch("backend.app.api.files_v2._validate_and_resolve_path") as mock_vrp, \
             patch("backend.app.api.files_v2._file_converter") as mock_fc:
            from pathlib import Path
            mock_vrp.return_value = Path("/workspace/doc.docx")
            mock_fc.convert = AsyncMock(side_effect=RuntimeError("fail"))
            resp = client.post("/api/v1/files/convert", json={
                "input_path": "doc.docx", "output_format": "pdf"
            })
            assert resp.status_code == 500

    def test_get_image_info_success(self, client):
        with patch("backend.app.api.files_v2._validate_and_resolve_path") as mock_vrp, \
             patch("backend.app.api.files_v2._image_processor") as mock_ip:
            from pathlib import Path
            mock_vrp.return_value = Path("/workspace/img.png")
            mock_ip.process = AsyncMock(return_value={"width": 800, "height": 600})
            resp = client.get("/api/v1/files/image/info?image_path=img.png")
            assert resp.status_code == 200

    def test_get_image_info_access_denied(self, client):
        with patch("backend.app.api.files_v2._validate_and_resolve_path") as mock_vrp:
            mock_vrp.side_effect = PermissionError("no")
            resp = client.get("/api/v1/files/image/info?image_path=secret.png")
            assert resp.status_code == 403

    def test_get_image_info_internal_error(self, client):
        with patch("backend.app.api.files_v2._validate_and_resolve_path") as mock_vrp, \
             patch("backend.app.api.files_v2._image_processor") as mock_ip:
            from pathlib import Path
            mock_vrp.return_value = Path("/workspace/img.png")
            mock_ip.process = AsyncMock(side_effect=RuntimeError("fail"))
            resp = client.get("/api/v1/files/image/info?image_path=img.png")
            assert resp.status_code == 500

    def test_batch_process_success(self, client):
        with patch("backend.app.api.files_v2._validate_and_resolve_path") as mock_vrp, \
             patch("backend.app.api.files_v2._document_processor") as mock_dp:
            from pathlib import Path
            mock_vrp.return_value = Path("/workspace/f.txt")
            mock_dp.process = AsyncMock(return_value={"ok": True})
            resp = client.post("/api/v1/files/batch-process", json={
                "files": [{"path": "f1.txt"}, {"path": "f2.txt"}],
                "operation": "extract",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 2
            assert data["processed"] == 2
            assert data["failed"] == 0

    def test_batch_process_missing_params(self, client):
        resp = client.post("/api/v1/files/batch-process", json={"files": []})
        assert resp.status_code == 400

    def test_batch_process_partial_failure(self, client):
        with patch("backend.app.api.files_v2._validate_and_resolve_path") as mock_vrp, \
             patch("backend.app.api.files_v2._document_processor") as mock_dp:
            from pathlib import Path
            mock_vrp.side_effect = [Path("/workspace/f1.txt"), PermissionError("denied")]
            mock_dp.process = AsyncMock(return_value={"ok": True})
            resp = client.post("/api/v1/files/batch-process", json={
                "files": [{"path": "f1.txt"}, {"path": "secret.txt"}],
                "operation": "extract",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["processed"] == 1
            assert data["failed"] == 1

    def test_batch_process_internal_error_per_file(self, client):
        with patch("backend.app.api.files_v2._validate_and_resolve_path") as mock_vrp, \
             patch("backend.app.api.files_v2._document_processor") as mock_dp:
            from pathlib import Path
            mock_vrp.return_value = Path("/workspace/f.txt")
            mock_dp.process = AsyncMock(side_effect=RuntimeError("boom"))
            resp = client.post("/api/v1/files/batch-process", json={
                "files": [{"path": "f1.txt"}],
                "operation": "extract",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["failed"] == 1
