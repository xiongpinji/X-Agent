"""Discord channel adapter (Phase 5.6).

Outbound: posts to a channel via the Discord Bot API
(POST /channels/{id}/messages with a Bot token).
Inbound: Discord interaction webhooks are Ed25519-signed; we verify the
X-Signature-Ed25519 / X-Signature-Timestamp headers when a public key is
configured (config.signing_secret holds the hex public key).
"""

from __future__ import annotations

from typing import Any

from backend.app.core.channels.base import (
    ChannelAdapter,
    ChannelConfig,
    ChannelMessage,
)


class DiscordAdapter(ChannelAdapter):
    name = "discord"

    _API = "https://discord.com/api/v10"

    def __init__(self, config: ChannelConfig | None = None):
        super().__init__(config)
        self._base = (self.config.base_url or self._API).rstrip("/")

    async def send_text(self, conversation_id: str, text: str) -> dict[str, Any]:
        import httpx

        url = f"{self._base}/channels/{conversation_id}/messages"
        headers = {
            "Authorization": f"Bot {self.config.token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json={"content": text})
            resp.raise_for_status()
            return resp.json()

    def verify_signature(self, body: bytes, headers: dict[str, str]) -> bool:
        public_key = self.config.signing_secret
        sig = headers.get("X-Signature-Ed25519", "")
        ts = headers.get("X-Signature-Timestamp", "")
        if not public_key or not sig or not ts:
            return False
        try:
            from nacl.signing import VerifyKey  # type: ignore

            vk = VerifyKey(bytes.fromhex(public_key))
            vk.verify(ts.encode() + body, bytes.fromhex(sig))
            return True
        except Exception:
            return False

    def parse_inbound(self, payload: dict[str, Any]) -> ChannelMessage | None:
        # Discord message-create gateway/webhook shape.
        if payload.get("type") == 1:  # PING
            return None
        content = payload.get("content") or payload.get("data", {}).get("content")
        if not content:
            return None
        author = payload.get("author", {}) or {}
        return ChannelMessage(
            channel=self.name,
            sender_id=str(author.get("id", payload.get("user", {}).get("id", ""))),
            text=str(content),
            conversation_id=str(payload.get("channel_id", "")),
            raw=payload,
        )
