"""Initial schema: users, api_keys, approvals, rate_limits, csrf_tokens.

Revision ID: 001_initial
Revises: None
Create Date: 2026-07-30
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Users
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(128), unique=True, nullable=False),
        sa.Column("email", sa.String(256), unique=True, nullable=True),
        sa.Column("hashed_password", sa.String(256), nullable=False),
        sa.Column("role", sa.String(32), server_default="user"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    # API Keys
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("key_hash", sa.String(128), unique=True, nullable=False),
        sa.Column("key_prefix", sa.String(16), nullable=False),
        sa.Column("name", sa.String(128), nullable=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_api_keys_prefix", "api_keys", ["key_prefix"])

    # Approvals
    op.create_table(
        "approvals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tool_name", sa.String(128), nullable=False),
        sa.Column("risk_level", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("arguments_json", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.String(36), nullable=True),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_approvals_status", "approvals", ["status"])

    # Rate Limit Logs
    op.create_table(
        "rate_limit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("client_ip", sa.String(64), nullable=False),
        sa.Column("endpoint", sa.String(256), nullable=True),
        sa.Column("blocked", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_rate_limit_logs_ip", "rate_limit_logs", ["client_ip"])

    # CSRF Tokens
    op.create_table(
        "csrf_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("token_hash", sa.String(128), unique=True, nullable=False),
        sa.Column("session_id", sa.String(128), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("csrf_tokens")
    op.drop_table("rate_limit_logs")
    op.drop_table("approvals")
    op.drop_table("api_keys")
    op.drop_table("users")
