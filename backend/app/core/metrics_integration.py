"""Example integration of metrics collection in X-Agent."""

from __future__ import annotations

import time
from typing import Any, Callable

from backend.app.core.metrics import metrics_collector


def record_http_request(method: str, endpoint: str, status: int, duration_seconds: float) -> None:
    """Record HTTP request metrics."""
    metrics_collector.record_http_request(method, endpoint, status, duration_seconds)


def record_agent_execution(agent_id: str, status: str, duration_seconds: float) -> None:
    """Record agent execution metrics."""
    metrics_collector.record_agent_execution(agent_id, status, duration_seconds)


def record_tool_call(tool_name: str, status: str, duration_seconds: float) -> None:
    """Record tool call metrics."""
    metrics_collector.record_tool_call(tool_name, status, duration_seconds)


def record_llm_call(
    model: str,
    status: str,
    duration_seconds: float,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    """Record LLM call metrics."""
    metrics_collector.record_llm_call(model, status, duration_seconds, input_tokens, output_tokens)


def record_memory_operation(operation: str, status: str, duration_seconds: float = 0) -> None:
    """Record memory operation metrics."""
    metrics_collector.record_memory_operation(operation, status, duration_seconds)


def record_workflow_execution(workflow_id: str, status: str, duration_seconds: float) -> None:
    """Record workflow execution metrics."""
    metrics_collector.record_workflow_execution(workflow_id, status, duration_seconds)


def record_db_query(query_type: str, status: str, duration_seconds: float) -> None:
    """Record database query metrics."""
    metrics_collector.record_db_query(query_type, status, duration_seconds)


def record_cache_operation(cache_name: str, hit: bool) -> None:
    """Record cache operation metrics."""
    if hit:
        metrics_collector.record_cache_hit(cache_name)
    else:
        metrics_collector.record_cache_miss(cache_name)


# Example usage in middleware
def metrics_middleware_example(request, call_next):
    """Example middleware for recording HTTP metrics."""
    start = time.perf_counter()
    response = call_next(request)
    duration = time.perf_counter() - start

    record_http_request(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code,
        duration_seconds=duration,
    )

    return response


# Example usage in agent execution
async def execute_agent_with_metrics(agent_id: str, task: str) -> Any:
    """Example agent execution with metrics."""
    start = time.perf_counter()
    try:
        # Execute agent
        result = await execute_agent(agent_id, task)
        duration = time.perf_counter() - start
        record_agent_execution(agent_id, "success", duration)
        return result
    except Exception as e:
        duration = time.perf_counter() - start
        record_agent_execution(agent_id, "failed", duration)
        raise


# Example usage in tool execution
async def execute_tool_with_metrics(tool_name: str, **kwargs) -> Any:
    """Example tool execution with metrics."""
    start = time.perf_counter()
    try:
        # Execute tool
        result = await execute_tool(tool_name, **kwargs)
        duration = time.perf_counter() - start
        record_tool_call(tool_name, "success", duration)
        return result
    except Exception as e:
        duration = time.perf_counter() - start
        record_tool_call(tool_name, "failed", duration)
        raise


# Example usage in LLM calls
async def call_llm_with_metrics(model: str, prompt: str) -> dict:
    """Example LLM call with metrics."""
    start = time.perf_counter()
    try:
        # Call LLM
        response = await call_llm(model, prompt)
        duration = time.perf_counter() - start

        input_tokens = len(prompt.split())
        output_tokens = len(response.get("text", "").split())

        record_llm_call(model, "success", duration, input_tokens, output_tokens)
        return response
    except Exception as e:
        duration = time.perf_counter() - start
        record_llm_call(model, "failed", duration)
        raise


# Example usage in memory operations
async def retrieve_memory_with_metrics(query: str) -> list:
    """Example memory retrieval with metrics."""
    start = time.perf_counter()
    try:
        # Retrieve memory
        results = await retrieve_memory(query)
        duration = time.perf_counter() - start
        record_memory_operation("retrieval", "success", duration)
        return results
    except Exception as e:
        duration = time.perf_counter() - start
        record_memory_operation("retrieval", "failed", duration)
        raise


# Example usage in workflow execution
async def execute_workflow_with_metrics(workflow_id: str) -> Any:
    """Example workflow execution with metrics."""
    start = time.perf_counter()
    try:
        # Execute workflow
        result = await execute_workflow(workflow_id)
        duration = time.perf_counter() - start
        record_workflow_execution(workflow_id, "success", duration)
        return result
    except Exception as e:
        duration = time.perf_counter() - start
        record_workflow_execution(workflow_id, "failed", duration)
        raise


# Example usage in database queries
async def query_database_with_metrics(query_type: str, query: str) -> Any:
    """Example database query with metrics."""
    start = time.perf_counter()
    try:
        # Execute query
        result = await execute_query(query)
        duration = time.perf_counter() - start
        record_db_query(query_type, "success", duration)
        return result
    except Exception as e:
        duration = time.perf_counter() - start
        record_db_query(query_type, "failed", duration)
        raise


# Example usage in cache operations
async def get_from_cache_with_metrics(cache_name: str, key: str) -> Any:
    """Example cache retrieval with metrics."""
    try:
        # Try to get from cache
        value = await get_from_cache(cache_name, key)
        if value is not None:
            record_cache_operation(cache_name, hit=True)
            return value
        else:
            record_cache_operation(cache_name, hit=False)
            # Fetch from source
            value = await fetch_from_source(key)
            await set_in_cache(cache_name, key, value)
            return value
    except Exception as e:
        record_cache_operation(cache_name, hit=False)
        raise


# Decorator for automatic metrics recording
def with_metrics(metric_type: str, **metric_labels):
    """Decorator for automatic metrics recording."""
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                duration = time.perf_counter() - start

                if metric_type == "agent_execution":
                    record_agent_execution(
                        metric_labels.get("agent_id", "unknown"),
                        "success",
                        duration,
                    )
                elif metric_type == "tool_call":
                    record_tool_call(
                        metric_labels.get("tool_name", "unknown"),
                        "success",
                        duration,
                    )
                elif metric_type == "workflow_execution":
                    record_workflow_execution(
                        metric_labels.get("workflow_id", "unknown"),
                        "success",
                        duration,
                    )

                return result
            except Exception as e:
                duration = time.perf_counter() - start

                if metric_type == "agent_execution":
                    record_agent_execution(
                        metric_labels.get("agent_id", "unknown"),
                        "failed",
                        duration,
                    )
                elif metric_type == "tool_call":
                    record_tool_call(
                        metric_labels.get("tool_name", "unknown"),
                        "failed",
                        duration,
                    )
                elif metric_type == "workflow_execution":
                    record_workflow_execution(
                        metric_labels.get("workflow_id", "unknown"),
                        "failed",
                        duration,
                    )

                raise

        return wrapper

    return decorator


# Example usage of decorator
@with_metrics("agent_execution", agent_id="agent-1")
async def my_agent_task():
    """Example agent task with automatic metrics."""
    pass


# Placeholder functions for examples
async def execute_agent(agent_id: str, task: str) -> Any:
    pass


async def execute_tool(tool_name: str, **kwargs) -> Any:
    pass


async def call_llm(model: str, prompt: str) -> dict:
    pass


async def retrieve_memory(query: str) -> list:
    pass


async def execute_workflow(workflow_id: str) -> Any:
    pass


async def execute_query(query: str) -> Any:
    pass


async def get_from_cache(cache_name: str, key: str) -> Any:
    pass


async def fetch_from_source(key: str) -> Any:
    pass


async def set_in_cache(cache_name: str, key: str, value: Any) -> None:
    pass
