from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from backend.app.api.errors import api_error
from backend.app.api.linked_summary import LinkedSummaryEnvelope, build_linked_summary
from backend.app.api.recovery_helpers import build_recovery_context
from backend.app.core.agent_serializers import serialize_run_view
from backend.app.core.approvals import ApprovalStore
from backend.app.core.audit import AuditStore
from backend.app.core.contracts import ErrorCode, TraceDetail, TraceSummary
from backend.app.core.memory import MemorySystem
from backend.app.core.security import Principal
from backend.app.core.runs import RunStore
from backend.app.core.tools import ToolExecutionStore
from backend.app.dependencies import (
    enforce_scope,
    get_approval_store,
    get_audit_store,
    get_current_principal,
    get_memory,
    get_run_store,
    get_trace_store,
    get_agent,
)

router = APIRouter(prefix="/api/v1/traces", tags=["traces"])
TraceStoreDependency = Annotated[object, Depends(get_trace_store)]
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
RunStoreDependency = Annotated[RunStore, Depends(get_run_store)]
ApprovalStoreDependency = Annotated[ApprovalStore, Depends(get_approval_store)]
AuditStoreDependency = Annotated[AuditStore, Depends(get_audit_store)]
MemoryDependency = Annotated[MemorySystem, Depends(get_memory)]
ToolExecutionStoreDependency = Annotated[ToolExecutionStore | None, Depends(lambda: get_agent().tools.get_execution_store())]


@router.get("")
async def list_traces(
    trace_store: TraceStoreDependency,
    principal: PrincipalDependency,
    limit: int = Query(default=20, ge=1, le=100),
    agent_id: str | None = None,
    user_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, object]:
    enforce_scope(principal, "audit:read")
    summaries = trace_store.list_summaries(limit=10_000)
    filtered = [
        summary.model_dump(mode="json")
        for summary in summaries
        if summary.snapshot.get("tenant_id") == principal.tenant_id
        and (agent_id is None or summary.snapshot.get("agent_id") == agent_id)
        and (user_id is None or summary.snapshot.get("user_id") == user_id)
        and (request_id is None or summary.snapshot.get("request_id") == request_id)
    ]
    primary = {
        "count": len(filtered[:limit]),
        "items": filtered[:limit],
        "filters": {"agent_id": agent_id, "user_id": user_id, "request_id": request_id},
    }
    return build_linked_summary(resource_type="trace_list", resource_id="trace_list", primary=primary, trace={"count": len(filtered[:limit]), "items": filtered[:limit], "filters": {"agent_id": agent_id, "user_id": user_id, "request_id": request_id}}, extra=primary)


@router.get("/{trace_id}", response_model=TraceDetail)
async def get_trace(
    trace_id: str,
    trace_store: TraceStoreDependency,
    principal: PrincipalDependency,
) -> TraceDetail:
    enforce_scope(principal, "audit:read")
    events = trace_store.list_events(trace_id)
    if not events:
        raise api_error(
            404,
            ErrorCode.TRACE_NOT_FOUND,
            "Trace not found.",
            trace_id=trace_id,
        )
    summary = trace_store.get_summary(trace_id)
    if summary.snapshot.get("tenant_id") != principal.tenant_id:
        raise api_error(404, ErrorCode.TRACE_NOT_FOUND, "Trace not found.", trace_id=trace_id)
    snapshot = summary.snapshot if isinstance(summary.snapshot, dict) else {}
    run_view = snapshot.get("run_view", {}) if isinstance(snapshot, dict) else {}
    recovery = run_view.get("recovery", {}) if isinstance(run_view, dict) else {}
    recovery_plan = {}
    if isinstance(run_view, dict):
        inner_snapshot = run_view.get("snapshot", {})
        if isinstance(inner_snapshot, dict):
            recovery_plan = inner_snapshot.get("recovery_plan", {}) if isinstance(inner_snapshot.get("recovery_plan", {}), dict) else {}
    if not recovery_plan and isinstance(snapshot, dict):
        recovery_plan = snapshot.get("recovery_plan", {}) if isinstance(snapshot.get("recovery_plan", {}), dict) else {}
    if not recovery:
        recovery = build_recovery_context(
            status=str(snapshot.get("status", "unknown")) if isinstance(snapshot, dict) else "unknown",
            resource_type="trace",
            resource_id=summary.trace_id,
            next_actions=recovery_plan.get("next_actions", []) if isinstance(recovery_plan, dict) else [],
            recovery_plan=recovery_plan,
            branch=snapshot.get("last_agent_recovery_branch") if isinstance(snapshot, dict) else None,
            retryable=bool(recovery_plan),
            confidence=0.8 if recovery_plan else 0.5,
            tool_name="inspect_trace",
            follow_up=["review trace summary", "inspect replay"],
            status_detail=f"trace {summary.event_count} events",
            remediation="review trace summary and replay if needed",
        )
    run_summary, approval_summary, audit_summary, memory_summary, tool_summary = _build_linked_summaries(
        trace_id=trace_id,
        trace_summary=summary,
        snapshot=snapshot,
        run_view=run_view,
    )
    linked_payload = build_linked_summary(
        resource_type="trace",
        resource_id=summary.trace_id,
        primary=summary.model_dump(mode="json"),
        run=run_summary,
        audit=audit_summary,
        approvals=approval_summary,
        memory=memory_summary,
        tools=tool_summary,
        extra={
            "event_count": summary.event_count,
            "last_event": summary.last_event,
            "task": summary.task,
            "run_view": run_view,
            "recovery": recovery.model_dump(mode="json") if hasattr(recovery, "model_dump") else recovery,
        },
    )
    linked_payload["snapshot"].update({"recovery": recovery.model_dump(mode="json") if hasattr(recovery, "model_dump") else recovery})
    return linked_payload


@router.get("/{trace_id}/correlation")
async def get_trace_correlation(
    trace_id: str,
    trace_store: TraceStoreDependency,
    principal: PrincipalDependency,
) -> dict[str, object]:
    enforce_scope(principal, "audit:read")
    summary = trace_store.get_summary(trace_id)
    if summary.event_count == 0:
        raise api_error(
            404,
            ErrorCode.TRACE_NOT_FOUND,
            "Trace not found.",
            trace_id=trace_id,
        )
    if summary.snapshot.get("tenant_id") != principal.tenant_id:
        raise api_error(404, ErrorCode.TRACE_NOT_FOUND, "Trace not found.", trace_id=trace_id)
    snapshot = summary.snapshot if isinstance(summary.snapshot, dict) else {}
    run_view = snapshot.get("run_view", {}) if isinstance(snapshot, dict) else {}
    recovery = run_view.get("recovery", {}) if isinstance(run_view, dict) else {}
    recovery_plan = {}
    if isinstance(run_view, dict):
        inner_snapshot = run_view.get("snapshot", {})
        if isinstance(inner_snapshot, dict):
            recovery_plan = inner_snapshot.get("recovery_plan", {}) if isinstance(inner_snapshot.get("recovery_plan", {}), dict) else {}
    if not recovery_plan and isinstance(snapshot, dict):
        recovery_plan = snapshot.get("recovery_plan", {}) if isinstance(snapshot.get("recovery_plan", {}), dict) else {}
    if not recovery:
        recovery = build_recovery_context(
            status=str(snapshot.get("status", "unknown")) if isinstance(snapshot, dict) else "unknown",
            resource_type="trace",
            resource_id=summary.trace_id,
            next_actions=recovery_plan.get("next_actions", []) if isinstance(recovery_plan, dict) else [],
            recovery_plan=recovery_plan,
            branch=snapshot.get("last_agent_recovery_branch") if isinstance(snapshot, dict) else None,
            retryable=bool(recovery_plan),
            confidence=0.8 if recovery_plan else 0.5,
            tool_name="inspect_trace",
            follow_up=["review trace summary", "inspect replay"],
            status_detail=f"trace {summary.event_count} events",
            remediation="review trace summary and replay if needed",
        )
    run_summary, approval_summary, audit_summary, memory_summary, tool_summary = _build_linked_summaries(
        trace_id=trace_id,
        trace_summary=summary,
        snapshot=snapshot,
        run_view=run_view,
    )
    return build_linked_summary(
        resource_type="trace",
        resource_id=summary.trace_id,
        primary=summary.model_dump(mode="json"),
        run=run_summary,
        audit=audit_summary,
        approvals=approval_summary,
        memory=memory_summary,
        tools=tool_summary,
        extra={
            "event_count": summary.event_count,
            "last_event": summary.last_event,
            "task": summary.task,
            "run_view": run_view,
            "recovery": recovery.model_dump(mode="json") if hasattr(recovery, "model_dump") else recovery,
        },
    )


@router.get("/{trace_id}/replay")
async def get_trace_replay(
    trace_id: str,
    trace_store: TraceStoreDependency,
    run_store: RunStoreDependency,
    approval_store: ApprovalStoreDependency,
    audit_store: AuditStoreDependency,
    memory: MemoryDependency,
    principal: PrincipalDependency,
) -> dict[str, object]:
    _enforce_trace_scope(principal)
    summary = trace_store.get_summary(trace_id)
    if summary.event_count == 0:
        raise api_error(404, ErrorCode.TRACE_NOT_FOUND, "Trace not found.", trace_id=trace_id)

    run = run_store.get(trace_id)
    approvals = approval_store.list(limit=200, tenant_id=summary.snapshot.get("tenant_id"))
    related_approvals = [record.model_dump(mode="json") for record in approvals if record.trace_id == trace_id or record.execution_trace_id == trace_id]
    audit_records = [
        record.model_dump(mode="json")
        for record in audit_store.list(limit=200, tenant_id=summary.snapshot.get("tenant_id"))
        if record.trace_id == trace_id or record.run_id == trace_id or record.workflow_id == trace_id
    ]
    memory_items = [
        item.model_dump(mode="json")
        for item in memory.layer_items(1) + memory.layer_items(2) + memory.layer_items(3) + memory.layer_items(4)
        if item.metadata.get("trace_id") == trace_id or item.metadata.get("request_id") == summary.snapshot.get("request_id")
    ] if hasattr(memory, "layer_items") else []

    snapshot = summary.snapshot if isinstance(summary.snapshot, dict) else {}
    run_view = snapshot.get("run_view", {}) if isinstance(snapshot, dict) else {}
    recovery = run_view.get("recovery", {}) if isinstance(run_view, dict) else {}
    recovery_plan = {}
    if isinstance(run_view, dict):
        inner_snapshot = run_view.get("snapshot", {})
        if isinstance(inner_snapshot, dict):
            recovery_plan = inner_snapshot.get("recovery_plan", {}) if isinstance(inner_snapshot.get("recovery_plan", {}), dict) else {}
    if not recovery_plan and isinstance(snapshot, dict):
        recovery_plan = snapshot.get("recovery_plan", {}) if isinstance(snapshot.get("recovery_plan", {}), dict) else {}
    if not recovery:
        recovery = build_recovery_context(
            status=str(snapshot.get("status", "unknown")) if isinstance(snapshot, dict) else "unknown",
            resource_type="trace_replay",
            resource_id=trace_id,
            next_actions=recovery_plan.get("next_actions", []) if isinstance(recovery_plan, dict) else [],
            recovery_plan=recovery_plan,
            branch=snapshot.get("last_agent_recovery_branch") if isinstance(snapshot, dict) else None,
            retryable=bool(recovery_plan),
            confidence=0.8 if recovery_plan else 0.5,
            tool_name="inspect_trace_replay",
            follow_up=["review replay output", "continue with related resources"],
            status_detail=f"trace replay for {summary.trace_id}",
            remediation="review replay output and continue with linked resources",
        )
    tool_executions = _collect_tool_executions(trace_id)
    run_view_payload = run.run_view if run and isinstance(run.run_view, dict) else run_view if isinstance(run_view, dict) else {}
    run_snapshot = run.snapshot if run and isinstance(run.snapshot, dict) else {}
    audit_summary = {
        "count": len(audit_records),
        "actions": sorted({record.get("action", "") for record in audit_records if isinstance(record, dict) and record.get("action")}),
        "resource_types": sorted({record.get("resource_type", "") for record in audit_records if isinstance(record, dict) and record.get("resource_type")}),
    }
    memory_summary = {
        "count": len(memory_items),
        "layers": sorted({item.get("layer") for item in memory_items if isinstance(item, dict) and item.get("layer") is not None}),
    }
    approval_summary = {
        "count": len(related_approvals),
        "statuses": sorted({record.get("status", "") for record in related_approvals if isinstance(record, dict) and record.get("status")}),
    }
    tool_summary = {
        "count": len(tool_executions),
        "names": sorted({record.get("tool_name", "") for record in tool_executions if isinstance(record, dict) and record.get("tool_name")}),
        "failures": sum(1 for record in tool_executions if isinstance(record, dict) and not record.get("success", False)),
    }
    primary = {
        "trace_summary": summary.model_dump(mode="json"),
        "recovery": recovery.model_dump(mode="json") if hasattr(recovery, "model_dump") else recovery,
        "events": trace_store.list_events(trace_id),
        "related_resources": {
            "run": run_summary,
            "approvals": related_approvals,
            "audit_records": audit_records,
            "memory_items": memory_items,
            "tool_executions": tool_executions,
        },
    }
    return build_linked_summary(
        resource_type="trace_replay",
        resource_id=trace_id,
        primary=primary,
        trace={"summary": summary.model_dump(mode="json"), "event_count": summary.event_count, "last_event": summary.last_event, "task": summary.task},
        run=run_summary,
        audit=audit_summary,
        approvals=approval_summary,
        memory=memory_summary,
        tools=tool_summary,
        extra={
            "trace_summary": summary.model_dump(mode="json"),
            "recovery": recovery.model_dump(mode="json") if hasattr(recovery, "model_dump") else recovery,
            "events": trace_store.list_events(trace_id),
            "related_resources": {
                "run": run_summary,
                "approvals": related_approvals,
                "audit_records": audit_records,
                "memory_items": memory_items,
                "tool_executions": tool_executions,
            },
        },
    )


@router.get("/{trace_id}/debug")
async def get_trace_debug(
    trace_id: str,
    trace_store: TraceStoreDependency,
    run_store: RunStoreDependency,
    approval_store: ApprovalStoreDependency,
    audit_store: AuditStoreDependency,
    memory: MemoryDependency,
    principal: PrincipalDependency,
) -> dict[str, object]:
    _enforce_trace_scope(principal)
    replay = await get_trace_replay(trace_id, trace_store, run_store, approval_store, audit_store, memory, principal)
    replay["resource_type"] = "trace_debug"
    replay["snapshot"]["resource_type"] = "trace_debug"
    replay["linked_summaries"]["primary"]["debug"] = {
        "failure_points": [event for event in replay["snapshot"].get("events", []) if isinstance(event, dict) and event.get("kind") in {"agent.failed", "tool.execution.failed"}],
        "latest_event": replay["snapshot"].get("events", [])[-1] if replay["snapshot"].get("events") else None,
    }
    replay["snapshot"]["linked_summaries"]["primary"]["debug"] = replay["linked_summaries"]["primary"]["debug"]
    return replay


def _collect_tool_executions(trace_id: str) -> list[dict[str, object]]:
    store = get_agent().tools.get_execution_store()
    if store is None:
        return []
    return [record.model_dump(mode="json") for record in store.by_trace(trace_id)]


def _build_linked_summaries(
    *,
    trace_id: str,
    trace_summary: TraceSummary,
    snapshot: dict[str, object],
    run_view: dict[str, object],
) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    run_summary = {
        "trace_id": snapshot.get("trace_id", trace_id),
        "status": snapshot.get("status", "unknown"),
        "iterations": snapshot.get("iterations"),
        "memory_hits": snapshot.get("memory_hits"),
        "tool_call_count": snapshot.get("tool_call_count"),
        "run_view": run_view,
        "snapshot": snapshot,
    }
    approval_summary = {
        "count": int(snapshot.get("related_approvals", 0) or 0),
        "statuses": [],
    }
    audit_summary = {
        "count": int(snapshot.get("related_audits", 0) or 0),
        "actions": [],
        "resource_types": [],
    }
    memory_summary = {
        "count": int(snapshot.get("related_memory_items", 0) or 0),
        "layers": [],
    }
    tool_summary = {
        "count": int(snapshot.get("related_tool_executions", 0) or 0),
        "names": [],
        "failures": 0,
    }
    return run_summary, approval_summary, audit_summary, memory_summary, tool_summary


def _enforce_trace_scope(principal: Principal, trace_tenant_id: str | None = None) -> None:
    enforce_scope(principal, "audit:read")
    if trace_tenant_id is not None and trace_tenant_id != principal.tenant_id:
        raise api_error(404, ErrorCode.TRACE_NOT_FOUND, "Trace not found.")
