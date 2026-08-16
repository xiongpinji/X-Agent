from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from backend.app.core.collaboration.store import collaboration_store
from backend.app.core.memory.store import MemorySystem
from backend.app.core.org import (
    ConsoleBootstrapResponse,
    RoleCatalog,
    organization_store,
)
from backend.app.core.runs import RunStore
from backend.app.core.security import ROLE_SCOPES, Principal
from backend.app.core.tools import ToolRegistry
from backend.app.dependencies import (
    enforce_scope,
    get_current_principal,
    get_memory,
    get_rbac_policy,
    get_run_store,
    get_runtime_tool_registry,
)
from backend.app.settings import get_settings

router = APIRouter(prefix="/api/v1/workbench", tags=["workbench"])
extended_router = APIRouter(prefix="/api/v1/workbench", tags=["workbench-extended"])  # C2: unmounted


def get_workbench_principal(request: Request) -> Principal:
    """Resolve principal for first-run workbench bootstrap.

    In development mode the workbench is allowed to bootstrap with a local
    default principal so the product entrypoint is visible without setup. Other
    protected APIs still use get_current_principal directly and reject anonymous
    access.
    """
    settings = get_settings()
    has_credentials = bool(
        request.headers.get("x-api-key")
        or request.headers.get("authorization")
    )
    if (
        not has_credentials
        and not settings.require_api_key
        and getattr(settings, "app_mode", "development") != "production"
    ):
        return Principal(
            tenant_id="default",
            user_id="anonymous",
            role="user",
            scopes=list(ROLE_SCOPES.get("user", [])),
            authenticated=True,
        )
    return get_current_principal(request)


PrincipalDependency = Annotated[Principal, Depends(get_workbench_principal)]
RunStoreDependency = Annotated[RunStore, Depends(get_run_store)]
MemoryDependency = Annotated[MemorySystem, Depends(get_memory)]
ToolRegistryDependency = Annotated[ToolRegistry, Depends(get_runtime_tool_registry)]


class WorkbenchTaskRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    kind: str = Field(default="general", max_length=80)
    metadata: dict[str, object] = Field(default_factory=dict)


@router.get("", response_model=ConsoleBootstrapResponse)
async def get_workbench(
    principal: PrincipalDependency,
    run_store: RunStoreDependency,
    memory: MemoryDependency,
    tools: ToolRegistryDependency,
) -> ConsoleBootstrapResponse:
    """Project tenant-scoped runtime state without starting any work."""
    enforce_scope(principal, "tools:read")
    tenant_id = principal.tenant_id
    policy = get_rbac_policy()
    can_read_runs = policy.has_scope(principal, "agent:read")
    can_read_memory = policy.has_scope(principal, "memory:read")
    can_read_collaboration = policy.has_scope(principal, "agent:read")
    can_stream_messages = policy.has_scope(principal, "agent:run")
    runs = (
        [
            record
            for record in run_store.list(limit=max(run_store.count(), 1))
            if record.tenant_id == tenant_id
        ]
        if can_read_runs
        else []
    )
    run_items = [record.model_dump(mode="json") for record in runs]
    active_runs = [item for item in run_items if item.get("status") == "running"]

    memory_available = can_read_memory and hasattr(memory, "export_bundle")
    if memory_available:
        memory_bundle = memory.export_bundle(tenant_id=tenant_id)
        memory_items = [item.model_dump(mode="json") for item in memory_bundle.memories]
        sessions = [session.model_dump(mode="json") for session in memory_bundle.sessions]
    else:
        memory_items = []
        sessions = []

    organizations = (
        organization_store.list_organizations(tenant_id=tenant_id)
        if can_read_collaboration
        else []
    )
    organization_graph: dict[str, object] = {
        "availability": "available" if can_read_collaboration else "unavailable",
        "organization": None,
        "departments": [],
        "role_templates": [],
        "agent_instances": [],
        "meeting_rooms": [],
        "nodes": [],
        "edges": [],
    }
    if organizations:
        graph = organization_store.build_organization_graph(organizations[0].org_id)
        if graph is not None:
            organization_graph = graph.model_dump(mode="json")
            organization_graph["availability"] = "available"
            organization_graph["role_templates"] = []
            organization_graph["meeting_rooms"] = []
            organization_graph["agent_instances"] = [
                {**agent, "role_template_id": ""}
                for agent in organization_graph.get("agent_instances", [])
            ]
            organization_graph["nodes"] = [
                node
                for node in organization_graph.get("nodes", [])
                if node.get("node_type") not in {"role_template", "meeting_room"}
            ]
            node_ids = {node["node_id"] for node in organization_graph["nodes"]}
            organization_graph["edges"] = [
                edge
                for edge in organization_graph.get("edges", [])
                if edge.get("source_id") in node_ids and edge.get("target_id") in node_ids
            ]

    rooms = (
        collaboration_store.list_rooms(tenant_id=tenant_id)
        if can_read_collaboration
        else []
    )
    room_items = [room.model_dump(mode="json") for room in rooms]
    tool_items = tools.manifest()

    from backend.app.core import skills_registry

    cached_skill_registry = skills_registry._skill_registry
    skill_items = (
        [skill.to_dict() for skill in cached_skill_registry.list_skills()]
        if cached_skill_registry is not None
        else []
    )
    skills_availability = "available" if cached_skill_registry is not None else "unavailable"
    now = datetime.now(UTC)
    return ConsoleBootstrapResponse(
        console={"mode": "unified_console", "tenant_id": tenant_id, "org_id": organizations[0].org_id if organizations else None, "agent_id": principal.agent_id, "session_id": principal.session_id, "user_id": principal.user_id, "created_at": principal.created_at, "server_time": now},
        dispatch={"availability": "unavailable", "status": "unavailable", "actions": [], "pending": [], "queue_size": 0, "last_result": None},
        collaboration={
            "availability": "available" if can_read_collaboration else "unavailable",
            "rooms": room_items,
            "online_agents": [],
            "active_threads": [],
            "handoff_available": False,
        },
        workflow={
            "availability": "unavailable",
            "templates": [],
            "active": [],
            "can_create": False,
        },
        execution={
            "availability": "available" if can_read_runs else "unavailable",
            "count": len(run_items),
            "runs": run_items,
            "active_runs": active_runs,
        },
        role_catalog=RoleCatalog(),
        organization_graph=organization_graph,
        meeting_rooms={"availability": "available" if can_read_collaboration else "unavailable", "rooms": room_items, "active_room": None, "room_members": [], "room_topics": [], "room_messages": [], "room_tasks": [], "room_summary": {}},
        realtime={"availability": "available" if can_stream_messages else "unavailable", "conversations": [], "messages": [], "presence": {}, "unread_count": 0, "online_agents": [], "typing_agents": [], "last_message_at": None},
        ui={"availability": "unavailable", "panels": [], "routes": [], "shortcuts": [], "actions": [], "badges": []},
        avatars=[],
        tools={"availability": "available", "items": tool_items, "available": [item["name"] for item in tool_items], "count": len(tool_items), "skills": {"availability": skills_availability, "items": skill_items, "count": len(skill_items)}},
        entries=[
            {"id": "chat", "label": "Chat", "path": "/chat"},
            {"id": "workbench", "label": "Workbench", "path": "/api/v1/workbench"},
        ],
        workflows={"availability": "unavailable", "templates": [], "active_workflows": [], "workflow_states": {}, "workflow_links": []},
        memory={"availability": "available" if memory_available else "unavailable", "count": len(memory_items), "items": memory_items, "sessions": sessions, "session_summary": {}, "agent_summary": {}, "department_summary": {}, "layer_totals": {}, "memory_refs": [item["id"] for item in memory_items]},
        permissions={"scope": list(principal.scopes), "can_create_agent": policy.has_scope(principal, "agent:run"), "can_create_room": policy.has_scope(principal, "agent:run"), "can_manage_org": policy.has_scope(principal, "security:manage"), "can_read_memory": can_read_memory, "can_send_message": can_stream_messages, "can_trigger_execution": policy.has_scope(principal, "agent:run"), "can_approve": policy.has_scope(principal, "security:manage"), "can_audit": policy.has_scope(principal, "audit:read")},
    )


@extended_router.post("/tasks")
async def create_workbench_task(request: WorkbenchTaskRequest, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    return {
        "task_id": f"workbench-task-{abs(hash((request.title, principal.user_id))) % 10_000_000}",
        "title": request.title,
        "description": request.description,
        "kind": request.kind,
        "metadata": request.metadata,
        "status": "accepted",
    }
