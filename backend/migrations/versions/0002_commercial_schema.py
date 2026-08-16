"""Install the durable schema used by the commercial runtime.

Revision ID: 0002_commercial_schema
Revises: 0001_initial
Create Date: 2026-08-16

The first migration predates the current workflow and audit stores.  On a
fresh install those legacy tables are empty, so this migration replaces them
with the current contracts.  A non-empty incompatible table fails closed: an
operator must migrate the data explicitly instead of losing it implicitly.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_commercial_schema"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _replace_incompatible_empty_table(name: str, required_columns: set[str]) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if name not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns(name)}
    if required_columns.issubset(columns):
        return
    row_count = bind.execute(sa.text(f'SELECT COUNT(*) FROM "{name}"')).scalar_one()
    if row_count:
        raise RuntimeError(
            f"incompatible non-empty table {name!r}; migrate its data before upgrade"
        )
    op.drop_table(name)


def _table_exists(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    # 0001 used incompatible workflow and audit contracts. Drop only when empty.
    _replace_incompatible_empty_table(
        "workflow_runs",
        {"run_id", "workflow_id", "tenant_id", "user_id", "resume_cursor", "doc"},
    )
    _replace_incompatible_empty_table(
        "workflow_definitions",
        {"id", "name", "description", "created_at", "updated_at", "doc"},
    )
    _replace_incompatible_empty_table(
        "audit_logs",
        {"id", "tenant_id", "actor_id", "actor_type", "outcome", "hash"},
    )

    if not _table_exists("admin_tenants"):
        op.create_table(
            "admin_tenants",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("plan", sa.String(50), nullable=False, server_default="free"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("idx_admin_tenants_updated_at", "admin_tenants", ["updated_at"])

    if not _table_exists("admin_users"):
        op.create_table(
            "admin_users",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("display_name", sa.String(255), nullable=False, server_default="User"),
            sa.Column("role", sa.String(50), nullable=False, server_default="developer"),
            sa.Column("tenant_id", sa.String(36), nullable=False, server_default="default"),
            sa.Column("password_hash", sa.String(255)),
            sa.Column("password_history_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("locked_until", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("email", "tenant_id", name="uq_admin_users_email_tenant"),
        )
        op.create_index("idx_admin_users_email", "admin_users", ["email"])
        op.create_index("idx_admin_users_tenant_id", "admin_users", ["tenant_id"])
        op.create_index("idx_admin_users_updated_at", "admin_users", ["updated_at"])

    if not _table_exists("rbac_roles"):
        op.create_table(
            "rbac_roles",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("permissions", postgresql.JSONB(), nullable=False, server_default="[]"),
            sa.Column("parent_roles", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
            sa.Column("tenant_id", sa.String(128), nullable=False, server_default="default"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("name", "tenant_id", name="uq_rbac_roles_name_tenant"),
        )
        op.create_index("idx_rbac_roles_tenant_id", "rbac_roles", ["tenant_id"])

    if not _table_exists("rbac_user_roles"):
        op.create_table(
            "rbac_user_roles",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("user_id", sa.String(128), nullable=False),
            sa.Column("role_id", sa.String(64), sa.ForeignKey("rbac_roles.id", ondelete="CASCADE"), nullable=False),
            sa.Column("assigned_by", sa.String(128), nullable=False, server_default="system"),
            sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("expires_at", sa.DateTime(timezone=True)),
            sa.Column("delegated_to", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
            sa.Column("scope", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("tenant_id", sa.String(128), nullable=False, server_default="default"),
            sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("granted_by", sa.String(128), nullable=False, server_default="system"),
            sa.UniqueConstraint(
                "user_id", "role_id", "tenant_id", name="uq_rbac_user_roles_user_role_tenant"
            ),
        )
        op.create_index("idx_rbac_user_roles_user_id", "rbac_user_roles", ["user_id"])
        op.create_index("idx_rbac_user_roles_role_id", "rbac_user_roles", ["role_id"])
        op.create_index("idx_rbac_user_roles_tenant_id", "rbac_user_roles", ["tenant_id"])

    if not _table_exists("rbac_audit_log"):
        op.create_table(
            "rbac_audit_log",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("user_id", sa.String(128), nullable=False),
            sa.Column("action", sa.String(64), nullable=False),
            sa.Column("resource_type", sa.String(64), nullable=False),
            sa.Column("resource_id", sa.String(128), nullable=False),
            sa.Column("result", sa.String(32), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False, server_default=""),
            sa.Column("attributes", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("ip_address", sa.String(45)),
            sa.Column("user_agent", sa.Text()),
        )
        op.create_index("idx_rbac_audit_log_user_id", "rbac_audit_log", ["user_id"])
        op.create_index("idx_rbac_audit_log_timestamp", "rbac_audit_log", ["timestamp"])

    if not _table_exists("workflow_definitions"):
        op.create_table(
            "workflow_definitions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("doc", postgresql.JSONB(), nullable=False),
        )
        op.create_index("idx_workflow_definitions_updated", "workflow_definitions", ["updated_at"])

    if not _table_exists("workflow_runs"):
        op.create_table(
            "workflow_runs",
            sa.Column("run_id", sa.String(36), primary_key=True),
            sa.Column("workflow_id", sa.String(36), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("tenant_id", sa.String(64), nullable=False),
            sa.Column("user_id", sa.String(64), nullable=False, server_default="anonymous"),
            sa.Column("resume_cursor", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("worker_id", sa.String(128)),
            sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True)),
            sa.Column("doc", postgresql.JSONB(), nullable=False),
        )
        op.create_index(
            "idx_workflow_runs_workflow_started", "workflow_runs", ["workflow_id", "started_at"]
        )
        op.create_index("idx_workflow_runs_status", "workflow_runs", ["status"])
        op.create_index("idx_workflow_runs_tenant", "workflow_runs", ["tenant_id"])

    if not _table_exists("workflow_schedules"):
        op.create_table(
            "workflow_schedules",
            sa.Column("schedule_id", sa.String(36), primary_key=True),
            sa.Column("workflow_id", sa.String(36), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("tenant_id", sa.String(64), nullable=False),
            sa.Column("user_id", sa.String(64), nullable=False, server_default="anonymous"),
            sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("cron", sa.String(128)),
            sa.Column("run_id", sa.String(36)),
            sa.Column("locked_by", sa.String(128)),
            sa.Column("locked_until", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("doc", postgresql.JSONB(), nullable=False),
        )
        op.create_index("idx_workflow_schedules_due", "workflow_schedules", ["status", "run_at"])
        op.create_index("idx_workflow_schedules_tenant", "workflow_schedules", ["tenant_id"])
        op.create_index("idx_workflow_schedules_workflow", "workflow_schedules", ["workflow_id"])

    if not _table_exists("chat_sessions"):
        op.create_table(
            "chat_sessions",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("tenant_id", sa.String(64), nullable=False),
            sa.Column("user_id", sa.String(64), nullable=False),
            sa.Column("title", sa.String(255), nullable=False, server_default=""),
            sa.Column("agent_id", sa.String(64), nullable=False, server_default="default"),
            sa.Column("created_at", sa.Float(), nullable=False),
            sa.Column("updated_at", sa.Float(), nullable=False),
            sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        )
        op.create_index(
            "idx_chat_sessions_principal_updated",
            "chat_sessions",
            ["tenant_id", "user_id", "updated_at"],
        )

    if not _table_exists("chat_messages"):
        op.create_table(
            "chat_messages",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column(
                "session_id",
                sa.String(64),
                sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("tenant_id", sa.String(64), nullable=False),
            sa.Column("user_id", sa.String(64), nullable=False),
            sa.Column("role", sa.String(20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("timestamp", sa.Float(), nullable=False),
            sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        )
        op.create_index(
            "idx_chat_messages_principal_session_time",
            "chat_messages",
            ["tenant_id", "user_id", "session_id", "timestamp"],
        )

    if not _table_exists("usage_reservations"):
        op.create_table(
            "usage_reservations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(64), nullable=False),
            sa.Column("operation_id", sa.String(255), nullable=False),
            sa.Column("root_operation_id", sa.String(255), nullable=False),
            sa.Column("user_id", sa.String(64)),
            sa.Column("provider", sa.String(64), nullable=False),
            sa.Column("model", sa.String(128), nullable=False),
            sa.Column("request_hash", sa.String(64), nullable=False),
            sa.Column("estimated_cost", sa.Numeric(18, 8), nullable=False),
            sa.Column("actual_cost", sa.Numeric(18, 8)),
            sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("run_id", sa.String(128)),
            sa.Column("trace_id", sa.String(128)),
            sa.Column("created_at", sa.Float(), nullable=False),
            sa.Column("updated_at", sa.Float(), nullable=False),
            sa.CheckConstraint(
                "status IN ('reserved', 'confirmed', 'refunded', 'submission_unknown')",
                name="ck_usage_reservation_status",
            ),
            sa.UniqueConstraint(
                "tenant_id", "operation_id", name="uq_usage_reservation_operation"
            ),
        )
        op.create_index(
            "idx_usage_reservations_root",
            "usage_reservations",
            ["tenant_id", "root_operation_id"],
        )
        op.create_index(
            "idx_usage_reservations_month",
            "usage_reservations",
            ["tenant_id", "updated_at"],
        )

    if not _table_exists("usage_reservation_ledger"):
        op.create_table(
            "usage_reservation_ledger",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "reservation_id",
                sa.String(36),
                sa.ForeignKey("usage_reservations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("tenant_id", sa.String(64), nullable=False),
            sa.Column("operation_id", sa.String(255), nullable=False),
            sa.Column("from_status", sa.String(32), nullable=False),
            sa.Column("to_status", sa.String(32), nullable=False),
            sa.Column("actual_cost", sa.Numeric(18, 8)),
            sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.Float(), nullable=False),
            sa.CheckConstraint(
                "to_status IN ('confirmed', 'refunded', 'submission_unknown')",
                name="ck_usage_ledger_to_status",
            ),
            sa.UniqueConstraint("reservation_id", name="uq_usage_ledger_terminal_transition"),
        )
        op.create_index(
            "idx_usage_ledger_operation",
            "usage_reservation_ledger",
            ["tenant_id", "operation_id", "created_at"],
        )

    if not _table_exists("usage_reservation_audit_outbox"):
        op.create_table(
            "usage_reservation_audit_outbox",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(64), nullable=False),
            sa.Column("operation_id", sa.String(255), nullable=False),
            sa.Column("action", sa.String(64), nullable=False),
            sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
            sa.Column("audit_id", sa.String(64)),
            sa.Column("delivery_token", sa.String(64)),
            sa.Column("lease_expires_at", sa.Float()),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_error", sa.String(128)),
            sa.Column("payload", postgresql.JSONB(), nullable=False),
            sa.Column("created_at", sa.Float(), nullable=False),
            sa.Column("updated_at", sa.Float(), nullable=False),
            sa.CheckConstraint(
                "status IN ('pending', 'delivering', 'delivered')",
                name="ck_usage_audit_outbox_status",
            ),
        )
        op.create_index(
            "idx_usage_audit_outbox_pending",
            "usage_reservation_audit_outbox",
            ["status", "created_at"],
        )
        op.create_index(
            "idx_usage_audit_outbox_operation",
            "usage_reservation_audit_outbox",
            ["tenant_id", "operation_id"],
        )

    if not _table_exists("feedback"):
        op.create_table(
            "feedback",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(255), nullable=False),
            sa.Column("tenant_id", sa.String(255), nullable=False),
            sa.Column("feedback_type", sa.String(50), nullable=False),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("severity", sa.String(50), nullable=False),
            sa.Column("status", sa.String(50), nullable=False, server_default="new"),
            sa.Column("sentiment", sa.String(50)),
            sa.Column("sentiment_score", sa.Float()),
            sa.Column("priority_score", sa.Float()),
            sa.Column("category", sa.String(255)),
            sa.Column("tags", postgresql.JSONB()),
            sa.Column("metadata", postgresql.JSONB()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("resolved_at", sa.DateTime(timezone=True)),
        )
        op.create_index("idx_feedback_user_tenant", "feedback", ["user_id", "tenant_id"])
        op.create_index("idx_feedback_status_created", "feedback", ["status", "created_at"])
        op.create_index(
            "idx_feedback_severity_priority", "feedback", ["severity", "priority_score"]
        )

    if not _table_exists("feedback_analysis"):
        op.create_table(
            "feedback_analysis",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("feedback_id", sa.String(36), nullable=False),
            sa.Column("sentiment_score", sa.Float(), nullable=False),
            sa.Column("sentiment_type", sa.String(50), nullable=False),
            sa.Column("category", sa.String(255), nullable=False),
            sa.Column("subcategory", sa.String(255)),
            sa.Column("tags", postgresql.JSONB(), nullable=False),
            sa.Column("priority_score", sa.Float(), nullable=False),
            sa.Column("urgency_score", sa.Float(), nullable=False),
            sa.Column("impact_score", sa.Float(), nullable=False),
            sa.Column("keywords", postgresql.JSONB()),
            sa.Column("entities", postgresql.JSONB()),
            sa.Column("analysis_metadata", postgresql.JSONB()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("idx_analysis_feedback", "feedback_analysis", ["feedback_id"])
        op.create_index("idx_analysis_category", "feedback_analysis", ["category"])

    if not _table_exists("audit_logs"):
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(255), nullable=False),
            sa.Column("actor_id", sa.String(255), nullable=False),
            sa.Column("actor_type", sa.String(50), nullable=False),
            sa.Column("action", sa.String(100), nullable=False),
            sa.Column("resource_type", sa.String(100), nullable=False),
            sa.Column("resource_id", sa.String(255)),
            sa.Column("outcome", sa.String(50), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("trace_id", sa.String(255)),
            sa.Column("run_id", sa.String(255)),
            sa.Column("workflow_id", sa.String(255)),
            sa.Column("session_id", sa.String(255)),
            sa.Column("details", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("changes", postgresql.JSONB(), nullable=False, server_default="[]"),
            sa.Column("snapshot_before", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("snapshot_after", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("ip_address", sa.String(45)),
            sa.Column("user_agent", sa.Text()),
            sa.Column("prev_hash", sa.String(64)),
            sa.Column("hash", sa.String(64), nullable=False),
            sa.Column("signature", sa.String(128)),
            sa.Column("audit_level", sa.String(50), nullable=False, server_default="standard"),
            sa.Column("tags", postgresql.JSONB(), nullable=False, server_default="[]"),
            sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("archive_timestamp", sa.DateTime(timezone=True)),
        )
        op.create_index("idx_tenant_created", "audit_logs", ["tenant_id", "created_at"])
        op.create_index("idx_actor_created", "audit_logs", ["actor_id", "created_at"])
        op.create_index("idx_action_outcome", "audit_logs", ["action", "outcome"])
        op.create_index("idx_resource_type_id", "audit_logs", ["resource_type", "resource_id"])
        op.create_index(
            "idx_trace_run_workflow", "audit_logs", ["trace_id", "run_id", "workflow_id"]
        )

    if not _table_exists("audit_logs_archive"):
        op.create_table(
            "audit_logs_archive",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(255), nullable=False),
            sa.Column("actor_id", sa.String(255), nullable=False),
            sa.Column("action", sa.String(100), nullable=False),
            sa.Column("resource_type", sa.String(100), nullable=False),
            sa.Column("resource_id", sa.String(255)),
            sa.Column("outcome", sa.String(50), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("record_data", postgresql.JSONB(), nullable=False),
        )
        op.create_index(
            "idx_archive_tenant_created", "audit_logs_archive", ["tenant_id", "created_at"]
        )
        op.create_index("idx_archive_archived_at", "audit_logs_archive", ["archived_at"])

    if not _table_exists("audit_log_signatures"):
        op.create_table(
            "audit_log_signatures",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("audit_log_id", sa.String(36), nullable=False),
            sa.Column("signature", sa.String(128), nullable=False),
            sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("signer_id", sa.String(255)),
            sa.Column("certificate_id", sa.String(255)),
        )
        op.create_index(
            "ix_audit_log_signatures_audit_log_id", "audit_log_signatures", ["audit_log_id"]
        )

    if not _table_exists("memories"):
        op.create_table(
            "memories",
            sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
            sa.Column("tenant_id", sa.Text(), nullable=False),
            sa.Column("agent_id", sa.Text()),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("layer", sa.Integer(), nullable=False),
            sa.Column("importance", sa.Float(), nullable=False),
            sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
            sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint("layer BETWEEN 1 AND 10", name="ck_memories_layer"),
            sa.CheckConstraint(
                "importance >= 0 AND importance <= 1", name="ck_memories_importance"
            ),
        )
        op.create_index(
            "idx_memories_tenant_layer_created",
            "memories",
            ["tenant_id", "layer", "created_at"],
        )

    if not _table_exists("trace_events"):
        op.create_table(
            "trace_events",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("trace_id", sa.String(128), nullable=False),
            sa.Column("request_id", sa.String(128)),
            sa.Column("agent_id", sa.String(128)),
            sa.Column("tenant_id", sa.String(64)),
            sa.Column("user_id", sa.String(64)),
            sa.Column("event", sa.Text(), nullable=False),
            sa.Column("data", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index(
            "idx_trace_events_trace_time", "trace_events", ["trace_id", "timestamp", "id"]
        )
        op.create_index(
            "idx_trace_events_event_time", "trace_events", ["event", "timestamp"]
        )
        op.create_index(
            "idx_trace_events_tenant_time", "trace_events", ["tenant_id", "timestamp"]
        )

    if not _table_exists("agent_run_records"):
        op.create_table(
            "agent_run_records",
            sa.Column("trace_id", sa.String(128), primary_key=True),
            sa.Column("tenant_id", sa.String(64), nullable=False),
            sa.Column("user_id", sa.String(64), nullable=False),
            sa.Column("agent_id", sa.String(128), nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("task", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("doc", postgresql.JSONB(), nullable=False),
        )
        op.create_index(
            "idx_agent_run_records_tenant_completed",
            "agent_run_records",
            ["tenant_id", "completed_at"],
        )
        op.create_index("ix_agent_run_records_user_id", "agent_run_records", ["user_id"])
        op.create_index("ix_agent_run_records_status", "agent_run_records", ["status"])

    if not _table_exists("commercial_audit_events"):
        op.create_table(
            "commercial_audit_events",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("tenant_id", sa.String(64), nullable=False),
            sa.Column("actor_id", sa.String(128), nullable=False),
            sa.Column("action", sa.String(128), nullable=False),
            sa.Column("resource_type", sa.String(128), nullable=False),
            sa.Column("resource_id", sa.String(255)),
            sa.Column("outcome", sa.String(32), nullable=False),
            sa.Column("trace_id", sa.String(128)),
            sa.Column("run_id", sa.String(128)),
            sa.Column("workflow_id", sa.String(128)),
            sa.Column("details", postgresql.JSONB(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("prev_hash", sa.String(64)),
            sa.Column("hash", sa.String(64), nullable=False),
            sa.Column("signature", sa.String(64), nullable=False),
            sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        )
        op.create_index(
            "idx_commercial_audit_tenant_created",
            "commercial_audit_events",
            ["tenant_id", "created_at"],
        )
        for name in ("actor_id", "action", "resource_type", "outcome"):
            op.create_index(
                f"ix_commercial_audit_events_{name}", "commercial_audit_events", [name]
            )


def downgrade() -> None:
    raise RuntimeError(
        "commercial schema downgrade is destructive; restore a verified pre-migration backup instead"
    )
