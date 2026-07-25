"""
订阅管理模型 - PostgreSQL实现
"""
from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models import Base


class SubscriptionStatus(StrEnum):
    """订阅状态"""
    TRIAL = "trial"  # 试用期
    ACTIVE = "active"  # 活跃
    PAUSED = "paused"  # 暂停
    CANCELLED = "cancelled"  # 已取消
    EXPIRED = "expired"  # 已过期


class SubscriptionPlan(StrEnum):
    """订阅计划"""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class SubscriptionModel(Base):
    """订阅模型"""
    __tablename__ = "subscriptions"

    # 主键
    subscription_id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # 关联信息
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # 订阅计划
    plan: Mapped[str] = mapped_column(
        SQLEnum(SubscriptionPlan),
        default=SubscriptionPlan.FREE,
        nullable=False,
        index=True,
    )

    # 订阅状态
    status: Mapped[str] = mapped_column(
        SQLEnum(SubscriptionStatus),
        default=SubscriptionStatus.TRIAL,
        nullable=False,
        index=True,
    )

    # 价格信息
    price_per_month: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)

    # 时间信息
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    current_period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    current_period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    trial_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    paused_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # 自动续费
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    renewal_failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 元数据
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 索引
    __table_args__ = (
        Index("idx_subscriptions_user_id", "user_id"),
        Index("idx_subscriptions_tenant_id", "tenant_id"),
        Index("idx_subscriptions_status", "status"),
        Index("idx_subscriptions_plan", "plan"),
        Index("idx_subscriptions_current_period_end", "current_period_end"),
        Index("idx_subscriptions_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<SubscriptionModel(subscription_id={self.subscription_id}, user_id={self.user_id}, plan={self.plan}, status={self.status})>"


class QuotaModel(Base):
    """配额模型"""
    __tablename__ = "quotas"

    # 主键
    quota_id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # 关联信息
    subscription_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # API调用配额
    api_calls_limit: Mapped[int] = mapped_column(Integer, default=10000, nullable=False)
    api_calls_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Token使用配额
    tokens_limit: Mapped[int] = mapped_column(Integer, default=1000000, nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 存储空间配额（MB）
    storage_limit_mb: Mapped[int] = mapped_column(Integer, default=1024, nullable=False)
    storage_used_mb: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 并发连接配额
    concurrent_connections_limit: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    concurrent_connections_current: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 重置周期
    reset_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

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

    # 索引
    __table_args__ = (
        Index("idx_quotas_subscription_id", "subscription_id"),
        Index("idx_quotas_user_id", "user_id"),
        Index("idx_quotas_tenant_id", "tenant_id"),
        Index("idx_quotas_reset_at", "reset_at"),
    )

    def __repr__(self) -> str:
        return f"<QuotaModel(quota_id={self.quota_id}, subscription_id={self.subscription_id})>"


class SubscriptionHistoryModel(Base):
    """订阅历史模型"""
    __tablename__ = "subscription_history"

    # 主键
    history_id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # 关联信息
    subscription_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # 事件类型
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # created, activated, upgraded, downgraded, paused, resumed, cancelled, renewed, failed_renewal

    # 旧值和新值
    old_plan: Mapped[str | None] = mapped_column(String(50), nullable=True)
    new_plan: Mapped[str | None] = mapped_column(String(50), nullable=True)
    old_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 详情
    details: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON格式

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    # 索引
    __table_args__ = (
        Index("idx_subscription_history_subscription_id", "subscription_id"),
        Index("idx_subscription_history_user_id", "user_id"),
        Index("idx_subscription_history_event_type", "event_type"),
        Index("idx_subscription_history_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<SubscriptionHistoryModel(history_id={self.history_id}, event_type={self.event_type})>"
