"""Sandbox orchestration — pulls tasks off the queue and runs each in an
isolated DockerSandbox, Codex-style.

Flow:
    TaskQueue.dequeue() -> SandboxWorker.process() -> DockerSandbox (per task)
        -> prepare workspace -> install deps -> run command/agent -> collect
        -> destroy container -> SandboxRunResult

The orchestrator runs N workers concurrently (each task gets its own
container), so assigning K tasks yields K parallel sandboxed executions —
the key Codex capability X-Agent was missing.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from backend.app.core.sandbox.docker_sandbox import (
    DockerSandbox,
    SandboxResult,
    SandboxSpec,
)
from backend.app.core.task_queue import QueuedTask, TaskPriority, TaskQueue

logger = logging.getLogger(__name__)


@dataclass
class SandboxRunResult:
    """Outcome of running one task through a sandbox."""

    task_id: str
    success: bool
    steps: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    backend: str = "subprocess"

    def add_step(self, name: str, result: SandboxResult) -> None:
        self.steps.append(
            {
                "step": name,
                "success": result.success,
                "exit_code": result.exit_code,
                "stdout": result.stdout[-4000:],  # cap to avoid bloat
                "stderr": result.stderr[-4000:],
                "duration_ms": result.duration_ms,
            }
        )


# A task handler receives the live sandbox + the queued task and drives the work.
# Returning falsy / raising marks the task failed.
TaskHandler = Callable[[DockerSandbox, QueuedTask, "SandboxRunResult"], Any]


class SandboxWorker:
    """Processes a single task inside a freshly provisioned sandbox."""

    def __init__(
        self,
        handler: TaskHandler,
        spec_factory: Callable[[QueuedTask], SandboxSpec] | None = None,
    ):
        self._handler = handler
        self._spec_factory = spec_factory or (lambda task: SandboxSpec())

    async def process(self, task: QueuedTask) -> SandboxRunResult:
        result = SandboxRunResult(task_id=(getattr(task, "task_id", None) or task.id), success=False)
        spec = self._spec_factory(task)
        sandbox = DockerSandbox(spec)
        result.backend = sandbox.backend
        try:
            await sandbox.start()
            outcome = self._handler(sandbox, task, result)
            if asyncio.iscoroutine(outcome):
                outcome = await outcome
            # handler may explicitly return False to signal failure
            result.success = outcome is not False and result.error is None
        except Exception as e:
            logger.exception("Sandbox worker failed for task %s", (getattr(task, "task_id", None) or task.id))
            result.error = str(e)
            result.success = False
        finally:
            await sandbox.stop()
        return result


class SandboxOrchestrator:
    """Runs a pool of workers that drain the task queue concurrently.

    Each dequeued task is handed to a SandboxWorker which provisions its own
    isolated container. Up to `max_concurrent` tasks run in parallel.
    """

    def __init__(
        self,
        queue: TaskQueue,
        handler: TaskHandler,
        max_concurrent: int = 4,
        spec_factory: Callable[[QueuedTask], SandboxSpec] | None = None,
    ):
        self._queue = queue
        self._worker = SandboxWorker(handler, spec_factory)
        self._max_concurrent = max_concurrent
        self._sem = asyncio.Semaphore(max_concurrent)
        self._running = False
        self._tasks: set[asyncio.Task] = set()
        self._results: dict[str, SandboxRunResult] = {}

    @property
    def results(self) -> dict[str, SandboxRunResult]:
        return self._results

    async def submit(
        self,
        name: str,
        payload: dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> str:
        """Enqueue a task for sandboxed execution. Returns the task_id."""
        return await self._queue.enqueue(name=name, payload=payload, priority=priority)

    async def _run_one(self, task: QueuedTask) -> None:
        async with self._sem:
            result = await self._worker.process(task)
            self._results[(getattr(task, "task_id", None) or task.id)] = result

    async def run_until_empty(self, idle_timeout: float = 1.0) -> dict[str, SandboxRunResult]:
        """Drain the queue: dequeue and process every pending task, then return.

        Suitable for batch mode (assign K tasks, await K results). For a
        long-lived service use start()/stop() instead.
        """
        self._running = True
        while self._running:
            task = await self._queue.dequeue(timeout_seconds=int(idle_timeout))
            if task is None:
                break  # queue drained
            t = asyncio.create_task(self._run_one(task))
            self._tasks.add(t)
            t.add_done_callback(self._tasks.discard)
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        return self._results

    async def start(self) -> None:
        """Start a background drain loop (long-lived service mode)."""
        self._running = True
        self._loop_task = asyncio.create_task(self._service_loop())

    async def _service_loop(self) -> None:
        while self._running:
            task = await self._queue.dequeue(timeout_seconds=1)
            if task is None:
                continue
            async with self._sem:
                result = await self._worker.process(task)
                self._results[(getattr(task, "task_id", None) or task.id)] = result

    async def stop(self) -> None:
        """Stop the background loop and wait for in-flight tasks."""
        self._running = False
        loop_task = getattr(self, "_loop_task", None)
        if loop_task:
            loop_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await loop_task
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
