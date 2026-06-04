"""Unified multi-channel adapter framework (Phase 5.6).

Provides a single ChannelAdapter abstraction so X-Agent can deliver agent
output and receive commands across many chat platforms (Feishu, Slack,
Discord, Telegram, DingTalk, ...) without each call site knowing the
platform specifics.

Design:
- ChannelAdapter: abstract base. Concrete adapters implement send_text() and
  verify_signature()/parse_inbound() for their platform's webhook format.
- ChannelMessage: normalized inbound message (channel, sender, text, raw).
- ChannelRegistry: name -> adapter lookup so the API/dispatcher can route by
  channel id without hard-coding platforms.

Adapters use httpx (already a dependency) for outbound calls. Inbound webhook
signature verification is per-platform; each adapter documents its scheme.
Network/credentials are read from config passed at construction — never
hard-coded.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ChannelMessage:
    """A normalized inbound message from any channel."""

    channel: str               # adapter name, e.g. "discord"
    sender_id: str             # platform user/chat id
    text: str                  # message body
    conversation_id: str = ""  # thread/channel/chat id to reply into
    raw: dict[str, Any] = field(default_factory=dict)  # original payload


@dataclass
class ChannelConfig:
    """Generic channel configuration. Adapters read what they need."""

    token: str = ""                 # bot token / webhook token
    signing_secret: str = ""        # inbound signature verification secret
    base_url: str = ""              # API base (platform default if empty)
    extra: dict[str, Any] = field(default_factory=dict)


class ChannelAdapter(abc.ABC):
    """Abstract base for a chat-platform adapter."""

    #: short stable identifier, e.g. "discord"
    name: str = "base"

    def __init__(self, config: Optional[ChannelConfig] = None):
        self.config = config or ChannelConfig()

    @abc.abstractmethod
    async def send_text(self, conversation_id: str, text: str) -> dict[str, Any]:
        """Send a plain-text message to a conversation/channel."""
        raise NotImplementedError

    @abc.abstractmethod
    def verify_signature(self, body: bytes, headers: dict[str, str]) -> bool:
        """Verify an inbound webhook's authenticity. Default-deny on no secret."""
        raise NotImplementedError

    @abc.abstractmethod
    def parse_inbound(self, payload: dict[str, Any]) -> Optional[ChannelMessage]:
        """Parse a verified webhook payload into a ChannelMessage, or None if
        it is not an actionable message event."""
        raise NotImplementedError


class ChannelRegistry:
    """Name -> ChannelAdapter registry for routing."""

    def __init__(self) -> None:
        self._adapters: dict[str, ChannelAdapter] = {}

    def register(self, adapter: ChannelAdapter) -> None:
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> Optional[ChannelAdapter]:
        return self._adapters.get(name)

    def names(self) -> list[str]:
        return sorted(self._adapters.keys())

    def __len__(self) -> int:
        return len(self._adapters)


# Process-wide default registry (populated by app startup / config).
_registry = ChannelRegistry()


def get_channel_registry() -> ChannelRegistry:
    return _registry
