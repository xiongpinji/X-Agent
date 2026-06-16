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
