from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from backend.app.dependencies import (
    enforce_scope,
    get_api_key_store,
    get_approval_store,
    get_audit_store,
    get_current_principal,
    get_memory,
    get_run_store,
    get_trace_store,
    get_workflow_repository,
    get_workflow_schedule_store,
)
from backend.app.core.security import Principal

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
ApprovalStoreDependency = Annotated[object, Depends(get_approval_store)]
AuditStoreDependency = Annotated[object, Depends(get_audit_store)]
APIKeyStoreDependency = Annotated[object, Depends(get_api_key_store)]
MemoryDependency = Annotated[object, Depends(get_memory)]
RunStoreDependency = Annotated[object, Depends(get_run_store)]
TraceStoreDependency = Annotated[object, Depends(get_trace_store)]
WorkflowRepositoryDependency = Annotated[object, Depends(get_workflow_repository)]
WorkflowScheduleStoreDependency = Annotated[object, Depends(get_workflow_schedule_store)]


@router.get("/summary")
async def metrics_summary(
    principal: PrincipalDependency,
    approval_store: ApprovalStoreDependency,
    audit_store: AuditStoreDependency,
    api_key_store: APIKeyStoreDependency,
    memory: MemoryDependency,
    run_store: RunStoreDependency,
    trace_store: TraceStoreDependency,
    workflow_repository: WorkflowRepositoryDependency,
    workflow_schedule_store: WorkflowScheduleStoreDependency,
) -> dict[str, int]:
    enforce_scope(principal, "audit:read")
    return await _summary_payload(
        approval_store,
        audit_store,
        api_key_store,
        memory,
        run_store,
        trace_store,
        workflow_repository,
        workflow_schedule_store,
    )


@router.get("/prometheus", response_class=PlainTextResponse)
async def prometheus_metrics(
    approval_store: ApprovalStoreDependency,
    audit_store: AuditStoreDependency,
    api_key_store: APIKeyStoreDependency,
    memory: MemoryDependency,
    run_store: RunStoreDependency,
    trace_store: TraceStoreDependency,
    workflow_repository: WorkflowRepositoryDependency,
    workflow_schedule_store: WorkflowScheduleStoreDependency,
) -> str:
    summary = await _summary_payload(
        approval_store,
        audit_store,
        api_key_store,
        memory,
        run_store,
        trace_store,
        workflow_repository,
        workflow_schedule_store,
    )
    lines: list[str] = []
    for name, value in sorted(summary.items()):
        metric_name = f"xagent_{name}_total"
        lines.append(f"# TYPE {metric_name} gauge")
        lines.append(f"{metric_name} {value}")
    return "\n".join(lines) + "\n"


async def _summary_payload(
    approval_store,
    audit_store,
    api_key_store,
    memory,
    run_store,
    trace_store,
    workflow_repository,
    workflow_schedule_store,
) -> dict[str, int]:
    memory_count = memory.count()
    if hasattr(memory_count, "__await__"):
        memory_count = await memory_count
    return {
        "runs": run_store.count(),
        "traces": len(trace_store.list_trace_ids()),
        "trace_events": trace_store.event_count(),
        "memories": memory_count,
        "workflows": workflow_repository.definition_count(),
        "workflow_runs": workflow_repository.run_count(),
        "workflow_schedules": workflow_schedule_store.count(),
        "audit_logs": audit_store.count(),
        "api_keys": api_key_store.count(),
        "active_api_keys": api_key_store.active_count(),
        "approvals": approval_store.count(),
        "pending_approvals": approval_store.pending_count(),
    }
