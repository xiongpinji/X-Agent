"""
Task management and visualization API for X-Agent.

Provides CRUD operations and real-time updates for task tracking,
including task dependencies, progress tracking, and status management.
"""

from __future__ import annotations

import contextlib
import logging
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


class TaskStatus(StrEnum):
    """Task status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(StrEnum):
    """Task priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskModel(BaseModel):
    """Task data model."""
    task_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique task ID")
    title: str = Field(..., min_length=1, max_length=500, description="Task title")
    description: str = Field(default="", max_length=5000, description="Task description")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Current task status")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM, description="Task priority")
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="Progress percentage (0-1)")

    # Timing
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Creation timestamp")
    started_at: str | None = Field(default=None, description="Start timestamp")
    completed_at: str | None = Field(default=None, description="Completion timestamp")
    estimated_duration_seconds: int | None = Field(default=None, ge=0, description="Estimated duration in seconds")

    # Dependencies
    depends_on: list[str] = Field(default_factory=list, description="List of task IDs this task depends on")
    blocks: list[str] = Field(default_factory=list, description="List of task IDs this task blocks")

    # Metadata
    tags: list[str] = Field(default_factory=list, description="Task tags for categorization")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Custom metadata")

    # Results
    result: Any = Field(default=None, description="Task result/output")
    error: str | None = Field(default=None, description="Error message if failed")

    # Tracking
    run_id: str | None = Field(default=None, description="Associated agent run ID")
    parent_task_id: str | None = Field(default=None, description="Parent task ID for subtasks")


class TaskCreateRequest(BaseModel):
    """Request to create a task."""
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(default="", max_length=5000)
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM)
    depends_on: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    estimated_duration_seconds: int | None = Field(default=None, ge=0)
    parent_task_id: str | None = Field(default=None)


class TaskUpdateRequest(BaseModel):
    """Request to update a task."""
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus | None = Field(default=None)
    priority: TaskPriority | None = Field(default=None)
    progress: float | None = Field(default=None, ge=0.0, le=1.0)
    tags: list[str] | None = Field(default=None)
    metadata: dict[str, Any] | None = Field(default=None)
    result: Any = Field(default=None)
    error: str | None = Field(default=None)


class TaskProgressResponse(BaseModel):
    """Task progress information."""
    task_id: str
    status: TaskStatus
    progress: float
    completed_steps: int = 0
    total_steps: int = 0
    estimated_remaining_seconds: int | None = None
    current_step_description: str = ""


class TaskListResponse(BaseModel):
    """Response for task list."""
    tasks: list[TaskModel]
    total: int
    completed: int
    in_progress: int
    failed: int
    pending: int


class TaskDependencyGraph(BaseModel):
    """Task dependency graph."""
    task_id: str
    dependencies: list[str]
    dependents: list[str]
    critical_path: list[str]


# In-memory task store (in production, use database)
class TaskStore:
    """Simple in-memory task store."""

    def __init__(self):
        self.tasks: dict[str, TaskModel] = {}
        self.task_index: dict[str, list[str]] = {}  # Index by run_id

    def create(self, task: TaskModel) -> TaskModel:
        """Create a new task."""
        self.tasks[task.task_id] = task
        if task.run_id:
            if task.run_id not in self.task_index:
                self.task_index[task.run_id] = []
            self.task_index[task.run_id].append(task.task_id)
        return task

    def get(self, task_id: str) -> TaskModel | None:
        """Get a task by ID."""
        return self.tasks.get(task_id)

    def list(self, run_id: str | None = None, status: TaskStatus | None = None) -> list[TaskModel]:
        """List tasks with optional filtering."""
        tasks = list(self.tasks.values())

        if run_id:
            tasks = [t for t in tasks if t.run_id == run_id]

        if status:
            tasks = [t for t in tasks if t.status == status]

        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    def update(self, task_id: str, updates: dict[str, Any]) -> TaskModel | None:
        """Update a task."""
        task = self.tasks.get(task_id)
        if not task:
            return None

        for key, value in updates.items():
            if hasattr(task, key) and value is not None:
                setattr(task, key, value)

        return task

    def delete(self, task_id: str) -> bool:
        """Delete a task."""
        if task_id in self.tasks:
            task = self.tasks.pop(task_id)
            if task.run_id and task.run_id in self.task_index:
                with contextlib.suppress(ValueError):
                    self.task_index[task.run_id].remove(task_id)
            return True
        return False

    def get_stats(self, run_id: str | None = None) -> dict[str, int]:
        """Get task statistics."""
        tasks = self.list(run_id=run_id)
        return {
            "total": len(tasks),
            "pending": sum(1 for t in tasks if t.status == TaskStatus.PENDING),
            "in_progress": sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS),
            "completed": sum(1 for t in tasks if t.status == TaskStatus.COMPLETED),
            "failed": sum(1 for t in tasks if t.status == TaskStatus.FAILED),
            "cancelled": sum(1 for t in tasks if t.status == TaskStatus.CANCELLED),
        }


# Global task store
task_store = TaskStore()


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    principal: PrincipalDependency,
    run_id: str | None = Query(default=None, description="Filter by run ID"),
    status: TaskStatus | None = Query(default=None, description="Filter by status"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> TaskListResponse:
    """
    List tasks with optional filtering.

    Args:
        run_id: Optional run ID to filter tasks
        status: Optional status to filter tasks
        limit: Maximum number of tasks to return
        offset: Number of tasks to skip

    Returns:
        List of tasks with statistics
    """
    enforce_scope(principal, "agent:read")

    tasks = task_store.list(run_id=run_id, status=status)
    stats = task_store.get_stats(run_id=run_id)

    paginated = tasks[offset : offset + limit]

    return TaskListResponse(
        tasks=paginated,
        total=stats["total"],
        completed=stats["completed"],
        in_progress=stats["in_progress"],
        failed=stats["failed"],
        pending=stats["pending"],
    )


@router.post("", response_model=TaskModel, status_code=status.HTTP_201_CREATED)
async def create_task(
    request: TaskCreateRequest,
    principal: PrincipalDependency,
) -> TaskModel:
    """
    Create a new task.

    Args:
        request: Task creation request

    Returns:
        Created task
    """
    enforce_scope(principal, "agent:run")

    task = TaskModel(
        title=request.title,
        description=request.description,
        priority=request.priority,
        depends_on=request.depends_on,
        tags=request.tags,
        metadata=request.metadata,
        estimated_duration_seconds=request.estimated_duration_seconds,
        parent_task_id=request.parent_task_id,
    )

    return task_store.create(task)


@router.get("/{task_id}", response_model=TaskModel)
async def get_task(
    task_id: str,
    principal: PrincipalDependency,
) -> TaskModel:
    """
    Get a task by ID.

    Args:
        task_id: Task ID

    Returns:
        Task details
    """
    enforce_scope(principal, "agent:read")

    task = task_store.get(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    return task


@router.put("/{task_id}", response_model=TaskModel)
async def update_task(
    task_id: str,
    request: TaskUpdateRequest,
    principal: PrincipalDependency,
) -> TaskModel:
    """
    Update a task.

    Args:
        task_id: Task ID
        request: Update request

    Returns:
        Updated task
    """
    enforce_scope(principal, "agent:run")

    task = task_store.get(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    updates = request.model_dump(exclude_unset=True)

    # Handle status transitions
    if "status" in updates:
        new_status = updates["status"]
        if new_status == TaskStatus.IN_PROGRESS and not task.started_at:
            updates["started_at"] = datetime.utcnow().isoformat()
        elif new_status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            if not task.completed_at:
                updates["completed_at"] = datetime.utcnow().isoformat()

    updated_task = task_store.update(task_id, updates)
    if not updated_task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    return updated_task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: str,
    principal: PrincipalDependency,
) -> None:
    """
    Delete a task.

    Args:
        task_id: Task ID
    """
    enforce_scope(principal, "agent:run")

    if not task_store.delete(task_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")


@router.get("/{task_id}/progress", response_model=TaskProgressResponse)
async def get_task_progress(
    task_id: str,
    principal: PrincipalDependency,
) -> TaskProgressResponse:
    """
    Get detailed progress information for a task.

    Args:
        task_id: Task ID

    Returns:
        Progress details
    """
    enforce_scope(principal, "agent:read")

    task = task_store.get(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    estimated_remaining = None
    if task.estimated_duration_seconds and task.started_at:
        start_time = datetime.fromisoformat(task.started_at)
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        remaining = max(0, task.estimated_duration_seconds - elapsed)
        estimated_remaining = int(remaining)

    return TaskProgressResponse(
        task_id=task_id,
        status=task.status,
        progress=task.progress,
        estimated_remaining_seconds=estimated_remaining,
        current_step_description=task.metadata.get("current_step", ""),
    )


@router.get("/{task_id}/dependencies", response_model=TaskDependencyGraph)
async def get_task_dependencies(
    task_id: str,
    principal: PrincipalDependency,
) -> TaskDependencyGraph:
    """
    Get task dependency graph.

    Args:
        task_id: Task ID

    Returns:
        Dependency information
    """
    enforce_scope(principal, "agent:read")

    task = task_store.get(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Find dependents (tasks that depend on this one)
    dependents = []
    for t in task_store.tasks.values():
        if task_id in t.depends_on:
            dependents.append(t.task_id)

    # Calculate critical path (simplified)
    critical_path = [task_id]
    current = task
    while current.depends_on:
        # Take first dependency
        dep_id = current.depends_on[0]
        critical_path.insert(0, dep_id)
        current = task_store.get(dep_id)
        if not current:
            break

    return TaskDependencyGraph(
        task_id=task_id,
        dependencies=task.depends_on,
        dependents=dependents,
        critical_path=critical_path,
    )


@router.post("/{task_id}/complete", response_model=TaskModel)
async def complete_task(
    task_id: str,
    result: Any = None,
    *,
    principal: PrincipalDependency,
) -> TaskModel:
    """
    Mark a task as completed.

    Args:
        task_id: Task ID
        result: Optional result data

    Returns:
        Updated task
    """
    enforce_scope(principal, "agent:run")

    task = task_store.get(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    updates = {
        "status": TaskStatus.COMPLETED,
        "progress": 1.0,
        "completed_at": datetime.utcnow().isoformat(),
    }
    if result is not None:
        updates["result"] = result

    updated_task = task_store.update(task_id, updates)
    return updated_task


@router.post("/{task_id}/fail", response_model=TaskModel)
async def fail_task(
    task_id: str,
    error: str = Body(..., description="Error message"),
    *,
    principal: PrincipalDependency,
) -> TaskModel:
    """
    Mark a task as failed.

    Args:
        task_id: Task ID
        error: Error message

    Returns:
        Updated task
    """
    enforce_scope(principal, "agent:run")

    task = task_store.get(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    updates = {
        "status": TaskStatus.FAILED,
        "error": error,
        "completed_at": datetime.utcnow().isoformat(),
    }

    updated_task = task_store.update(task_id, updates)
    return updated_task


@router.get("/run/{run_id}/summary", response_model=dict[str, Any])
async def get_run_task_summary(
    run_id: str,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """
    Get task summary for a run.

    Args:
        run_id: Run ID

    Returns:
        Task summary statistics
    """
    enforce_scope(principal, "agent:read")

    tasks = task_store.list(run_id=run_id)
    stats = task_store.get_stats(run_id=run_id)

    total_progress = sum(t.progress for t in tasks) / len(tasks) if tasks else 0.0

    return {
        "run_id": run_id,
        "statistics": stats,
        "overall_progress": total_progress,
        "tasks": [t.model_dump() for t in tasks],
    }
