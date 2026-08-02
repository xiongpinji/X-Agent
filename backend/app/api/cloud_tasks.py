"""Cloud Tasks API — submit, monitor, cancel, and retrieve cloud-executed tasks.

Endpoints:
  POST   /api/v1/cloud-tasks              - submit new task
  GET    /api/v1/cloud-tasks              - list all tasks (with filters)
  GET    /api/v1/cloud-tasks/{task_id}    - get task status/progress
  GET    /api/v1/cloud-tasks/{task_id}/result - get result
  POST   /api/v1/cloud-tasks/{task_id}/cancel - cancel task
  GET    /api/v1/cloud-tasks/{task_id}/logs   - stream execution logs
  POST   /api/v1/cloud-tasks/{task_id}/retry  - retry failed task
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.app.core.cloud_executor import (
    CloudTask,
    TaskPriority,
    TaskStatus,
    get_cloud_executor,
)
from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal

router = APIRouter(prefix="/api/v1/cloud-tasks", tags=["cloud-tasks"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------


class SubmitTaskRequest(BaseModel):
    prompt: str = Field(..., description="The task/prompt to execute")
    type: str = Field(default="agent_run", description="Task type")
    priority: TaskPriority = Field(default=TaskPriority.NORMAL)
    extra_context: dict[str, Any] | None = None
    budget_tokens: int = Field(default=16_000, ge=1000, le=200_000)
    budget_usd: float = Field(default=1.0, ge=0.01, le=100.0)
    session_id: str | None = None
    webhook_url: str | None = Field(default=None, description="Webhook URL for completion callback")
    max_retries: int = Field(default=3, ge=0, le=10)


class SubmitTaskResponse(BaseModel):
    task_id: str
    status: str
    message: str


class TaskStatusResponse(BaseModel):
    id: str
    status: str
    progress: dict[str, Any]
    created_at: str
    started_at: str | None
    completed_at: str | None


class TaskDetailResponse(BaseModel):
    id: str
    type: str
    priority: str
    status: str
    payload: dict[str, Any]
    progress: dict[str, Any]
    created_at: str
    started_at: str | None
    completed_at: str | None
    retry_count: int
    tenant_id: str
    user_id: str


class TaskResultResponse(BaseModel):
    id: str
    status: str
    result: dict[str, Any] | None


class TaskListResponse(BaseModel):
    tasks: list[dict[str, Any]]
    total: int


class CancelResponse(BaseModel):
    task_id: str
    cancelled: bool
    message: str


class RetryResponse(BaseModel):
    task_id: str
    retried: bool
    message: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=SubmitTaskResponse, status_code=202)
async def submit_task(body: SubmitTaskRequest, principal: PrincipalDependency) -> SubmitTaskResponse:
    """Submit a new cloud task for background execution."""
    executor = get_cloud_executor()

    task = CloudTask(
        type=body.type,
        payload={
            "prompt": body.prompt,
            "extra_context": body.extra_context,
            "budget_tokens": body.budget_tokens,
            "budget_usd": body.budget_usd,
            "session_id": body.session_id,
        },
        priority=body.priority,
        webhook_url=body.webhook_url,
        max_retries=body.max_retries,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
    )

    task_id = await executor.submit(task)
    return SubmitTaskResponse(
        task_id=task_id,
        status="queued",
        message=f"Task submitted successfully. Use GET /api/v1/cloud-tasks/{task_id} to track progress.",
    )


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    principal: PrincipalDependency,
    status: TaskStatus | None = Query(default=None, description="Filter by status"),
    priority: TaskPriority | None = Query(default=None, description="Filter by priority"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TaskListResponse:
    """List all cloud tasks with optional filters."""
    executor = get_cloud_executor()
    tasks = await executor.queue.list_tasks(
        status=status,
        priority=priority,
        tenant_id=principal.tenant_id,
        limit=limit,
        offset=offset,
    )
    return TaskListResponse(
        tasks=[t.to_dict() for t in tasks],
        total=len(tasks),
    )


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task(task_id: str, principal: PrincipalDependency) -> TaskDetailResponse:
    """Get task status and progress."""
    executor = get_cloud_executor()
    task = await executor.queue.get(task_id)
    if task is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return TaskDetailResponse(
        id=task.id,
        type=task.type,
        priority=task.priority.value,
        status=task.status.value,
        payload=task.payload,
        progress=task.progress.to_dict(),
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        retry_count=task.retry_count,
        tenant_id=task.tenant_id,
        user_id=task.user_id,
    )


@router.get("/{task_id}/result", response_model=TaskResultResponse)
async def get_task_result(task_id: str, principal: PrincipalDependency) -> TaskResultResponse:
    """Get the final result of a completed task."""
    executor = get_cloud_executor()
    result = await executor.get_result(task_id)
    if result is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return TaskResultResponse(**result)


@router.post("/{task_id}/cancel", response_model=CancelResponse)
async def cancel_task(task_id: str, principal: PrincipalDependency) -> CancelResponse:
    """Cancel a queued or running task."""
    executor = get_cloud_executor()
    cancelled = await executor.cancel(task_id)
    if not cancelled:
        task = await executor.queue.get(task_id)
        if task is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        return CancelResponse(
            task_id=task_id,
            cancelled=False,
            message=f"Task cannot be cancelled (status={task.status.value})",
        )
    return CancelResponse(task_id=task_id, cancelled=True, message="Task cancelled successfully")


@router.get("/{task_id}/logs")
async def stream_task_logs(task_id: str, principal: PrincipalDependency) -> StreamingResponse:
    """Stream execution logs for a task (SSE format)."""
    import asyncio
    import json

    executor = get_cloud_executor()
    task = await executor.queue.get(task_id)
    if task is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    async def _log_stream():
        last_idx = 0
        while True:
            current_task = await executor.queue.get(task_id)
            if current_task is None:
                break
            logs = current_task.logs
            if last_idx < len(logs):
                for line in logs[last_idx:]:
                    yield f"data: {json.dumps({'log': line})}\n\n"
                last_idx = len(logs)
            # Stop streaming when task is in terminal state
            if current_task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                yield f"data: {json.dumps({'event': 'done', 'status': current_task.status.value})}\n\n"
                break
            await asyncio.sleep(1.0)

    return StreamingResponse(_log_stream(), media_type="text/event-stream")


@router.post("/{task_id}/retry", response_model=RetryResponse)
async def retry_task(task_id: str, principal: PrincipalDependency) -> RetryResponse:
    """Retry a failed task."""
    executor = get_cloud_executor()
    retried = await executor.retry(task_id)
    if not retried:
        task = await executor.queue.get(task_id)
        if task is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        if task.status != TaskStatus.FAILED:
            return RetryResponse(
                task_id=task_id, retried=False,
                message=f"Only failed tasks can be retried (status={task.status.value})",
            )
        return RetryResponse(
            task_id=task_id, retried=False,
            message=f"Max retries ({task.max_retries}) exceeded",
        )
    return RetryResponse(task_id=task_id, retried=True, message="Task re-queued for execution")
