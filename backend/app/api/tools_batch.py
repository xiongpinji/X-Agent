"""API endpoints for batch tool execution."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_agent, get_current_principal

router = APIRouter(prefix="/api/v1/tools/batch", tags=["tools-batch"])
AgentDependency = Annotated[object, Depends(get_agent)]
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.post("/execute")
async def execute_batch(
    request: dict[str, Any],
    agent: AgentDependency,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Execute multiple tool calls in parallel.

    Request format:
    {
        "calls": [
            {"name": "tool_name", "arguments": {...}},
            ...
        ],
        "allow_partial_failure": true
    }

    Response format:
    {
        "success": true,
        "results": [
            {"tool_name": "...", "success": true, "output": ...},
            ...
        ],
        "stats": {
            "total_calls": 3,
            "successful_calls": 3,
            "failed_calls": 0,
            "cached_calls": 0,
            "total_latency_ms": 1234.5,
            "parallelism_factor": 2.8
        }
    }
    """
    enforce_scope(principal, "tools:execute")

    calls = request.get("calls", [])
    allow_partial_failure = request.get("allow_partial_failure", True)

    if not calls:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "No tool calls provided")

    if not isinstance(calls, list):
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "calls must be a list")

    try:
        # Get execution context from agent
        context = agent.get_context()

        # Execute batch
        records = await agent.tools.execute_batch(
            context=context,
            tool_calls=calls,
            allow_partial_failure=allow_partial_failure,
        )

        # Get executor stats
        from backend.app.core.parallel_tool_executor import ParallelToolExecutor
        from backend.app.core.tool_result_cache import ToolResultCache

        executor = ParallelToolExecutor(
            tool_registry=agent.tools,
            cache=ToolResultCache(),
        )
        stats = executor.get_stats()

        return {
            "success": all(r.success for r in records),
            "results": [r.model_dump(mode="json") for r in records],
            "stats": {
                "total_calls": stats.total_calls,
                "successful_calls": stats.successful_calls,
                "failed_calls": stats.failed_calls,
                "cached_calls": stats.cached_calls,
                "total_latency_ms": stats.total_latency_ms,
                "parallelism_factor": stats.parallelism_factor,
            },
        }

    except Exception as exc:
        raise api_error(
            500,
            ErrorCode.INTERNAL_ERROR,
            f"Batch execution failed: {exc!s}",
        )


@router.post("/analyze")
async def analyze_dependencies(
    request: dict[str, Any],
    agent: AgentDependency,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Analyze dependencies between tool calls.

    Request format:
    {
        "calls": [
            {"id": "call_1", "name": "tool_name", "arguments": {...}},
            ...
        ]
    }

    Response format:
    {
        "layers": [
            {"layer_id": 0, "call_ids": ["call_1", "call_2"]},
            {"layer_id": 1, "call_ids": ["call_3"]}
        ],
        "max_parallelism": 2,
        "cycles": []
    }
    """
    enforce_scope(principal, "tools:read")

    calls = request.get("calls", [])

    if not calls:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "No tool calls provided")

    try:
        from backend.app.core.parallel_tool_executor import ToolCall
        from backend.app.core.tool_dependency_analyzer import ToolDependencyAnalyzer

        # Convert to ToolCall objects
        tool_calls = [
            ToolCall(
                tool_name=call.get("name", ""),
                arguments=call.get("arguments", {}),
                call_id=call.get("id", __import__("uuid").uuid4().hex[:8]),
            )
            for call in calls
        ]

        # Analyze dependencies
        analyzer = ToolDependencyAnalyzer()
        graph = analyzer.analyze_dependencies(tool_calls)
        plan = analyzer.build_execution_plan(graph)
        cycles = analyzer.detect_cycles(graph)

        return {
            "layers": [
                {
                    "layer_id": layer.layer_id,
                    "call_ids": list(layer.call_ids),
                    "dependencies": list(layer.dependencies),
                }
                for layer in plan.layers
            ],
            "max_parallelism": plan.max_parallelism,
            "total_calls": plan.total_calls,
            "cycles": cycles,
        }

    except Exception as exc:
        raise api_error(
            500,
            ErrorCode.INTERNAL_ERROR,
            f"Dependency analysis failed: {exc!s}",
        )


@router.get("/cache/stats")
async def get_cache_stats(
    agent: AgentDependency,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Get cache statistics.

    Response format:
    {
        "total_requests": 1000,
        "cache_hits": 750,
        "cache_misses": 250,
        "hit_rate": 0.75,
        "miss_rate": 0.25,
        "evictions": 10,
        "expirations": 5,
        "current_size": 500,
        "max_size": 1000
    }
    """
    enforce_scope(principal, "tools:read")

    try:
        from backend.app.core.tool_result_cache import ToolResultCache

        cache = ToolResultCache()
        stats = cache.get_stats()

        return {
            "total_requests": stats.total_requests,
            "cache_hits": stats.cache_hits,
            "cache_misses": stats.cache_misses,
            "hit_rate": stats.hit_rate,
            "miss_rate": stats.miss_rate,
            "evictions": stats.evictions,
            "expirations": stats.expirations,
            "current_size": stats.current_size,
            "max_size": stats.max_size,
        }

    except Exception as exc:
        raise api_error(
            500,
            ErrorCode.INTERNAL_ERROR,
            f"Failed to get cache stats: {exc!s}",
        )


@router.delete("/cache/clear")
async def clear_cache(
    request: dict[str, Any] | None = None,
    agent: AgentDependency = None,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """Clear the tool result cache.

    Request format (optional):
    {
        "tool_name": "read_file",  # Optional: clear only this tool's cache
        "args": {...}  # Optional: clear only this specific entry
    }

    Response format:
    {
        "success": true,
        "message": "Cache cleared"
    }
    """
    enforce_scope(principal, "tools:write")

    try:
        from backend.app.core.tool_result_cache import ToolResultCache

        cache = ToolResultCache()

        if request:
            tool_name = request.get("tool_name")
            args = request.get("args")
            await cache.invalidate(tool_name=tool_name, args=args)
        else:
            await cache.invalidate()

        return {
            "success": True,
            "message": "Cache cleared",
        }

    except Exception as exc:
        raise api_error(
            500,
            ErrorCode.INTERNAL_ERROR,
            f"Failed to clear cache: {exc!s}",
        )
