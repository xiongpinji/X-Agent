"""Telegram channel adapter (Phase 5.6).

Outbound: Bot API sendMessage (POST /bot{token}/sendMessage).
Inbound: Telegram webhooks carry no cryptographic signature; instead Telegram
recommends a secret token in the X-Telegram-Bot-Api-Secret-Token header
(set when registering the webhook). We compare it constant-time against the
configured signing_secret.
"""

from __future__ import annotations

import hmac
from typing import Any

from backend.app.core.channels.base import (
    ChannelAdapter,
    ChannelConfig,
    ChannelMessage,
)


class TelegramAdapter(ChannelAdapter):
    name = "telegram"

    _API = "https://api.telegram.org"

    def __init__(self, config: ChannelConfig | None = None):
        super().__init__(config)
        self._base = (self.config.base_url or self._API).rstrip("/")

    async def send_text(self, conversation_id: str, text: str) -> dict[str, Any]:
        import httpx

        url = f"{self._base}/bot{self.config.token}/sendMessage"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url, json={"chat_id": conversation_id, "text": text}
            )
            resp.raise_for_status()
            return resp.json()

    def verify_signature(self, body: bytes, headers: dict[str, str]) -> bool:
        expected = self.config.signing_secret
        provided = headers.get("X-Telegram-Bot-Api-Secret-Token", "") or headers.get(
            "x-telegram-bot-api-secret-token",
            "",
        )
        if not expected or not provided:
            return False
        return hmac.compare_digest(expected, provided)

    def parse_inbound(self, payload: dict[str, Any]) -> ChannelMessage | None:
        message = payload.get("message") or payload.get("edited_message")
        if not message:
            return None
        text = message.get("text")
        if not text:
            return None
        chat = message.get("chat", {}) or {}
        sender = message.get("from", {}) or {}
        return ChannelMessage(
            channel=self.name,
            sender_id=str(sender.get("id", "")),
            text=str(text),
            conversation_id=str(chat.get("id", "")),
            raw=payload,
        )
