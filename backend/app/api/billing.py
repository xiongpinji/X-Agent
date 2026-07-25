"""
计费API端点
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.app.core.billing_engine import get_billing_engine
from backend.app.core.payment_providers import PaymentProviderFactory
from backend.app.core.security import Principal
from backend.app.core.session import SessionManager
from backend.app.dependencies import get_current_principal
from backend.app.models.billing import (
    Invoice,
    PricingTier,
    Subscription,
    SubscriptionStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


# Pydantic模型

class PricingTierResponse(BaseModel):
    """价格层级响应"""
    id: str
    tier_name: str
    billing_model: str
    monthly_price: str | None = None
    annual_price: str | None = None
    api_call_price: str | None = None
    token_price: str | None = None
    storage_price: str | None = None
    monthly_api_calls: int | None = None
    monthly_tokens: int | None = None
    storage_gb: int | None = None
    features: dict | None = None
    description: str | None = None


class SubscriptionRequest(BaseModel):
    """订阅请求"""
    pricing_tier_id: str
    payment_method: str = Field(..., description="stripe, alipay, wechat, bank_transfer")
    payment_method_id: str
    auto_renew: bool = True
    promotion_code: str | None = None


class SubscriptionResponse(BaseModel):
    """订阅响应"""
    id: str
    status: str
    billing_model: str
    start_date: str
    end_date: str | None = None
    renewal_date: str | None = None
    auto_renew: bool
    discount_percent: str


class UsageResponse(BaseModel):
    """使用统计响应"""
    date: str
    api_calls: int
    tokens_used: int
    storage_used_gb: str
    estimated_cost: str


class QuotaResponse(BaseModel):
    """配额响应"""
    has_quota: bool
    api_calls: dict
    tokens: dict
    storage: dict


class InvoiceResponse(BaseModel):
    """发票响应"""
    id: str
    invoice_number: str
    period_start: str
    period_end: str
    issue_date: str
    due_date: str
    subtotal: str
    tax: str
    discount: str
    total: str
    status: str
    line_items: list | None = None


class PaymentRequest(BaseModel):
    """支付请求"""
    amount: str
    payment_method: str
    payment_method_id: str
    invoice_id: str | None = None


class PaymentResponse(BaseModel):
    """支付响应"""
    id: str
    amount: str
    status: str
    payment_date: str | None = None
    transaction_id: str | None = None


# API端点

@router.get("/plans", response_model=list[PricingTierResponse])
async def get_billing_plans(
    principal: Principal = Depends(get_current_principal),
) -> list[PricingTierResponse]:
    """获取计费计划"""
    async with SessionManager.get_session() as session:
        stmt = select(PricingTier).where(
            (PricingTier.tenant_id == principal.tenant_id)
            & (PricingTier.is_active)
        )
        result = await session.execute(stmt)
        tiers = result.scalars().all()

        return [
            PricingTierResponse(
                id=tier.id,
                tier_name=tier.tier_name,
                billing_model=tier.billing_model.value,
                monthly_price=str(tier.monthly_price) if tier.monthly_price else None,
                annual_price=str(tier.annual_price) if tier.annual_price else None,
                api_call_price=str(tier.api_call_price) if tier.api_call_price else None,
                token_price=str(tier.token_price) if tier.token_price else None,
                storage_price=str(tier.storage_price) if tier.storage_price else None,
                monthly_api_calls=tier.monthly_api_calls,
                monthly_tokens=tier.monthly_tokens,
                storage_gb=tier.storage_gb,
                features=tier.features,
                description=tier.description,
            )
            for tier in tiers
        ]


@router.post("/subscribe", response_model=SubscriptionResponse)
async def subscribe(
    request: SubscriptionRequest,
    principal: Principal = Depends(get_current_principal),
) -> SubscriptionResponse:
    """订阅计费计划"""
    async with SessionManager.get_session() as session:
        # 验证价格层级
        pricing_tier = await session.get(PricingTier, request.pricing_tier_id)
        if not pricing_tier or pricing_tier.tenant_id != principal.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pricing tier not found",
            )

        # 检查是否已有活跃订阅
        stmt = select(Subscription).where(
            (Subscription.tenant_id == principal.tenant_id)
            & (Subscription.user_id == principal.user_id)
            & (Subscription.status == SubscriptionStatus.ACTIVE)
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # 取消旧订阅
            existing.status = SubscriptionStatus.CANCELLED
            existing.updated_at = datetime.now(UTC)

        # 创建新订阅
        subscription = Subscription(
            id=str(uuid4()),
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            pricing_tier_id=request.pricing_tier_id,
            status=SubscriptionStatus.ACTIVE,
            billing_model=pricing_tier.billing_model,
            start_date=datetime.now(UTC),
            end_date=datetime.now(UTC) + timedelta(days=30),
            renewal_date=datetime.now(UTC) + timedelta(days=30),
            payment_method=request.payment_method,
            payment_method_id=request.payment_method_id,
            auto_renew=request.auto_renew,
        )

        session.add(subscription)
        await session.flush()

        # 应用促销代码
        if request.promotion_code:
            billing_engine = get_billing_engine()
            await billing_engine.apply_promotion_code(
                principal.tenant_id,
                principal.user_id,
                request.promotion_code,
            )

        logger.info(
            f"订阅创建: subscription={subscription.id}, "
            f"user={principal.user_id}, tier={request.pricing_tier_id}"
        )

        return SubscriptionResponse(
            id=subscription.id,
            status=subscription.status.value,
            billing_model=subscription.billing_model.value,
            start_date=subscription.start_date.isoformat(),
            end_date=subscription.end_date.isoformat() if subscription.end_date else None,
            renewal_date=subscription.renewal_date.isoformat() if subscription.renewal_date else None,
            auto_renew=subscription.auto_renew,
            discount_percent=str(subscription.discount_percent),
        )


@router.get("/usage", response_model=list[UsageResponse])
async def get_usage(
    days: int = Query(30, ge=1, le=365),
    principal: Principal = Depends(get_current_principal),
) -> list[UsageResponse]:
    """获取使用统计"""
    from backend.app.models.billing import UsageMetrics

    async with SessionManager.get_session() as session:
        start_date = datetime.now(UTC) - timedelta(days=days)
        stmt = select(UsageMetrics).where(
            (UsageMetrics.tenant_id == principal.tenant_id)
            & (UsageMetrics.user_id == principal.user_id)
            & (UsageMetrics.date >= start_date)
        )
        result = await session.execute(stmt)
        metrics = result.scalars().all()

        return [
            UsageResponse(
                date=metric.date.isoformat(),
                api_calls=metric.api_calls,
                tokens_used=metric.tokens_used,
                storage_used_gb=str(metric.storage_used_gb),
                estimated_cost=str(metric.estimated_cost),
            )
            for metric in metrics
        ]


@router.get("/quota", response_model=QuotaResponse)
async def check_quota(
    principal: Principal = Depends(get_current_principal),
) -> QuotaResponse:
    """检查配额"""
    billing_engine = get_billing_engine()
    quota_info = await billing_engine.check_quota(
        principal.tenant_id,
        principal.user_id,
    )

    if not quota_info.get("has_quota"):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=quota_info.get("reason", "No quota available"),
        )

    return QuotaResponse(**quota_info)


@router.get("/invoices", response_model=list[InvoiceResponse])
async def get_invoices(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    principal: Principal = Depends(get_current_principal),
) -> list[InvoiceResponse]:
    """获取发票列表"""
    async with SessionManager.get_session() as session:
        stmt = (
            select(Invoice)
            .where(
                (Invoice.tenant_id == principal.tenant_id)
                & (Invoice.user_id == principal.user_id)
            )
            .order_by(Invoice.issue_date.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(stmt)
        invoices = result.scalars().all()

        return [
            InvoiceResponse(
                id=invoice.id,
                invoice_number=invoice.invoice_number,
                period_start=invoice.period_start.isoformat(),
                period_end=invoice.period_end.isoformat(),
                issue_date=invoice.issue_date.isoformat(),
                due_date=invoice.due_date.isoformat(),
                subtotal=str(invoice.subtotal),
                tax=str(invoice.tax),
                discount=str(invoice.discount),
                total=str(invoice.total),
                status=invoice.status.value,
                line_items=invoice.line_items,
            )
            for invoice in invoices
        ]


@router.post("/payment", response_model=PaymentResponse)
async def process_payment(
    request: PaymentRequest,
    principal: Principal = Depends(get_current_principal),
) -> PaymentResponse:
    """处理支付"""
    billing_engine = get_billing_engine()

    # 验证支付提供商
    provider = PaymentProviderFactory.get_provider(request.payment_method)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported payment method: {request.payment_method}",
        )

    # 处理支付
    payment = await billing_engine.process_payment(
        principal.tenant_id,
        principal.user_id,
        Decimal(request.amount),
        request.payment_method,
        request.payment_method_id,
        request.invoice_id,
    )

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment processing failed",
        )

    return PaymentResponse(
        id=payment.id,
        amount=str(payment.amount),
        status=payment.status.value,
        payment_date=payment.payment_date.isoformat() if payment.payment_date else None,
        transaction_id=payment.transaction_id,
    )


@router.post("/apply-promo-code")
async def apply_promo_code(
    code: str = Query(...),
    principal: Principal = Depends(get_current_principal),
) -> dict:
    """应用促销代码"""
    billing_engine = get_billing_engine()
    result = await billing_engine.apply_promotion_code(
        principal.tenant_id,
        principal.user_id,
        code,
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to apply promotion code"),
        )

    return result


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    principal: Principal = Depends(get_current_principal),
) -> SubscriptionResponse:
    """获取当前订阅"""
    async with SessionManager.get_session() as session:
        stmt = select(Subscription).where(
            (Subscription.tenant_id == principal.tenant_id)
            & (Subscription.user_id == principal.user_id)
            & (Subscription.status == SubscriptionStatus.ACTIVE)
        )
        result = await session.execute(stmt)
        subscription = result.scalar_one_or_none()

        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active subscription",
            )

        return SubscriptionResponse(
            id=subscription.id,
            status=subscription.status.value,
            billing_model=subscription.billing_model.value,
            start_date=subscription.start_date.isoformat(),
            end_date=subscription.end_date.isoformat() if subscription.end_date else None,
            renewal_date=subscription.renewal_date.isoformat() if subscription.renewal_date else None,
            auto_renew=subscription.auto_renew,
            discount_percent=str(subscription.discount_percent),
        )


@router.post("/cancel-subscription")
async def cancel_subscription(
    principal: Principal = Depends(get_current_principal),
) -> dict:
    """取消订阅"""
    async with SessionManager.get_session() as session:
        stmt = select(Subscription).where(
            (Subscription.tenant_id == principal.tenant_id)
            & (Subscription.user_id == principal.user_id)
            & (Subscription.status == SubscriptionStatus.ACTIVE)
        )
        result = await session.execute(stmt)
        subscription = result.scalar_one_or_none()

        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active subscription",
            )

        subscription.status = SubscriptionStatus.CANCELLED
        subscription.updated_at = datetime.now(UTC)
        await session.flush()

        logger.info(
            f"订阅取消: subscription={subscription.id}, user={principal.user_id}"
        )

        return {
            "success": True,
            "message": "Subscription cancelled successfully",
        }
