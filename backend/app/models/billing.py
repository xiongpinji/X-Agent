"""
计费系统数据模型 - PostgreSQL实现
支持多租户、多种计费模型、支付集成
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, relationship

logger = logging.getLogger(__name__)

Base = declarative_base()


class BillingModel(str, Enum):
    """计费模型"""
    PAY_AS_YOU_GO = "pay_as_you_go"  # 按量计费
    SUBSCRIPTION = "subscription"    # 订阅计费
    HYBRID = "hybrid"                # 混合计费


class SubscriptionStatus(str, Enum):
    """订阅状态"""
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class PaymentStatus(str, Enum):
    """支付状态"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentMethod(str, Enum):
    """支付方式"""
    STRIPE = "stripe"
    ALIPAY = "alipay"
    WECHAT = "wechat"
    BANK_TRANSFER = "bank_transfer"


class InvoiceStatus(str, Enum):
    """发票状态"""
    DRAFT = "draft"
    ISSUED = "issued"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class PricingTier(Base):
    """价格层级表"""
    __tablename__ = "pricing_tiers"
    __table_args__ = (
        Index("idx_pricing_tier_tenant_name", "tenant_id", "tier_name"),
        UniqueConstraint("tenant_id", "tier_name", name="uq_tenant_tier_name"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), nullable=False)
    tier_name = Column(String(50), nullable=False)  # basic, professional, enterprise
    billing_model = Column(SQLEnum(BillingModel), nullable=False)

    # 订阅价格（月度）
    monthly_price = Column(Numeric(10, 2), nullable=True)
    annual_price = Column(Numeric(10, 2), nullable=True)

    # 按量计费价格
    api_call_price = Column(Numeric(10, 6), nullable=True)  # 每次API调用
    token_price = Column(Numeric(10, 8), nullable=True)     # 每个Token
    storage_price = Column(Numeric(10, 6), nullable=True)   # 每GB存储

    # 配额限制
    monthly_api_calls = Column(Integer, nullable=True)
    monthly_tokens = Column(Integer, nullable=True)
    storage_gb = Column(Integer, nullable=True)
    concurrent_users = Column(Integer, nullable=True)

    # 功能开关
    features = Column(JSON, nullable=True)  # {"advanced_analytics": true, ...}

    # 元数据
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class Subscription(Base):
    """订阅表"""
    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("idx_subscription_tenant_user", "tenant_id", "user_id"),
        Index("idx_subscription_status", "status"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), nullable=False)
    user_id = Column(String(36), nullable=False)
    pricing_tier_id = Column(String(36), ForeignKey("pricing_tiers.id"), nullable=False)

    status = Column(SQLEnum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE)
    billing_model = Column(SQLEnum(BillingModel), nullable=False)

    # 订阅周期
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=True)
    renewal_date = Column(DateTime(timezone=True), nullable=True)

    # 支付信息
    payment_method = Column(SQLEnum(PaymentMethod), nullable=False)
    payment_method_id = Column(String(255), nullable=True)  # Stripe ID, Alipay ID等

    # 自动续费
    auto_renew = Column(Boolean, default=True)

    # 折扣
    discount_percent = Column(Numeric(5, 2), default=0)
    discount_reason = Column(String(255), nullable=True)

    # 元数据
    extra_metadata = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class UsageMetrics(Base):
    """使用统计表"""
    __tablename__ = "usage_metrics"
    __table_args__ = (
        Index("idx_usage_tenant_user_date", "tenant_id", "user_id", "date"),
        Index("idx_usage_date", "date"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), nullable=False)
    user_id = Column(String(36), nullable=False)
    subscription_id = Column(String(36), ForeignKey("subscriptions.id"), nullable=True)

    # 使用日期
    date = Column(DateTime(timezone=True), nullable=False)

    # 使用指标
    api_calls = Column(Integer, default=0)
    tokens_used = Column(Integer, default=0)
    storage_used_gb = Column(Numeric(10, 2), default=0)
    concurrent_users = Column(Integer, default=0)

    # 成本计算
    estimated_cost = Column(Numeric(10, 2), default=0)

    # 元数据
    extra_metadata = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class Invoice(Base):
    """发票表"""
    __tablename__ = "invoices"
    __table_args__ = (
        Index("idx_invoice_tenant_user", "tenant_id", "user_id"),
        Index("idx_invoice_status", "status"),
        Index("idx_invoice_date", "issue_date"),
    )

    id = Column(String(36), primary_key=True)
    invoice_number = Column(String(50), unique=True, nullable=False)
    tenant_id = Column(String(36), nullable=False)
    user_id = Column(String(36), nullable=False)
    subscription_id = Column(String(36), ForeignKey("subscriptions.id"), nullable=True)

    # 发票周期
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    issue_date = Column(DateTime(timezone=True), nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=False)

    # 金额
    subtotal = Column(Numeric(10, 2), nullable=False)
    tax = Column(Numeric(10, 2), default=0)
    discount = Column(Numeric(10, 2), default=0)
    total = Column(Numeric(10, 2), nullable=False)

    # 状态
    status = Column(SQLEnum(InvoiceStatus), default=InvoiceStatus.DRAFT)

    # 明细
    line_items = Column(JSON, nullable=True)  # [{description, quantity, unit_price, amount}, ...]

    # 支付信息
    paid_date = Column(DateTime(timezone=True), nullable=True)
    payment_id = Column(String(36), ForeignKey("payments.id"), nullable=True)

    # 元数据
    notes = Column(Text, nullable=True)
    extra_metadata = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class Payment(Base):
    """支付记录表"""
    __tablename__ = "payments"
    __table_args__ = (
        Index("idx_payment_tenant_user", "tenant_id", "user_id"),
        Index("idx_payment_status", "status"),
        Index("idx_payment_date", "payment_date"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), nullable=False)
    user_id = Column(String(36), nullable=False)
    subscription_id = Column(String(36), ForeignKey("subscriptions.id"), nullable=True)

    # 支付方式
    payment_method = Column(SQLEnum(PaymentMethod), nullable=False)
    payment_method_id = Column(String(255), nullable=True)  # 第三方支付ID

    # 金额
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="USD")

    # 状态
    status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING)

    # 时间
    payment_date = Column(DateTime(timezone=True), nullable=True)
    refund_date = Column(DateTime(timezone=True), nullable=True)

    # 交易信息
    transaction_id = Column(String(255), nullable=True)
    reference_id = Column(String(255), nullable=True)

    # 元数据
    extra_metadata = Column("metadata", JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class QuotaUsage(Base):
    """配额使用表"""
    __tablename__ = "quota_usage"
    __table_args__ = (
        Index("idx_quota_tenant_user", "tenant_id", "user_id"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), nullable=False)
    user_id = Column(String(36), nullable=False)
    subscription_id = Column(String(36), ForeignKey("subscriptions.id"), nullable=False)

    # 当前周期
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)

    # 配额使用
    api_calls_used = Column(Integer, default=0)
    api_calls_limit = Column(Integer, nullable=True)

    tokens_used = Column(Integer, default=0)
    tokens_limit = Column(Integer, nullable=True)

    storage_used_gb = Column(Numeric(10, 2), default=0)
    storage_limit_gb = Column(Integer, nullable=True)

    # 警告标志
    api_calls_warning = Column(Boolean, default=False)
    tokens_warning = Column(Boolean, default=False)
    storage_warning = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class PromotionCode(Base):
    """促销代码表"""
    __tablename__ = "promotion_codes"
    __table_args__ = (
        Index("idx_promo_code", "code"),
        Index("idx_promo_status", "is_active"),
    )

    id = Column(String(36), primary_key=True)
    code = Column(String(50), unique=True, nullable=False)

    # 折扣信息
    discount_type = Column(String(20), nullable=False)  # percentage, fixed_amount
    discount_value = Column(Numeric(10, 2), nullable=False)

    # 使用限制
    max_uses = Column(Integer, nullable=True)
    current_uses = Column(Integer, default=0)

    # 有效期
    valid_from = Column(DateTime(timezone=True), nullable=False)
    valid_until = Column(DateTime(timezone=True), nullable=False)

    # 适用范围
    applicable_tiers = Column(JSON, nullable=True)  # ["basic", "professional"]
    min_amount = Column(Numeric(10, 2), nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class BillingHistory(Base):
    """计费历史表（审计日志）"""
    __tablename__ = "billing_history"
    __table_args__ = (
        Index("idx_billing_history_tenant_user", "tenant_id", "user_id"),
        Index("idx_billing_history_date", "created_at"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), nullable=False)
    user_id = Column(String(36), nullable=False)

    # 事件类型
    event_type = Column(String(50), nullable=False)  # subscription_created, payment_received, invoice_issued等

    # 相关资源
    subscription_id = Column(String(36), nullable=True)
    invoice_id = Column(String(36), nullable=True)
    payment_id = Column(String(36), nullable=True)

    # 事件详情
    details = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
