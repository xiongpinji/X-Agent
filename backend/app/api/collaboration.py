from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.api.messages import UnifiedMessageEvent, build_channel_key, message_event_bus
from backend.app.core.collaboration import collaboration_store
from backend.app.core.contracts import ErrorCode
from backend.app.core.memory import MemoryScope, MemorySystem
from backend.app.core.security import Principal
from backend.app.core.workflows import WorkflowChatCreateRequest
from backend.app.dependencies import enforce_scope, get_current_principal, get_memory

router = APIRouter(prefix="/api/v1/collaboration", tags=["collaboration"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
MemoryDependency = Annotated[object, Depends(get_memory)]


class CollaborationRoomCreateRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=200)
    tenant_id: str = "default"
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
    room = collaboration_store.create_room(
        topic=request.topic,
        tenant_id=request.tenant_id,
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
    return [room.model_dump(mode="json") for room in collaboration_store.list_rooms(tenant_id=tenant_id)]


@router.get("/rooms/{room_id}")
async def get_room(room_id: str, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    room = collaboration_store.get_room(room_id)
    if room is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Collaboration room not found.", details={"resource_type": "collaboration_room", "resource_id": room_id})
    return room.model_dump(mode="json")


@router.get("/rooms/{room_id}/correlation")
async def get_room_correlation(room_id: str, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    room = collaboration_store.get_room(room_id)
    if room is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Collaboration room not found.", details={"resource_type": "collaboration_room", "resource_id": room_id})
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
    room = collaboration_store.get_room(room_id)
    if room is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Collaboration room not found.", details={"resource_type": "collaboration_room", "resource_id": room_id})
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
        room.memory_refs.append(memory_id)
        agent_key = str(metadata.get("agent_id") or message.sender_id)
        if agent_key:
            room.agent_memory_refs.setdefault(agent_key, []).append(memory_id)
        department_key = str(metadata.get("department_id") or "")
        if department_key:
            room.department_memory_refs.setdefault(department_key, []).append(memory_id)
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
    room = collaboration_store.get_room(room_id)
    if room is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Collaboration room not found.", details={"resource_type": "collaboration_room", "resource_id": room_id})
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
        channel_key = build_channel_key(tenant_id=room.tenant_id, room_id=room.room_id, conversation_id=str(request.metadata.get("conversation_id") or "") or None, agent_id=principal.agent_id, user_id=principal.user_id, trace_id=principal.trace_id)
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
    room = collaboration_store.get_room(room_id)
    if room is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Collaboration room not found.", details={"resource_type": "collaboration_room", "resource_id": room_id})
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
