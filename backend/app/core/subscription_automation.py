"""
订阅自动化流程 - 处理自动续费、过期提醒、支付重试等
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.notifications import notification_service
from backend.app.core.session import SessionManager
from backend.app.core.subscription_manager import (
    SubscriptionEvent,
    get_subscription_manager,
)
from backend.app.models.billing import (
    BillingHistory,
    Invoice,
    InvoiceStatus,
    Payment,
    PaymentStatus,
    PricingTier,
    Subscription,
    SubscriptionStatus,
)

logger = logging.getLogger(__name__)


class SubscriptionAutomation:
    """订阅自动化处理"""

    async def process_auto_renewals(self) -> dict:
        """处理自动续费（每日定时任务）"""
        async with SessionManager.get_session() as session:
            # 查找需要续费的订阅（续费日期 <= 今天）
            now = datetime.now(UTC)
            stmt = select(Subscription).where(
                and_(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.auto_renew,
                    Subscription.renewal_date <= now,
                )
            )
            result = await session.execute(stmt)
            subscriptions = result.scalars().all()

            success_count = 0
            failed_count = 0
            failed_subscriptions = []

            for subscription in subscriptions:
                try:
                    # 创建续费发票
                    invoice = await self._create_renewal_invoice(
                        session, subscription
                    )

                    # 处理支付
                    payment_result = await self._process_renewal_payment(
                        session, subscription, invoice
                    )

                    if payment_result.get("success"):
                        # 续费订阅
                        subscription_manager = get_subscription_manager()
                        await subscription_manager.renew_subscription(
                            subscription.tenant_id,
                            subscription.user_id,
                        )
                        success_count += 1

                        logger.info(
                            f"自动续费成功: subscription={subscription.id}, "
                            f"invoice={invoice.id}"
                        )
                    else:
                        failed_count += 1
                        failed_subscriptions.append(
                            {
                                "subscription_id": subscription.id,
                                "reason": payment_result.get("error"),
                            }
                        )

                        logger.warning(
                            f"自动续费失败: subscription={subscription.id}, "
                            f"error={payment_result.get('error')}"
                        )

                except Exception as e:
                    failed_count += 1
                    failed_subscriptions.append(
                        {
                            "subscription_id": subscription.id,
                            "reason": str(e),
                        }
                    )
                    logger.error(
                        f"自动续费异常: subscription={subscription.id}, "
                        f"error={e!s}"
                    )

            await session.commit()

            return {
                "total": len(subscriptions),
                "success": success_count,
                "failed": failed_count,
                "failed_subscriptions": failed_subscriptions,
            }

    async def send_expiration_reminders(self) -> dict:
        """发送过期提醒"""
        async with SessionManager.get_session() as session:
            now = datetime.now(UTC)
            reminders_sent = 0

            # 7天前提醒
            seven_days_later = now + timedelta(days=7)
            stmt = select(Subscription).where(
                and_(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.renewal_date >= seven_days_later,
                    Subscription.renewal_date < seven_days_later + timedelta(hours=1),
                )
            )
            result = await session.execute(stmt)
            subscriptions = result.scalars().all()

            for subscription in subscriptions:
                await self._send_expiration_reminder(
                    session, subscription, days_until_expiration=7
                )
                reminders_sent += 1

            # 3天前提醒
            three_days_later = now + timedelta(days=3)
            stmt = select(Subscription).where(
                and_(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.renewal_date >= three_days_later,
                    Subscription.renewal_date < three_days_later + timedelta(hours=1),
                )
            )
            result = await session.execute(stmt)
            subscriptions = result.scalars().all()

            for subscription in subscriptions:
                await self._send_expiration_reminder(
                    session, subscription, days_until_expiration=3
                )
                reminders_sent += 1

            # 1天前提醒
            one_day_later = now + timedelta(days=1)
            stmt = select(Subscription).where(
                and_(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.renewal_date >= one_day_later,
                    Subscription.renewal_date < one_day_later + timedelta(hours=1),
                )
            )
            result = await session.execute(stmt)
            subscriptions = result.scalars().all()

            for subscription in subscriptions:
                await self._send_expiration_reminder(
                    session, subscription, days_until_expiration=1
                )
                reminders_sent += 1

            await session.commit()

            return {
                "reminders_sent": reminders_sent,
            }

    async def handle_expired_subscriptions(self) -> dict:
        """处理过期订阅"""
        async with SessionManager.get_session() as session:
            now = datetime.now(UTC)

            # 查找已过期的订阅
            stmt = select(Subscription).where(
                and_(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.renewal_date < now,
                )
            )
            result = await session.execute(stmt)
            subscriptions = result.scalars().all()

            expired_count = 0

            for subscription in subscriptions:
                subscription.status = SubscriptionStatus.EXPIRED
                subscription.updated_at = now

                # 记录事件
                event = BillingHistory(
                    id=str(uuid4()),
                    tenant_id=subscription.tenant_id,
                    user_id=subscription.user_id,
                    event_type=SubscriptionEvent.EXPIRED.value,
                    subscription_id=subscription.id,
                    details={"expired_at": now.isoformat()},
                )
                session.add(event)

                expired_count += 1

                logger.info(
                    f"订阅过期: subscription={subscription.id}, "
                    f"user={subscription.user_id}"
                )

            await session.commit()

            return {
                "expired_count": expired_count,
            }

    async def retry_failed_payments(self) -> dict:
        """重试失败的支付（最多3次）"""
        async with SessionManager.get_session() as session:
            # 查找失败的支付
            stmt = select(Payment).where(
                and_(
                    Payment.status == PaymentStatus.FAILED,
                )
            )
            result = await session.execute(stmt)
            payments = result.scalars().all()

            retry_count = 0
            success_count = 0

            for payment in payments:
                # 检查重试次数
                retry_times = payment.extra_metadata.get("retry_times", 0) if payment.extra_metadata else 0
                if retry_times >= 3:
                    logger.warning(
                        f"支付重试次数已达上限: payment={payment.id}"
                    )
                    continue

                try:
                    # 重试支付
                    # NOTE: Requires real payment SDK integration (Stripe/PayPal)
                    retry_count += 1

                    # 更新重试次数
                    payment.extra_metadata = payment.extra_metadata or {}
                    payment.extra_metadata["retry_times"] = retry_times + 1
                    payment.extra_metadata["last_retry_at"] = datetime.now(UTC).isoformat()

                    logger.info(
                        f"支付重试: payment={payment.id}, "
                        f"retry_times={retry_times + 1}"
                    )

                except Exception as e:
                    logger.error(
                        f"支付重试异常: payment={payment.id}, error={e!s}"
                    )

            await session.commit()

            return {
                "retry_count": retry_count,
                "success_count": success_count,
            }

    # 私有方法

    async def _create_renewal_invoice(
        self, session: AsyncSession, subscription: Subscription
    ) -> Invoice:
        """创建续费发票"""
        pricing_tier = await session.get(
            PricingTier, subscription.pricing_tier_id
        )
        if not pricing_tier:
            raise ValueError(f"Pricing tier not found: {subscription.pricing_tier_id}")

        now = datetime.now(UTC)
        invoice_number = f"INV-{now.strftime('%Y%m%d')}-{str(uuid4())[:8].upper()}"

        # 计算金额
        subtotal = pricing_tier.monthly_price or Decimal(0)
        tax = subtotal * Decimal("0.1")  # 假设10%税率
        discount = Decimal(0)
        total = subtotal + tax - discount

        invoice = Invoice(
            id=str(uuid4()),
            invoice_number=invoice_number,
            tenant_id=subscription.tenant_id,
            user_id=subscription.user_id,
            subscription_id=subscription.id,
            period_start=subscription.start_date,
            period_end=subscription.end_date,
            issue_date=now,
            due_date=now + timedelta(days=30),
            subtotal=subtotal,
            tax=tax,
            discount=discount,
            total=total,
            status=InvoiceStatus.ISSUED,
            line_items=[
                {
                    "description": f"Subscription renewal - {pricing_tier.tier_name}",
                    "quantity": 1,
                    "unit_price": str(subtotal),
                    "amount": str(subtotal),
                }
            ],
        )

        session.add(invoice)
        return invoice

    async def _process_renewal_payment(
        self,
        session: AsyncSession,
        subscription: Subscription,
        invoice: Invoice,
    ) -> dict:
        """处理续费支付"""
        # NOTE: Requires real payment SDK integration (Stripe/PayPal)
        # 这里是简化实现

        payment = Payment(
            id=str(uuid4()),
            tenant_id=subscription.tenant_id,
            user_id=subscription.user_id,
            subscription_id=subscription.id,
            payment_method=subscription.payment_method,
            payment_method_id=subscription.payment_method_id,
            amount=invoice.total,
            status=PaymentStatus.COMPLETED,
            payment_date=datetime.now(UTC),
            transaction_id=f"TXN-{str(uuid4())[:8].upper()}",
        )

        session.add(payment)

        # 更新发票状态
        invoice.status = InvoiceStatus.PAID
        invoice.paid_date = datetime.now(UTC)
        invoice.payment_id = payment.id

        return {
            "success": True,
            "payment_id": payment.id,
        }

    async def _send_expiration_reminder(
        self,
        session: AsyncSession,
        subscription: Subscription,
        days_until_expiration: int,
    ) -> None:
        """发送过期提醒"""
        # 记录提醒事件
        event = BillingHistory(
            id=str(uuid4()),
            tenant_id=subscription.tenant_id,
            user_id=subscription.user_id,
            event_type="subscription_expiration_reminder",
            subscription_id=subscription.id,
            details={
                "days_until_expiration": days_until_expiration,
                "renewal_date": subscription.renewal_date.isoformat()
                if subscription.renewal_date
                else None,
            },
        )
        session.add(event)

        logger.info(
            f"过期提醒: subscription={subscription.id}, "
            f"user={subscription.user_id}, "
            f"days_until_expiration={days_until_expiration}"
        )

        await notification_service.send_email(
            to=subscription.user_id,
            subject=f"订阅即将到期提醒 ({days_until_expiration}天)",
            body=f"您的订阅 {subscription.id} 将在 {days_until_expiration} 天后到期，请及时续费。",
        )


# 全局实例
_subscription_automation: SubscriptionAutomation | None = None


def get_subscription_automation() -> SubscriptionAutomation:
    """获取订阅自动化处理实例"""
    global _subscription_automation
    if _subscription_automation is None:
        _subscription_automation = SubscriptionAutomation()
    return _subscription_automation
