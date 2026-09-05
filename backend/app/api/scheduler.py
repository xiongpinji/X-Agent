"""
Scheduler API endpoints for X-Agent.

Provides endpoints for managing scheduled tasks.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.scheduler import cron_scheduler
from backend.app.core.security import Principal
from backend.app.core.task_monitor import task_monitor
from backend.app.core.task_queue import TaskPriority, task_queue
from backend.app.dependencies import enforce_scope, get_current_principal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


def _build_task_coroutine(
    payload: dict[str, Any],
) -> Callable[[], Coroutine[Any, Any, Any]]:
    """构建定时触发的实际协程：到点后向 task_queue 投递 agent 运行任务。

    payload["agent_task"] = {"task": "...", "context": {...}} 时投递真实 agent
    任务（由 main.py startup 注册的 "agent.run" handler 执行）；未提供时
    显式返回 skipped 并告警——不再用哑协程伪装执行成功。
    """
    agent_task = payload.get("agent_task") or {}
    schedule_name = str(payload.get("name", "task"))

    async def _fire():
        task_text = str(agent_task.get("task") or "").strip()
        if not task_text:
            logger.warning(
                "Scheduled task %r fired without agent_task.task; skipping. "
                "Provide payload[\"agent_task\"][\"task\"] to run a real agent task.",
                schedule_name,
            )
            return {"status": "skipped", "reason": "no agent_task.task configured"}
        queue_task_id = await task_queue.enqueue(
            "agent.run",
            {"task": task_text, "context": agent_task.get("context", {})},
        )
        logger.info(
            "Scheduled task %r enqueued agent.run %s", schedule_name, queue_task_id
        )
        return {"status": "enqueued", "queue_task_id": queue_task_id}

    return _fire


@router.post("/tasks")
async def create_scheduled_task(
    payload: dict[str, Any] | None = None,
    principal: PrincipalDependency = None,
) -> dict[str, object]:
    """
    Create a scheduled task.

    Args:
        payload: Task configuration
        principal: Current principal

    Returns:
        Created task info
    """
    enforce_scope(principal, "scheduler:manage")
    payload = payload or {}

    try:
        schedule_type = payload.get("schedule_type", "interval")
        task_coroutine = _build_task_coroutine(payload)

        if schedule_type == "cron":
            task_id = cron_scheduler.schedule_cron(
                name=payload.get("name", "task"),
                coroutine=task_coroutine,
                cron_expression=payload.get("cron_expression", "0 * * * *"),
                max_runs=payload.get("max_runs"),
                metadata=payload.get("metadata", {}),
            )

        elif schedule_type == "interval":
            task_id = cron_scheduler.schedule_interval(
                name=payload.get("name", "task"),
                coroutine=task_coroutine,
                interval_seconds=payload.get("interval_seconds", 3600),
                max_runs=payload.get("max_runs"),
                metadata=payload.get("metadata", {}),
            )

        elif schedule_type == "once":
            run_at = datetime.fromisoformat(payload.get("run_at"))
            task_id = cron_scheduler.schedule_once(
                name=payload.get("name", "task"),
                coroutine=task_coroutine,
                run_at=run_at,
                metadata=payload.get("metadata", {}),
            )

        else:
            raise ValueError(f"Unknown schedule type: {schedule_type}")

        return {
            "task_id": task_id,
            "status": "created",
            "created_at": datetime.now(UTC).isoformat(),
        }

    except Exception as e:
        raise api_error(
            400,
            ErrorCode.INVALID_REQUEST,
            str(e),
        )


@router.get("/tasks")
async def list_scheduled_tasks(
    status: str | None = Query(None),
    principal: PrincipalDependency = None,
) -> dict[str, object]:
    """
    List scheduled tasks.

    Args:
        status: Filter by status
        principal: Current principal

    Returns:
        List of tasks
    """
    enforce_scope(principal, "scheduler:read")

    tasks = cron_scheduler.list_tasks(status=status)

    return {
        "data": tasks,
        "count": len(tasks),
    }


@router.get("/tasks/{task_id}")
async def get_scheduled_task(
    task_id: str,
    principal: PrincipalDependency = None,
) -> dict[str, object]:
    """
    Get details of a scheduled task.

    Args:
        task_id: ID of task
        principal: Current principal

    Returns:
        Task details
    """
    enforce_scope(principal, "scheduler:read")

    task_status = cron_scheduler.get_task_status(task_id)

    if not task_status:
        raise api_error(
            404,
            ErrorCode.RESOURCE_NOT_FOUND,
            "Task not found",
            details={"task_id": task_id},
        )

    # Get execution history
    history = cron_scheduler.get_execution_history(task_id, limit=10)

    return {
        **task_status,
        "execution_history": history,
    }


@router.put("/tasks/{task_id}")
async def update_scheduled_task(
    task_id: str,
    payload: dict[str, Any] | None = None,
    principal: PrincipalDependency = None,
) -> dict[str, object]:
    """
    Update a scheduled task.

    Args:
        task_id: ID of task
        payload: Update data
        principal: Current principal

    Returns:
        Updated task info
    """
    enforce_scope(principal, "scheduler:manage")
    payload = payload or {}

    task_status = cron_scheduler.get_task_status(task_id)

    if not task_status:
        raise api_error(
            404,
            ErrorCode.RESOURCE_NOT_FOUND,
            "Task not found",
            details={"task_id": task_id},
        )

    # For now, just return the current status
    # In production, implement actual update logic
    return {
        **task_status,
        "updated_at": datetime.now(UTC).isoformat(),
    }


@router.delete("/tasks/{task_id}")
async def delete_scheduled_task(
    task_id: str,
    principal: PrincipalDependency = None,
) -> dict[str, object]:
    """
    Delete a scheduled task.

    Args:
        task_id: ID of task
        principal: Current principal

    Returns:
        Deletion result
    """
    enforce_scope(principal, "scheduler:manage")

    success = cron_scheduler.cancel_task(task_id)

    if not success:
        raise api_error(
            404,
            ErrorCode.RESOURCE_NOT_FOUND,
            "Task not found",
            details={"task_id": task_id},
        )

    return {
        "task_id": task_id,
        "status": "deleted",
        "deleted_at": datetime.now(UTC).isoformat(),
    }


@router.post("/tasks/{task_id}/pause")
async def pause_scheduled_task(
    task_id: str,
    principal: PrincipalDependency = None,
) -> dict[str, object]:
    """
    Pause a scheduled task.

    Args:
        task_id: ID of task
        principal: Current principal

    Returns:
        Pause result
    """
    enforce_scope(principal, "scheduler:manage")

    success = cron_scheduler.pause_task(task_id)

    if not success:
        raise api_error(
            404,
            ErrorCode.RESOURCE_NOT_FOUND,
            "Task not found",
            details={"task_id": task_id},
        )

    return {
        "task_id": task_id,
        "status": "paused",
        "paused_at": datetime.now(UTC).isoformat(),
    }


@router.post("/tasks/{task_id}/resume")
async def resume_scheduled_task(
    task_id: str,
    principal: PrincipalDependency = None,
) -> dict[str, object]:
    """
    Resume a paused task.

    Args:
        task_id: ID of task
        principal: Current principal

    Returns:
        Resume result
    """
    enforce_scope(principal, "scheduler:manage")

    success = cron_scheduler.resume_task(task_id)

    if not success:
        raise api_error(
            404,
            ErrorCode.RESOURCE_NOT_FOUND,
            "Task not found",
            details={"task_id": task_id},
        )

    return {
        "task_id": task_id,
        "status": "resumed",
        "resumed_at": datetime.now(UTC).isoformat(),
    }


@router.get("/queue/stats")
async def get_queue_stats(
    principal: PrincipalDependency = None,
) -> dict[str, object]:
    """
    Get task queue statistics.

    Args:
        principal: Current principal

    Returns:
        Queue statistics
    """
    enforce_scope(principal, "scheduler:read")

    stats = await task_queue.get_stats()

    return stats


@router.post("/queue/enqueue")
async def enqueue_task(
    payload: dict[str, Any] | None = None,
    principal: PrincipalDependency = None,
) -> dict[str, object]:
    """
    Enqueue a task.

    Args:
        payload: Task data
        principal: Current principal

    Returns:
        Enqueue result
    """
    enforce_scope(principal, "scheduler:manage")
    payload = payload or {}

    try:
        priority_str = payload.get("priority", "NORMAL")
        priority = TaskPriority[priority_str]

        # RedisTaskQueue.enqueue 是位置参数签名（task_name, payload, ...），
        # 此前按 name=/payload=/metadata= 关键字调用必然 TypeError→400。
        task_id = await task_queue.enqueue(
            payload.get("name", "task"),
            payload.get("payload", {}),
            priority=priority,
            max_retries=payload.get("max_retries", 3),
        )

        return {
            "task_id": task_id,
            "status": "enqueued",
            "enqueued_at": datetime.now(UTC).isoformat(),
        }

    except Exception as e:
        raise api_error(
            400,
            ErrorCode.INVALID_REQUEST,
            str(e),
        )


@router.get("/monitor/health")
async def get_health_status(
    principal: PrincipalDependency = None,
) -> dict[str, object]:
    """
    Get task monitoring health status.

    Args:
        principal: Current principal

    Returns:
        Health status
    """
    enforce_scope(principal, "scheduler:read")

    health = task_monitor.get_health_status()

    return health


@router.get("/monitor/performance")
async def get_performance_summary(
    principal: PrincipalDependency = None,
) -> dict[str, object]:
    """
    Get performance summary.

    Args:
        principal: Current principal

    Returns:
        Performance summary
    """
    enforce_scope(principal, "scheduler:read")

    summary = task_monitor.get_performance_summary()

    return summary


@router.get("/stats")
async def get_scheduler_stats(
    principal: PrincipalDependency = None,
) -> dict[str, object]:
    """
    Get scheduler statistics.

    Args:
        principal: Current principal

    Returns:
        Scheduler statistics
    """
    enforce_scope(principal, "scheduler:read")

    stats = cron_scheduler.get_scheduler_stats()

    return stats
