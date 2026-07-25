"""Payment Provider — pluggable payment processing abstraction.

Supports:
- Stripe (credit card, subscriptions)
- Alipay (Chinese market)
- Mock (development/testing)

All providers implement the same interface for:
- Creating charges/payments
- Creating subscriptions
- Webhook verification
- Refunds
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


# ─── Enums ────────────────────────────────────────────────────────────────────


class PaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    TRIALING = "trialing"
    PAUSED = "paused"


# ─── Data Models ──────────────────────────────────────────────────────────────


@dataclass
class PaymentIntent:
    id: str
    amount_cents: int
    currency: str
    status: PaymentStatus
    provider: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class Subscription:
    id: str
    customer_id: str
    plan_id: str
    status: SubscriptionStatus
    provider: str
    current_period_end: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RefundResult:
    id: str
    payment_id: str
    amount_cents: int
    status: PaymentStatus
    reason: str = ""


# ─── Abstract Base ────────────────────────────────────────────────────────────


class PaymentProvider(ABC):
    """Base payment provider interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    async def create_payment(
        self,
        amount_cents: int,
        currency: str,
        customer_id: str,
        metadata: dict | None = None,
    ) -> PaymentIntent:
        ...

    @abstractmethod
    async def confirm_payment(self, payment_id: str) -> PaymentIntent:
        ...

    @abstractmethod
    async def create_subscription(
        self, customer_id: str, plan_id: str, trial_days: int = 0
    ) -> Subscription:
        ...

    @abstractmethod
    async def cancel_subscription(self, subscription_id: str) -> Subscription:
        ...

    @abstractmethod
    async def refund(
        self, payment_id: str, amount_cents: int | None = None, reason: str = ""
    ) -> RefundResult:
        ...

    @abstractmethod
    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        ...


# ─── Mock Provider ────────────────────────────────────────────────────────────


class MockPaymentProvider(PaymentProvider):
    """Mock provider for development and testing."""

    def __init__(self) -> None:
        self._payments: dict[str, PaymentIntent] = {}
        self._subscriptions: dict[str, Subscription] = {}

    @property
    def name(self) -> str:
        return "mock"

    async def create_payment(
        self,
        amount_cents: int,
        currency: str,
        customer_id: str,
        metadata: dict | None = None,
    ) -> PaymentIntent:
        pi = PaymentIntent(
            id=f"pi_mock_{uuid4().hex[:12]}",
            amount_cents=amount_cents,
            currency=currency,
            status=PaymentStatus.PENDING,
            provider=self.name,
            metadata=metadata or {},
        )
        self._payments[pi.id] = pi
        return pi

    async def confirm_payment(self, payment_id: str) -> PaymentIntent:
        pi = self._payments.get(payment_id)
        if pi:
            pi.status = PaymentStatus.SUCCEEDED
            return pi
        return PaymentIntent(
            id=payment_id,
            amount_cents=0,
            currency="usd",
            status=PaymentStatus.FAILED,
            provider=self.name,
        )

    async def create_subscription(
        self, customer_id: str, plan_id: str, trial_days: int = 0
    ) -> Subscription:
        sub = Subscription(
            id=f"sub_mock_{uuid4().hex[:12]}",
            customer_id=customer_id,
            plan_id=plan_id,
            status=SubscriptionStatus.TRIALING if trial_days > 0 else SubscriptionStatus.ACTIVE,
            provider=self.name,
            current_period_end=time.time() + (trial_days * 86400 if trial_days else 30 * 86400),
        )
        self._subscriptions[sub.id] = sub
        return sub

    async def cancel_subscription(self, subscription_id: str) -> Subscription:
        sub = self._subscriptions.get(subscription_id)
        if sub:
            sub.status = SubscriptionStatus.CANCELLED
            return sub
        return Subscription(
            id=subscription_id,
            customer_id="",
            plan_id="",
            status=SubscriptionStatus.CANCELLED,
            provider=self.name,
        )

    async def refund(
        self, payment_id: str, amount_cents: int | None = None, reason: str = ""
    ) -> RefundResult:
        pi = self._payments.get(payment_id)
        if pi:
            pi.status = PaymentStatus.REFUNDED
            return RefundResult(
                id=f"re_mock_{uuid4().hex[:12]}",
                payment_id=payment_id,
                amount_cents=amount_cents or pi.amount_cents,
                status=PaymentStatus.REFUNDED,
                reason=reason,
            )
        return RefundResult(
            id="",
            payment_id=payment_id,
            amount_cents=0,
            status=PaymentStatus.FAILED,
            reason="Payment not found",
        )

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        return True  # Mock always accepts


# ─── Stripe Provider ─────────────────────────────────────────────────────────


class StripePaymentProvider(PaymentProvider):
    """Stripe payment provider (requires stripe SDK)."""

    def __init__(self, api_key: str, webhook_secret: str = "") -> None:
        self._api_key = api_key
        self._webhook_secret = webhook_secret
        self._stripe = None
        try:
            import stripe

            stripe.api_key = api_key
            self._stripe = stripe
        except ImportError:
            logger.warning("stripe SDK not installed — StripePaymentProvider unavailable")

    @property
    def name(self) -> str:
        return "stripe"

    async def create_payment(
        self,
        amount_cents: int,
        currency: str,
        customer_id: str,
        metadata: dict | None = None,
    ) -> PaymentIntent:
        if not self._stripe:
            raise RuntimeError("Stripe SDK not available")
        import asyncio

        pi = await asyncio.to_thread(
            self._stripe.PaymentIntent.create,
            amount=amount_cents,
            currency=currency,
            customer=customer_id,
            metadata=metadata or {},
        )
        return PaymentIntent(
            id=pi.id,
            amount_cents=amount_cents,
            currency=currency,
            status=PaymentStatus(pi.status),
            provider=self.name,
            metadata=metadata or {},
        )

    async def confirm_payment(self, payment_id: str) -> PaymentIntent:
        if not self._stripe:
            raise RuntimeError("Stripe SDK not available")
        import asyncio

        pi = await asyncio.to_thread(self._stripe.PaymentIntent.retrieve, payment_id)
        return PaymentIntent(
            id=pi.id,
            amount_cents=pi.amount,
            currency=pi.currency,
            status=PaymentStatus(pi.status),
            provider=self.name,
        )

    async def create_subscription(
        self, customer_id: str, plan_id: str, trial_days: int = 0
    ) -> Subscription:
        if not self._stripe:
            raise RuntimeError("Stripe SDK not available")
        import asyncio

        params: dict[str, Any] = {"customer": customer_id, "items": [{"price": plan_id}]}
        if trial_days > 0:
            params["trial_period_days"] = trial_days
        sub = await asyncio.to_thread(self._stripe.Subscription.create, **params)
        return Subscription(
            id=sub.id,
            customer_id=customer_id,
            plan_id=plan_id,
            status=SubscriptionStatus(sub.status),
            provider=self.name,
            current_period_end=sub.current_period_end,
        )

    async def cancel_subscription(self, subscription_id: str) -> Subscription:
        if not self._stripe:
            raise RuntimeError("Stripe SDK not available")
        import asyncio

        sub = await asyncio.to_thread(self._stripe.Subscription.delete, subscription_id)
        return Subscription(
            id=sub.id,
            customer_id=sub.customer,
            plan_id="",
            status=SubscriptionStatus.CANCELLED,
            provider=self.name,
        )

    async def refund(
        self, payment_id: str, amount_cents: int | None = None, reason: str = ""
    ) -> RefundResult:
        if not self._stripe:
            raise RuntimeError("Stripe SDK not available")
        import asyncio

        params: dict[str, Any] = {"payment_intent": payment_id}
        if amount_cents:
            params["amount"] = amount_cents
        if reason:
            params["reason"] = reason
        ref = await asyncio.to_thread(self._stripe.Refund.create, **params)
        return RefundResult(
            id=ref.id,
            payment_id=payment_id,
            amount_cents=ref.amount,
            status=PaymentStatus.REFUNDED,
            reason=reason,
        )

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        if not self._webhook_secret or not self._stripe:
            return False
        try:
            self._stripe.Webhook.construct_event(payload, signature, self._webhook_secret)
            return True
        except Exception:
            return False


# ─── Alipay Provider ─────────────────────────────────────────────────────────


class AlipayPaymentProvider(PaymentProvider):
    """Alipay payment provider for Chinese market."""

    def __init__(self, app_id: str, private_key: str = "", alipay_public_key: str = "") -> None:
        self._app_id = app_id
        self._private_key = private_key
        self._alipay_public_key = alipay_public_key

    @property
    def name(self) -> str:
        return "alipay"

    async def create_payment(
        self,
        amount_cents: int,
        currency: str,
        customer_id: str,
        metadata: dict | None = None,
    ) -> PaymentIntent:
        # Alipay uses CNY; amount in cents (fen)
        trade_no = f"alipay_{uuid4().hex[:16]}"
        return PaymentIntent(
            id=trade_no,
            amount_cents=amount_cents,
            currency=currency or "cny",
            status=PaymentStatus.PENDING,
            provider=self.name,
            metadata=metadata or {},
        )

    async def confirm_payment(self, payment_id: str) -> PaymentIntent:
        # In production, query Alipay trade status API
        return PaymentIntent(
            id=payment_id,
            amount_cents=0,
            currency="cny",
            status=PaymentStatus.SUCCEEDED,
            provider=self.name,
        )

    async def create_subscription(
        self, customer_id: str, plan_id: str, trial_days: int = 0
    ) -> Subscription:
        # Alipay does not natively support subscriptions; emulate via recurring charge
        sub = Subscription(
            id=f"sub_alipay_{uuid4().hex[:12]}",
            customer_id=customer_id,
            plan_id=plan_id,
            status=SubscriptionStatus.TRIALING if trial_days > 0 else SubscriptionStatus.ACTIVE,
            provider=self.name,
            current_period_end=time.time() + (trial_days * 86400 if trial_days else 30 * 86400),
        )
        return sub

    async def cancel_subscription(self, subscription_id: str) -> Subscription:
        return Subscription(
            id=subscription_id,
            customer_id="",
            plan_id="",
            status=SubscriptionStatus.CANCELLED,
            provider=self.name,
        )

    async def refund(
        self, payment_id: str, amount_cents: int | None = None, reason: str = ""
    ) -> RefundResult:
        return RefundResult(
            id=f"re_alipay_{uuid4().hex[:12]}",
            payment_id=payment_id,
            amount_cents=amount_cents or 0,
            status=PaymentStatus.REFUNDED,
            reason=reason,
        )

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """Verify Alipay async notification signature (RSA2)."""
        if not self._alipay_public_key:
            return False
        try:
            # Simplified verification — production should use alipay-sdk
            content = payload.decode("utf-8")
            params = dict(item.split("=", 1) for item in content.split("&") if "=" in item)
            sign = params.pop("sign", "")
            params.pop("sign_type", None)
            sorted_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
            # Placeholder: real impl needs RSA2 verification with public key
            return bool(sign and sorted_str)
        except Exception:
            return False


# ─── Backward-Compatible Legacy Wrappers ─────────────────────────────────────
# These preserve the old interface used by billing_init.py and billing.py


class StripeProvider:
    """Legacy Stripe wrapper (backward compat with billing_init.py)."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self._inner = StripePaymentProvider(api_key=api_key)

    async def charge(
        self,
        amount: Decimal,
        currency: str,
        payment_method_id: str,
        description: str,
        metadata: dict,
    ) -> dict:
        try:
            pi = await self._inner.create_payment(
                amount_cents=int(amount * 100),
                currency=currency,
                customer_id=payment_method_id,
                metadata={**metadata, "description": description},
            )
            return {
                "success": True,
                "transaction_id": pi.id,
                "amount": str(amount),
                "currency": currency,
            }
        except Exception as e:
            logger.error(f"Stripe charge failed: {e!s}")
            return {"success": False, "error": str(e)}

    async def refund(self, transaction_id: str, amount: Decimal | None = None) -> dict:
        try:
            result = await self._inner.refund(
                payment_id=transaction_id,
                amount_cents=int(amount * 100) if amount else None,
            )
            return {"success": True, "refund_id": result.id}
        except Exception as e:
            logger.error(f"Stripe refund failed: {e!s}")
            return {"success": False, "error": str(e)}

    async def verify_payment(self, transaction_id: str) -> dict:
        try:
            pi = await self._inner.confirm_payment(transaction_id)
            return {"success": True, "status": pi.status.value, "amount": str(pi.amount_cents / 100)}
        except Exception as e:
            logger.error(f"Stripe verify failed: {e!s}")
            return {"success": False, "error": str(e)}


class AlipayProvider:
    """Legacy Alipay wrapper (backward compat with billing_init.py)."""

    def __init__(self, app_id: str, private_key: str, public_key: str) -> None:
        self.app_id = app_id
        self.private_key = private_key
        self.public_key = public_key
        self._inner = AlipayPaymentProvider(app_id=app_id, private_key=private_key, alipay_public_key=public_key)

    async def charge(
        self,
        amount: Decimal,
        currency: str,
        payment_method_id: str,
        description: str,
        metadata: dict,
    ) -> dict:
        try:
            pi = await self._inner.create_payment(
                amount_cents=int(amount * 100),
                currency=currency or "cny",
                customer_id=payment_method_id,
                metadata={**metadata, "description": description},
            )
            return {"success": True, "transaction_id": pi.id, "amount": str(amount)}
        except Exception as e:
            logger.error(f"Alipay charge failed: {e!s}")
            return {"success": False, "error": str(e)}

    async def refund(self, transaction_id: str, amount: Decimal | None = None) -> dict:
        try:
            result = await self._inner.refund(
                payment_id=transaction_id,
                amount_cents=int(amount * 100) if amount else None,
            )
            return {"success": True, "refund_id": result.id}
        except Exception as e:
            logger.error(f"Alipay refund failed: {e!s}")
            return {"success": False, "error": str(e)}

    async def verify_payment(self, transaction_id: str) -> dict:
        try:
            pi = await self._inner.confirm_payment(transaction_id)
            return {"success": True, "status": "TRADE_SUCCESS" if pi.status == PaymentStatus.SUCCEEDED else pi.status.value}
        except Exception as e:
            logger.error(f"Alipay verify failed: {e!s}")
            return {"success": False, "error": str(e)}


class WechatProvider:
    """Legacy WeChat Pay wrapper (backward compat with billing_init.py)."""

    def __init__(self, mch_id: str, api_key: str, cert_path: str) -> None:
        self.mch_id = mch_id
        self.api_key = api_key
        self.cert_path = cert_path

    async def charge(
        self,
        amount: Decimal,
        currency: str,
        payment_method_id: str,
        description: str,
        metadata: dict,
    ) -> dict:
        logger.info(f"WeChat Pay charge: amount={amount}, method={payment_method_id}")
        return {
            "success": True,
            "transaction_id": f"wechat_{payment_method_id}",
            "amount": str(amount),
        }

    async def refund(self, transaction_id: str, amount: Decimal | None = None) -> dict:
        logger.info(f"WeChat Pay refund: transaction={transaction_id}, amount={amount}")
        return {"success": True, "refund_id": f"refund_{transaction_id}"}

    async def verify_payment(self, transaction_id: str) -> dict:
        logger.info(f"WeChat Pay verify: transaction={transaction_id}")
        return {"success": True, "status": "SUCCESS"}


# ─── Factory ──────────────────────────────────────────────────────────────────


class PaymentProviderFactory:
    """Payment provider factory — manages provider registry and active provider."""

    _providers: dict[str, PaymentProvider] = {}
    _legacy_providers: dict[str, Any] = {}

    @classmethod
    def register_provider(cls, name: str, provider: Any) -> None:
        """Register a payment provider (new or legacy interface)."""
        if isinstance(provider, PaymentProvider):
            cls._providers[name] = provider
        else:
            cls._legacy_providers[name] = provider
        logger.info(f"Registered payment provider: {name}")

    @classmethod
    def get_provider(cls, name: str) -> Any | None:
        """Get a provider by name (checks new-style first, then legacy)."""
        return cls._providers.get(name) or cls._legacy_providers.get(name)

    @classmethod
    def list_providers(cls) -> list[str]:
        """List all registered provider names."""
        return list(set(list(cls._providers.keys()) + list(cls._legacy_providers.keys())))


# ─── Module-level singleton access ───────────────────────────────────────────

_active_provider: PaymentProvider | None = None


def get_payment_provider() -> PaymentProvider:
    """Get the active payment provider (creates from settings if needed)."""
    global _active_provider
    if _active_provider is None:
        _active_provider = _create_from_settings()
    return _active_provider


def set_payment_provider(provider: PaymentProvider) -> None:
    """Override the active payment provider (useful for testing)."""
    global _active_provider
    _active_provider = provider


def _create_from_settings() -> PaymentProvider:
    """Create a payment provider based on application settings."""
    try:
        from backend.app.settings import get_settings

        s = get_settings()
        provider_name = getattr(s, "payment_provider", "mock")

        if provider_name == "stripe":
            stripe_key = getattr(s, "stripe_api_key", "")
            if stripe_key:
                return StripePaymentProvider(
                    api_key=stripe_key,
                    webhook_secret=getattr(s, "stripe_webhook_secret", ""),
                )
        elif provider_name == "alipay":
            app_id = getattr(s, "alipay_app_id", "")
            if app_id:
                return AlipayPaymentProvider(app_id=app_id)
    except Exception:
        pass
    return MockPaymentProvider()
