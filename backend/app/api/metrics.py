"""Prometheus metrics endpoint for X-Agent."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from fastapi.responses import PlainTextResponse

from backend.app.core.security import Principal
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

# ---------------------------------------------------------------------------
# Prometheus client integration (optional dependency)
# ---------------------------------------------------------------------------
try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

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

# ---------------------------------------------------------------------------
# Real Prometheus metric definitions (Phase 2.6)
# ---------------------------------------------------------------------------
if PROMETHEUS_AVAILABLE:
    from prometheus_client import REGISTRY as _REGISTRY

    def _get_or_create(metric_cls, name, *args, **kwargs):
        """Get existing metric or create new one (avoids duplicate registration)."""
        try:
            return metric_cls(name, *args, **kwargs)
        except ValueError:
            # Already registered - retrieve from registry
            return _REGISTRY._names_to_collectors.get(name.removesuffix("_total").removesuffix("_created"))

    # Agent execution metrics
    AGENT_RUNS_TOTAL = _get_or_create(
        Counter,
        "xagent_agent_runs_total",
        "Total agent runs",
        ["status"],
    )
    AGENT_RUN_DURATION = _get_or_create(
        Histogram,
        "xagent_agent_run_duration_seconds",
        "Agent run duration",
        buckets=[0.5, 1, 2, 5, 10, 30, 60, 120, 300],
    )

    # LLM backend metrics
    LLM_CALLS_TOTAL = _get_or_create(
        Counter,
        "xagent_llm_calls_total",
        "LLM API calls",
        ["backend", "model"],
    )
    LLM_TOKENS_TOTAL = _get_or_create(
        Counter,
        "xagent_llm_tokens_total",
        "LLM tokens consumed",
        ["backend", "type"],
    )

    # Memory subsystem metrics
    MEMORY_OPS_TOTAL = _get_or_create(
        Counter,
        "xagent_memory_ops_total",
        "Memory operations",
        ["op", "layer"],
    )

    # Workflow metrics
    WORKFLOW_RUNS_TOTAL = _get_or_create(
        Counter,
        "xagent_workflow_runs_total",
        "Workflow runs",
        ["status"],
    )

    # Connection metrics
    ACTIVE_CONNECTIONS = _get_or_create(
        Gauge,
        "xagent_active_connections",
        "Active SSE connections",
    )


@router.get("/metrics")
async def metrics_endpoint() -> Response:
    """Expose Prometheus metrics in standard exposition format."""
    if not PROMETHEUS_AVAILABLE:
        return Response(
            content="# prometheus_client not installed\n",
            media_type="text/plain",
        )
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


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
