"""
SQLAlchemy ORM模型 - 用户存储
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy基类"""
    pass


class UserStoreModel(Base):
    """用户存储模型"""
    __tablename__ = "users"

    # 主键
    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # 基本信息
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # 租户信息
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # 角色和权限
    role: Mapped[str] = mapped_column(String(50), default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # 元数据
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 索引
    __table_args__ = (
        Index("idx_users_tenant_id", "tenant_id"),
        Index("idx_users_email_tenant", "email", "tenant_id"),
        Index("idx_users_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<UserStoreModel(user_id={self.user_id}, email={self.email})>"


class APIKeyStoreModel(Base):
    """API密钥存储模型"""
    __tablename__ = "api_keys"

    # 主键
    key_id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # 密钥信息
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # 关联信息
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # 元数据
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="developer", nullable=False)
    scopes: Mapped[str] = mapped_column(Text, nullable=False)  # JSON格式

    # 状态
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # 索引
    __table_args__ = (
        Index("idx_api_keys_user_id", "user_id"),
        Index("idx_api_keys_tenant_id", "tenant_id"),
        Index("idx_api_keys_key_prefix", "key_prefix"),
        Index("idx_api_keys_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<APIKeyStoreModel(key_id={self.key_id}, key_prefix={self.key_prefix})>"


class ApprovalStoreModel(Base):
    """审批存储模型"""
    __tablename__ = "approvals"

    # 主键
    approval_id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # 关联信息
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)

    # 审批内容
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False)  # JSON格式

    # 审批状态
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        index=True,
    )  # pending, approved, rejected
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approval_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # 索引
    __table_args__ = (
        Index("idx_approvals_tenant_id", "tenant_id"),
        Index("idx_approvals_user_id", "user_id"),
        Index("idx_approvals_status", "status"),
        Index("idx_approvals_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ApprovalStoreModel(approval_id={self.approval_id}, status={self.status})>"


class RateLimitLogModel(Base):
    """速率限制日志模型"""
    __tablename__ = "rate_limit_logs"

    # 主键
    log_id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # 限制信息
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # 计数
    request_count: Mapped[int] = mapped_column(default=0, nullable=False)
    limit: Mapped[int] = mapped_column(nullable=False)
    window_size_seconds: Mapped[int] = mapped_column(nullable=False)

    # 时间戳
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # 索引
    __table_args__ = (
        Index("idx_rate_limit_tenant_user", "tenant_id", "user_id"),
        Index("idx_rate_limit_endpoint", "endpoint"),
        Index("idx_rate_limit_window", "window_start", "window_end"),
    )

    def __repr__(self) -> str:
        return f"<RateLimitLogModel(log_id={self.log_id}, endpoint={self.endpoint})>"


class CSRFTokenModel(Base):
    """CSRF令牌存储模型"""
    __tablename__ = "csrf_tokens"

    # 主键
    token_id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # 令牌信息
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # 关联信息
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # 索引
    __table_args__ = (
        Index("idx_csrf_tokens_tenant_id", "tenant_id"),
        Index("idx_csrf_tokens_user_id", "user_id"),
        Index("idx_csrf_tokens_session_id", "session_id"),
        Index("idx_csrf_tokens_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<CSRFTokenModel(token_id={self.token_id})>"
