from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

import httpx
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

logger = logging.getLogger("xagent.feishu")


@dataclass
class FeishuEvent:
    event_id: str
    event_type: str
    tenant_key: str | None
    message_id: str | None
    chat_id: str | None
    sender_id: str | None
    content: str | None
    raw: dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class SyncEnvelope:
    direction: Literal["feishu_to_cursor", "cursor_to_feishu"]
    session_id: str
    source: str
    payload: dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class FeishuSyncStore:
    def __init__(self) -> None:
        self._seen_event_ids: set[str] = set()
        self._seen_message_ids: set[str] = set()
        self._lock = asyncio.Lock()
        self._events: list[FeishuEvent] = []
        self._envelopes: list[SyncEnvelope] = []

    async def mark_event_seen(self, event_id: str) -> bool:
        async with self._lock:
            if event_id in self._seen_event_ids:
                return False
            self._seen_event_ids.add(event_id)
            return True

    async def mark_message_seen(self, message_id: str) -> bool:
        async with self._lock:
            if message_id in self._seen_message_ids:
                return False
            self._seen_message_ids.add(message_id)
            return True

    async def add_event(self, event: FeishuEvent) -> None:
        async with self._lock:
            self._events.append(event)
            self._seen_event_ids.add(event.event_id)

    async def add_envelope(self, envelope: SyncEnvelope) -> None:
        async with self._lock:
            self._envelopes.append(envelope)

    async def snapshot(self) -> dict[str, Any]:
        async with self._lock:
            return {
                "event_count": len(self._events),
                "envelope_count": len(self._envelopes),
                "recent_events": [
                    {
                        "event_id": item.event_id,
                        "event_type": item.event_type,
                        "message_id": item.message_id,
                        "chat_id": item.chat_id,
                        "created_at": item.created_at.isoformat(),
                    }
                    for item in self._events[-10:]
                ],
            }


class FeishuBridge:
    def __init__(self) -> None:
        self.app_id: str | None = None
        self.app_secret: str | None = None
        self.encrypt_key: str | None = None
        self.base_url = "https://open.feishu.cn"
        self._tenant_access_token: str | None = None
        self._tenant_token_expire_at: datetime | None = None
        self.store = FeishuSyncStore()

    def configure(
        self,
        *,
        app_id: str,
        app_secret: str,
        base_url: str = "https://open.feishu.cn",
        encrypt_key: str | None = None,
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.encrypt_key = encrypt_key
        self.base_url = base_url.rstrip("/")

    def configure_from_env(self) -> bool:
        app_id = os.getenv("XAGENT_FEISHU_APP_ID") or os.getenv("FEISHU_APP_ID")
        app_secret = os.getenv("XAGENT_FEISHU_APP_SECRET") or os.getenv("FEISHU_APP_SECRET")
        encrypt_key = os.getenv("XAGENT_FEISHU_ENCRYPT_KEY") or os.getenv("FEISHU_ENCRYPT_KEY")
        base_url = os.getenv("XAGENT_FEISHU_BASE_URL") or os.getenv("FEISHU_BASE_URL") or self.base_url
        if not (app_id and app_secret):
            return False
        self.configure(
            app_id=app_id,
            app_secret=app_secret,
            base_url=base_url,
            encrypt_key=encrypt_key,
        )
        return True

    async def get_tenant_access_token(self) -> str:
        if self._tenant_access_token and self._tenant_token_expire_at and datetime.now(UTC) < self._tenant_token_expire_at:
            return self._tenant_access_token
        if not self.app_id or not self.app_secret:
            raise RuntimeError("Feishu app credentials are not configured")
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{self.base_url}/open-apis/auth/v3/tenant_access_token/internal/",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
            )
            response.raise_for_status()
            data = response.json()
        token = data.get("tenant_access_token")
        expire = int(data.get("expire", 3600))
        if not token:
            raise RuntimeError(f"Unable to fetch tenant access token: {data}")
        self._tenant_access_token = token
        self._tenant_token_expire_at = datetime.now(UTC).timestamp()  # type: ignore[assignment]
        self._tenant_token_expire_at = datetime.fromtimestamp(datetime.now(UTC).timestamp() + max(expire - 60, 60), tz=UTC)
        return token

    async def send_text_message(self, *, receive_id: str, text: str, receive_id_type: str = "chat_id") -> dict[str, Any]:
        token = await self.get_tenant_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "receive_id": receive_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        }
        async with httpx.AsyncClient(timeout=15, headers=headers) as client:
            response = await client.post(
                f"{self.base_url}/open-apis/im/v1/messages?receive_id_type={receive_id_type}",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    @staticmethod
    def calculate_lark_signature(*, timestamp: str, nonce: str, encrypt_key: str, body: bytes) -> str:
        """Calculate Feishu/Lark event-callback signature for signed events."""

        raw = f"{timestamp}{nonce}{encrypt_key}".encode("utf-8") + body
        return hashlib.sha256(raw).hexdigest()

    def _verify_lark_signature(self, *, timestamp: str, nonce: str, body: bytes, signature: str) -> bool:
        if not self.encrypt_key:
            return False
        expected = self.calculate_lark_signature(
            timestamp=timestamp,
            nonce=nonce,
            encrypt_key=self.encrypt_key,
            body=body,
        )
        return hmac.compare_digest(expected, signature)

    def _verify_legacy_signature(self, *, timestamp: str, nonce: str, body: bytes, signature: str) -> bool:
        if not self.app_secret:
            return False
        raw = f"{timestamp}\n{nonce}\n".encode("utf-8") + body
        digest = hmac.new(self.app_secret.encode("utf-8"), raw, hashlib.sha256).digest()
        expected = base64.b64encode(digest).decode("utf-8")
        return hmac.compare_digest(expected, signature)

    def verify_signature(
        self,
        *,
        timestamp: str,
        nonce: str,
        body: bytes,
        signature: str,
        mode: Literal["lark_sha256", "legacy_hmac_sha256"] | None = None,
    ) -> bool:
        if not (timestamp and nonce and signature):
            return False
        if mode == "lark_sha256":
            return self._verify_lark_signature(timestamp=timestamp, nonce=nonce, body=body, signature=signature)
        if mode == "legacy_hmac_sha256":
            return self._verify_legacy_signature(timestamp=timestamp, nonce=nonce, body=body, signature=signature)
        return self._verify_lark_signature(
            timestamp=timestamp,
            nonce=nonce,
            body=body,
            signature=signature,
        ) or self._verify_legacy_signature(timestamp=timestamp, nonce=nonce, body=body, signature=signature)

    def decrypt_callback_payload(self, encrypted: str) -> dict[str, Any]:
        if not self.encrypt_key:
            raise RuntimeError("Feishu event encrypt key is not configured")
        key = hashlib.sha256(self.encrypt_key.encode("utf-8")).digest()
        raw = base64.b64decode(encrypted)
        if len(raw) < 32:
            raise ValueError("Encrypted Feishu callback payload is too short")
        iv = raw[:16]
        ciphertext = raw[16:]
        if len(ciphertext) % 16 != 0:
            raise ValueError("Encrypted Feishu callback payload is not block aligned")
        decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        padded = decryptor.update(ciphertext) + decryptor.finalize()
        padding_size = padded[-1]
        if padding_size < 1 or padding_size > 16:
            raise ValueError("Invalid Feishu callback padding")
        plaintext = padded[:-padding_size]
        payload = json.loads(plaintext.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Decrypted Feishu callback payload must be an object")
        return payload

    async def handle_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        event_id = payload.get("event_id") or payload.get("header", {}).get("event_id") or payload.get("uuid") or str(uuid4())
        if not await self.store.mark_event_seen(event_id):
            return {"accepted": False, "reason": "duplicate_event", "event_id": event_id}
        event_type = payload.get("header", {}).get("event_type") or payload.get("type") or "unknown"
        event = FeishuEvent(
            event_id=event_id,
            event_type=event_type,
            tenant_key=payload.get("tenant_key") or payload.get("header", {}).get("tenant_key"),
            message_id=payload.get("event", {}).get("message", {}).get("message_id") or payload.get("event", {}).get("message_id"),
            chat_id=payload.get("event", {}).get("message", {}).get("chat_id") or payload.get("event", {}).get("chat_id"),
            sender_id=(payload.get("event", {}).get("sender", {}) or {}).get("sender_id", {}).get("open_id") if isinstance((payload.get("event", {}).get("sender", {}) or {}).get("sender_id"), dict) else payload.get("event", {}).get("sender", {}).get("sender_id", {}).get("open_id") if isinstance(payload.get("event", {}).get("sender", {}).get("sender_id"), dict) else payload.get("event", {}).get("sender", {}).get("sender_id"),
            content=self._extract_text(payload),
            raw=payload,
        )
        await self.store.add_event(event)
        return {"accepted": True, "event_id": event.event_id, "event_type": event.event_type}

    def _extract_text(self, payload: dict[str, Any]) -> str | None:
        event = payload.get("event", {})
        message = event.get("message", {})
        content = message.get("content")
        if isinstance(content, str):
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    return parsed.get("text") or content
            except json.JSONDecodeError:
                return content
        return None


feishu_bridge = FeishuBridge()
