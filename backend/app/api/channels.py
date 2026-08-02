from __future__ import annotations

import json
import os
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from backend.app.api.errors import api_error
from backend.app.core.channels import (
    ChannelConfig,
    ChannelRegistry,
    ChannelRouter,
    ChannelRouterError,
    ChannelSignatureError,
    DingTalkAdapter,
    DiscordAdapter,
    SlackAdapter,
    TelegramAdapter,
)
from backend.app.core.contracts import ErrorCode

router = APIRouter(prefix="/api/v1/channels", tags=["channels"])


def get_channel_router() -> ChannelRouter:
    registry = ChannelRegistry()
    registry.register(
        TelegramAdapter(
            ChannelConfig(
                token=os.getenv("XAGENT_TELEGRAM_BOT_TOKEN", ""),
                signing_secret=os.getenv("XAGENT_TELEGRAM_WEBHOOK_SECRET", "")
                or os.getenv("XAGENT_TELEGRAM_SIGNING_SECRET", ""),
                base_url=os.getenv("XAGENT_TELEGRAM_BASE_URL", ""),
            )
        )
    )
    registry.register(
        SlackAdapter(
            ChannelConfig(
                token=os.getenv("XAGENT_SLACK_BOT_TOKEN", ""),
                signing_secret=os.getenv("XAGENT_SLACK_SIGNING_SECRET", ""),
                base_url=os.getenv("XAGENT_SLACK_BASE_URL", ""),
            )
        )
    )
    registry.register(
        DiscordAdapter(
            ChannelConfig(
                token=os.getenv("XAGENT_DISCORD_BOT_TOKEN", ""),
                signing_secret=os.getenv("XAGENT_DISCORD_PUBLIC_KEY", ""),
                base_url=os.getenv("XAGENT_DISCORD_BASE_URL", ""),
            )
        )
    )
    registry.register(
        DingTalkAdapter(
            ChannelConfig(
                token=os.getenv("XAGENT_DINGTALK_TOKEN", ""),
                signing_secret=os.getenv("XAGENT_DINGTALK_SECRET", ""),
                base_url=os.getenv("XAGENT_DINGTALK_WEBHOOK_URL", ""),
            )
        )
    )
    return ChannelRouter(registry)


ChannelRouterDependency = Annotated[ChannelRouter, Depends(get_channel_router)]


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request, channel_router: ChannelRouterDependency) -> dict[str, object]:
    body = await request.body()
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "Invalid Telegram webhook JSON.")

    try:
        result = await channel_router.process_inbound(
            channel="telegram",
            body=body,
            headers=dict(request.headers),
            payload=payload,
        )
    except ChannelSignatureError as exc:
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, str(exc))
    except ChannelRouterError as exc:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, str(exc))

    return {
        "channel": result.channel,
        "conversation_id": result.conversation_id,
        "message_id": result.message_id,
        "run_id": result.run_id,
        "status": result.status,
        "reply_sent": result.reply_sent,
        "reply_text": result.reply_text,
        "sender_id": result.sender_id,
        "dispatch": result.dispatch,
        "outbound": result.outbound,
    }


def _slack_adapter(channel_router: ChannelRouter) -> SlackAdapter:
    adapter = channel_router._registry.get("slack")  # noqa: SLF001 - registry lookup
    if adapter is None or not isinstance(adapter, SlackAdapter) or not adapter.configured:
        raise api_error(
            503,
            ErrorCode.INTERNAL_ERROR,
            "Slack channel not configured: set XAGENT_SLACK_BOT_TOKEN and "
            "XAGENT_SLACK_SIGNING_SECRET.",
        )
    return adapter


@router.post("/slack/events")
async def slack_events(request: Request, channel_router: ChannelRouterDependency) -> dict[str, object]:
    """Slack Events API endpoint.

    Handles url_verification challenges (after signature verification) and
    event_callback messages. Unconfigured credentials fail loudly with 503.
    """
    body = await request.body()
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "Invalid Slack webhook JSON.")

    adapter = _slack_adapter(channel_router)
    headers = dict(request.headers)
    if not adapter.verify_signature(body, headers):
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Invalid slack webhook signature")

    # URL verification handshake: echo the challenge back to Slack.
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge", "")}

    try:
        result = await channel_router.process_inbound(
            channel="slack",
            body=body,
            headers=headers,
            payload=payload,
        )
    except ChannelSignatureError as exc:
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, str(exc))
    except ChannelRouterError as exc:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, str(exc))

    return {
        "channel": result.channel,
        "conversation_id": result.conversation_id,
        "message_id": result.message_id,
        "run_id": result.run_id,
        "status": result.status,
        "reply_sent": result.reply_sent,
        "reply_text": result.reply_text,
        "sender_id": result.sender_id,
        "dispatch": result.dispatch,
        "outbound": result.outbound,
    }


# ─── Discord Interaction Webhook ─────────────────────────────────────────────


def _discord_adapter(channel_router: ChannelRouter) -> DiscordAdapter:
    adapter = channel_router._registry.get("discord")  # noqa: SLF001
    if adapter is None or not isinstance(adapter, DiscordAdapter):
        raise api_error(
            503,
            ErrorCode.INTERNAL_ERROR,
            "Discord channel not configured: set XAGENT_DISCORD_BOT_TOKEN and "
            "XAGENT_DISCORD_PUBLIC_KEY.",
        )
    return adapter


@router.post("/discord/interactions")
async def discord_interactions(request: Request, channel_router: ChannelRouterDependency) -> dict[str, object]:
    """Discord Interactions endpoint.

    Handles PING (type=1) and APPLICATION_COMMAND / MESSAGE_COMPONENT interactions.
    Verified via Ed25519 signature (X-Signature-Ed25519 + X-Signature-Timestamp).
    """
    body = await request.body()
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "Invalid Discord webhook JSON.")

    adapter = _discord_adapter(channel_router)
    headers = dict(request.headers)
    if not adapter.verify_signature(body, headers):
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Invalid Discord interaction signature")

    # Discord PING handshake
    if payload.get("type") == 1:
        return {"type": 1}  # PONG

    try:
        result = await channel_router.process_inbound(
            channel="discord",
            body=body,
            headers=headers,
            payload=payload,
        )
    except ChannelSignatureError as exc:
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, str(exc))
    except ChannelRouterError as exc:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, str(exc))

    return {
        "channel": result.channel,
        "conversation_id": result.conversation_id,
        "message_id": result.message_id,
        "run_id": result.run_id,
        "status": result.status,
        "reply_sent": result.reply_sent,
        "reply_text": result.reply_text,
        "sender_id": result.sender_id,
        "dispatch": result.dispatch,
        "outbound": result.outbound,
    }


# ─── DingTalk Robot Webhook ──────────────────────────────────────────────────


@router.post("/dingtalk/webhook")
async def dingtalk_webhook(request: Request, channel_router: ChannelRouterDependency) -> dict[str, object]:
    """DingTalk robot callback endpoint."""
    body = await request.body()
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "Invalid DingTalk webhook JSON.")

    try:
        result = await channel_router.process_inbound(
            channel="dingtalk",
            body=body,
            headers=dict(request.headers),
            payload=payload,
        )
    except ChannelSignatureError as exc:
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, str(exc))
    except ChannelRouterError as exc:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, str(exc))

    return {
        "channel": result.channel,
        "conversation_id": result.conversation_id,
        "message_id": result.message_id,
        "run_id": result.run_id,
        "status": result.status,
        "reply_sent": result.reply_sent,
        "reply_text": result.reply_text,
        "sender_id": result.sender_id,
        "dispatch": result.dispatch,
        "outbound": result.outbound,
    }
