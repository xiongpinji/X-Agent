"""Base channel adapter interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class ChannelMessage:
    """Incoming message from a channel."""
    id: str = field(default_factory=lambda: str(uuid4()))
    channel: str = ""
    sender_id: str = ""
    sender_name: str = ""
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    reply_to: str | None = None


@dataclass
class ChannelResponse:
    """Outgoing response to a channel."""
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    reply_to: str | None = None


class ChannelAdapter(ABC):
    """Base class for all channel adapters."""

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Unique channel identifier."""
        ...

    @abstractmethod
    async def send_message(self, chat_id: str, response: ChannelResponse) -> bool:
        """Send a message to the channel."""
        ...

    @abstractmethod
    async def handle_webhook(self, payload: dict[str, Any]) -> ChannelMessage | None:
        """Parse incoming webhook payload into a ChannelMessage."""
        ...

    async def start(self) -> None:
        """Start the channel (e.g., polling or webhook listener)."""
        pass

    async def stop(self) -> None:
        """Stop the channel."""
        pass
