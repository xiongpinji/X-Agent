"""Unit tests for payment provider pattern."""
from __future__ import annotations

import pytest

from backend.app.core.payment_providers import (
    AlipayPaymentProvider,
    MockPaymentProvider,
    PaymentIntent,
    PaymentProvider,
    PaymentProviderFactory,
    PaymentStatus,
    RefundResult,
    StripePaymentProvider,
    Subscription,
    SubscriptionStatus,
    get_payment_provider,
    set_payment_provider,
)


# ─── Enum Tests ───────────────────────────────────────────────────────────────


class TestPaymentStatusEnum:
    def test_values(self):
        assert PaymentStatus.PENDING == "pending"
        assert PaymentStatus.SUCCEEDED == "succeeded"
        assert PaymentStatus.FAILED == "failed"
        assert PaymentStatus.REFUNDED == "refunded"
        assert PaymentStatus.CANCELLED == "cancelled"

    def test_is_str_enum(self):
        assert isinstance(PaymentStatus.PENDING, str)

    def test_member_count(self):
        assert len(PaymentStatus) == 5


class TestSubscriptionStatusEnum:
    def test_values(self):
        assert SubscriptionStatus.ACTIVE == "active"
        assert SubscriptionStatus.PAST_DUE == "past_due"
        assert SubscriptionStatus.CANCELLED == "cancelled"
        assert SubscriptionStatus.TRIALING == "trialing"
        assert SubscriptionStatus.PAUSED == "paused"

    def test_is_str_enum(self):
        assert isinstance(SubscriptionStatus.ACTIVE, str)

    def test_member_count(self):
        assert len(SubscriptionStatus) == 5


# ─── MockPaymentProvider Tests ────────────────────────────────────────────────


class TestMockPaymentProvider:
    @pytest.fixture
    def provider(self):
        return MockPaymentProvider()

    def test_name(self, provider):
        assert provider.name == "mock"

    def test_is_payment_provider(self, provider):
        assert isinstance(provider, PaymentProvider)

    @pytest.mark.asyncio
    async def test_create_payment(self, provider):
        pi = await provider.create_payment(
            amount_cents=2500,
            currency="usd",
            customer_id="cust_123",
            metadata={"order": "abc"},
        )
        assert pi.id.startswith("pi_mock_")
        assert pi.amount_cents == 2500
        assert pi.currency == "usd"
        assert pi.status == PaymentStatus.PENDING
        assert pi.provider == "mock"
        assert pi.metadata == {"order": "abc"}

    @pytest.mark.asyncio
    async def test_confirm_payment(self, provider):
        pi = await provider.create_payment(1000, "usd", "cust_1")
        confirmed = await provider.confirm_payment(pi.id)
        assert confirmed.status == PaymentStatus.SUCCEEDED
        assert confirmed.id == pi.id

    @pytest.mark.asyncio
    async def test_confirm_nonexistent_payment(self, provider):
        result = await provider.confirm_payment("pi_nonexistent")
        assert result.status == PaymentStatus.FAILED

    @pytest.mark.asyncio
    async def test_create_subscription_active(self, provider):
        sub = await provider.create_subscription("cust_1", "plan_pro")
        assert sub.id.startswith("sub_mock_")
        assert sub.customer_id == "cust_1"
        assert sub.plan_id == "plan_pro"
        assert sub.status == SubscriptionStatus.ACTIVE
        assert sub.provider == "mock"
        assert sub.current_period_end > 0

    @pytest.mark.asyncio
    async def test_create_subscription_trialing(self, provider):
        sub = await provider.create_subscription("cust_1", "plan_pro", trial_days=14)
        assert sub.status == SubscriptionStatus.TRIALING

    @pytest.mark.asyncio
    async def test_cancel_subscription(self, provider):
        sub = await provider.create_subscription("cust_1", "plan_pro")
        cancelled = await provider.cancel_subscription(sub.id)
        assert cancelled.status == SubscriptionStatus.CANCELLED
        assert cancelled.id == sub.id

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_subscription(self, provider):
        result = await provider.cancel_subscription("sub_nonexistent")
        assert result.status == SubscriptionStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_refund_full(self, provider):
        pi = await provider.create_payment(5000, "usd", "cust_1")
        refund = await provider.refund(pi.id, reason="customer request")
        assert refund.id.startswith("re_mock_")
        assert refund.payment_id == pi.id
        assert refund.amount_cents == 5000
        assert refund.status == PaymentStatus.REFUNDED
        assert refund.reason == "customer request"

    @pytest.mark.asyncio
    async def test_refund_partial(self, provider):
        pi = await provider.create_payment(5000, "usd", "cust_1")
        refund = await provider.refund(pi.id, amount_cents=2000)
        assert refund.amount_cents == 2000

    @pytest.mark.asyncio
    async def test_refund_nonexistent_payment(self, provider):
        refund = await provider.refund("pi_nonexistent")
        assert refund.status == PaymentStatus.FAILED
        assert refund.reason == "Payment not found"

    def test_verify_webhook_always_true(self, provider):
        assert provider.verify_webhook(b"payload", "sig") is True
        assert provider.verify_webhook(b"", "") is True


# ─── StripePaymentProvider Tests ─────────────────────────────────────────────


class TestStripePaymentProvider:
    def test_name(self):
        # stripe SDK likely not installed — provider still instantiates
        provider = StripePaymentProvider(api_key="sk_test_fake")
        assert provider.name == "stripe"

    def test_is_payment_provider(self):
        provider = StripePaymentProvider(api_key="sk_test_fake")
        assert isinstance(provider, PaymentProvider)

    def test_verify_webhook_no_secret(self):
        provider = StripePaymentProvider(api_key="sk_test_fake", webhook_secret="")
        assert provider.verify_webhook(b"payload", "sig") is False

    def test_verify_webhook_no_stripe_sdk(self):
        # If stripe not installed, _stripe is None → returns False
        provider = StripePaymentProvider(api_key="sk_test_fake", webhook_secret="whsec_x")
        if provider._stripe is None:
            assert provider.verify_webhook(b"payload", "sig") is False


# ─── AlipayPaymentProvider Tests ─────────────────────────────────────────────


class TestAlipayPaymentProvider:
    @pytest.fixture
    def provider(self):
        return AlipayPaymentProvider(app_id="2021001234")

    def test_name(self, provider):
        assert provider.name == "alipay"

    def test_is_payment_provider(self, provider):
        assert isinstance(provider, PaymentProvider)

    @pytest.mark.asyncio
    async def test_create_payment(self, provider):
        pi = await provider.create_payment(9900, "cny", "buyer_1")
        assert pi.id.startswith("alipay_")
        assert pi.amount_cents == 9900
        assert pi.currency == "cny"
        assert pi.status == PaymentStatus.PENDING

    def test_verify_webhook_no_key(self, provider):
        assert provider.verify_webhook(b"data", "sig") is False


# ─── Factory Tests ────────────────────────────────────────────────────────────


class TestPaymentProviderFactory:
    def test_default_returns_mock(self):
        # Reset singleton
        set_payment_provider(MockPaymentProvider())
        provider = get_payment_provider()
        assert isinstance(provider, MockPaymentProvider)
        assert provider.name == "mock"

    def test_set_and_get_provider(self):
        custom = MockPaymentProvider()
        set_payment_provider(custom)
        assert get_payment_provider() is custom

    def test_factory_register_and_get(self):
        provider = MockPaymentProvider()
        PaymentProviderFactory.register_provider("test_mock", provider)
        assert PaymentProviderFactory.get_provider("test_mock") is provider
        assert "test_mock" in PaymentProviderFactory.list_providers()

    def test_factory_get_nonexistent(self):
        assert PaymentProviderFactory.get_provider("nonexistent_xyz") is None


# ─── Dataclass Tests ─────────────────────────────────────────────────────────


class TestDataclasses:
    def test_payment_intent_defaults(self):
        pi = PaymentIntent(
            id="pi_1", amount_cents=100, currency="usd",
            status=PaymentStatus.PENDING, provider="mock",
        )
        assert pi.metadata == {}
        assert pi.created_at > 0

    def test_subscription_defaults(self):
        sub = Subscription(
            id="sub_1", customer_id="c1", plan_id="p1",
            status=SubscriptionStatus.ACTIVE, provider="mock",
        )
        assert sub.current_period_end == 0.0
        assert sub.metadata == {}

    def test_refund_result(self):
        r = RefundResult(
            id="re_1", payment_id="pi_1", amount_cents=500,
            status=PaymentStatus.REFUNDED, reason="test",
        )
        assert r.reason == "test"
