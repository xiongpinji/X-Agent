"""飞书 (Feishu/Lark) channel adapter."""
from __future__ import annotations

import logging
from typing import Any

from backend.app.channels.base import ChannelAdapter, ChannelMessage, ChannelResponse

logger = logging.getLogger(__name__)


class FeishuAdapter(ChannelAdapter):
    """飞书 Bot adapter."""

    def __init__(self, app_id: str, app_secret: str, verification_token: str = ""):
        self.app_id = app_id
        self.app_secret = app_secret
        self.verification_token = verification_token
        self._tenant_token: str | None = None

    @property
    def channel_name(self) -> str:
        return "feishu"

    async def send_message(self, chat_id: str, response: ChannelResponse) -> bool:
        import httpx
        token = await self._get_tenant_token()
        if not token:
            return False
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://open.feishu.cn/open-apis/im/v1/messages",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"receive_id_type": "chat_id"},
                    json={
                        "receive_id": chat_id,
                        "msg_type": "text",
                        "content": f'"text": "{response.content}"',
                    },
                    timeout=30,
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"Feishu send failed: {e}")
            return False

    async def handle_webhook(self, payload: dict[str, Any]) -> ChannelMessage | None:
        # URL verification challenge
        if "challenge" in payload:
            return None
        event = payload.get("event", {})
        message = event.get("message", {})
        sender = event.get("sender", {}).get("sender_id", {})
        return ChannelMessage(
            channel="feishu",
            sender_id=sender.get("open_id", ""),
            sender_name=sender.get("name", ""),
            content=message.get("content", ""),
            metadata={"chat_id": message.get("chat_id", "")},
        )

    async def _get_tenant_token(self) -> str | None:
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                    json={"app_id": self.app_id, "app_secret": self.app_secret},
                    timeout=10,
                )
                data = resp.json()
                return data.get("tenant_access_token")
        except Exception:
            return None
