"""Slack channel adapter (Phase 5.6).

Outbound: Slack Web API chat.postMessage (POST https://slack.com/api/chat.postMessage).
Inbound: Slack Events API webhooks with request signature verification using HMAC-SHA256.

Signature verification:
  1. Extract X-Slack-Request-Timestamp header (seconds since epoch).
  2. Check timestamp is within 5 minutes of current time (replay attack defense).
  3. Construct signing base: f"v0:{timestamp}:{body}"
  4. Compute HMAC-SHA256(signing_secret, signing_base).
  5. Compare hex-encoded result with X-Slack-Signature (constant-time).

Inbound message events:
  - message: User sends a direct message or channel message
  - app_mention: User mentions the bot in a public channel

See: https://api.slack.com/authentication/verifying-requests-from-slack
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any, Optional

from backend.app.core.channels.base import (
    ChannelAdapter,
    ChannelConfig,
    ChannelMessage,
)

logger = logging.getLogger(__name__)

# Slack signature header format: "v0=<signature>"
_SLACK_SIG_VERSION = "v0"
_SLACK_TIMESTAMP_TOLERANCE_SECS = 300  # 5 minutes


class SlackAdapter(ChannelAdapter):
    """Slack chat platform adapter.

    Configuration (ChannelConfig):
      token (str): Bot User OAuth token (xoxb-...). Used for chat.postMessage.
      signing_secret (str): Signing secret (required for inbound webhook verification).
      base_url (str): Slack API base URL (default: https://slack.com/api).
    """

    name = "slack"

    _API_BASE = "https://slack.com/api"
    _SEND_MESSAGE_METHOD = "chat.postMessage"
    _THREAD_REPLY_METHOD = "chat.postMessage"

    def __init__(self, config: Optional[ChannelConfig] = None):
        super().__init__(config)
        self._base = (self.config.base_url or self._API_BASE).rstrip("/")

    async def send_text(self, conversation_id: str, text: str) -> dict[str, Any]:
        """Send a plain-text message to a Slack channel or thread.

        Args:
            conversation_id: Slack channel ID (C123...) or user ID (U123...).
                If thread_ts is embedded as "channel_id::thread_ts", reply to thread.
            text: Message content.

        Returns:
            Slack API response (e.g., {"ok": True, "channel": "C123", "ts": "1234567890.001234"}).

        Raises:
            httpx.HTTPError: Network error or Slack API error.
        """
        import httpx

        # Parse thread context if present (e.g., "C123::1234567890.001234")
        channel_id = conversation_id
        thread_ts = None
        if "::" in conversation_id:
            channel_id, thread_ts = conversation_id.split("::", 1)

        url = f"{self._base}/{self._SEND_MESSAGE_METHOD}"
        payload = {
            "channel": channel_id,
            "text": text,
        }
        if thread_ts:
            payload["thread_ts"] = thread_ts

        headers = {
            "Authorization": f"Bearer {self.config.token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            if not data.get("ok"):
                error = data.get("error", "unknown_error")
                logger.warning(f"Slack API error: {error}")
                # Still return the response so caller can check .get("ok")
            return data

    def verify_signature(self, body: bytes, headers: dict[str, str]) -> bool:
        """Verify the Slack request signature (HMAC-SHA256).

        Algorithm:
          1. Check X-Slack-Request-Timestamp is within 5 minutes.
          2. Construct signing_base = "v0:{timestamp}:{body_str}".
          3. Compute HMAC-SHA256(signing_secret, signing_base).
          4. Compare against X-Slack-Signature (constant-time).

        Args:
            body: Raw request body bytes.
            headers: HTTP headers dict.

        Returns:
            True if signature is valid, False otherwise.
        """
        if not self.config.signing_secret:
            logger.warning("Slack adapter: signing_secret not configured; rejecting all webhooks")
            return False

        # Extract signature header (case-insensitive)
        provided_sig = (
            headers.get("X-Slack-Signature")
            or headers.get("x-slack-signature")
            or ""
        )
        timestamp_str = (
            headers.get("X-Slack-Request-Timestamp")
            or headers.get("x-slack-request-timestamp")
            or ""
        )

        if not provided_sig or not timestamp_str:
            logger.warning("Slack: missing signature or timestamp header")
            return False

        # Verify timestamp is recent (replay attack defense)
        try:
            ts = int(timestamp_str)
        except ValueError:
            logger.warning(f"Slack: invalid timestamp format: {timestamp_str}")
            return False

        now = int(time.time())
        if abs(now - ts) > _SLACK_TIMESTAMP_TOLERANCE_SECS:
            logger.warning(
                f"Slack: timestamp drift too large ({abs(now - ts)}s > {_SLACK_TIMESTAMP_TOLERANCE_SECS}s)"
            )
            return False

        # Construct signing base
        signing_base = f"{_SLACK_SIG_VERSION}:{timestamp_str}:{body.decode('utf-8')}"

        # Compute expected signature
        expected_sig = hmac.new(
            self.config.signing_secret.encode("utf-8"),
            signing_base.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        expected_sig_header = f"{_SLACK_SIG_VERSION}={expected_sig}"

        # Constant-time comparison
        return hmac.compare_digest(provided_sig, expected_sig_header)

    def parse_inbound(self, payload: dict[str, Any]) -> Optional[ChannelMessage]:
        """Parse a Slack Events API webhook into a ChannelMessage.

        Handles:
          - url_verification challenge (not a message; returns None)
          - message events (both direct messages and channel messages)
          - app_mention events (bot mentioned in a channel)
          - thread replies (captured via thread_ts)

        Args:
            payload: Parsed JSON body from Slack webhook.

        Returns:
            ChannelMessage if actionable message event, None otherwise.
        """
        # Handle url_verification challenge (part of Slack setup flow)
        if payload.get("type") == "url_verification":
            # Caller should respond with the challenge string in body
            logger.debug("Slack: url_verification challenge")
            return None

        # Handle event wrapper
        event = payload.get("event", {})
        if not event:
            logger.debug("Slack: no event in payload")
            return None

        # Ignore non-message events
        event_type = event.get("type")
        if event_type not in ("message", "app_mention"):
            logger.debug(f"Slack: ignoring event type {event_type}")
            return None

        # Extract message text
        text = event.get("text", "").strip()
        if not text:
            logger.debug("Slack: empty message text")
            return None

        # Ignore messages from bots (avoid echoing ourselves)
        if event.get("bot_id") or event.get("subtype") in ("bot_message", "slackbot_response"):
            logger.debug("Slack: ignoring bot message")
            return None

        # Extract sender
        user_id = event.get("user", "")
        if not user_id:
            logger.debug("Slack: no user_id in event")
            return None

        # Extract conversation (channel or direct message)
        channel_id = event.get("channel", "")
        if not channel_id:
            logger.debug("Slack: no channel_id in event")
            return None

        # Capture thread context if present (for threaded replies)
        thread_ts = event.get("thread_ts", "")
        conversation_id = channel_id
        if thread_ts:
            # Encode thread context for send_text() to recognize
            conversation_id = f"{channel_id}::{thread_ts}"

        return ChannelMessage(
            channel=self.name,
            sender_id=user_id,
            text=text,
            conversation_id=conversation_id,
            raw=payload,
        )

    async def start(self) -> None:
        """Initialize Slack adapter (e.g., validate token).

        In production, could call auth.test to verify bot token is valid.
        """
        logger.info("Slack adapter started")

    async def stop(self) -> None:
        """Cleanup Slack adapter."""
        logger.info("Slack adapter stopped")
