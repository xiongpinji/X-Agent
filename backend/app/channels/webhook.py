"""Generic webhook channel adapter."""
from __future__ import annotations

import logging
from typing import Any

from backend.app.channels.base import ChannelAdapter, ChannelMessage, ChannelResponse

logger = logging.getLogger(__name__)


class WebhookAdapter(ChannelAdapter):
    """Generic webhook adapter for custom integrations."""

    def __init__(self, name: str = "webhook", callback_url: str | None = None):
        self._name = name
        self.callback_url = callback_url

    @property
    def channel_name(self) -> str:
        return self._name

    async def send_message(self, chat_id: str, response: ChannelResponse) -> bool:
        if not self.callback_url:
            return False
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    self.callback_url,
                    json={"chat_id": chat_id, "content": response.content, **response.metadata},
                    timeout=30,
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"Webhook send failed: {e}")
            return False

    async def handle_webhook(self, payload: dict[str, Any]) -> ChannelMessage | None:
        return ChannelMessage(
            channel=self._name,
            sender_id=payload.get("sender_id", ""),
            sender_name=payload.get("sender_name", ""),
            content=payload.get("content", payload.get("text", "")),
            metadata=payload.get("metadata", {}),
        )
