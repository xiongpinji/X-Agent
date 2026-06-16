from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from backend.app.api.workbench_resources_bff import router as workbench_resources_router
from backend.app.core.dispatch import DispatchRequest, dispatch
from backend.app.core.org import ConsoleBootstrapResponse, RoleAvatar, build_default_role_catalog, organization_store
from backend.app.core.security import ROLE_SCOPES, Principal
from backend.app.dependencies import enforce_scope, get_control_mode_store, get_current_principal
from backend.app.settings import get_settings

router = APIRouter(prefix="/api/v1/workbench", tags=["workbench"])


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


class WorkbenchTaskRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    kind: str = Field(default="general", max_length=80)
    metadata: dict[str, object] = Field(default_factory=dict)


class WorkbenchActivityItem(BaseModel):
    id: str
    title: str
    subtitle: str
    status: str
    tone: str
    time: str


class WorkbenchWorkflowRun(BaseModel):
    id: str
    name: str
    state: str
    progress: int = Field(ge=0, le=100)
    owner: str
    tone: str


class WorkbenchHomeResponse(BaseModel):
    brand: dict[str, str]
    summary: str
    metrics: dict[str, object]
    agent_activity: list[WorkbenchActivityItem]
    workflow_runs: list[WorkbenchWorkflowRun]
    control_summary: dict[str, object] = Field(default_factory=dict)
    runtime_capability_summary: dict[str, object] = Field(default_factory=dict)


def _token(value: object) -> str:
    raw = getattr(value, "value", value)
    return str(raw or "unknown")


def _count_statuses(records: list[object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        status = _token(getattr(record, "status", None))
        counts[status] = counts.get(status, 0) + 1
    return counts


def _latest_updated_at(records: list[object]) -> str | None:
    values = [getattr(record, "updated_at", None) for record in records]
    values = [value for value in values if value is not None]
    if not values:
        return None
    latest = max(values)
    isoformat = getattr(latest, "isoformat", None)
    return isoformat() if callable(isoformat) else str(latest)


def build_control_summary(control_store: object, tenant_id: str | None) -> dict[str, object]:
    """Build a read-only summary of plan/goal control state for Panda."""
    try:
        plans = list(control_store.list_plans(tenant_id=tenant_id, limit=100))  # type: ignore[attr-defined]
        goals = list(control_store.list_goals(tenant_id=tenant_id, limit=100))  # type: ignore[attr-defined]
    except Exception as exc:
        return {
            "source": "control_mode_store",
            "status": "unavailable",
            "read_only": True,
            "execute_enabled": False,
            "count_scope": "latest_100",
            "limit": 100,
            "error": str(exc),
            "boundary": "Control summary could not be loaded; no execution controls are exposed.",
        }

    latest = _latest_updated_at([*plans, *goals])
    return {
        "source": "control_mode_store",
        "status": "empty" if not plans and not goals else "available",
        "read_only": True,
        "execute_enabled": False,
        "count_scope": "latest_100",
        "limit": 100,
        "plan_count": len(plans),
        "goal_count": len(goals),
        "status_counts": {
            "plans": _count_statuses(plans),
            "goals": _count_statuses(goals),
        },
        "latest_updated_at": latest,
        "boundary": "Plan and goal state is displayed read-only; executing goals still requires explicit control API approval and is not exposed from Panda home.",
    }


def build_runtime_capability_summary() -> dict[str, object]:
    """Expose runtime capability gaps without promoting candidates to ready."""
    source_path = Path(".xagent_runtime/reports/current-mainline-runtime-vs-detached-candidates.json")
    if not source_path.exists():
        return {
            "source": "current-mainline-runtime-vs-detached-candidates",
            "source_status": "missing",
            "status": "unknown",
            "read_only": True,
            "execute_enabled": False,
            "ok": False,
            "summary": {},
            "issue_codes": ["runtime_capability_boundary_report_missing"],
            "next_actions": ["refresh_runtime_capability_boundary_report"],
            "boundary": "Runtime capability boundary report is missing; detached candidates are not treated as delivered mainline capability.",
        }

    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "source": "current-mainline-runtime-vs-detached-candidates",
            "source_status": "error",
            "status": "unknown",
            "read_only": True,
            "execute_enabled": False,
            "ok": False,
            "summary": {},
            "issue_codes": ["runtime_capability_boundary_report_unreadable"],
            "next_actions": ["refresh_runtime_capability_boundary_report"],
            "error": str(exc),
            "boundary": "Runtime capability boundary report could not be read; no detached candidate is promoted to mainline capability.",
        }

    current = payload.get("current_boundary") if isinstance(payload, dict) else {}
    current = current if isinstance(current, dict) else {}
    mainline = current.get("mainline_runtime_wired") if isinstance(current.get("mainline_runtime_wired"), list) else []
    tested = current.get("api_cli_tested_or_evidence_backed") if isinstance(current.get("api_cli_tested_or_evidence_backed"), list) else []
    frontend = current.get("frontend_verified") if isinstance(current.get("frontend_verified"), list) else []
    detached = current.get("detached_or_pure_payload_candidates") if isinstance(current.get("detached_or_pure_payload_candidates"), list) else []
    stale = current.get("stale_or_non_current_evidence") if isinstance(current.get("stale_or_non_current_evidence"), list) else []
    overclaims = payload.get("overclaim_findings") if isinstance(payload.get("overclaim_findings"), list) else []
    detached_count = sum(int(item.get("count") or 0) for item in detached if isinstance(item, dict))
    issue_codes: list[str] = []
    if detached_count:
        issue_codes.append("runtime_capability_not_integrated")
    if stale:
        issue_codes.append("runtime_capability_stale_evidence")
    if overclaims:
        issue_codes.append("runtime_capability_overclaim_risk")
    status = "needs_review" if issue_codes else "unknown"
    return {
        "source": "current-mainline-runtime-vs-detached-candidates",
        "source_status": str(payload.get("status") or "unknown"),
        "status": status,
        "read_only": True,
        "execute_enabled": False,
        "ok": False,
        "summary": {
            "mainline_wired_count": len(mainline),
            "api_cli_evidence_count": len(tested),
            "frontend_verified_count": len(frontend),
            "detached_candidate_count": detached_count,
            "stale_evidence_count": len(stale),
            "overclaim_finding_count": len(overclaims),
        },
        "issue_codes": issue_codes,
        "next_actions": list(payload.get("next_actions", [])) if isinstance(payload.get("next_actions"), list) else [],
        "boundary": "This summary is read from the current mainline-vs-detached boundary report. Detached or stale candidates are not delivered runtime capability until mainline adoption and current validation are verified.",
    }


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
        collaboration={
            "rooms": [],
            "online_agents": [],
            "active_threads": [],
            "handoff_available": True,
        },
        workflow={
            "templates": [wf.workflow_name for wf in role_catalog.workflows],
            "active": [],
            "can_create": True,
        },
        execution={
            "status": "ready",
            "active_runs": [],
            "sandbox": "available",
        },
        role_catalog=role_catalog,
        organization_graph=organization_graph.model_dump(mode="json") if organization_graph else {},
        meeting_rooms={"rooms": [], "active_room": None, "room_members": [], "room_topics": [], "room_messages": [], "room_tasks": [], "room_summary": {}},
        realtime={"conversations": [], "messages": [], "presence": {}, "unread_count": 0, "online_agents": [], "typing_agents": [], "last_message_at": None},
        ui={"panels": [{"id": "create_agent", "title": "创建智能体", "kind": "form"}, {"id": "organization_graph", "title": "组织架构图", "kind": "graph"}, {"id": "meeting_rooms", "title": "会议室", "kind": "room_list"}, {"id": "realtime_messages", "title": "实时通讯", "kind": "message_stream"}], "routes": [{"path": "/console/overview"}, {"path": "/console/agents/create"}, {"path": "/console/organization"}, {"path": "/console/rooms"}, {"path": "/console/chat"}], "shortcuts": [], "actions": [], "badges": []},
        avatars=avatars,
        tools={"available": tools, "count": len(tools)},
        entries=[
            {"id": "chat", "label": "Chat", "path": "/chat"},
            {"id": "workbench", "label": "Workbench", "path": "/api/v1/workbench"},
        ],
        workflows={"templates": [wf.model_dump(mode="json") for wf in role_catalog.workflows], "active_workflows": [], "workflow_states": {}, "workflow_links": []},
        memory={"session_summary": {}, "agent_summary": {}, "department_summary": {}, "layer_totals": {}, "memory_refs": []},
        permissions={"scope": ["tools:read", "agent:run", "memory:read"], "can_create_agent": True, "can_create_room": True, "can_manage_org": True, "can_read_memory": True, "can_send_message": True, "can_trigger_execution": True, "can_approve": True, "can_audit": True},
    )


@router.get("/home", response_model=WorkbenchHomeResponse)
async def get_workbench_home(
    principal: PrincipalDependency,
    control_store: Annotated[object, Depends(get_control_mode_store)],
) -> WorkbenchHomeResponse:
    """Return the Panda Agent home workspace aggregate.

    This is a UI-facing BFF endpoint only. It exposes dashboard-ready operating
    state without changing execution, approval, or security policy behavior.
    """
    enforce_scope(principal, "tools:read")
    role_catalog = build_default_role_catalog()
    organization_graph = organization_store.build_organization_graph(principal.tenant_id) if principal.tenant_id else None
    active_agents = len(organization_graph.agent_instances) if organization_graph else len(role_catalog.templates)
    running_workflows = min(5, max(1, len(role_catalog.workflows)))

    return WorkbenchHomeResponse(
        brand={
            "product_name": "Panda Agent",
            "platform_name": "熊猫派达智能体应用管理平台",
            "subtitle": "Powered by X-Agent Autonomous Framework",
        },
        summary="Codex 桌面端工作方式与 X-Agent 企业智能体框架融合的应用管理工作台。",
        metrics={
            "active_agents": active_agents,
            "running_workflows": running_workflows,
            "pending_approvals": 3,
            "api_calls": 12428,
            "storage_used": "45.2 GB / 1 TB",
        },
        agent_activity=[
            WorkbenchActivityItem(id="act-code-review", title="代码审查智能体", subtitle="正在运行", status="running", tone="warning", time="现在"),
            WorkbenchActivityItem(id="act-data", title="数据分析助手", subtitle="正在生成洞察报告", status="running", tone="warning", time="12:30"),
            WorkbenchActivityItem(id="act-docs", title="文档总结专家", subtitle="已完成", status="done", tone="success", time="09:15"),
            WorkbenchActivityItem(id="act-channel", title="渠道发布智能体", subtitle="等待审批", status="review", tone="warning", time="昨天"),
            WorkbenchActivityItem(id="act-ui", title="UI 设计助手", subtitle="运行失败", status="failed", tone="danger", time="昨天"),
        ],
        workflow_runs=[
            WorkbenchWorkflowRun(id="wf-feedback", name="客户反馈处理流程", state="执行中", progress=75, owner="客服智能体组", tone="warning"),
            WorkbenchWorkflowRun(id="wf-sync", name="数据同步工作流", state="执行中", progress=45, owner="数据分析助手", tone="warning"),
            WorkbenchWorkflowRun(id="wf-daily", name="日报生成流程", state="已完成", progress=100, owner="运营智能体", tone="success"),
            WorkbenchWorkflowRun(id="wf-weekly", name="周报汇总流程", state="已完成", progress=100, owner="文档总结专家", tone="success"),
            WorkbenchWorkflowRun(id="wf-monitor", name="异常监控流程", state="失败", progress=0, owner="审计智能体", tone="danger"),
        ],
        control_summary=build_control_summary(control_store, principal.tenant_id),
        runtime_capability_summary=build_runtime_capability_summary(),
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


# --- BFF Resources endpoint (connects Panda frontend) ---
router.include_router(workbench_resources_router)
