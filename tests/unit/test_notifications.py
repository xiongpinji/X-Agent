"""Tests for the notification provider system."""
from __future__ import annotations

import pytest

from backend.app.core.notifications import (
    ConsoleNotificationProvider,
    DeliveryResult,
    NoopNotificationProvider,
    NotificationMessage,
    SMTPNotificationProvider,
    WebhookNotificationProvider,
    get_notification_provider,
    send_notification,
    set_notification_provider,
)


@pytest.fixture(autouse=True)
def _reset_provider():
    """Reset the global provider before/after each test."""
    set_notification_provider(ConsoleNotificationProvider())
    yield
    set_notification_provider(ConsoleNotificationProvider())


# --- ConsoleProvider ---


@pytest.mark.asyncio
async def test_console_provider_sends_successfully():
    provider = ConsoleNotificationProvider()
    msg = NotificationMessage(to="user@example.com", subject="Test", body="Hello")
    result = await provider.send(msg)

    assert result.success is True
    assert result.provider == "console"
    assert result.message_id.startswith("console-")


@pytest.mark.asyncio
async def test_console_provider_is_configured():
    provider = ConsoleNotificationProvider()
    assert provider.is_configured() is True


# --- NoopProvider ---


@pytest.mark.asyncio
async def test_noop_provider_sends_successfully():
    provider = NoopNotificationProvider()
    msg = NotificationMessage(to="user@example.com", subject="Test", body="Hello")
    result = await provider.send(msg)

    assert result.success is True
    assert result.provider == "noop"
    assert result.message_id == "noop"


@pytest.mark.asyncio
async def test_noop_provider_is_configured():
    provider = NoopNotificationProvider()
    assert provider.is_configured() is True


# --- WebhookProvider ---


@pytest.mark.asyncio
async def test_webhook_provider_handles_errors_gracefully():
    """Webhook provider should return failure (not raise) on connection error."""
    provider = WebhookNotificationProvider(url="http://127.0.0.1:1/nonexistent")
    msg = NotificationMessage(to="user@example.com", subject="Test", body="Hello")
    result = await provider.send(msg)

    assert result.success is False
    assert result.provider == "webhook"
    assert result.error != ""


def test_webhook_provider_is_configured():
    provider = WebhookNotificationProvider(url="http://example.com/hook")
    assert provider.is_configured() is True

    empty_provider = WebhookNotificationProvider(url="")
    assert empty_provider.is_configured() is False


# --- SMTPProvider ---


def test_smtp_provider_not_configured_without_host():
    provider = SMTPNotificationProvider(host="")
    assert provider.is_configured() is False


def test_smtp_provider_configured_with_host():
    provider = SMTPNotificationProvider(host="smtp.example.com")
    assert provider.is_configured() is True


# --- Factory ---


def test_factory_returns_console_provider_by_default():
    """With no SMTP/webhook settings, factory should return ConsoleProvider."""
    set_notification_provider(None)  # type: ignore[arg-type]
    # Force re-creation from settings (no smtp_host configured in test env)
    import backend.app.core.notifications as mod

    mod._active_provider = None
    provider = get_notification_provider()
    assert isinstance(provider, ConsoleNotificationProvider)


# --- send_notification convenience ---


@pytest.mark.asyncio
async def test_send_notification_convenience_function():
    set_notification_provider(NoopNotificationProvider())
    result = await send_notification(
        to="dev@example.com",
        subject="Hello",
        body="World",
        channel="email",
        extra_key="extra_value",
    )

    assert isinstance(result, DeliveryResult)
    assert result.success is True
    assert result.provider == "noop"
