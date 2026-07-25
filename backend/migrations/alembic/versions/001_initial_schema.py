"""Initial schema - memories, trace_events, RBAC, and workflow tables.

Revision ID: 001
Revises:
Create Date: 2026-07-25

Based on backend/migrations/init_schema.sql and workflow_store_schema.sql.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable pg_trgm extension for trigram indexes
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # --- memories table ---
    op.create_table(
        'memories',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', sa.Text(), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('layer', sa.Integer(), nullable=False),
        sa.Column('importance', sa.Float(), nullable=False),
        sa.Column('tags', postgresql.ARRAY(sa.Text()), nullable=False, server_default='{}'),
        sa.Column('metadata', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('layer BETWEEN 1 AND 10', name='ck_memories_layer'),
        sa.CheckConstraint('importance >= 0 AND importance <= 1', name='ck_memories_importance'),
    )
    op.create_index(
        'idx_memories_tenant_layer_created', 'memories',
        ['tenant_id', 'layer', sa.text('created_at DESC')],
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_memories_content_trgm "
        "ON memories USING gin (content gin_trgm_ops)"
    )

    # --- trace_events table ---
    op.create_table(
        'trace_events',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('trace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event', sa.Text(), nullable=False),
        sa.Column('data', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        'idx_trace_events_trace_time', 'trace_events',
        ['trace_id', sa.text('timestamp ASC'), sa.text('id ASC')],
    )
    op.create_index(
        'idx_trace_events_event_time', 'trace_events',
        ['event', sa.text('timestamp DESC')],
    )

    # --- RBAC tables ---
    op.create_table(
        'rbac_roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.Text(), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('permissions', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('parent_roles', postgresql.ARRAY(sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'rbac_user_roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('role_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('rbac_roles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assigned_by', sa.Text(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delegated_to', postgresql.ARRAY(sa.Text()), nullable=False, server_default='{}'),
        sa.Column('scope', postgresql.JSONB(), nullable=False, server_default='{}'),
    )
    op.create_index('idx_rbac_user_roles_user', 'rbac_user_roles', ['user_id'])

    op.create_table(
        'rbac_audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('resource_type', sa.Text(), nullable=False),
        sa.Column('resource_id', sa.Text(), nullable=False),
        sa.Column('result', sa.Text(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False, server_default=''),
        sa.Column('attributes', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('ip_address', sa.Text(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
    )
    op.create_index(
        'idx_rbac_audit_user_time', 'rbac_audit_logs',
        ['user_id', sa.text('timestamp DESC')],
    )

    # --- Workflow tables (from workflow_store_schema.sql) ---
    op.create_table(
        'workflow_definitions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('doc', postgresql.JSONB(), nullable=False),
    )
    op.create_index(
        'idx_workflow_definitions_updated', 'workflow_definitions',
        [sa.text('updated_at DESC')],
    )

    op.create_table(
        'workflow_runs',
        sa.Column('run_id', sa.String(36), primary_key=True),
        sa.Column('workflow_id', sa.String(36), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('tenant_id', sa.String(64), nullable=False),
        sa.Column('user_id', sa.String(64), nullable=False, server_default='anonymous'),
        sa.Column('resume_cursor', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('worker_id', sa.String(128), nullable=True),
        sa.Column('heartbeat_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('doc', postgresql.JSONB(), nullable=False),
    )
    op.create_index(
        'idx_workflow_runs_workflow_started', 'workflow_runs',
        ['workflow_id', sa.text('started_at DESC')],
    )
    op.create_index('idx_workflow_runs_status', 'workflow_runs', ['status'])
    op.create_index('idx_workflow_runs_tenant', 'workflow_runs', ['tenant_id'])

    op.create_table(
        'workflow_schedules',
        sa.Column('schedule_id', sa.String(36), primary_key=True),
        sa.Column('workflow_id', sa.String(36), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('tenant_id', sa.String(64), nullable=False),
        sa.Column('user_id', sa.String(64), nullable=False, server_default='anonymous'),
        sa.Column('run_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('cron', sa.String(128), nullable=True),
        sa.Column('run_id', sa.String(36), nullable=True),
        sa.Column('locked_by', sa.String(128), nullable=True),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('doc', postgresql.JSONB(), nullable=False),
    )
    op.create_index('idx_workflow_schedules_due', 'workflow_schedules', ['status', 'run_at'])
    op.create_index('idx_workflow_schedules_tenant', 'workflow_schedules', ['tenant_id'])
    op.create_index('idx_workflow_schedules_workflow', 'workflow_schedules', ['workflow_id'])


def downgrade() -> None:
    op.drop_table('workflow_schedules')
    op.drop_table('workflow_runs')
    op.drop_table('workflow_definitions')
    op.drop_table('rbac_audit_logs')
    op.drop_table('rbac_user_roles')
    op.drop_table('rbac_roles')
    op.drop_table('trace_events')
    op.drop_table('memories')
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
