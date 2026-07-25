"""
订阅管理服务 - 业务逻辑实现
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.session import SessionManager
from backend.app.models.subscription import (
    QuotaModel,
    SubscriptionHistoryModel,
    SubscriptionModel,
    SubscriptionPlan,
    SubscriptionStatus,
)

logger = logging.getLogger(__name__)


class SubscriptionService:
    """订阅管理服务"""

    # 计划配置
    PLAN_CONFIG = {
        SubscriptionPlan.FREE: {
            "price_per_month": 0.0,
            "api_calls_limit": 1000,
            "tokens_limit": 100000,
            "storage_limit_mb": 100,
            "concurrent_connections_limit": 1,
        },
        SubscriptionPlan.STARTER: {
            "price_per_month": 9.99,
            "api_calls_limit": 50000,
            "tokens_limit": 5000000,
            "storage_limit_mb": 5120,
            "concurrent_connections_limit": 5,
        },
        SubscriptionPlan.PROFESSIONAL: {
            "price_per_month": 49.99,
            "api_calls_limit": 500000,
            "tokens_limit": 50000000,
            "storage_limit_mb": 51200,
            "concurrent_connections_limit": 20,
        },
        SubscriptionPlan.ENTERPRISE: {
            "price_per_month": 299.99,
            "api_calls_limit": 5000000,
            "tokens_limit": 500000000,
            "storage_limit_mb": 512000,
            "concurrent_connections_limit": 100,
        },
    }

    async def create_subscription(
        self,
        user_id: str,
        tenant_id: str,
        plan: SubscriptionPlan = SubscriptionPlan.FREE,
        trial_days: int = 14,
    ) -> SubscriptionModel:
        """创建订阅"""
        async with SessionManager.get_session() as session:
            subscription_id = str(uuid.uuid4())
            now = datetime.now(UTC)

            # 计算试用期结束时间
            trial_end = now + timedelta(days=trial_days) if plan != SubscriptionPlan.FREE else None

            # 计算当前周期结束时间
            current_period_end = now + timedelta(days=30)

            config = self.PLAN_CONFIG.get(plan, self.PLAN_CONFIG[SubscriptionPlan.FREE])

            subscription = SubscriptionModel(
                subscription_id=subscription_id,
                user_id=user_id,
                tenant_id=tenant_id,
                plan=plan,
                status=SubscriptionStatus.TRIAL if trial_end else SubscriptionStatus.ACTIVE,
                price_per_month=config["price_per_month"],
                currency="USD",
                current_period_start=now,
                current_period_end=current_period_end,
                trial_end=trial_end,
                auto_renew=True,
            )

            session.add(subscription)
            await session.flush()

            # 创建配额
            await self._create_quota(session, subscription_id, user_id, tenant_id, plan)

            # 记录历史
            await self._record_history(
                session,
                subscription_id,
                user_id,
                tenant_id,
                "created",
                new_plan=plan.value,
                new_status=subscription.status,
            )

            logger.info(f"订阅创建成功: {subscription_id}, 用户: {user_id}, 计划: {plan}")
            return subscription

    async def get_subscription(self, subscription_id: str) -> SubscriptionModel | None:
        """获取订阅"""
        async with SessionManager.get_session() as session:
            stmt = select(SubscriptionModel).where(
                SubscriptionModel.subscription_id == subscription_id
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_user_subscription(
        self, user_id: str, tenant_id: str
    ) -> SubscriptionModel | None:
        """获取用户订阅"""
        async with SessionManager.get_session() as session:
            stmt = select(SubscriptionModel).where(
                and_(
                    SubscriptionModel.user_id == user_id,
                    SubscriptionModel.tenant_id == tenant_id,
                )
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def upgrade_subscription(
        self, subscription_id: str, new_plan: SubscriptionPlan
    ) -> SubscriptionModel:
        """升级订阅"""
        async with SessionManager.get_session() as session:
            stmt = select(SubscriptionModel).where(
                SubscriptionModel.subscription_id == subscription_id
            )
            result = await session.execute(stmt)
            subscription = result.scalar_one_or_none()

            if not subscription:
                raise ValueError(f"订阅不存在: {subscription_id}")

            old_plan = subscription.plan
            subscription.plan = new_plan
            subscription.updated_at = datetime.now(UTC)

            config = self.PLAN_CONFIG.get(new_plan, self.PLAN_CONFIG[SubscriptionPlan.FREE])
            subscription.price_per_month = config["price_per_month"]

            # 更新配额
            await self._update_quota(session, subscription_id, new_plan)

            await session.flush()

            # 记录历史
            await self._record_history(
                session,
                subscription_id,
                subscription.user_id,
                subscription.tenant_id,
                "upgraded",
                old_plan=old_plan.value,
                new_plan=new_plan.value,
            )

            logger.info(
                f"订阅升级成功: {subscription_id}, 从 {old_plan} 升级到 {new_plan}"
            )
            return subscription

    async def downgrade_subscription(
        self, subscription_id: str, new_plan: SubscriptionPlan
    ) -> SubscriptionModel:
        """降级订阅"""
        async with SessionManager.get_session() as session:
            stmt = select(SubscriptionModel).where(
                SubscriptionModel.subscription_id == subscription_id
            )
            result = await session.execute(stmt)
            subscription = result.scalar_one_or_none()

            if not subscription:
                raise ValueError(f"订阅不存在: {subscription_id}")

            old_plan = subscription.plan
            subscription.plan = new_plan
            subscription.updated_at = datetime.now(UTC)

            config = self.PLAN_CONFIG.get(new_plan, self.PLAN_CONFIG[SubscriptionPlan.FREE])
            subscription.price_per_month = config["price_per_month"]

            # 更新配额
            await self._update_quota(session, subscription_id, new_plan)

            await session.flush()

            # 记录历史
            await self._record_history(
                session,
                subscription_id,
                subscription.user_id,
                subscription.tenant_id,
                "downgraded",
                old_plan=old_plan.value,
                new_plan=new_plan.value,
            )

            logger.info(
                f"订阅降级成功: {subscription_id}, 从 {old_plan} 降级到 {new_plan}"
            )
            return subscription

    async def pause_subscription(self, subscription_id: str) -> SubscriptionModel:
        """暂停订阅"""
        async with SessionManager.get_session() as session:
            stmt = select(SubscriptionModel).where(
                SubscriptionModel.subscription_id == subscription_id
            )
            result = await session.execute(stmt)
            subscription = result.scalar_one_or_none()

            if not subscription:
                raise ValueError(f"订阅不存在: {subscription_id}")

            old_status = subscription.status
            subscription.status = SubscriptionStatus.PAUSED
            subscription.paused_at = datetime.now(UTC)
            subscription.updated_at = datetime.now(UTC)

            await session.flush()

            # 记录历史
            await self._record_history(
                session,
                subscription_id,
                subscription.user_id,
                subscription.tenant_id,
                "paused",
                old_status=old_status.value,
                new_status=SubscriptionStatus.PAUSED.value,
            )

            logger.info(f"订阅暂停成功: {subscription_id}")
            return subscription

    async def resume_subscription(self, subscription_id: str) -> SubscriptionModel:
        """恢复订阅"""
        async with SessionManager.get_session() as session:
            stmt = select(SubscriptionModel).where(
                SubscriptionModel.subscription_id == subscription_id
            )
            result = await session.execute(stmt)
            subscription = result.scalar_one_or_none()

            if not subscription:
                raise ValueError(f"订阅不存在: {subscription_id}")

            old_status = subscription.status
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.paused_at = None
            subscription.updated_at = datetime.now(UTC)

            await session.flush()

            # 记录历史
            await self._record_history(
                session,
                subscription_id,
                subscription.user_id,
                subscription.tenant_id,
                "resumed",
                old_status=old_status.value,
                new_status=SubscriptionStatus.ACTIVE.value,
            )

            logger.info(f"订阅恢复成功: {subscription_id}")
            return subscription

    async def cancel_subscription(self, subscription_id: str) -> SubscriptionModel:
        """取消订阅"""
        async with SessionManager.get_session() as session:
            stmt = select(SubscriptionModel).where(
                SubscriptionModel.subscription_id == subscription_id
            )
            result = await session.execute(stmt)
            subscription = result.scalar_one_or_none()

            if not subscription:
                raise ValueError(f"订阅不存在: {subscription_id}")

            old_status = subscription.status
            subscription.status = SubscriptionStatus.CANCELLED
            subscription.cancelled_at = datetime.now(UTC)
            subscription.auto_renew = False
            subscription.updated_at = datetime.now(UTC)

            await session.flush()

            # 记录历史
            await self._record_history(
                session,
                subscription_id,
                subscription.user_id,
                subscription.tenant_id,
                "cancelled",
                old_status=old_status.value,
                new_status=SubscriptionStatus.CANCELLED.value,
            )

            logger.info(f"订阅取消成功: {subscription_id}")
            return subscription

    async def renew_subscription(self, subscription_id: str) -> SubscriptionModel:
        """续费订阅"""
        async with SessionManager.get_session() as session:
            stmt = select(SubscriptionModel).where(
                SubscriptionModel.subscription_id == subscription_id
            )
            result = await session.execute(stmt)
            subscription = result.scalar_one_or_none()

            if not subscription:
                raise ValueError(f"订阅不存在: {subscription_id}")

            now = datetime.now(UTC)
            subscription.current_period_start = now
            subscription.current_period_end = now + timedelta(days=30)
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.renewal_failed_count = 0
            subscription.updated_at = now

            await session.flush()

            # 记录历史
            await self._record_history(
                session,
                subscription_id,
                subscription.user_id,
                subscription.tenant_id,
                "renewed",
                new_status=SubscriptionStatus.ACTIVE.value,
            )

            logger.info(f"订阅续费成功: {subscription_id}")
            return subscription

    async def mark_renewal_failed(self, subscription_id: str) -> SubscriptionModel:
        """标记续费失败"""
        async with SessionManager.get_session() as session:
            stmt = select(SubscriptionModel).where(
                SubscriptionModel.subscription_id == subscription_id
            )
            result = await session.execute(stmt)
            subscription = result.scalar_one_or_none()

            if not subscription:
                raise ValueError(f"订阅不存在: {subscription_id}")

            subscription.renewal_failed_count += 1
            subscription.updated_at = datetime.now(UTC)

            # 如果失败次数超过3次，标记为过期
            if subscription.renewal_failed_count >= 3:
                subscription.status = SubscriptionStatus.EXPIRED

            await session.flush()

            # 记录历史
            await self._record_history(
                session,
                subscription_id,
                subscription.user_id,
                subscription.tenant_id,
                "failed_renewal",
                details=json.dumps({"failed_count": subscription.renewal_failed_count}),
            )

            logger.warning(
                f"订阅续费失败: {subscription_id}, 失败次数: {subscription.renewal_failed_count}"
            )
            return subscription

    async def get_quota(self, subscription_id: str) -> QuotaModel | None:
        """获取配额"""
        async with SessionManager.get_session() as session:
            stmt = select(QuotaModel).where(QuotaModel.subscription_id == subscription_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def check_quota(
        self, subscription_id: str, quota_type: str, amount: int = 1
    ) -> bool:
        """检查配额是否充足"""
        quota = await self.get_quota(subscription_id)
        if not quota:
            return False

        if quota_type == "api_calls":
            return quota.api_calls_used + amount <= quota.api_calls_limit
        elif quota_type == "tokens":
            return quota.tokens_used + amount <= quota.tokens_limit
        elif quota_type == "storage":
            return quota.storage_used_mb + amount <= quota.storage_limit_mb
        elif quota_type == "concurrent_connections":
            return quota.concurrent_connections_current + amount <= quota.concurrent_connections_limit

        return False

    async def consume_quota(
        self, subscription_id: str, quota_type: str, amount: int = 1
    ) -> bool:
        """消费配额"""
        async with SessionManager.get_session() as session:
            stmt = select(QuotaModel).where(QuotaModel.subscription_id == subscription_id)
            result = await session.execute(stmt)
            quota = result.scalar_one_or_none()

            if not quota:
                return False

            # 检查配额是否充足
            if quota_type == "api_calls":
                if quota.api_calls_used + amount > quota.api_calls_limit:
                    return False
                quota.api_calls_used += amount
            elif quota_type == "tokens":
                if quota.tokens_used + amount > quota.tokens_limit:
                    return False
                quota.tokens_used += amount
            elif quota_type == "storage":
                if quota.storage_used_mb + amount > quota.storage_limit_mb:
                    return False
                quota.storage_used_mb += amount
            elif quota_type == "concurrent_connections":
                if quota.concurrent_connections_current + amount > quota.concurrent_connections_limit:
                    return False
                quota.concurrent_connections_current += amount
            else:
                return False

            quota.updated_at = datetime.now(UTC)
            await session.flush()
            return True

    async def release_quota(
        self, subscription_id: str, quota_type: str, amount: int = 1
    ) -> bool:
        """释放配额"""
        async with SessionManager.get_session() as session:
            stmt = select(QuotaModel).where(QuotaModel.subscription_id == subscription_id)
            result = await session.execute(stmt)
            quota = result.scalar_one_or_none()

            if not quota:
                return False

            if quota_type == "concurrent_connections":
                quota.concurrent_connections_current = max(0, quota.concurrent_connections_current - amount)
            else:
                return False

            quota.updated_at = datetime.now(UTC)
            await session.flush()
            return True

    async def reset_quota(self, subscription_id: str) -> QuotaModel:
        """重置配额"""
        async with SessionManager.get_session() as session:
            stmt = select(QuotaModel).where(QuotaModel.subscription_id == subscription_id)
            result = await session.execute(stmt)
            quota = result.scalar_one_or_none()

            if not quota:
                raise ValueError(f"配额不存在: {subscription_id}")

            quota.api_calls_used = 0
            quota.tokens_used = 0
            quota.storage_used_mb = 0
            quota.reset_at = datetime.now(UTC) + timedelta(days=30)
            quota.updated_at = datetime.now(UTC)

            await session.flush()
            logger.info(f"配额重置成功: {subscription_id}")
            return quota

    async def get_subscription_history(
        self, subscription_id: str, limit: int = 100, offset: int = 0
    ) -> list[SubscriptionHistoryModel]:
        """获取订阅历史"""
        async with SessionManager.get_session() as session:
            stmt = (
                select(SubscriptionHistoryModel)
                .where(SubscriptionHistoryModel.subscription_id == subscription_id)
                .order_by(SubscriptionHistoryModel.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    # 私有方法

    async def _create_quota(
        self,
        session: AsyncSession,
        subscription_id: str,
        user_id: str,
        tenant_id: str,
        plan: SubscriptionPlan,
    ) -> QuotaModel:
        """创建配额"""
        quota_id = str(uuid.uuid4())
        config = self.PLAN_CONFIG.get(plan, self.PLAN_CONFIG[SubscriptionPlan.FREE])
        now = datetime.now(UTC)

        quota = QuotaModel(
            quota_id=quota_id,
            subscription_id=subscription_id,
            user_id=user_id,
            tenant_id=tenant_id,
            api_calls_limit=config["api_calls_limit"],
            tokens_limit=config["tokens_limit"],
            storage_limit_mb=config["storage_limit_mb"],
            concurrent_connections_limit=config["concurrent_connections_limit"],
            reset_at=now + timedelta(days=30),
        )

        session.add(quota)
        await session.flush()
        return quota

    async def _update_quota(
        self, session: AsyncSession, subscription_id: str, plan: SubscriptionPlan
    ) -> QuotaModel:
        """更新配额"""
        stmt = select(QuotaModel).where(QuotaModel.subscription_id == subscription_id)
        result = await session.execute(stmt)
        quota = result.scalar_one_or_none()

        if not quota:
            raise ValueError(f"配额不存在: {subscription_id}")

        config = self.PLAN_CONFIG.get(plan, self.PLAN_CONFIG[SubscriptionPlan.FREE])
        quota.api_calls_limit = config["api_calls_limit"]
        quota.tokens_limit = config["tokens_limit"]
        quota.storage_limit_mb = config["storage_limit_mb"]
        quota.concurrent_connections_limit = config["concurrent_connections_limit"]
        quota.updated_at = datetime.now(UTC)

        await session.flush()
        return quota

    async def _record_history(
        self,
        session: AsyncSession,
        subscription_id: str,
        user_id: str,
        tenant_id: str,
        event_type: str,
        old_plan: str | None = None,
        new_plan: str | None = None,
        old_status: str | None = None,
        new_status: str | None = None,
        details: str | None = None,
    ) -> SubscriptionHistoryModel:
        """记录订阅历史"""
        history_id = str(uuid.uuid4())

        history = SubscriptionHistoryModel(
            history_id=history_id,
            subscription_id=subscription_id,
            user_id=user_id,
            tenant_id=tenant_id,
            event_type=event_type,
            old_plan=old_plan,
            new_plan=new_plan,
            old_status=old_status,
            new_status=new_status,
            details=details,
        )

        session.add(history)
        await session.flush()
        return history


# 全局实例
_subscription_service: SubscriptionService | None = None


def get_subscription_service() -> SubscriptionService:
    """获取全局订阅服务实例"""
    global _subscription_service
    if _subscription_service is None:
        _subscription_service = SubscriptionService()
    return _subscription_service
