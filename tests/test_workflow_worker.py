from datetime import UTC, datetime

from backend.app.core.audit import AuditStore
from backend.app.core.workflows import WorkflowScheduleRecord, WorkflowScheduleStatus
from backend.app.workflow_worker import audit_triggered_records, build_parser


def test_workflow_worker_audits_triggered_records() -> None:
    audit_store = AuditStore()
    record = WorkflowScheduleRecord(
        workflow_id="workflow-1",
        status=WorkflowScheduleStatus.TRIGGERED,
        run_id="run-1",
        tenant_id="tenant-a",
        run_at=datetime.now(UTC),
    )

    audit_triggered_records(audit_store, [record], worker_id="worker-a")
    logs = audit_store.list(action="workflow.schedule.worker.trigger")

    assert len(logs) == 1
    assert logs[0].resource_id == record.schedule_id
    assert logs[0].run_id == "run-1"
    assert logs[0].actor_id == "worker-a"
    assert logs[0].snapshot["workflow_id"] == record.workflow_id


def test_workflow_worker_parser_supports_once_mode() -> None:
    args = build_parser().parse_args(
        ["--once", "--interval", "1.5", "--limit", "3", "--lease-seconds", "30"]
    )

    assert args.once is True
    assert args.interval == 1.5
    assert args.limit == 3
    assert args.lease_seconds == 30
