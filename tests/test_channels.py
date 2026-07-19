"""Tests for the Phase 5.6 multi-channel adapter framework.

Verifies registry routing, inbound parsing, and signature verification for
Discord / Telegram / DingTalk. Outbound send_text is not network-tested here
(it requires live platform tokens); the parse/verify logic is the security-
and correctness-critical part and is fully covered.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time

import pytest

from backend.app.core.channels import (
    ChannelConfig,
    ChannelMessage,
    ChannelRegistry,
    DiscordAdapter,
    TelegramAdapter,
    DingTalkAdapter,
    get_channel_registry,
)


class TestChannelRegistry:
    def test_register_and_get(self):
        reg = ChannelRegistry()
        d = DiscordAdapter(ChannelConfig(token="x"))
        reg.register(d)
        assert reg.get("discord") is d
        assert reg.get("nope") is None
        assert "discord" in reg.names()
        assert len(reg) == 1

    def test_module_registry_singleton(self):
        assert get_channel_registry() is get_channel_registry()


class TestTelegramAdapter:
    def test_parse_inbound_message(self):
        a = TelegramAdapter(ChannelConfig(token="t"))
        payload = {
            "message": {
                "text": "hello",
                "chat": {"id": 555},
                "from": {"id": 999},
            }
        }
        msg = a.parse_inbound(payload)
        assert isinstance(msg, ChannelMessage)
        assert msg.text == "hello"
        assert msg.conversation_id == "555"
        assert msg.sender_id == "999"
        assert msg.channel == "telegram"

    def test_parse_inbound_non_message_returns_none(self):
        a = TelegramAdapter()
        assert a.parse_inbound({"poll": {}}) is None

    def test_verify_signature_secret_token(self):
        a = TelegramAdapter(ChannelConfig(signing_secret="s3cret"))
        ok = a.verify_signature(
            b"{}", {"X-Telegram-Bot-Api-Secret-Token": "s3cret"}
        )
        assert ok is True
        assert a.verify_signature(b"{}", {"X-Telegram-Bot-Api-Secret-Token": "wrong"}) is False
        assert a.verify_signature(b"{}", {}) is False


class TestDingTalkAdapter:
    def test_verify_signature_roundtrip(self):
        secret = "ding-secret"
        a = DingTalkAdapter(ChannelConfig(signing_secret=secret))
        ts = str(round(time.time() * 1000))
        string_to_sign = f"{ts}\n{secret}"
        digest = hmac.new(secret.encode(), string_to_sign.encode(), hashlib.sha256).digest()
        sign = base64.b64encode(digest).decode()
        assert a.verify_signature(b"{}", {"timestamp": ts, "sign": sign}) is True
        assert a.verify_signature(b"{}", {"timestamp": ts, "sign": "bad"}) is False
        assert a.verify_signature(b"{}", {}) is False

    def test_parse_inbound(self):
        a = DingTalkAdapter()
        payload = {
            "text": {"content": "  do something  "},
            "senderId": "u1",
            "conversationId": "c1",
        }
        msg = a.parse_inbound(payload)
        assert msg is not None
        assert msg.text == "do something"
        assert msg.sender_id == "u1"
        assert msg.conversation_id == "c1"

    def test_parse_inbound_empty(self):
        a = DingTalkAdapter()
        assert a.parse_inbound({"text": {}}) is None


class TestDiscordAdapter:
    def test_ping_returns_none(self):
        a = DiscordAdapter(ChannelConfig(token="b"))
        assert a.parse_inbound({"type": 1}) is None

    def test_parse_message(self):
        a = DiscordAdapter(ChannelConfig(token="b"))
        payload = {
            "content": "hi bot",
            "author": {"id": "42"},
            "channel_id": "chan9",
        }
        msg = a.parse_inbound(payload)
        assert msg is not None
        assert msg.text == "hi bot"
        assert msg.sender_id == "42"
        assert msg.conversation_id == "chan9"

    def test_verify_signature_no_key_denies(self):
        a = DiscordAdapter(ChannelConfig(token="b"))  # no signing_secret
        assert a.verify_signature(b"{}", {}) is False
