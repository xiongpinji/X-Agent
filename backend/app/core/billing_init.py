"""
计费系统初始化和集成
"""
from __future__ import annotations

import logging
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.billing import (
    Base,
    BillingModel,
    PricingTier,
    PromotionCode,
)
from backend.app.core.billing_config import BILLING_CONFIG
from backend.app.core.payment_providers import (
    PaymentProviderFactory,
    StripeProvider,
    AlipayProvider,
    WechatProvider,
)
from backend.app.core.session import SessionManager
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)


async def initialize_billing_system(
    stripe_api_key: str = None,
    alipay_app_id: str = None,
    alipay_private_key: str = None,
    alipay_public_key: str = None,
    wechat_mch_id: str = None,
    wechat_api_key: str = None,
    wechat_cert_path: str = None,
) -> None:
    """初始化计费系统"""
    logger.info("初始化计费系统...")

    # 注册支付提供商
    if stripe_api_key:
        stripe_provider = StripeProvider(stripe_api_key)
        PaymentProviderFactory.register_provider("stripe", stripe_provider)
        logger.info("Stripe支付提供商已注册")

    if alipay_app_id and alipay_private_key and alipay_public_key:
        alipay_provider = AlipayProvider(
            alipay_app_id, alipay_private_key, alipay_public_key
        )
        PaymentProviderFactory.register_provider("alipay", alipay_provider)
        logger.info("支付宝支付提供商已注册")

    if wechat_mch_id and wechat_api_key and wechat_cert_path:
        wechat_provider = WechatProvider(wechat_mch_id, wechat_api_key, wechat_cert_path)
        PaymentProviderFactory.register_provider("wechat", wechat_provider)
        logger.info("微信支付提供商已注册")

    logger.info("计费系统初始化完成")


async def create_default_pricing_tiers(tenant_id: str = "default") -> None:
    """创建默认价格层级"""
    logger.info(f"为租户 {tenant_id} 创建默认价格层级...")

    async with SessionManager.get_session() as session:
        for tier_key, tier_config in BILLING_CONFIG["pricing_tiers"].items():
            # 检查是否已存在
            from sqlalchemy import select

            stmt = select(PricingTier).where(
                (PricingTier.tenant_id == tenant_id)
                & (PricingTier.tier_name == tier_key)
            )
            result = await session.execute(stmt)
            if result.scalar_one_or_none():
                logger.info(f"价格层级 {tier_key} 已存在，跳过")
                continue

            # 创建价格层级
            pricing_tier = PricingTier(
                id=str(uuid4()),
                tenant_id=tenant_id,
                tier_name=tier_key,
                billing_model=BillingModel(tier_config["billing_model"]),
                monthly_price=(
                    Decimal(str(tier_config["monthly_price"]))
                    if tier_config.get("monthly_price")
                    else None
                ),
                annual_price=(
                    Decimal(str(tier_config["annual_price"]))
                    if tier_config.get("annual_price")
                    else None
                ),
                api_call_price=(
                    Decimal(str(tier_config["api_call_price"]))
                    if tier_config.get("api_call_price")
                    else None
                ),
                token_price=(
                    Decimal(str(tier_config["token_price"]))
                    if tier_config.get("token_price")
                    else None
                ),
                storage_price=(
                    Decimal(str(tier_config["storage_price"]))
                    if tier_config.get("storage_price")
                    else None
                ),
                monthly_api_calls=tier_config.get("monthly_api_calls"),
                monthly_tokens=tier_config.get("monthly_tokens"),
                storage_gb=tier_config.get("storage_gb"),
                concurrent_users=tier_config.get("concurrent_users"),
                features=tier_config.get("features"),
                description=tier_config.get("name"),
                is_active=True,
            )

            session.add(pricing_tier)
            logger.info(f"创建价格层级: {tier_key}")

        await session.commit()

    logger.info(f"租户 {tenant_id} 的默认价格层级创建完成")


async def create_sample_promotion_codes(tenant_id: str = "default") -> None:
    """创建示例促销代码"""
    logger.info(f"为租户 {tenant_id} 创建示例促销代码...")

    async with SessionManager.get_session() as session:
        now = datetime.now(UTC)

        sample_codes = [
            {
                "code": "WELCOME20",
                "discount_type": "percentage",
                "discount_value": Decimal("20"),
                "description": "新用户欢迎折扣",
            },
            {
                "code": "SAVE50",
                "discount_type": "percentage",
                "discount_value": Decimal("50"),
                "description": "限时50%折扣",
            },
            {
                "code": "ANNUAL100",
                "discount_type": "fixed_amount",
                "discount_value": Decimal("100"),
                "description": "年度订阅优惠",
            },
        ]

        for code_config in sample_codes:
            # 检查是否已存在
            from sqlalchemy import select

            stmt = select(PromotionCode).where(PromotionCode.code == code_config["code"])
            result = await session.execute(stmt)
            if result.scalar_one_or_none():
                logger.info(f"促销代码 {code_config['code']} 已存在，跳过")
                continue

            # 创建促销代码
            promo = PromotionCode(
                id=str(uuid4()),
                code=code_config["code"],
                discount_type=code_config["discount_type"],
                discount_value=code_config["discount_value"],
                max_uses=1000,
                current_uses=0,
                valid_from=now,
                valid_until=now + timedelta(days=365),
                is_active=True,
            )

            session.add(promo)
            logger.info(f"创建促销代码: {code_config['code']}")

        await session.commit()

    logger.info(f"租户 {tenant_id} 的示例促销代码创建完成")


async def setup_billing_database() -> None:
    """设置计费数据库"""
    logger.info("设置计费数据库...")

    # 创建表
    from backend.app.core.session import get_engine

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("计费数据库表创建完成")


# 集成到主应用

def register_billing_routes(app) -> None:
    """注册计费API路由"""
    from backend.app.api.billing import router as billing_router

    app.include_router(billing_router)
    logger.info("计费API路由已注册")


async def initialize_billing_on_startup(app) -> None:
    """应用启动时初始化计费系统"""
    logger.info("应用启动时初始化计费系统...")

    try:
        # 设置数据库
        await setup_billing_database()

        # 初始化计费系统
        await initialize_billing_system(
            stripe_api_key="sk_test_123",  # 从环境变量读取
            alipay_app_id="2021000000000000",
            alipay_private_key="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----",
            alipay_public_key="-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----",
            wechat_mch_id="1234567890",
            wechat_api_key="your_api_key",
            wechat_cert_path="/path/to/cert.pem",
        )

        # 创建默认价格层级
        await create_default_pricing_tiers()

        # 创建示例促销代码
        await create_sample_promotion_codes()

        logger.info("计费系统启动初始化完成")
    except Exception as e:
        logger.error(f"计费系统启动初始化失败: {str(e)}")
        raise


# 计费系统监控和维护

async def check_subscription_renewals() -> None:
    """检查订阅续费"""
    logger.info("检查订阅续费...")

    from sqlalchemy import select
    from backend.app.models.billing import Subscription, SubscriptionStatus

    async with SessionManager.get_session() as session:
        # 查找需要续费的订阅
        now = datetime.now(UTC)
        stmt = select(Subscription).where(
            (Subscription.status == SubscriptionStatus.ACTIVE)
            & (Subscription.auto_renew == True)
            & (Subscription.renewal_date <= now)
        )
        result = await session.execute(stmt)
        subscriptions = result.scalars().all()

        for subscription in subscriptions:
            logger.info(f"续费订阅: {subscription.id}")
            # 这里应该调用支付处理逻辑
            # 如果续费失败，标记为需要手动处理

    logger.info(f"检查完成，共处理 {len(subscriptions)} 个订阅")


async def generate_monthly_invoices() -> None:
    """生成月度发票"""
    logger.info("生成月度发票...")

    from backend.app.core.billing_engine import get_billing_engine
    from sqlalchemy import select
    from backend.app.models.billing import Subscription, SubscriptionStatus

    billing_engine = get_billing_engine()

    async with SessionManager.get_session() as session:
        # 查找所有活跃订阅
        stmt = select(Subscription).where(
            Subscription.status == SubscriptionStatus.ACTIVE
        )
        result = await session.execute(stmt)
        subscriptions = result.scalars().all()

        now = datetime.now(UTC)
        period_start = (now.replace(day=1) - timedelta(days=1)).replace(day=1)
        period_end = now.replace(day=1) - timedelta(days=1)

        for subscription in subscriptions:
            try:
                invoice = await billing_engine.generate_invoice(
                    subscription.tenant_id,
                    subscription.user_id,
                    period_start,
                    period_end,
                )
                if invoice:
                    logger.info(f"生成发票: {invoice.invoice_number}")
            except Exception as e:
                logger.error(
                    f"生成发票失败 (subscription={subscription.id}): {str(e)}"
                )

    logger.info("月度发票生成完成")


async def cleanup_expired_data() -> None:
    """清理过期数据"""
    logger.info("清理过期数据...")

    from sqlalchemy import delete
    from backend.app.models.billing import BillingHistory

    async with SessionManager.get_session() as session:
        # 删除90天前的计费历史
        cutoff_date = datetime.now(UTC) - timedelta(days=90)
        stmt = delete(BillingHistory).where(BillingHistory.created_at < cutoff_date)
        result = await session.execute(stmt)
        await session.commit()

        logger.info(f"删除 {result.rowcount} 条过期计费历史")


# 定时任务

async def setup_billing_scheduled_tasks(scheduler) -> None:
    """设置计费系统定时任务"""
    logger.info("设置计费系统定时任务...")

    # 每天检查一次订阅续费
    scheduler.add_job(
        check_subscription_renewals,
        "cron",
        hour=0,
        minute=0,
        id="check_subscription_renewals",
    )

    # 每月1号生成发票
    scheduler.add_job(
        generate_monthly_invoices,
        "cron",
        day=1,
        hour=1,
        minute=0,
        id="generate_monthly_invoices",
    )

    # 每周清理一次过期数据
    scheduler.add_job(
        cleanup_expired_data,
        "cron",
        day_of_week="sun",
        hour=2,
        minute=0,
        id="cleanup_expired_data",
    )

    logger.info("计费系统定时任务设置完成")
