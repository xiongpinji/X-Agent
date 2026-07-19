"""Collaboration chat-room API.

Tenant convergence (P1-09): non-admin principals are pinned to their own
``principal.tenant_id`` — a mismatched explicit ``tenant_id`` is rejected with
403, and cross-tenant room access answers 404 (no existence leak). Admins may
address any tenant explicitly.

Persistence: rooms live in the in-memory CollaborationStore by default
(**dev-only: lost on restart**). Set ``XAGENT_COLLABORATION_STORE_PATH`` to a
JSON file path to enable durable snapshot persistence.

Runtime delegation: ``POST /delegate`` runs a real sub-AgentLoop via the
collaboration delegator (capability match + round-robin load balancing,
core.dispatch ranking when org hints are present).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.api.messages import UnifiedMessageEvent, build_channel_key, message_event_bus
from backend.app.core.collaboration import collaboration_store
from backend.app.core.collaboration.delegation import (
    CandidateSpec,
    DelegationRequest,
    NoCapableAgentError,
    get_delegator,
)
from backend.app.core.collaboration.store import CollaborationRoom
from backend.app.core.contracts import ErrorCode
from backend.app.core.memory import MemoryScope, MemorySystem
from backend.app.core.security import Principal
from backend.app.core.workflows import WorkflowChatCreateRequest
from backend.app.dependencies import enforce_scope, get_current_principal, get_memory

router = APIRouter(prefix="/api/v1/collaboration", tags=["collaboration"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
MemoryDependency = Annotated[object, Depends(get_memory)]


def _resolve_tenant(principal: Principal, requested: str | None) -> str:
    """Converge the effective tenant onto the principal.

    Non-admins may omit ``requested`` (defaults to their own tenant) or repeat
    their own tenant; anything else is a 403 tenant-isolation violation — the
    same contract as the browser session API. Admins may address any tenant.
    """
    if requested is None or requested == "":
        return principal.tenant_id
    if principal.role != "admin" and requested != principal.tenant_id:
        raise api_error(
            403,
            ErrorCode.AUTHORIZATION_FAILED,
            f"Cannot act on tenant '{requested}'. You can only act on your own tenant '{principal.tenant_id}'.",
        )
    return requested


def _get_room_for_principal(room_id: str, principal: Principal) -> CollaborationRoom:
    """Fetch a room enforcing tenant convergence.

    Cross-tenant access by non-admins answers 404 (identical to a missing
    room) so room existence does not leak across tenants.
    """
    room = collaboration_store.get_room(room_id)
    if room is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Collaboration room not found.", details={"resource_type": "collaboration_room", "resource_id": room_id})
    if principal.role != "admin" and room.tenant_id != principal.tenant_id:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Collaboration room not found.", details={"resource_type": "collaboration_room", "resource_id": room_id})
    return room


class CollaborationRoomCreateRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=200)
    tenant_id: str | None = None
    members: list[str] = Field(default_factory=list)
    invited_role_template_ids: list[str] = Field(default_factory=list)
    department_id: str | None = None


class CollaborationMessageCreateRequest(BaseModel):
    sender_id: str = Field(..., min_length=1)
    sender_type: str = Field(default="agent", min_length=1)
    content: str = Field(..., min_length=1)
    message_type: str = Field(default="text", max_length=40)
    reply_to_message_id: str | None = None
    mentions: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


@router.post("/rooms")
async def create_room(request: CollaborationRoomCreateRequest, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    tenant_id = _resolve_tenant(principal, request.tenant_id)
    room = collaboration_store.create_room(
        topic=request.topic,
        tenant_id=tenant_id,
        created_by=principal.user_id,
        members=request.members,
        memory_scope={
            "department_id": request.department_id or "",
            "invited_role_template_ids": ",".join(request.invited_role_template_ids),
        },
    )
    channel_key = build_channel_key(tenant_id=room.tenant_id, room_id=room.room_id, agent_id=principal.agent_id, user_id=principal.user_id, trace_id=principal.trace_id)
    await message_event_bus.publish(
        channel_key,
        UnifiedMessageEvent(
            event_type="room.created",
            trace_id=principal.trace_id,
            tenant_id=room.tenant_id,
            room_id=room.room_id,
            agent_id=principal.agent_id,
            user_id=principal.user_id,
            channel_type="room",
            payload={"room": room.model_dump(mode="json")},
        ),
    )
    return room.model_dump(mode="json")


@router.get("/rooms")
async def list_rooms(principal: PrincipalDependency, tenant_id: str | None = None) -> list[dict[str, object]]:
    enforce_scope(principal, "agent:run")
    # Tenant convergence: non-admins are always pinned to their own tenant;
    # passing a different tenant_id is a 403 violation instead of a silent
    # cross-tenant listing (the old direct pass-through behavior).
    effective_tenant = _resolve_tenant(principal, tenant_id) if tenant_id else principal.tenant_id
    if principal.role == "admin":
        effective_tenant = tenant_id  # admins may list any tenant, or all when omitted
    return [room.model_dump(mode="json") for room in collaboration_store.list_rooms(tenant_id=effective_tenant)]


@router.get("/rooms/{room_id}")
async def get_room(room_id: str, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    room = _get_room_for_principal(room_id, principal)
    return room.model_dump(mode="json")


@router.get("/rooms/{room_id}/correlation")
async def get_room_correlation(room_id: str, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    room = _get_room_for_principal(room_id, principal)
    trace_id = room.room_id
    return {
        "room_id": room.room_id,
        "trace_id": trace_id,
        "resource_type": "collaboration_room",
        "resource_id": room.room_id,
        "status": room.status,
        "trace_summary": {
            "trace_id": trace_id,
            "event_count": len(room.messages),
            "started_at": room.created_at,
            "ended_at": room.updated_at if room.status != "active" else None,
            "last_event": room.messages[-1].content if room.messages else "collaboration.room.created",
            "task": room.topic,
            "snapshot": {
                "room_id": room.room_id,
                "tenant_id": room.tenant_id,
                "status": room.status,
                "member_count": len(room.members),
                "message_count": len(room.messages),
            },
        },
        "snapshot": {
            "room_id": room.room_id,
            "tenant_id": room.tenant_id,
            "status": room.status,
            "member_count": len(room.members),
            "message_count": len(room.messages),
        },
    }


@router.post("/rooms/{room_id}/memory-sync")
async def sync_room_memory(room_id: str, principal: PrincipalDependency, memory: MemoryDependency) -> dict[str, object]:
    enforce_scope(principal, "memory:write")
    room = _get_room_for_principal(room_id, principal)
    if not hasattr(memory, "store"):
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "Current memory backend does not support syncing.")
    context = _memory_context_from_principal(principal)
    shared_scope = MemoryScope(
        owner_agent_id=principal.agent_id,
        share_scope="room",
        visibility="shared",
        room_id=room.room_id,
        task_id=room.room_id,
    )
    synced_ids: list[str] = []
    for message in room.messages[-20:]:
        metadata = dict(message.metadata)
        memory_id = await memory.store(
            context,
            content=message.content,
            layer=7,
            importance=0.65,
            tags=["collaboration", "room", room.topic],
            metadata={
                **metadata,
                "room_id": room.room_id,
                "message_id": message.message_id,
                "sender_id": message.sender_id,
                "sender_type": message.sender_type,
                "source": "collaboration_room",
            },
            session_id=room.room_id,
            scope=shared_scope,
        )
        synced_ids.append(memory_id)
        # Route ref bookkeeping through the store so optional persistence
        # captures it (direct room mutation would bypass snapshot writes).
        collaboration_store.add_memory_ref(room.room_id, memory_id)
        agent_key = str(metadata.get("agent_id") or message.sender_id)
        if agent_key:
            collaboration_store.add_agent_memory_ref(room.room_id, agent_key, memory_id)
        department_key = str(metadata.get("department_id") or "")
        if department_key:
            collaboration_store.add_department_memory_ref(room.room_id, department_key, memory_id)
        if hasattr(memory, "route_shared_memory"):
            memory.route_shared_memory(memory_id)
    return {
        "room_id": room.room_id,
        "synced_count": len(synced_ids),
        "memory_ids": synced_ids,
        "room_memory_refs": list(room.memory_refs),
        "agent_memory_refs": {agent_id: list(refs) for agent_id, refs in room.agent_memory_refs.items()},
        "department_memory_refs": {department_id: list(refs) for department_id, refs in room.department_memory_refs.items()},
        "scope": shared_scope.model_dump(mode="json"),
    }


@router.get("/rooms/{room_id}/workflow-suggestion")
async def get_room_workflow_suggestion(room_id: str, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "workflow:create")
    room = _get_room_for_principal(room_id, principal)
    topic = room.topic.strip() or "协作任务"
    lower = f"{topic} {' '.join(message.content for message in room.messages[-5:])}".lower()
    nodes = [
        {"id": "input", "type": "input"},
        {"id": "collaboration", "type": "agent", "config": {"role": "collaborator"}},
    ]
    edges = [{"source": "input", "target": "collaboration"}]
    if any(keyword in lower for keyword in ["审批", "approval", "审核"]):
        nodes.extend([
            {"id": "approval", "type": "approval"},
            {"id": "output", "type": "output"},
        ])
        edges.extend([
            {"source": "collaboration", "target": "approval"},
            {"source": "approval", "target": "output"},
        ])
    elif any(keyword in lower for keyword in ["浏览器", "网页", "web", "browser", "页面"]):
        nodes.extend([
            {"id": "browser", "type": "tool", "config": {"tool": "browser"}},
            {"id": "output", "type": "output"},
        ])
        edges.extend([
            {"source": "collaboration", "target": "browser"},
            {"source": "browser", "target": "output"},
        ])
    else:
        nodes.append({"id": "output", "type": "output"})
        edges.append({"source": "collaboration", "target": "output"})
    return {
        "room_id": room.room_id,
        "topic": room.topic,
        "suggested_nodes": nodes,
        "suggested_edges": edges,
        "snapshot": {
            "room_id": room.room_id,
            "topic": room.topic,
            "message_count": len(room.messages),
            "suggested_node_count": len(nodes),
            "suggested_edge_count": len(edges),
        },
    }


@router.post("/rooms/{room_id}/members")
async def add_member(room_id: str, request: dict[str, str], principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    member_id = request.get("member_id")
    if not member_id:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "member_id is required.")
    _get_room_for_principal(room_id, principal)
    try:
        room = collaboration_store.add_member(room_id, member_id)
    except (KeyError, ValueError):
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Collaboration room not found.", details={"resource_type": "collaboration_room", "resource_id": room_id})
    channel_key = build_channel_key(tenant_id=room.tenant_id, room_id=room.room_id, agent_id=principal.agent_id, user_id=principal.user_id, trace_id=principal.trace_id)
    await message_event_bus.publish(
        channel_key,
        UnifiedMessageEvent(
            event_type="room.member_added",
            trace_id=principal.trace_id,
            tenant_id=room.tenant_id,
            room_id=room.room_id,
            agent_id=principal.agent_id,
            user_id=principal.user_id,
            channel_type="room",
            payload={"room": room.model_dump(mode="json"), "member_id": member_id},
        ),
    )
    return room.model_dump(mode="json")


@router.post("/rooms/{room_id}/messages")
async def post_message(room_id: str, request: CollaborationMessageCreateRequest, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    _get_room_for_principal(room_id, principal)
    try:
        message = collaboration_store.post_message(
            room_id,
            sender_id=request.sender_id,
            sender_type=request.sender_type,
            content=request.content,
            metadata={
                **request.metadata,
                "agent_id": request.metadata.get("agent_id") or principal.agent_id,
            },
        )
    except (KeyError, ValueError):
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Collaboration room not found.", details={"resource_type": "collaboration_room", "resource_id": room_id})
    room = collaboration_store.get_room(room_id)
    if room is not None:
        # Route message events on the room-level channel key (no conversation_id
        # dimension) so room subscribers receive them, matching room.created /
        # member_added / workflow.updated / room.closed. The conversation_id is
        # still preserved on the event object and payload for consumers.
        channel_key = build_channel_key(tenant_id=room.tenant_id, room_id=room.room_id, agent_id=principal.agent_id, user_id=principal.user_id, trace_id=principal.trace_id)
        await message_event_bus.publish(
            channel_key,
            UnifiedMessageEvent(
                event_type="message.created",
                trace_id=principal.trace_id,
                tenant_id=room.tenant_id,
                room_id=room.room_id,
                conversation_id=str(request.metadata.get("conversation_id") or "") or None,
                agent_id=principal.agent_id,
                user_id=principal.user_id,
                channel_type="room",
                payload={"message": message.model_dump(mode="json"), "room": room.model_dump(mode="json")},
            ),
        )
    return message.model_dump(mode="json")


@router.post("/rooms/{room_id}/workflow-suggestion")
async def suggest_workflow_from_room(room_id: str, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    room = _get_room_for_principal(room_id, principal)
    transcript = "\n".join(message.content for message in room.messages[-8:])
    topic = room.topic
    prompt = f"{topic}\n{transcript}".strip()
    suggestion = _build_workflow_suggestion(prompt)
    result = {
        "room_id": room.room_id,
        "topic": room.topic,
        "suggested_nodes": suggestion["nodes"],
        "suggested_edges": suggestion["edges"],
        "snapshot": {
            "room_id": room.room_id,
            "member_count": len(room.members),
            "message_count": len(room.messages),
            "suggested_node_count": len(suggestion["nodes"]),
            "suggested_edge_count": len(suggestion["edges"]),
        },
    }
    channel_key = build_channel_key(tenant_id=room.tenant_id, room_id=room.room_id, agent_id=principal.agent_id, user_id=principal.user_id, trace_id=principal.trace_id)
    await message_event_bus.publish(
        channel_key,
        UnifiedMessageEvent(
            event_type="workflow.updated",
            trace_id=principal.trace_id,
            tenant_id=room.tenant_id,
            room_id=room.room_id,
            agent_id=principal.agent_id,
            user_id=principal.user_id,
            channel_type="workflow",
            payload={"workflow_suggestion": result},
        ),
    )
    return result


@router.post("/rooms/{room_id}/close")
async def close_room(room_id: str, principal: PrincipalDependency) -> dict[str, bool]:
    enforce_scope(principal, "agent:run")
    _get_room_for_principal(room_id, principal)
    try:
        room = collaboration_store.close_room(room_id)
    except (KeyError, ValueError):
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Collaboration room not found.", details={"resource_type": "collaboration_room", "resource_id": room_id})
    channel_key = build_channel_key(tenant_id=room.tenant_id, room_id=room.room_id, agent_id=principal.agent_id, user_id=principal.user_id, trace_id=principal.trace_id)
    await message_event_bus.publish(
        channel_key,
        UnifiedMessageEvent(
            event_type="room.closed",
            trace_id=principal.trace_id,
            tenant_id=room.tenant_id,
            room_id=room.room_id,
            agent_id=principal.agent_id,
            user_id=principal.user_id,
            channel_type="room",
            payload={"room": room.model_dump(mode="json")},
        ),
    )
    return {"closed": True}


# ---------------------------------------------------------------------------
# Runtime delegation (P1-09)
# ---------------------------------------------------------------------------


class DelegationCandidateModel(BaseModel):
    agent_id: str = Field(..., min_length=1)
    agent_type: str = "subagent"
    capabilities: list[str] = Field(default_factory=list)


class DelegationRequestModel(BaseModel):
    task: str = Field(..., min_length=1)
    required_capabilities: list[str] = Field(default_factory=list)
    candidates: list[DelegationCandidateModel] = Field(default_factory=list)
    org_id: str | None = None
    department_id: str | None = None
    room_id: str | None = None
    tenant_id: str | None = None
    isolation: str | None = None
    wait: bool = True
    timeout_seconds: int = Field(default=600, ge=1, le=86400)
    max_iterations: int = Field(default=10, ge=1, le=100)
    metadata: dict[str, object] = Field(default_factory=dict)


@router.post("/delegate")
async def delegate_task(request: DelegationRequestModel, principal: PrincipalDependency) -> dict[str, object]:
    """Delegate a task to a capability-matched sub-agent running a real AgentLoop.

    Load balancing is round-robin over the capability-matched pool; org hints
    additionally rank candidates via core.dispatch. Failures are explicit:
    422 when no candidate is capable, 400 for invalid input (e.g. unsupported
    isolation), 429 when the spawner's concurrency cap is reached.
    """
    enforce_scope(principal, "agent:run")
    tenant_id = _resolve_tenant(principal, request.tenant_id)
    if request.room_id:
        _get_room_for_principal(request.room_id, principal)
    try:
        result = await get_delegator().delegate(
            DelegationRequest(
                task=request.task,
                required_capabilities=request.required_capabilities,
                candidates=[
                    CandidateSpec(
                        agent_id=candidate.agent_id,
                        agent_type=candidate.agent_type,
                        capabilities=candidate.capabilities,
                    )
                    for candidate in request.candidates
                ],
                org_id=request.org_id,
                department_id=request.department_id,
                room_id=request.room_id,
                tenant_id=tenant_id,
                user_id=principal.user_id,
                isolation=request.isolation,
                wait=request.wait,
                timeout_seconds=request.timeout_seconds,
                max_iterations=request.max_iterations,
                metadata={
                    **request.metadata,
                    "agent_id": principal.agent_id,
                    "trace_id": principal.trace_id,
                    "request_id": principal.request_id,
                    "delegator": principal.user_id,
                },
            )
        )
    except NoCapableAgentError as exc:
        raise api_error(422, ErrorCode.VALIDATION_ERROR, str(exc)) from exc
    except (NotImplementedError, ValueError) as exc:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, str(exc)) from exc
    except RuntimeError as exc:
        # Spawner concurrency cap (and other runtime delegation failures).
        raise api_error(429, ErrorCode.RATE_LIMIT_EXCEEDED, str(exc)) from exc
    return result.model_dump(mode="json")


@router.get("/delegations")
async def list_delegations(principal: PrincipalDependency, tenant_id: str | None = None, limit: int = 50) -> list[dict[str, object]]:
    enforce_scope(principal, "agent:run")
    if principal.role == "admin":
        effective_tenant = tenant_id  # admins: any tenant, or all when omitted
    else:
        effective_tenant = _resolve_tenant(principal, tenant_id) if tenant_id else principal.tenant_id
    return [item.model_dump(mode="json") for item in get_delegator().list_delegations(tenant_id=effective_tenant, limit=limit)]


@router.get("/delegations/{delegation_id}")
async def get_delegation(delegation_id: str, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    result = get_delegator().get_delegation(delegation_id)
    if result is None or (principal.role != "admin" and result.tenant_id != principal.tenant_id):
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Delegation not found.", details={"resource_type": "delegation", "resource_id": delegation_id})
    return result.model_dump(mode="json")


def _memory_context_from_principal(principal: Principal):
    return type("MemoryContext", (), {
        "tenant_id": principal.tenant_id,
        "user_id": principal.user_id,
        "agent_id": principal.agent_id,
        "request_id": principal.request_id,
        "trace_id": principal.trace_id,
    })()


def _build_workflow_suggestion(prompt: str) -> dict[str, list[dict[str, object]]]:
    lower = prompt.lower()
    nodes = [{"id": "input", "type": "input"}]
    edges: list[dict[str, object]] = []
    if any(keyword in lower for keyword in ["审批", "approval", "审核"]):
        nodes.extend([
            {"id": "agent_plan", "type": "agent", "config": {"role": "planner"}},
            {"id": "approval", "type": "approval"},
            {"id": "output", "type": "output"},
        ])
        edges.extend([
            {"source": "input", "target": "agent_plan"},
            {"source": "agent_plan", "target": "approval"},
            {"source": "approval", "target": "output"},
        ])
    elif any(keyword in lower for keyword in ["浏览器", "网页", "web", "browser", "页面"]):
        nodes.extend([
            {"id": "agent_plan", "type": "agent", "config": {"role": "planner"}},
            {"id": "browser", "type": "tool", "config": {"tool": "browser"}},
            {"id": "output", "type": "output"},
        ])
        edges.extend([
            {"source": "input", "target": "agent_plan"},
            {"source": "agent_plan", "target": "browser"},
            {"source": "browser", "target": "output"},
        ])
    elif any(keyword in lower for keyword in ["群聊", "协作", "agent", "团队", "多智能体"]):
        nodes.extend([
            {"id": "collaboration", "type": "agent", "config": {"role": "collaboration"}},
            {"id": "output", "type": "output"},
        ])
        edges.extend([
            {"source": "input", "target": "collaboration"},
            {"source": "collaboration", "target": "output"},
        ])
    else:
        nodes.extend([
            {"id": "agent_plan", "type": "agent", "config": {"role": "planner"}},
            {"id": "output", "type": "output"},
        ])
        edges.extend([
            {"source": "input", "target": "agent_plan"},
            {"source": "agent_plan", "target": "output"},
        ])
    return {"nodes": nodes, "edges": edges}
