from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode, RunContext
from backend.app.core.security import Principal
from backend.app.dependencies import (
    enforce_scope,
    get_agent,
    get_audit_store,
    get_current_principal,
    get_run_store,
    get_trace_store,
)

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
    # Include principal wildcard scopes (e.g. "tool:*") so the agent loop
    # can use any tool without the client enumerating each one explicitly.
    for scope in principal_scopes:
        if scope.endswith(":*") and scope not in allowed_scope:
            allowed_scope.append(scope)
    context = RunContext(
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        permission_scope=allowed_scope,
    )
    # Allow per-request override of max_iterations for long-running tasks
    req_max_iter = request.get("max_iterations")
    if req_max_iter and isinstance(req_max_iter, int) and 1 <= req_max_iter <= 100:
        agent.max_iterations = req_max_iter
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
async def run_agent_stream(payload: dict[str, Any] | None = None, principal: PrincipalDependency = None):
    """True SSE streaming endpoint: emits real-time trace events as the agent works."""
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
    for scope in principal_scopes:
        if scope.endswith(":*") and scope not in allowed_scope:
            allowed_scope.append(scope)
    context = RunContext(
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        permission_scope=allowed_scope,
    )
    req_max_iter = request.get("max_iterations")
    if req_max_iter and isinstance(req_max_iter, int) and 1 <= req_max_iter <= 100:
        agent.max_iterations = req_max_iter

    # asyncio.Queue 桥接 event_callback → SSE generator
    queue: asyncio.Queue[dict | None] = asyncio.Queue()

    def _on_event(trace_event) -> None:
        """Synchronous callback that pushes trace events into the queue."""
        try:
            data = trace_event.model_dump(mode="json") if hasattr(trace_event, "model_dump") else {"event": str(trace_event)}
            queue.put_nowait(data)
        except Exception:
            pass

    async def _run_agent_task():
        """Background task: run agent and signal completion."""
        try:
            result = await agent.run(context, task, request.get("extra_context", {}), event_callback=_on_event)
            get_audit_store().record(
                action="agent.run.stream",
                resource_type="agent",
                resource_id=context.agent_id,
                tenant_id=context.tenant_id,
                actor_id=context.user_id,
                trace_id=result.trace_id,
                run_id=result.trace_id,
                details={"task_preview": task[:120], "status": result.status.value, "tool_call_count": len(result.tool_calls)},
            )
            # Push final result as completion signal
            queue.put_nowait({"_final": True, "result": result.model_dump(mode="json")})
        except Exception as exc:
            queue.put_nowait({"_final": True, "error": str(exc)})
        finally:
            queue.put_nowait(None)  # Sentinel to stop generator

    async def _sse_generator():
        """Yield SSE events from the queue until sentinel."""
        # Start agent in background
        bg_task = asyncio.create_task(_run_agent_task())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                if item.get("_final"):
                    final_data = json.dumps(item, ensure_ascii=False, default=str)
                    yield f"event: completed\ndata: {final_data}\n\n"
                else:
                    event_data = json.dumps(item, ensure_ascii=False, default=str)
                    yield f"event: trace\ndata: {event_data}\n\n"
        finally:
            if not bg_task.done():
                bg_task.cancel()

    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
