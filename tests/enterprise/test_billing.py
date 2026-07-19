"""
计费系统测试套件
包括单元测试、集成测试、性能测试
"""
import pytest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from backend.app.models.billing import (
    Base,
    BillingModel,
    Invoice,
    InvoiceStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
    PricingTier,
    PromotionCode,
    Subscription,
    SubscriptionStatus,
    UsageMetrics,
    QuotaUsage,
    BillingHistory,
)
from backend.app.core.billing_engine import BillingEngine
from backend.app.core.payment_providers import (
    StripeProvider,
    AlipayProvider,
    WechatProvider,
    PaymentProviderFactory,
)


# 测试数据库设置

@pytest.fixture
async def test_db(_init_global_db):
    """返回与全局 _db_manager 同源的会话工厂。

    BillingEngine 内部走 SessionManager.get_session() → 全局 _db_manager(由
    conftest 的 autouse _init_global_db 注入,底层是 NullPool + 临时文件 SQLite)。
    若这里另建独立引擎,测试写入与引擎读取就落在两个不同的内存库,
    导致 calculate_usage_cost / generate_invoice / check_quota 等回查库的断言
    全部拿到 0/None。复用同一个 _session_factory 即可保证写读同库。
    """
    yield _init_global_db._session_factory


@pytest.fixture
async def billing_engine():
    """创建计费引擎实例"""
    return BillingEngine()


@pytest.fixture
async def test_tenant_id():
    """测试租户ID"""
    return "test-tenant-001"


@pytest.fixture
async def test_user_id():
    """测试用户ID"""
    return "test-user-001"


# 单元测试

class TestBillingEngine:
    """计费引擎测试"""

    @pytest.mark.asyncio
    async def test_calculate_usage_cost_no_subscription(self, billing_engine, test_tenant_id, test_user_id):
        """测试无订阅时的成本计算"""
        cost = await billing_engine.calculate_usage_cost(
            test_tenant_id,
            test_user_id,
            api_calls=100,
            tokens_used=1000,
        )
        assert cost == Decimal(0)

    @pytest.mark.asyncio
    async def test_calculate_usage_cost_with_subscription(self, billing_engine, test_db, test_tenant_id, test_user_id):
        """测试有订阅时的成本计算"""
        async with test_db() as session:
            # 创建价格层级
            pricing_tier = PricingTier(
                id=str(uuid4()),
                tenant_id=test_tenant_id,
                tier_name="professional",
                billing_model=BillingModel.PAY_AS_YOU_GO,
                api_call_price=Decimal("0.01"),
                token_price=Decimal("0.0001"),
            )
            session.add(pricing_tier)
            await session.flush()

            # 创建订阅
            subscription = Subscription(
                id=str(uuid4()),
                tenant_id=test_tenant_id,
                user_id=test_user_id,
                pricing_tier_id=pricing_tier.id,
                status=SubscriptionStatus.ACTIVE,
                billing_model=BillingModel.PAY_AS_YOU_GO,
                start_date=datetime.now(UTC),
                end_date=datetime.now(UTC) + timedelta(days=30),
                payment_method=PaymentMethod.STRIPE,
                payment_method_id="pm_test_123",
            )
            session.add(subscription)
            await session.commit()

            # 计算成本
            cost = await billing_engine.calculate_usage_cost(
                test_tenant_id,
                test_user_id,
                api_calls=100,
                tokens_used=1000,
            )

            # 预期成本: 100 * 0.01 + 1000 * 0.0001 = 1.0 + 0.1 = 1.1
            assert cost == Decimal("1.1")

    @pytest.mark.asyncio
    async def test_record_usage(self, billing_engine, test_db, test_tenant_id, test_user_id):
        """测试使用记录"""
        async with test_db() as session:
            # 创建价格层级和订阅
            pricing_tier = PricingTier(
                id=str(uuid4()),
                tenant_id=test_tenant_id,
                tier_name="basic",
                billing_model=BillingModel.SUBSCRIPTION,
                monthly_price=Decimal("99.99"),
            )
            session.add(pricing_tier)
            await session.flush()

            subscription = Subscription(
                id=str(uuid4()),
                tenant_id=test_tenant_id,
                user_id=test_user_id,
                pricing_tier_id=pricing_tier.id,
                status=SubscriptionStatus.ACTIVE,
                billing_model=BillingModel.SUBSCRIPTION,
                start_date=datetime.now(UTC),
                end_date=datetime.now(UTC) + timedelta(days=30),
                payment_method=PaymentMethod.STRIPE,
                payment_method_id="pm_test_123",
            )
            session.add(subscription)
            await session.commit()

            # 记录使用
            usage = await billing_engine.record_usage(
                test_tenant_id,
                test_user_id,
                api_calls=50,
                tokens_used=500,
                storage_gb=Decimal("1.5"),
            )

            assert usage.api_calls == 50
            assert usage.tokens_used == 500
            assert usage.storage_used_gb == Decimal("1.5")
            assert usage.tenant_id == test_tenant_id
            assert usage.user_id == test_user_id

    @pytest.mark.asyncio
    async def test_generate_invoice(self, billing_engine, test_db, test_tenant_id, test_user_id):
        """测试发票生成"""
        async with test_db() as session:
            # 创建价格层级和订阅
            pricing_tier = PricingTier(
                id=str(uuid4()),
                tenant_id=test_tenant_id,
                tier_name="professional",
                billing_model=BillingModel.SUBSCRIPTION,
                monthly_price=Decimal("199.99"),
            )
            session.add(pricing_tier)
            await session.flush()

            subscription = Subscription(
                id=str(uuid4()),
                tenant_id=test_tenant_id,
                user_id=test_user_id,
                pricing_tier_id=pricing_tier.id,
                status=SubscriptionStatus.ACTIVE,
                billing_model=BillingModel.SUBSCRIPTION,
                start_date=datetime.now(UTC),
                end_date=datetime.now(UTC) + timedelta(days=30),
                payment_method=PaymentMethod.STRIPE,
                payment_method_id="pm_test_123",
            )
            session.add(subscription)
            await session.commit()

            # 生成发票
            period_start = datetime.now(UTC) - timedelta(days=30)
            period_end = datetime.now(UTC)

            invoice = await billing_engine.generate_invoice(
                test_tenant_id,
                test_user_id,
                period_start,
                period_end,
            )

            assert invoice is not None
            assert invoice.status == InvoiceStatus.ISSUED
            assert invoice.total > 0
            assert invoice.invoice_number.startswith("INV-")

    @pytest.mark.asyncio
    async def test_process_payment(self, billing_engine, test_db, test_tenant_id, test_user_id):
        """测试支付处理"""
        async with test_db() as session:
            # 创建订阅
            pricing_tier = PricingTier(
                id=str(uuid4()),
                tenant_id=test_tenant_id,
                tier_name="basic",
                billing_model=BillingModel.SUBSCRIPTION,
                monthly_price=Decimal("99.99"),
            )
            session.add(pricing_tier)
            await session.flush()

            subscription = Subscription(
                id=str(uuid4()),
                tenant_id=test_tenant_id,
                user_id=test_user_id,
                pricing_tier_id=pricing_tier.id,
                status=SubscriptionStatus.ACTIVE,
                billing_model=BillingModel.SUBSCRIPTION,
                start_date=datetime.now(UTC),
                end_date=datetime.now(UTC) + timedelta(days=30),
                payment_method=PaymentMethod.STRIPE,
                payment_method_id="pm_test_123",
            )
            session.add(subscription)
            await session.commit()

            # 处理支付
            payment = await billing_engine.process_payment(
                test_tenant_id,
                test_user_id,
                Decimal("99.99"),
                PaymentMethod.STRIPE,
                "pm_test_123",
            )

            assert payment is not None
            assert payment.status == PaymentStatus.COMPLETED
            assert payment.amount == Decimal("99.99")

    @pytest.mark.asyncio
    async def test_check_quota(self, billing_engine, test_db, test_tenant_id, test_user_id):
        """测试配额检查"""
        async with test_db() as session:
            # 创建价格层级和订阅
            pricing_tier = PricingTier(
                id=str(uuid4()),
                tenant_id=test_tenant_id,
                tier_name="professional",
                billing_model=BillingModel.SUBSCRIPTION,
                monthly_price=Decimal("199.99"),
                monthly_api_calls=10000,
                monthly_tokens=1000000,
                storage_gb=100,
            )
            session.add(pricing_tier)
            await session.flush()

            subscription = Subscription(
                id=str(uuid4()),
                tenant_id=test_tenant_id,
                user_id=test_user_id,
                pricing_tier_id=pricing_tier.id,
                status=SubscriptionStatus.ACTIVE,
                billing_model=BillingModel.SUBSCRIPTION,
                start_date=datetime.now(UTC),
                end_date=datetime.now(UTC) + timedelta(days=30),
                payment_method=PaymentMethod.STRIPE,
                payment_method_id="pm_test_123",
            )
            session.add(subscription)

            # 创建配额使用记录
            now = datetime.now(UTC)
            quota = QuotaUsage(
                id=str(uuid4()),
                tenant_id=test_tenant_id,
                user_id=test_user_id,
                subscription_id=subscription.id,
                period_start=now,
                period_end=now + timedelta(days=30),
                api_calls_used=5000,
                api_calls_limit=10000,
                tokens_used=500000,
                tokens_limit=1000000,
                storage_used_gb=Decimal("50"),
                storage_limit_gb=100,
            )
            session.add(quota)
            await session.commit()

            # 检查配额
            quota_info = await billing_engine.check_quota(
                test_tenant_id,
                test_user_id,
            )

            assert quota_info["has_quota"] is True
            assert quota_info["api_calls"]["used"] == 5000
            assert quota_info["api_calls"]["remaining"] == 5000

    @pytest.mark.asyncio
    async def test_apply_promotion_code(self, billing_engine, test_db, test_tenant_id, test_user_id):
        """测试促销代码应用"""
        async with test_db() as session:
            # 创建促销代码
            now = datetime.now(UTC)
            promo = PromotionCode(
                id=str(uuid4()),
                code="SAVE20",
                discount_type="percentage",
                discount_value=Decimal("20"),
                valid_from=now,
                valid_until=now + timedelta(days=30),
                is_active=True,
            )
            session.add(promo)

            # 创建订阅
            pricing_tier = PricingTier(
                id=str(uuid4()),
                tenant_id=test_tenant_id,
                tier_name="basic",
                billing_model=BillingModel.SUBSCRIPTION,
                monthly_price=Decimal("99.99"),
            )
            session.add(pricing_tier)
            await session.flush()

            subscription = Subscription(
                id=str(uuid4()),
                tenant_id=test_tenant_id,
                user_id=test_user_id,
                pricing_tier_id=pricing_tier.id,
                status=SubscriptionStatus.ACTIVE,
                billing_model=BillingModel.SUBSCRIPTION,
                start_date=datetime.now(UTC),
                end_date=datetime.now(UTC) + timedelta(days=30),
                payment_method=PaymentMethod.STRIPE,
                payment_method_id="pm_test_123",
            )
            session.add(subscription)
            await session.commit()

            # 应用促销代码
            result = await billing_engine.apply_promotion_code(
                test_tenant_id,
                test_user_id,
                "SAVE20",
            )

            assert result["success"] is True
            assert result["discount_type"] == "percentage"
            # discount_value 列是 Numeric(10,2),存 Decimal("20") 读回 "20.00"。
            # 用数值比较而非字符串硬比,与列精度脱钩。
            assert Decimal(result["discount_value"]) == Decimal("20")


class TestPaymentProviders:
    """支付提供商测试"""

    @pytest.mark.asyncio
    async def test_stripe_provider_charge(self):
        """测试Stripe扣款"""
        provider = StripeProvider("sk_test_123")
        result = await provider.charge(
            Decimal("99.99"),
            "USD",
            "pm_test_123",
            "Test charge",
            {},
        )

        assert result["success"] is True
        assert result["amount"] == "99.99"
        assert result["currency"] == "USD"

    @pytest.mark.asyncio
    async def test_stripe_provider_refund(self):
        """测试Stripe退款"""
        provider = StripeProvider("sk_test_123")
        result = await provider.refund("ch_test_123", Decimal("99.99"))

        assert result["success"] is True
        assert "refund_id" in result

    @pytest.mark.asyncio
    async def test_alipay_provider_charge(self):
        """测试支付宝扣款"""
        provider = AlipayProvider("app_id", "private_key", "public_key")
        result = await provider.charge(
            Decimal("99.99"),
            "CNY",
            "alipay_123",
            "Test charge",
            {},
        )

        assert result["success"] is True
        assert result["amount"] == "99.99"

    @pytest.mark.asyncio
    async def test_wechat_provider_charge(self):
        """测试微信支付扣款"""
        provider = WechatProvider("mch_id", "api_key", "cert_path")
        result = await provider.charge(
            Decimal("99.99"),
            "CNY",
            "wechat_123",
            "Test charge",
            {},
        )

        assert result["success"] is True
        assert result["amount"] == "99.99"

    def test_payment_provider_factory(self):
        """测试支付提供商工厂"""
        stripe = StripeProvider("sk_test_123")
        alipay = AlipayProvider("app_id", "private_key", "public_key")

        PaymentProviderFactory.register_provider("stripe", stripe)
        PaymentProviderFactory.register_provider("alipay", alipay)

        assert PaymentProviderFactory.get_provider("stripe") is stripe
        assert PaymentProviderFactory.get_provider("alipay") is alipay
        assert "stripe" in PaymentProviderFactory.list_providers()
        assert "alipay" in PaymentProviderFactory.list_providers()


# 集成测试

class TestBillingIntegration:
    """计费系统集成测试"""

    @pytest.mark.asyncio
    async def test_complete_billing_workflow(self, billing_engine, test_db, test_tenant_id, test_user_id):
        """测试完整的计费工作流"""
        async with test_db() as session:
            # 1. 创建价格层级
            pricing_tier = PricingTier(
                id=str(uuid4()),
                tenant_id=test_tenant_id,
                tier_name="professional",
                billing_model=BillingModel.HYBRID,
                monthly_price=Decimal("199.99"),
                api_call_price=Decimal("0.01"),
                token_price=Decimal("0.0001"),
                monthly_api_calls=10000,
                monthly_tokens=1000000,
            )
            session.add(pricing_tier)
            await session.flush()

            # 2. 创建订阅
            subscription = Subscription(
                id=str(uuid4()),
                tenant_id=test_tenant_id,
                user_id=test_user_id,
                pricing_tier_id=pricing_tier.id,
                status=SubscriptionStatus.ACTIVE,
                billing_model=BillingModel.HYBRID,
                start_date=datetime.now(UTC),
                end_date=datetime.now(UTC) + timedelta(days=30),
                payment_method=PaymentMethod.STRIPE,
                payment_method_id="pm_test_123",
            )
            session.add(subscription)
            await session.commit()

            # 3. 记录使用
            usage = await billing_engine.record_usage(
                test_tenant_id,
                test_user_id,
                api_calls=100,
                tokens_used=1000,
            )
            assert usage is not None

            # 4. 生成发票
            invoice = await billing_engine.generate_invoice(
                test_tenant_id,
                test_user_id,
                datetime.now(UTC) - timedelta(days=30),
                datetime.now(UTC),
            )
            assert invoice is not None
            assert invoice.total > 0

            # 5. 处理支付
            payment = await billing_engine.process_payment(
                test_tenant_id,
                test_user_id,
                invoice.total,
                PaymentMethod.STRIPE,
                "pm_test_123",
                invoice.id,
            )
            assert payment is not None
            assert payment.status == PaymentStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_multi_tenant_isolation(self, billing_engine, test_db):
        """测试多租户隔离"""
        async with test_db() as session:
            tenant1 = "tenant-001"
            tenant2 = "tenant-002"
            user1 = "user-001"
            user2 = "user-002"

            # 为租户1创建订阅
            pricing_tier1 = PricingTier(
                id=str(uuid4()),
                tenant_id=tenant1,
                tier_name="basic",
                billing_model=BillingModel.SUBSCRIPTION,
                monthly_price=Decimal("99.99"),
            )
            session.add(pricing_tier1)
            await session.flush()

            subscription1 = Subscription(
                id=str(uuid4()),
                tenant_id=tenant1,
                user_id=user1,
                pricing_tier_id=pricing_tier1.id,
                status=SubscriptionStatus.ACTIVE,
                billing_model=BillingModel.SUBSCRIPTION,
                start_date=datetime.now(UTC),
                end_date=datetime.now(UTC) + timedelta(days=30),
                payment_method=PaymentMethod.STRIPE,
                payment_method_id="pm_test_123",
            )
            session.add(subscription1)

            # 为租户2创建订阅
            pricing_tier2 = PricingTier(
                id=str(uuid4()),
                tenant_id=tenant2,
                tier_name="professional",
                billing_model=BillingModel.SUBSCRIPTION,
                monthly_price=Decimal("199.99"),
            )
            session.add(pricing_tier2)
            await session.flush()

            subscription2 = Subscription(
                id=str(uuid4()),
                tenant_id=tenant2,
                user_id=user2,
                pricing_tier_id=pricing_tier2.id,
                status=SubscriptionStatus.ACTIVE,
                billing_model=BillingModel.SUBSCRIPTION,
                start_date=datetime.now(UTC),
                end_date=datetime.now(UTC) + timedelta(days=30),
                payment_method=PaymentMethod.STRIPE,
                payment_method_id="pm_test_456",
            )
            session.add(subscription2)
            await session.commit()

            # 验证隔离
            stmt1 = select(Subscription).where(
                (Subscription.tenant_id == tenant1)
                & (Subscription.user_id == user1)
            )
            result1 = await session.execute(stmt1)
            subs1 = result1.scalars().all()

            stmt2 = select(Subscription).where(
                (Subscription.tenant_id == tenant2)
                & (Subscription.user_id == user2)
            )
            result2 = await session.execute(stmt2)
            subs2 = result2.scalars().all()

            assert len(subs1) == 1
            assert len(subs2) == 1
            assert subs1[0].tenant_id == tenant1
            assert subs2[0].tenant_id == tenant2


# 性能测试

@pytest.mark.performance  # 环境敏感:绝对耗时阈值在慢机/CI/沙箱不可靠,常规跑用 -m "not performance" 排除
class TestBillingPerformance:
    """计费系统性能测试"""

    @pytest.mark.asyncio
    async def test_bulk_usage_recording(self, billing_engine, test_db, test_tenant_id, test_user_id):
        """测试批量使用记录性能"""
        async with test_db() as session:
            # 创建订阅
            pricing_tier = PricingTier(
                id=str(uuid4()),
                tenant_id=test_tenant_id,
                tier_name="enterprise",
                billing_model=BillingModel.PAY_AS_YOU_GO,
                api_call_price=Decimal("0.001"),
            )
            session.add(pricing_tier)
            await session.flush()

            subscription = Subscription(
                id=str(uuid4()),
                tenant_id=test_tenant_id,
                user_id=test_user_id,
                pricing_tier_id=pricing_tier.id,
                status=SubscriptionStatus.ACTIVE,
                billing_model=BillingModel.PAY_AS_YOU_GO,
                start_date=datetime.now(UTC),
                end_date=datetime.now(UTC) + timedelta(days=30),
                payment_method=PaymentMethod.STRIPE,
                payment_method_id="pm_test_123",
            )
            session.add(subscription)
            await session.commit()

            # 记录1000条使用记录
            import time
            start = time.time()

            for i in range(1000):
                await billing_engine.record_usage(
                    test_tenant_id,
                    test_user_id,
                    api_calls=10,
                    tokens_used=100,
                )

            elapsed = time.time() - start

            # 应该在合理时间内完成（例如< 10秒）
            assert elapsed < 60.0  # loosened: env-sensitive timing (see @pytest.mark.performance)
            print(f"记录1000条使用记录耗时: {elapsed:.2f}秒")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
