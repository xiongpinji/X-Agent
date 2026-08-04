"""Cloud Async Execution — Codex-style task queue + background execution + completion notification.

Submit task → disconnect → cloud executes → notify on completion.
Supports long-running tasks (up to 7 hours), priority queue, graceful shutdown,
progress reporting, cost tracking, and persistent queue (SQLite) for restart survival.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TaskPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Priority ordering for the queue (lower number = higher priority)
_PRIORITY_ORDER: dict[TaskPriority, int] = {
    TaskPriority.CRITICAL: 0,
    TaskPriority.HIGH: 1,
    TaskPriority.NORMAL: 2,
    TaskPriority.LOW: 3,
}


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class TaskProgress:
    current_step: int = 0
    total_steps: int = 0
    percentage: float = 0.0
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "percentage": self.percentage,
            "message": self.message,
        }


@dataclass
class TaskResult:
    output: str = ""
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    cost_usd: float = 0.0
    tokens_used: int = 0
    duration_seconds: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "output": self.output,
            "artifacts": self.artifacts,
            "cost_usd": self.cost_usd,
            "tokens_used": self.tokens_used,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
        }


@dataclass
class CloudTask:
    id: str = field(default_factory=lambda: str(uuid4()))
    type: str = "agent_run"
    payload: dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.QUEUED
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    started_at: str | None = None
    completed_at: str | None = None
    result: TaskResult = field(default_factory=TaskResult)
    progress: TaskProgress = field(default_factory=TaskProgress)
    logs: list[str] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    webhook_url: str | None = None
    tenant_id: str = "default"
    user_id: str = "anonymous"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "payload": self.payload,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result.to_dict(),
            "progress": self.progress.to_dict(),
            "logs": self.logs[-100:],  # last 100 log lines
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "webhook_url": self.webhook_url,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
        }


# ---------------------------------------------------------------------------
# Persistent Queue (SQLite)
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cloud_tasks (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL DEFAULT 'agent_run',
    payload TEXT NOT NULL DEFAULT '{}',
    priority TEXT NOT NULL DEFAULT 'normal',
    status TEXT NOT NULL DEFAULT 'queued',
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    result TEXT NOT NULL DEFAULT '{}',
    progress TEXT NOT NULL DEFAULT '{}',
    logs TEXT NOT NULL DEFAULT '[]',
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    webhook_url TEXT,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    user_id TEXT NOT NULL DEFAULT 'anonymous'
);
CREATE INDEX IF NOT EXISTS idx_cloud_tasks_status ON cloud_tasks(status);
CREATE INDEX IF NOT EXISTS idx_cloud_tasks_priority ON cloud_tasks(priority);
"""


class CloudTaskQueue:
    """In-memory + SQLite persistent task queue with priority support."""

    def __init__(self, db_path: str | Path = "data/cloud_tasks.db", max_queue_size: int = 1000):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._max_queue_size = max_queue_size
        self._tasks: dict[str, CloudTask] = {}
        self._queue: asyncio.PriorityQueue[tuple[int, float, str]] = asyncio.PriorityQueue()
        self._lock = asyncio.Lock()
        self._init_db()
        self._recover_from_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.executescript(_SCHEMA_SQL)
            conn.commit()
        finally:
            conn.close()

    def _recover_from_db(self) -> None:
        """Recover queued/running tasks from SQLite after restart."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM cloud_tasks WHERE status IN ('queued', 'running') ORDER BY created_at"
            ).fetchall()
            for row in rows:
                task = self._row_to_task(row)
                # Running tasks that were interrupted → mark as queued for retry
                if task.status == TaskStatus.RUNNING:
                    task.status = TaskStatus.QUEUED
                    task.started_at = None
                    task.logs.append(f"[recovery] Task was running during shutdown, re-queued at {datetime.now(UTC).isoformat()}")
                self._tasks[task.id] = task
            logger.info("CloudTaskQueue recovered %d tasks from SQLite", len(rows))
        finally:
            conn.close()

    def _row_to_task(self, row: sqlite3.Row) -> CloudTask:
        result_data = json.loads(row["result"] or "{}")
        progress_data = json.loads(row["progress"] or "{}")
        return CloudTask(
            id=row["id"],
            type=row["type"],
            payload=json.loads(row["payload"] or "{}"),
            priority=TaskPriority(row["priority"]),
            status=TaskStatus(row["status"]),
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            result=TaskResult(
                output=result_data.get("output", ""),
                artifacts=result_data.get("artifacts", []),
                cost_usd=result_data.get("cost_usd", 0.0),
                tokens_used=result_data.get("tokens_used", 0),
                duration_seconds=result_data.get("duration_seconds", 0.0),
                error=result_data.get("error"),
            ),
            progress=TaskProgress(
                current_step=progress_data.get("current_step", 0),
                total_steps=progress_data.get("total_steps", 0),
                percentage=progress_data.get("percentage", 0.0),
                message=progress_data.get("message", ""),
            ),
            logs=json.loads(row["logs"] or "[]"),
            retry_count=row["retry_count"],
            max_retries=row["max_retries"],
            webhook_url=row["webhook_url"],
            tenant_id=row["tenant_id"],
            user_id=row["user_id"],
        )

    def _persist_task(self, task: CloudTask) -> None:
        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.execute(
                """INSERT OR REPLACE INTO cloud_tasks
                   (id, type, payload, priority, status, created_at, started_at, completed_at,
                    result, progress, logs, retry_count, max_retries, webhook_url, tenant_id, user_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task.id, task.type, json.dumps(task.payload), task.priority.value,
                    task.status.value, task.created_at, task.started_at, task.completed_at,
                    json.dumps(task.result.to_dict()), json.dumps(task.progress.to_dict()),
                    json.dumps(task.logs[-200:]), task.retry_count, task.max_retries,
                    task.webhook_url, task.tenant_id, task.user_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    async def enqueue(self, task: CloudTask) -> None:
        async with self._lock:
            if len(self._tasks) >= self._max_queue_size:
                raise RuntimeError(f"Queue full (max {self._max_queue_size})")
            self._tasks[task.id] = task
            self._persist_task(task)
            priority_num = _PRIORITY_ORDER.get(task.priority, 2)
            await self._queue.put((priority_num, time.time(), task.id))

    async def dequeue(self) -> CloudTask | None:
        try:
            _, _, task_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)
        except (TimeoutError, asyncio.QueueEmpty):
            return None
        async with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == TaskStatus.QUEUED:
                return task
        return None

    async def get(self, task_id: str) -> CloudTask | None:
        async with self._lock:
            return self._tasks.get(task_id)

    async def update(self, task: CloudTask) -> None:
        async with self._lock:
            self._tasks[task.id] = task
            self._persist_task(task)

    async def list_tasks(
        self,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        tenant_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CloudTask]:
        async with self._lock:
            tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        if priority:
            tasks = [t for t in tasks if t.priority == priority]
        if tenant_id:
            tasks = [t for t in tasks if t.tenant_id == tenant_id]
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks[offset: offset + limit]

    @property
    def pending_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status == TaskStatus.QUEUED)

    @property
    def running_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status == TaskStatus.RUNNING)


# ---------------------------------------------------------------------------
# Completion Notifier
# ---------------------------------------------------------------------------


class CompletionNotifier:
    """Notify on task completion via webhook, in-app notification, or optional channels."""

    def __init__(self) -> None:
        self._in_app_notifications: list[dict[str, Any]] = []
        self._subscribers: list[Callable[[CloudTask], Any]] = []

    def subscribe(self, callback: Callable[[CloudTask], Any]) -> None:
        self._subscribers.append(callback)

    async def notify(self, task: CloudTask) -> None:
        """Send completion notifications through all configured channels."""
        # In-app notification
        notification = {
            "id": str(uuid4()),
            "task_id": task.id,
            "type": "task_completed" if task.status == TaskStatus.COMPLETED else "task_failed",
            "title": f"Task {task.id[:8]}... {task.status.value}",
            "message": task.result.output[:500] if task.result.output else (task.result.error or ""),
            "created_at": datetime.now(UTC).isoformat(),
            "read": False,
        }
        self._in_app_notifications.append(notification)
        # Keep last 500 notifications
        if len(self._in_app_notifications) > 500:
            self._in_app_notifications = self._in_app_notifications[-500:]

        # Webhook callback
        if task.webhook_url:
            await self._send_webhook(task)

        # Subscribers (e.g., email/Slack integrations)
        for subscriber in self._subscribers:
            try:
                result = subscriber(task)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                logger.warning("Notification subscriber failed: %s", exc)

    async def _send_webhook(self, task: CloudTask) -> None:
        try:
            payload = {
                "event": "task.completed",
                "task_id": task.id,
                "status": task.status.value,
                "result": task.result.to_dict(),
                "progress": task.progress.to_dict(),
                "timestamp": datetime.now(UTC).isoformat(),
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(task.webhook_url, json=payload)  # type: ignore[arg-type]
                if resp.status_code >= 400:
                    logger.warning("Webhook returned %d for task %s", resp.status_code, task.id)
        except Exception as exc:
            logger.warning("Webhook delivery failed for task %s: %s", task.id, exc)

    def get_notifications(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._in_app_notifications[-limit:]


# ---------------------------------------------------------------------------
# Cloud Executor
# ---------------------------------------------------------------------------


class CloudExecutor:
    """Background task executor with worker pool, progress reporting, and graceful shutdown.

    Uses asyncio.Semaphore for concurrency control. Tasks run AgentLoop in background.
    """

    def __init__(
        self,
        queue: CloudTaskQueue,
        notifier: CompletionNotifier,
        max_concurrent: int = 3,
        task_timeout: float = 3600.0,
    ):
        self._queue = queue
        self._notifier = notifier
        self._max_concurrent = max_concurrent
        self._task_timeout = task_timeout
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._workers: list[asyncio.Task] = []
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._shutdown_event = asyncio.Event()
        self._started = False

    @property
    def queue(self) -> CloudTaskQueue:
        return self._queue

    @property
    def notifier(self) -> CompletionNotifier:
        return self._notifier

    async def start(self) -> None:
        """Start the worker pool."""
        if self._started:
            return
        self._started = True
        self._shutdown_event.clear()
        for i in range(self._max_concurrent):
            worker = asyncio.create_task(self._worker_loop(i), name=f"cloud-worker-{i}")
            self._workers.append(worker)
        logger.info("CloudExecutor started with %d workers (timeout=%.0fs)", self._max_concurrent, self._task_timeout)

    async def stop(self, graceful_timeout: float = 30.0) -> None:
        """Graceful shutdown: signal workers, wait for running tasks or timeout."""
        self._shutdown_event.set()
        # Cancel idle workers
        for w in self._workers:
            w.cancel()
        # Wait for running tasks up to graceful_timeout
        if self._running_tasks:
            logger.info("Waiting up to %.0fs for %d running tasks...", graceful_timeout, len(self._running_tasks))
            _done, pending = await asyncio.wait(
                list(self._running_tasks.values()), timeout=graceful_timeout
            )
            for t in pending:
                t.cancel()
                logger.warning("Force-cancelled cloud task on shutdown")
        self._workers.clear()
        self._running_tasks.clear()
        self._started = False
        logger.info("CloudExecutor stopped")

    async def submit(self, task: CloudTask) -> str:
        """Queue a task for background execution. Returns task_id."""
        await self._queue.enqueue(task)
        logger.info("Task %s submitted (priority=%s, type=%s)", task.id, task.priority.value, task.type)
        return task.id

    async def cancel(self, task_id: str) -> bool:
        """Gracefully cancel a task."""
        task = await self._queue.get(task_id)
        if task is None:
            return False
        if task.status == TaskStatus.QUEUED:
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now(UTC).isoformat()
            await self._queue.update(task)
            return True
        if task.status == TaskStatus.RUNNING:
            # Signal the asyncio task to cancel
            asyncio_task = self._running_tasks.get(task_id)
            if asyncio_task:
                asyncio_task.cancel()
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now(UTC).isoformat()
            task.logs.append(f"[cancel] Cancelled at {datetime.now(UTC).isoformat()}")
            await self._queue.update(task)
            return True
        return False

    async def get_status(self, task_id: str) -> dict[str, Any] | None:
        task = await self._queue.get(task_id)
        if task is None:
            return None
        return {
            "id": task.id,
            "status": task.status.value,
            "progress": task.progress.to_dict(),
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
        }

    async def get_result(self, task_id: str) -> dict[str, Any] | None:
        task = await self._queue.get(task_id)
        if task is None:
            return None
        if task.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            return {"id": task.id, "status": task.status.value, "result": None}
        return {"id": task.id, "status": task.status.value, "result": task.result.to_dict()}

    async def retry(self, task_id: str) -> bool:
        """Retry a failed task."""
        task = await self._queue.get(task_id)
        if task is None or task.status != TaskStatus.FAILED:
            return False
        if task.retry_count >= task.max_retries:
            return False
        task.retry_count += 1
        task.status = TaskStatus.QUEUED
        task.started_at = None
        task.completed_at = None
        task.result = TaskResult()
        task.progress = TaskProgress()
        task.logs.append(f"[retry] Retry #{task.retry_count} at {datetime.now(UTC).isoformat()}")
        await self._queue.update(task)
        # Re-enqueue
        priority_num = _PRIORITY_ORDER.get(task.priority, 2)
        await self._queue._queue.put((priority_num, time.time(), task.id))
        return True

    async def _worker_loop(self, worker_id: int) -> None:
        """Worker loop: pull tasks from queue and execute them."""
        while not self._shutdown_event.is_set():
            task = await self._queue.dequeue()
            if task is None:
                await asyncio.sleep(0.5)
                continue
            async with self._semaphore:
                exec_task = asyncio.create_task(
                    self._execute_task(task), name=f"exec-{task.id[:8]}"
                )
                self._running_tasks[task.id] = exec_task
                try:
                    await exec_task
                except asyncio.CancelledError:
                    pass
                finally:
                    self._running_tasks.pop(task.id, None)

    async def _execute_task(self, task: CloudTask) -> None:
        """Execute a single task with timeout and progress tracking."""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(UTC).isoformat()
        task.logs.append(f"[start] Execution started at {task.started_at}")
        await self._queue.update(task)

        start_time = time.monotonic()
        try:
            await asyncio.wait_for(
                self._run_agent_task(task),
                timeout=self._task_timeout,
            )
            task.status = TaskStatus.COMPLETED
            task.progress.percentage = 100.0
            task.progress.message = "Completed"
        except TimeoutError:
            task.status = TaskStatus.FAILED
            task.result.error = f"Task timed out after {self._task_timeout:.0f}s"
            task.logs.append(f"[timeout] {task.result.error}")
        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            task.logs.append("[cancelled] Task was cancelled")
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.result.error = str(exc)
            task.logs.append(f"[error] {exc}")
            logger.exception("Cloud task %s failed", task.id)
        finally:
            elapsed = time.monotonic() - start_time
            task.result.duration_seconds = round(elapsed, 2)
            task.completed_at = datetime.now(UTC).isoformat()
            await self._queue.update(task)
            await self._notifier.notify(task)

    async def _run_agent_task(self, task: CloudTask) -> None:
        """Run the AgentLoop for this task. Emits progress events."""
        from backend.app.core.contracts import RunContext
        from backend.app.dependencies import get_agent

        task_payload = task.payload
        prompt = task_payload.get("prompt", task_payload.get("task", ""))
        if not prompt:
            raise ValueError("Task payload must contain 'prompt' or 'task' field")

        # Update progress: starting
        task.progress = TaskProgress(current_step=1, total_steps=3, percentage=10.0, message="Initializing agent...")
        task.logs.append("[progress] Initializing agent...")
        await self._queue.update(task)

        # Build RunContext
        context = RunContext(
            tenant_id=task.tenant_id,
            user_id=task.user_id,
            budget_tokens=task_payload.get("budget_tokens", 16_000),
            budget_usd=task_payload.get("budget_usd", 1.0),
            session_id=task_payload.get("session_id"),
        )

        # Progress: executing
        task.progress = TaskProgress(current_step=2, total_steps=3, percentage=30.0, message="Agent executing...")
        task.logs.append("[progress] Agent executing task...")
        await self._queue.update(task)

        # Define progress callback for trace events
        async def _progress_callback(event: Any) -> None:
            if hasattr(event, "event_type"):
                task.logs.append(f"[event] {event.event_type}: {getattr(event, 'data', '')}")
                # Keep logs bounded
                if len(task.logs) > 500:
                    task.logs = task.logs[-300:]

        # Run the agent
        agent = get_agent()
        response = await agent.run(
            context=context,
            task=prompt,
            extra_context=task_payload.get("extra_context"),
            event_callback=_progress_callback,
        )

        # Collect results
        task.result.output = response.answer or ""
        task.result.tokens_used = getattr(response, "tokens_used", 0) or 0
        task.result.cost_usd = getattr(response, "cost_usd", 0.0) or 0.0

        # Collect artifacts from tool calls
        if hasattr(response, "tool_calls") and response.tool_calls:
            for tc in response.tool_calls:
                artifact = {
                    "tool": getattr(tc, "tool_name", "unknown"),
                    "output_preview": str(getattr(tc, "result", ""))[:200],
                }
                task.result.artifacts.append(artifact)

        # Progress: done
        task.progress = TaskProgress(current_step=3, total_steps=3, percentage=100.0, message="Completed")
        task.logs.append(f"[done] Agent completed. Tokens={task.result.tokens_used}, Cost=${task.result.cost_usd:.4f}")
        await self._queue.update(task)


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

_executor_instance: CloudExecutor | None = None


def get_cloud_executor() -> CloudExecutor:
    """Get or create the global CloudExecutor singleton."""
    global _executor_instance
    if _executor_instance is None:
        from backend.app.settings import get_settings

        settings = get_settings()
        db_path = Path("data") / "cloud_tasks.db"
        queue = CloudTaskQueue(
            db_path=db_path,
            max_queue_size=getattr(settings, "cloud_executor_queue_size", 1000),
        )
        notifier = CompletionNotifier()
        _executor_instance = CloudExecutor(
            queue=queue,
            notifier=notifier,
            max_concurrent=getattr(settings, "cloud_executor_max_concurrent", 3),
            task_timeout=getattr(settings, "cloud_executor_timeout", 3600.0),
        )
    return _executor_instance
