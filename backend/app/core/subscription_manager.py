"""
订阅管理系统 - 完整的订阅生命周期管理
支持订阅创建、激活、暂停、取消、升级、降级、续费等操作
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.billing import (
    BillingModel,
    Invoice,
    InvoiceStatus,
    Payment,
    PaymentStatus,
    PricingTier,
    Subscription,
    SubscriptionStatus,
    UsageMetrics,
    QuotaUsage,
    BillingHistory,
)
from backend.app.core.session import SessionManager

logger = logging.getLogger(__name__)


class SubscriptionEvent(str, Enum):
    """订阅事件类型"""
    CREATED = "subscription_created"
    ACTIVATED = "subscription_activated"
    PAUSED = "subscription_paused"
    RESUMED = "subscription_resumed"
    UPGRADED = "subscription_upgraded"
    DOWNGRADED = "subscription_downgraded"
    RENEWED = "subscription_renewed"
    CANCELLED = "subscription_cancelled"
    EXPIRED = "subscription_expired"
    TRIAL_STARTED = "trial_started"
    TRIAL_ENDED = "trial_ended"


class TrialPeriod(str, Enum):
    """试用期类型"""
    SEVEN_DAYS = "7_days"
    FOURTEEN_DAYS = "14_days"
    THIRTY_DAYS = "30_days"


class SubscriptionManager:
    """订阅管理器 - 处理订阅生命周期"""

    async def create_subscription(
        self,
        tenant_id: str,
        user_id: str,
        pricing_tier_id: str,
        payment_method: str,
        payment_method_id: str,
        auto_renew: bool = True,
        trial_period: Optional[TrialPeriod] = None,
        promotion_code: Optional[str] = None,
    ) -> Subscription:
        """创建新订阅"""
        async with SessionManager.get_session() as session:
            # 验证价格层级
            pricing_tier = await session.get(PricingTier, pricing_tier_id)
            if not pricing_tier or pricing_tier.tenant_id != tenant_id:
                raise ValueError(f"Invalid pricing tier: {pricing_tier_id}")

            # 检查是否已有活跃订阅
            existing = await self._get_active_subscription(
                session, tenant_id, user_id
            )
            if existing:
                # 取消旧订阅
                existing.status = SubscriptionStatus.CANCELLED
                existing.updated_at = datetime.now(UTC)
                await self._record_event(
                    session,
                    tenant_id,
                    user_id,
                    SubscriptionEvent.CANCELLED,
                    existing.id,
                    {"reason": "replaced_by_new_subscription"},
                )

            # 计算订阅周期
            now = datetime.now(UTC)
            start_date = now

            # 处理试用期
            if trial_period:
                trial_days = int(trial_period.value.split("_")[0])
                end_date = now + timedelta(days=trial_days)
                renewal_date = end_date
                status = SubscriptionStatus.ACTIVE
            else:
                # 标准订阅周期（30天）
                end_date = now + timedelta(days=30)
                renewal_date = end_date
                status = SubscriptionStatus.ACTIVE

            # 创建订阅
            subscription = Subscription(
                id=str(uuid4()),
                tenant_id=tenant_id,
                user_id=user_id,
                pricing_tier_id=pricing_tier_id,
                status=status,
                billing_model=pricing_tier.billing_model,
                start_date=start_date,
                end_date=end_date,
                renewal_date=renewal_date,
                payment_method=payment_method,
                payment_method_id=payment_method_id,
                auto_renew=auto_renew,
                extra_metadata={
                    "trial_period": trial_period.value if trial_period else None,
                    "created_from": "api",
                },
            )

            session.add(subscription)
            await session.flush()

            # 初始化配额
            await self._initialize_quota(
                session, tenant_id, user_id, subscription.id, pricing_tier
            )

            # 记录事件
            event_type = (
                SubscriptionEvent.TRIAL_STARTED
                if trial_period
                else SubscriptionEvent.CREATED
            )
            await self._record_event(
                session,
                tenant_id,
                user_id,
                event_type,
                subscription.id,
                {
                    "pricing_tier_id": pricing_tier_id,
                    "trial_period": trial_period.value if trial_period else None,
                },
            )

            await session.commit()

            logger.info(
                f"订阅创建: subscription={subscription.id}, "
                f"user={user_id}, tier={pricing_tier_id}"
            )

            return subscription

    async def pause_subscription(
        self, tenant_id: str, user_id: str, reason: Optional[str] = None
    ) -> Subscription:
        """暂停订阅"""
        async with SessionManager.get_session() as session:
            subscription = await self._get_active_subscription(
                session, tenant_id, user_id
            )
            if not subscription:
                raise ValueError("No active subscription found")

            subscription.status = SubscriptionStatus.PAUSED
            subscription.updated_at = datetime.now(UTC)

            await self._record_event(
                session,
                tenant_id,
                user_id,
                SubscriptionEvent.PAUSED,
                subscription.id,
                {"reason": reason},
            )

            await session.commit()

            logger.info(
                f"订阅暂停: subscription={subscription.id}, user={user_id}"
            )

            return subscription

    async def resume_subscription(
        self, tenant_id: str, user_id: str
    ) -> Subscription:
        """恢复订阅"""
        async with SessionManager.get_session() as session:
            stmt = select(Subscription).where(
                and_(
                    Subscription.tenant_id == tenant_id,
                    Subscription.user_id == user_id,
                    Subscription.status == SubscriptionStatus.PAUSED,
                )
            )
            result = await session.execute(stmt)
            subscription = result.scalar_one_or_none()

            if not subscription:
                raise ValueError("No paused subscription found")

            subscription.status = SubscriptionStatus.ACTIVE
            subscription.updated_at = datetime.now(UTC)

            await self._record_event(
                session,
                tenant_id,
                user_id,
                SubscriptionEvent.RESUMED,
                subscription.id,
            )

            await session.commit()

            logger.info(
                f"订阅恢复: subscription={subscription.id}, user={user_id}"
            )

            return subscription

    async def cancel_subscription(
        self, tenant_id: str, user_id: str, reason: Optional[str] = None
    ) -> Subscription:
        """取消订阅"""
        async with SessionManager.get_session() as session:
            subscription = await self._get_active_subscription(
                session, tenant_id, user_id
            )
            if not subscription:
                raise ValueError("No active subscription found")

            subscription.status = SubscriptionStatus.CANCELLED
            subscription.updated_at = datetime.now(UTC)

            await self._record_event(
                session,
                tenant_id,
                user_id,
                SubscriptionEvent.CANCELLED,
                subscription.id,
                {"reason": reason},
            )

            await session.commit()

            logger.info(
                f"订阅取消: subscription={subscription.id}, user={user_id}"
            )

            return subscription

    async def upgrade_subscription(
        self,
        tenant_id: str,
        user_id: str,
        new_pricing_tier_id: str,
        effective_immediately: bool = True,
    ) -> Subscription:
        """升级订阅计划"""
        async with SessionManager.get_session() as session:
            subscription = await self._get_active_subscription(
                session, tenant_id, user_id
            )
            if not subscription:
                raise ValueError("No active subscription found")

            # 验证新价格层级
            new_tier = await session.get(PricingTier, new_pricing_tier_id)
            if not new_tier or new_tier.tenant_id != tenant_id:
                raise ValueError(f"Invalid pricing tier: {new_pricing_tier_id}")

            old_tier_id = subscription.pricing_tier_id

            if effective_immediately:
                # 立即生效：计算差价
                old_tier = await session.get(PricingTier, old_tier_id)
                price_diff = await self._calculate_upgrade_credit(
                    subscription, old_tier, new_tier
                )

                subscription.pricing_tier_id = new_pricing_tier_id
                subscription.billing_model = new_tier.billing_model
                subscription.updated_at = datetime.now(UTC)

                # 更新配额
                await self._update_quota_for_tier(
                    session, tenant_id, user_id, subscription.id, new_tier
                )

                await self._record_event(
                    session,
                    tenant_id,
                    user_id,
                    SubscriptionEvent.UPGRADED,
                    subscription.id,
                    {
                        "old_tier": old_tier_id,
                        "new_tier": new_pricing_tier_id,
                        "price_diff": str(price_diff),
                        "effective_immediately": True,
                    },
                )
            else:
                # 下期生效
                subscription.extra_metadata = subscription.extra_metadata or {}
                subscription.extra_metadata["pending_upgrade"] = {
                    "new_tier_id": new_pricing_tier_id,
                    "effective_date": (
                        subscription.renewal_date.isoformat()
                        if subscription.renewal_date
                        else None
                    ),
                }
                subscription.updated_at = datetime.now(UTC)

                await self._record_event(
                    session,
                    tenant_id,
                    user_id,
                    SubscriptionEvent.UPGRADED,
                    subscription.id,
                    {
                        "old_tier": old_tier_id,
                        "new_tier": new_pricing_tier_id,
                        "effective_immediately": False,
                        "effective_date": subscription.renewal_date.isoformat()
                        if subscription.renewal_date
                        else None,
                    },
                )

            await session.commit()

            logger.info(
                f"订阅升级: subscription={subscription.id}, "
                f"user={user_id}, old_tier={old_tier_id}, new_tier={new_pricing_tier_id}"
            )

            return subscription

    async def downgrade_subscription(
        self,
        tenant_id: str,
        user_id: str,
        new_pricing_tier_id: str,
        effective_immediately: bool = False,
    ) -> Subscription:
        """降级订阅计划"""
        async with SessionManager.get_session() as session:
            subscription = await self._get_active_subscription(
                session, tenant_id, user_id
            )
            if not subscription:
                raise ValueError("No active subscription found")

            # 验证新价格层级
            new_tier = await session.get(PricingTier, new_pricing_tier_id)
            if not new_tier or new_tier.tenant_id != tenant_id:
                raise ValueError(f"Invalid pricing tier: {new_pricing_tier_id}")

            old_tier_id = subscription.pricing_tier_id

            if effective_immediately:
                subscription.pricing_tier_id = new_pricing_tier_id
                subscription.billing_model = new_tier.billing_model
                subscription.updated_at = datetime.now(UTC)

                # 更新配额
                await self._update_quota_for_tier(
                    session, tenant_id, user_id, subscription.id, new_tier
                )

                await self._record_event(
                    session,
                    tenant_id,
                    user_id,
                    SubscriptionEvent.DOWNGRADED,
                    subscription.id,
                    {
                        "old_tier": old_tier_id,
                        "new_tier": new_pricing_tier_id,
                        "effective_immediately": True,
                    },
                )
            else:
                # 下期生效
                subscription.extra_metadata = subscription.extra_metadata or {}
                subscription.extra_metadata["pending_downgrade"] = {
                    "new_tier_id": new_pricing_tier_id,
                    "effective_date": (
                        subscription.renewal_date.isoformat()
                        if subscription.renewal_date
                        else None
                    ),
                }
                subscription.updated_at = datetime.now(UTC)

                await self._record_event(
                    session,
                    tenant_id,
                    user_id,
                    SubscriptionEvent.DOWNGRADED,
                    subscription.id,
                    {
                        "old_tier": old_tier_id,
                        "new_tier": new_pricing_tier_id,
                        "effective_immediately": False,
                        "effective_date": subscription.renewal_date.isoformat()
                        if subscription.renewal_date
                        else None,
                    },
                )

            await session.commit()

            logger.info(
                f"订阅降级: subscription={subscription.id}, "
                f"user={user_id}, old_tier={old_tier_id}, new_tier={new_pricing_tier_id}"
            )

            return subscription

    async def renew_subscription(
        self, tenant_id: str, user_id: str
    ) -> Subscription:
        """续费订阅"""
        async with SessionManager.get_session() as session:
            subscription = await self._get_active_subscription(
                session, tenant_id, user_id
            )
            if not subscription:
                raise ValueError("No active subscription found")

            # 处理待处理的升级/降级
            if subscription.extra_metadata:
                if "pending_upgrade" in subscription.extra_metadata:
                    pending = subscription.extra_metadata["pending_upgrade"]
                    subscription.pricing_tier_id = pending["new_tier_id"]
                    new_tier = await session.get(
                        PricingTier, pending["new_tier_id"]
                    )
                    subscription.billing_model = new_tier.billing_model
                    await self._update_quota_for_tier(
                        session,
                        tenant_id,
                        user_id,
                        subscription.id,
                        new_tier,
                    )
                    del subscription.extra_metadata["pending_upgrade"]

                elif "pending_downgrade" in subscription.extra_metadata:
                    pending = subscription.extra_metadata["pending_downgrade"]
                    subscription.pricing_tier_id = pending["new_tier_id"]
                    new_tier = await session.get(
                        PricingTier, pending["new_tier_id"]
                    )
                    subscription.billing_model = new_tier.billing_model
                    await self._update_quota_for_tier(
                        session,
                        tenant_id,
                        user_id,
                        subscription.id,
                        new_tier,
                    )
                    del subscription.extra_metadata["pending_downgrade"]

            # 更新续费日期
            now = datetime.now(UTC)
            subscription.start_date = now
            subscription.end_date = now + timedelta(days=30)
            subscription.renewal_date = now + timedelta(days=30)
            subscription.updated_at = now

            await self._record_event(
                session,
                tenant_id,
                user_id,
                SubscriptionEvent.RENEWED,
                subscription.id,
            )

            await session.commit()

            logger.info(
                f"订阅续费: subscription={subscription.id}, user={user_id}"
            )

            return subscription

    async def get_subscription(
        self, tenant_id: str, user_id: str
    ) -> Optional[Subscription]:
        """获取活跃订阅"""
        async with SessionManager.get_session() as session:
            return await self._get_active_subscription(session, tenant_id, user_id)

    async def get_subscription_by_id(
        self, subscription_id: str
    ) -> Optional[Subscription]:
        """根据ID获取订阅"""
        async with SessionManager.get_session() as session:
            return await session.get(Subscription, subscription_id)

    # 私有方法

    async def _get_active_subscription(
        self, session: AsyncSession, tenant_id: str, user_id: str
    ) -> Optional[Subscription]:
        """获取活跃订阅"""
        stmt = select(Subscription).where(
            and_(
                Subscription.tenant_id == tenant_id,
                Subscription.user_id == user_id,
                Subscription.status == SubscriptionStatus.ACTIVE,
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _initialize_quota(
        self,
        session: AsyncSession,
        tenant_id: str,
        user_id: str,
        subscription_id: str,
        pricing_tier: PricingTier,
    ) -> QuotaUsage:
        """初始化配额"""
        now = datetime.now(UTC)
        quota = QuotaUsage(
            id=str(uuid4()),
            tenant_id=tenant_id,
            user_id=user_id,
            subscription_id=subscription_id,
            period_start=now,
            period_end=now + timedelta(days=30),
            api_calls_limit=pricing_tier.monthly_api_calls,
            tokens_limit=pricing_tier.monthly_tokens,
            storage_limit_gb=pricing_tier.storage_gb,
        )
        session.add(quota)
        return quota

    async def _update_quota_for_tier(
        self,
        session: AsyncSession,
        tenant_id: str,
        user_id: str,
        subscription_id: str,
        pricing_tier: PricingTier,
    ) -> None:
        """更新配额"""
        stmt = select(QuotaUsage).where(
            and_(
                QuotaUsage.tenant_id == tenant_id,
                QuotaUsage.user_id == user_id,
                QuotaUsage.subscription_id == subscription_id,
            )
        )
        result = await session.execute(stmt)
        quota = result.scalar_one_or_none()

        if quota:
            quota.api_calls_limit = pricing_tier.monthly_api_calls
            quota.tokens_limit = pricing_tier.monthly_tokens
            quota.storage_limit_gb = pricing_tier.storage_gb
            quota.updated_at = datetime.now(UTC)

    async def _calculate_upgrade_credit(
        self,
        subscription: Subscription,
        old_tier: PricingTier,
        new_tier: PricingTier,
    ) -> Decimal:
        """计算升级差价"""
        # 简化实现：按天数比例计算
        if not old_tier.monthly_price or not new_tier.monthly_price:
            return Decimal(0)

        end_date = subscription.end_date
        # SQLite 读回的 DateTime 可能是 naive,归一化为 UTC aware 再相减
        if end_date is not None and end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=UTC)
        days_remaining = (
            (end_date - datetime.now(UTC)).days if end_date else 0
        )
        if days_remaining <= 0:
            return Decimal(0)

        daily_old = old_tier.monthly_price / 30
        daily_new = new_tier.monthly_price / 30
        diff = (daily_new - daily_old) * days_remaining

        return max(diff, Decimal(0))

    async def _record_event(
        self,
        session: AsyncSession,
        tenant_id: str,
        user_id: str,
        event_type: SubscriptionEvent,
        subscription_id: str,
        details: Optional[dict] = None,
    ) -> BillingHistory:
        """记录订阅事件"""
        event = BillingHistory(
            id=str(uuid4()),
            tenant_id=tenant_id,
            user_id=user_id,
            event_type=event_type.value,
            subscription_id=subscription_id,
            details=details or {},
        )
        session.add(event)
        return event


# 全局实例
_subscription_manager: Optional[SubscriptionManager] = None


def get_subscription_manager() -> SubscriptionManager:
    """获取订阅管理器实例"""
    global _subscription_manager
    if _subscription_manager is None:
        _subscription_manager = SubscriptionManager()
    return _subscription_manager
