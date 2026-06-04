"""Multi-channel adapter framework (Phase 5.6).

Unified ChannelAdapter abstraction over chat platforms. Concrete adapters:
Discord, Telegram, DingTalk (Feishu/Slack remain in their existing modules
and can be wrapped later). Use get_channel_registry() to route by channel id.
"""

from backend.app.core.channels.base import (
    ChannelAdapter,
    ChannelConfig,
    ChannelMessage,
    ChannelRegistry,
    get_channel_registry,
)
from backend.app.core.channels.discord_adapter import DiscordAdapter
from backend.app.core.channels.telegram_adapter import TelegramAdapter
from backend.app.core.channels.dingtalk_adapter import DingTalkAdapter

__all__ = [
    "ChannelAdapter",
    "ChannelConfig",
    "ChannelMessage",
    "ChannelRegistry",
    "get_channel_registry",
    "DiscordAdapter",
    "TelegramAdapter",
    "DingTalkAdapter",
]
