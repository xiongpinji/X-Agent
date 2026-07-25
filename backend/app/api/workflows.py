from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from backend.app.api.errors import api_error
from backend.app.api.linked_summary import build_linked_summary
from backend.app.api.workflow_view_model import build_workflow_run_view_model
from backend.app.core.audit import AuditStore
from backend.app.core.contracts import ErrorCode
from backend.app.core.memory import MemorySystem
from backend.app.core.security import ROLE_SCOPES, Principal
from backend.app.core.workflows import (
    WorkflowDefinition,
    WorkflowExecutionError,
    WorkflowRunRecord,
    WorkflowRunRequest,
    WorkflowRunStatus,
    WorkflowScheduler,
    WorkflowScheduleRequest,
    WorkflowScheduleStore,
)
from backend.app.dependencies import (
    enforce_scope,
    get_approval_store,
    get_audit_store,
    get_current_principal,
    get_memory,
    get_workflow_repository,
    get_workflow_schedule_store,
    get_workflow_scheduler,
)
from backend.app.settings import get_settings

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
MemoryDependency = Annotated[MemorySystem, Depends(get_memory)]
WorkflowRepositoryDependency = Annotated[object, Depends(get_workflow_repository)]
WorkflowSchedulerDependency = Annotated[WorkflowScheduler, Depends(get_workflow_scheduler)]
WorkflowScheduleStoreDependency = Annotated[WorkflowScheduleStore, Depends(get_workflow_schedule_store)]
AuditStoreDependency = Annotated[AuditStore, Depends(get_audit_store)]


def _audit_store() -> AuditStore:
    return get_audit_store()


def get_chat_principal(request: Request) -> Principal:
    """Resolve principal for the first-run chat endpoint only.

    This mirrors the workbench bootstrap rule: in local development the chat
    entrypoint can be tried without credentials, while production and invalid
    credentials still use the normal authentication path.
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


ChatPrincipalDependency = Annotated[Principal, Depends(get_chat_principal)]


def _workflow_chat_response(
    *,
    request_text: str,
    workflow_id: str,
    principal: Principal,
    agent_id: str | None = None,
) -> dict[str, object]:
    run_id = f"chat-{uuid4()}"
    selected_agent = agent_id or principal.agent_id
    message = f"Workflow chat received: {request_text}" if request_text else "Workflow chat is ready."
    created_at = datetime.now(UTC).isoformat()
    events: list[dict[str, object]] = [
        {
            "type": "run.accepted",
            "status": "accepted",
            "message": "Chat request accepted by X-Agent.",
            "created_at": created_at,
        },
        {
            "type": "tool_events.placeholder",
            "status": "idle",
            "message": "Tool execution events will stream here when a run uses tools.",
            "created_at": created_at,
        },
    ]
    next_actions = [
        {"id": "open_workbench", "label": "Open Workbench", "path": "/api/v1/workbench"},
        {"id": "watch_events", "label": "Watch Events", "path": f"/api/v1/workflows/runs/{run_id}"},
    ]
    return {
        "run_id": run_id,
        "trace_id": run_id,
        "status": "accepted",
        "message": message,
        "events": events,
        "approval_required": False,
        "next_actions": next_actions,
        "agent_id": selected_agent,
        "workflow_id": workflow_id,
        "request": request_text,
        "response": message,
        "name": request_text[:32] if request_text else "workflow chat",
        "id": run_id,
        "resource_type": "workflow_chat",
        "snapshot": {
            "workflow_id": workflow_id,
            "request": request_text,
            "run_id": run_id,
            "agent_id": selected_agent,
            "tenant_id": principal.tenant_id,
            "user_id": principal.user_id,
            "status": "accepted",
        },
    }


@router.post("")
async def create_workflow(payload: dict[str, object], repository: WorkflowRepositoryDependency, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "workflow:create")
    workflow = WorkflowDefinition.model_validate(payload)
    saved = repository.upsert_definition(workflow)
    _audit_store().record(action="workflow.create", resource_type="workflow", resource_id=saved.id, tenant_id=principal.tenant_id, actor_id=principal.user_id, workflow_id=saved.id, details={"name": saved.name})
    return {**saved.model_dump(mode="json"), "id": saved.id, "workflow_id": saved.id, "resource_type": "workflow", "snapshot": {"workflow_id": saved.id, "node_count": len(saved.nodes), "edge_count": len(saved.edges)}}


@router.get("")
async def list_workflows(repository: WorkflowRepositoryDependency, principal: PrincipalDependency) -> list[dict[str, object]]:
    enforce_scope(principal, "workflow:run")
    return [{**workflow.model_dump(mode="json"), "id": workflow.id, "workflow_id": workflow.id, "resource_type": "workflow", "snapshot": {"workflow_id": workflow.id, "node_count": len(workflow.nodes), "edge_count": len(workflow.edges)}} for workflow in repository.list_definitions()]


@router.get("/status")
async def list_workflow_status(repository: WorkflowRepositoryDependency, principal: PrincipalDependency) -> list[dict[str, object]]:
    enforce_scope(principal, "workflow:run")
    items: list[dict[str, object]] = []
    for workflow in repository.list_definitions():
        latest = repository.latest_run_for(workflow.id)
        items.append({"workflow_id": workflow.id, "workflow_name": workflow.name, "status": latest.status.value if latest else "draft", "latest_run_id": latest.run_id if latest else None, "latest_run_status": latest.status.value if latest else None, "run_count": repository.count_runs(workflow.id), "updated_at": workflow.updated_at, "snapshot": {"workflow_id": workflow.id, "run_count": repository.count_runs(workflow.id)}})
    return items


@router.get("/templates")
async def list_global_workflow_templates(repository: WorkflowRepositoryDependency, principal: PrincipalDependency) -> list[dict[str, object]]:
    enforce_scope(principal, "workflow:run")
    return [{"id": f"template-{workflow.id}", "workflow_id": workflow.id, "name": workflow.name, "description": workflow.description, "nodes": len(workflow.nodes), "edges": len(workflow.edges), "resource_type": "workflow_template", "snapshot": {"workflow_id": workflow.id, "template_id": f"template-{workflow.id}"}} for workflow in repository.list_definitions()]


@router.post("/create/chat")
async def create_global_workflow_chat(payload: dict[str, object], repository: WorkflowRepositoryDependency, principal: ChatPrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "workflow:run")
    request = str(payload.get("request", ""))
    workflow_id = str(payload.get("workflow_id") or "")
    agent_id = str(payload.get("agent_id") or payload.get("agentId") or principal.agent_id)
    return _workflow_chat_response(
        request_text=request,
        workflow_id=workflow_id,
        principal=principal,
        agent_id=agent_id,
    )


@router.get("/runs")
async def list_workflow_runs(repository: WorkflowRepositoryDependency, principal: PrincipalDependency, limit: int = Query(default=20, ge=1, le=1000)) -> dict[str, object]:
    enforce_scope(principal, "workflow:run")
    runs = [
        {
            **run.model_dump(mode="json"),
            "id": run.run_id,
            "run_id": run.run_id,
            "trace_id": run.run_id,
            "workflow_id": run.workflow_id,
            "resource_type": "workflow_run",
            "snapshot": {**run.snapshot, "run_id": run.run_id, "workflow_id": run.workflow_id, "trace_id": run.run_id},
            "ui": {"title": run.workflow_name, "subtitle": run.status.value, "badges": [run.status.value, f"nodes:{len(run.node_results)}"]},
        }
        for run in repository.list_runs(limit=limit)
        if run.tenant_id == principal.tenant_id
    ]
    return {"items": runs, "layout": {"framework": "React", "ui_kit": "mantine", "primary": "overview", "secondary": ["timeline", "nodes"], "tertiary": ["failures", "compensations", "traces"]}, "components": {"workflow_shell": {}, "timeline_panel": {}, "node_list": {}}, "snapshot": {"count": len(runs)}}


@router.get("/schedules")
async def list_workflow_schedules(schedule_store: WorkflowScheduleStoreDependency, principal: PrincipalDependency, limit: int = Query(default=20, ge=1, le=1000)) -> list[dict[str, object]]:
    enforce_scope(principal, "workflow:run")
    records = schedule_store.list(limit=limit)
    return [{"id": record.schedule_id, "schedule_id": record.schedule_id, "workflow_id": record.workflow_id, "status": record.status.value, "run_id": record.run_id, "locked_by": record.locked_by, "locked_until": record.locked_until, "resource_type": "workflow_schedule", "snapshot": {**record.snapshot, "workflow_id": record.workflow_id, "schedule_id": record.schedule_id, "status": record.status.value}} for record in records if record.tenant_id == principal.tenant_id]


@router.get("/schedules/{schedule_id}")
async def get_workflow_schedule(schedule_id: str, schedule_store: WorkflowScheduleStoreDependency, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "workflow:run")
    record = schedule_store.get(schedule_id)
    if record is None:
        raise api_error(404, ErrorCode.WORKFLOW_NOT_FOUND, "Workflow schedule not found.")
    if record.tenant_id != principal.tenant_id:
        raise api_error(404, ErrorCode.WORKFLOW_NOT_FOUND, "Workflow schedule not found.")
    return {**record.model_dump(mode="json"), "id": record.schedule_id, "schedule_id": record.schedule_id, "workflow_id": record.workflow_id, "resource_type": "workflow_schedule", "snapshot": {**record.snapshot, "workflow_id": record.workflow_id, "schedule_id": record.schedule_id}}


@router.get("/schedules/{schedule_id}/correlation")
async def get_workflow_schedule_correlation(schedule_id: str, schedule_store: WorkflowScheduleStoreDependency, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "workflow:run")
    schedule = await get_workflow_schedule(schedule_id, schedule_store, principal)
    trace_id = schedule["schedule_id"]
    return {"schedule_id": schedule["schedule_id"], "workflow_id": schedule["workflow_id"], "trace_id": trace_id, "resource_type": "workflow_schedule", "correlation": {"schedule": schedule}, "trace_summary": {"trace_id": trace_id, "event_count": 1, "started_at": schedule["created_at"], "ended_at": schedule["updated_at"], "last_event": f"schedule.{schedule['status']}", "task": schedule["workflow_id"], "snapshot": {"schedule_id": schedule["schedule_id"], "workflow_id": schedule["workflow_id"], "trace_id": trace_id, "status": schedule["status"]}}, "snapshot": {**schedule.get("snapshot", {}), "schedule_id": schedule["schedule_id"], "workflow_id": schedule["workflow_id"], "trace_id": trace_id}}


@router.post("/schedules/run-due")
async def run_due_schedules(scheduler: WorkflowSchedulerDependency, schedule_store: WorkflowScheduleStoreDependency, principal: PrincipalDependency, limit: int = Query(default=20, ge=1, le=1000)) -> list[dict[str, object]]:
    enforce_scope(principal, "workflow:control")
    triggered = await scheduler.run_due(limit=limit)
    records = {record.schedule_id: record for record in schedule_store.list(limit=1000)}
    return [{"schedule_id": item.schedule_id, "workflow_id": item.workflow_id, "status": item.status.value, "run_id": item.run_id, "resource_type": "workflow_schedule", "snapshot": {**records.get(item.schedule_id, item).snapshot, "schedule_id": item.schedule_id, "workflow_id": item.workflow_id}} for item in triggered]


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str, repository: WorkflowRepositoryDependency, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "workflow:run")
    workflow = repository.get_definition(workflow_id)
    if workflow is None:
        raise api_error(404, ErrorCode.WORKFLOW_NOT_FOUND, "Workflow not found.")
    latest_run = repository.latest_run_for(workflow_id)
    latest_status = latest_run.status.value if latest_run else "draft"
    snapshot = {
        "workflow_id": workflow.id,
        "latest_run_id": latest_run.run_id if latest_run else None,
        "latest_run_status": latest_status,
        "latest_run_resume_cursor": latest_run.resume_cursor if latest_run else 0,
        "node_count": len(workflow.nodes),
        "edge_count": len(workflow.edges),
        "run_count": repository.count_runs(workflow.id),
    }
    return {**workflow.model_dump(mode="json"), "id": workflow.id, "workflow_id": workflow.id, "resource_type": "workflow", "status": latest_status, "latest_run_id": latest_run.run_id if latest_run else None, "latest_run_status": latest_status, "run_count": repository.count_runs(workflow.id), "snapshot": snapshot}


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(workflow_id: str, repository: WorkflowRepositoryDependency, principal: PrincipalDependency) -> None:
    enforce_scope(principal, "workflow:create")
    deleted = repository.delete_definition(workflow_id)
    if not deleted:
        raise api_error(404, ErrorCode.WORKFLOW_NOT_FOUND, "Workflow not found.")
    _audit_store().record(action="workflow.delete", resource_type="workflow", resource_id=workflow_id, tenant_id=principal.tenant_id, actor_id=principal.user_id, workflow_id=workflow_id, details={})


@router.get("/{workflow_id}/status")
async def get_workflow_status(workflow_id: str, repository: WorkflowRepositoryDependency, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "workflow:run")
    workflow = repository.get_definition(workflow_id)
    if workflow is None:
        raise api_error(404, ErrorCode.WORKFLOW_NOT_FOUND, "Workflow not found.")
    latest_run = repository.latest_run_for(workflow_id)
    latest_status = latest_run.status.value if latest_run else "draft"
    snapshot = {
        "workflow_id": workflow.id,
        "run_count": repository.count_runs(workflow.id),
        "latest_run_id": latest_run.run_id if latest_run else None,
        "latest_run_status": latest_status,
        "latest_run_resume_cursor": latest_run.resume_cursor if latest_run else 0,
        "node_count": len(workflow.nodes),
        "edge_count": len(workflow.edges),
        "updated_at": workflow.updated_at,
    }
    return {"workflow_id": workflow.id, "workflow_name": workflow.name, "status": latest_status, "latest_run_id": latest_run.run_id if latest_run else None, "latest_run_status": latest_status, "run_count": repository.count_runs(workflow.id), "updated_at": workflow.updated_at, "snapshot": snapshot, "id": workflow.id, "resource_type": "workflow"}


@router.get("/{workflow_id}/instances")
async def list_workflow_instances(workflow_id: str, repository: WorkflowRepositoryDependency, principal: PrincipalDependency) -> list[dict[str, object]]:
    enforce_scope(principal, "workflow:run")
    return [{**run.model_dump(mode="json"), "id": run.run_id, "run_id": run.run_id, "trace_id": run.run_id, "workflow_id": run.workflow_id, "resource_type": "workflow_run", "snapshot": {**run.snapshot, "run_id": run.run_id, "workflow_id": run.workflow_id, "trace_id": run.run_id, "status": run.status.value, "resume_cursor": run.resume_cursor}} for run in repository.list_runs(workflow_id=workflow_id) if run.tenant_id == principal.tenant_id]


@router.get("/{workflow_id}/templates")
async def list_workflow_templates(workflow_id: str, repository: WorkflowRepositoryDependency, principal: PrincipalDependency) -> list[dict[str, object]]:
    enforce_scope(principal, "workflow:run")
    workflow = repository.get_definition(workflow_id)
    if workflow is None:
        raise api_error(404, ErrorCode.WORKFLOW_NOT_FOUND, "Workflow not found.")
    return [{"id": f"template-{workflow.id}", "workflow_id": workflow.id, "name": workflow.name, "description": workflow.description, "nodes": len(workflow.nodes), "edges": len(workflow.edges), "resource_type": "workflow_template", "snapshot": {"workflow_id": workflow.id, "template_id": f"template-{workflow.id}"}}]


@router.post("/{workflow_id}/create/chat")
async def create_workflow_chat(workflow_id: str, payload: dict[str, object], repository: WorkflowRepositoryDependency, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "workflow:run")
    workflow = repository.get_definition(workflow_id)
    if workflow is None:
        raise api_error(404, ErrorCode.WORKFLOW_NOT_FOUND, "Workflow not found.")
    request = str(payload.get("request", ""))
    agent_id = str(payload.get("agent_id") or payload.get("agentId") or principal.agent_id)
    response = _workflow_chat_response(
        request_text=request,
        workflow_id=workflow.id,
        principal=principal,
        agent_id=agent_id,
    )
    response["name"] = request[:32] if request else workflow.name
    return response


@router.post("/{workflow_id}/pause")
async def pause_workflow(workflow_id: str, scheduler: WorkflowSchedulerDependency, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "workflow:control")
    response = await scheduler.runtime.pause_latest(workflow_id)
    _audit_store().record(action="workflow.run.paused", resource_type="workflow_run", resource_id=response.run_id, tenant_id=principal.tenant_id, actor_id=principal.user_id, workflow_id=workflow_id, run_id=response.run_id, details={"status": response.status.value})
    return response.model_dump(mode="json")


@router.post("/{workflow_id}/resume")
async def resume_workflow(workflow_id: str, scheduler: WorkflowSchedulerDependency, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "workflow:control")
    response = await scheduler.runtime.resume_latest(workflow_id)
    _audit_store().record(action="workflow.run.resumed", resource_type="workflow_run", resource_id=response.run_id, tenant_id=principal.tenant_id, actor_id=principal.user_id, workflow_id=workflow_id, run_id=response.run_id, details={"status": response.status.value})
    return response.model_dump(mode="json")


@router.post("/runs/{run_id}/resume-approved")
async def resume_approved_run(run_id: str, scheduler: WorkflowSchedulerDependency, principal: PrincipalDependency, payload: dict[str, object] | None = None) -> dict[str, object]:
    enforce_scope(principal, "workflow:control")
    run = scheduler.repository.get_run(run_id)
    if run is None:
        raise api_error(404, ErrorCode.WORKFLOW_NOT_FOUND, "Workflow run not found.")
    if run.tenant_id != principal.tenant_id:
        raise api_error(404, ErrorCode.WORKFLOW_NOT_FOUND, "Workflow run not found.")
    payload = payload or {}
    explicit_approval_id = str(payload.get("approval_id") or "")
    if not explicit_approval_id:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "approval_id is required.")
    approval = get_approval_store().get(explicit_approval_id)
    if approval is None or approval.status.value != "approved" or approval.tenant_id != principal.tenant_id:
        raise api_error(403, ErrorCode.AUTHORIZATION_FAILED, "Approval invalid or not approved.")
    approved = {run.pending_node_id: explicit_approval_id} if run.pending_node_id else {explicit_approval_id: explicit_approval_id}
    response = await scheduler.runtime.executor.execute(
        run.workflow_id,
        run.inputs,
        tenant_id=run.tenant_id,
        user_id=run.user_id,
        permission_scope=list(set(principal.permission_scope) & set(run.snapshot.get("permission_scope", principal.permission_scope))) if run.snapshot.get("permission_scope") else principal.permission_scope,
        run_id=run.run_id,
        approved_approvals=approved,
    )
    _audit_store().record(action="workflow.run.resumed", resource_type="workflow_run", resource_id=response.run_id, tenant_id=principal.tenant_id, actor_id=principal.user_id, workflow_id=run.workflow_id, run_id=response.run_id, details={"status": response.status.value, "approved": True})
    return {**response.model_dump(mode="json"), "id": response.run_id, "run_id": response.run_id, "trace_id": response.run_id, "workflow_id": run.workflow_id, "resource_type": "workflow_run", "snapshot": {**response.snapshot, "workflow_id": run.workflow_id, "run_id": response.run_id, "trace_id": response.run_id}}


@router.post("/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str, scheduler: WorkflowSchedulerDependency, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "workflow:control")
    response = await scheduler.runtime.cancel_latest(workflow_id)
    _audit_store().record(action="workflow.run.canceled", resource_type="workflow_run", resource_id=response.run_id, tenant_id=principal.tenant_id, actor_id=principal.user_id, workflow_id=workflow_id, run_id=response.run_id, details={"status": response.status.value})
    return response.model_dump(mode="json")


@router.post("/{workflow_id}/run")
@router.post("/{workflow_id}/execute")
async def run_workflow(workflow_id: str, payload: dict[str, object], repository: WorkflowRepositoryDependency, scheduler: WorkflowSchedulerDependency, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "workflow:run")
    workflow = repository.get_definition(workflow_id)
    if workflow is None:
        raise api_error(404, ErrorCode.WORKFLOW_NOT_FOUND, "Workflow not found.")
    request = WorkflowRunRequest.model_validate(payload)
    tenant_id = principal.tenant_id
    user_id = principal.user_id
    if request.async_run:
        run = await scheduler.runtime.start(
            workflow.id,
            request.inputs,
            tenant_id=tenant_id,
            user_id=user_id,
            permission_scope=principal.permission_scope,
        )
    else:
        run = await scheduler.runtime.executor.execute(
            workflow.id,
            request.inputs,
            tenant_id=tenant_id,
            user_id=user_id,
            permission_scope=principal.permission_scope,
        )
    _audit_store().record(action="workflow.run", resource_type="workflow", resource_id=workflow.id, tenant_id=tenant_id, actor_id=user_id, trace_id=run.run_id, run_id=run.run_id, workflow_id=workflow.id, details={"status": run.status.value, "async_run": request.async_run})
    return {**run.model_dump(mode="json"), "id": run.run_id, "run_id": run.run_id, "trace_id": run.run_id, "workflow_id": workflow.id, "resource_type": "workflow_run", "snapshot": {**run.snapshot, "workflow_id": workflow.id, "run_id": run.run_id, "trace_id": run.run_id}}


@router.post("/{workflow_id}/schedule")
async def schedule_workflow(workflow_id: str, payload: dict[str, object], repository: WorkflowRepositoryDependency, scheduler: WorkflowSchedulerDependency, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "workflow:control")
    workflow = repository.get_definition(workflow_id)
    if workflow is None:
        raise api_error(404, ErrorCode.WORKFLOW_NOT_FOUND, "Workflow not found.")
    request = WorkflowScheduleRequest.model_validate({"inputs": payload.get("inputs", {}), "tenant_id": principal.tenant_id, "user_id": principal.user_id, "delay_seconds": payload.get("delay_seconds", 0), "run_at": payload.get("run_at"), "cron": payload.get("cron")})
    try:
        schedule = scheduler.schedule(workflow.id, request, tenant_id=request.tenant_id, user_id=request.user_id, permission_scope=principal.permission_scope)
    except WorkflowExecutionError as exc:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, str(exc)) from exc
    _audit_store().record(action="workflow.schedule", resource_type="workflow", resource_id=workflow.id, tenant_id=request.tenant_id, actor_id=request.user_id, workflow_id=workflow.id, details={"schedule_id": schedule.schedule_id})
    return {**schedule.model_dump(mode="json"), "id": schedule.schedule_id, "schedule_id": schedule.schedule_id, "workflow_id": workflow.id, "resource_type": "workflow_schedule", "snapshot": {**schedule.snapshot, "workflow_id": workflow.id, "schedule_id": schedule.schedule_id}}


_AUDIT_ANCHOR_EVENT_TYPES = frozenset({
    "run.started", "run.completed",
    "node.started", "node.completed",
    "node.compensated", "node.failed",
})


def _build_audit_anchors(timeline: list[dict[str, object]]) -> list[dict[str, object]]:
    """从运行时间线中提取审计锚点事件。"""
    return [
        {"kind": event["kind"], "timestamp": event["timestamp"],
         "node_id": event.get("node_id"), "status": event.get("status")}
        for event in timeline
        if event["kind"] in _AUDIT_ANCHOR_EVENT_TYPES
    ]


def _build_workflow_summary(run: WorkflowRunRecord, failure_count: int, compensation_count: int) -> dict[str, object]:
    recovery_plan = run.snapshot.get("last_agent_execution_summary", {}).get("recovery_plan", {}) if isinstance(run.snapshot, dict) else {}
    return {
        "workflow_id": run.workflow_id,
        "workflow_name": run.workflow_name,
        "status": run.status.value,
        "tenant_id": run.tenant_id,
        "user_id": run.user_id,
        "node_count": len(run.node_results),
        "failure_count": failure_count,
        "compensation_count": compensation_count,
        "latest_branch": run.snapshot.get("last_agent_recovery_branch") if isinstance(run.snapshot, dict) else None,
        "recovery_plan": recovery_plan,
        "ui": {
            "title": run.workflow_name,
            "status": run.status.value,
            "subtitle": f"{failure_count} failures / {compensation_count} compensations",
        },
    }


def _node_result_view(result: Any) -> dict[str, object]:
    data = result.model_dump(mode="json") if hasattr(result, "model_dump") else dict(result)
    return {"node_id": data.get("node_id"), "node_type": data.get("node_type"), "status": data.get("status"), "attempts": data.get("attempts", 1), "output": data.get("output"), "error": data.get("error"), "started_at": data.get("started_at"), "completed_at": data.get("completed_at"), "agent_trace_id": data.get("agent_trace_id"), "compensated": data.get("compensated", False), "compensation_output": data.get("compensation_output"), "compensation_error": data.get("compensation_error")}


def _build_node_result_summary(node_results: list[dict[str, object]]) -> dict[str, object]:
    by_status: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for item in node_results:
        status = str(item.get("status") or "unknown")
        node_type = str(item.get("node_type") or "unknown")
        by_status[status] = by_status.get(status, 0) + 1
        by_type[node_type] = by_type.get(node_type, 0) + 1
    return {"total": len(node_results), "by_status": by_status, "by_type": by_type, "failure_nodes": [item["node_id"] for item in node_results if item.get("error")]}


def _build_workflow_linked_summaries(run: WorkflowRunRecord, timeline: list[dict[str, object]], node_results: list[dict[str, object]], failure_chain: list[dict[str, object]], compensation_chain: list[dict[str, object]], trace_ids: list[str]) -> dict[str, object]:
    failure_count = len(failure_chain)
    compensation_count = len(compensation_chain)
    workflow_summary = _build_workflow_summary(run, failure_count, compensation_count)
    node_result_summary = _build_node_result_summary(node_results)
    trace_summary = {
        "trace_id": run.run_id,
        "event_count": len(timeline),
        "started_at": run.started_at,
        "ended_at": run.completed_at,
        "last_event": "run.completed",
        "task": run.workflow_name,
        "snapshot": {
            "workflow_id": run.workflow_id,
            "run_id": run.run_id,
            "status": run.status.value,
            "failure_count": failure_count,
            "compensation_count": compensation_count,
            "node_count": len(run.node_results),
            "resume_cursor": run.resume_cursor,
            "recovery_plan": run.snapshot.get("last_agent_execution_summary", {}).get("recovery_plan", {}) if isinstance(run.snapshot, dict) else {},
        },
    }
    return {
        "run": {
            "run_id": run.run_id,
            "workflow_id": run.workflow_id,
            "status": run.status.value,
            "resume_cursor": run.resume_cursor,
            "node_count": len(run.node_results),
            "run_view": build_workflow_run_view_model(run, timeline, node_results, failure_chain, compensation_chain, trace_ids),
            "snapshot": {
                "run_id": run.run_id,
                "workflow_id": run.workflow_id,
                "status": run.status.value,
                "resume_cursor": run.resume_cursor,
                "node_count": len(run.node_results),
            },
        },
        "workflow": workflow_summary,
        "trace": trace_summary,
        "nodes": node_result_summary,
        "failures": {"count": failure_count, "items": failure_chain},
        "compensations": {"count": compensation_count, "items": compensation_chain},
    }


def _build_failure_view(failure_events: list[dict[str, object]]) -> list[dict[str, object]]:
    return [{"node_id": event.get("node_id"), "node_type": event.get("node_type"), "error": event.get("error"), "attempts": event.get("attempts"), "agent_trace_id": event.get("agent_trace_id")} for event in failure_events]


def _build_compensation_view(compensation_events: list[dict[str, object]]) -> list[dict[str, object]]:
    return [{"node_id": event.get("node_id"), "node_type": event.get("node_type"), "attempts": event.get("attempts"), "compensation_error": event.get("compensation_error"), "compensation_output": event.get("compensation_output")} for event in compensation_events]


def _build_timeline_sections(timeline: list[dict[str, object]]) -> list[dict[str, object]]:
    sections: list[dict[str, object]] = [{"title": "Run", "events": []}]
    node_sections: dict[str, dict[str, object]] = {}
    for event in timeline:
        if event["kind"] in {"run.started", "run.completed"}:
            sections[0]["events"].append(event)
            continue
        node_id = str(event.get("node_id") or "node")
        section = node_sections.get(node_id)
        if section is None:
            section = {"node_id": node_id, "title": f"Node {node_id}", "events": [], "status": event.get("status"), "node_type": event.get("node_type")}
            node_sections[node_id] = section
            sections.append(section)
        section["events"].append(event)
        section["status"] = event.get("status")
        section["node_type"] = event.get("node_type")
    return sections


def _build_run_timeline(run: WorkflowRunRecord) -> list[dict[str, object]]:
    timeline = [{"kind": "run.started", "timestamp": run.started_at.isoformat(), "workflow_id": run.workflow_id}]
    for result in run.node_results:
        timeline.append({"kind": "node.started", "timestamp": result.started_at.isoformat(), "node_id": result.node_id, "node_type": result.node_type.value, "status": result.status.value})
        kind = "node.completed" if result.status == WorkflowRunStatus.COMPLETED else "node.compensated" if result.compensated else "node.failed"
        timeline.append({"kind": kind, "timestamp": result.completed_at.isoformat(), "node_id": result.node_id, "node_type": result.node_type.value, "status": result.status.value, "attempts": result.attempts, "agent_trace_id": result.agent_trace_id, "compensated": result.compensated, "error": result.error, "compensation_error": result.compensation_error, "compensation_output": result.compensation_output})
    timeline.append({"kind": "run.completed", "timestamp": run.completed_at.isoformat(), "workflow_id": run.workflow_id, "status": run.status.value})
    return timeline


@router.get("/runs/{run_id}")
async def get_workflow_run_detail(run_id: str, repository: WorkflowRepositoryDependency, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "workflow:run")
    run = repository.get_run(run_id)
    if run is None:
        raise api_error(404, ErrorCode.WORKFLOW_NOT_FOUND, "Workflow run not found.")
    if run.tenant_id != principal.tenant_id:
        raise api_error(404, ErrorCode.WORKFLOW_NOT_FOUND, "Workflow run not found.")
    timeline = _build_run_timeline(run)
    node_results = [_node_result_view(item) for item in run.node_results]
    trace_ids = sorted({item.get("agent_trace_id") for item in node_results if item.get("agent_trace_id")})
    failure_chain = _build_failure_view([event for event in timeline if event["kind"] == "node.failed"])
    compensation_chain = _build_compensation_view([event for event in timeline if event["kind"] == "node.compensated"])
    linked_summaries = _build_workflow_linked_summaries(run, timeline, node_results, failure_chain, compensation_chain, trace_ids)
    primary = {
        "run": run.model_dump(mode="json"),
        "timeline": timeline,
        "view_model": build_workflow_run_view_model(run, timeline, node_results, failure_chain, compensation_chain, trace_ids),
    }
    payload = build_linked_summary(
        resource_type="workflow_run",
        resource_id=run.run_id,
        primary=primary,
        trace=linked_summaries["trace"],
        run=linked_summaries["run"],
        workflow=linked_summaries["workflow"],
        extra={
            "timeline": timeline,
            "view_model": primary["view_model"],
            "audit_anchors": _build_audit_anchors(timeline),
            "failure_events": failure_chain,
            "compensation_events": compensation_chain,
        },
    )
    # 顶层补 run / timeline，与姊妹端点(traces /correlation)一致：调用方按
    # detail["run"]["run_id"] / detail["timeline"] 直接取值；富链接信封仍在
    # linked_summaries / snapshot 内保留，二者并存互不破坏。
    payload["run"] = run.model_dump(mode="json")
    payload["timeline"] = timeline
    # 把 run 字段(含 run_id/workflow_id/status 等)并入顶层 snapshot，
    # 与 correlation 端点保持一致(调用方按 detail["snapshot"]["run_id"] 取值);
    # 原信封字段(linked_summaries/timeline 等)仍保留在 snapshot 内。
    payload["snapshot"] = {**payload.get("snapshot", {}), **run.model_dump(mode="json")}
    return payload


@router.get("/runs/{run_id}/correlation")
async def get_workflow_run_correlation(run_id: str, repository: WorkflowRepositoryDependency, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "workflow:run")
    run = repository.get_run(run_id)
    if run is None:
        raise api_error(404, ErrorCode.WORKFLOW_NOT_FOUND, "Workflow run not found.")
    if run.tenant_id != principal.tenant_id:
        raise api_error(404, ErrorCode.WORKFLOW_NOT_FOUND, "Workflow run not found.")
    timeline = _build_run_timeline(run)
    trace_ids = sorted({node.agent_trace_id for node in run.node_results if node.agent_trace_id})
    failure_events = [event for event in timeline if event["kind"] == "node.failed"]
    compensation_events = [event for event in timeline if event["kind"] == "node.compensated"]
    node_results = [_node_result_view(item) for item in run.node_results]
    failure_chain = _build_failure_view(failure_events)
    compensation_chain = _build_compensation_view(compensation_events)
    linked_summaries = _build_workflow_linked_summaries(run, timeline, node_results, failure_chain, compensation_chain, trace_ids)
    primary = {
        "trace_ids": trace_ids,
        "workflow_summary": linked_summaries["workflow"],
        "node_result_summary": linked_summaries["nodes"],
        "timeline": timeline,
        "timeline_sections": _build_timeline_sections(timeline),
        "node_results": node_results,
        "failure_events": failure_events,
        "compensation_events": compensation_events,
        "failure_count": len(failure_events),
        "compensation_count": len(compensation_events),
        "failure_chain": failure_chain,
        "compensation_chain": compensation_chain,
        "trace_summary": linked_summaries["trace"],
        "view_model": build_workflow_run_view_model(run, timeline, node_results, failure_chain, compensation_chain, trace_ids),
    }
    payload = build_linked_summary(
        resource_type="workflow_run",
        resource_id=run.run_id,
        primary=primary,
        trace=linked_summaries["trace"],
        run=linked_summaries["run"],
        workflow=linked_summaries["workflow"],
        extra={
            "trace_ids": trace_ids,
            "timeline": timeline,
            "timeline_sections": _build_timeline_sections(timeline),
            "node_results": node_results,
            "failure_events": failure_events,
            "compensation_events": compensation_events,
            "failure_count": len(failure_events),
            "compensation_count": len(compensation_events),
            "failure_chain": failure_chain,
            "compensation_chain": compensation_chain,
            "trace_summary": linked_summaries["trace"],
            "view_model": primary["view_model"],
            "audit_anchors": _build_audit_anchors(timeline),
        },
    )
    # 顶层补 run_id/workflow_id/trace_id/trace_summary/audit_anchors，
    # 与姊妹端点 /api/v1/traces/{id}/correlation 一致(调用方按
    # correlation.json()["trace_summary"]["trace_id"] 等取值)。
    payload["run_id"] = run.run_id
    payload["workflow_id"] = run.workflow_id
    payload["trace_id"] = run.run_id
    payload["trace_summary"] = linked_summaries["trace"]
    payload["audit_anchors"] = _build_audit_anchors(timeline)
    payload["snapshot"] = run.model_dump(mode="json")
    return payload


@router.get("/runs/{run_id}/stream")
async def stream_workflow_run(
    run_id: str,
    repository: WorkflowRepositoryDependency,
    principal: PrincipalDependency,
):
    """SSE endpoint for real-time workflow run status updates.

    Streams node-level status changes: pending → running → completed/failed.
    """
    enforce_scope(principal, "workflow:run")

    async def event_generator():
        # Send initial status
        run = repository.get_run(run_id)
        if run is None:
            yield f"data: {json.dumps({'event': 'error', 'message': 'Run not found'})}\n\n"
            return

        yield f"data: {json.dumps({'event': 'connected', 'run_id': run_id, 'status': run.status.value})}\n\n"

        # Poll for status updates (in production, use Redis pub/sub)
        last_cursor = run.resume_cursor or 0
        nodes = run.snapshot.get("nodes", []) if run.snapshot else []
        max_polls = 60  # Max 60 seconds of polling

        for _ in range(max_polls):
            await asyncio.sleep(1)
            current_run = repository.get_run(run_id)
            if current_run is None:
                break

            current_cursor = current_run.resume_cursor or 0
            if current_cursor > last_cursor:
                # Send node progress updates
                for i in range(last_cursor, min(current_cursor, len(nodes))):
                    node = nodes[i] if i < len(nodes) else {}
                    yield f"data: {json.dumps({'event': 'node_completed', 'node_index': i, 'node_id': node.get('id', f'node-{i}'), 'status': 'completed'})}\n\n"
                last_cursor = current_cursor

            if current_run.status.value in ("completed", "failed", "cancelled"):
                yield f"data: {json.dumps({'event': 'run_finished', 'status': current_run.status.value, 'run_id': run_id})}\n\n"
                return

        # Timeout
        yield f"data: {json.dumps({'event': 'timeout', 'run_id': run_id})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
