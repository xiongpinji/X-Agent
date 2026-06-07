"""Inbound channel routing and dispatch helpers."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from backend.app.core.channels.base import (
    ChannelAdapter,
    ChannelDispatchResult,
    ChannelMessage,
    ChannelRegistry,
)
from backend.app.core.dispatch import DispatchRequest, dispatch

DispatchCallable = Callable[[ChannelMessage], dict[str, Any] | Awaitable[dict[str, Any]]]
ReplySender = Callable[[ChannelMessage, str], dict[str, Any] | Awaitable[dict[str, Any]]]


class ChannelRouterError(Exception):
    """Base class for channel router errors."""


class ChannelSignatureError(ChannelRouterError):
    """Raised when a channel webhook signature is invalid."""


class ChannelNotConfiguredError(ChannelRouterError):
    """Raised when the requested channel has no adapter."""


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _message_id(message: ChannelMessage) -> str:
    raw_message = message.raw.get("message") or message.raw.get("edited_message") or {}
    return str(raw_message.get("message_id") or raw_message.get("id") or uuid4())


def default_channel_dispatch(message: ChannelMessage) -> dict[str, Any]:
    """Dispatch an inbound channel message into X-Agent's routing boundary."""

    result = dispatch(
        DispatchRequest(
            org_id="default",
            agent_id="default-agent",
            room_id=message.conversation_id,
            task=message.text,
            task_type=f"channel:{message.channel}",
            mode="suggest",
            collaboration_hint={
                "channel": message.channel,
                "sender_id": message.sender_id,
                "conversation_id": message.conversation_id,
            },
            replay_hint=True,
        )
    )
    return {
        "run_id": result.trace_id or str(uuid4()),
        "status": result.status,
        "reply_text": f"X-Agent received: {message.text}",
        "dispatch": result.model_dump(mode="json"),
    }


class ChannelRouter:
    """Route verified inbound channel payloads to dispatch and optional replies."""

    def __init__(
        self,
        registry: ChannelRegistry,
        *,
        dispatch_callable: DispatchCallable = default_channel_dispatch,
        reply_sender: ReplySender | None = None,
    ) -> None:
        self._registry = registry
        self._dispatch = dispatch_callable
        self._reply_sender = reply_sender

    async def process_inbound(
        self,
        *,
        channel: str,
        body: bytes,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> ChannelDispatchResult:
        adapter = self._registry.get(channel)
        if adapter is None:
            raise ChannelNotConfiguredError(f"Channel adapter not configured: {channel}")
        if not adapter.verify_signature(body, headers):
            raise ChannelSignatureError(f"Invalid {channel} webhook signature")

        message = adapter.parse_inbound(payload)
        if message is None:
            return ChannelDispatchResult(
                channel=channel,
                conversation_id="",
                message_id="",
                run_id="",
                status="ignored",
                reply_sent=False,
            )

        dispatch_payload = await _maybe_await(self._dispatch(message))
        run_id = str(dispatch_payload.get("run_id") or uuid4())
        status = str(dispatch_payload.get("status") or "accepted")
        reply_text = str(dispatch_payload.get("reply_text") or "")
        outbound: dict[str, Any] = {}
        reply_sent = False
        if reply_text:
            outbound = await self._send_reply(adapter, message, reply_text)
            reply_sent = True

        return ChannelDispatchResult(
            channel=message.channel,
            conversation_id=message.conversation_id,
            message_id=_message_id(message),
            run_id=run_id,
            status=status,
            reply_sent=reply_sent,
            reply_text=reply_text,
            sender_id=message.sender_id,
            dispatch=dict(dispatch_payload.get("dispatch") or dispatch_payload),
            outbound=outbound,
        )

    async def _send_reply(
        self,
        adapter: ChannelAdapter,
        message: ChannelMessage,
        reply_text: str,
    ) -> dict[str, Any]:
        if self._reply_sender is not None:
            return dict(await _maybe_await(self._reply_sender(message, reply_text)))
        return dict(await adapter.send_text(message.conversation_id, reply_text))
