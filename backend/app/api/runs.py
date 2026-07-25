from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.api.recovery_helpers import build_recovery_context
from backend.app.core.agent import AgentLoop
from backend.app.core.agent_serializers import serialize_run_view
from backend.app.core.contracts import AgentRunRecord, AgentRunResponse, ErrorCode, RunContext
from backend.app.core.security import Principal
from backend.app.dependencies import (
    enforce_scope,
    get_agent,
    get_current_principal,
    get_run_store,
    get_trace_store,
)

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])
AgentDependency = Annotated[AgentLoop, Depends(get_agent)]
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
RunStoreDependency = Annotated[object, Depends(get_run_store)]
TraceStoreDependency = Annotated[object, Depends(get_trace_store)]


class AgentRunStartRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=20_000)
    extra_context: dict[str, Any] = Field(default_factory=dict)
    async_run: bool = False


class RunViewModelEnvelope(BaseModel):
    run: dict[str, object]
    timeline: list[dict[str, object]]
    resource_type: str = "run"
    snapshot: dict[str, object] = Field(default_factory=dict)


class RunStatusEnvelope(BaseModel):
    trace_id: str
    resource_type: str = "run"
    status: str
    snapshot: dict[str, object] = Field(default_factory=dict)


def _context_from_principal(principal: Principal) -> RunContext:
    return RunContext(tenant_id=principal.tenant_id, user_id=principal.user_id, permission_scope=list(principal.scopes))




@router.get("", response_model=list[AgentRunRecord])
async def list_runs(
    run_store: RunStoreDependency,
    principal: PrincipalDependency,
    limit: int = Query(default=20, ge=1, le=100),
    status: str | None = None,
    user_id: str | None = None,
    trace_id: str | None = None,
) -> list[AgentRunRecord]:
    enforce_scope(principal, "agent:read")
    items = run_store.list(limit=limit)
    items = [item for item in items if item.tenant_id == principal.tenant_id]
    if status is not None:
        items = [item for item in items if item.status.value == status]
    if user_id is not None:
        items = [item for item in items if item.user_id == user_id]
    if trace_id is not None:
        items = [item for item in items if item.trace_id == trace_id]
    return items


@router.post("/start")
async def start_run(
    request: AgentRunStartRequest,
    agent: AgentDependency,
    principal: PrincipalDependency,
    run_store: RunStoreDependency,
) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    context = _context_from_principal(principal)
    result: AgentRunResponse = await agent.run(context, request.task, request.extra_context)
    record = run_store.save(context, request.task, result, run_view=result.execution_summary.get("run_view", {}))
    run_view = getattr(record, "run_view", {}) or {}
    recovery = run_view.get("recovery", {}) if isinstance(run_view, dict) else {}
    if not recovery:
        recovery = build_recovery_context(
            status=record.status.value,
            resource_type="run",
            resource_id=record.trace_id,
            next_actions=[
                "inspect run detail",
                "replay run" if record.status.value != "completed" else "review final output",
            ],
            latest_decision=record.status.value,
            retryable=record.status.value != "completed",
            confidence=0.95 if record.status.value == "completed" else 0.65,
            tool_name="replay_run" if record.status.value != "completed" else "inspect_run",
            follow_up=["inspect trace summary", "check execution summary"],
        )
    return serialize_run_view(
        trace_id=record.trace_id,
        status=record.status.value,
        recovery=recovery,
        snapshot={
            "trace_id": record.trace_id,
            "status": record.status.value,
            "iterations": record.iterations,
            "memory_hits": record.memory_hits,
            "tool_call_count": record.tool_call_count,
            "recovery": recovery.model_dump(mode="json") if hasattr(recovery, "model_dump") else recovery,
            "run_view": run_view,
        },
        summary=record.model_dump(mode="json"),
        metadata={
            "resource_type": "run",
            "run": record.model_dump(mode="json"),
        },
    )


@router.get("/{trace_id}", response_model=AgentRunRecord)
async def get_run(trace_id: str, run_store: RunStoreDependency, principal: PrincipalDependency) -> AgentRunRecord:
    enforce_scope(principal, "agent:read")
    record = run_store.get(trace_id)
    if record is None:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Run not found.", trace_id=trace_id)
    if record.tenant_id != principal.tenant_id:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Run not found.", trace_id=trace_id)
    return record


@router.get("/{trace_id}/status", response_model=RunStatusEnvelope)
async def get_run_status(trace_id: str, run_store: RunStoreDependency, trace_store: TraceStoreDependency, principal: PrincipalDependency) -> RunStatusEnvelope:
    enforce_scope(principal, "agent:read")
    record = run_store.get(trace_id)
    if record is None:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Run not found.", trace_id=trace_id)
    if record.tenant_id != principal.tenant_id:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Run not found.", trace_id=trace_id)
    summary = trace_store.get_summary(trace_id)
    run_view = getattr(record, "run_view", {}) or {}
    recovery = run_view.get("recovery", {}) if isinstance(run_view, dict) else {}
    if not recovery:
        recovery = build_recovery_context(
            status=record.status.value,
            resource_type="run",
            resource_id=record.trace_id,
            next_actions=["inspect trace summary", "review replay" if record.status.value != "completed" else "review completed run"],
            latest_decision=record.status.value,
            retryable=record.status.value != "completed",
            confidence=0.95 if record.status.value == "completed" else 0.65,
            tool_name="replay_run" if record.status.value != "completed" else "inspect_run",
            follow_up=["review trace events", "validate run output"],
        )
    return RunStatusEnvelope(
        trace_id=record.trace_id,
        status=record.status.value,
        snapshot={
            "trace_id": record.trace_id,
            "status": record.status.value,
            "event_count": summary.event_count,
            "started_at": summary.started_at,
            "ended_at": summary.ended_at,
            "iterations": record.iterations,
            "memory_hits": record.memory_hits,
            "tool_call_count": record.tool_call_count,
            "recovery": recovery.model_dump(mode="json") if hasattr(recovery, "model_dump") else recovery,
            "run_view": run_view,
        },
    )


@router.get("/{trace_id}/detail", response_model=RunViewModelEnvelope)
async def get_run_detail(trace_id: str, run_store: RunStoreDependency, trace_store: TraceStoreDependency, principal: PrincipalDependency) -> RunViewModelEnvelope:
    enforce_scope(principal, "agent:read")
    record = run_store.get(trace_id)
    if record is None:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Run not found.", trace_id=trace_id)
    if record.tenant_id != principal.tenant_id:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Run not found.", trace_id=trace_id)
    events = [event.model_dump(mode="json") for event in trace_store.list_events(trace_id)]
    run_view = getattr(record, "run_view", {}) or {}
    recovery = run_view.get("recovery", {}) if isinstance(run_view, dict) else {}
    if not recovery:
        recovery = build_recovery_context(
            status=record.status.value,
            resource_type="run",
            resource_id=record.trace_id,
            next_actions=["inspect timeline", "replay run" if record.status.value != "completed" else "review final result"],
            latest_decision=record.status.value,
            retryable=record.status.value != "completed",
            confidence=0.95 if record.status.value == "completed" else 0.65,
            tool_name="inspect_timeline",
            follow_up=["review execution steps", "inspect trace summary"],
            status_detail=f"run {record.status.value}",
            remediation="review timeline and replay if needed",
        )
    return RunViewModelEnvelope(
        run=record.model_dump(mode="json"),
        timeline=events,
        snapshot={
            "trace_id": record.trace_id,
            "status": record.status.value,
            "event_count": len(events),
            "iterations": record.iterations,
            "memory_hits": record.memory_hits,
            "tool_call_count": record.tool_call_count,
            "recovery": recovery.model_dump(mode="json") if hasattr(recovery, "model_dump") else recovery,
            "run_view": run_view,
        },
    )


@router.get("/{trace_id}/correlation", response_model=dict[str, object])
async def get_run_correlation(trace_id: str, run_store: RunStoreDependency, trace_store: TraceStoreDependency, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "agent:read")
    record = run_store.get(trace_id)
    if record is None:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Run not found.", trace_id=trace_id)
    if record.tenant_id != principal.tenant_id:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Run not found.", trace_id=trace_id)
    summary = trace_store.get_summary(trace_id)
    run_view = getattr(record, "run_view", {}) or {}
    recovery = run_view.get("recovery", {}) if isinstance(run_view, dict) else {}
    if not recovery:
        recovery = build_recovery_context(
            status=record.status.value,
            resource_type="run",
            resource_id=record.trace_id,
            next_actions=["inspect trace summary", "review run replay" if record.status.value != "completed" else "verify completed result"],
            latest_decision=record.status.value,
            retryable=record.status.value != "completed",
            confidence=0.95 if record.status.value == "completed" else 0.65,
            tool_name="replay_run" if record.status.value != "completed" else "inspect_run",
            follow_up=["inspect trace summary", "verify completed result"],
            status_detail=f"run {record.status.value}",
            remediation="replay run or verify completed output",
        )
    return serialize_run_view(
        trace_id=record.trace_id,
        status=record.status.value,
        recovery=recovery,
        snapshot={
            "resource_type": "run",
            "resource_id": record.trace_id,
            "trace_id": record.trace_id,
            "status": record.status.value,
            "iterations": record.iterations,
            "memory_hits": record.memory_hits,
            "tool_call_count": record.tool_call_count,
            "recovery": recovery.model_dump(mode="json") if hasattr(recovery, "model_dump") else recovery,
            "run_view": run_view,
        },
        summary=summary.model_dump(mode="json"),
        metadata={
            "resource_type": "run",
            "resource_id": record.trace_id,
        },
    )


@router.get("/{trace_id}/timeline")
async def get_run_timeline(trace_id: str, run_store: RunStoreDependency, trace_store: TraceStoreDependency, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "agent:read")
    record = run_store.get(trace_id)
    if record is None:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Run not found.", trace_id=trace_id)
    if record.tenant_id != principal.tenant_id:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Run not found.", trace_id=trace_id)
    events = [event.model_dump(mode="json") for event in trace_store.list_events(trace_id)]
    run_view = getattr(record, "run_view", {}) or {}
    return serialize_run_view(
        trace_id=trace_id,
        status=record.status.value,
        snapshot={
            "trace_id": trace_id,
            "event_count": len(events),
            "status": record.status.value,
            "run_view": run_view,
        },
        summary={"events": events, "run": record.model_dump(mode="json")},
        metadata={"resource_type": "run_timeline", "resource_id": trace_id, "events": events},
    )


@router.post("/{trace_id}/replay", response_model=AgentRunRecord)
async def replay_run(
    trace_id: str,
    agent: AgentDependency,
    run_store: RunStoreDependency,
    principal: PrincipalDependency,
) -> AgentRunRecord:
    enforce_scope(principal, "agent:run")
    record = run_store.get(trace_id)
    if record is None:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Run not found.", trace_id=trace_id)
    if record.tenant_id != principal.tenant_id:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Run not found.", trace_id=trace_id)
    context = RunContext(tenant_id=principal.tenant_id, user_id=principal.user_id, permission_scope=list(principal.scopes))
    result = await agent.run(context, record.task, {"replay_of": trace_id})
    return run_store.save(context, record.task, result, run_view=result.execution_summary.get("run_view", {}))
