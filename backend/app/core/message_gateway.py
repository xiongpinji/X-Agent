"""Message Platform Gateway — unified multi-platform messaging integration.

Production-grade gateway layer connecting X-Agent to real messaging platforms:

- **Telegram**  — Bot API in webhook mode (``X-Telegram-Bot-Api-Secret-Token``).
- **Discord**   — Bot REST API + slash command registration + optional Gateway
  websocket listener (HELLO / IDENTIFY / heartbeat / RESUME reconnect loop).
- **DingTalk**  — Enterprise robot: access-token auth, signed custom-robot
  webhook outbound, HMAC-SHA256 verified outgoing callbacks inbound.
- **Feishu**    — Lark/Feishu open platform: tenant_access_token auth,
  im/v1 message + file APIs, event-subscription signature verification.

All platforms normalize traffic into :class:`GatewayMessage` and are managed by
:class:`GatewayManager` (registry, async outbound queue with retry, inbound
routing, per-platform history and aggregated health checks).
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.parse
import uuid
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Maximum inbound/outbound messages retained per platform for the history API.
_HISTORY_LIMIT = 500
# Outbound retry policy.
_MAX_SEND_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 1.5


# ─── Enums & Data Models ──────────────────────────────────────────────────────


class GatewayPlatform(StrEnum):
    """Supported messaging platforms."""

    TELEGRAM = "telegram"
    DISCORD = "discord"
    DINGTALK = "dingtalk"
    FEISHU = "feishu"


class MessageKind(StrEnum):
    """Kind of message payload carried by a :class:`GatewayMessage`."""

    TEXT = "text"
    CARD = "card"  # rich card / interactive card template
    FILE = "file"  # file attachment message
    INTERACTIVE = "interactive"  # buttons / components


class GatewayState(StrEnum):
    """Lifecycle state of a gateway connection."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class Attachment:
    """A file attachment (inline bytes or remote URL)."""

    filename: str
    content_type: str = "application/octet-stream"
    data: bytes | None = None
    url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "content_type": self.content_type,
            "url": self.url,
            "size": len(self.data) if self.data else None,
        }


@dataclass
class GatewayButton:
    """An interactive button rendered on rich messages."""

    label: str
    value: str
    style: str = "default"  # default | primary | danger | link
    url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "value": self.value, "style": self.style, "url": self.url}


@dataclass
class GatewayMessage:
    """Unified cross-platform message envelope.

    Inbound messages are produced by :meth:`MessageGateway.webhook_handler`;
    outbound messages are submitted to :meth:`MessageGateway.send` (directly or
    through the :class:`GatewayManager` queue).
    """

    platform: str
    channel_id: str
    user_id: str
    content: str
    kind: MessageKind = MessageKind.TEXT
    attachments: list[Attachment] = field(default_factory=list)
    buttons: list[GatewayButton] = field(default_factory=list)
    card: dict[str, Any] | None = None  # platform-agnostic rich card descriptor
    metadata: dict[str, Any] = field(default_factory=dict)
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    direction: str = "inbound"  # inbound | outbound
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["attachments"] = [a.to_dict() for a in self.attachments]
        payload["buttons"] = [b.to_dict() for b in self.buttons]
        return payload


# ─── Exceptions ───────────────────────────────────────────────────────────────


class GatewayError(Exception):
    """Base error for all gateway failures."""


class GatewayNotConfiguredError(GatewayError):
    """Raised when a gateway lacks required credentials."""


class GatewaySignatureError(GatewayError):
    """Raised when an inbound webhook fails signature verification."""


class GatewayConnectionError(GatewayError):
    """Raised when connecting to / authenticating with a platform fails."""


# Handler signature for inbound message subscribers.
MessageHandler = Callable[[GatewayMessage], Awaitable[None]]


# ─── Base Gateway ─────────────────────────────────────────────────────────────


class MessageGateway(ABC):
    """Abstract base class for a single-platform message gateway.

    Subclasses implement platform authentication (:meth:`connect`), outbound
    delivery (:meth:`send`) and inbound webhook processing
    (:meth:`webhook_handler`) with real platform API call patterns.
    """

    platform: GatewayPlatform

    def __init__(self) -> None:
        self.state: GatewayState = GatewayState.DISCONNECTED
        self.last_error: str | None = None
        self.connected_at: float | None = None
        self.messages_sent: int = 0
        self.messages_received: int = 0
        self._client: httpx.AsyncClient | None = None
        self._handlers: list[MessageHandler] = []
        self.history: deque[GatewayMessage] = deque(maxlen=_HISTORY_LIMIT)

    # ── HTTP client management ────────────────────────────────────────────

    async def _http(self) -> httpx.AsyncClient:
        """Lazily create (or recreate) the shared async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                follow_redirects=True,
            )
        return self._client

    async def _close_http(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    # ── Inbound subscription ──────────────────────────────────────────────

    def on_message(self, handler: MessageHandler) -> None:
        """Register an async handler invoked for every verified inbound message."""
        self._handlers.append(handler)

    async def _dispatch_inbound(self, message: GatewayMessage) -> None:
        """Record + fan out an inbound message to all registered handlers."""
        message.direction = "inbound"
        self.messages_received += 1
        self.history.append(message)
        for handler in self._handlers:
            try:
                await handler(message)
            except Exception:
                logger.exception(
                    "%s gateway inbound handler failed", self.platform.value
                )

    # ── Abstract contract ─────────────────────────────────────────────────

    @property
    @abstractmethod
    def configured(self) -> bool:
        """Whether the minimum credentials for this gateway are present."""

    @abstractmethod
    async def connect(self) -> None:
        """Authenticate / establish the platform connection."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Tear down the platform connection and release resources."""

    @abstractmethod
    async def send(self, message: GatewayMessage) -> dict[str, Any]:
        """Deliver an outbound message; returns the platform API response."""

    @abstractmethod
    async def webhook_handler(
        self, body: bytes, headers: dict[str, str]
    ) -> dict[str, Any]:
        """Verify + parse an inbound webhook payload.

        Implementations MUST verify the platform signature first and raise
        :class:`GatewaySignatureError` on mismatch.
        """

    @abstractmethod
    def verify_signature(self, body: bytes, headers: dict[str, str]) -> bool:
        """Verify the platform-specific webhook signature."""

    async def receive(self) -> GatewayMessage | None:
        """Return the most recent inbound message (polling fallback)."""
        return self.history[-1] if self.history else None

    # ── Health ────────────────────────────────────────────────────────────

    def health(self) -> dict[str, Any]:
        """Structured health snapshot used by the status endpoint."""
        return {
            "platform": self.platform.value,
            "configured": self.configured,
            "state": self.state.value,
            "connected_at": self.connected_at,
            "last_error": self.last_error,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "queued_history": len(self.history),
        }

    def _mark_connected(self) -> None:
        self.state = GatewayState.CONNECTED
        self.connected_at = time.time()
        self.last_error = None

    def _mark_error(self, error: str) -> None:
        self.state = GatewayState.ERROR
        self.last_error = error


# ─── Telegram Gateway ─────────────────────────────────────────────────────────


class TelegramGateway(MessageGateway):
    """Telegram Bot API gateway operating in webhook mode.

    Outbound uses ``sendMessage`` / ``sendDocument`` / inline keyboards;
    inbound webhooks are authenticated via the
    ``X-Telegram-Bot-Api-Secret-Token`` header that Telegram echoes back when
    the webhook is registered with ``secret_token``.
    """

    platform = GatewayPlatform.TELEGRAM
    _API = "https://api.telegram.org"

    def __init__(
        self,
        bot_token: str,
        webhook_secret: str = "",
        webhook_url: str = "",
        base_url: str = "",
    ) -> None:
        super().__init__()
        self.bot_token = bot_token
        self.webhook_secret = webhook_secret
        self.webhook_url = webhook_url
        self._base = (base_url or self._API).rstrip("/")
        self.bot_info: dict[str, Any] | None = None

    @property
    def configured(self) -> bool:
        return bool(self.bot_token)

    @property
    def _api_root(self) -> str:
        return f"{self._base}/bot{self.bot_token}"

    def _require_configured(self) -> None:
        if not self.configured:
            raise GatewayNotConfiguredError(
                "Telegram gateway not configured: set telegram_bot_token"
            )

    # ── Connection ────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Validate the bot token via ``getMe`` and (re)register the webhook."""
        self._require_configured()
        self.state = GatewayState.CONNECTING
        client = await self._http()
        try:
            resp = await client.post(f"{self._api_root}/getMe")
            data = resp.json()
            if not data.get("ok"):
                raise GatewayConnectionError(
                    f"Telegram getMe failed: {data.get('description', resp.status_code)}"
                )
            self.bot_info = data.get("result")
            if self.webhook_url:
                wh_payload: dict[str, Any] = {"url": self.webhook_url}
                if self.webhook_secret:
                    wh_payload["secret_token"] = self.webhook_secret
                wh = await client.post(
                    f"{self._api_root}/setWebhook", json=wh_payload
                )
                wh_data = wh.json()
                if not wh_data.get("ok"):
                    raise GatewayConnectionError(
                        f"Telegram setWebhook failed: {wh_data.get('description')}"
                    )
            self._mark_connected()
            logger.info("Telegram gateway connected as @%s",
                        (self.bot_info or {}).get("username", "?"))
        except httpx.HTTPError as exc:
            self._mark_error(str(exc))
            raise GatewayConnectionError(f"Telegram connect failed: {exc}") from exc

    async def disconnect(self) -> None:
        """Remove the webhook registration and close the HTTP client."""
        if self.configured and self._client is not None:
            try:
                client = await self._http()
                await client.post(f"{self._api_root}/deleteWebhook")
            except httpx.HTTPError:
                logger.warning("Telegram deleteWebhook failed during disconnect")
        await self._close_http()
        self.state = GatewayState.DISCONNECTED
        self.connected_at = None

    # ── Outbound ──────────────────────────────────────────────────────────

    def _inline_keyboard(self, message: GatewayMessage) -> dict[str, Any] | None:
        if not message.buttons:
            return None
        rows: list[list[dict[str, Any]]] = []
        for btn in message.buttons:
            if btn.url:
                rows.append([{"text": btn.label, "url": btn.url}])
            else:
                rows.append([{"text": btn.label, "callback_data": btn.value}])
        return {"inline_keyboard": rows}

    async def send(self, message: GatewayMessage) -> dict[str, Any]:
        """Send text / card / file messages via the Bot API."""
        self._require_configured()
        client = await self._http()
        chat_id = message.channel_id or message.user_id
        if not chat_id:
            raise GatewayError("Telegram send requires channel_id or user_id")

        try:
            # File attachment → sendDocument (multipart)
            if message.kind == MessageKind.FILE and message.attachments:
                att = message.attachments[0]
                files: dict[str, Any]
                if att.data is not None:
                    files = {"document": (att.filename, att.data, att.content_type)}
                elif att.url:
                    files = {"document": (att.filename, att.url, att.content_type)}
                else:
                    raise GatewayError("Attachment has neither data nor url")
                resp = await client.post(
                    f"{self._api_root}/sendDocument",
                    data={"chat_id": chat_id, "caption": message.content},
                    files=files,
                )
            else:
                payload: dict[str, Any] = {
                    "chat_id": chat_id,
                    "text": message.content,
                    "parse_mode": message.metadata.get("parse_mode", "Markdown"),
                }
                keyboard = self._inline_keyboard(message)
                if keyboard:
                    payload["reply_markup"] = keyboard
                resp = await client.post(
                    f"{self._api_root}/sendMessage", json=payload
                )

            data = resp.json()
            if not data.get("ok"):
                raise GatewayError(
                    f"Telegram send failed: {data.get('description', resp.status_code)}"
                )
            self.messages_sent += 1
            message.direction = "outbound"
            self.history.append(message)
            return data.get("result", {})
        except httpx.HTTPError as exc:
            self._mark_error(str(exc))
            raise GatewayError(f"Telegram send transport error: {exc}") from exc

    # ── Inbound ───────────────────────────────────────────────────────────

    def verify_signature(self, body: bytes, headers: dict[str, str]) -> bool:
        """Verify the ``X-Telegram-Bot-Api-Secret-Token`` webhook header.

        When no secret is configured verification is skipped (dev mode).
        """
        if not self.webhook_secret:
            return True
        provided = headers.get("x-telegram-bot-api-secret-token") or headers.get(
            "X-Telegram-Bot-Api-Secret-Token", ""
        )
        return hmac.compare_digest(provided, self.webhook_secret)

    async def webhook_handler(
        self, body: bytes, headers: dict[str, str]
    ) -> dict[str, Any]:
        """Parse a Telegram Update object into a :class:`GatewayMessage`."""
        if not self.verify_signature(body, headers):
            raise GatewaySignatureError("Invalid Telegram webhook secret token")
        try:
            update = json.loads(body.decode("utf-8") or "{}")
        except json.JSONDecodeError as exc:
            raise GatewayError(f"Invalid Telegram update JSON: {exc}") from exc

        message_obj: dict[str, Any] | None = None
        is_callback = False
        if "message" in update:
            message_obj = update["message"]
        elif "edited_message" in update:
            message_obj = update["edited_message"]
        elif "callback_query" in update:
            cb = update["callback_query"]
            message_obj = cb.get("message") or {}
            message_obj = dict(message_obj)
            message_obj["text"] = cb.get("data", "")
            is_callback = True

        if message_obj is None:
            return {"ok": True, "ignored": True}

        chat = message_obj.get("chat") or {}
        sender = message_obj.get("from") or {}
        attachments: list[Attachment] = []
        for doc_key in ("document", "photo", "audio", "video"):
            raw_att = message_obj.get(doc_key)
            if raw_att:
                items = raw_att if isinstance(raw_att, list) else [raw_att]
                for item in items:
                    attachments.append(
                        Attachment(
                            filename=item.get("file_name", doc_key),
                            content_type=item.get("mime_type", "application/octet-stream"),
                            url=None,  # resolvable via getFile API using file_id
                        )
                    )
                break

        gateway_message = GatewayMessage(
            platform=self.platform.value,
            channel_id=str(chat.get("id", "")),
            user_id=str(sender.get("id", "")),
            content=str(message_obj.get("text", "")),
            kind=MessageKind.INTERACTIVE if is_callback else MessageKind.TEXT,
            attachments=attachments,
            metadata={
                "update_id": update.get("update_id"),
                "message_id": message_obj.get("message_id"),
                "chat_type": chat.get("type"),
                "username": sender.get("username"),
                "callback_query_id": update.get("callback_query", {}).get("id")
                if is_callback
                else None,
            },
        )
        await self._dispatch_inbound(gateway_message)
        return {"ok": True, "message_id": gateway_message.message_id}


# ─── Discord Gateway ──────────────────────────────────────────────────────────


class DiscordGateway(MessageGateway):
    """Discord bot gateway: REST messaging + slash commands + WS listener.

    - Outbound: ``POST /channels/{id}/messages`` with components (buttons)
      and multipart file attachments.
    - Slash commands: registered via ``PUT /applications/{app_id}/commands``.
    - Inbound: Ed25519-verified interaction webhooks, plus an optional
      Gateway websocket listener (HELLO → IDENTIFY → heartbeat → dispatch)
      with automatic RESUME/reconnect when the ``websockets`` package is
      installed.
    """

    platform = GatewayPlatform.DISCORD
    _API = "https://discord.com/api/v10"
    _GATEWAY_URL = "wss://gateway.discord.gg/?v=10&encoding=json"

    def __init__(
        self,
        bot_token: str,
        public_key: str = "",
        application_id: str = "",
        base_url: str = "",
        commands: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__()
        self.bot_token = bot_token
        self.public_key = public_key
        self.application_id = application_id
        self._base = (base_url or self._API).rstrip("/")
        self._commands = commands or [
            {
                "name": "ask",
                "description": "Ask X-Agent a question",
                "options": [
                    {
                        "name": "question",
                        "description": "Your question",
                        "type": 3,  # STRING
                        "required": True,
                    }
                ],
            }
        ]
        self._ws_task: asyncio.Task[None] | None = None
        self._ws_stop = asyncio.Event()
        self._session_id: str | None = None
        self._resume_url: str | None = None
        self._seq: int | None = None

    @property
    def configured(self) -> bool:
        return bool(self.bot_token)

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bot {self.bot_token}",
            "Content-Type": "application/json",
        }

    def _require_configured(self) -> None:
        if not self.configured:
            raise GatewayNotConfiguredError(
                "Discord gateway not configured: set discord_bot_token"
            )

    # ── Connection ────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Validate the token, resolve the application id, register slash commands."""
        self._require_configured()
        self.state = GatewayState.CONNECTING
        client = await self._http()
        try:
            me = await client.get(
                f"{self._base}/users/@me", headers=self._auth_headers()
            )
            if me.status_code != 200:
                raise GatewayConnectionError(
                    f"Discord auth failed ({me.status_code}): {me.text[:200]}"
                )
            me_data = me.json()
            if not self.application_id:
                # For most bots user id == application id.
                self.application_id = str(me_data.get("id", ""))
            await self._register_slash_commands()
            self._mark_connected()
            logger.info("Discord gateway connected as %s", me_data.get("username"))
            self._start_ws_listener()
        except httpx.HTTPError as exc:
            self._mark_error(str(exc))
            raise GatewayConnectionError(f"Discord connect failed: {exc}") from exc

    async def _register_slash_commands(self) -> None:
        """Register global application (slash) commands."""
        if not self.application_id or not self._commands:
            return
        client = await self._http()
        resp = await client.put(
            f"{self._base}/applications/{self.application_id}/commands",
            headers=self._auth_headers(),
            json=self._commands,
        )
        if resp.status_code >= 300:
            logger.warning(
                "Discord slash command registration failed (%s): %s",
                resp.status_code,
                resp.text[:200],
            )

    def _start_ws_listener(self) -> None:
        """Start the Gateway websocket listener if ``websockets`` is available."""
        if self._ws_task is not None and not self._ws_task.done():
            return
        try:
            import websockets  # noqa: F401  # optional dependency probe
        except ImportError:
            logger.info(
                "Discord WS listener disabled: install 'websockets' for realtime events"
            )
            return
        self._ws_stop.clear()
        self._ws_task = asyncio.create_task(self._ws_loop(), name="discord-gateway-ws")

    async def _ws_loop(self) -> None:
        """Discord Gateway websocket loop with heartbeat + reconnect (discord.py pattern)."""
        import websockets

        backoff = 1.0
        while not self._ws_stop.is_set():
            url = self._resume_url or self._GATEWAY_URL
            try:
                async with websockets.connect(url) as ws:
                    hello = json.loads(await ws.recv())
                    interval = hello["d"]["heartbeat_interval"] / 1000.0
                    hb_task = asyncio.create_task(self._heartbeat_loop(ws, interval))
                    await self._ws_identify(ws, resume=self._resume_url is not None)
                    try:
                        async for raw in ws:
                            event = json.loads(raw)
                            await self._ws_dispatch(event)
                    finally:
                        hb_task.cancel()
                backoff = 1.0  # clean close → reset backoff
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self._ws_stop.is_set():
                    break
                logger.warning("Discord WS error (%s); reconnecting in %.1fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

    async def _heartbeat_loop(self, ws: Any, interval: float) -> None:
        while True:
            await asyncio.sleep(interval)
            await ws.send(json.dumps({"op": 1, "d": self._seq}))

    async def _ws_identify(self, ws: Any, *, resume: bool) -> None:
        if resume and self._session_id:
            await ws.send(
                json.dumps(
                    {
                        "op": 6,
                        "d": {
                            "token": self.bot_token,
                            "session_id": self._session_id,
                            "seq": self._seq,
                        },
                    }
                )
            )
        else:
            await ws.send(
                json.dumps(
                    {
                        "op": 2,
                        "d": {
                            "token": self.bot_token,
                            "intents": (1 << 12) | (1 << 15),  # GUILD_MESSAGES | MESSAGE_CONTENT
                            "properties": {
                                "os": "linux",
                                "browser": "x-agent",
                                "device": "x-agent",
                            },
                        },
                    }
                )
            )

    async def _ws_dispatch(self, event: dict[str, Any]) -> None:
        op = event.get("op")
        if event.get("s") is not None:
            self._seq = event["s"]
        if op == 10:  # HELLO (handled before recv loop, kept for safety)
            return
        if op == 7:  # RECONNECT requested
            raise ConnectionError("Discord requested reconnect")
        if op == 9:  # INVALID SESSION — resumable flag in d
            self._resume_url = None if not event.get("d") else self._resume_url
            raise ConnectionError("Discord invalid session")
        if op != 0:
            return
        event_name = event.get("t")
        data = event.get("d") or {}
        if event_name == "READY":
            self._session_id = data.get("session_id")
            self._resume_url = data.get("resume_gateway_url")
        elif event_name == "MESSAGE_CREATE":
            author = data.get("author") or {}
            if author.get("bot"):
                return  # ignore other bots (and ourselves)
            gateway_message = GatewayMessage(
                platform=self.platform.value,
                channel_id=str(data.get("channel_id", "")),
                user_id=str(author.get("id", "")),
                content=str(data.get("content", "")),
                kind=MessageKind.TEXT,
                attachments=[
                    Attachment(
                        filename=a.get("filename", "file"),
                        content_type=a.get("content_type", "application/octet-stream"),
                        url=a.get("url"),
                    )
                    for a in data.get("attachments", [])
                ],
                metadata={"discord_message_id": data.get("id"), "guild_id": data.get("guild_id")},
            )
            await self._dispatch_inbound(gateway_message)

    async def disconnect(self) -> None:
        """Stop the WS listener and close the HTTP client."""
        self._ws_stop.set()
        if self._ws_task is not None:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except (asyncio.CancelledError, Exception):
                pass
            self._ws_task = None
        await self._close_http()
        self.state = GatewayState.DISCONNECTED
        self.connected_at = None

    # ── Outbound ──────────────────────────────────────────────────────────

    def _components(self, message: GatewayMessage) -> list[dict[str, Any]]:
        """Map unified buttons to Discord message components (action rows)."""
        if not message.buttons:
            return []
        style_map = {"primary": 1, "default": 2, "danger": 4, "link": 5}
        components: list[dict[str, Any]] = []
        row: list[dict[str, Any]] = []
        for btn in message.buttons:
            style = style_map.get(btn.style, 2)
            if btn.url:
                style = 5
            comp: dict[str, Any] = {
                "type": 2,  # BUTTON
                "label": btn.label[:80],
                "style": style,
            }
            if style == 5:
                comp["url"] = btn.url or ""
            else:
                comp["custom_id"] = btn.value[:100]
            row.append(comp)
            if len(row) == 5:  # Discord max 5 buttons per row
                components.append({"type": 1, "components": row})
                row = []
        if row:
            components.append({"type": 1, "components": row})
        return components

    async def send(self, message: GatewayMessage) -> dict[str, Any]:
        """Post a message (with components / attachments) to a Discord channel."""
        self._require_configured()
        channel_id = message.channel_id
        if not channel_id:
            raise GatewayError("Discord send requires channel_id")
        client = await self._http()
        url = f"{self._base}/channels/{channel_id}/messages"
        try:
            payload: dict[str, Any] = {"content": message.content[:2000]}
            components = self._components(message)
            if components:
                payload["components"] = components
            if message.card:
                # Rich card → embed
                payload["embeds"] = [
                    {
                        "title": str(message.card.get("title", ""))[:256],
                        "description": str(
                            message.card.get("description", message.content)
                        )[:4096],
                        "fields": [
                            {"name": str(k)[:256], "value": str(v)[:1024]}
                            for k, v in (message.card.get("fields") or {}).items()
                        ][:25],
                    }
                ]

            file_atts = [a for a in message.attachments if a.data is not None]
            if file_atts:
                files: dict[str, tuple[str, bytes, str]] = {}
                for idx, att in enumerate(file_atts[:10]):
                    files[f"files[{idx}]"] = (att.filename, att.data, att.content_type)
                payload["attachments"] = [
                    {"id": idx, "filename": att.filename}
                    for idx, att in enumerate(file_atts[:10])
                ]
                resp = await client.post(
                    url,
                    headers={"Authorization": f"Bot {self.bot_token}"},
                    data={"payload_json": json.dumps(payload)},
                    files=files,
                )
            else:
                resp = await client.post(url, headers=self._auth_headers(), json=payload)

            if resp.status_code >= 300:
                raise GatewayError(
                    f"Discord send failed ({resp.status_code}): {resp.text[:300]}"
                )
            self.messages_sent += 1
            message.direction = "outbound"
            self.history.append(message)
            return resp.json()
        except httpx.HTTPError as exc:
            self._mark_error(str(exc))
            raise GatewayError(f"Discord send transport error: {exc}") from exc

    # ── Inbound ───────────────────────────────────────────────────────────

    def verify_signature(self, body: bytes, headers: dict[str, str]) -> bool:
        """Ed25519 verification of X-Signature-Ed25519 / X-Signature-Timestamp."""
        sig = headers.get("x-signature-ed25519") or headers.get("X-Signature-Ed25519", "")
        ts = headers.get("x-signature-timestamp") or headers.get("X-Signature-Timestamp", "")
        if not self.public_key or not sig or not ts:
            return False
        message_bytes = ts.encode("utf-8") + body
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PublicKey,
            )

            key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(self.public_key))
            key.verify(bytes.fromhex(sig), message_bytes)
            return True
        except ImportError:
            pass
        except Exception:
            return False
        try:  # fallback: PyNaCl
            from nacl.signing import VerifyKey  # type: ignore

            VerifyKey(bytes.fromhex(self.public_key)).verify(
                message_bytes, bytes.fromhex(sig)
            )
            return True
        except Exception:
            return False

    async def webhook_handler(
        self, body: bytes, headers: dict[str, str]
    ) -> dict[str, Any]:
        """Handle Discord interaction webhooks (PING / commands / components)."""
        if not self.verify_signature(body, headers):
            raise GatewaySignatureError("Invalid Discord interaction signature")
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except json.JSONDecodeError as exc:
            raise GatewayError(f"Invalid Discord interaction JSON: {exc}") from exc

        interaction_type = payload.get("type")
        if interaction_type == 1:  # PING → PONG
            return {"type": 1}

        user = payload.get("member", {}).get("user") or payload.get("user") or {}
        data = payload.get("data") or {}
        if interaction_type == 2:  # APPLICATION_COMMAND (slash command)
            content = " ".join(
                str(opt.get("value", "")) for opt in data.get("options", [])
            ) or data.get("name", "")
            kind = MessageKind.INTERACTIVE
        elif interaction_type == 3:  # MESSAGE_COMPONENT (button press)
            content = data.get("custom_id", "")
            kind = MessageKind.INTERACTIVE
        else:
            return {"type": 1}

        gateway_message = GatewayMessage(
            platform=self.platform.value,
            channel_id=str(payload.get("channel_id") or payload.get("channel", {}).get("id", "")),
            user_id=str(user.get("id", "")),
            content=content,
            kind=kind,
            metadata={
                "interaction_id": payload.get("id"),
                "interaction_token": payload.get("token"),
                "command_name": data.get("name"),
                "component_type": data.get("component_type"),
            },
        )
        await self._dispatch_inbound(gateway_message)
        # Respond inline with a deferred message so Discord doesn't time out.
        return {
            "type": 4,
            "data": {"content": message_ack(gateway_message.content)},
        }


def message_ack(content: str) -> str:
    """Default acknowledgement text for interaction responses."""
    return f"✅ Received: {content[:120]}" if content else "✅ Received"


# ─── DingTalk Gateway ─────────────────────────────────────────────────────────


class DingTalkGateway(MessageGateway):
    """DingTalk (钉钉) enterprise robot gateway.

    - Auth: ``gettoken`` via app_key / app_secret (auto-refresh on expiry).
    - Outbound: signed custom-robot webhook (text / actionCard / markdown) or
      the server API ``robot/oToMessages/batchSend`` for 1:1 messages.
    - Inbound: outgoing-robot callbacks verified with HMAC-SHA256 over
      ``"{timestamp}\\n{app_secret}"`` (``timestamp`` + ``sign`` headers).
    """

    platform = GatewayPlatform.DINGTALK
    _OAPI = "https://oapi.dingtalk.com"
    _API = "https://api.dingtalk.com"
    _TOKEN_TTL_MARGIN = 300.0  # refresh 5 minutes before expiry

    def __init__(
        self,
        app_key: str = "",
        app_secret: str = "",
        webhook_url: str = "",
        robot_code: str = "",
        oapi_base: str = "",
        api_base: str = "",
    ) -> None:
        super().__init__()
        self.app_key = app_key
        self.app_secret = app_secret
        self.webhook_url = webhook_url
        self.robot_code = robot_code or app_key
        self._oapi = (oapi_base or self._OAPI).rstrip("/")
        self._api = (api_base or self._API).rstrip("/")
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    @property
    def configured(self) -> bool:
        return bool(self.app_key and self.app_secret) or bool(self.webhook_url)

    def _require_configured(self) -> None:
        if not self.configured:
            raise GatewayNotConfiguredError(
                "DingTalk gateway not configured: set dingtalk_app_key/dingtalk_app_secret "
                "or dingtalk_webhook_url"
            )

    # ── Auth ──────────────────────────────────────────────────────────────

    async def _ensure_token(self) -> str:
        """Return a valid access token, refreshing when expired."""
        if (
            self._access_token
            and time.time() < self._token_expires_at - self._TOKEN_TTL_MARGIN
        ):
            return self._access_token
        if not (self.app_key and self.app_secret):
            raise GatewayNotConfiguredError(
                "DingTalk access token requires dingtalk_app_key and dingtalk_app_secret"
            )
        client = await self._http()
        resp = await client.get(
            f"{self._oapi}/gettoken",
            params={"appkey": self.app_key, "appsecret": self.app_secret},
        )
        data = resp.json()
        if data.get("errcode") != 0:
            raise GatewayConnectionError(
                f"DingTalk gettoken failed: {data.get('errmsg', resp.status_code)}"
            )
        self._access_token = data["access_token"]
        self._token_expires_at = time.time() + float(data.get("expires_in", 7200))
        return self._access_token

    async def connect(self) -> None:
        """Fetch an access token to validate app credentials."""
        self._require_configured()
        self.state = GatewayState.CONNECTING
        try:
            if self.app_key and self.app_secret:
                await self._ensure_token()
            self._mark_connected()
            logger.info("DingTalk gateway connected (app_key=%s***)", self.app_key[:4])
        except httpx.HTTPError as exc:
            self._mark_error(str(exc))
            raise GatewayConnectionError(f"DingTalk connect failed: {exc}") from exc

    async def disconnect(self) -> None:
        await self._close_http()
        self._access_token = None
        self._token_expires_at = 0.0
        self.state = GatewayState.DISCONNECTED
        self.connected_at = None

    # ── Signing ───────────────────────────────────────────────────────────

    def _sign_webhook(self) -> dict[str, str]:
        """Compute (timestamp, sign) query params for the custom robot webhook."""
        ts = str(round(time.time() * 1000))
        string_to_sign = f"{ts}\n{self.app_secret}"
        digest = hmac.new(
            self.app_secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return {"timestamp": ts, "sign": base64.b64encode(digest).decode("utf-8")}

    def verify_signature(self, body: bytes, headers: dict[str, str]) -> bool:
        """Verify outgoing-robot callback headers (``timestamp`` + ``sign``)."""
        if not self.app_secret:
            return True  # dev mode: no secret configured
        ts = headers.get("timestamp", "")
        provided = headers.get("sign", "")
        if not ts or not provided:
            return False
        # Reject stale timestamps (±1h) to block replay attacks.
        try:
            if abs(time.time() * 1000 - int(ts)) > 3_600_000:
                return False
        except ValueError:
            return False
        string_to_sign = f"{ts}\n{self.app_secret}"
        digest = hmac.new(
            self.app_secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        expected = base64.b64encode(digest).decode("utf-8")
        return hmac.compare_digest(expected, provided)

    # ── Outbound ──────────────────────────────────────────────────────────

    def _build_robot_body(self, message: GatewayMessage) -> dict[str, Any]:
        """Map a unified message to a DingTalk robot webhook payload."""
        if message.kind in (MessageKind.CARD, MessageKind.INTERACTIVE) and (
            message.buttons or message.card
        ):
            btns = [
                {"title": b.label, "actionURL": b.url or f"dtmd://dingtalkclient/sendMessage?content={urllib.parse.quote(b.value)}"}
                for b in message.buttons
            ]
            return {
                "msgtype": "actionCard",
                "actionCard": {
                    "title": (message.card or {}).get("title", "X-Agent"),
                    "text": message.card.get("text", message.content)
                    if message.card
                    else message.content,
                    "btnOrientation": "0",
                    "btns": btns,
                },
            }
        if message.kind == MessageKind.FILE and message.attachments:
            att = message.attachments[0]
            return {
                "msgtype": "link",
                "link": {
                    "title": att.filename,
                    "text": message.content or att.filename,
                    "messageUrl": att.url or "",
                },
            }
        return {"msgtype": "text", "text": {"content": message.content}}

    async def send(self, message: GatewayMessage) -> dict[str, Any]:
        """Send via custom robot webhook or the 1:1 batchSend server API."""
        self._require_configured()
        client = await self._http()
        try:
            use_webhook = bool(self.webhook_url) and not message.metadata.get(
                "use_server_api"
            )
            if use_webhook:
                params = self._sign_webhook() if self.app_secret else {}
                resp = await client.post(
                    self.webhook_url,
                    params=params,
                    json=self._build_robot_body(message),
                )
                data = resp.json()
                if data.get("errcode") not in (0, None):
                    raise GatewayError(f"DingTalk webhook send failed: {data.get('errmsg')}")
            else:
                token = await self._ensure_token()
                user_ids = [message.user_id] if message.user_id else []
                if not user_ids:
                    raise GatewayError(
                        "DingTalk server API send requires user_id (staffId)"
                    )
                sample = (
                    "sampleActionCard"
                    if message.kind in (MessageKind.CARD, MessageKind.INTERACTIVE)
                    else "sampleText"
                )
                param = (
                    json.dumps({"title": "X-Agent", "text": message.content})
                    if sample == "sampleActionCard"
                    else json.dumps({"content": message.content})
                )
                resp = await client.post(
                    f"{self._api}/v1.0/robot/oToMessages/batchSend",
                    headers={"x-acs-dingtalk-access-token": token},
                    json={
                        "robotCode": self.robot_code,
                        "userIds": user_ids,
                        "msgKey": sample,
                        "msgParam": param,
                    },
                )
                if resp.status_code >= 300:
                    raise GatewayError(
                        f"DingTalk batchSend failed ({resp.status_code}): {resp.text[:300]}"
                    )
                data = resp.json()
            self.messages_sent += 1
            message.direction = "outbound"
            self.history.append(message)
            return data
        except httpx.HTTPError as exc:
            self._mark_error(str(exc))
            raise GatewayError(f"DingTalk send transport error: {exc}") from exc

    # ── Inbound ───────────────────────────────────────────────────────────

    async def webhook_handler(
        self, body: bytes, headers: dict[str, str]
    ) -> dict[str, Any]:
        """Parse an outgoing-robot callback into a :class:`GatewayMessage`."""
        if not self.verify_signature(body, headers):
            raise GatewaySignatureError("Invalid DingTalk callback signature")
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except json.JSONDecodeError as exc:
            raise GatewayError(f"Invalid DingTalk callback JSON: {exc}") from exc

        text_obj = payload.get("text") or {}
        content = str(text_obj.get("content", "")).strip()
        if not content and payload.get("msgtype") not in ("text", None):
            content = f"[{payload.get('msgtype', 'event')}]"
        gateway_message = GatewayMessage(
            platform=self.platform.value,
            channel_id=str(
                payload.get("conversationId")
                or payload.get("chatbotCorpId")
                or ""
            ),
            user_id=str(payload.get("senderStaffId") or payload.get("senderId", "")),
            content=content,
            kind=MessageKind.TEXT,
            metadata={
                "conversation_type": payload.get("conversationType"),
                "sender_nick": payload.get("senderNick"),
                "session_webhook": payload.get("sessionWebhook"),
                "msg_id": payload.get("msgId"),
            },
        )
        await self._dispatch_inbound(gateway_message)
        return {"ok": True, "message_id": gateway_message.message_id}


# ─── Feishu Gateway ───────────────────────────────────────────────────────────


class FeishuGateway(MessageGateway):
    """Feishu / Lark open-platform gateway.

    - Auth: internal app ``tenant_access_token`` (auto-refresh on expiry).
    - Outbound: ``im/v1/messages`` with msg_type text / interactive (card) /
      post; files uploaded via ``im/v1/files`` then sent as file messages.
    - Inbound: event-subscription v2 callbacks — ``url_verification``
      challenge echo + SHA256 signature verification
      (``sha256(timestamp + nonce + encrypt_key + body)``).
    """

    platform = GatewayPlatform.FEISHU
    _BASE = "https://open.feishu.cn"
    _TOKEN_TTL_MARGIN = 300.0

    def __init__(
        self,
        app_id: str = "",
        app_secret: str = "",
        encrypt_key: str = "",
        verification_token: str = "",
        base_url: str = "",
    ) -> None:
        super().__init__()
        self.app_id = app_id
        self.app_secret = app_secret
        self.encrypt_key = encrypt_key
        self.verification_token = verification_token
        self._base = (base_url or self._BASE).rstrip("/")
        self._tenant_token: str | None = None
        self._token_expires_at: float = 0.0

    @property
    def configured(self) -> bool:
        return bool(self.app_id and self.app_secret)

    def _require_configured(self) -> None:
        if not self.configured:
            raise GatewayNotConfiguredError(
                "Feishu gateway not configured: set feishu_app_id and feishu_app_secret"
            )

    # ── Auth ──────────────────────────────────────────────────────────────

    async def _ensure_token(self) -> str:
        """Return a valid tenant_access_token, refreshing when expired."""
        if (
            self._tenant_token
            and time.time() < self._token_expires_at - self._TOKEN_TTL_MARGIN
        ):
            return self._tenant_token
        self._require_configured()
        client = await self._http()
        resp = await client.post(
            f"{self._base}/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
        )
        data = resp.json()
        if data.get("code") != 0:
            raise GatewayConnectionError(
                f"Feishu tenant token failed: {data.get('msg', resp.status_code)}"
            )
        self._tenant_token = data["tenant_access_token"]
        self._token_expires_at = time.time() + float(data.get("expire", 7200))
        return self._tenant_token

    async def connect(self) -> None:
        """Obtain a tenant_access_token to validate app credentials."""
        self._require_configured()
        self.state = GatewayState.CONNECTING
        try:
            await self._ensure_token()
            self._mark_connected()
            logger.info("Feishu gateway connected (app_id=%s***)", self.app_id[:4])
        except httpx.HTTPError as exc:
            self._mark_error(str(exc))
            raise GatewayConnectionError(f"Feishu connect failed: {exc}") from exc

    async def disconnect(self) -> None:
        await self._close_http()
        self._tenant_token = None
        self._token_expires_at = 0.0
        self.state = GatewayState.DISCONNECTED
        self.connected_at = None

    # ── Signature ─────────────────────────────────────────────────────────

    def verify_signature(self, body: bytes, headers: dict[str, str]) -> bool:
        """Feishu event signature: sha256(timestamp + nonce + encrypt_key + body)."""
        if not self.encrypt_key:
            return True  # dev mode
        signature = (
            headers.get("x-lark-signature")
            or headers.get("X-Lark-Signature")
            or headers.get("x-feishu-signature")
            or headers.get("X-Feishu-Signature")
            or ""
        )
        timestamp = (
            headers.get("x-lark-request-timestamp")
            or headers.get("X-Lark-Request-Timestamp")
            or headers.get("x-feishu-timestamp")
            or headers.get("X-Feishu-Timestamp")
            or ""
        )
        nonce = (
            headers.get("x-lark-request-nonce")
            or headers.get("X-Lark-Request-Nonce")
            or headers.get("x-feishu-nonce")
            or headers.get("X-Feishu-Nonce")
            or ""
        )
        if not signature or not timestamp or not nonce:
            return False
        content = timestamp.encode() + nonce.encode() + self.encrypt_key.encode() + body
        expected = hashlib.sha256(content).hexdigest()
        return hmac.compare_digest(expected, signature)

    # ── Outbound ──────────────────────────────────────────────────────────

    def _build_message_payload(self, message: GatewayMessage) -> tuple[str, str]:
        """Return (msg_type, content-json) for im/v1/messages."""
        if message.kind in (MessageKind.CARD, MessageKind.INTERACTIVE) and (
            message.card or message.buttons
        ):
            card = message.card or {}
            elements: list[dict[str, Any]] = [
                {"tag": "div", "text": {"tag": "lark_md", "content": message.content}}
            ]
            if message.buttons:
                elements.append(
                    {
                        "tag": "action",
                        "actions": [
                            {
                                "tag": "button",
                                "text": {"tag": "plain_text", "content": b.label},
                                "type": "danger" if b.style == "danger" else "default",
                                "url": b.url,
                                "value": {"key": b.value},
                            }
                            for b in message.buttons
                        ],
                    }
                )
            interactive = {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": card.get("title", "X-Agent")},
                },
                "elements": elements,
            }
            return "interactive", json.dumps(interactive)
        return "text", json.dumps({"text": message.content})

    async def _upload_file(self, att: Attachment) -> str:
        """Upload a file via im/v1/files and return the file_key."""
        token = await self._ensure_token()
        client = await self._http()
        file_type = "stream"
        if att.content_type.startswith("image/"):
            file_type = "image"
        elif att.content_type.startswith(("audio/", "video/")):
            file_type = att.content_type.split("/", 1)[0]
        resp = await client.post(
            f"{self._base}/open-apis/im/v1/files",
            headers={"Authorization": f"Bearer {token}"},
            data={"file_type": file_type, "file_name": att.filename},
            files={"file": (att.filename, att.data or b"", att.content_type)},
        )
        data = resp.json()
        if data.get("code") != 0:
            raise GatewayError(f"Feishu file upload failed: {data.get('msg')}")
        return data["data"]["file_key"]

    async def send(self, message: GatewayMessage) -> dict[str, Any]:
        """Send a message to a Feishu chat / user via im/v1/messages."""
        self._require_configured()
        receive_id = message.channel_id or message.user_id
        if not receive_id:
            raise GatewayError("Feishu send requires channel_id (chat_id) or user_id")
        receive_id_type = str(message.metadata.get("receive_id_type", "chat_id"))
        token = await self._ensure_token()
        client = await self._http()
        try:
            if message.kind == MessageKind.FILE and message.attachments:
                att = message.attachments[0]
                if att.data is None:
                    raise GatewayError("Feishu file send requires attachment data")
                file_key = await self._upload_file(att)
                msg_type, content = "file", json.dumps({"file_key": file_key})
            else:
                msg_type, content = self._build_message_payload(message)

            resp = await client.post(
                f"{self._base}/open-apis/im/v1/messages",
                params={"receive_id_type": receive_id_type},
                headers={"Authorization": f"Bearer {token}"},
                json={"receive_id": receive_id, "msg_type": msg_type, "content": content},
            )
            data = resp.json()
            if data.get("code") != 0:
                raise GatewayError(
                    f"Feishu send failed: {data.get('msg', resp.status_code)}"
                )
            self.messages_sent += 1
            message.direction = "outbound"
            self.history.append(message)
            return data.get("data", {})
        except httpx.HTTPError as exc:
            self._mark_error(str(exc))
            raise GatewayError(f"Feishu send transport error: {exc}") from exc

    # ── Inbound ───────────────────────────────────────────────────────────

    async def webhook_handler(
        self, body: bytes, headers: dict[str, str]
    ) -> dict[str, Any]:
        """Handle Feishu event-subscription callbacks (v1 schema + v2 schema)."""
        if not self.verify_signature(body, headers):
            raise GatewaySignatureError("Invalid Feishu event signature")
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except json.JSONDecodeError as exc:
            raise GatewayError(f"Invalid Feishu event JSON: {exc}") from exc

        # URL verification handshake (challenge echo).
        if payload.get("type") == "url_verification":
            return {"challenge": payload.get("challenge", "")}
        # v2 schema wraps the event; v1 may carry token at top level.
        if self.verification_token:
            token = payload.get("token") or payload.get("header", {}).get("token")
            if token and not hmac.compare_digest(token, self.verification_token):
                raise GatewaySignatureError("Invalid Feishu verification token")

        header = payload.get("header") or {}
        event = payload.get("event") or payload
        event_type = header.get("event_type") or payload.get("event", {}).get("type", "")

        # im.message.receive_v1 (v2) or message event (v1)
        message_obj = event.get("message") or event.get("event", {}).get("message") or {}
        sender = event.get("sender") or {}
        sender_id = (
            sender.get("sender_id", {}).get("open_id")
            or sender.get("sender_id", {}).get("user_id")
            or event.get("open_id", "")
        )
        content_raw = message_obj.get("content", "")
        try:
            content = json.loads(content_raw).get("text", content_raw) if content_raw else ""
        except (json.JSONDecodeError, AttributeError):
            content = str(content_raw)

        if not message_obj and event_type not in ("", "im.message.receive_v1"):
            # Non-message event (e.g. bot added) — record as metadata only.
            return {"ok": True, "event_type": event_type, "ignored": True}

        gateway_message = GatewayMessage(
            platform=self.platform.value,
            channel_id=str(message_obj.get("chat_id", "")),
            user_id=str(sender_id),
            content=str(content),
            kind=MessageKind.TEXT,
            metadata={
                "event_type": event_type,
                "message_type": message_obj.get("message_type"),
                "feishu_message_id": message_obj.get("message_id"),
                "chat_type": message_obj.get("chat_type"),
            },
        )
        await self._dispatch_inbound(gateway_message)
        return {"ok": True, "message_id": gateway_message.message_id}


# ─── Gateway Manager ──────────────────────────────────────────────────────────


class GatewayManager:
    """Central registry + router for all platform gateways.

    Responsibilities:
    - Registry: register / lookup gateways by platform name.
    - Outbound queue: async worker drains queued messages with retry + backoff.
    - Inbound routing: fans gateway events out to application handlers.
    - History & health: per-platform message history and aggregated status.
    """

    def __init__(self, queue_size: int = 1000) -> None:
        self._gateways: dict[str, MessageGateway] = {}
        self._queue: asyncio.Queue[GatewayMessage] = asyncio.Queue(maxsize=queue_size)
        self._worker_task: asyncio.Task[None] | None = None
        self._inbound_handlers: list[MessageHandler] = []
        self._stop = asyncio.Event()

    # ── Registry ──────────────────────────────────────────────────────────

    def register(self, gateway: MessageGateway) -> None:
        """Register a gateway and wire its inbound events into the manager."""
        self._gateways[gateway.platform.value] = gateway
        gateway.on_message(self._route_inbound)

    def get(self, platform: str) -> MessageGateway:
        """Return the gateway for a platform or raise ``GatewayError``."""
        gateway = self._gateways.get(platform)
        if gateway is None:
            raise GatewayError(f"Unknown gateway platform: {platform!r}")
        return gateway

    def platforms(self) -> list[str]:
        return list(self._gateways.keys())

    # ── Inbound routing ───────────────────────────────────────────────────

    def on_inbound(self, handler: MessageHandler) -> None:
        """Subscribe to inbound messages from every registered gateway."""
        self._inbound_handlers.append(handler)

    async def _route_inbound(self, message: GatewayMessage) -> None:
        for handler in self._inbound_handlers:
            try:
                await handler(message)
            except Exception:
                logger.exception("Gateway inbound handler failed for %s", message.platform)

    # ── Outbound queue ────────────────────────────────────────────────────

    async def enqueue(self, message: GatewayMessage) -> str:
        """Queue a message for async delivery; returns the message id."""
        await self._queue.put(message)
        return message.message_id

    async def send_now(self, message: GatewayMessage) -> dict[str, Any]:
        """Deliver a message immediately with retry (bypasses the queue)."""
        gateway = self.get(message.platform)
        last_exc: Exception | None = None
        for attempt in range(1, _MAX_SEND_ATTEMPTS + 1):
            try:
                return await gateway.send(message)
            except GatewayNotConfiguredError:
                raise
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Gateway send to %s failed (attempt %d/%d): %s",
                    message.platform,
                    attempt,
                    _MAX_SEND_ATTEMPTS,
                    exc,
                )
                if attempt < _MAX_SEND_ATTEMPTS:
                    await asyncio.sleep(_RETRY_BACKOFF_SECONDS * attempt)
        raise GatewayError(
            f"Gateway send to {message.platform} failed after {_MAX_SEND_ATTEMPTS} attempts: {last_exc}"
        )

    async def _worker(self) -> None:
        """Drain the outbound queue until stopped."""
        while not self._stop.is_set():
            try:
                message = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except TimeoutError:
                continue
            try:
                await self.send_now(message)
            except Exception:
                logger.error(
                    "Dropping undeliverable %s message %s",
                    message.platform,
                    message.message_id,
                )
            finally:
                self._queue.task_done()

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def start(self, *, auto_connect: bool = True) -> None:
        """Start the outbound worker and connect all configured gateways."""
        self._stop.clear()
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(
                self._worker(), name="gateway-manager-worker"
            )
        if auto_connect:
            for gateway in self._gateways.values():
                if gateway.configured:
                    try:
                        await gateway.connect()
                    except GatewayError as exc:
                        logger.warning(
                            "%s gateway auto-connect failed: %s",
                            gateway.platform.value,
                            exc,
                        )

    async def stop(self) -> None:
        """Stop the worker and disconnect every gateway."""
        self._stop.set()
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except (asyncio.CancelledError, Exception):
                pass
            self._worker_task = None
        for gateway in self._gateways.values():
            try:
                await gateway.disconnect()
            except Exception:
                logger.warning(
                    "%s gateway disconnect failed", gateway.platform.value
                )

    # ── Observability ─────────────────────────────────────────────────────

    def health(self) -> dict[str, Any]:
        """Aggregated health snapshot across all gateways."""
        gateways = {name: gw.health() for name, gw in self._gateways.items()}
        connected = sum(
            1 for gw in self._gateways.values() if gw.state == GatewayState.CONNECTED
        )
        return {
            "total": len(self._gateways),
            "connected": connected,
            "queue_depth": self._queue.qsize(),
            "worker_running": self._worker_task is not None
            and not self._worker_task.done(),
            "gateways": gateways,
        }

    def history(
        self, platform: str, *, limit: int = 50, direction: str | None = None
    ) -> list[dict[str, Any]]:
        """Return recent messages for a platform (newest first)."""
        gateway = self.get(platform)
        items: list[GatewayMessage] = list(gateway.history)
        if direction:
            items = [m for m in items if m.direction == direction]
        items = items[-limit:]
        return [m.to_dict() for m in reversed(items)]


# ─── Singleton Factory ────────────────────────────────────────────────────────

_manager: GatewayManager | None = None


def get_gateway_manager() -> GatewayManager:
    """Return the process-wide :class:`GatewayManager`, built from settings.

    Gateways are always registered (even without credentials) so the API can
    report their configuration state; unconfigured gateways fail loudly on use.
    """
    global _manager
    if _manager is not None:
        return _manager

    from backend.app.settings import get_settings

    settings = get_settings()
    manager = GatewayManager()
    manager.register(
        TelegramGateway(
            bot_token=getattr(settings, "telegram_bot_token", "") or "",
            webhook_secret=getattr(settings, "telegram_webhook_secret", "") or "",
            webhook_url=getattr(settings, "telegram_webhook_url", "") or "",
        )
    )
    manager.register(
        DiscordGateway(
            bot_token=getattr(settings, "discord_bot_token", "") or "",
            public_key=getattr(settings, "discord_public_key", "") or "",
            application_id=getattr(settings, "discord_application_id", "") or "",
        )
    )
    manager.register(
        DingTalkGateway(
            app_key=getattr(settings, "dingtalk_app_key", "") or "",
            app_secret=getattr(settings, "dingtalk_app_secret", "") or "",
            webhook_url=getattr(settings, "dingtalk_webhook_url", "") or "",
            robot_code=getattr(settings, "dingtalk_robot_code", "") or "",
        )
    )
    manager.register(
        FeishuGateway(
            app_id=getattr(settings, "feishu_app_id", "") or "",
            app_secret=getattr(settings, "feishu_app_secret", "") or "",
            encrypt_key=getattr(settings, "feishu_encrypt_key", "") or "",
            base_url=getattr(settings, "feishu_base_url", "") or "",
        )
    )
    _manager = manager
    return manager


def reset_gateway_manager() -> None:
    """Reset the singleton (used by tests)."""
    global _manager
    _manager = None
