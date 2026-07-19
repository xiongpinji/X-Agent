"""P1-09 collaboration convergence tests.

Covers:
- Runtime delegation end-to-end under the mock LLM (main agent -> delegator
  -> spawned real sub-AgentLoop -> result returned + room callback)
- Capability matching (scopes/tags, case-insensitive) and round-robin
  load balancing
- Explicit failure paths (no capable candidate -> 422; CONTAINER -> 400)
- Tenant convergence on the collaboration API (403 on mismatch, 404 on
  cross-tenant room access, admin pass-through)
- Optional store persistence (JSON snapshot survives "restart")
- IsolationLevel.PROCESS real child-process execution
"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.app.api.messages import message_event_bus
from backend.app.core.agent_spawner import AgentSpawner
from backend.app.core.collaboration import (
    CandidateSpec,
    CollaborationDelegator,
    CollaborationStore,
    DelegationRequest,
    NoCapableAgentError,
)
from backend.app.dependencies import get_current_principal
from backend.app.main import app


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class _FakePrincipal:
    def __init__(self, tenant_id: str = "tenant-1", role: str = "developer", user_id: str = "user-1", agent_id: str = "agent-1"):
        self.tenant_id = tenant_id
        self.org_id = "org-1"
        self.agent_id = agent_id
        self.user_id = user_id
        self.trace_id = f"trace-{uuid.uuid4().hex[:8]}"
        self.request_id = f"req-{uuid.uuid4().hex[:8]}"
        self.permission_scope: list[str] = []
        self.role = role
        self.scopes: list[str] = [
            "agent:run",
            "agent:read",
            "tools:read",
            "memory:read",
            "memory:write",
            "workflow:create",
            "workflow:run",
            "audit:read",
        ]
        self.authenticated = True


class _PrincipalBoundClient:
    """TestClient wrapper that binds a specific principal per request.

    ``app.dependency_overrides`` is process-global; with several clients of
    different tenants in one test, each call must re-pin its own principal
    right before dispatch (TestClient is synchronous, so this is race-free).
    """

    def __init__(self, holder: dict, principal: _FakePrincipal) -> None:
        self._holder = holder
        self._principal = principal
        self._client = TestClient(app, headers={"x-api-key": "bootstrap"})

    def _bind(self) -> None:
        self._holder["principal"] = self._principal

    def get(self, *args, **kwargs):
        self._bind()
        return self._client.get(*args, **kwargs)

    def post(self, *args, **kwargs):
        self._bind()
        return self._client.post(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._bind()
        return self._client.delete(*args, **kwargs)


@pytest.fixture
def client_factory():
    holder: dict = {}
    app.dependency_overrides[get_current_principal] = lambda: holder["principal"]

    def _make(principal: _FakePrincipal) -> _PrincipalBoundClient:
        return _PrincipalBoundClient(holder, principal)

    yield _make
    app.dependency_overrides.pop(get_current_principal, None)
    message_event_bus.clear()


# ---------------------------------------------------------------------------
# Runtime delegation (unit-level, isolated spawner)
# ---------------------------------------------------------------------------


class TestDelegatorCore:
    @pytest.mark.asyncio
    async def test_end_to_end_delegation_mock_llm(self) -> None:
        """Main path: delegate -> spawn real AgentLoop (mock LLM) -> result back."""
        delegator = CollaborationDelegator(spawner=AgentSpawner())
        result = await delegator.delegate(
            DelegationRequest(task="summarize the quarter", timeout_seconds=120)
        )
        assert result.status == "completed"
        assert result.spawned_agent_id and result.spawned_agent_id.startswith("agent_")
        assert result.selected_candidate is not None
        assert result.balancer == "round_robin"
        assert result.result is not None
        assert "mock response" in str(result.result.get("answer", "")).lower()

    @pytest.mark.asyncio
    async def test_capability_match_selects_only_qualified(self) -> None:
        delegator = CollaborationDelegator(spawner=AgentSpawner())
        pool = [
            CandidateSpec(agent_id=_uid("web"), capabilities=["web", "search"]),
            CandidateSpec(agent_id=_uid("sql"), capabilities=["sql"]),
        ]
        result = await delegator.delegate(
            DelegationRequest(
                task="run query",
                required_capabilities=["SQL"],  # case-insensitive
                candidates=pool,
                wait=False,
            )
        )
        assert result.selected_candidate is not None
        assert result.selected_candidate.capabilities == ["sql"]
        assert result.matched_candidate_ids == [pool[1].agent_id]

    @pytest.mark.asyncio
    async def test_round_robin_rotates_over_matched_pool(self) -> None:
        delegator = CollaborationDelegator(spawner=AgentSpawner())
        pool = [
            CandidateSpec(agent_id=_uid("w1"), capabilities=["web"]),
            CandidateSpec(agent_id=_uid("w2"), capabilities=["web"]),
            CandidateSpec(agent_id=_uid("w3"), capabilities=["web"]),
        ]
        picks: list[str] = []
        for _ in range(4):
            result = await delegator.delegate(
                DelegationRequest(
                    task="t",
                    required_capabilities=["web"],
                    candidates=pool,
                    wait=False,
                )
            )
            assert result.selected_candidate is not None
            picks.append(result.selected_candidate.agent_id)
        expected = [c.agent_id for c in pool]
        assert picks == [expected[0], expected[1], expected[2], expected[0]]

    @pytest.mark.asyncio
    async def test_no_capable_agent_raises_explicitly(self) -> None:
        delegator = CollaborationDelegator(spawner=AgentSpawner())
        with pytest.raises(NoCapableAgentError) as exc_info:
            await delegator.delegate(
                DelegationRequest(
                    task="t",
                    required_capabilities=["gpu-inference"],
                    candidates=[CandidateSpec(agent_id=_uid("cpu"), capabilities=["cpu"])],
                    wait=False,
                )
            )
        assert "gpu-inference" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_room_callback_posts_result_message(self) -> None:
        store = CollaborationStore()
        room = store.create_room(topic="delegation room", tenant_id=_uid("tenant"), created_by="tester")
        delegator = CollaborationDelegator(spawner=AgentSpawner(), store=store)
        result = await delegator.delegate(
            DelegationRequest(
                task="report back",
                room_id=room.room_id,
                timeout_seconds=120,
                metadata={"agent_id": "main-agent"},
            )
        )
        assert result.status == "completed"
        updated = store.get_room(room.room_id)
        assert updated is not None
        callback_messages = [m for m in updated.messages if result.delegation_id in m.content]
        assert len(callback_messages) == 1
        assert "status=completed" in callback_messages[0].content
        assert callback_messages[0].metadata.get("delegation_id") == result.delegation_id

    @pytest.mark.asyncio
    async def test_org_hints_wire_dispatch_into_runtime(self) -> None:
        """Org context makes the delegator consult core.dispatch for ranking."""
        from backend.app.core import org as org_core

        tenant = _uid("tenant")
        organization = org_core.organization_store.create_organization(tenant_id=tenant, name=_uid("org"))
        department = org_core.organization_store.create_department(org_id=organization.org_id, name=_uid("dept"))
        leader = org_core.organization_store.create_agent(
            org_id=organization.org_id,
            department_id=department.department_id,
            name=_uid("leader"),
            capabilities=["research"],
        )
        org_core.organization_store.create_agent(
            org_id=organization.org_id,
            department_id=department.department_id,
            name=_uid("worker"),
            manager_agent_id=leader.agent_id,
            capabilities=["research"],
        )

        delegator = CollaborationDelegator(spawner=AgentSpawner())
        result = await delegator.delegate(
            DelegationRequest(
                task="research task",
                required_capabilities=["research"],
                org_id=organization.org_id,
                department_id=department.department_id,
                wait=False,
            )
        )
        assert result.dispatch_evidence.get("dispatch_used") is True
        assert result.pool_size == 2
        assert len(result.matched_candidate_ids) == 2
        assert result.selected_candidate is not None
        assert result.selected_candidate.source == "org"

    def test_container_isolation_explicitly_rejected(self) -> None:
        delegator = CollaborationDelegator(spawner=AgentSpawner())
        with pytest.raises(NotImplementedError) as exc_info:
            asyncio.run(
                delegator.delegate(DelegationRequest(task="t", isolation="container", wait=False))
            )
        assert "sandbox" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Delegation via the collaboration API (mock LLM, TestClient)
# ---------------------------------------------------------------------------


class TestDelegationAPI:
    def test_delegate_end_to_end_via_api(self, client_factory) -> None:
        tenant = _uid("tenant")
        client = client_factory(_FakePrincipal(tenant_id=tenant))

        room_response = client.post("/api/v1/collaboration/rooms", json={"topic": "delegation e2e"})
        assert room_response.status_code == 200
        room_id = room_response.json()["room_id"]

        response = client.post(
            "/api/v1/collaboration/delegate",
            json={
                "task": "draft the weekly summary",
                "room_id": room_id,
                "wait": True,
                "timeout_seconds": 120,
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "completed"
        assert body["spawned_agent_id"].startswith("agent_")
        assert "mock response" in str((body["result"] or {}).get("answer", "")).lower()
        assert body["balancer"] == "round_robin"

        # Result was reported back into the room.
        room = client.get(f"/api/v1/collaboration/rooms/{room_id}").json()
        assert any(body["delegation_id"] in m["content"] for m in room["messages"])

        # Delegation is queryable afterwards.
        listing = client.get("/api/v1/collaboration/delegations")
        assert listing.status_code == 200
        assert any(item["delegation_id"] == body["delegation_id"] for item in listing.json())
        detail = client.get(f"/api/v1/collaboration/delegations/{body['delegation_id']}")
        assert detail.status_code == 200
        assert detail.json()["status"] == "completed"

    def test_delegate_no_capable_agent_returns_422(self, client_factory) -> None:
        client = client_factory(_FakePrincipal(tenant_id=_uid("tenant")))
        response = client.post(
            "/api/v1/collaboration/delegate",
            json={
                "task": "needs gpu",
                "required_capabilities": ["gpu-inference"],
                "candidates": [{"agent_id": _uid("cpu"), "capabilities": ["cpu"]}],
                "wait": False,
            },
        )
        assert response.status_code == 422
        assert "gpu-inference" in response.text

    def test_delegate_container_isolation_returns_400(self, client_factory) -> None:
        client = client_factory(_FakePrincipal(tenant_id=_uid("tenant")))
        response = client.post(
            "/api/v1/collaboration/delegate",
            json={"task": "t", "isolation": "container", "wait": False},
        )
        assert response.status_code == 400
        assert "sandbox" in response.text

    def test_delegate_cross_tenant_rejected(self, client_factory) -> None:
        client = client_factory(_FakePrincipal(tenant_id=_uid("tenant")))
        response = client.post(
            "/api/v1/collaboration/delegate",
            json={"task": "t", "tenant_id": _uid("other-tenant"), "wait": False},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Tenant convergence on the room API
# ---------------------------------------------------------------------------


class TestTenantConvergence:
    def test_create_room_with_foreign_tenant_forbidden(self, client_factory) -> None:
        client = client_factory(_FakePrincipal(tenant_id="tenant-a"))
        response = client.post("/api/v1/collaboration/rooms", json={"topic": "x", "tenant_id": "tenant-b"})
        assert response.status_code == 403

    def test_create_room_defaults_to_principal_tenant(self, client_factory) -> None:
        tenant = _uid("tenant")
        client = client_factory(_FakePrincipal(tenant_id=tenant))
        response = client.post("/api/v1/collaboration/rooms", json={"topic": "x"})
        assert response.status_code == 200
        assert response.json()["tenant_id"] == tenant

    def test_create_room_own_tenant_explicitly_allowed(self, client_factory) -> None:
        tenant = _uid("tenant")
        client = client_factory(_FakePrincipal(tenant_id=tenant))
        response = client.post("/api/v1/collaboration/rooms", json={"topic": "x", "tenant_id": tenant})
        assert response.status_code == 200
        assert response.json()["tenant_id"] == tenant

    def test_list_rooms_pinned_to_own_tenant(self, client_factory) -> None:
        tenant_a = _uid("tenant-a")
        tenant_b = _uid("tenant-b")
        client_a = client_factory(_FakePrincipal(tenant_id=tenant_a))
        client_b = client_factory(_FakePrincipal(tenant_id=tenant_b))

        room_a = client_a.post("/api/v1/collaboration/rooms", json={"topic": "room A"}).json()
        room_b = client_b.post("/api/v1/collaboration/rooms", json={"topic": "room B"}).json()

        listed_a = client_a.get("/api/v1/collaboration/rooms").json()
        ids_a = {room["room_id"] for room in listed_a}
        assert room_a["room_id"] in ids_a
        assert room_b["room_id"] not in ids_a
        assert all(room["tenant_id"] == tenant_a for room in listed_a)

        # Passing the other tenant explicitly is a 403, not a silent listing.
        assert client_a.get(f"/api/v1/collaboration/rooms?tenant_id={tenant_b}").status_code == 403
        # Passing the own tenant explicitly works.
        assert client_a.get(f"/api/v1/collaboration/rooms?tenant_id={tenant_a}").status_code == 200

    def test_cross_tenant_room_access_returns_404(self, client_factory) -> None:
        tenant_a = _uid("tenant-a")
        client_a = client_factory(_FakePrincipal(tenant_id=tenant_a))
        client_b = client_factory(_FakePrincipal(tenant_id=_uid("tenant-b")))

        room_id = client_a.post("/api/v1/collaboration/rooms", json={"topic": "private"}).json()["room_id"]
        assert client_b.get(f"/api/v1/collaboration/rooms/{room_id}").status_code == 404
        assert client_b.post(f"/api/v1/collaboration/rooms/{room_id}/messages", json={"sender_id": "x", "content": "hi"}).status_code == 404
        assert client_b.post(f"/api/v1/collaboration/rooms/{room_id}/close").status_code == 404

    def test_admin_can_address_other_tenants(self, client_factory) -> None:
        tenant_a = _uid("tenant-a")
        client_a = client_factory(_FakePrincipal(tenant_id=tenant_a))
        admin = client_factory(_FakePrincipal(tenant_id=_uid("tenant-admin"), role="admin"))

        room_id = client_a.post("/api/v1/collaboration/rooms", json={"topic": "for admin"}).json()["room_id"]
        assert admin.get(f"/api/v1/collaboration/rooms/{room_id}").status_code == 200
        listed = admin.get(f"/api/v1/collaboration/rooms?tenant_id={tenant_a}").json()
        assert any(room["room_id"] == room_id for room in listed)


# ---------------------------------------------------------------------------
# Store persistence (optional JSON snapshot)
# ---------------------------------------------------------------------------


class TestStorePersistence:
    def test_snapshot_survives_reload(self, tmp_path) -> None:
        path = tmp_path / "rooms.json"
        store = CollaborationStore(storage_path=path)
        assert store.persistent is True
        room = store.create_room(topic="durable", tenant_id="t1", created_by="u1", members=["a1"])
        store.post_message(room.room_id, sender_id="a1", sender_type="agent", content="persisted", metadata={"department_id": "d1"})
        store.add_memory_ref(room.room_id, "mem-1")
        store.add_department_memory_ref(room.room_id, "d1", "mem-2")
        store.close_room(room.room_id)

        reloaded = CollaborationStore(storage_path=path)
        restored = reloaded.get_room(room.room_id)
        assert restored is not None
        assert restored.topic == "durable"
        assert restored.status == "closed"
        assert len(restored.messages) == 1
        assert restored.messages[0].content == "persisted"
        assert "mem-1" in restored.memory_refs
        assert restored.department_memory_refs.get("d1") == ["mem-2"]
        assert restored.agent_memory_refs.get("a1"), "agent refs must survive reload"

    def test_memory_only_store_is_explicitly_non_persistent(self) -> None:
        store = CollaborationStore()
        assert store.persistent is False

    def test_atomic_write_leaves_no_tmp_file(self, tmp_path) -> None:
        path = tmp_path / "rooms.json"
        store = CollaborationStore(storage_path=path)
        store.create_room(topic="t", tenant_id="t1", created_by="u1")
        assert path.exists()
        assert not (tmp_path / "rooms.json.tmp").exists()


# ---------------------------------------------------------------------------
# IsolationLevel.PROCESS (real child process)
# ---------------------------------------------------------------------------


class TestProcessIsolation:
    @pytest.mark.asyncio
    async def test_process_isolated_spawn_completes_in_child(self, monkeypatch) -> None:
        """PROCESS isolation runs the task in a real OS child process.

        The mock LLM backend is selected through the environment, which the
        spawn-context child inherits — no monkeypatching crosses the process
        boundary, so this is a genuine end-to-end process run.
        """
        monkeypatch.setenv("XAGENT_LLM_BACKEND", "mock")
        spawner = AgentSpawner()
        agent_id = await spawner.spawn_agent(
            agent_type="subagent",
            task="hello from parent",
            context={"tenant_id": "default"},
            isolation="process",
            timeout_seconds=180,
        )
        final = await spawner.wait_for_agent(agent_id, timeout_seconds=200)
        assert final is not None, "child process did not report back in time"
        assert final["status"] == "completed", final
        assert final["isolation"] == "process"
        assert final["resource_limits_enforced"] is False
        result = final["result"] or {}
        assert "mock response" in str(result.get("answer", "")).lower()
        child_pid = result.get("child_pid")
        assert child_pid and int(child_pid) != os.getpid()

    @pytest.mark.asyncio
    async def test_thread_alias_maps_to_none(self) -> None:
        spawner = AgentSpawner()
        agent_id = await spawner.spawn_agent(
            agent_type="subagent",
            task="t",
            context={},
            isolation="thread",
            timeout_seconds=120,
        )
        status = await spawner.get_agent_status(agent_id)
        assert status is not None
        assert status["isolation"] == "none"
        await spawner.terminate_agent(agent_id)

    def test_container_raises_with_sandbox_pointer(self) -> None:
        spawner = AgentSpawner()
        with pytest.raises(NotImplementedError) as exc_info:
            asyncio.run(
                spawner.spawn_agent(agent_type="subagent", task="t", context={}, isolation="container")
            )
        message = str(exc_info.value)
        assert "sandbox" in message
        assert "docker" in message

    def test_unknown_isolation_raises_value_error(self) -> None:
        spawner = AgentSpawner()
        with pytest.raises(ValueError):
            asyncio.run(
                spawner.spawn_agent(agent_type="subagent", task="t", context={}, isolation="sideways")
            )
