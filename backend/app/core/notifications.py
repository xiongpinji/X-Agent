"""Notification Provider — pluggable email/SMS/webhook notification delivery.

Supports multiple backends:
- SMTP (real email via smtplib)
- Webhook (HTTP POST to configured URL)
- Console (development/debug — logs to stdout)
- Noop (silently discard — for testing)
"""
from __future__ import annotations

import logging
import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from email.mime.text import MIMEText
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class NotificationMessage:
    """A notification to be delivered."""

    to: str
    subject: str
    body: str
    channel: str = "email"  # email | sms | webhook
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeliveryResult:
    """Result of a notification delivery attempt."""

    success: bool
    provider: str
    message_id: str = ""
    error: str = ""


class NotificationProvider(ABC):
    """Base class for notification providers."""

    @abstractmethod
    async def send(self, message: NotificationMessage) -> DeliveryResult:
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        ...


class ConsoleNotificationProvider(NotificationProvider):
    """Logs notifications to console (development mode)."""

    async def send(self, message: NotificationMessage) -> DeliveryResult:
        logger.info(f"[NOTIFICATION] To: {message.to} | Subject: {message.subject}")
        logger.debug(f"[NOTIFICATION] Body: {message.body[:200]}")
        return DeliveryResult(success=True, provider="console", message_id=f"console-{id(message)}")

    def is_configured(self) -> bool:
        return True


class SMTPNotificationProvider(NotificationProvider):
    """Sends emails via SMTP."""

    def __init__(
        self,
        host: str,
        port: int = 587,
        username: str = "",
        password: str = "",
        use_tls: bool = True,
        from_addr: str = "",
    ):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._from_addr = from_addr or username

    async def send(self, message: NotificationMessage) -> DeliveryResult:
        try:
            msg = MIMEText(message.body, "html")
            msg["Subject"] = message.subject
            msg["From"] = self._from_addr
            msg["To"] = message.to

            import asyncio

            await asyncio.to_thread(self._send_sync, msg)
            return DeliveryResult(success=True, provider="smtp", message_id=f"smtp-{message.to}")
        except Exception as e:
            logger.error(f"SMTP send failed: {e}")
            return DeliveryResult(success=False, provider="smtp", error=str(e))

    def _send_sync(self, msg: MIMEText) -> None:
        with smtplib.SMTP(self._host, self._port) as server:
            if self._use_tls:
                server.starttls()
            if self._username:
                server.login(self._username, self._password)
            server.send_message(msg)

    def is_configured(self) -> bool:
        return bool(self._host)


class WebhookNotificationProvider(NotificationProvider):
    """Sends notifications via HTTP webhook."""

    def __init__(self, url: str, headers: dict[str, str] | None = None):
        self._url = url
        self._headers = headers or {}

    async def send(self, message: NotificationMessage) -> DeliveryResult:
        try:
            payload = {
                "to": message.to,
                "subject": message.subject,
                "body": message.body,
                "channel": message.channel,
                "metadata": message.metadata,
            }
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self._url, json=payload, headers=self._headers)
                resp.raise_for_status()
            return DeliveryResult(success=True, provider="webhook", message_id=f"wh-{resp.status_code}")
        except Exception as e:
            logger.error(f"Webhook send failed: {e}")
            return DeliveryResult(success=False, provider="webhook", error=str(e))

    def is_configured(self) -> bool:
        return bool(self._url)


class NoopNotificationProvider(NotificationProvider):
    """Silently discards notifications (testing)."""

    async def send(self, message: NotificationMessage) -> DeliveryResult:
        return DeliveryResult(success=True, provider="noop", message_id="noop")

    def is_configured(self) -> bool:
        return True


# --- Factory ---

_active_provider: NotificationProvider | None = None


def get_notification_provider() -> NotificationProvider:
    """Get the active notification provider (singleton)."""
    global _active_provider
    if _active_provider is None:
        _active_provider = _create_provider_from_settings()
    return _active_provider


def set_notification_provider(provider: NotificationProvider) -> None:
    """Override the active provider (for testing)."""
    global _active_provider
    _active_provider = provider


def _create_provider_from_settings() -> NotificationProvider:
    """Create provider based on settings."""
    try:
        from backend.app.settings import get_settings

        s = get_settings()
        smtp_host = getattr(s, "smtp_host", "")
        webhook_url = getattr(s, "notification_webhook_url", "")

        if smtp_host:
            return SMTPNotificationProvider(
                host=smtp_host,
                port=getattr(s, "smtp_port", 587),
                username=getattr(s, "smtp_username", ""),
                password=getattr(s, "smtp_password", ""),
                from_addr=getattr(s, "smtp_from", ""),
            )
        if webhook_url:
            return WebhookNotificationProvider(url=webhook_url)
    except Exception:
        pass
    return ConsoleNotificationProvider()


async def send_notification(
    to: str, subject: str, body: str, channel: str = "email", **metadata: Any
) -> DeliveryResult:
    """Convenience function to send a notification."""
    provider = get_notification_provider()
    msg = NotificationMessage(to=to, subject=subject, body=body, channel=channel, metadata=metadata)
    return await provider.send(msg)


# --- Backward-compatible NotificationService ---


class NotificationService:
    """Unified notification service (backward-compatible facade).

    Delegates to the active NotificationProvider.
    """

    async def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send email notification via the active provider."""
        result = await send_notification(to=to, subject=subject, body=body, channel="email")
        return result.success

    async def send_sms(self, to: str, message: str) -> bool:
        """Send SMS notification via the active provider."""
        result = await send_notification(to=to, subject="SMS", body=message, channel="sms")
        return result.success

    async def send_webhook(self, url: str, payload: dict) -> bool:
        """Send webhook notification via HTTP POST (direct, bypasses provider)."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=payload)
                return resp.status_code < 400
        except Exception:
            return False


notification_service = NotificationService()
