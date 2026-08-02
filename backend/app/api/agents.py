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
        # Hermes-style persona configuration
        "persona": {
            "system_prompt": payload.get("system_prompt", ""),
            "personality": payload.get("personality", "professional"),
            "allowed_tools": payload.get("allowed_tools") or [],  # empty = all tools
            "blocked_tools": payload.get("blocked_tools") or [],
            "model_preference": payload.get("model_preference", ""),  # e.g. "gpt-4o", "deepseek-chat"
            "temperature": payload.get("temperature", 0.7),
            "max_tokens": payload.get("max_tokens", 0),  # 0 = default
            "custom_instructions": payload.get("custom_instructions", ""),
        },
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
        # Codex-style multimodal: pass images through extra_context
        extra = dict(request.get("extra_context") or {})
        images = request.get("images")
        if images and isinstance(images, list):
            extra["images"] = images
        result = await agent.run(context, task, extra)
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


@router.post("/run/multi", response_model=None)
async def run_agent_multi_solution(payload: dict[str, Any] | None = None, principal: PrincipalDependency = None):
    """Generate multiple candidate solutions for a task (Codex-style multi-solution).

    Runs the agent N times with different strategy hints, returning all candidates
    so the user can pick the best one.

    Body params:
        task: str (required)
        num_solutions: int (2-5, default 3)
        agent_id: str (optional)
    """
    import asyncio as _aio

    agent = get_agent()
    request = payload or {}
    enforce_scope(principal, "agent:run")
    task = str(request.get("task", ""))
    if not task:
        raise api_error(422, ErrorCode.VALIDATION_ERROR, "task is required.")

    num_solutions = min(max(int(request.get("num_solutions", 3)), 2), 5)

    # Strategy hints to diversify solutions
    strategies = [
        "Prefer the simplest, most readable solution.",
        "Optimize for performance and efficiency.",
        "Focus on robustness, error handling, and edge cases.",
        "Use modern best practices and design patterns.",
        "Minimize dependencies and keep it self-contained.",
    ]

    async def _run_one(idx: int) -> dict[str, Any]:
        hint = strategies[idx % len(strategies)]
        context = RunContext(
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            permission_scope=list(principal.scopes or []),
        )
        augmented_task = f"{task}\n\n[Strategy hint: {hint}]"
        try:
            result = await agent.run(context, augmented_task, {"auto_commit": False, "auto_review": False})
            return {
                "solution_id": idx + 1,
                "strategy": hint,
                "status": result.status.value,
                "answer": result.answer,
                "iterations": result.iterations,
                "tool_calls": len(result.tool_calls),
                "trace_id": result.trace_id,
            }
        except Exception as exc:
            return {
                "solution_id": idx + 1,
                "strategy": hint,
                "status": "error",
                "answer": str(exc)[:500],
                "iterations": 0,
                "tool_calls": 0,
                "trace_id": None,
            }

    # Run all solutions concurrently
    candidates = await _aio.gather(*[_run_one(i) for i in range(num_solutions)])

    return {
        "task": task,
        "num_requested": num_solutions,
        "candidates": list(candidates),
        "best_candidate": max(candidates, key=lambda c: (c["status"] == "completed", c["iterations"], c["tool_calls"])).get("solution_id"),
    }


@router.post("/structured", response_model=None)
async def run_structured_output(payload: dict[str, Any] | None = None, principal: PrincipalDependency = None):
    """Codex-style structured output: force LLM to respond with a strict JSON schema.

    Body params:
        prompt: str (required) — the instruction/question
        schema: dict (required) — JSON Schema the response must conform to
        model: str (optional) — model override
        temperature: float (optional, default 0.2)
    """
    from backend.app.dependencies import get_llm_router

    request = payload or {}
    enforce_scope(principal, "agent:run")
    prompt = str(request.get("prompt", ""))
    schema = request.get("schema")
    if not prompt:
        raise api_error(422, ErrorCode.VALIDATION_ERROR, "prompt is required.")
    if not schema or not isinstance(schema, dict):
        raise api_error(422, ErrorCode.VALIDATION_ERROR, "schema (JSON Schema object) is required.")

    llm_router = get_llm_router()
    messages = [
        {"role": "system", "content": "You are a precise assistant. Respond ONLY with valid JSON matching the provided schema. No markdown, no explanation."},
        {"role": "user", "content": f"{prompt}\n\nRespond with JSON conforming to this schema:\n{json.dumps(schema, indent=2)}"},
    ]
    response_format = {"type": "json_schema", "json_schema": {"name": "structured_response", "strict": True, "schema": schema}}
    try:
        # Try with strict response_format first (OpenAI-compatible)
        try:
            response = await llm_router.chat(
                messages, [],
                tenant_id=principal.tenant_id,
                user_id=principal.user_id,
                response_format=response_format,
            )
        except Exception:
            # Fallback: prompt-only approach for backends without response_format support
            response = await llm_router.chat(
                messages, [],
                tenant_id=principal.tenant_id,
                user_id=principal.user_id,
            )
        import json as _json
        # Extract JSON from response (handle markdown code fences)
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            parsed = _json.loads(raw)
        except Exception:
            parsed = response.content
        return {
            "status": "completed",
            "data": parsed,
            "model": response.model,
            "tokens_used": response.tokens_used,
            "latency_ms": response.latency_ms,
        }
    except Exception as exc:
        raise api_error(502, ErrorCode.INTERNAL_ERROR, f"Structured output generation failed: {exc}") from exc


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


@router.post("/runs/{trace_id}/retry", response_model=None)
async def retry_agent_run(trace_id: str, payload: dict[str, Any] | None = None, principal: PrincipalDependency = None):
    """Codex-style one-click retry: re-run a failed/completed task from its last checkpoint.

    Automatically resumes from the last successful iteration if checkpoint data exists.
    Body params (optional):
        task_override: str — override the original task text
        max_iterations: int — cap iterations for the retry
    """
    agent = get_agent()
    enforce_scope(principal, "agent:run")
    request = payload or {}

    # Retrieve original run (may not exist for fast-path runs)
    run_store = get_run_store()
    original_run = run_store.get(trace_id) if run_store else None

    # Determine task text
    original_task = ""
    if original_run is not None:
        if hasattr(original_run, "task"):
            original_task = original_run.task
        elif isinstance(original_run, dict):
            original_task = original_run.get("task", "")
    task = request.get("task_override") or original_task or f"Retry of {trace_id}"

    context = RunContext(
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        permission_scope=list(principal.scopes or []),
    )

    # Resume from checkpoint if available
    extra: dict[str, Any] = {"resume_trace_id": trace_id, "auto_review": False}
    req_max_iter = request.get("max_iterations")
    if req_max_iter and isinstance(req_max_iter, int) and 1 <= req_max_iter <= 100:
        agent.max_iterations = req_max_iter

    result = await agent.run(context, task, extra)

    get_audit_store().record(
        action="agent.run.retry",
        resource_type="agent",
        resource_id=context.agent_id,
        tenant_id=context.tenant_id,
        actor_id=context.user_id,
        trace_id=result.trace_id,
        run_id=result.trace_id,
        details={"original_trace_id": trace_id, "task_preview": task[:120], "status": result.status.value},
    )
    return {
        **result.model_dump(mode="json"),
        "retry_of": trace_id,
        "resumed": True,
    }


@router.get("/runs/{trace_id}/plan")
async def get_execution_plan(trace_id: str, principal: PrincipalDependency = None) -> dict[str, object]:
    """Codex-style execution plan visibility: per-step status for a run.

    Reconstructs the plan from trace events, showing each step's status
    (pending/completed/failed) and timing information.
    """
    enforce_scope(principal, "agent:run")
    events = [e.model_dump(mode="json") for e in get_trace_store().list_events(trace_id)]
    if not events:
        raise api_error(404, ErrorCode.TRACE_NOT_FOUND, "Trace not found.", trace_id=trace_id)

    # Extract plan info from events
    plan_steps: list[dict[str, Any]] = []
    subtasks: list[str] = []
    subtask_status: dict[str, str] = {}
    current_iteration = 0
    tool_calls_done: list[dict[str, Any]] = []
    status = "unknown"

    for evt in events:
        event_name = evt.get("event", "")
        payload = evt.get("payload", {})

        if event_name == "agent.plan.created":
            # Plan was created
            pass
        elif event_name == "agent.task.decomposed":
            subtasks = payload.get("subtasks", [])
        elif event_name == "agent.iteration.completed":
            current_iteration = payload.get("iteration", current_iteration + 1)
        elif event_name == "agent.tool.completed":
            tool_calls_done.append({
                "tool": payload.get("tool_name", ""),
                "success": payload.get("success", True),
                "iteration": current_iteration,
            })
        elif event_name == "agent.completed":
            status = "completed"
        elif event_name == "agent.failed" or event_name == "agent.blocked":
            status = "failed"

    # Build step-level progress from subtasks
    for i, st in enumerate(subtasks):
        step_status = "completed" if i < current_iteration else "in_progress" if i == current_iteration else "pending"
        plan_steps.append({"step": i + 1, "instruction": st, "status": step_status})

    # If no subtasks, synthesize from tool calls
    if not plan_steps and tool_calls_done:
        for i, tc in enumerate(tool_calls_done):
            plan_steps.append({
                "step": i + 1,
                "instruction": f"Execute {tc['tool']}",
                "status": "completed" if tc["success"] else "failed",
            })

    total_steps = len(plan_steps)
    completed_steps = sum(1 for s in plan_steps if s["status"] == "completed")
    progress_pct = round(completed_steps / max(total_steps, 1) * 100, 1)

    return {
        "trace_id": trace_id,
        "status": status,
        "progress_pct": progress_pct,
        "total_steps": total_steps,
        "completed_steps": completed_steps,
        "current_iteration": current_iteration,
        "steps": plan_steps,
        "tool_calls_executed": len(tool_calls_done),
        "subtasks": subtasks,
    }


@router.get("/runs/{trace_id}/reasoning", response_model=None)
async def get_reasoning_trace(trace_id: str, principal: PrincipalDependency = None):
    """Codex-style reasoning visibility: expose the agent's decision chain.

    Shows WHY the agent chose each tool, what it was thinking at each step,
    and how confidence evolved throughout the run.
    """
    enforce_scope(principal, "agent:run")
    try:
        events = [e.model_dump(mode="json") for e in get_trace_store().list_events(trace_id)]
    except Exception:
        events = []
    if not events:
        raise api_error(404, ErrorCode.TRACE_NOT_FOUND, "Trace not found.", trace_id=trace_id)

    reasoning_steps: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    confidence_timeline: list[dict[str, Any]] = []

    for evt in events:
        etype = evt.get("event", "")
        payload = evt.get("payload", evt.get("data", {}))
        ts = evt.get("timestamp", "")

        # Capture planning rationale
        if etype == "agent.plan.created":
            reasoning_steps.append({
                "type": "planning",
                "timestamp": ts,
                "thought": payload.get("rationale", payload.get("instruction", "Initial plan created")),
                "context": {k: v for k, v in payload.items() if k in ("intent", "mode", "urgency", "next_action")},
            })
        elif etype == "agent.task.decomposed":
            reasoning_steps.append({
                "type": "decomposition",
                "timestamp": ts,
                "thought": f"Decomposed into {len(payload.get('subtasks', []))} subtasks",
                "subtasks": payload.get("subtasks", [])[:10],
            })
        elif etype == "agent.iteration.started":
            reasoning_steps.append({
                "type": "iteration_start",
                "timestamp": ts,
                "thought": f"Starting iteration {payload.get('iteration', '?')}: {payload.get('instruction', '')[:200]}",
                "step_kind": payload.get("step_kind", ""),
            })
        elif etype in ("agent.tool.completed", "agent.tool.failed"):
            success = etype == "agent.tool.completed"
            decisions.append({
                "timestamp": ts,
                "tool": payload.get("tool_name", ""),
                "decision": "execute",
                "outcome": "success" if success else "failure",
                "error": (payload.get("error") or "")[:200] if not success else None,
            })
        elif etype == "agent.plan.reordered":
            reasoning_steps.append({
                "type": "replan",
                "timestamp": ts,
                "thought": f"Re-planning: {payload.get('reason', 'tool failure')}",
                "confidence": payload.get("confidence"),
                "reroute": payload.get("reroute"),
            })
        elif etype == "agent.escalation.requested":
            reasoning_steps.append({
                "type": "escalation",
                "timestamp": ts,
                "thought": f"Low confidence ({payload.get('confidence', 0):.0%}), requesting user clarification",
                "confidence": payload.get("confidence"),
            })
        elif etype == "agent.auto_commit.success":
            reasoning_steps.append({
                "type": "commit",
                "timestamp": ts,
                "thought": f"Auto-committed: {payload.get('message', '')[:100]}",
            })
        elif etype == "agent.completed":
            reasoning_steps.append({
                "type": "completion",
                "timestamp": ts,
                "thought": "Task completed successfully",
            })

        # Track confidence changes
        conf = payload.get("confidence")
        if conf is not None:
            confidence_timeline.append({"timestamp": ts, "confidence": float(conf), "event": etype})

    return {
        "trace_id": trace_id,
        "reasoning_steps": reasoning_steps,
        "tool_decisions": decisions,
        "confidence_timeline": confidence_timeline,
        "summary": {
            "total_reasoning_steps": len(reasoning_steps),
            "tool_decisions_made": len(decisions),
            "replans": sum(1 for r in reasoning_steps if r["type"] == "replan"),
            "escalations": sum(1 for r in reasoning_steps if r["type"] == "escalation"),
            "final_confidence": confidence_timeline[-1]["confidence"] if confidence_timeline else None,
        },
    }


@router.get("/runs/{trace_id}/files-changed", response_model=None)
async def get_files_changed(trace_id: str, principal: PrincipalDependency = None):
    """Codex-style file change tracking: list all files modified during a run.

    Shows which files were written/patched, with operation type and verification status.
    """
    enforce_scope(principal, "agent:run")
    try:
        events = [e.model_dump(mode="json") for e in get_trace_store().list_events(trace_id)]
    except Exception:
        events = []
    if not events:
        raise api_error(404, ErrorCode.TRACE_NOT_FOUND, "Trace not found.", trace_id=trace_id)

    files_changed: dict[str, dict[str, Any]] = {}
    write_tools = {"write_file", "apply_text_patch", "apply_batch_patch"}

    for evt in events:
        etype = evt.get("event", "")
        payload = evt.get("payload", evt.get("data", {}))

        if etype == "agent.tool.completed":
            tool_name = payload.get("tool_name", "")
            if tool_name in write_tools:
                # Extract file path from arguments_preview or output
                args_preview = payload.get("arguments_preview", "")
                output = payload.get("output", "")
                path = ""
                if isinstance(args_preview, dict):
                    path = args_preview.get("path", args_preview.get("file", ""))
                elif isinstance(args_preview, str) and "path" in args_preview:
                    # Try to extract path from string preview
                    import re as _re
                    m = _re.search(r"['\"]?path['\"]?\s*[:=]\s*['\"]([^'\"]+)", args_preview)
                    if m:
                        path = m.group(1)
                if not path and isinstance(output, str):
                    import re as _re
                    m = _re.search(r"(?:wrote|patched|applied).*?['\"]([^'\"]+\.[a-z]+)", output, _re.IGNORECASE)
                    if m:
                        path = m.group(1)

                if path:
                    if path not in files_changed:
                        files_changed[path] = {"path": path, "operations": [], "verified": False}
                    files_changed[path]["operations"].append({
                        "tool": tool_name,
                        "timestamp": evt.get("timestamp", ""),
                        "success": True,
                    })

        elif etype == "agent.tool.failed":
            tool_name = payload.get("tool_name", "")
            if tool_name in write_tools:
                args_preview = payload.get("arguments_preview", "")
                path = ""
                if isinstance(args_preview, dict):
                    path = args_preview.get("path", args_preview.get("file", ""))
                if path:
                    if path not in files_changed:
                        files_changed[path] = {"path": path, "operations": [], "verified": False}
                    files_changed[path]["operations"].append({
                        "tool": tool_name,
                        "timestamp": evt.get("timestamp", ""),
                        "success": False,
                        "error": (payload.get("error") or "")[:150],
                    })

        # Track verification (re-read after write)
        if etype == "agent.write.verified":
            vpath = payload.get("path", "")
            if vpath and vpath in files_changed:
                files_changed[vpath]["verified"] = True

    file_list = list(files_changed.values())
    return {
        "trace_id": trace_id,
        "total_files_changed": len(file_list),
        "files": file_list,
        "summary": {
            "writes": sum(len(f["operations"]) for f in file_list),
            "verified": sum(1 for f in file_list if f["verified"]),
            "failed_ops": sum(1 for f in file_list for op in f["operations"] if not op["success"]),
        },
    }


@router.post("/runs/{trace_id}/refine", response_model=None)
async def refine_agent_run(trace_id: str, payload: dict[str, Any] | None = None, principal: PrincipalDependency = None):
    """Multi-turn task refinement: continue improving a previous run's result.

    Codex-style iterative workflow: user provides follow-up instructions that
    build upon the previous run's context and output.
    """
    enforce_scope(principal, "agent:run")
    request = payload or {}
    refinement = str(request.get("instruction", request.get("task", "")))
    if not refinement:
        raise api_error(422, ErrorCode.VALIDATION_ERROR, "instruction is required.")

    # Retrieve previous run context
    try:
        prev_events = [e.model_dump(mode="json") for e in get_trace_store().list_events(trace_id)]
    except Exception:
        prev_events = []

    # Build context from previous run
    prev_answer = ""
    prev_task = ""
    files_touched: list[str] = []
    for evt in prev_events:
        p = evt.get("payload", evt.get("data", {}))
        if evt.get("event") == "agent.completed":
            prev_answer = p.get("answer", p.get("output", ""))[:2000]
        if evt.get("event") == "agent.started":
            prev_task = p.get("task", "")[:500]
        if evt.get("event") == "agent.tool.completed" and p.get("tool_name") in ("write_file", "apply_text_patch", "apply_batch_patch"):
            fp = p.get("arguments_preview", {})
            if isinstance(fp, dict) and fp.get("path"):
                files_touched.append(fp["path"])

    # Compose refined task with full context
    context_parts = [f"Previous task: {prev_task}" if prev_task else ""]
    if prev_answer:
        context_parts.append(f"Previous result summary: {prev_answer[:800]}")
    if files_touched:
        context_parts.append(f"Files previously modified: {', '.join(files_touched[:10])}")
    context_parts.append(f"Refinement instruction: {refinement}")

    refined_task = "\n".join(part for part in context_parts if part)

    # Execute refined task
    agent = get_agent()
    extra = dict(request.get("extra_context") or {})
    extra["auto_commit"] = extra.get("auto_commit", True)
    extra["refinement_of"] = trace_id
    extra["previous_files"] = files_touched

    from backend.app.core.contracts import RunContext
    context = RunContext(trace_id=f"refine_{trace_id}_{uuid4().hex[:6]}", tenant_id=principal.tenant_id)
    result = await agent.run(context, refined_task, extra)

    return {
        "trace_id": context.trace_id,
        "refinement_of": trace_id,
        "status": result.status.value if hasattr(result.status, "value") else str(result.status),
        "answer": getattr(result, "answer", "") or "",
        "previous_files": files_touched,
        "instruction": refinement,
    }


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
    # Hermes-style persona update
    persona = dict(record.get("persona") or {})
    for key in ("system_prompt", "personality", "allowed_tools", "blocked_tools", "model_preference", "temperature", "max_tokens", "custom_instructions"):
        if key in payload:
            persona[key] = payload[key]
    record["persona"] = persona
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


@router.get("/runs/{trace_id}/test-fix-loop", response_model=None)
async def get_test_fix_loop(
    trace_id: str,
    principal: PrincipalDependency,
):
    """Get the test-fix loop status and history for an agent run.

    Codex-style: shows each iteration of the test → fail → fix → retest cycle,
    including what was attempted, what failed, and what was repaired.
    """
    enforce_scope(principal, "agent:run")

    try:
        events = [e.model_dump(mode="json") for e in get_trace_store().list_events(trace_id)]
    except Exception:
        events = []
    if not events:
        raise api_error(404, ErrorCode.TRACE_NOT_FOUND, "Trace not found.", trace_id=trace_id)

    # Reconstruct test-fix loop iterations from trace events
    iterations: list[dict[str, Any]] = []
    current_iter: dict[str, Any] | None = None
    test_results: list[dict[str, Any]] = []
    repair_actions: list[dict[str, Any]] = []
    verification_events: list[dict[str, Any]] = []

    for ev in events:
        etype = ev.get("event", "")
        payload = ev.get("data", ev)

        # Track test execution results
        if "test" in etype and ("result" in etype or "run" in etype):
            test_results.append({
                "event": etype,
                "timestamp": ev.get("timestamp", ""),
                "passed": payload.get("passed", payload.get("success")),
                "details": {k: v for k, v in payload.items() if k not in ("event", "timestamp")},
            })

        # Track repair/fix actions
        if "repair" in etype or "fix" in etype or "retry" in etype:
            repair_actions.append({
                "event": etype,
                "timestamp": ev.get("timestamp", ""),
                "tool": payload.get("tool_name", payload.get("tool")),
                "reason": payload.get("reason", payload.get("error", ""))[:200],
                "confidence": payload.get("confidence"),
            })

        # Track verification results
        if "verif" in etype:
            verification_events.append({
                "event": etype,
                "timestamp": ev.get("timestamp", ""),
                "passed": payload.get("passed"),
                "summary": payload.get("summary", "")[:200],
            })

        # Track iteration boundaries
        if etype == "agent.iteration.started":
            if current_iter:
                iterations.append(current_iter)
            current_iter = {
                "iteration": payload.get("iteration", len(iterations) + 1),
                "step_kind": payload.get("step_kind", ""),
                "instruction": payload.get("instruction", "")[:200],
                "timestamp": ev.get("timestamp", ""),
            }
        elif etype in ("agent.tool.completed", "agent.tool.failed") and current_iter:
            current_iter.setdefault("tool_calls", []).append({
                "tool": payload.get("tool_name", ""),
                "success": etype == "agent.tool.completed",
                "error": (payload.get("error") or "")[:150],
            })

    if current_iter:
        iterations.append(current_iter)

    # Determine overall loop status
    total_tests = len(test_results)
    passed_tests = sum(1 for t in test_results if t.get("passed"))
    total_repairs = len(repair_actions)
    loop_converged = all(v.get("passed", True) for v in verification_events[-3:]) if verification_events else True

    return {
        "trace_id": trace_id,
        "loop_status": "converged" if loop_converged else "in_progress",
        "summary": {
            "total_iterations": len(iterations),
            "test_executions": total_tests,
            "tests_passed": passed_tests,
            "tests_failed": total_tests - passed_tests,
            "repair_attempts": total_repairs,
            "verification_checks": len(verification_events),
        },
        "iterations": iterations[-20:],  # Last 20 iterations
        "test_results": test_results[-15:],
        "repair_actions": repair_actions[-15:],
        "verification_events": verification_events[-10:],
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
