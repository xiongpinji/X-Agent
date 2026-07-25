"""Telegram Bot channel adapter."""
from __future__ import annotations

import logging
from typing import Any

from backend.app.channels.base import ChannelAdapter, ChannelMessage, ChannelResponse

logger = logging.getLogger(__name__)


class TelegramAdapter(ChannelAdapter):
    """Telegram Bot API adapter."""

    def __init__(self, bot_token: str, webhook_url: str | None = None):
        self.bot_token = bot_token
        self.webhook_url = webhook_url
        self._api_base = f"https://api.telegram.org/bot{bot_token}"

    @property
    def channel_name(self) -> str:
        return "telegram"

    async def send_message(self, chat_id: str, response: ChannelResponse) -> bool:
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._api_base}/sendMessage",
                    json={"chat_id": chat_id, "text": response.content},
                    timeout=30,
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    async def handle_webhook(self, payload: dict[str, Any]) -> ChannelMessage | None:
        message = payload.get("message")
        if not message:
            return None
        return ChannelMessage(
            channel="telegram",
            sender_id=str(message.get("from", {}).get("id", "")),
            sender_name=message.get("from", {}).get("first_name", ""),
            content=message.get("text", ""),
            metadata={"chat_id": str(message.get("chat", {}).get("id", ""))},
        )
