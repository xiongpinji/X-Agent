"""DingTalk (钉钉) channel adapter (Phase 5.6).

Outbound: custom robot webhook (POST with optional HMAC-SHA256 sign param).
Inbound: DingTalk outgoing-robot callbacks are signed with HMAC-SHA256 over
"{timestamp}\n{app_secret}" in the 'sign' + 'timestamp' headers; we verify
against the configured signing_secret.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Any

from backend.app.core.channels.base import (
    ChannelAdapter,
    ChannelConfig,
    ChannelMessage,
)


class DingTalkAdapter(ChannelAdapter):
    name = "dingtalk"

    def __init__(self, config: ChannelConfig | None = None):
        super().__init__(config)
        # base_url holds the full robot webhook URL for outbound.
        self._webhook = self.config.base_url

    def _sign_outbound(self) -> tuple[str, str]:
        """Return (timestamp, sign) for the outbound robot webhook."""
        secret = self.config.signing_secret
        ts = str(round(time.time() * 1000))
        string_to_sign = f"{ts}\n{secret}"
        digest = hmac.new(
            secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256
        ).digest()
        sign = base64.b64encode(digest).decode("utf-8")
        return ts, sign

    async def send_text(self, conversation_id: str, text: str) -> dict[str, Any]:
        import httpx

        url = self._webhook or conversation_id
        params: dict[str, str] = {}
        if self.config.signing_secret:
            ts, sign = self._sign_outbound()
            params = {"timestamp": ts, "sign": sign}
        body = {"msgtype": "text", "text": {"content": text}}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, params=params, json=body)
            resp.raise_for_status()
            return resp.json()

    def verify_signature(self, body: bytes, headers: dict[str, str]) -> bool:
        secret = self.config.signing_secret
        ts = headers.get("timestamp", "")
        provided = headers.get("sign", "")
        if not secret or not ts or not provided:
            return False
        string_to_sign = f"{ts}\n{secret}"
        digest = hmac.new(
            secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256
        ).digest()
        expected = base64.b64encode(digest).decode("utf-8")
        return hmac.compare_digest(expected, provided)

    def parse_inbound(self, payload: dict[str, Any]) -> ChannelMessage | None:
        text_obj = payload.get("text", {}) or {}
        content = text_obj.get("content")
        if not content:
            return None
        return ChannelMessage(
            channel=self.name,
            sender_id=str(payload.get("senderId", "")),
            text=str(content).strip(),
            conversation_id=str(payload.get("conversationId", "")),
            raw=payload,
        )
