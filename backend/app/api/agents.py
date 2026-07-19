from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode, RunContext
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_agent, get_audit_store, get_run_store, get_trace_store, get_current_principal

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

_AGENTS: dict[str, dict[str, Any]] = {
    "default-agent": {
        "id": "default-agent",
        "name": "Default X-Agent",
        "status": "active",
        "capabilities": ["run", "trace", "memory", "tools"],
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
}


@router.post("")
async def create_agent(payload: dict[str, Any] | None = None, principal: PrincipalDependency = None) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    payload = payload or {}
    agent_id = payload.get("id") or f"agent_{uuid4().hex[:8]}"
    record = {
        "id": agent_id,
        "name": payload.get("name") or "Agent",
        "status": payload.get("status") or "active",
        "capabilities": payload.get("capabilities") or ["run", "trace", "memory", "tools"],
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    _AGENTS[agent_id] = record
    return record


@router.get("")
async def list_agents(principal: PrincipalDependency = None) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    agent = get_agent()
    items = [dict(item) for item in _AGENTS.values()]
    for item in items:
        if item["id"] == "default-agent":
            item["max_iterations"] = agent.max_iterations
    return {"data": items}


@router.get("/{agent_id}")
async def get_agent_detail(agent_id: str, principal: PrincipalDependency = None) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    record = _AGENTS.get(agent_id)
    if record is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Agent not found.", details={"resource_type": "agent", "resource_id": agent_id})
    agent = get_agent()
    record = dict(record)
    record["max_iterations"] = agent.max_iterations
    return record


@router.put("/{agent_id}")
async def update_agent(agent_id: str, payload: dict[str, Any] | None = None, principal: PrincipalDependency = None) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    record = _AGENTS.get(agent_id)
    if record is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Agent not found.", details={"resource_type": "agent", "resource_id": agent_id})
    payload = payload or {}
    record = dict(record)
    record.update({k: v for k, v in payload.items() if k in {"name", "status", "capabilities"}})
    record["updated_at"] = datetime.now(UTC).isoformat()
    _AGENTS[agent_id] = record
    return record


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str, principal: PrincipalDependency = None) -> dict[str, bool]:
    enforce_scope(principal, "security:manage")
    if agent_id not in _AGENTS:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Agent not found.", details={"resource_type": "agent", "resource_id": agent_id})
    if agent_id == "default-agent":
        return {"deleted": False}
    del _AGENTS[agent_id]
    return {"deleted": True}


@router.post("/{agent_id}/pause")
async def pause_agent(agent_id: str, principal: PrincipalDependency = None) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    record = _AGENTS.get(agent_id)
    if record is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Agent not found.", details={"resource_type": "agent", "resource_id": agent_id})
    record["status"] = "paused"
    record["updated_at"] = datetime.now(UTC).isoformat()
    return record


@router.post("/{agent_id}/resume")
async def resume_agent(agent_id: str, principal: PrincipalDependency = None) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    record = _AGENTS.get(agent_id)
    if record is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Agent not found.", details={"resource_type": "agent", "resource_id": agent_id})
    record["status"] = "active"
    record["updated_at"] = datetime.now(UTC).isoformat()
    return record


@router.post("/{agent_id}/cancel")
async def cancel_agent(agent_id: str, principal: PrincipalDependency = None) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    record = _AGENTS.get(agent_id)
    if record is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Agent not found.", details={"resource_type": "agent", "resource_id": agent_id})
    record["status"] = "canceled"
    record["updated_at"] = datetime.now(UTC).isoformat()
    return record


@router.post("/run", response_model=None)
async def run_agent(payload: dict[str, Any] | None = None, principal: PrincipalDependency = None):
    agent = get_agent()
    request = payload or {}
    enforce_scope(principal, "agent:run")
    task = str(request.get("task", ""))
    if not task:
        raise api_error(422, ErrorCode.VALIDATION_ERROR, "task is required.", details={"errors": [{"field": "task", "message": "task is required."}]})

    requested_scope = request.get("permission_scope", ["tools:read", "memory:read", "memory:write"])
    if not isinstance(requested_scope, list):
        requested_scope = []
    principal_scopes = set(principal.scopes or [])
    allowed_scope = [
        scope
        for scope in requested_scope
        if scope in principal_scopes or f"{str(scope).split(':', 1)[0]}:*" in principal_scopes
    ]
    context = RunContext(
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        permission_scope=allowed_scope,
    )
    result = await agent.run(context, task, request.get("extra_context", {}))
    get_audit_store().record(
        action="agent.run",
        resource_type="agent",
        resource_id=context.agent_id,
        tenant_id=context.tenant_id,
        actor_id=context.user_id,
        trace_id=result.trace_id,
        run_id=result.trace_id,
        details={"task_preview": task[:120], "status": result.status.value, "tool_call_count": len(result.tool_calls)},
    )
    body = result.model_dump(mode="json")
    if request.get("stream"):
        async def _event_stream():
            yield f"event: trace\ndata: {body}\n\n"
            yield f"event: completed\ndata: {body}\n\n"
        return StreamingResponse(_event_stream(), media_type="text/event-stream")
    return body


@router.get("/runs")
async def list_agent_runs(principal: PrincipalDependency = None, limit: int = 20) -> list[dict[str, object]]:
    enforce_scope(principal, "agent:run")
    records = get_run_store().list(limit=limit)
    return [record.model_dump(mode="json") for record in records if getattr(record, "tenant_id", None) == principal.tenant_id]


@router.get("/runs/{trace_id}")
async def get_agent_run(trace_id: str, principal: PrincipalDependency = None) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    record = get_run_store().get(trace_id)
    if record is None:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Run not found.", trace_id=trace_id)
    if getattr(record, "tenant_id", None) != principal.tenant_id:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Run not found.", trace_id=trace_id)
    return record.model_dump(mode="json")


@router.get("/runs/{trace_id}/correlation")
async def get_agent_run_correlation(trace_id: str, principal: PrincipalDependency = None) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    run = await get_agent_run(trace_id, principal)
    summary = get_trace_store().get_summary(trace_id)
    trace_summary = summary.model_dump(mode="json")
    trace_summary["snapshot"] = {**trace_summary.get("snapshot", {}), "resource_type": "agent_run", "trace_id": trace_id, "run_id": trace_id}
    return {"trace_id": trace_id, "resource_type": "agent_run", "resource_id": trace_id, "run": run, "trace_summary": trace_summary, "snapshot": {"trace_id": trace_id, "run_id": trace_id, "event_count": summary.event_count, "resource_type": "agent_run"}}


@router.get("/runs/{trace_id}/timeline")
async def get_agent_run_timeline(trace_id: str, principal: PrincipalDependency = None) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    events = [event.model_dump(mode="json") for event in get_trace_store().list_events(trace_id)]
    if not events:
        raise api_error(404, ErrorCode.TRACE_NOT_FOUND, "Trace not found.", trace_id=trace_id)
    return {"trace_id": trace_id, "events": events, "snapshot": {"trace_id": trace_id, "timeline_events": len(events), "last_event": events[-1]["event"] if events else None}}


@router.post("/run/stream")
async def run_agent_stream(payload: dict[str, Any] | None = None, principal: PrincipalDependency = None) -> dict[str, object]:
    return await run_agent(payload, principal)
