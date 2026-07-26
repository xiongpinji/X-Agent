"""Slack channel adapter (Events API).

Outbound: chat.postMessage via the Slack Web API
(POST {base}/chat.postMessage with a Bearer bot token).

Inbound: Slack Events API requests are signed with HMAC-SHA256 over
``v0:{timestamp}:{raw_body}`` using the app's signing secret, delivered in the
``X-Slack-Signature`` (``v0=<hex>``) and ``X-Slack-Request-Timestamp``
headers. Verification is default-deny: no configured secret or missing/ stale
headers means rejection (Slack recommends a 5-minute timestamp tolerance to
blunt replay attacks).

Config:
- config.token         <- XAGENT_SLACK_BOT_TOKEN (xoxb-...)
- config.signing_secret<- XAGENT_SLACK_SIGNING_SECRET
- config.base_url      <- optional API base override (tests / proxies)
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

from backend.app.core.channels.base import (
    ChannelAdapter,
    ChannelConfig,
    ChannelMessage,
)

#: Max age of X-Slack-Request-Timestamp before we treat the request as replayed.
_TIMESTAMP_TOLERANCE_SECONDS = 60 * 5


class SlackAdapter(ChannelAdapter):
    name = "slack"

    _API = "https://slack.com/api"

    def __init__(self, config: ChannelConfig | None = None):
        super().__init__(config)
        self._base = (self.config.base_url or self._API).rstrip("/")

    @property
    def configured(self) -> bool:
        """Explicit availability: both credentials must be present."""
        return bool(self.config.token and self.config.signing_secret)

    async def send_text(self, conversation_id: str, text: str) -> dict[str, Any]:
        import httpx

        url = f"{self._base}/chat.postMessage"
        headers = {
            "Authorization": f"Bearer {self.config.token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url, headers=headers, json={"channel": conversation_id, "text": text}
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok", False):
                raise RuntimeError(f"Slack chat.postMessage failed: {data.get('error')}")
            return data

    def verify_signature(self, body: bytes, headers: dict[str, str]) -> bool:
        secret = self.config.signing_secret
        if not secret:
            return False
        # Headers may arrive in any case from the ASGI layer.
        lowered = {k.lower(): v for k, v in headers.items()}
        signature = lowered.get("x-slack-signature", "")
        timestamp = lowered.get("x-slack-request-timestamp", "")
        if not signature or not timestamp:
            return False
        try:
            ts = int(timestamp)
        except ValueError:
            return False
        if abs(time.time() - ts) > _TIMESTAMP_TOLERANCE_SECONDS:
            return False
        basestring = b"v0:" + timestamp.encode() + b":" + body
        expected = "v0=" + hmac.new(secret.encode(), basestring, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def parse_inbound(self, payload: dict[str, Any]) -> ChannelMessage | None:
        # url_verification is answered by the API layer (challenge echo), not
        # dispatched as a message.
        if payload.get("type") == "url_verification":
            return None
        if payload.get("type") != "event_callback":
            return None
        event = payload.get("event", {}) or {}
        if event.get("type") not in {"message", "app_mention"}:
            return None
        # Ignore bot/self messages and message subtypes (edits, joins, ...).
        if event.get("bot_id") or event.get("subtype"):
            return None
        text = event.get("text")
        if not text:
            return None
        channel_id = str(event.get("channel", ""))
        return ChannelMessage(
            channel=self.name,
            sender_id=str(event.get("user", "")),
            text=str(text),
            conversation_id=channel_id,
            raw={
                "event": event,
                "event_id": payload.get("event_id", ""),
                "team_id": payload.get("team_id", ""),
                # Surfaced so router message_id extraction finds a stable id.
                "message": {"id": event.get("client_msg_id") or event.get("ts", "")},
            },
        )
