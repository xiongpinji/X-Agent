from __future__ import annotations

import os
import subprocess
import sys

from backend.app.core.audit import AuditEventConflictError
from backend.app.core.audit_sql import SqlAuditStore
from backend.app.core.contracts import AgentRunResponse, RunContext, RunStatus
from backend.app.core.runs_sql import SqlRunStore


def test_billing_import_can_initialize_postgres_admin_store(tmp_path) -> None:
    env = os.environ.copy()
    env.update(
        {
            "XAGENT_APP_MODE": "development",
            "XAGENT_ADMIN_STORE_BACKEND": "postgres",
            "XAGENT_DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'admin.db'}",
        }
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import backend.app.core.billing.reservations; "
                "from backend.app.core.admin import user_store; "
                "assert type(user_store).__name__ == 'SqlUserStore'"
            ),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_sql_run_store_survives_restart(tmp_path) -> None:
    url = f"sqlite:///{tmp_path / 'runs.db'}"
    context = RunContext(
        trace_id="trace-commercial",
        tenant_id="tenant-a",
        user_id="user-a",
        agent_id="agent-a",
    )
    response = AgentRunResponse(
        trace_id=context.trace_id,
        agent_id=context.agent_id,
        status=RunStatus.COMPLETED,
        answer="durable answer",
        iterations=1,
        memory_hits=0,
    )

    SqlRunStore(url, create_schema=True).save(context, "durable task", response)
    reloaded = SqlRunStore(url, create_schema=False)

    assert reloaded.count() == 1
    assert reloaded.get(context.trace_id).answer == "durable answer"
    assert reloaded.list(limit=1)[0].tenant_id == "tenant-a"


def test_sql_audit_store_is_durable_idempotent_and_signed(tmp_path) -> None:
    url = f"sqlite:///{tmp_path / 'audit.db'}"
    first = SqlAuditStore(url, hmac_secret="commercial-audit-secret", create_schema=True)
    record = first.record(
        event_id="audit-event-1",
        tenant_id="tenant-a",
        actor_id="user-a",
        action="run.completed",
        resource_type="run",
        resource_id="trace-commercial",
    )

    reloaded = SqlAuditStore(url, hmac_secret="commercial-audit-secret", create_schema=False)
    replay = reloaded.record(
        event_id="audit-event-1",
        tenant_id="tenant-a",
        actor_id="user-a",
        action="run.completed",
        resource_type="run",
        resource_id="trace-commercial",
    )
    reloaded.record(
        event_id="audit-event-2",
        tenant_id="tenant-a",
        actor_id="user-a",
        action="artifact.created",
        resource_type="artifact",
    )

    assert replay.id == record.id
    assert reloaded.count() == 2
    assert reloaded.verify_chain().valid is True
    assert reloaded.verify_chain().signed == 2

    try:
        reloaded.record(
            event_id="audit-event-1",
            tenant_id="tenant-a",
            actor_id="user-a",
            action="different",
            resource_type="run",
            resource_id="trace-commercial",
        )
    except AuditEventConflictError:
        pass
    else:
        raise AssertionError("conflicting audit replay must fail closed")
