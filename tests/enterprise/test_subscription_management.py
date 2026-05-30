"""
订阅管理系统测试套件
包括单元测试、集成测试、状态机测试
"""
import pytest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from backend.app.core.subscription_manager import (
    SubscriptionManager,
    TrialPeriod,
    SubscriptionEvent,
)
from backend.app.core.quota_manager import (
    QuotaManager,
    QuotaType,
    QuotaAlertLevel,
)
from backend.app.core.subscription_automation import SubscriptionAutomation
from backend.app.models.billing import (
    Subscription,
    SubscriptionStatus,
    PricingTier,
    BillingModel,
    QuotaUsage,
)
from backend.app.core.session import SessionManager


class TestSubscriptionManager:
    """订阅管理器测试"""

    @pytest.mark.asyncio
    async def test_create_subscription(self):
        """测试创建订阅"""
        manager = SubscriptionManager()
        tenant_id = str(uuid4())
        user_id = str(uuid4())
        pricing_tier_id = str(uuid4())

        # 创建价格层级
        async with SessionManager.get_session() as session:
            tier = PricingTier(
                id=pricing_tier_id,
                tenant_id=tenant_id,
                tier_name="professional",
                billing_model=BillingModel.SUBSCRIPTION,
                monthly_price=Decimal("99.99"),
                monthly_api_calls=10000,
                monthly_tokens=1000000,
                storage_gb=100,
            )
            session.add(tier)
            await session.commit()

        # 创建订阅
        subscription = await manager.create_subscription(
            tenant_id=tenant_id,
            user_id=user_id,
            pricing_tier_id=pricing_tier_id,
            payment_method="stripe",
            payment_method_id="pm_test_123",
            auto_renew=True,
        )

        assert subscription.id is not None
        assert subscription.status == SubscriptionStatus.ACTIVE
        assert subscription.auto_renew is True
        assert subscription.start_date is not None
        assert subscription.end_date is not None

    @pytest.mark.asyncio
    async def test_create_subscription_with_trial(self):
        """测试创建带试用期的订阅"""
        manager = SubscriptionManager()
        tenant_id = str(uuid4())
        user_id = str(uuid4())
        pricing_tier_id = str(uuid4())

        # 创建价格层级
        async with SessionManager.get_session() as session:
            tier = PricingTier(
                id=pricing_tier_id,
                tenant_id=tenant_id,
                tier_name="professional",
                billing_model=BillingModel.SUBSCRIPTION,
                monthly_price=Decimal("99.99"),
                monthly_api_calls=10000,
                monthly_tokens=1000000,
                storage_gb=100,
            )
            session.add(tier)
            await session.commit()

        # 创建带试用期的订阅
        subscription = await manager.create_subscription(
            tenant_id=tenant_id,
            user_id=user_id,
            pricing_tier_id=pricing_tier_id,
            payment_method="stripe",
            payment_method_id="pm_test_123",
            trial_period=TrialPeriod.FOURTEEN_DAYS,
        )

        assert subscription.status == SubscriptionStatus.ACTIVE
        assert subscription.extra_metadata.get("trial_period") == "14_days"

    @pytest.mark.asyncio
    async def test_pause_subscription(self):
        """测试暂停订阅"""
        manager = SubscriptionManager()
        tenant_id = str(uuid4())
        user_id = str(uuid4())
        pricing_tier_id = str(uuid4())

        # 创建订阅
        async with SessionManager.get_session() as session:
            tier = PricingTier(
                id=pricing_tier_id,
                tenant_id=tenant_id,
                tier_name="professional",
                billing_model=BillingModel.SUBSCRIPTION,
                monthly_price=Decimal("99.99"),
            )
            session.add(tier)
            await session.commit()

        subscription = await manager.create_subscription(
            tenant_id=tenant_id,
            user_id=user_id,
            pricing_tier_id=pricing_tier_id,
            payment_method="stripe",
            payment_method_id="pm_test_123",
        )

        # 暂停订阅
        paused = await manager.pause_subscription(tenant_id, user_id)
        assert paused.status == SubscriptionStatus.PAUSED

    @pytest.mark.asyncio
    async def test_resume_subscription(self):
        """测试恢复订阅"""
        manager = SubscriptionManager()
        tenant_id = str(uuid4())
        user_id = str(uuid4())
        pricing_tier_id = str(uuid4())

        # 创建并暂停订阅
        async with SessionManager.get_session() as session:
            tier = PricingTier(
                id=pricing_tier_id,
                tenant_id=tenant_id,
                tier_name="professional",
                billing_model=BillingModel.SUBSCRIPTION,
                monthly_price=Decimal("99.99"),
            )
            session.add(tier)
            await session.commit()

        subscription = await manager.create_subscription(
            tenant_id=tenant_id,
            user_id=user_id,
            pricing_tier_id=pricing_tier_id,
            payment_method="stripe",
            payment_method_id="pm_test_123",
        )

        await manager.pause_subscription(tenant_id, user_id)

        # 恢复订阅
        resumed = await manager.resume_subscription(tenant_id, user_id)
        assert resumed.status == SubscriptionStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_upgrade_subscription(self):
        """测试升级订阅"""
        manager = SubscriptionManager()
        tenant_id = str(uuid4())
        user_id = str(uuid4())
        old_tier_id = str(uuid4())
        new_tier_id = str(uuid4())

        # 创建价格层级
        async with SessionManager.get_session() as session:
            old_tier = PricingTier(
                id=old_tier_id,
                tenant_id=tenant_id,
                tier_name="basic",
                billing_model=BillingModel.SUBSCRIPTION,
                monthly_price=Decimal("29.99"),
                monthly_api_calls=1000,
            )
            new_tier = PricingTier(
                id=new_tier_id,
                tenant_id=tenant_id,
                tier_name="professional",
                billing_model=BillingModel.SUBSCRIPTION,
                monthly_price=Decimal("99.99"),
                monthly_api_calls=10000,
            )
            session.add(old_tier)
            session.add(new_tier)
            await session.commit()

        # 创建订阅
        subscription = await manager.create_subscription(
            tenant_id=tenant_id,
            user_id=user_id,
            pricing_tier_id=old_tier_id,
            payment_method="stripe",
            payment_method_id="pm_test_123",
        )

        # 升级订阅
        upgraded = await manager.upgrade_subscription(
            tenant_id=tenant_id,
            user_id=user_id,
            new_pricing_tier_id=new_tier_id,
            effective_immediately=True,
        )

        assert upgraded.pricing_tier_id == new_tier_id

    @pytest.mark.asyncio
    async def test_downgrade_subscription(self):
        """测试降级订阅"""
        manager = SubscriptionManager()
        tenant_id = str(uuid4())
        user_id = str(uuid4())
        old_tier_id = str(uuid4())
        new_tier_id = str(uuid4())

        # 创建价格层级
        async with SessionManager.get_session() as session:
            old_tier = PricingTier(
                id=old_tier_id,
                tenant_id=tenant_id,
                tier_name="professional",
                billing_model=BillingModel.SUBSCRIPTION,
                monthly_price=Decimal("99.99"),
                monthly_api_calls=10000,
            )
            new_tier = PricingTier(
                id=new_tier_id,
                tenant_id=tenant_id,
                tier_name="basic",
                billing_model=BillingModel.SUBSCRIPTION,
                monthly_price=Decimal("29.99"),
                monthly_api_calls=1000,
            )
            session.add(old_tier)
            session.add(new_tier)
            await session.commit()

        # 创建订阅
        subscription = await manager.create_subscription(
            tenant_id=tenant_id,
            user_id=user_id,
            pricing_tier_id=old_tier_id,
            payment_method="stripe",
            payment_method_id="pm_test_123",
        )

        # 降级订阅
        downgraded = await manager.downgrade_subscription(
            tenant_id=tenant_id,
            user_id=user_id,
            new_pricing_tier_id=new_tier_id,
            effective_immediately=False,
        )

        assert downgraded.extra_metadata.get("pending_downgrade") is not None


class TestQuotaManager:
    """配额管理器测试"""

    @pytest.mark.asyncio
    async def test_check_quota_sufficient(self):
        """测试配额充足检查"""
        quota_manager = QuotaManager()
        manager = SubscriptionManager()
        tenant_id = str(uuid4())
        user_id = str(uuid4())
        pricing_tier_id = str(uuid4())

        # 创建价格层级 + 订阅(create_subscription 会自动初始化配额)
        async with SessionManager.get_session() as session:
            tier = PricingTier(
                id=pricing_tier_id,
                tenant_id=tenant_id,
                tier_name="professional",
                billing_model=BillingModel.SUBSCRIPTION,
                monthly_price=Decimal("99.99"),
                monthly_api_calls=10000,
                monthly_tokens=1000000,
                storage_gb=100,
            )
            session.add(tier)
            await session.commit()

        await manager.create_subscription(
            tenant_id=tenant_id,
            user_id=user_id,
            pricing_tier_id=pricing_tier_id,
            payment_method="stripe",
            payment_method_id="pm_test_123",
        )

        result = await quota_manager.check_quota(
            tenant_id=tenant_id,
            user_id=user_id,
            quota_type=QuotaType.API_CALLS,
            amount=100,
        )

        assert result.get("has_quota") is True

    @pytest.mark.asyncio
    async def test_check_quota_insufficient(self):
        """测试配额不足检查"""
        quota_manager = QuotaManager()
        manager = SubscriptionManager()
        tenant_id = str(uuid4())
        user_id = str(uuid4())
        pricing_tier_id = str(uuid4())

        # 创建配额很小的价格层级,使请求量超出限制
        async with SessionManager.get_session() as session:
            tier = PricingTier(
                id=pricing_tier_id,
                tenant_id=tenant_id,
                tier_name="basic",
                billing_model=BillingModel.SUBSCRIPTION,
                monthly_price=Decimal("9.99"),
                monthly_api_calls=50,
                monthly_tokens=1000,
                storage_gb=1,
            )
            session.add(tier)
            await session.commit()

        await manager.create_subscription(
            tenant_id=tenant_id,
            user_id=user_id,
            pricing_tier_id=pricing_tier_id,
            payment_method="stripe",
            payment_method_id="pm_test_123",
        )

        # 请求 100 次,但配额上限仅 50,应判定为不足
        result = await quota_manager.check_quota(
            tenant_id=tenant_id,
            user_id=user_id,
            quota_type=QuotaType.API_CALLS,
            amount=100,
        )

        assert result.get("has_quota") is False

    @pytest.mark.asyncio
    async def test_consume_quota(self):
        """测试消费配额"""
        quota_manager = QuotaManager()
        manager = SubscriptionManager()
        tenant_id = str(uuid4())
        user_id = str(uuid4())
        pricing_tier_id = str(uuid4())

        # 创建价格层级 + 订阅(自动初始化配额)
        async with SessionManager.get_session() as session:
            tier = PricingTier(
                id=pricing_tier_id,
                tenant_id=tenant_id,
                tier_name="professional",
                billing_model=BillingModel.SUBSCRIPTION,
                monthly_price=Decimal("99.99"),
                monthly_api_calls=10000,
                monthly_tokens=1000000,
                storage_gb=100,
            )
            session.add(tier)
            await session.commit()

        await manager.create_subscription(
            tenant_id=tenant_id,
            user_id=user_id,
            pricing_tier_id=pricing_tier_id,
            payment_method="stripe",
            payment_method_id="pm_test_123",
        )

        result = await quota_manager.consume_quota(
            tenant_id=tenant_id,
            user_id=user_id,
            quota_type=QuotaType.API_CALLS,
            amount=100,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_quota_alert_levels(self):
        """测试配额告警级别"""
        quota_manager = QuotaManager()

        # 测试80%告警
        alert = quota_manager._get_alert_level(80.0)
        assert alert == QuotaAlertLevel.WARNING_80.value

        # 测试90%告警
        alert = quota_manager._get_alert_level(90.0)
        assert alert == QuotaAlertLevel.WARNING_90.value

        # 测试100%告警
        alert = quota_manager._get_alert_level(100.0)
        assert alert == QuotaAlertLevel.CRITICAL_100.value

        # 测试无告警
        alert = quota_manager._get_alert_level(50.0)
        assert alert is None


class TestSubscriptionAutomation:
    """订阅自动化测试"""

    @pytest.mark.asyncio
    async def test_process_auto_renewals(self):
        """测试自动续费处理"""
        automation = SubscriptionAutomation()

        result = await automation.process_auto_renewals()

        assert "total" in result
        assert "success" in result
        assert "failed" in result

    @pytest.mark.asyncio
    async def test_send_expiration_reminders(self):
        """测试发送过期提醒"""
        automation = SubscriptionAutomation()

        result = await automation.send_expiration_reminders()

        assert "reminders_sent" in result

    @pytest.mark.asyncio
    async def test_handle_expired_subscriptions(self):
        """测试处理过期订阅"""
        automation = SubscriptionAutomation()

        result = await automation.handle_expired_subscriptions()

        assert "expired_count" in result


class TestSubscriptionStateMachine:
    """订阅状态机测试"""

    @pytest.mark.asyncio
    async def test_subscription_state_transitions(self):
        """测试订阅状态转换"""
        manager = SubscriptionManager()
        tenant_id = str(uuid4())
        user_id = str(uuid4())
        pricing_tier_id = str(uuid4())

        # 创建价格层级
        async with SessionManager.get_session() as session:
            tier = PricingTier(
                id=pricing_tier_id,
                tenant_id=tenant_id,
                tier_name="professional",
                billing_model=BillingModel.SUBSCRIPTION,
                monthly_price=Decimal("99.99"),
            )
            session.add(tier)
            await session.commit()

        # 创建订阅 (ACTIVE)
        subscription = await manager.create_subscription(
            tenant_id=tenant_id,
            user_id=user_id,
            pricing_tier_id=pricing_tier_id,
            payment_method="stripe",
            payment_method_id="pm_test_123",
        )
        assert subscription.status == SubscriptionStatus.ACTIVE

        # 暂停 (ACTIVE -> PAUSED)
        paused = await manager.pause_subscription(tenant_id, user_id)
        assert paused.status == SubscriptionStatus.PAUSED

        # 恢复 (PAUSED -> ACTIVE)
        resumed = await manager.resume_subscription(tenant_id, user_id)
        assert resumed.status == SubscriptionStatus.ACTIVE

        # 取消 (ACTIVE -> CANCELLED)
        cancelled = await manager.cancel_subscription(tenant_id, user_id)
        assert cancelled.status == SubscriptionStatus.CANCELLED


# 集成测试

class TestSubscriptionIntegration:
    """订阅系统集成测试"""

    @pytest.mark.asyncio
    async def test_complete_subscription_lifecycle(self):
        """测试完整的订阅生命周期"""
        manager = SubscriptionManager()
        quota_manager = QuotaManager()
        tenant_id = str(uuid4())
        user_id = str(uuid4())
        pricing_tier_id = str(uuid4())

        # 创建价格层级
        async with SessionManager.get_session() as session:
            tier = PricingTier(
                id=pricing_tier_id,
                tenant_id=tenant_id,
                tier_name="professional",
                billing_model=BillingModel.SUBSCRIPTION,
                monthly_price=Decimal("99.99"),
                monthly_api_calls=10000,
                monthly_tokens=1000000,
                storage_gb=100,
            )
            session.add(tier)
            await session.commit()

        # 1. 创建订阅
        subscription = await manager.create_subscription(
            tenant_id=tenant_id,
            user_id=user_id,
            pricing_tier_id=pricing_tier_id,
            payment_method="stripe",
            payment_method_id="pm_test_123",
            trial_period=TrialPeriod.SEVEN_DAYS,
        )
        assert subscription.status == SubscriptionStatus.ACTIVE

        # 2. 检查配额
        quota_info = await quota_manager.get_quota_info(tenant_id, user_id)
        assert quota_info is not None
        assert quota_info["api_calls"]["limit"] == 10000

        # 3. 消费配额
        result = await quota_manager.consume_quota(
            tenant_id=tenant_id,
            user_id=user_id,
            quota_type=QuotaType.API_CALLS,
            amount=100,
        )
        assert result is True

        # 4. 升级订阅
        new_tier_id = str(uuid4())
        async with SessionManager.get_session() as session:
            new_tier = PricingTier(
                id=new_tier_id,
                tenant_id=tenant_id,
                tier_name="enterprise",
                billing_model=BillingModel.SUBSCRIPTION,
                monthly_price=Decimal("299.99"),
                monthly_api_calls=100000,
                monthly_tokens=10000000,
                storage_gb=1000,
            )
            session.add(new_tier)
            await session.commit()

        upgraded = await manager.upgrade_subscription(
            tenant_id=tenant_id,
            user_id=user_id,
            new_pricing_tier_id=new_tier_id,
            effective_immediately=True,
        )
        assert upgraded.pricing_tier_id == new_tier_id

        # 5. 暂停订阅
        paused = await manager.pause_subscription(tenant_id, user_id)
        assert paused.status == SubscriptionStatus.PAUSED

        # 6. 恢复订阅
        resumed = await manager.resume_subscription(tenant_id, user_id)
        assert resumed.status == SubscriptionStatus.ACTIVE

        # 7. 取消订阅
        cancelled = await manager.cancel_subscription(tenant_id, user_id)
        assert cancelled.status == SubscriptionStatus.CANCELLED
