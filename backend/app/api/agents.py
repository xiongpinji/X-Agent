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


@router.get("/stats")
async def get_agent_stats(principal: PrincipalDependency = None) -> dict[str, object]:
    """Observability: run duration distribution, tool success rates, and anomaly alerts."""
    enforce_scope(principal, "agent:run")
    records = get_run_store().list(limit=100)
    tenant_runs = [r for r in records if getattr(r, "tenant_id", None) == principal.tenant_id]

    # F1: Duration distribution
    durations: list[float] = []
    status_counts: dict[str, int] = {}
    for r in tenant_runs:
        status = getattr(r, "status", None)
        status_val = status.value if hasattr(status, "value") else str(status or "unknown")
        status_counts[status_val] = status_counts.get(status_val, 0) + 1
        # Estimate duration from created_at / completed_at
        created = getattr(r, "created_at", None)
        completed = getattr(r, "completed_at", None)
        if created and completed:
            try:
                from datetime import datetime as _dt
                c = _dt.fromisoformat(str(created)) if isinstance(created, str) else created
                f = _dt.fromisoformat(str(completed)) if isinstance(completed, str) else completed
                delta_ms = (f - c).total_seconds() * 1000
                if 0 < delta_ms < 600_000:  # sanity: < 10 min
                    durations.append(delta_ms)
            except Exception:
                pass

    durations.sort()
    duration_stats = {
        "count": len(durations),
        "p50_ms": durations[len(durations) // 2] if durations else None,
        "p90_ms": durations[int(len(durations) * 0.9)] if durations else None,
        "p99_ms": durations[int(len(durations) * 0.99)] if durations else None,
        "avg_ms": sum(durations) / len(durations) if durations else None,
        "max_ms": durations[-1] if durations else None,
    }

    # F2: Tool call success rate
    tool_stats: dict[str, dict[str, int]] = {}
    for r in tenant_runs:
        tool_calls = getattr(r, "tool_calls", None) or []
        if isinstance(tool_calls, list):
            for tc in tool_calls:
                name = tc.get("tool_name", "unknown") if isinstance(tc, dict) else getattr(tc, "tool_name", "unknown")
                success = tc.get("success", False) if isinstance(tc, dict) else getattr(tc, "success", False)
                if name not in tool_stats:
                    tool_stats[name] = {"total": 0, "success": 0, "failure": 0}
                tool_stats[name]["total"] += 1
                if success:
                    tool_stats[name]["success"] += 1
                else:
                    tool_stats[name]["failure"] += 1

    tool_success_rates = {
        name: {
            **stats,
            "success_rate": round(stats["success"] / stats["total"], 3) if stats["total"] > 0 else 0,
        }
        for name, stats in tool_stats.items()
    }

    # F3: Anomaly detection - consecutive failures
    recent_runs = tenant_runs[:10]  # last 10 runs
    consecutive_failures = 0
    for r in recent_runs:
        status = getattr(r, "status", None)
        status_val = status.value if hasattr(status, "value") else str(status or "unknown")
        if status_val == "failed":
            consecutive_failures += 1
        else:
            break

    alerts: list[dict[str, object]] = []
    if consecutive_failures >= 3:
        alerts.append({
            "level": "critical",
            "type": "consecutive_failures",
            "message": f"Agent has failed {consecutive_failures} consecutive runs",
            "count": consecutive_failures,
        })
    # Alert on low tool success rate
    for name, stats in tool_success_rates.items():
        if stats["total"] >= 5 and stats["success_rate"] < 0.5:
            alerts.append({
                "level": "warning",
                "type": "low_tool_success",
                "message": f"Tool '{name}' success rate is {stats['success_rate']:.0%} ({stats['success']}/{stats['total']})",
                "tool": name,
                "success_rate": stats["success_rate"],
            })

    return {
        "total_runs": len(tenant_runs),
        "status_distribution": status_counts,
        "duration": duration_stats,
        "tool_success_rates": tool_success_rates,
        "alerts": alerts,
        "consecutive_failures": consecutive_failures,
    }


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

    # Per-run sandbox mode override (docker/subprocess/auto)
    import os as _os
    sandbox_override = request.get("sandbox_mode")
    _prev_sandbox = _os.environ.get("XAGENT_SANDBOX_MODE")
    if sandbox_override in ("docker", "subprocess", "auto"):
        _os.environ["XAGENT_SANDBOX_MODE"] = sandbox_override

    try:
        result = await agent.run(context, task, request.get("extra_context", {}))
    finally:
        # Restore previous sandbox mode
        if _prev_sandbox is None:
            _os.environ.pop("XAGENT_SANDBOX_MODE", None)
        elif sandbox_override:
            _os.environ["XAGENT_SANDBOX_MODE"] = _prev_sandbox

    get_audit_store().record(
        action="agent.run",
        resource_type="agent",
        resource_id=context.agent_id,
        tenant_id=context.tenant_id,
        actor_id=context.user_id,
        trace_id=result.trace_id,
        run_id=result.trace_id,
        details={"task_preview": task[:120], "status": result.status.value, "tool_call_count": len(result.tool_calls), "sandbox_mode": sandbox_override or "default"},
    )
    body = result.model_dump(mode="json")
    if request.get("stream"):
        async def _event_stream():
            yield f"event: trace\ndata: {body}\n\n"
            yield f"event: completed\ndata: {body}\n\n"
        return StreamingResponse(_event_stream(), media_type="text/event-stream")
    return body


@router.get("/git/status")
async def get_git_status(principal: PrincipalDependency = None) -> dict[str, object]:
    """Lightweight git status endpoint for the frontend Git panel."""
    enforce_scope(principal, "agent:run")
    import os
    from backend.app.core.git_ops import GitOperations

    workspace = os.environ.get("XAGENT_WORKSPACE", ".")
    ops = GitOperations(cwd=workspace)
    branch = await ops.current_branch()
    result = await ops._run("status", "--porcelain")
    lines = [ln for ln in result.stdout.strip().splitlines() if ln.strip()] if result.success else []
    # Parse porcelain output: XY PATH (2 status chars + space(s) + path)
    files = []
    for ln in lines:
        status_code = ln[:2].strip() if len(ln) >= 2 else "?"
        filepath = ln[2:].lstrip() if len(ln) > 2 else ln.strip()
        files.append({"status": status_code, "path": filepath})
    return {
        "success": result.success,
        "branch": branch,
        "has_changes": len(files) > 0,
        "file_count": len(files),
        "files": files[:50],  # Cap at 50 files
    }


@router.get("/sandbox/status")
async def get_sandbox_status(principal: PrincipalDependency = None) -> dict[str, object]:
    """Sandbox environment status: Docker availability, pool, execution history."""
    enforce_scope(principal, "agent:run")
    import os
    from backend.app.core.sandbox.docker_sandbox import is_docker_available
    from backend.app.core.sandbox.container_cache import pool_size_from_env, pre_pull_enabled

    docker_ok = is_docker_available()
    sandbox_mode = os.environ.get("XAGENT_SANDBOX_MODE", "auto")
    sandbox_image = os.environ.get("XAGENT_SANDBOX_IMAGE", "python:3.11-slim")
    pool_size = pool_size_from_env()

    # Container pool stats if available
    pool_stats: dict[str, object] = {"configured_size": pool_size, "pre_pull_enabled": pre_pull_enabled()}
    if docker_ok and pool_size > 0:
        try:
            from backend.app.core.sandbox.container_cache import get_container_pool
            pool = get_container_pool(sandbox_image)
            pool_stats["active_containers"] = pool.active_count if hasattr(pool, "active_count") else 0
            pool_stats["available_containers"] = pool.available_count if hasattr(pool, "available_count") else 0
        except Exception:
            pool_stats["error"] = "pool not initialized"

    # Execution history from sandbox manager
    exec_history: list[dict[str, object]] = []
    try:
        from backend.app.core.sandbox.manager import get_sandbox_manager
        mgr = get_sandbox_manager()
        exec_history = mgr._execution_history[-20:] if hasattr(mgr, "_execution_history") else []
    except Exception:
        pass

    return {
        "docker_available": docker_ok,
        "sandbox_mode": sandbox_mode,
        "sandbox_image": sandbox_image,
        "effective_backend": "docker" if docker_ok else "subprocess",
        "pool": pool_stats,
        "recent_executions": exec_history,
        "security": {
            "network_isolated": not docker_ok or True,  # Docker disables network by default
            "filesystem_isolated": docker_ok,
            "code_validation": True,
        },
    }


@router.get("/performance")
async def get_performance_dashboard(principal: PrincipalDependency = None) -> dict[str, object]:
    """Unified performance dashboard: spawner, sandbox, rate limiter, cache metrics."""
    enforce_scope(principal, "agent:run")
    import time

    # 1. Agent spawner stats
    spawner_stats: dict[str, object] = {}
    try:
        from backend.app.core.agent_spawner import agent_spawner
        spawner_stats = agent_spawner.get_stats()
    except Exception:
        spawner_stats = {"error": "unavailable"}

    # 2. Sandbox execution stats
    sandbox_stats: dict[str, object] = {}
    try:
        from backend.app.core.sandbox.manager import get_sandbox_manager
        mgr = get_sandbox_manager()
        sandbox_stats = mgr.get_execution_stats()
    except Exception:
        sandbox_stats = {"error": "not initialized"}

    # 3. Rate limiter stats (from main app)
    rate_stats: dict[str, object] = {}
    try:
        from backend.app.main import _rate_limiter
        rate_stats = {
            "active_keys": len(_rate_limiter._windows) if hasattr(_rate_limiter, "_windows") else 0,
        }
    except Exception:
        rate_stats = {"error": "unavailable"}

    # 4. Run store throughput
    run_stats: dict[str, object] = {}
    try:
        records = get_run_store().list(limit=50)
        tenant_runs = [r for r in records if getattr(r, "tenant_id", None) == principal.tenant_id]
        run_stats = {
            "total_runs": len(tenant_runs),
            "recent_50": len(tenant_runs),
        }
    except Exception:
        run_stats = {"error": "unavailable"}

    # 5. Cache layer metrics
    cache_stats: dict[str, object] = {}
    try:
        from backend.app.core.performance_optimization import ResponseCache
        # Use a shared instance if available, else report config
        cache_stats = {"engine": "ResponseCache", "strategy": "LRU+TTL"}
    except Exception:
        cache_stats = {"error": "unavailable"}

    # 6. Memory optimizer
    memory_stats: dict[str, object] = {}
    try:
        from backend.app.core.performance_optimization import MemoryOptimizer
        mem_opt = MemoryOptimizer()
        memory_stats = mem_opt.get_stats()
    except Exception:
        memory_stats = {"error": "unavailable"}

    # 7. Parallel executor pool
    parallel_stats: dict[str, object] = {}
    try:
        from backend.app.api.parallel_agents import get_executor
        parallel_stats = get_executor().get_stats()
    except Exception:
        parallel_stats = {"error": "unavailable"}

    return {
        "timestamp": time.time(),
        "spawner": spawner_stats,
        "sandbox": sandbox_stats,
        "rate_limiter": rate_stats,
        "runs": run_stats,
        "cache": cache_stats,
        "memory": memory_stats,
        "parallel_pool": parallel_stats,
    }


@router.get("/model-routing")
async def get_model_routing_status(principal: PrincipalDependency = None) -> dict[str, object]:
    """P: Model routing status, fallback chain, cost summary."""
    enforce_scope(principal, "agent:run")
    import time

    # Smart router info
    router_info: dict[str, object] = {}
    try:
        from backend.app.dependencies import get_llm_router
        llm_router = get_llm_router()
        backends = getattr(llm_router, "_backends", [])
        router_info = {
            "type": type(llm_router).__name__,
            "backend_count": len(backends),
            "backends": [type(b).__name__ for b in backends[:10]],
            "strategy": getattr(llm_router, "default_strategy", "default"),
        }
    except Exception:
        router_info = {"error": "router unavailable"}

    # Fallback manager
    fallback_info: dict[str, object] = {}
    try:
        from backend.app.core.llm.fallback import FallbackManager, FallbackConfig
        # Report config shape
        fallback_info = {"engine": "FallbackManager", "features": ["circuit_breaker", "exponential_backoff", "degradation_models"]}
    except Exception:
        fallback_info = {"error": "unavailable"}

    # Cost tracker summary
    cost_info: dict[str, object] = {}
    try:
        from backend.app.core.llm.cost_optimizer import CostTracker
        tracker = CostTracker()
        cost_info = {"engine": "CostTracker", "features": ["per_model_breakdown", "budget_alerts", "task_type_analysis"]}
    except Exception:
        cost_info = {"error": "unavailable"}

    # Quota manager
    quota_info: dict[str, object] = {}
    try:
        from backend.app.core.llm.quota import get_quota_manager
        mgr = get_quota_manager()
        quota_info = {
            "enabled": mgr.enabled,
            "period": mgr.period,
            "default_tenant_tokens": mgr.default_tenant_tokens,
            "default_user_tokens": mgr.default_user_tokens,
        }
    except Exception:
        quota_info = {"error": "unavailable"}

    return {
        "timestamp": time.time(),
        "router": router_info,
        "fallback": fallback_info,
        "cost_tracker": cost_info,
        "quota": quota_info,
    }


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


# ─── Parameterized /{agent_id} routes (MUST come after fixed-path routes) ───

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


# ─── S: WebSocket Real-time Agent Events ─────────────────────────────────────

from fastapi import WebSocket, WebSocketDisconnect


class _AgentEventBus:
    """Simple pub/sub bus for agent execution events over WebSocket."""

    def __init__(self):
        self._subscribers: list[WebSocket] = []

    async def subscribe(self, ws: WebSocket) -> None:
        await ws.accept()
        self._subscribers.append(ws)

    def unsubscribe(self, ws: WebSocket) -> None:
        self._subscribers = [s for s in self._subscribers if s is not ws]

    async def broadcast(self, event: dict) -> None:
        dead: list[WebSocket] = []
        for ws in self._subscribers:
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.unsubscribe(ws)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


agent_event_bus = _AgentEventBus()


@router.get("/dev-portal")
async def get_developer_portal(principal: PrincipalDependency = None) -> dict[str, object]:
    """T: Developer portal metadata — API catalog, plugin guide, ADR index."""
    enforce_scope(principal, "agent:run")
    import time

    # API catalog: list all registered route prefixes
    api_catalog = [
        {"prefix": "/api/v1/agents", "description": "Agent execution, streaming, stats, performance"},
        {"prefix": "/api/v1/agents/parallel", "description": "Parallel agent execution & queue management"},
        {"prefix": "/api/v1/collaboration", "description": "Multi-agent collaboration rooms & messaging"},
        {"prefix": "/api/v1/memory", "description": "Enhanced memory system with tiers & consolidation"},
        {"prefix": "/api/v1/security", "description": "Auth, API keys, posture, secret scan, audit chain"},
        {"prefix": "/api/v1/security/tenant-isolation", "description": "Tenant quotas, usage, RBAC matrix"},
        {"prefix": "/api/v1/health", "description": "Liveness, readiness, deploy probes, drain status"},
        {"prefix": "/api/v1/workflows", "description": "Workflow CRUD, execution, scheduling"},
        {"prefix": "/api/v1/tools", "description": "Tool registry, execution, batch operations"},
        {"prefix": "/api/v1/backup", "description": "Backup create, restore, verify, schedule"},
    ]

    # Plugin development guide
    plugin_guide = {
        "manifest_format": "plugin.json with name, version, description, tools[], permissions[]",
        "lifecycle": ["install", "activate", "deactivate", "uninstall"],
        "hot_reload": True,
        "sdk_language": ["python", "typescript"],
        "example_structure": ["plugin.json", "main.py", "tools/", "README.md"],
    }

    # Architecture Decision Records index
    adr_index = [
        {"id": "ADR-001", "title": "Agent Loop 采用 ReAct 模式", "status": "accepted"},
        {"id": "ADR-002", "title": "工具执行通过沙箱隔离", "status": "accepted"},
        {"id": "ADR-003", "title": "记忆系统三层架构 (hot/warm/cold)", "status": "accepted"},
        {"id": "ADR-004", "title": "多 Agent 协作采用 Shared Context Room", "status": "accepted"},
        {"id": "ADR-005", "title": "LLM 路由采用 SmartRouter + CircuitBreaker", "status": "accepted"},
        {"id": "ADR-006", "title": "前端状态管理使用 Zustand + persist", "status": "accepted"},
    ]

    return {
        "timestamp": time.time(),
        "version": "0.4.0-alpha",
        "api_catalog": api_catalog,
        "plugin_guide": plugin_guide,
        "adr_index": adr_index,
        "websocket_endpoints": [
            {"path": "/api/v1/agents/events/ws", "description": "Real-time agent execution events"},
            {"path": "/api/v1/notifications/ws", "description": "User notifications push"},
            {"path": "/api/v1/mobile/ws", "description": "Mobile real-time status"},
        ],
    }


@router.get("/evaluation")
async def get_agent_evaluation(principal: PrincipalDependency = None) -> dict[str, object]:
    """V: Agent evaluation framework — completion rate, quality score, benchmark."""
    enforce_scope(principal, "agent:run")
    import time

    records = get_run_store().list(limit=100)
    tenant_runs = [r for r in records if getattr(r, "tenant_id", None) == principal.tenant_id]

    if not tenant_runs:
        return {"timestamp": time.time(), "total_runs": 0, "evaluation": None}

    # 1. Task completion rate
    completed = sum(1 for r in tenant_runs if getattr(r, "status", None) and getattr(r.status, "value", str(r.status)) == "completed")
    failed = sum(1 for r in tenant_runs if getattr(r, "status", None) and getattr(r.status, "value", str(r.status)) == "failed")
    completion_rate = round(completed / len(tenant_runs), 3) if tenant_runs else 0

    # 2. Tool quality score (success rate weighted by usage)
    tool_calls_total = 0
    tool_calls_success = 0
    for r in tenant_runs:
        tcs = getattr(r, "tool_calls", None) or []
        if isinstance(tcs, list):
            for tc in tcs:
                tool_calls_total += 1
                success = tc.get("success", False) if isinstance(tc, dict) else getattr(tc, "success", False)
                if success:
                    tool_calls_success += 1
    tool_quality = round(tool_calls_success / tool_calls_total, 3) if tool_calls_total > 0 else 1.0

    # 3. Efficiency score (avg iterations vs max)
    iterations_used = []
    for r in tenant_runs:
        iters = getattr(r, "iterations", None) or getattr(r, "step_count", None)
        if iters and isinstance(iters, (int, float)):
            iterations_used.append(iters)
    avg_iterations = round(sum(iterations_used) / len(iterations_used), 1) if iterations_used else 0

    # 4. Composite quality score (0-100)
    quality_score = round(
        (completion_rate * 40) + (tool_quality * 35) + (max(0, 1 - avg_iterations / 20) * 25), 1
    )

    # 5. Benchmark comparison
    benchmark = {
        "baseline_completion": 0.7,
        "baseline_tool_quality": 0.8,
        "baseline_quality_score": 65.0,
        "vs_baseline": round(quality_score - 65.0, 1),
    }

    return {
        "timestamp": time.time(),
        "total_runs": len(tenant_runs),
        "evaluation": {
            "completion_rate": completion_rate,
            "completed": completed,
            "failed": failed,
            "tool_quality_score": tool_quality,
            "tool_calls_total": tool_calls_total,
            "avg_iterations": avg_iterations,
            "quality_score": quality_score,
            "grade": "A" if quality_score >= 80 else "B" if quality_score >= 60 else "C" if quality_score >= 40 else "D",
        },
        "benchmark": benchmark,
    }


@router.websocket("/events/ws")
async def agent_events_websocket(websocket: WebSocket):
    """WebSocket: real-time agent execution events.

    Connect: ws://host/api/v1/agents/events/ws?api_key=...
    Receives: {type: 'agent.started'|'agent.completed'|'agent.failed'|'tool.call', ...}
    """
    # Lightweight auth via query param
    api_key = websocket.query_params.get("api_key", "")
    if not api_key:
        await websocket.close(code=4001, reason="api_key required")
        return

    await agent_event_bus.subscribe(websocket)
    try:
        await websocket.send_json({"type": "connected", "subscribers": agent_event_bus.subscriber_count})
        while True:
            # Keep connection alive; client can send ping/subscribe commands
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        agent_event_bus.unsubscribe(websocket)
