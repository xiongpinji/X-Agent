from __future__ import annotations

import json
import logging
import os
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

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
from backend.app.core.messaging_gateway import (
    BaseChannel,
    ChannelConfig as GatewayChannelConfig,
    DiscordChannel,
    IncomingMessage,
    MessagingGateway,
    OutgoingMessage,
    PlatformType,
    WhatsAppChannel,
    get_messaging_gateway,
)

logger = logging.getLogger(__name__)

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

    response: dict[str, object] = {
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
    gateway_forward = await _forward_webhook_to_gateway_agent(channel_router, "telegram", payload)
    if gateway_forward is not None:
        response["gateway"] = gateway_forward
    return response


def _slack_adapter(channel_router: ChannelRouter) -> SlackAdapter:
    adapter = channel_router._registry.get("slack")
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
    adapter = channel_router._registry.get("discord")
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

    response: dict[str, object] = {
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
    gateway_forward = await _forward_webhook_to_gateway_agent(channel_router, "discord", payload)
    if gateway_forward is not None:
        response["gateway"] = gateway_forward
    return response


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


# ─── Messaging Gateway (core/messaging_gateway.py 接线) ──────────────────────
#
# MessagingGateway 是进程内多平台网关（Discord/WhatsApp 常驻通道 + 统一
# Incoming/Outgoing 消息模型）。本节把它接到 channels API：
# - 管理端点：register/status/send/broadcast/start/stop（鉴权沿用本 router
#   惯例：依赖全局 require_api_key_header 中间件，webhook 之外的路径不豁免）。
# - Agent 回路：gateway 收到 IncomingMessage 后经 set_gateway_agent_handler
#   注入的 relay 调用 Agent（默认 get_agent().run(RunContext(), content)），
#   回复经 gateway.send 送回来源平台。
# - 进程内安全：gateway 的一切连接行为只在显式 register（connect=true）或
#   显式 POST /gateway/start 后发生，不随 app startup 自动启动。
# - Telegram/Discord webhook 消息在对应平台已注册进 gateway 时也走同一
#   agent 回路（_forward_webhook_to_gateway_agent）。


class GatewayDependencyMissingError(Exception):
    """Optional platform SDK (discord.py / websockets) is not installed."""


class GatewayChannelUnsupportedError(Exception):
    """Platform has no MessagingGateway channel implementation."""


GatewayAgentHandler = Callable[[IncomingMessage], Awaitable[str]]

_gateway_agent_handler: GatewayAgentHandler | None = None


def set_gateway_agent_handler(handler: GatewayAgentHandler | None) -> None:
    """注入/清除 gateway 入站消息的 agent 回路 handler。

    handler 签名: (IncomingMessage) -> str（返回回复文本；None 视为清除，
    回落到默认 handler）。默认 handler 调用 backend.app.dependencies.get_agent()
    .run(RunContext(), message.content) 并返回 answer。
    """
    global _gateway_agent_handler
    _gateway_agent_handler = handler


async def _default_gateway_agent_handler(message: IncomingMessage) -> str:
    """默认 agent 回路：IncomingMessage.content -> AgentLoop.run -> answer。"""
    try:
        from backend.app.core.contracts import RunContext

        from backend.app.dependencies import get_agent

        response = await get_agent().run(RunContext(), message.content)
        answer = getattr(response, "answer", "") or ""
        return answer.strip()
    except Exception as exc:
        logger.error("Gateway default agent handler failed: %s", exc, exc_info=True)
        return f"[X-Agent gateway] 处理消息失败: {exc}"


async def _gateway_agent_relay(message: IncomingMessage) -> str:
    """gateway._handle_incoming 的统一入口：自定义 handler 或默认 agent 回路。"""
    handler = _gateway_agent_handler or _default_gateway_agent_handler
    try:
        return await handler(message)
    except Exception as exc:
        logger.error("Gateway agent relay failed: %s", exc, exc_info=True)
        return f"[X-Agent gateway] 处理消息失败: {exc}"


def _build_gateway_channel(
    platform: PlatformType, config: GatewayChannelConfig
) -> BaseChannel:
    """构造平台 channel，可选依赖缺失时抛可诊断错误（fail-closed）。

    测试可 monkeypatch 本函数注入 mock channel。
    """
    if platform is PlatformType.DISCORD:
        try:
            import discord  # noqa: F401
        except ImportError as exc:
            raise GatewayDependencyMissingError(
                "discord.py is not installed. Install with: pip install discord.py"
            ) from exc
        return DiscordChannel(config)
    if platform is PlatformType.WHATSAPP:
        try:
            import websockets  # noqa: F401
        except ImportError as exc:
            raise GatewayDependencyMissingError(
                "websockets is not installed (Baileys bridge transport). "
                "Install with: pip install websockets"
            ) from exc
        return WhatsAppChannel(config)
    raise GatewayChannelUnsupportedError(
        f"platform '{platform.value}' has no MessagingGateway channel implementation; "
        "telegram/slack/dingtalk use the webhook routes under /api/v1/channels/"
    )


def _parse_gateway_platform(raw: str) -> PlatformType:
    try:
        return PlatformType(raw)
    except ValueError:
        supported = ", ".join(p.value for p in PlatformType)
        raise api_error(
            400,
            ErrorCode.VALIDATION_ERROR,
            f"Unknown platform '{raw}'. Known platforms: {supported}",
        )


class GatewayRegisterRequest(BaseModel):
    platform: str
    token: str = ""
    api_key: str = ""
    api_secret: str = ""
    enabled: bool = True
    connect: bool = True
    auto_reply: bool = True
    allowed_users: list[str] = Field(default_factory=list)
    blocked_users: list[str] = Field(default_factory=list)
    rate_limit_per_minute: int = 60
    extra: dict[str, Any] = Field(default_factory=dict)


class GatewaySendRequest(BaseModel):
    platform: str
    channel_id: str
    content: str
    reply_to: str | None = None
    markdown: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class GatewayBroadcastRequest(BaseModel):
    content: str
    platforms: list[str] | None = None
    channel_ids: dict[str, str] = Field(default_factory=dict)


@router.post("/gateway/register")
async def gateway_register(request: GatewayRegisterRequest) -> dict[str, object]:
    """注册并（默认）连接一个平台 channel。

    fail-closed：可选依赖缺失 -> 503（含安装指引）；connect 失败 -> 502，
    且不留半注册状态（先连接成功再注册进 gateway）。
    """
    gateway = get_messaging_gateway()
    platform = _parse_gateway_platform(request.platform)

    try:
        channel = _build_gateway_channel(
            platform,
            GatewayChannelConfig(
                platform=platform,
                enabled=request.enabled,
                token=request.token,
                api_key=request.api_key,
                api_secret=request.api_secret,
                auto_reply=request.auto_reply,
                allowed_users=request.allowed_users,
                blocked_users=request.blocked_users,
                rate_limit_per_minute=request.rate_limit_per_minute,
                extra=request.extra,
            ),
        )
    except GatewayDependencyMissingError as exc:
        raise api_error(503, ErrorCode.INTERNAL_ERROR, str(exc))
    except GatewayChannelUnsupportedError as exc:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, str(exc))

    if not request.connect:
        gateway.register_channel(channel)
        return {
            "platform": platform.value,
            "registered": True,
            "connected": False,
            "connect_requested": False,
        }

    connected = False
    failure = ""
    try:
        connected = await channel.connect()
    except Exception as exc:
        failure = str(exc)
    if not connected:
        try:
            await channel.disconnect()
        except Exception:
            pass
        raise api_error(
            502,
            ErrorCode.INTERNAL_ERROR,
            f"Failed to connect {platform.value} channel"
            + (f": {failure}" if failure else "; see server logs for details"),
        )

    gateway.register_channel(channel)
    return {
        "platform": platform.value,
        "registered": True,
        "connected": connected,
        "connect_requested": True,
    }


@router.get("/gateway/status")
async def gateway_status() -> dict[str, object]:
    """gateway 运行状态（running/channels/queue_size + agent 回路模式）。"""
    gateway = get_messaging_gateway()
    status = await gateway.get_status_async()
    return dict(status, agent_handler="custom" if _gateway_agent_handler else "default")


@router.post("/gateway/send")
async def gateway_send(request: GatewaySendRequest) -> dict[str, object]:
    """经 gateway 向指定平台的 channel_id 发送一条消息。"""
    gateway = get_messaging_gateway()
    platform = _parse_gateway_platform(request.platform)
    if not gateway.has_channel(platform):
        raise api_error(
            404,
            ErrorCode.RESOURCE_NOT_FOUND,
            f"No gateway channel registered for platform '{request.platform}'. "
            "POST /api/v1/channels/gateway/register first.",
        )
    sent = await gateway.send(
        OutgoingMessage(
            content=request.content,
            platform=platform,
            channel_id=request.channel_id,
            reply_to=request.reply_to,
            markdown=request.markdown,
            metadata=request.metadata,
        )
    )
    return {"platform": platform.value, "channel_id": request.channel_id, "sent": sent}


@router.post("/gateway/broadcast")
async def gateway_broadcast(request: GatewayBroadcastRequest) -> dict[str, object]:
    """向多平台广播：platforms 省略时取全部已注册平台，channel_ids 提供
    每个平台的 目标 channel_id。"""
    gateway = get_messaging_gateway()
    if request.platforms is None:
        platforms = list(gateway._channels.keys()) if gateway._channels else []
        if not platforms:
            raise api_error(
                400,
                ErrorCode.VALIDATION_ERROR,
                "No gateway channels registered to broadcast to.",
            )
    else:
        platforms = [_parse_gateway_platform(p) for p in request.platforms]

    targets: dict[PlatformType, str] = {
        platform: request.channel_ids.get(platform.value, "")
        for platform in platforms
    }
    results = await gateway.broadcast_to_targets(request.content, targets)
    return {
        "results": results,
        "delivered": sum(1 for ok in results.values() if ok),
        "total": len(results),
    }


@router.post("/gateway/start")
async def gateway_start() -> dict[str, object]:
    """显式启动 gateway（幂等；不随 app startup 自动调用）。"""
    gateway = get_messaging_gateway()
    status = await gateway.get_status_async()
    if not status["channels"]:
        raise api_error(
            400,
            ErrorCode.VALIDATION_ERROR,
            "No gateway channels registered. POST /api/v1/channels/gateway/register first.",
        )
    if gateway.running:
        return {
            "started": False,
            "already_running": True,
            "status": dict(status, agent_handler="custom" if _gateway_agent_handler else "default"),
        }
    await gateway.start()
    return {
        "started": True,
        "already_running": False,
        "status": dict(
            await gateway.get_status_async(),
            agent_handler="custom" if _gateway_agent_handler else "default",
        ),
    }


@router.post("/gateway/stop")
async def gateway_stop() -> dict[str, object]:
    """停止 gateway 全部 channel（幂等）。"""
    gateway = get_messaging_gateway()
    if not gateway.running:
        return {
            "stopped": False,
            "already_stopped": True,
            "status": dict(
                await gateway.get_status_async(),
                agent_handler="custom" if _gateway_agent_handler else "default",
            ),
        }
    await gateway.stop()
    return {
        "stopped": True,
        "already_stopped": False,
        "status": dict(
            await gateway.get_status_async(),
            agent_handler="custom" if _gateway_agent_handler else "default",
        ),
    }


async def _forward_webhook_to_gateway_agent(
    channel_router: ChannelRouter, channel_name: str, payload: dict[str, Any]
) -> dict[str, Any] | None:
    """把已验签的 webhook 消息也送进 gateway agent 回路。

    仅当该平台已显式注册进 MessagingGateway 时激活；否则返回 None（webhook
    自身的 dispatch/回复路径保持原样，不重复处理、不重复回复）。
    """
    gateway = get_messaging_gateway()
    try:
        platform = PlatformType(channel_name)
    except ValueError:
        return None
    if not gateway.has_channel(platform):
        return None

    adapter = channel_router._registry.get(channel_name)
    if adapter is None:
        return None
    webhook_message = adapter.parse_inbound(payload)
    if webhook_message is None:
        return None

    incoming = IncomingMessage(
        platform=platform,
        channel_id=webhook_message.conversation_id or webhook_message.sender_id,
        user_id=webhook_message.sender_id,
        username=webhook_message.sender_id,
        content=webhook_message.text,
        metadata={"source": "webhook", "channel": channel_name},
    )
    reply = await _gateway_agent_relay(incoming)
    reply_sent = False
    if reply:
        reply_sent = await gateway.send(
            OutgoingMessage(
                content=reply,
                platform=platform,
                channel_id=incoming.channel_id,
                reply_to=incoming.id,
            )
        )
    return {
        "platform": platform.value,
        "content": incoming.content,
        "reply": reply,
        "reply_sent": reply_sent,
    }


def _wire_gateway_agent_loop() -> None:
    """router 模块 import 时自举：给 gateway 单例挂上 agent 回路。

    只挂 handler，不连接任何平台、不启动任何常驻循环——连接/启动只发生在
    显式 POST /gateway/register（connect=true）或 POST /gateway/start。
    """
    gateway: MessagingGateway = get_messaging_gateway()
    gateway.set_incoming_handler(_gateway_agent_relay)


_wire_gateway_agent_loop()
