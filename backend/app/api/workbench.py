from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.core.dispatch import DispatchRequest, dispatch
from backend.app.core.org import ConsoleBootstrapResponse, ConsoleContext, RoleAvatar, build_default_role_catalog, organization_store
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/workbench", tags=["workbench"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


class WorkbenchTaskRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    kind: str = Field(default="general", max_length=80)
    metadata: dict[str, object] = Field(default_factory=dict)


@router.get("", response_model=ConsoleBootstrapResponse)
async def get_workbench(principal: PrincipalDependency) -> ConsoleBootstrapResponse:
    enforce_scope(principal, "tools:read")
    tools = ["agent", "memory", "workflow", "browser", "desktop", "plugins", "open_source"]
    dispatch_result = dispatch(
        DispatchRequest(
            org_id=principal.tenant_id,
            agent_id=principal.agent_id,
            session_id=principal.session_id,
            trace_id=principal.trace_id,
            task="workbench overview",
            task_type="overview",
            mode="suggest",
            replay_hint=True,
        )
    )
    role_catalog = build_default_role_catalog()
    organization_graph = organization_store.build_organization_graph(principal.tenant_id) if principal.tenant_id else None
    avatars = [
        RoleAvatar(avatar_id="avatar-ceo", role_name="总经理", display_name="总经理", category="leadership", style="executive", icon_type="portrait", expression="confident", outfit="suit", palette=["#0F172A", "#1D4ED8", "#F59E0B"], badge="CEO", status_variants={"online": "/avatars/ceo_online.png", "busy": "/avatars/ceo_busy.png", "in_meeting": "/avatars/ceo_meeting.png"}, graph_variant="ceo_graph", chat_variant="ceo_chat", meeting_variant="ceo_meeting", thumbnail_url="/avatars/ceo_thumb.png", full_image_url="/avatars/ceo_full.png", alt_text="总经理形象头像", usage=["organization_graph", "chat", "meeting_room", "agent_card", "role_catalog"], tags=["executive", "formal", "leadership"]),
        RoleAvatar(avatar_id="avatar-legal", role_name="法律顾问", display_name="法务顾问", category="legal", style="formal", icon_type="portrait", expression="strict", outfit="business_formal", palette=["#0F172A", "#334155", "#94A3B8"], badge="LEGAL", status_variants={"online": "/avatars/legal_online.png", "busy": "/avatars/legal_busy.png"}, graph_variant="legal_graph", chat_variant="legal_chat", meeting_variant="legal_meeting", thumbnail_url="/avatars/legal_thumb.png", full_image_url="/avatars/legal_full.png", alt_text="法务顾问形象头像", usage=["organization_graph", "chat", "meeting_room", "agent_card", "role_catalog"], tags=["formal", "strict", "risk_averse"]),
        RoleAvatar(avatar_id="avatar-finance", role_name="财务会计", display_name="财务会计", category="finance", style="business", icon_type="portrait", expression="thoughtful", outfit="office_uniform", palette=["#1D4ED8", "#10B981", "#CBD5E1"], badge="FINANCE", status_variants={"online": "/avatars/finance_online.png", "reviewing": "/avatars/finance_reviewing.png"}, graph_variant="finance_graph", chat_variant="finance_chat", meeting_variant="finance_meeting", thumbnail_url="/avatars/finance_thumb.png", full_image_url="/avatars/finance_full.png", alt_text="财务会计形象头像", usage=["organization_graph", "chat", "meeting_room", "agent_card", "role_catalog"], tags=["careful", "structured", "finance"]),
        RoleAvatar(avatar_id="avatar-engineering", role_name="编程大牛", display_name="编程大牛", category="engineering", style="technical", icon_type="portrait", expression="focused", outfit="techwear", palette=["#111827", "#06B6D4", "#A855F7"], badge="ENGINEERING", status_variants={"online": "/avatars/eng_online.png", "executing": "/avatars/eng_executing.png"}, graph_variant="eng_graph", chat_variant="eng_chat", meeting_variant="eng_meeting", thumbnail_url="/avatars/eng_thumb.png", full_image_url="/avatars/eng_full.png", alt_text="编程大牛形象头像", usage=["organization_graph", "chat", "meeting_room", "agent_card", "role_catalog"], tags=["technical", "focused", "expert"]),
        RoleAvatar(avatar_id="avatar-content-director", role_name="短剧导演", display_name="短剧导演", category="content", style="creative", icon_type="portrait", expression="energetic", outfit="director_style", palette=["#F97316", "#1F2937", "#FB7185"], badge="CONTENT", status_variants={"online": "/avatars/content_online.png", "in_meeting": "/avatars/content_meeting.png"}, graph_variant="content_graph", chat_variant="content_chat", meeting_variant="content_meeting", thumbnail_url="/avatars/content_thumb.png", full_image_url="/avatars/content_full.png", alt_text="短剧导演形象头像", usage=["organization_graph", "chat", "meeting_room", "agent_card", "role_catalog"], tags=["creative", "director", "video"]),
        RoleAvatar(avatar_id="avatar-design", role_name="设计师", display_name="设计师", category="design", style="creative", icon_type="portrait", expression="inspired", outfit="creative_casual", palette=["#8B5CF6", "#EC4899", "#22C55E"], badge="DESIGN", status_variants={"online": "/avatars/design_online.png", "reviewing": "/avatars/design_reviewing.png"}, graph_variant="design_graph", chat_variant="design_chat", meeting_variant="design_meeting", thumbnail_url="/avatars/design_thumb.png", full_image_url="/avatars/design_full.png", alt_text="设计师形象头像", usage=["organization_graph", "chat", "meeting_room", "agent_card", "role_catalog"], tags=["creative", "visual", "ui"]),
        RoleAvatar(avatar_id="avatar-admin", role_name="管理员", display_name="管理员", category="administration", style="system", icon_type="portrait", expression="calm", outfit="system_admin", palette=["#64748B", "#0EA5E9", "#E2E8F0"], badge="ADMIN", status_variants={"online": "/avatars/admin_online.png", "busy": "/avatars/admin_busy.png"}, graph_variant="admin_graph", chat_variant="admin_chat", meeting_variant="admin_meeting", thumbnail_url="/avatars/admin_thumb.png", full_image_url="/avatars/admin_full.png", alt_text="管理员形象头像", usage=["organization_graph", "chat", "meeting_room", "agent_card", "role_catalog"], tags=["system", "stable", "admin"]),
    ]
    return ConsoleBootstrapResponse(
        console={"mode": "unified_console", "tenant_id": principal.tenant_id, "org_id": principal.tenant_id, "agent_id": principal.agent_id, "session_id": principal.session_id, "user_id": principal.user_id, "created_at": principal.created_at, "server_time": principal.created_at},
        dispatch=dispatch_result.model_dump(mode="json"),
        role_catalog=role_catalog,
        organization_graph=organization_graph.model_dump(mode="json") if organization_graph else {},
        meeting_rooms={"rooms": [], "active_room": None, "room_members": [], "room_topics": [], "room_messages": [], "room_tasks": [], "room_summary": {}},
        realtime={"conversations": [], "messages": [], "presence": {}, "unread_count": 0, "online_agents": [], "typing_agents": [], "last_message_at": None},
        ui={"panels": [{"id": "create_agent", "title": "创建智能体", "kind": "form"}, {"id": "organization_graph", "title": "组织架构图", "kind": "graph"}, {"id": "meeting_rooms", "title": "会议室", "kind": "room_list"}, {"id": "realtime_messages", "title": "实时通讯", "kind": "message_stream"}], "routes": [{"path": "/console/overview"}, {"path": "/console/agents/create"}, {"path": "/console/organization"}, {"path": "/console/rooms"}, {"path": "/console/chat"}], "shortcuts": [], "actions": [], "badges": []},
        avatars=avatars,
        workflows={"templates": [wf.model_dump(mode="json") for wf in role_catalog.workflows], "active_workflows": [], "workflow_states": {}, "workflow_links": []},
        memory={"session_summary": {}, "agent_summary": {}, "department_summary": {}, "layer_totals": {}, "memory_refs": []},
        permissions={"scope": ["tools:read", "agent:run", "memory:read"], "can_create_agent": True, "can_create_room": True, "can_manage_org": True, "can_read_memory": True, "can_send_message": True, "can_trigger_execution": True, "can_approve": True, "can_audit": True},
    )


@router.post("/tasks")
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
