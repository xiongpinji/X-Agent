from __future__ import annotations

import pytest

from backend.app.core.channels import (
    ChannelConfig,
    ChannelRegistry,
    TelegramAdapter,
)
from backend.app.core.channels.router import ChannelRouter, ChannelSignatureError
from backend.app.core.channels.base import ChannelMessage


def _registry(secret: str = "secret") -> ChannelRegistry:
    registry = ChannelRegistry()
    registry.register(TelegramAdapter(ChannelConfig(token="token", signing_secret=secret)))
    return registry


def _telegram_payload(text: str = "run status") -> dict[str, object]:
    return {
        "message": {
            "message_id": 42,
            "text": text,
            "chat": {"id": 1001},
            "from": {"id": 2002},
        }
    }


@pytest.mark.asyncio
async def test_channel_router_dispatches_and_sends_mocked_reply() -> None:
    sent: list[tuple[str, str]] = []

    async def dispatch_message(message: ChannelMessage) -> dict[str, object]:
        return {
            "run_id": "run-telegram-1",
            "status": "accepted",
            "reply_text": f"reply: {message.text}",
            "dispatch": {"task": message.text},
        }

    async def reply_sender(message: ChannelMessage, text: str) -> dict[str, object]:
        sent.append((message.conversation_id, text))
        return {"ok": True, "message_id": "out-1"}

    router = ChannelRouter(
        _registry(),
        dispatch_callable=dispatch_message,
        reply_sender=reply_sender,
    )

    result = await router.process_inbound(
        channel="telegram",
        body=b"{}",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
        payload=_telegram_payload(),
    )

    assert result.channel == "telegram"
    assert result.conversation_id == "1001"
    assert result.message_id == "42"
    assert result.run_id == "run-telegram-1"
    assert result.status == "accepted"
    assert result.reply_sent is True
    assert result.reply_text == "reply: run status"
    assert sent == [("1001", "reply: run status")]


@pytest.mark.asyncio
async def test_channel_router_rejects_invalid_signature() -> None:
    router = ChannelRouter(_registry())

    with pytest.raises(ChannelSignatureError):
        await router.process_inbound(
            channel="telegram",
            body=b"{}",
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
            payload=_telegram_payload(),
        )


@pytest.mark.asyncio
async def test_channel_router_ignores_unsupported_payload() -> None:
    router = ChannelRouter(_registry())

    result = await router.process_inbound(
        channel="telegram",
        body=b"{}",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
        payload={"poll": {"id": "p1"}},
    )

    assert result.status == "ignored"
    assert result.reply_sent is False
    assert result.run_id == ""
