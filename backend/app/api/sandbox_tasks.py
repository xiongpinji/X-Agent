"""Sandbox task API — Codex-style async task submission + GitHub webhook.

Endpoints:
  POST /api/v1/sandbox/tasks         submit a task for isolated execution
  GET  /api/v1/sandbox/tasks/{id}    poll a task's status/result
  GET  /api/v1/sandbox/tasks         list recent tasks
  POST /api/v1/sandbox/webhook/github  receive GitHub issue events (signed)

The submit endpoint is fire-and-forget: it enqueues the task and returns a
task_id immediately. Results are collected in an in-memory store and polled
via the GET endpoints. This mirrors Codex's "assign and come back" model.

Security:
  - All non-webhook endpoints require the `sandbox:run` scope.
  - The webhook verifies GitHub's HMAC signature when XAGENT_GITHUB_WEBHOOK_SECRET
    is configured; otherwise it rejects with 403 (no unsigned execution).
  - Webhook payloads only enqueue tasks — they never execute issue-body
    instructions directly.
"""

from __future__ import annotations

import asyncio

import logging
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.dependencies import get_current_principal, enforce_scope
from backend.app.core.security import Principal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sandbox", tags=["sandbox"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


class TaskSubmitRequest(BaseModel):
    """Request to submit a sandboxed task."""

    name: str = Field(..., description="Human-readable task name")
    command: str = Field(..., description="Shell command to run in the sandbox")
    image: str = Field(default="python:3.11-slim", description="Container image")
    timeout_seconds: float = Field(default=300.0, ge=1, le=3600)
    enable_network: bool = Field(default=False)


class TaskSubmitResponse(BaseModel):
    task_id: str
    status: str = "queued"


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    backend: Optional[str] = None
    steps: list[dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None


# ----- module-level orchestrator (lazy singleton) -----

_queue: Any = None
_orchestrator: Any = None
_results: dict[str, Any] = {}
_status: dict[str, str] = {}


def _get_orchestrator():
    """Lazily build a TaskQueue + SandboxOrchestrator running a shell-command
    handler. Kept module-level so submitted tasks share one queue."""
    global _queue, _orchestrator
    if _orchestrator is not None:
        return _orchestrator

    import asyncio
    from backend.app.core.task_queue import TaskQueue
    from backend.app.core.sandbox.orchestrator import SandboxOrchestrator
    from backend.app.core.sandbox.docker_sandbox import SandboxSpec

    async def _command_handler(sandbox, task, result):
        cmd = task.payload.get("command", "")
        r = await sandbox.run(cmd, timeout=task.payload.get("timeout_seconds", 300.0))
        result.add_step("command", r)
        return r.success

    def _spec_factory(task):
        return SandboxSpec(
            image=task.payload.get("image", "python:3.11-slim"),
            timeout_seconds=task.payload.get("timeout_seconds", 300.0),
            enable_network=task.payload.get("enable_network", False),
        )

    _queue = TaskQueue()
    _orchestrator = SandboxOrchestrator(
        _queue, _command_handler, max_concurrent=4, spec_factory=_spec_factory
    )
    return _orchestrator


_worker_task = None
_worker_running = False


async def _drain_loop() -> None:
    """Persistent background loop: drain the queue, run each task in its own
    sandbox, store results. Launched at app startup so it lives on the app's
    event loop (not a per-request loop that closes)."""
    global _worker_running
    orch = _get_orchestrator()
    _worker_running = True
    import asyncio

    while _worker_running:
        task = await _queue.dequeue(timeout_seconds=1)
        if task is None:
            await asyncio.sleep(0.05)
            continue
        _status[task.task_id] = "running"
        try:
            result = await orch._worker.process(task)
            _results[task.task_id] = result
            _status[task.task_id] = "completed" if result.success else "failed"
        except Exception:
            _status[task.task_id] = "error"
            logger.exception("sandbox task %s failed", task.task_id)


async def start_sandbox_worker() -> None:
    """Start the background drain loop (called from app startup).

    Idempotent + loop-aware: if a previous worker task exists but is done
    (e.g. its event loop closed between TestClient contexts), it is replaced
    with a fresh task on the current loop.
    """
    global _worker_task, _worker_running

    _get_orchestrator()
    if _worker_task is not None and not _worker_task.done():
        return  # already running on the current loop
    _worker_running = True
    _worker_task = asyncio.create_task(_drain_loop())
    logger.info("Sandbox worker started")


async def stop_sandbox_worker() -> None:
    """Stop the background drain loop (called from app shutdown)."""
    global _worker_task, _worker_running
    import asyncio
    _worker_running = False
    if _worker_task is not None:
        _worker_task.cancel()
        try:
            await _worker_task
        except (Exception, asyncio.CancelledError):
            pass
        _worker_task = None


@router.post("/tasks", response_model=TaskSubmitResponse)
async def submit_task(
    request: TaskSubmitRequest, principal: PrincipalDependency
) -> TaskSubmitResponse:
    """Submit a task for isolated sandbox execution (fire-and-forget)."""
    enforce_scope(principal, "sandbox:run")
    import asyncio

    orch = _get_orchestrator()
    task_id = await orch.submit(
        name=request.name,
        payload={
            "command": request.command,
            "image": request.image,
            "timeout_seconds": request.timeout_seconds,
            "enable_network": request.enable_network,
        },
    )
    _status[task_id] = "queued"
    return TaskSubmitResponse(task_id=task_id, status="queued")


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task(task_id: str, principal: PrincipalDependency) -> TaskStatusResponse:
    """Poll a task's status and result."""
    enforce_scope(principal, "sandbox:run")
    status = _status.get(task_id)
    if status is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, f"task {task_id} not found")
    result = _results.get(task_id)
    return TaskStatusResponse(
        task_id=task_id,
        status=status,
        backend=getattr(result, "backend", None),
        steps=getattr(result, "steps", []),
        error=getattr(result, "error", None),
    )


@router.get("/tasks")
async def list_tasks(principal: PrincipalDependency) -> dict[str, Any]:
    """List all known task ids and their statuses."""
    enforce_scope(principal, "sandbox:run")
    return {"tasks": [{"task_id": tid, "status": st} for tid, st in _status.items()]}


@router.post("/webhook/github")
async def github_webhook(request: Request) -> dict[str, Any]:
    """Receive a GitHub issue webhook and enqueue an issue task.

    Verifies the HMAC signature when XAGENT_GITHUB_WEBHOOK_SECRET is set.
    Without a configured secret, the endpoint refuses to process (no unsigned
    execution).
    """
    import os
    from backend.app.core.github_integration import verify_signature, parse_issue_event

    secret = os.environ.get("XAGENT_GITHUB_WEBHOOK_SECRET", "")
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not secret or not verify_signature(body, signature, secret):
        raise api_error(
            403,
            ErrorCode.AUTHORIZATION_FAILED,
            "invalid or missing webhook signature",
        )

    import json

    payload = json.loads(body.decode("utf-8"))
    event = parse_issue_event(payload)
    if event is None:
        return {"status": "ignored", "reason": "not an actionable issue event"}

    orch = _get_orchestrator()
    task_id = await orch.submit(
        name=f"github-issue-{event.issue_number}",
        payload={
            "command": f"echo 'received issue #{event.issue_number}: {event.title}'",
            "image": "python:3.11-slim",
            "issue_number": event.issue_number,
            "repo": event.repo_full_name,
        },
    )
    _status[task_id] = "queued"
    return {"status": "queued", "task_id": task_id, "issue": event.issue_number}
