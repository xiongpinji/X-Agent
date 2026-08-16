from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api import workbench
from backend.app.api.auth import _issue_token, _store_token_user
from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler
from backend.app.core.admin import UserCreateRequest, UserStore
from backend.app.core.collaboration.store import CollaborationStore
from backend.app.core.contracts import AgentRunResponse, RunContext, RunStatus
from backend.app.core.memory.store import MemorySystem
from backend.app.core.org import OrganizationStore
from backend.app.core.runs import RunStore
from backend.app.core.security import APIKeyCreateRequest, APIKeyStore
from backend.app.core.skills_core import SkillMetadata
from backend.app.core.skills_registry import SkillRegistry
from backend.app.core.tools import ToolPolicyEngine, ToolRegistry
from backend.app.dependencies import get_memory, get_run_store, get_runtime_tool_registry
from backend.app.main import app as mounted_app


def _production_settings() -> SimpleNamespace:
    return SimpleNamespace(
        app_mode="production",
        require_api_key=True,
        bootstrap_api_key=None,
        bootstrap_api_key_sha256=None,
    )


def _save_run(store: RunStore, *, tenant_id: str, user_id: str, trace_id: str) -> None:
    context = RunContext(
        trace_id=trace_id,
        tenant_id=tenant_id,
        user_id=user_id,
        agent_id="agent-1",
    )
    store.save(
        context,
        f"task-{trace_id}",
        AgentRunResponse(
            trace_id=trace_id,
            agent_id="agent-1",
            status=RunStatus.COMPLETED,
            answer=f"answer-{trace_id}",
            iterations=1,
            memory_hits=0,
        ),
    )


def _build_app(
    *,
    run_store: RunStore | None = None,
    memory: MemorySystem | None = None,
    tools: ToolRegistry | None = None,
) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
    app.include_router(workbench.router)
    if run_store is not None:
        app.dependency_overrides[get_run_store] = lambda: run_store
    if memory is not None:
        app.dependency_overrides[get_memory] = lambda: memory
    if tools is not None:
        app.dependency_overrides[get_runtime_tool_registry] = lambda: tools
    return app


def _install_auth(monkeypatch, *, tenant_id: str, user_id: str) -> tuple[str, str]:
    api_keys = APIKeyStore()
    raw_key = api_keys.create(
        APIKeyCreateRequest(
            name="console-test",
            tenant_id=tenant_id,
            user_id=user_id,
            role="developer",
        )
    ).key
    monkeypatch.setattr("backend.app.dependencies.get_api_key_store", lambda: api_keys)

    users = UserStore()
    user = users.create(
        UserCreateRequest(
            email=f"{user_id}@example.com",
            display_name=user_id,
            role="developer",
            tenant_id=tenant_id,
        )
    )
    monkeypatch.setattr("backend.app.core.admin.user_store", users)
    token = _issue_token()
    _store_token_user(token, user.id)
    return raw_key, token


def test_workbench_production_requires_credentials(monkeypatch) -> None:
    settings = _production_settings()
    monkeypatch.setattr(workbench, "get_settings", lambda: settings)
    monkeypatch.setattr("backend.app.dependencies.get_settings", lambda: settings)

    response = TestClient(_build_app()).get("/api/v1/workbench")

    assert response.status_code == 401


def test_workbench_accepts_bearer_and_api_key(monkeypatch) -> None:
    settings = _production_settings()
    monkeypatch.setattr(workbench, "get_settings", lambda: settings)
    monkeypatch.setattr("backend.app.dependencies.get_settings", lambda: settings)
    api_key, bearer = _install_auth(monkeypatch, tenant_id="tenant-a", user_id="user-a")
    client = TestClient(
        _build_app(
            run_store=RunStore(),
            memory=MemorySystem(),
            tools=ToolRegistry(ToolPolicyEngine()),
        )
    )

    api_key_response = client.get("/api/v1/workbench", headers={"x-api-key": api_key})
    bearer_response = client.get(
        "/api/v1/workbench", headers={"Authorization": f"Bearer {bearer}"}
    )

    assert api_key_response.status_code == 200
    assert bearer_response.status_code == 200
    assert api_key_response.json()["console"]["tenant_id"] == "tenant-a"
    assert bearer_response.json()["console"]["tenant_id"] == "tenant-a"


def test_workbench_reads_real_tenant_scoped_stores_without_dispatch(monkeypatch) -> None:
    settings = _production_settings()
    monkeypatch.setattr(workbench, "get_settings", lambda: settings)
    monkeypatch.setattr("backend.app.dependencies.get_settings", lambda: settings)
    api_key, _ = _install_auth(monkeypatch, tenant_id="tenant-a", user_id="user-a")

    run_store = RunStore()
    _save_run(run_store, tenant_id="tenant-a", user_id="user-a", trace_id="run-a")
    _save_run(run_store, tenant_id="tenant-b", user_id="user-b", trace_id="run-b")
    memory = MemorySystem()
    memory.add("memory-a", tenant_id="tenant-a")
    memory.add("memory-b", tenant_id="tenant-b")
    organization_store = OrganizationStore()
    org_a = organization_store.create_organization(
        tenant_id="tenant-a", name="Org A", owner_user_id="user-a"
    )
    organization_store.create_organization(
        tenant_id="tenant-b", name="Org B", owner_user_id="user-b"
    )
    collaboration_store = CollaborationStore()
    room_a = collaboration_store.create_room(
        topic="Room A", tenant_id="tenant-a", created_by="user-a"
    )
    collaboration_store.create_room(
        topic="Room B", tenant_id="tenant-b", created_by="user-b"
    )
    tools = ToolRegistry(ToolPolicyEngine())
    tools.register("real-tool", "real", lambda: {"ok": True})
    cached_skills = SkillRegistry()
    cached_skills.skills["skill-a"] = SkillMetadata(skill_id="skill-a", name="Cached Skill")

    monkeypatch.setattr(workbench, "organization_store", organization_store)
    monkeypatch.setattr(workbench, "collaboration_store", collaboration_store, raising=False)
    monkeypatch.setattr("backend.app.core.skills_registry._skill_registry", cached_skills)
    monkeypatch.setattr(
        workbench,
        "dispatch",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("GET dispatched")),
        raising=False,
    )
    client = TestClient(_build_app(run_store=run_store, memory=memory, tools=tools))
    before_counts = {
        "runs": run_store.count(),
        "memory": memory.count(),
        "organizations": len(organization_store.list_organizations()),
        "rooms": len(collaboration_store.list_rooms()),
    }

    response = client.get(
        "/api/v1/workbench?tenant_id=tenant-b", headers={"x-api-key": api_key}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["console"]["tenant_id"] == "tenant-a"
    assert payload["execution"]["count"] == 1
    assert [item["trace_id"] for item in payload["execution"]["runs"]] == ["run-a"]
    assert payload["memory"]["count"] == 1
    assert len(payload["memory"]["items"]) == 1
    assert "content" not in payload["memory"]["items"][0]
    assert payload["organization_graph"]["organization"]["org_id"] == org_a.org_id
    assert payload["organization_graph"]["role_templates"] == []
    assert all(node["node_type"] != "role_template" for node in payload["organization_graph"]["nodes"])
    assert [room["room_id"] for room in payload["meeting_rooms"]["rooms"]] == [room_a.room_id]
    assert payload["meeting_rooms"]["rooms"][0] == {
        "room_id": room_a.room_id,
        "name": "Room A",
        "topic": "Room A",
        "status": "active",
        "member_count": 0,
        "member_agent_ids": [],
        "message_count": 0,
        "created_at": room_a.created_at.isoformat(),
        "updated_at": room_a.updated_at.isoformat(),
    }
    assert payload["tools"]["items"][0]["name"] == "real-tool"
    assert payload["tools"]["skills"]["items"][0]["skill_id"] == "skill-a"
    assert before_counts == {
        "runs": run_store.count(),
        "memory": memory.count(),
        "organizations": len(organization_store.list_organizations()),
        "rooms": len(collaboration_store.list_rooms()),
    }
    assert "run-b" not in response.text
    assert "memory-b" not in response.text
    assert "Org B" not in response.text
    assert "Room B" not in response.text


def test_workbench_bounds_and_redacts_runtime_summaries(monkeypatch) -> None:
    settings = _production_settings()
    monkeypatch.setattr(workbench, "get_settings", lambda: settings)
    monkeypatch.setattr("backend.app.dependencies.get_settings", lambda: settings)
    api_key, _ = _install_auth(monkeypatch, tenant_id="tenant-a", user_id="user-a")
    runs = RunStore()
    memory = MemorySystem()
    for index in range(55):
        _save_run(
            runs,
            tenant_id="tenant-a",
            user_id="user-a",
            trace_id=f"run-{index:02d}",
        )
        memory.add(
            f"private-memory-content-{index:02d}",
            summary=f"private-memory-summary-{index:02d}",
            tenant_id="tenant-a",
        )
    rooms = CollaborationStore()
    room = rooms.create_room(
        topic="Bounded Room",
        tenant_id="tenant-a",
        created_by="user-a",
        members=["agent-a"],
    )
    rooms.post_message(
        room.room_id,
        sender_id="user-a",
        sender_type="user",
        content="private-room-message",
    )
    monkeypatch.setattr(workbench, "organization_store", OrganizationStore())
    monkeypatch.setattr(workbench, "collaboration_store", rooms)

    response = TestClient(
        _build_app(
            run_store=runs,
            memory=memory,
            tools=ToolRegistry(ToolPolicyEngine()),
        )
    ).get("/api/v1/workbench", headers={"x-api-key": api_key})

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution"]["count"] == 55
    assert len(payload["execution"]["runs"]) == 50
    assert payload["memory"]["count"] == 55
    assert len(payload["memory"]["items"]) == 50
    assert all(
        forbidden not in run
        for run in payload["execution"]["runs"]
        for forbidden in ("answer", "tool_calls", "snapshot", "run_view", "execution_summary")
    )
    assert all(
        forbidden not in item
        for item in payload["memory"]["items"]
        for forbidden in ("content", "metadata", "embedding", "revisions")
    )
    room_summary = payload["meeting_rooms"]["rooms"][0]
    assert room_summary["member_count"] == 1
    assert room_summary["member_agent_ids"] == ["agent-a"]
    assert room_summary["message_count"] == 1
    assert "messages" not in room_summary
    assert "private-memory-content" not in response.text
    assert "private-memory-summary" not in response.text
    assert "answer-run" not in response.text
    assert "private-room-message" not in response.text


def test_workbench_empty_stores_report_truthful_availability(monkeypatch) -> None:
    settings = _production_settings()
    monkeypatch.setattr(workbench, "get_settings", lambda: settings)
    monkeypatch.setattr("backend.app.dependencies.get_settings", lambda: settings)
    api_key, _ = _install_auth(monkeypatch, tenant_id="tenant-a", user_id="user-a")
    monkeypatch.setattr(workbench, "organization_store", OrganizationStore())
    monkeypatch.setattr(workbench, "collaboration_store", CollaborationStore(), raising=False)
    monkeypatch.setattr("backend.app.core.skills_registry._skill_registry", None)

    response = TestClient(
        _build_app(run_store=RunStore(), memory=MemorySystem(), tools=ToolRegistry(ToolPolicyEngine()))
    ).get("/api/v1/workbench", headers={"x-api-key": api_key})

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution"] == {
        "availability": "available",
        "count": 0,
        "runs": [],
        "active_runs": [],
    }
    assert payload["memory"]["availability"] == "available"
    assert payload["memory"]["count"] == 0
    assert payload["memory"]["items"] == []
    assert payload["meeting_rooms"]["rooms"] == []
    assert payload["tools"]["count"] == 0
    assert payload["tools"]["items"] == []
    assert payload["tools"]["skills"] == {
        "availability": "unavailable",
        "items": [],
        "count": 0,
    }
    assert payload["workflow"]["availability"] == "unavailable"
    assert payload["workflow"]["templates"] == []
    assert payload["avatars"] == []


def test_workbench_reports_unavailable_when_memory_store_has_no_read_interface(monkeypatch) -> None:
    settings = _production_settings()
    monkeypatch.setattr(workbench, "get_settings", lambda: settings)
    monkeypatch.setattr("backend.app.dependencies.get_settings", lambda: settings)
    api_key, _ = _install_auth(monkeypatch, tenant_id="tenant-a", user_id="user-a")
    app = _build_app(
        run_store=RunStore(),
        memory=MemorySystem(),
        tools=ToolRegistry(ToolPolicyEngine()),
    )
    app.dependency_overrides[get_memory] = lambda: object()

    response = TestClient(app).get("/api/v1/workbench", headers={"x-api-key": api_key})

    assert response.status_code == 200
    assert response.json()["memory"] == {
        "availability": "unavailable",
        "count": 0,
        "items": [],
        "sessions": [],
        "session_summary": {},
        "agent_summary": {},
        "department_summary": {},
        "layer_totals": {},
        "memory_refs": [],
    }


def test_workbench_does_not_project_resources_outside_principal_scopes(monkeypatch) -> None:
    settings = _production_settings()
    monkeypatch.setattr(workbench, "get_settings", lambda: settings)
    monkeypatch.setattr("backend.app.dependencies.get_settings", lambda: settings)
    api_keys = APIKeyStore()
    raw_key = api_keys.create(
        APIKeyCreateRequest(
            name="tools-only",
            tenant_id="tenant-a",
            user_id="user-a",
            role="developer",
            scopes=["tools:read"],
        )
    ).key
    monkeypatch.setattr("backend.app.dependencies.get_api_key_store", lambda: api_keys)
    runs = RunStore()
    _save_run(runs, tenant_id="tenant-a", user_id="user-a", trace_id="private-run")
    memory = MemorySystem()
    memory.add("private-memory", tenant_id="tenant-a")
    organizations = OrganizationStore()
    organizations.create_organization(tenant_id="tenant-a", name="Private Org")
    rooms = CollaborationStore()
    rooms.create_room(topic="Private Room", tenant_id="tenant-a", created_by="user-a")
    monkeypatch.setattr(workbench, "organization_store", organizations)
    monkeypatch.setattr(workbench, "collaboration_store", rooms)

    response = TestClient(
        _build_app(
            run_store=runs,
            memory=memory,
            tools=ToolRegistry(ToolPolicyEngine()),
        )
    ).get("/api/v1/workbench", headers={"x-api-key": raw_key})

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution"] == {
        "availability": "unavailable",
        "count": 0,
        "runs": [],
        "active_runs": [],
    }
    assert payload["memory"]["availability"] == "unavailable"
    assert payload["memory"]["items"] == []
    assert payload["organization_graph"]["availability"] == "unavailable"
    assert payload["meeting_rooms"]["availability"] == "unavailable"
    assert "private-run" not in response.text
    assert "private-memory" not in response.text
    assert "Private Org" not in response.text
    assert "Private Room" not in response.text


def test_mounted_workbench_overrides_foreign_tenant_query_only_on_scoped_get(monkeypatch) -> None:
    settings = _production_settings()
    monkeypatch.setattr(workbench, "get_settings", lambda: settings)
    monkeypatch.setattr("backend.app.dependencies.get_settings", lambda: settings)
    api_key, _ = _install_auth(monkeypatch, tenant_id="tenant-a", user_id="user-a")
    runs = RunStore()
    _save_run(runs, tenant_id="tenant-a", user_id="user-a", trace_id="mounted-run-a")
    _save_run(runs, tenant_id="tenant-b", user_id="user-b", trace_id="mounted-run-b")
    mounted_app.dependency_overrides[get_run_store] = lambda: runs
    mounted_app.dependency_overrides[get_memory] = lambda: MemorySystem()
    mounted_app.dependency_overrides[get_runtime_tool_registry] = lambda: ToolRegistry(ToolPolicyEngine())

    try:
        client = TestClient(mounted_app)
        response = client.get(
            "/api/v1/workbench?tenant_id=tenant-b",
            headers={"x-api-key": api_key},
        )
        protected_response = client.get(
            "/api/v1/collaboration/rooms?tenant_id=tenant-b",
            headers={"x-api-key": api_key},
        )
        anonymous_response = client.get("/api/v1/workbench?tenant_id=tenant-b")

        assert response.status_code == 200
        assert response.json()["console"]["tenant_id"] == "tenant-a"
        assert [run["trace_id"] for run in response.json()["execution"]["runs"]] == ["mounted-run-a"]
        assert protected_response.status_code == 403
        assert anonymous_response.status_code == 401
    finally:
        mounted_app.dependency_overrides.pop(get_run_store, None)
        mounted_app.dependency_overrides.pop(get_memory, None)
        mounted_app.dependency_overrides.pop(get_runtime_tool_registry, None)
