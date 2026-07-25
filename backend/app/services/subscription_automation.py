"""
订阅自动化流程 - 续费、提醒、过期处理
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, select

from backend.app.core.notifications import send_notification
from backend.app.core.session import SessionManager
from backend.app.models.subscription import (
    SubscriptionModel,
    SubscriptionStatus,
)
from backend.app.services.subscription import get_subscription_service

logger = logging.getLogger(__name__)


class SubscriptionAutomationService:
    """订阅自动化服务"""

    async def process_auto_renewals(self) -> dict[str, int]:
        """处理自动续费

        检查所有需要续费的订阅并进行续费处理。

        Returns:
            处理结果统计
        """
        async with SessionManager.get_session() as session:
            now = datetime.now(UTC)

            # 查找需要续费的订阅
            stmt = select(SubscriptionModel).where(
                and_(
                    SubscriptionModel.auto_renew,
                    SubscriptionModel.status == SubscriptionStatus.ACTIVE,
                    SubscriptionModel.current_period_end <= now,
                )
            )

            result = await session.execute(stmt)
            subscriptions = result.scalars().all()

            success_count = 0
            failed_count = 0

            service = get_subscription_service()

            for subscription in subscriptions:
                try:
                    await service.renew_subscription(subscription.subscription_id)
                    success_count += 1
                    logger.info(f"自动续费成功: {subscription.subscription_id}")
                except Exception as e:
                    failed_count += 1
                    await service.mark_renewal_failed(subscription.subscription_id)
                    logger.error(f"自动续费失败: {subscription.subscription_id}, 错误: {e!s}")

            return {
                "total": len(subscriptions),
                "success": success_count,
                "failed": failed_count,
            }

    async def send_expiration_reminders(self) -> dict[str, int]:
        """发送过期提醒

        检查即将过期的订阅并发送提醒。

        Returns:
            发送结果统计
        """
        async with SessionManager.get_session() as session:
            now = datetime.now(UTC)
            reminder_threshold = now + timedelta(days=7)

            # 查找即将过期的订阅
            stmt = select(SubscriptionModel).where(
                and_(
                    SubscriptionModel.status == SubscriptionStatus.ACTIVE,
                    SubscriptionModel.current_period_end > now,
                    SubscriptionModel.current_period_end <= reminder_threshold,
                )
            )

            result = await session.execute(stmt)
            subscriptions = result.scalars().all()

            sent_count = 0

            for subscription in subscriptions:
                try:
                    # 这里可以集成邮件服务发送提醒
                    await self._send_expiration_email(subscription)
                    sent_count += 1
                    logger.info(f"过期提醒已发送: {subscription.subscription_id}")
                except Exception as e:
                    logger.error(f"发送过期提醒失败: {subscription.subscription_id}, 错误: {e!s}")

            return {
                "total": len(subscriptions),
                "sent": sent_count,
            }

    async def send_quota_warnings(self) -> dict[str, int]:
        """发送配额告警

        检查配额使用超过80%的订阅并发送告警。

        Returns:
            发送结果统计
        """
        async with SessionManager.get_session() as session:
            from backend.app.models.subscription import QuotaModel

            # 查找配额使用超过80%的订阅
            stmt = select(QuotaModel).where(
                or_(
                    QuotaModel.api_calls_used >= QuotaModel.api_calls_limit * 0.8,
                    QuotaModel.tokens_used >= QuotaModel.tokens_limit * 0.8,
                    QuotaModel.storage_used_mb >= QuotaModel.storage_limit_mb * 0.8,
                )
            )

            result = await session.execute(stmt)
            quotas = result.scalars().all()

            sent_count = 0

            for quota in quotas:
                try:
                    # 这里可以集成邮件服务发送告警
                    await self._send_quota_warning_email(quota)
                    sent_count += 1
                    logger.info(f"配额告警已发送: {quota.quota_id}")
                except Exception as e:
                    logger.error(f"发送配额告警失败: {quota.quota_id}, 错误: {e!s}")

            return {
                "total": len(quotas),
                "sent": sent_count,
            }

    async def handle_expired_subscriptions(self) -> dict[str, int]:
        """处理过期订阅

        标记已过期的订阅。

        Returns:
            处理结果统计
        """
        async with SessionManager.get_session() as session:
            now = datetime.now(UTC)

            # 查找已过期的订阅
            stmt = select(SubscriptionModel).where(
                and_(
                    SubscriptionModel.status != SubscriptionStatus.EXPIRED,
                    SubscriptionModel.status != SubscriptionStatus.CANCELLED,
                    SubscriptionModel.current_period_end <= now,
                    not SubscriptionModel.auto_renew,
                )
            )

            result = await session.execute(stmt)
            subscriptions = result.scalars().all()

            expired_count = 0

            for subscription in subscriptions:
                try:
                    subscription.status = SubscriptionStatus.EXPIRED
                    subscription.updated_at = now
                    await session.flush()
                    expired_count += 1
                    logger.info(f"订阅标记为过期: {subscription.subscription_id}")
                except Exception as e:
                    logger.error(f"标记订阅过期失败: {subscription.subscription_id}, 错误: {e!s}")

            return {
                "total": len(subscriptions),
                "expired": expired_count,
            }

    async def reset_monthly_quotas(self) -> dict[str, int]:
        """重置月度配额

        重置所有需要重置的月度配额。

        Returns:
            重置结果统计
        """
        async with SessionManager.get_session() as session:
            now = datetime.now(UTC)

            from backend.app.models.subscription import QuotaModel

            # 查找需要重置的配额
            stmt = select(QuotaModel).where(QuotaModel.reset_at <= now)

            result = await session.execute(stmt)
            quotas = result.scalars().all()

            reset_count = 0

            service = get_subscription_service()

            for quota in quotas:
                try:
                    await service.reset_quota(quota.subscription_id)
                    reset_count += 1
                    logger.info(f"配额重置成功: {quota.quota_id}")
                except Exception as e:
                    logger.error(f"配额重置失败: {quota.quota_id}, 错误: {e!s}")

            return {
                "total": len(quotas),
                "reset": reset_count,
            }

    async def cleanup_old_history(self, days: int = 90) -> dict[str, int]:
        """清理旧历史记录

        删除超过指定天数的历史记录。

        Args:
            days: 保留天数

        Returns:
            清理结果统计
        """
        async with SessionManager.get_session() as session:
            from backend.app.models.subscription import SubscriptionHistoryModel

            now = datetime.now(UTC)
            cutoff_date = now - timedelta(days=days)

            # 查找需要删除的历史记录
            stmt = select(SubscriptionHistoryModel).where(
                SubscriptionHistoryModel.created_at <= cutoff_date
            )

            result = await session.execute(stmt)
            histories = result.scalars().all()

            deleted_count = 0

            for history in histories:
                try:
                    await session.delete(history)
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"删除历史记录失败: {history.history_id}, 错误: {e!s}")

            await session.flush()

            return {
                "total": len(histories),
                "deleted": deleted_count,
            }

    # 私有方法

    async def _send_expiration_email(self, subscription: SubscriptionModel) -> None:
        """发送过期提醒邮件"""
        result = await send_notification(
            to=str(subscription.user_id),
            subject="订阅即将到期提醒",
            body=f"您的订阅将在近期到期，请及时续费。订阅ID: {subscription.id}",
            channel="email",
            subscription_id=str(subscription.id),
        )
        if not result.success:
            logger.error(f"过期提醒邮件发送失败: user={subscription.user_id}, error={result.error}")

    async def _send_quota_warning_email(self, quota) -> None:
        """发送配额告警邮件"""
        result = await send_notification(
            to=str(quota.user_id),
            subject="配额使用告警",
            body=f"您的配额使用率已接近上限，请关注用量。用户: {quota.user_id}",
            channel="email",
            user_id=str(quota.user_id),
        )
        if not result.success:
            logger.error(f"配额告警邮件发送失败: user={quota.user_id}, error={result.error}")


# 全局实例
_automation_service: SubscriptionAutomationService | None = None


def get_subscription_automation_service() -> SubscriptionAutomationService:
    """获取全局订阅自动化服务实例"""
    global _automation_service
    if _automation_service is None:
        _automation_service = SubscriptionAutomationService()
    return _automation_service


# 导入 or_ 操作符
from sqlalchemy import or_
