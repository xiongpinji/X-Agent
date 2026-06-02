"""
配额管理系统 - 处理API调用、Token、存储、并发连接配额
支持软限制、硬限制、告警机制
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.billing import (
    QuotaUsage,
    Subscription,
    SubscriptionStatus,
    PricingTier,
    BillingHistory,
)
from backend.app.core.session import SessionManager

logger = logging.getLogger(__name__)


class QuotaType(str, Enum):
    """配额类型"""
    API_CALLS = "api_calls"
    TOKENS_INPUT = "tokens_input"
    TOKENS_OUTPUT = "tokens_output"
    STORAGE = "storage"
    CONCURRENT_CONNECTIONS = "concurrent_connections"


class QuotaAlertLevel(str, Enum):
    """配额告警级别"""
    WARNING_80 = "80"  # 80%使用率
    WARNING_90 = "90"  # 90%使用率
    CRITICAL_100 = "100"  # 100%使用率


class QuotaManager:
    """配额管理器 - 处理配额检查、更新、告警"""

    async def check_quota(
        self,
        tenant_id: str,
        user_id: str,
        quota_type: QuotaType,
        amount: int | Decimal = 1,
    ) -> dict:
        """检查配额是否充足"""
        async with SessionManager.get_session() as session:
            quota = await self._get_current_quota(session, tenant_id, user_id)
            if not quota:
                return {
                    "has_quota": False,
                    "reason": "No active subscription",
                    "quota_type": quota_type.value,
                }

            # 检查配额限制
            if quota_type == QuotaType.API_CALLS:
                if quota.api_calls_limit is None:
                    return {"has_quota": True, "quota_type": quota_type.value}

                remaining = quota.api_calls_limit - quota.api_calls_used
                if remaining < amount:
                    return {
                        "has_quota": False,
                        "reason": "API calls quota exceeded",
                        "quota_type": quota_type.value,
                        "used": quota.api_calls_used,
                        "limit": quota.api_calls_limit,
                        "remaining": max(0, remaining),
                    }

                # 检查告警
                usage_percent = (quota.api_calls_used / quota.api_calls_limit) * 100
                alert_level = self._get_alert_level(usage_percent)

                return {
                    "has_quota": True,
                    "quota_type": quota_type.value,
                    "used": quota.api_calls_used,
                    "limit": quota.api_calls_limit,
                    "remaining": remaining,
                    "usage_percent": usage_percent,
                    "alert_level": alert_level,
                }

            elif quota_type == QuotaType.TOKENS_INPUT:
                if quota.tokens_limit is None:
                    return {"has_quota": True, "quota_type": quota_type.value}

                remaining = quota.tokens_limit - quota.tokens_used
                if remaining < amount:
                    return {
                        "has_quota": False,
                        "reason": "Tokens quota exceeded",
                        "quota_type": quota_type.value,
                        "used": quota.tokens_used,
                        "limit": quota.tokens_limit,
                        "remaining": max(0, remaining),
                    }

                usage_percent = (quota.tokens_used / quota.tokens_limit) * 100
                alert_level = self._get_alert_level(usage_percent)

                return {
                    "has_quota": True,
                    "quota_type": quota_type.value,
                    "used": quota.tokens_used,
                    "limit": quota.tokens_limit,
                    "remaining": remaining,
                    "usage_percent": usage_percent,
                    "alert_level": alert_level,
                }

            elif quota_type == QuotaType.STORAGE:
                if quota.storage_limit_gb is None:
                    return {"has_quota": True, "quota_type": quota_type.value}

                remaining = quota.storage_limit_gb - quota.storage_used_gb
                if remaining < amount:
                    return {
                        "has_quota": False,
                        "reason": "Storage quota exceeded",
                        "quota_type": quota_type.value,
                        "used": float(quota.storage_used_gb),
                        "limit": quota.storage_limit_gb,
                        "remaining": max(0, float(remaining)),
                    }

                usage_percent = (
                    (quota.storage_used_gb / quota.storage_limit_gb) * 100
                )
                alert_level = self._get_alert_level(usage_percent)

                return {
                    "has_quota": True,
                    "quota_type": quota_type.value,
                    "used": float(quota.storage_used_gb),
                    "limit": quota.storage_limit_gb,
                    "remaining": float(remaining),
                    "usage_percent": float(usage_percent),
                    "alert_level": alert_level,
                }

            return {
                "has_quota": True,
                "quota_type": quota_type.value,
            }

    async def consume_quota(
        self,
        tenant_id: str,
        user_id: str,
        quota_type: QuotaType,
        amount: int | Decimal = 1,
    ) -> bool:
        """消费配额"""
        async with SessionManager.get_session() as session:
            # 检查配额
            check_result = await self.check_quota(
                tenant_id, user_id, quota_type, amount
            )
            if not check_result.get("has_quota"):
                logger.warning(
                    f"配额不足: tenant={tenant_id}, user={user_id}, "
                    f"type={quota_type.value}, amount={amount}"
                )
                return False

            # 更新配额使用
            quota = await self._get_current_quota(session, tenant_id, user_id)
            if not quota:
                return False

            if quota_type == QuotaType.API_CALLS:
                quota.api_calls_used += int(amount)
            elif quota_type == QuotaType.TOKENS_INPUT:
                quota.tokens_used += int(amount)
            elif quota_type == QuotaType.TOKENS_OUTPUT:
                quota.tokens_used += int(amount)
            elif quota_type == QuotaType.STORAGE:
                quota.storage_used_gb += Decimal(str(amount))

            quota.updated_at = datetime.now(UTC)

            # 检查是否需要发送告警
            alert_level = check_result.get("alert_level")
            if alert_level:
                await self._send_quota_alert(
                    session,
                    tenant_id,
                    user_id,
                    quota_type,
                    alert_level,
                    check_result,
                )

            await session.commit()

            logger.info(
                f"配额消费: tenant={tenant_id}, user={user_id}, "
                f"type={quota_type.value}, amount={amount}"
            )

            return True

    async def get_quota_info(
        self, tenant_id: str, user_id: str
    ) -> Optional[dict]:
        """获取配额信息"""
        async with SessionManager.get_session() as session:
            quota = await self._get_current_quota(session, tenant_id, user_id)
            if not quota:
                return None

            # 获取订阅信息
            subscription = await self._get_active_subscription(
                session, tenant_id, user_id
            )
            if not subscription:
                return None

            # 计算使用百分比
            api_calls_percent = (
                (quota.api_calls_used / quota.api_calls_limit * 100)
                if quota.api_calls_limit
                else 0
            )
            tokens_percent = (
                (quota.tokens_used / quota.tokens_limit * 100)
                if quota.tokens_limit
                else 0
            )
            storage_percent = (
                (quota.storage_used_gb / quota.storage_limit_gb * 100)
                if quota.storage_limit_gb
                else 0
            )

            return {
                "subscription_id": subscription.id,
                "period_start": quota.period_start.isoformat(),
                "period_end": quota.period_end.isoformat(),
                "api_calls": {
                    "used": quota.api_calls_used,
                    "limit": quota.api_calls_limit,
                    "remaining": max(
                        0,
                        (quota.api_calls_limit - quota.api_calls_used)
                        if quota.api_calls_limit
                        else 0,
                    ),
                    "usage_percent": api_calls_percent,
                    "alert_level": self._get_alert_level(api_calls_percent),
                },
                "tokens": {
                    "used": quota.tokens_used,
                    "limit": quota.tokens_limit,
                    "remaining": max(
                        0,
                        (quota.tokens_limit - quota.tokens_used)
                        if quota.tokens_limit
                        else 0,
                    ),
                    "usage_percent": tokens_percent,
                    "alert_level": self._get_alert_level(tokens_percent),
                },
                "storage": {
                    "used": float(quota.storage_used_gb),
                    "limit": quota.storage_limit_gb,
                    "remaining": max(
                        0,
                        float(quota.storage_limit_gb - quota.storage_used_gb)
                        if quota.storage_limit_gb
                        else 0,
                    ),
                    "usage_percent": storage_percent,
                    "alert_level": self._get_alert_level(storage_percent),
                },
            }

    async def reset_quota(
        self, tenant_id: str, user_id: str
    ) -> Optional[QuotaUsage]:
        """重置配额（用于新的计费周期）"""
        async with SessionManager.get_session() as session:
            subscription = await self._get_active_subscription(
                session, tenant_id, user_id
            )
            if not subscription:
                return None

            # 获取价格层级
            pricing_tier = await session.get(
                PricingTier, subscription.pricing_tier_id
            )
            if not pricing_tier:
                return None

            # 创建新的配额记录
            now = datetime.now(UTC)
            new_quota = QuotaUsage(
                id=str(uuid4()),
                tenant_id=tenant_id,
                user_id=user_id,
                subscription_id=subscription.id,
                period_start=now,
                period_end=now + timedelta(days=30),
                api_calls_limit=pricing_tier.monthly_api_calls,
                tokens_limit=pricing_tier.monthly_tokens,
                storage_limit_gb=pricing_tier.storage_gb,
            )

            session.add(new_quota)
            await session.commit()

            logger.info(
                f"配额重置: tenant={tenant_id}, user={user_id}"
            )

            return new_quota

    # 私有方法

    async def _get_current_quota(
        self, session: AsyncSession, tenant_id: str, user_id: str
    ) -> Optional[QuotaUsage]:
        """获取当前配额"""
        now = datetime.now(UTC)
        stmt = select(QuotaUsage).where(
            and_(
                QuotaUsage.tenant_id == tenant_id,
                QuotaUsage.user_id == user_id,
                QuotaUsage.period_start <= now,
                QuotaUsage.period_end >= now,
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

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

    def _get_alert_level(self, usage_percent: float) -> Optional[str]:
        """获取告警级别"""
        if usage_percent >= 100:
            return QuotaAlertLevel.CRITICAL_100.value
        elif usage_percent >= 90:
            return QuotaAlertLevel.WARNING_90.value
        elif usage_percent >= 80:
            return QuotaAlertLevel.WARNING_80.value
        return None

    async def _send_quota_alert(
        self,
        session: AsyncSession,
        tenant_id: str,
        user_id: str,
        quota_type: QuotaType,
        alert_level: str,
        quota_info: dict,
    ) -> None:
        """发送配额告警"""
        # 记录告警事件
        event = BillingHistory(
            id=str(uuid4()),
            tenant_id=tenant_id,
            user_id=user_id,
            event_type=f"quota_alert_{alert_level}",
            details={
                "quota_type": quota_type.value,
                "alert_level": alert_level,
                "usage_info": quota_info,
            },
        )
        session.add(event)

        logger.warning(
            f"配额告警: tenant={tenant_id}, user={user_id}, "
            f"type={quota_type.value}, level={alert_level}, "
            f"usage={quota_info.get('usage_percent')}%"
        )

        # TODO: 发送邮件/站内信通知


# 全局实例
_quota_manager: Optional[QuotaManager] = None


def get_quota_manager() -> QuotaManager:
    """获取配额管理器实例"""
    global _quota_manager
    if _quota_manager is None:
        _quota_manager = QuotaManager()
    return _quota_manager
