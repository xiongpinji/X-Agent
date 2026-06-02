"""
计费引擎 - 核心计费逻辑
支持按量计费、订阅计费、混合计费
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.billing import (
    BillingModel,
    Invoice,
    InvoiceStatus,
    Payment,
    PaymentStatus,
    PricingTier,
    PromotionCode,
    QuotaUsage,
    Subscription,
    SubscriptionStatus,
    UsageMetrics,
    BillingHistory,
)
from backend.app.core.session import SessionManager

logger = logging.getLogger(__name__)


class BillingEngine:
    """计费引擎 - 处理所有计费逻辑"""

    async def calculate_usage_cost(
        self,
        tenant_id: str,
        user_id: str,
        api_calls: int = 0,
        tokens_used: int = 0,
        storage_gb: Decimal = Decimal(0),
    ) -> Decimal:
        """计算使用成本"""
        subscription = await self._get_active_subscription(tenant_id, user_id)
        if not subscription:
            return Decimal(0)

        pricing_tier = await self._get_pricing_tier(subscription.pricing_tier_id)
        if not pricing_tier:
            return Decimal(0)

        cost = Decimal(0)

        # 按量计费
        if pricing_tier.api_call_price:
            cost += Decimal(api_calls) * pricing_tier.api_call_price

        if pricing_tier.token_price:
            cost += Decimal(tokens_used) * pricing_tier.token_price

        if pricing_tier.storage_price:
            cost += storage_gb * pricing_tier.storage_price

        return cost

    async def record_usage(
        self,
        tenant_id: str,
        user_id: str,
        api_calls: int = 0,
        tokens_used: int = 0,
        storage_gb: Decimal = Decimal(0),
    ) -> UsageMetrics:
        """记录使用指标"""
        async with SessionManager.get_session() as session:
            # 获取活跃订阅
            subscription = await self._get_active_subscription(tenant_id, user_id)

            # 计算成本
            cost = await self.calculate_usage_cost(
                tenant_id, user_id, api_calls, tokens_used, storage_gb
            )

            # 创建使用记录
            usage = UsageMetrics(
                id=str(uuid4()),
                tenant_id=tenant_id,
                user_id=user_id,
                subscription_id=subscription.id if subscription else None,
                date=datetime.now(UTC),
                api_calls=api_calls,
                tokens_used=tokens_used,
                storage_used_gb=storage_gb,
                estimated_cost=cost,
            )

            session.add(usage)
            await session.flush()

            # 更新配额使用
            if subscription:
                await self._update_quota_usage(
                    session, subscription.id, api_calls, tokens_used, storage_gb
                )

            # 记录历史
            await self._record_billing_history(
                session,
                tenant_id,
                user_id,
                "usage_recorded",
                usage_id=usage.id,
                details={
                    "api_calls": api_calls,
                    "tokens_used": tokens_used,
                    "storage_gb": str(storage_gb),
                    "cost": str(cost),
                },
            )

            logger.info(
                f"使用记录: tenant={tenant_id}, user={user_id}, "
                f"api_calls={api_calls}, tokens={tokens_used}, cost={cost}"
            )

            return usage

    async def generate_invoice(
        self,
        tenant_id: str,
        user_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> Optional[Invoice]:
        """生成发票"""
        async with SessionManager.get_session() as session:
            # 获取订阅
            subscription = await self._get_active_subscription(tenant_id, user_id)
            if not subscription:
                logger.warning(f"未找到活跃订阅: {tenant_id}/{user_id}")
                return None

            pricing_tier = await self._get_pricing_tier(subscription.pricing_tier_id)
            if not pricing_tier:
                return None

            # 获取使用数据
            usage_records = await self._get_usage_records(
                session, tenant_id, user_id, period_start, period_end
            )

            # 计算金额
            line_items = []
            subtotal = Decimal(0)

            # 订阅费用
            if pricing_tier.monthly_price:
                line_items.append({
                    "description": f"{pricing_tier.tier_name} 订阅费",
                    "quantity": 1,
                    "unit_price": str(pricing_tier.monthly_price),
                    "amount": str(pricing_tier.monthly_price),
                })
                subtotal += pricing_tier.monthly_price

            # 按量计费
            for usage in usage_records:
                if usage.estimated_cost > 0:
                    line_items.append({
                        "description": f"使用费 ({usage.date.strftime('%Y-%m-%d')})",
                        "quantity": 1,
                        "unit_price": str(usage.estimated_cost),
                        "amount": str(usage.estimated_cost),
                    })
                    subtotal += usage.estimated_cost

            # 应用折扣
            discount = Decimal(0)
            if subscription.discount_percent > 0:
                discount = subtotal * (subscription.discount_percent / 100)

            # 计算税费（示例：10%）
            tax = (subtotal - discount) * Decimal("0.1")

            total = subtotal - discount + tax

            # 创建发票
            invoice = Invoice(
                id=str(uuid4()),
                invoice_number=await self._generate_invoice_number(session, tenant_id),
                tenant_id=tenant_id,
                user_id=user_id,
                subscription_id=subscription.id,
                period_start=period_start,
                period_end=period_end,
                issue_date=datetime.now(UTC),
                due_date=datetime.now(UTC) + timedelta(days=30),
                subtotal=subtotal,
                tax=tax,
                discount=discount,
                total=total,
                status=InvoiceStatus.ISSUED,
                line_items=line_items,
            )

            session.add(invoice)
            await session.flush()

            # 记录历史
            await self._record_billing_history(
                session,
                tenant_id,
                user_id,
                "invoice_generated",
                invoice_id=invoice.id,
                details={
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "total": str(total),
                },
            )

            logger.info(
                f"发票生成: invoice={invoice.invoice_number}, "
                f"total={total}, user={user_id}"
            )

            return invoice

    async def process_payment(
        self,
        tenant_id: str,
        user_id: str,
        amount: Decimal,
        payment_method: str,
        payment_method_id: str,
        invoice_id: Optional[str] = None,
    ) -> Optional[Payment]:
        """处理支付"""
        async with SessionManager.get_session() as session:
            # 创建支付记录
            payment = Payment(
                id=str(uuid4()),
                tenant_id=tenant_id,
                user_id=user_id,
                payment_method=payment_method,
                payment_method_id=payment_method_id,
                amount=amount,
                status=PaymentStatus.PENDING,
            )

            session.add(payment)
            await session.flush()

            # 调用第三方支付API（这里是占位符）
            success = await self._process_third_party_payment(
                payment, payment_method, payment_method_id, amount
            )

            if success:
                payment.status = PaymentStatus.COMPLETED
                payment.payment_date = datetime.now(UTC)

                # 更新发票状态
                if invoice_id:
                    invoice = await session.get(Invoice, invoice_id)
                    if invoice:
                        invoice.status = InvoiceStatus.PAID
                        invoice.paid_date = datetime.now(UTC)
                        invoice.payment_id = payment.id

                # 更新订阅
                subscription = await self._get_active_subscription(tenant_id, user_id)
                if subscription and subscription.end_date:
                    # 延长订阅期限
                    subscription.end_date = subscription.end_date + timedelta(days=30)
                    subscription.renewal_date = subscription.end_date

                logger.info(
                    f"支付成功: payment={payment.id}, amount={amount}, user={user_id}"
                )
            else:
                payment.status = PaymentStatus.FAILED
                logger.warning(
                    f"支付失败: payment={payment.id}, amount={amount}, user={user_id}"
                )

            await session.flush()

            # 记录历史
            await self._record_billing_history(
                session,
                tenant_id,
                user_id,
                "payment_processed",
                payment_id=payment.id,
                details={
                    "amount": str(amount),
                    "status": payment.status,
                    "method": payment_method,
                },
            )

            return payment

    async def check_quota(
        self,
        tenant_id: str,
        user_id: str,
    ) -> dict:
        """检查配额使用情况"""
        async with SessionManager.get_session() as session:
            subscription = await self._get_active_subscription(tenant_id, user_id)
            if not subscription:
                return {"has_quota": False, "reason": "No active subscription"}

            pricing_tier = await self._get_pricing_tier(subscription.pricing_tier_id)
            if not pricing_tier:
                return {"has_quota": False, "reason": "Invalid pricing tier"}

            # 获取当前配额使用
            quota = await self._get_current_quota_usage(session, subscription.id)

            return {
                "has_quota": True,
                "api_calls": {
                    "used": quota.api_calls_used,
                    "limit": quota.api_calls_limit,
                    "remaining": (quota.api_calls_limit - quota.api_calls_used)
                    if quota.api_calls_limit
                    else None,
                    "warning": quota.api_calls_warning,
                },
                "tokens": {
                    "used": quota.tokens_used,
                    "limit": quota.tokens_limit,
                    "remaining": (quota.tokens_limit - quota.tokens_used)
                    if quota.tokens_limit
                    else None,
                    "warning": quota.tokens_warning,
                },
                "storage": {
                    "used": str(quota.storage_used_gb),
                    "limit": quota.storage_limit_gb,
                    "remaining": (quota.storage_limit_gb - quota.storage_used_gb)
                    if quota.storage_limit_gb
                    else None,
                    "warning": quota.storage_warning,
                },
            }

    async def apply_promotion_code(
        self,
        tenant_id: str,
        user_id: str,
        code: str,
    ) -> dict:
        """应用促销代码"""
        async with SessionManager.get_session() as session:
            # 查找促销代码
            stmt = select(PromotionCode).where(PromotionCode.code == code)
            result = await session.execute(stmt)
            promo = result.scalar_one_or_none()

            if not promo:
                return {"success": False, "error": "Invalid promotion code"}

            if not promo.is_active:
                return {"success": False, "error": "Promotion code is inactive"}

            now = datetime.now(UTC)
            # DateTime(timezone=True) 在 Postgres 下读回 aware,但 SQLite 不持久化
            # 时区,读回是 naive。统一把 naive 视为 UTC,避免 aware/naive 比较 TypeError。
            valid_from = promo.valid_from
            valid_until = promo.valid_until
            if valid_from is not None and valid_from.tzinfo is None:
                valid_from = valid_from.replace(tzinfo=UTC)
            if valid_until is not None and valid_until.tzinfo is None:
                valid_until = valid_until.replace(tzinfo=UTC)
            if now < valid_from or now > valid_until:
                return {"success": False, "error": "Promotion code expired"}

            if promo.max_uses and promo.current_uses >= promo.max_uses:
                return {"success": False, "error": "Promotion code usage limit reached"}

            # 获取订阅
            subscription = await self._get_active_subscription(tenant_id, user_id)
            if not subscription:
                return {"success": False, "error": "No active subscription"}

            # 应用折扣
            if promo.discount_type == "percentage":
                subscription.discount_percent = promo.discount_value
            elif promo.discount_type == "fixed_amount":
                # 固定金额折扣需要特殊处理
                pass

            promo.current_uses += 1
            await session.flush()

            logger.info(
                f"促销代码应用: code={code}, user={user_id}, "
                f"discount={promo.discount_value}"
            )

            return {
                "success": True,
                "discount_type": promo.discount_type,
                "discount_value": str(promo.discount_value),
            }

    # 私有方法

    async def _get_active_subscription(
        self, tenant_id: str, user_id: str
    ) -> Optional[Subscription]:
        """获取活跃订阅"""
        async with SessionManager.get_session() as session:
            stmt = select(Subscription).where(
                (Subscription.tenant_id == tenant_id)
                & (Subscription.user_id == user_id)
                & (Subscription.status == SubscriptionStatus.ACTIVE)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def _get_pricing_tier(self, tier_id: str) -> Optional[PricingTier]:
        """获取价格层级"""
        async with SessionManager.get_session() as session:
            return await session.get(PricingTier, tier_id)

    async def _get_usage_records(
        self,
        session: AsyncSession,
        tenant_id: str,
        user_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> list[UsageMetrics]:
        """获取使用记录"""
        stmt = select(UsageMetrics).where(
            (UsageMetrics.tenant_id == tenant_id)
            & (UsageMetrics.user_id == user_id)
            & (UsageMetrics.date >= period_start)
            & (UsageMetrics.date <= period_end)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def _update_quota_usage(
        self,
        session: AsyncSession,
        subscription_id: str,
        api_calls: int,
        tokens_used: int,
        storage_gb: Decimal,
    ) -> None:
        """更新配额使用"""
        quota = await self._get_current_quota_usage(session, subscription_id)
        if quota:
            quota.api_calls_used += api_calls
            quota.tokens_used += tokens_used
            quota.storage_used_gb += storage_gb
            quota.updated_at = datetime.now(UTC)

            # 检查警告
            if quota.api_calls_limit and quota.api_calls_used >= quota.api_calls_limit * 0.8:
                quota.api_calls_warning = True
            if quota.tokens_limit and quota.tokens_used >= quota.tokens_limit * 0.8:
                quota.tokens_warning = True
            if quota.storage_limit_gb and quota.storage_used_gb >= quota.storage_limit_gb * 0.8:
                quota.storage_warning = True

    async def _get_current_quota_usage(
        self, session: AsyncSession, subscription_id: str
    ) -> Optional[QuotaUsage]:
        """获取当前配额使用"""
        now = datetime.now(UTC)
        stmt = select(QuotaUsage).where(
            (QuotaUsage.subscription_id == subscription_id)
            & (QuotaUsage.period_start <= now)
            & (QuotaUsage.period_end >= now)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _generate_invoice_number(
        self, session: AsyncSession, tenant_id: str
    ) -> str:
        """生成发票号"""
        now = datetime.now(UTC)
        date_str = now.strftime("%Y%m%d")
        # 简单的发票号生成逻辑
        return f"INV-{tenant_id[:4]}-{date_str}-{str(uuid4())[:8].upper()}"

    async def _process_third_party_payment(
        self,
        payment: Payment,
        payment_method: str,
        payment_method_id: str,
        amount: Decimal,
    ) -> bool:
        """处理第三方支付（占位符）"""
        # 这里应该调用实际的支付API
        # 例如：Stripe、支付宝、微信支付
        logger.info(
            f"处理第三方支付: method={payment_method}, "
            f"amount={amount}, payment_id={payment.id}"
        )
        # 模拟成功
        return True

    async def _record_billing_history(
        self,
        session: AsyncSession,
        tenant_id: str,
        user_id: str,
        event_type: str,
        **kwargs,
    ) -> None:
        """记录计费历史"""
        history = BillingHistory(
            id=str(uuid4()),
            tenant_id=tenant_id,
            user_id=user_id,
            event_type=event_type,
            subscription_id=kwargs.get("subscription_id"),
            invoice_id=kwargs.get("invoice_id"),
            payment_id=kwargs.get("payment_id"),
            details=kwargs.get("details"),
        )
        session.add(history)


# 全局实例
_billing_engine: BillingEngine | None = None


def get_billing_engine() -> BillingEngine:
    """获取全局计费引擎实例"""
    global _billing_engine
    if _billing_engine is None:
        _billing_engine = BillingEngine()
    return _billing_engine
