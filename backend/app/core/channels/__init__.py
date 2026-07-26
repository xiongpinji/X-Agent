"""Multi-channel adapter framework (Phase 5.6).

Unified ChannelAdapter abstraction over chat platforms. Concrete adapters:
Discord, Telegram, DingTalk (Feishu/Slack remain in their existing modules
and can be wrapped later). Use get_channel_registry() to route by channel id.
"""

from backend.app.core.channels.base import (
    ChannelAdapter,
    ChannelConfig,
    ChannelDispatchResult,
    ChannelMessage,
    ChannelRegistry,
    get_channel_registry,
)
from backend.app.core.channels.dingtalk_adapter import DingTalkAdapter
from backend.app.core.channels.discord_adapter import DiscordAdapter
from backend.app.core.channels.router import (
    ChannelRouter,
    ChannelRouterError,
    ChannelSignatureError,
    default_channel_dispatch,
)
from backend.app.core.channels.slack_adapter import SlackAdapter
from backend.app.core.channels.telegram_adapter import TelegramAdapter

__all__ = [
    "ChannelAdapter",
    "ChannelConfig",
    "ChannelDispatchResult",
    "ChannelMessage",
    "ChannelRegistry",
    "ChannelRouter",
    "ChannelRouterError",
    "ChannelSignatureError",
    "DingTalkAdapter",
    "DiscordAdapter",
    "SlackAdapter",
    "TelegramAdapter",
    "default_channel_dispatch",
    "get_channel_registry",
]
