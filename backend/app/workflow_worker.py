from __future__ import annotations

import argparse
import asyncio
import logging
from uuid import uuid4

from backend.app.core.audit import AuditStore
from backend.app.core.workflows import WorkflowScheduler, WorkflowScheduleRecord
from backend.app.dependencies import get_audit_store, get_workflow_scheduler

logger = logging.getLogger(__name__)


async def run_once(
    *,
    scheduler: WorkflowScheduler | None = None,
    audit_store: AuditStore | None = None,
    limit: int = 20,
    worker_id: str = "workflow-worker",
    lease_seconds: int = 60,
) -> list[WorkflowScheduleRecord]:
    scheduler = scheduler or get_workflow_scheduler()
    audit_store = audit_store or get_audit_store()
    records = await scheduler.run_due(
        limit=limit,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
    )
    audit_triggered_records(audit_store, records, worker_id=worker_id)
    return records


async def run_forever(interval_seconds: float, limit: int, lease_seconds: int) -> None:
    worker_id = f"workflow-worker-{uuid4()}"
    while True:
        await run_once(limit=limit, worker_id=worker_id, lease_seconds=lease_seconds)
        await asyncio.sleep(interval_seconds)


def audit_triggered_records(
    audit_store: AuditStore,
    records: list[WorkflowScheduleRecord],
    worker_id: str = "workflow-worker",
) -> None:
    for record in records:
        audit_store.record(
            action="workflow.schedule.worker.trigger",
            resource_type="workflow_schedule",
            resource_id=record.schedule_id,
            outcome=record.status.value,
            tenant_id=record.tenant_id,
            actor_id=worker_id,
            run_id=record.run_id,
            workflow_id=record.workflow_id,
        )


def audit_recovered_runs(
    audit_store: AuditStore,
    records: list,
    worker_id: str = "workflow-worker",
) -> None:
    for record in records:
        audit_store.record(
            action="workflow.run.recovered",
            resource_type="workflow_run",
            resource_id=record.run_id,
            outcome=record.status.value,
            tenant_id=record.tenant_id,
            actor_id=worker_id,
            run_id=record.run_id,
            workflow_id=record.workflow_id,
        )


class WorkflowSchedulerService:
    """In-process scheduler loop with crash recovery on startup.

    Designed to be started with the application (integration-wave wiring,
    see below) or standalone via ``python -m backend.app.workflow_worker``.
    On start it recovers workflow runs left in RUNNING state by a crashed
    process (resuming them from persisted checkpoints by default), then
    polls for due schedules until ``stop`` is called.

    Integration-wave wiring (backend/app/main.py):

        from backend.app.workflow_worker import WorkflowSchedulerService

        # startup_event:
        app.state.workflow_scheduler_service = WorkflowSchedulerService(
            scheduler=get_workflow_scheduler(),
            audit_store=get_audit_store(),
            interval_seconds=5.0,
        )
        await app.state.workflow_scheduler_service.start()

        # shutdown_event:
        await app.state.workflow_scheduler_service.stop()
    """

    def __init__(
        self,
        *,
        scheduler: WorkflowScheduler | None = None,
        audit_store: AuditStore | None = None,
        interval_seconds: float = 5.0,
        limit: int = 20,
        lease_seconds: int = 60,
        worker_id: str | None = None,
        recover_on_start: bool = True,
        resume_interrupted: bool = True,
    ) -> None:
        self._scheduler = scheduler
        self._audit_store = audit_store
        self.interval_seconds = interval_seconds
        self.limit = limit
        self.lease_seconds = lease_seconds
        self.worker_id = worker_id or f"workflow-worker-{uuid4()}"
        self.recover_on_start = recover_on_start
        self.resume_interrupted = resume_interrupted
        self._task: asyncio.Task | None = None
        self._stopping: asyncio.Event | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> "WorkflowSchedulerService":
        """Start the polling loop. Safe to call more than once."""
        if self.running:
            return self
        scheduler = self._scheduler or get_workflow_scheduler()
        audit_store = self._audit_store or get_audit_store()
        if self.recover_on_start:
            recovered = await scheduler.runtime.recover_interrupted_runs(
                resume=self.resume_interrupted,
            )
            if recovered:
                audit_recovered_runs(audit_store, recovered, worker_id=self.worker_id)
                logger.info(
                    "Recovered %d interrupted workflow run(s) on scheduler startup.",
                    len(recovered),
                )
        self._stopping = asyncio.Event()
        self._task = asyncio.create_task(self._loop(scheduler, audit_store))
        return self

    async def stop(self) -> None:
        """Stop the polling loop and wait for the current tick to finish."""
        if self._stopping is not None:
            self._stopping.set()
        task, self._task = self._task, None
        if task is not None:
            try:
                await asyncio.wait_for(task, timeout=self.interval_seconds + 10)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                task.cancel()

    async def _loop(self, scheduler: WorkflowScheduler, audit_store: AuditStore) -> None:
        assert self._stopping is not None
        while not self._stopping.is_set():
            try:
                records = await scheduler.run_due(
                    limit=self.limit,
                    worker_id=self.worker_id,
                    lease_seconds=self.lease_seconds,
                )
                audit_triggered_records(audit_store, records, worker_id=self.worker_id)
            except Exception:  # noqa: BLE001 - a bad tick must not kill the loop
                logger.exception("Workflow scheduler tick failed; continuing next interval.")
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run due X-Agent workflow schedules.")
    parser.add_argument("--once", action="store_true", help="Run due schedules once and exit.")
    parser.add_argument("--interval", type=float, default=5.0, help="Polling interval in seconds.")
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum schedules to trigger per tick.",
    )
    parser.add_argument(
        "--lease-seconds",
        type=int,
        default=60,
        help="Schedule lock lease duration.",
    )
    parser.add_argument(
        "--no-recover",
        action="store_true",
        help="Skip interrupted-run recovery on startup.",
    )
    parser.add_argument(
        "--mark-failed",
        action="store_true",
        help="Mark interrupted runs FAILED on recovery instead of resuming them.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.once:
        asyncio.run(run_once(limit=args.limit, lease_seconds=args.lease_seconds))
        return

    async def _serve() -> None:
        service = WorkflowSchedulerService(
            interval_seconds=args.interval,
            limit=args.limit,
            lease_seconds=args.lease_seconds,
            recover_on_start=not args.no_recover,
            resume_interrupted=not args.mark_failed,
        )
        await service.start()
        try:
            while service.running:
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:  # pragma: no cover - signal path
            pass
        finally:
            await service.stop()

    asyncio.run(_serve())


if __name__ == "__main__":
    main()
