"""Deep coverage tests for backend/app/api/collaboration.py — helpers + endpoints."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.api.collaboration import (
    CollaborationMessageCreateRequest,
    CollaborationRoomCreateRequest,
    DelegationCandidateModel,
    DelegationRequestModel,
    _build_workflow_suggestion,
    _get_room_for_principal,
    _memory_context_from_principal,
    _resolve_tenant,
    add_member,
    close_room,
    create_room,
    delegate_task,
    get_delegation,
    get_room,
    get_room_correlation,
    get_room_workflow_suggestion,
    list_delegations,
    list_rooms,
    post_message,
    suggest_workflow_from_room,
)
from backend.app.core.collaboration.store import CollaborationRoom


# ═══════════════════════════════════════════════════════════════════════════════
# _resolve_tenant
# ═══════════════════════════════════════════════════════════════════════════════

class TestResolveTenant:
    def test_none_requested(self):
        principal = MagicMock()
        principal.tenant_id = "t1"
        principal.role = "user"
        assert _resolve_tenant(principal, None) == "t1"

    def test_empty_requested(self):
        principal = MagicMock()
        principal.tenant_id = "t1"
        principal.role = "user"
        assert _resolve_tenant(principal, "") == "t1"

    def test_same_tenant(self):
        principal = MagicMock()
        principal.tenant_id = "t1"
        principal.role = "user"
        assert _resolve_tenant(principal, "t1") == "t1"

    def test_different_tenant_non_admin_raises(self):
        principal = MagicMock()
        principal.tenant_id = "t1"
        principal.role = "user"
        with pytest.raises(Exception) as exc_info:
            _resolve_tenant(principal, "t2")
        assert exc_info.value.status_code == 403

    def test_different_tenant_admin(self):
        principal = MagicMock()
        principal.tenant_id = "t1"
        principal.role = "admin"
        assert _resolve_tenant(principal, "t2") == "t2"


# ═══════════════════════════════════════════════════════════════════════════════
# _get_room_for_principal
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetRoomForPrincipal:
    @patch("backend.app.api.collaboration.collaboration_store")
    def test_room_not_found(self, mock_store):
        mock_store.get_room.return_value = None
        principal = MagicMock()
        principal.role = "user"
        principal.tenant_id = "t1"
        with pytest.raises(Exception) as exc_info:
            _get_room_for_principal("r1", principal)
        assert exc_info.value.status_code == 404

    @patch("backend.app.api.collaboration.collaboration_store")
    def test_cross_tenant_non_admin(self, mock_store):
        room = MagicMock()
        room.tenant_id = "t2"
        mock_store.get_room.return_value = room
        principal = MagicMock()
        principal.role = "user"
        principal.tenant_id = "t1"
        with pytest.raises(Exception) as exc_info:
            _get_room_for_principal("r1", principal)
        assert exc_info.value.status_code == 404

    @patch("backend.app.api.collaboration.collaboration_store")
    def test_same_tenant(self, mock_store):
        room = MagicMock()
        room.tenant_id = "t1"
        mock_store.get_room.return_value = room
        principal = MagicMock()
        principal.role = "user"
        principal.tenant_id = "t1"
        result = _get_room_for_principal("r1", principal)
        assert result is room

    @patch("backend.app.api.collaboration.collaboration_store")
    def test_admin_cross_tenant(self, mock_store):
        room = MagicMock()
        room.tenant_id = "t2"
        mock_store.get_room.return_value = room
        principal = MagicMock()
        principal.role = "admin"
        principal.tenant_id = "t1"
        result = _get_room_for_principal("r1", principal)
        assert result is room


# ═══════════════════════════════════════════════════════════════════════════════
# _memory_context_from_principal
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryContextFromPrincipal:
    def test_creates_context(self):
        principal = MagicMock()
        principal.tenant_id = "t1"
        principal.user_id = "u1"
        principal.agent_id = "a1"
        principal.request_id = "req1"
        principal.trace_id = "tr1"
        ctx = _memory_context_from_principal(principal)
        assert ctx.tenant_id == "t1"
        assert ctx.user_id == "u1"
        assert ctx.agent_id == "a1"
        assert ctx.request_id == "req1"
        assert ctx.trace_id == "tr1"


# ═══════════════════════════════════════════════════════════════════════════════
# _build_workflow_suggestion
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildWorkflowSuggestion:
    def test_approval_keywords(self):
        result = _build_workflow_suggestion("需要审批这个任务")
        node_ids = [n["id"] for n in result["nodes"]]
        assert "approval" in node_ids
        assert "agent_plan" in node_ids

    def test_browser_keywords(self):
        result = _build_workflow_suggestion("打开浏览器搜索")
        node_ids = [n["id"] for n in result["nodes"]]
        assert "browser" in node_ids

    def test_collaboration_keywords(self):
        result = _build_workflow_suggestion("多智能体协作任务")
        node_ids = [n["id"] for n in result["nodes"]]
        assert "collaboration" in node_ids

    def test_default_workflow(self):
        result = _build_workflow_suggestion("普通任务")
        node_ids = [n["id"] for n in result["nodes"]]
        assert "agent_plan" in node_ids
        assert "output" in node_ids
        assert len(result["edges"]) == 2

    def test_english_approval(self):
        result = _build_workflow_suggestion("need approval for this")
        node_ids = [n["id"] for n in result["nodes"]]
        assert "approval" in node_ids

    def test_english_browser(self):
        result = _build_workflow_suggestion("open web page")
        node_ids = [n["id"] for n in result["nodes"]]
        assert "browser" in node_ids


# ═══════════════════════════════════════════════════════════════════════════════
# Request Models
# ═══════════════════════════════════════════════════════════════════════════════

class TestRequestModels:
    def test_room_create_request(self):
        req = CollaborationRoomCreateRequest(topic="Test Room")
        assert req.topic == "Test Room"
        assert req.tenant_id is None
        assert req.members == []

    def test_message_create_request(self):
        req = CollaborationMessageCreateRequest(sender_id="s1", content="hello")
        assert req.sender_type == "agent"
        assert req.message_type == "text"

    def test_delegation_candidate_model(self):
        c = DelegationCandidateModel(agent_id="a1")
        assert c.agent_type == "subagent"
        assert c.capabilities == []

    def test_delegation_request_model(self):
        req = DelegationRequestModel(task="do something")
        assert req.wait is True
        assert req.timeout_seconds == 600
        assert req.max_iterations == 10


# ═══════════════════════════════════════════════════════════════════════════════
# Endpoints (unit-level with mocked dependencies)
# ═══════════════════════════════════════════════════════════════════════════════

class TestEndpoints:
    def _make_principal(self, role="user", tenant_id="t1"):
        p = MagicMock()
        p.role = role
        p.tenant_id = tenant_id
        p.user_id = "u1"
        p.agent_id = "a1"
        p.trace_id = "tr1"
        p.request_id = "req1"
        return p

    @pytest.mark.asyncio
    @patch("backend.app.api.collaboration.message_event_bus")
    @patch("backend.app.api.collaboration.collaboration_store")
    @patch("backend.app.api.collaboration.enforce_scope")
    async def test_create_room(self, mock_scope, mock_store, mock_bus):
        room = MagicMock()
        room.tenant_id = "t1"
        room.room_id = "r1"
        room.model_dump.return_value = {"room_id": "r1"}
        mock_store.create_room.return_value = room
        mock_bus.publish = AsyncMock()
        principal = self._make_principal()
        req = CollaborationRoomCreateRequest(topic="Test")
        result = await create_room(req, principal)
        assert result == {"room_id": "r1"}

    @pytest.mark.asyncio
    @patch("backend.app.api.collaboration.collaboration_store")
    @patch("backend.app.api.collaboration.enforce_scope")
    async def test_list_rooms(self, mock_scope, mock_store):
        room = MagicMock()
        room.model_dump.return_value = {"room_id": "r1"}
        mock_store.list_rooms.return_value = [room]
        principal = self._make_principal()
        result = await list_rooms(principal)
        assert len(result) == 1

    @pytest.mark.asyncio
    @patch("backend.app.api.collaboration.collaboration_store")
    @patch("backend.app.api.collaboration.enforce_scope")
    async def test_list_rooms_admin(self, mock_scope, mock_store):
        mock_store.list_rooms.return_value = []
        principal = self._make_principal(role="admin")
        result = await list_rooms(principal, tenant_id="t2")
        assert result == []

    @pytest.mark.asyncio
    @patch("backend.app.api.collaboration._get_room_for_principal")
    @patch("backend.app.api.collaboration.enforce_scope")
    async def test_get_room_endpoint(self, mock_scope, mock_get_room):
        room = MagicMock()
        room.model_dump.return_value = {"room_id": "r1"}
        mock_get_room.return_value = room
        principal = self._make_principal()
        result = await get_room("r1", principal)
        assert result == {"room_id": "r1"}

    @pytest.mark.asyncio
    @patch("backend.app.api.collaboration._get_room_for_principal")
    @patch("backend.app.api.collaboration.enforce_scope")
    async def test_get_room_correlation(self, mock_scope, mock_get_room):
        room = MagicMock()
        room.room_id = "r1"
        room.tenant_id = "t1"
        room.status = "active"
        room.topic = "Test"
        room.created_at = "2024-01-01"
        room.updated_at = "2024-01-02"
        room.members = ["m1"]
        room.messages = []
        mock_get_room.return_value = room
        principal = self._make_principal()
        result = await get_room_correlation("r1", principal)
        assert result["room_id"] == "r1"
        assert result["trace_id"] == "r1"

    @pytest.mark.asyncio
    @patch("backend.app.api.collaboration._get_room_for_principal")
    @patch("backend.app.api.collaboration.enforce_scope")
    async def test_get_room_workflow_suggestion(self, mock_scope, mock_get_room):
        room = MagicMock()
        room.room_id = "r1"
        room.topic = "审批任务"
        room.messages = []
        mock_get_room.return_value = room
        principal = self._make_principal()
        result = await get_room_workflow_suggestion("r1", principal)
        assert "suggested_nodes" in result
        node_ids = [n["id"] for n in result["suggested_nodes"]]
        assert "approval" in node_ids

    @pytest.mark.asyncio
    @patch("backend.app.api.collaboration.message_event_bus")
    @patch("backend.app.api.collaboration.collaboration_store")
    @patch("backend.app.api.collaboration._get_room_for_principal")
    @patch("backend.app.api.collaboration.enforce_scope")
    async def test_add_member_endpoint(self, mock_scope, mock_get_room, mock_store, mock_bus):
        mock_get_room.return_value = MagicMock()
        room = MagicMock()
        room.tenant_id = "t1"
        room.room_id = "r1"
        room.model_dump.return_value = {"room_id": "r1"}
        mock_store.add_member.return_value = room
        mock_bus.publish = AsyncMock()
        principal = self._make_principal()
        result = await add_member("r1", {"member_id": "m1"}, principal)
        assert result == {"room_id": "r1"}

    @pytest.mark.asyncio
    @patch("backend.app.api.collaboration._get_room_for_principal")
    @patch("backend.app.api.collaboration.enforce_scope")
    async def test_add_member_missing_id(self, mock_scope, mock_get_room):
        mock_get_room.return_value = MagicMock()
        principal = self._make_principal()
        with pytest.raises(Exception) as exc_info:
            await add_member("r1", {}, principal)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    @patch("backend.app.api.collaboration.message_event_bus")
    @patch("backend.app.api.collaboration.collaboration_store")
    @patch("backend.app.api.collaboration._get_room_for_principal")
    @patch("backend.app.api.collaboration.enforce_scope")
    async def test_post_message_endpoint(self, mock_scope, mock_get_room, mock_store, mock_bus):
        mock_get_room.return_value = MagicMock()
        message = MagicMock()
        message.model_dump.return_value = {"message_id": "m1"}
        mock_store.post_message.return_value = message
        room = MagicMock()
        room.tenant_id = "t1"
        room.room_id = "r1"
        room.model_dump.return_value = {"room_id": "r1"}
        mock_store.get_room.return_value = room
        mock_bus.publish = AsyncMock()
        principal = self._make_principal()
        req = CollaborationMessageCreateRequest(sender_id="s1", content="hello")
        result = await post_message("r1", req, principal)
        assert result == {"message_id": "m1"}

    @pytest.mark.asyncio
    @patch("backend.app.api.collaboration.message_event_bus")
    @patch("backend.app.api.collaboration.collaboration_store")
    @patch("backend.app.api.collaboration._get_room_for_principal")
    @patch("backend.app.api.collaboration.enforce_scope")
    async def test_close_room_endpoint(self, mock_scope, mock_get_room, mock_store, mock_bus):
        mock_get_room.return_value = MagicMock()
        room = MagicMock()
        room.tenant_id = "t1"
        room.room_id = "r1"
        room.model_dump.return_value = {"room_id": "r1"}
        mock_store.close_room.return_value = room
        mock_bus.publish = AsyncMock()
        principal = self._make_principal()
        result = await close_room("r1", principal)
        assert result == {"closed": True}

    @pytest.mark.asyncio
    @patch("backend.app.api.collaboration.get_delegator")
    @patch("backend.app.api.collaboration.enforce_scope")
    async def test_delegate_task_endpoint(self, mock_scope, mock_get_delegator):
        delegator = MagicMock()
        result_obj = MagicMock()
        result_obj.model_dump.return_value = {"delegation_id": "d1"}
        delegator.delegate = AsyncMock(return_value=result_obj)
        mock_get_delegator.return_value = delegator
        principal = self._make_principal()
        req = DelegationRequestModel(task="do something")
        result = await delegate_task(req, principal)
        assert result == {"delegation_id": "d1"}

    @pytest.mark.asyncio
    @patch("backend.app.api.collaboration.get_delegator")
    @patch("backend.app.api.collaboration.enforce_scope")
    async def test_list_delegations_endpoint(self, mock_scope, mock_get_delegator):
        delegator = MagicMock()
        item = MagicMock()
        item.model_dump.return_value = {"id": "d1"}
        delegator.list_delegations.return_value = [item]
        mock_get_delegator.return_value = delegator
        principal = self._make_principal()
        result = await list_delegations(principal)
        assert len(result) == 1

    @pytest.mark.asyncio
    @patch("backend.app.api.collaboration.get_delegator")
    @patch("backend.app.api.collaboration.enforce_scope")
    async def test_get_delegation_endpoint(self, mock_scope, mock_get_delegator):
        delegator = MagicMock()
        result_obj = MagicMock()
        result_obj.tenant_id = "t1"
        result_obj.model_dump.return_value = {"id": "d1"}
        delegator.get_delegation.return_value = result_obj
        mock_get_delegator.return_value = delegator
        principal = self._make_principal()
        result = await get_delegation("d1", principal)
        assert result == {"id": "d1"}

    @pytest.mark.asyncio
    @patch("backend.app.api.collaboration.get_delegator")
    @patch("backend.app.api.collaboration.enforce_scope")
    async def test_get_delegation_not_found(self, mock_scope, mock_get_delegator):
        delegator = MagicMock()
        delegator.get_delegation.return_value = None
        mock_get_delegator.return_value = delegator
        principal = self._make_principal()
        with pytest.raises(Exception) as exc_info:
            await get_delegation("d1", principal)
        assert exc_info.value.status_code == 404
