"""Multi-Platform Messaging Gateway

Provides unified messaging across multiple platforms, comparable to
Hermes Agent's 22-platform gateway. Currently supports:
- Discord
- WhatsApp (via Baileys bridge)
- Telegram (existing)
- Slack (existing)
- Feishu/Lark (existing)

Architecture:
- BaseChannel: Abstract interface for all platforms
- Platform-specific adapters implement the interface
- Gateway routes messages to/from the Agent core
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class PlatformType(StrEnum):
    """Supported messaging platforms."""

    DISCORD = "discord"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    SLACK = "slack"
    FEISHU = "feishu"
    CLI = "cli"
    WEB = "web"
    # Future platforms (Hermes supports 22)
    SIGNAL = "signal"
    LINE = "line"
    SIMPLEX = "simplex"
    EMAIL = "email"
    SMS = "sms"


@dataclass
class IncomingMessage:
    """Message received from a platform."""

    id: str = field(default_factory=lambda: str(uuid4()))
    platform: PlatformType = PlatformType.CLI
    channel_id: str = ""  # Platform-specific channel/chat ID
    user_id: str = ""
    username: str = ""
    content: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    # Rich content
    attachments: list[dict[str, Any]] = field(default_factory=list)
    reply_to: str | None = None
    # Voice/audio
    is_voice: bool = False
    voice_transcript: str | None = None


@dataclass
class OutgoingMessage:
    """Message to send to a platform."""

    content: str
    platform: PlatformType
    channel_id: str
    reply_to: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    # Formatting
    markdown: bool = True
    embed: dict[str, Any] | None = None
    buttons: list[dict[str, str]] | None = None


@dataclass
class ChannelConfig:
    """Configuration for a messaging channel."""

    platform: PlatformType
    enabled: bool = False
    # Auth credentials (platform-specific)
    token: str = ""
    api_key: str = ""
    api_secret: str = ""
    # Behavior
    auto_reply: bool = True
    allowed_users: list[str] = field(default_factory=list)
    blocked_users: list[str] = field(default_factory=list)
    # Rate limiting
    rate_limit_per_minute: int = 60
    # Extra config
    extra: dict[str, Any] = field(default_factory=dict)


class BaseChannel(ABC):
    """Abstract base class for messaging platform adapters."""

    def __init__(self, config: ChannelConfig):
        self.config = config
        self._running = False
        self._message_handler: Callable[[IncomingMessage], Coroutine] | None = None

    @property
    @abstractmethod
    def platform(self) -> PlatformType:
        """Return the platform type."""
        ...

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the platform. Returns True if successful."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the platform."""
        ...

    @abstractmethod
    async def send_message(self, message: OutgoingMessage) -> bool:
        """Send a message to the platform."""
        ...

    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if connected to the platform."""
        ...

    def on_message(self, handler: Callable[[IncomingMessage], Coroutine]) -> None:
        """Register message handler."""
        self._message_handler = handler

    async def _dispatch_message(self, message: IncomingMessage) -> None:
        """Dispatch incoming message to handler."""
        if self._message_handler:
            try:
                await self._message_handler(message)
            except Exception as e:
                logger.error(f"Message handler error: {e}")


class DiscordChannel(BaseChannel):
    """Discord messaging adapter.

    Requires: discord.py library
    Install: pip install discord.py
    """

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self._client = None
        self._ready_event = asyncio.Event()

    @property
    def platform(self) -> PlatformType:
        return PlatformType.DISCORD

    async def connect(self) -> bool:
        """Connect to Discord using discord.py."""
        try:
            import discord

            intents = discord.Intents.default()
            intents.message_content = True
            intents.dm_messages = True

            self._client = discord.Client(intents=intents)

            @self._client.event
            async def on_ready():
                logger.info(f"Discord connected as {self._client.user}")
                self._running = True
                self._ready_event.set()

            @self._client.event
            async def on_message(message):
                if message.author.bot:
                    return

                # Check allowed users
                user_id = str(message.author.id)
                if self.config.allowed_users and user_id not in self.config.allowed_users:
                    return
                if user_id in self.config.blocked_users:
                    return

                incoming = IncomingMessage(
                    platform=PlatformType.DISCORD,
                    channel_id=str(message.channel.id),
                    user_id=user_id,
                    username=str(message.author),
                    content=message.content,
                    metadata={
                        "guild_id": str(message.guild.id) if message.guild else None,
                        "message_id": str(message.id),
                    },
                    attachments=[
                        {"url": a.url, "filename": a.filename, "size": a.size}
                        for a in message.attachments
                    ],
                )
                await self._dispatch_message(incoming)

            # Run client in background
            asyncio.create_task(self._client.start(self.config.token))

            # Wait for ready
            await asyncio.wait_for(self._ready_event.wait(), timeout=30)
            return True

        except ImportError:
            logger.error("discord.py not installed. Run: pip install discord.py")
            return False
        except Exception as e:
            logger.error(f"Discord connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()
            self._running = False

    async def send_message(self, message: OutgoingMessage) -> bool:
        if not self._client or not self._running:
            return False

        try:
            channel = self._client.get_channel(int(message.channel_id))
            if channel:
                await channel.send(message.content)
                return True
        except Exception as e:
            logger.error(f"Discord send failed: {e}")
        return False

    async def is_connected(self) -> bool:
        return self._running and self._client is not None


class WhatsAppChannel(BaseChannel):
    """WhatsApp messaging adapter via Baileys bridge.

    Requires: Node.js Baileys bridge running separately
    This adapter communicates with the bridge via WebSocket.
    """

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self._ws = None
        self._bridge_url = config.extra.get("bridge_url", "ws://localhost:3001")

    @property
    def platform(self) -> PlatformType:
        return PlatformType.WHATSAPP

    async def connect(self) -> bool:
        """Connect to WhatsApp via Baileys bridge."""
        try:
            import websockets

            self._ws = await websockets.connect(self._bridge_url)
            self._running = True

            # Start message listener
            asyncio.create_task(self._listen_messages())

            logger.info(f"WhatsApp bridge connected at {self._bridge_url}")
            return True

        except ImportError:
            logger.error("websockets not installed. Run: pip install websockets")
            return False
        except Exception as e:
            logger.error(f"WhatsApp bridge connection failed: {e}")
            return False

    async def _listen_messages(self):
        """Listen for incoming WhatsApp messages from bridge."""
        import json

        while self._running and self._ws:
            try:
                data = await self._ws.recv()
                msg = json.loads(data)

                if msg.get("type") == "message":
                    incoming = IncomingMessage(
                        platform=PlatformType.WHATSAPP,
                        channel_id=msg.get("chat_id", ""),
                        user_id=msg.get("sender_id", ""),
                        username=msg.get("sender_name", ""),
                        content=msg.get("text", ""),
                        is_voice=msg.get("is_voice", False),
                        voice_transcript=msg.get("transcript"),
                        metadata=msg.get("metadata", {}),
                    )
                    await self._dispatch_message(incoming)

            except Exception as e:
                if self._running:
                    logger.error(f"WhatsApp listener error: {e}")
                    await asyncio.sleep(1)

    async def disconnect(self) -> None:
        self._running = False
        if self._ws:
            await self._ws.close()

    async def send_message(self, message: OutgoingMessage) -> bool:
        if not self._ws:
            return False

        import json

        try:
            await self._ws.send(json.dumps({
                "type": "send",
                "chat_id": message.channel_id,
                "text": message.content,
            }))
            return True
        except Exception as e:
            logger.error(f"WhatsApp send failed: {e}")
            return False

    async def is_connected(self) -> bool:
        return self._running and self._ws is not None


class MessagingGateway:
    """Unified messaging gateway across all platforms.

    Routes messages between platforms and the Agent core,
    providing a single interface for multi-platform communication.
    """

    def __init__(self):
        self._channels: dict[PlatformType, BaseChannel] = {}
        self._message_queue: asyncio.Queue[IncomingMessage] = asyncio.Queue()
        self._running = False

    def register_channel(self, channel: BaseChannel) -> None:
        """Register a platform channel."""
        self._channels[channel.platform] = channel
        channel.on_message(self._handle_incoming)
        logger.info(f"Registered channel: {channel.platform.value}")

    async def _handle_incoming(self, message: IncomingMessage) -> None:
        """Handle incoming message from any platform."""
        await self._message_queue.put(message)

    async def start(self) -> None:
        """Start all enabled channels."""
        self._running = True
        for platform, channel in self._channels.items():
            if channel.config.enabled:
                success = await channel.connect()
                if success:
                    logger.info(f"Started channel: {platform.value}")
                else:
                    logger.warning(f"Failed to start channel: {platform.value}")

    async def stop(self) -> None:
        """Stop all channels."""
        self._running = False
        for channel in self._channels.values():
            await channel.disconnect()

    async def send(self, message: OutgoingMessage) -> bool:
        """Send message to appropriate platform."""
        channel = self._channels.get(message.platform)
        if channel:
            return await channel.send_message(message)
        logger.warning(f"No channel for platform: {message.platform}")
        return False

    async def broadcast(self, content: str, platforms: list[PlatformType] | None = None) -> dict[str, bool]:
        """Broadcast message to multiple platforms."""
        results = {}
        targets = platforms or list(self._channels.keys())
        for platform in targets:
            channel = self._channels.get(platform)
            if channel and await channel.is_connected():
                # Would need channel_id for each platform
                results[platform.value] = False  # Placeholder
        return results

    def get_status(self) -> dict[str, Any]:
        """Get gateway status."""
        return {
            "running": self._running,
            "channels": {
                p.value: {
                    "enabled": c.config.enabled,
                    "connected": asyncio.get_event_loop().run_until_complete(c.is_connected())
                    if self._running else False,
                }
                for p, c in self._channels.items()
            },
            "queue_size": self._message_queue.qsize(),
        }

    @property
    def message_queue(self) -> asyncio.Queue[IncomingMessage]:
        """Get the incoming message queue."""
        return self._message_queue


# Global gateway instance
_gateway: MessagingGateway | None = None


def get_messaging_gateway() -> MessagingGateway:
    """Get or create the global messaging gateway."""
    global _gateway
    if _gateway is None:
        _gateway = MessagingGateway()
    return _gateway
