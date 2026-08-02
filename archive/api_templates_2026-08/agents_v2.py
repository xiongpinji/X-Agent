"""
Multi-agent API endpoints for X-Agent v2.

Provides endpoints for spawning, managing, and coordinating agents.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Query

from backend.app.api.errors import api_error
from backend.app.core.agent_coordinator import CoordinationStrategy, agent_coordinator
from backend.app.core.agent_spawner import agent_spawner
from backend.app.core.contracts import ErrorCode
from backend.app.core.parallel_executor import Task, parallel_executor
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v2/agents", tags=["agents_v2"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.post("/spawn")
async def spawn_agent(
    payload: dict[str, Any] | None = None,
    principal: PrincipalDependency = None,
) -> dict[str, object]:
    """
    Spawn a new sub-agent.

    Args:
        payload: Agent configuration
        principal: Current principal

    Returns:
        Agent info
    """
    enforce_scope(principal, "agent:manage")
    payload = payload or {}

    try:
        agent_id = await agent_spawner.spawn_agent(
            agent_type=payload.get("agent_type", "default"),
            task=payload.get("task", ""),
            context=payload.get("context", {}),
            isolation=payload.get("isolation"),
            max_iterations=payload.get("max_iterations", 10),
            timeout_seconds=payload.get("timeout_seconds", 3600),
            memory_limit_mb=payload.get("memory_limit_mb", 512),
            cpu_limit_percent=payload.get("cpu_limit_percent", 100),
            metadata=payload.get("metadata", {}),
        )

        return {
            "agent_id": agent_id,
            "status": "spawned",
            "created_at": datetime.now(UTC).isoformat(),
        }

    except RuntimeError as e:
        raise api_error(
            400,
            ErrorCode.INVALID_REQUEST,
            str(e),
        )


@router.get("/{agent_id}/status")
async def get_agent_status(
    agent_id: str,
    principal: PrincipalDependency = None,
) -> dict[str, object]:
    """
    Get status of an agent.

    Args:
        agent_id: ID of agent
        principal: Current principal

    Returns:
        Agent status
    """
    enforce_scope(principal, "agent:read")

    status = await agent_spawner.get_agent_status(agent_id)

    if not status:
        raise api_error(
            404,
            ErrorCode.RESOURCE_NOT_FOUND,
            "Agent not found",
            details={"agent_id": agent_id},
        )

    return status


@router.post("/{agent_id}/terminate")
async def terminate_agent(
    agent_id: str,
    principal: PrincipalDependency = None,
) -> dict[str, object]:
    """
    Terminate an agent.

    Args:
        agent_id: ID of agent
        principal: Current principal

    Returns:
        Termination result
    """
    enforce_scope(principal, "agent:manage")

    success = await agent_spawner.terminate_agent(agent_id)

    if not success:
        raise api_error(
            404,
            ErrorCode.RESOURCE_NOT_FOUND,
            "Agent not found",
            details={"agent_id": agent_id},
        )

    return {
        "agent_id": agent_id,
        "status": "terminated",
        "terminated_at": datetime.now(UTC).isoformat(),
    }


@router.get("")
async def list_agents(
    status: str | None = Query(None),
    agent_type: str | None = Query(None),
    principal: PrincipalDependency = None,
) -> dict[str, object]:
    """
    List agents.

    Args:
        status: Filter by status
        agent_type: Filter by agent type
        principal: Current principal

    Returns:
        List of agents
    """
    enforce_scope(principal, "agent:read")

    agents = await agent_spawner.list_agents(
        status=status,
        agent_type=agent_type,
    )

    return {
        "data": agents,
        "count": len(agents),
    }


@router.post("/parallel")
async def execute_parallel_tasks(
    payload: dict[str, Any] | None = None,
    principal: PrincipalDependency = None,
) -> dict[str, object]:
    """
    Execute multiple tasks in parallel.

    Args:
        payload: Task configuration
        principal: Current principal

    Returns:
        Execution result
    """
    enforce_scope(principal, "agent:execute")
    payload = payload or {}

    try:
        # Create tasks
        tasks = []
        for task_config in payload.get("tasks", []):
            async def dummy_coro():
                return {"status": "completed"}

            task = Task(
                task_id=task_config.get("task_id", f"task_{uuid4().hex[:8]}"),
                name=task_config.get("name", "task"),
                coroutine=dummy_coro,
                priority=task_config.get("priority", 0),
                timeout_seconds=task_config.get("timeout_seconds"),
                retry_count=task_config.get("retry_count", 0),
                metadata=task_config.get("metadata", {}),
            )
            tasks.append(task)

        # Execute in parallel
        results = await parallel_executor.execute_parallel(
            tasks,
            max_concurrent=payload.get("max_concurrent", 5),
        )

        # Format results
        formatted_results = [
            {
                "task_id": r.task_id,
                "name": r.name,
                "status": r.status.value,
                "result": r.result,
                "error": r.error,
                "duration_seconds": r.duration_seconds,
            }
            for r in results
        ]

        stats = parallel_executor.get_execution_stats(results)

        return {
            "execution_id": f"exec_{uuid4().hex[:12]}",
            "results": formatted_results,
            "stats": stats,
        }

    except Exception as e:
        raise api_error(
            400,
            ErrorCode.INVALID_REQUEST,
            str(e),
        )


@router.post("/coordinate")
async def coordinate_agents(
    payload: dict[str, Any] | None = None,
    principal: PrincipalDependency = None,
) -> dict[str, object]:
    """
    Coordinate multiple agents.

    Args:
        payload: Coordination configuration
        principal: Current principal

    Returns:
        Coordination result
    """
    enforce_scope(principal, "agent:manage")
    payload = payload or {}

    try:
        # Get agents
        agent_ids = payload.get("agent_ids", [])
        agents = []

        for agent_id in agent_ids:
            status = await agent_spawner.get_agent_status(agent_id)
            if status:
                agents.append({"agent_id": agent_id, "status": status})

        if not agents:
            raise ValueError("No valid agents found")

        # Coordinate
        strategy = CoordinationStrategy(payload.get("strategy", "parallel"))
        result = await agent_coordinator.coordinate_agents(
            agents,
            strategy=strategy,
            task=payload.get("task"),
            context=payload.get("context", {}),
        )

        # Format results
        formatted_results = [
            {
                "agent_id": r.agent_id,
                "status": r.status,
                "output": r.output,
                "error": r.error,
            }
            for r in result.agent_results
        ]

        return {
            "coordination_id": result.coordination_id,
            "strategy": result.strategy.value,
            "results": formatted_results,
            "completed_at": result.completed_at.isoformat(),
        }

    except Exception as e:
        raise api_error(
            400,
            ErrorCode.INVALID_REQUEST,
            str(e),
        )


@router.get("/stats")
async def get_spawner_stats(
    principal: PrincipalDependency = None,
) -> dict[str, object]:
    """
    Get spawner statistics.

    Args:
        principal: Current principal

    Returns:
        Statistics
    """
    enforce_scope(principal, "agent:read")

    stats = agent_spawner.get_stats()

    return stats


@router.post("/{agent_id}/wait")
async def wait_for_agent(
    agent_id: str,
    timeout_seconds: int | None = Query(None),
    principal: PrincipalDependency = None,
) -> dict[str, object]:
    """
    Wait for an agent to complete.

    Args:
        agent_id: ID of agent
        timeout_seconds: Timeout in seconds
        principal: Current principal

    Returns:
        Final agent status
    """
    enforce_scope(principal, "agent:read")

    status = await agent_spawner.wait_for_agent(
        agent_id,
        timeout_seconds=timeout_seconds,
    )

    if not status:
        raise api_error(
            408,
            ErrorCode.TIMEOUT,
            "Timeout waiting for agent",
            details={"agent_id": agent_id},
        )

    return status
