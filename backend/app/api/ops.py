from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_approval_store, get_run_store, get_trace_store, get_agent, get_current_principal

router = APIRouter(prefix="/api/v1/ops", tags=["ops"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.get("/summary")
async def get_ops_summary(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "audit:read")
    trace_store = get_trace_store()
    run_store = get_run_store()
    approval_store = get_approval_store()
    agent = get_agent()

    failure_traces = []
    for summary in trace_store.list_summaries(limit=200):
        snapshot = summary.snapshot or {}
        if snapshot.get("status") in {"failed", "error"} or summary.last_event in {"agent.failed", "tool.execution.failed"}:
            failure_traces.append({
                "trace_id": summary.trace_id,
                "status": snapshot.get("status") or "failed",
                "last_event": summary.last_event,
                "event_count": summary.event_count,
            })

    approval_backlog = approval_store.pending_count()
    tool_failures = 0
    for record in run_store.list(limit=200):
        if record.status in {"failed", "error"}:
            tool_failures += max(record.tool_call_count, 1)

    healthy = approval_backlog == 0 and tool_failures == 0 and len(failure_traces) == 0

    return {
        "healthy": healthy,
        "failure_traces": failure_traces[:10],
        "approval_backlog": approval_backlog,
        "tool_failures": tool_failures,
        "overview": {
            "traces": trace_store.event_count(),
            "runs": run_store.count(),
            "approvals": approval_store.count(),
            "tools": len(agent.tools.manifest()),
        },
    }
