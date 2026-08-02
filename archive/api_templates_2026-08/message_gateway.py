"""Message Platform Gateway API.

HTTP surface for the multi-platform message gateway
(:mod:`backend.app.core.message_gateway`):

- ``POST   /api/v1/gateway/{platform}/webhook``   — inbound platform webhooks (public, signature-verified)
- ``POST   /api/v1/gateway/{platform}/send``      — send a message (auth: ``agent:run``)
- ``GET    /api/v1/gateway/status``               — aggregated gateway health (auth: ``agent:read``)
- ``POST   /api/v1/gateway/{platform}/connect``   — connect / authenticate (auth: ``security:manage``)
- ``DELETE /api/v1/gateway/{platform}/disconnect``— disconnect (auth: ``security:manage``)
- ``GET    /api/v1/gateway/{platform}/history``   — recent message history (auth: ``agent:read``)
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.message_gateway import (
    Attachment,
    GatewayButton,
    GatewayError,
    GatewayManager,
    GatewayMessage,
    GatewayNotConfiguredError,
    GatewaySignatureError,
    MessageKind,
    get_gateway_manager,
)
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/gateway", tags=["message-gateway"])

PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
ManagerDependency = Annotated[GatewayManager, Depends(get_gateway_manager)]

_VALID_PLATFORMS = ("telegram", "discord", "dingtalk", "feishu")


# ─── Request / Response Models ────────────────────────────────────────────────


class AttachmentRequest(BaseModel):
    """Attachment descriptor for outbound messages (URL-based)."""

    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(default="application/octet-stream", max_length=127)
    url: str | None = Field(default=None, max_length=2048)


class ButtonRequest(BaseModel):
    """Interactive button descriptor."""

    label: str = Field(..., min_length=1, max_length=80)
    value: str = Field(..., min_length=1, max_length=200)
    style: str = Field(default="default", pattern="^(default|primary|danger|link)$")
    url: str | None = Field(default=None, max_length=2048)


class GatewaySendRequest(BaseModel):
    """Unified outbound message request."""

    channel_id: str = Field(default="", max_length=255)
    user_id: str = Field(default="", max_length=255)
    content: str = Field(..., max_length=20_000)
    kind: Literal["text", "card", "file", "interactive"] = Field(default="text")
    attachments: list[AttachmentRequest] = Field(default_factory=list, max_length=10)
    buttons: list[ButtonRequest] = Field(default_factory=list, max_length=25)
    card: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    async_mode: bool = Field(
        default=False,
        description="Queue for async delivery (true) or send inline with retry (false)",
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _validate_platform(platform: str) -> str:
    normalized = platform.strip().lower()
    if normalized not in _VALID_PLATFORMS:
        raise api_error(
            404,
            ErrorCode.RESOURCE_NOT_FOUND,
            f"Unknown gateway platform: {platform!r}. "
            f"Valid platforms: {', '.join(_VALID_PLATFORMS)}",
        )
    return normalized


def _to_gateway_message(platform: str, req: GatewaySendRequest) -> GatewayMessage:
    """Convert an API request into the unified :class:`GatewayMessage`."""
    if not req.channel_id and not req.user_id:
        raise api_error(
            422,
            ErrorCode.VALIDATION_ERROR,
            "Either channel_id or user_id is required to send a message.",
        )
    return GatewayMessage(
        platform=platform,
        channel_id=req.channel_id,
        user_id=req.user_id,
        content=req.content,
        kind=MessageKind(req.kind),
        attachments=[
            Attachment(
                filename=a.filename,
                content_type=a.content_type,
                url=a.url,
            )
            for a in req.attachments
        ],
        buttons=[
            GatewayButton(label=b.label, value=b.value, style=b.style, url=b.url)
            for b in req.buttons
        ],
        card=req.card,
        metadata=req.metadata,
        direction="outbound",
    )


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/{platform}/webhook")
async def gateway_webhook(
    platform: str,
    request: Request,
    manager: ManagerDependency,
) -> dict[str, Any]:
    """Receive an inbound webhook from a messaging platform.

    Public endpoint — platforms call this directly. Security is enforced by
    each gateway's platform-specific signature verification.
    """
    normalized = _validate_platform(platform)
    gateway = manager.get(normalized)
    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    try:
        return await gateway.webhook_handler(body, headers)
    except GatewaySignatureError as exc:
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, str(exc))
    except GatewayError as exc:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, str(exc))


@router.post("/{platform}/send")
async def gateway_send(
    platform: str,
    payload: GatewaySendRequest,
    principal: PrincipalDependency,
    manager: ManagerDependency,
) -> dict[str, Any]:
    """Send a message through a platform gateway (sync or queued)."""
    enforce_scope(principal, "agent:run")
    normalized = _validate_platform(platform)
    gateway = manager.get(normalized)
    if not gateway.configured:
        raise api_error(
            503,
            ErrorCode.INTERNAL_ERROR,
            f"{normalized} gateway is not configured. Set the corresponding "
            "credentials (e.g. telegram_bot_token) and connect first.",
        )
    message = _to_gateway_message(normalized, payload)
    try:
        if payload.async_mode:
            message_id = await manager.enqueue(message)
            return {
                "accepted": True,
                "queued": True,
                "message_id": message_id,
                "platform": normalized,
            }
        result = await manager.send_now(message)
        return {
            "accepted": True,
            "queued": False,
            "message_id": message.message_id,
            "platform": normalized,
            "result": result,
        }
    except GatewayNotConfiguredError as exc:
        raise api_error(503, ErrorCode.INTERNAL_ERROR, str(exc))
    except GatewayError as exc:
        raise api_error(502, ErrorCode.INTERNAL_ERROR, str(exc))


@router.get("/status")
async def gateway_status(
    principal: PrincipalDependency,
    manager: ManagerDependency,
) -> dict[str, Any]:
    """Aggregated health status for every registered gateway."""
    enforce_scope(principal, "agent:read")
    return manager.health()


@router.post("/{platform}/connect")
async def gateway_connect(
    platform: str,
    principal: PrincipalDependency,
    manager: ManagerDependency,
) -> dict[str, Any]:
    """Connect / authenticate a gateway with its configured credentials."""
    enforce_scope(principal, "security:manage")
    normalized = _validate_platform(platform)
    gateway = manager.get(normalized)
    if not gateway.configured:
        raise api_error(
            503,
            ErrorCode.INTERNAL_ERROR,
            f"{normalized} gateway is not configured. Set its credentials first.",
        )
    try:
        await gateway.connect()
    except GatewayError as exc:
        raise api_error(502, ErrorCode.INTERNAL_ERROR, f"Connect failed: {exc}")
    return {"platform": normalized, "connected": True, "health": gateway.health()}


@router.delete("/{platform}/disconnect")
async def gateway_disconnect(
    platform: str,
    principal: PrincipalDependency,
    manager: ManagerDependency,
) -> dict[str, Any]:
    """Disconnect a gateway and release its resources."""
    enforce_scope(principal, "security:manage")
    normalized = _validate_platform(platform)
    gateway = manager.get(normalized)
    try:
        await gateway.disconnect()
    except GatewayError as exc:
        raise api_error(502, ErrorCode.INTERNAL_ERROR, f"Disconnect failed: {exc}")
    return {"platform": normalized, "connected": False, "health": gateway.health()}


@router.get("/{platform}/history")
async def gateway_history(
    platform: str,
    principal: PrincipalDependency,
    manager: ManagerDependency,
    limit: int = 50,
    direction: str | None = None,
) -> dict[str, Any]:
    """Return recent message history for a platform (newest first)."""
    enforce_scope(principal, "agent:read")
    normalized = _validate_platform(platform)
    if direction is not None and direction not in ("inbound", "outbound"):
        raise api_error(
            422,
            ErrorCode.VALIDATION_ERROR,
            "direction must be 'inbound' or 'outbound'.",
        )
    try:
        messages = manager.history(
            normalized, limit=max(1, min(limit, 500)), direction=direction
        )
    except GatewayError as exc:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, str(exc))
    return {"platform": normalized, "count": len(messages), "messages": messages}
