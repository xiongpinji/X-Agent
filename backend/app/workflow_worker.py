from __future__ import annotations

import argparse
import asyncio
from uuid import uuid4

from backend.app.core.audit import AuditStore
from backend.app.core.workflows import WorkflowScheduler, WorkflowScheduleRecord
from backend.app.dependencies import get_audit_store, get_workflow_scheduler


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
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.once:
        asyncio.run(run_once(limit=args.limit, lease_seconds=args.lease_seconds))
        return
    asyncio.run(run_forever(args.interval, args.limit, args.lease_seconds))


if __name__ == "__main__":
    main()
