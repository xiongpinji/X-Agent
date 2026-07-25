"""
Alembic迁移脚本 - 创建初始表结构
"""
import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    """升级数据库"""
    # 创建users表
    op.create_table(
        'users',
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('role', sa.String(50), nullable=False, server_default='user'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('user_id'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('idx_users_tenant_id', 'users', ['tenant_id'])
    op.create_index('idx_users_email_tenant', 'users', ['email', 'tenant_id'])
    op.create_index('idx_users_created_at', 'users', ['created_at'])

    # 创建api_keys表
    op.create_table(
        'api_keys',
        sa.Column('key_id', sa.String(36), nullable=False),
        sa.Column('key_prefix', sa.String(12), nullable=False),
        sa.Column('key_hash', sa.String(255), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('role', sa.String(50), nullable=False, server_default='developer'),
        sa.Column('scopes', sa.Text(), nullable=False),
        sa.Column('revoked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('key_id'),
        sa.UniqueConstraint('key_hash'),
    )
    op.create_index('idx_api_keys_user_id', 'api_keys', ['user_id'])
    op.create_index('idx_api_keys_tenant_id', 'api_keys', ['tenant_id'])
    op.create_index('idx_api_keys_key_prefix', 'api_keys', ['key_prefix'])
    op.create_index('idx_api_keys_created_at', 'api_keys', ['created_at'])

    # 创建approvals表
    op.create_table(
        'approvals',
        sa.Column('approval_id', sa.String(36), nullable=False),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('request_id', sa.String(36), nullable=False),
        sa.Column('action', sa.String(255), nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=False),
        sa.Column('resource_id', sa.String(255), nullable=False),
        sa.Column('details', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('approved_by', sa.String(36), nullable=True),
        sa.Column('approval_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('approval_id'),
        sa.UniqueConstraint('request_id'),
    )
    op.create_index('idx_approvals_tenant_id', 'approvals', ['tenant_id'])
    op.create_index('idx_approvals_user_id', 'approvals', ['user_id'])
    op.create_index('idx_approvals_status', 'approvals', ['status'])
    op.create_index('idx_approvals_created_at', 'approvals', ['created_at'])

    # 创建rate_limit_logs表
    op.create_table(
        'rate_limit_logs',
        sa.Column('log_id', sa.String(36), nullable=False),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('endpoint', sa.String(255), nullable=False),
        sa.Column('request_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('limit', sa.Integer(), nullable=False),
        sa.Column('window_size_seconds', sa.Integer(), nullable=False),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('window_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('log_id'),
    )
    op.create_index('idx_rate_limit_tenant_user', 'rate_limit_logs', ['tenant_id', 'user_id'])
    op.create_index('idx_rate_limit_endpoint', 'rate_limit_logs', ['endpoint'])
    op.create_index('idx_rate_limit_window', 'rate_limit_logs', ['window_start', 'window_end'])

    # 创建csrf_tokens表
    op.create_table(
        'csrf_tokens',
        sa.Column('token_id', sa.String(36), nullable=False),
        sa.Column('token_hash', sa.String(255), nullable=False),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('session_id', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('token_id'),
        sa.UniqueConstraint('token_hash'),
    )
    op.create_index('idx_csrf_tokens_tenant_id', 'csrf_tokens', ['tenant_id'])
    op.create_index('idx_csrf_tokens_user_id', 'csrf_tokens', ['user_id'])
    op.create_index('idx_csrf_tokens_session_id', 'csrf_tokens', ['session_id'])
    op.create_index('idx_csrf_tokens_expires_at', 'csrf_tokens', ['expires_at'])


def downgrade() -> None:
    """降级数据库"""
    op.drop_table('csrf_tokens')
    op.drop_table('rate_limit_logs')
    op.drop_table('approvals')
    op.drop_table('api_keys')
    op.drop_table('users')
