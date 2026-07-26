"""WebSocket notifications endpoint for X-Agent.

Provides real-time push notifications to connected clients:
- Agent task completion
- Workflow status changes
- System alerts
- Memory updates

Usage:
    Frontend connects to ws://host/api/v1/notifications/ws
    Server pushes JSON messages: { type, title, body, timestamp, metadata }
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from backend.app.core.notification_subscriptions import (
    PushSubscriptionKeys,
    PushSubscriptionRecord,
    get_subscription_store,
)
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

logger = logging.getLogger("xagent.notifications")

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

# WS 心跳间隔(秒)。无真实推送源时, 服务端按此周期向已连接客户端发送
# {"type": "heartbeat"} 保活帧; 测试可下调该值以快速验证。
HEARTBEAT_INTERVAL_SECONDS = 30.0


class ConnectionManager:
    """Manages WebSocket connections for real-time notifications."""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}  # user_id -> connections
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        async with self._lock:
            if user_id not in self._connections:
                self._connections[user_id] = []
            self._connections[user_id].append(websocket)
        logger.debug(f"WebSocket connected: user={user_id}, total={len(self._connections[user_id])}")

    async def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        async with self._lock:
            if user_id in self._connections:
                self._connections[user_id] = [
                    ws for ws in self._connections[user_id] if ws is not websocket
                ]
                if not self._connections[user_id]:
                    del self._connections[user_id]

    async def send_to_user(self, user_id: str, message: dict[str, Any]) -> None:
        """Send notification to all connections of a specific user."""
        async with self._lock:
            connections = self._connections.get(user_id, [])
            dead: list[WebSocket] = []
            for ws in connections:
                try:
                    await ws.send_json(message)
                except Exception:
                    dead.append(ws)
            # Clean up dead connections
            if dead:
                self._connections[user_id] = [
                    ws for ws in connections if ws not in dead
                ]

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Broadcast notification to all connected users."""
        async with self._lock:
            all_connections = []
            for conns in self._connections.values():
                all_connections.extend(conns)

        for ws in all_connections:
            with contextlib.suppress(Exception):
                await ws.send_json(message)

    @property
    def active_connections(self) -> int:
        return sum(len(conns) for conns in self._connections.values())


# Global connection manager
notification_manager = ConnectionManager()


@router.websocket("/ws")
async def notifications_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time notifications.

    Client connects and receives push notifications.
    Optionally send { "type": "subscribe", "channels": [...] } to filter.
    服务端每 HEARTBEAT_INTERVAL_SECONDS 秒发送一帧 {"type": "heartbeat"} 保活。
    """
    # Extract user_id from query params or token
    user_id = websocket.query_params.get("user_id", "anonymous")
    token = websocket.query_params.get("token")

    # Basic token validation (in production, validate JWT)
    if token:
        try:
            from backend.app.core.security import decode_token
            payload = decode_token(token)
            user_id = payload.get("sub", user_id)
        except Exception:
            pass  # Fall back to anonymous

    await notification_manager.connect(websocket, user_id)

    async def _heartbeat_loop() -> None:
        """周期性发送心跳帧, 无真实推送源时保持连接存活。"""
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
            await websocket.send_json({
                "type": "heartbeat",
                "timestamp": time.time(),
            })

    heartbeat_task = asyncio.create_task(_heartbeat_loop())

    try:
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "message": "Notification stream established",
            "timestamp": time.time(),
        })

        # Keep connection alive and listen for client messages
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": time.time()})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat_task
        await notification_manager.disconnect(websocket, user_id)


@router.get("/status")
async def notification_status() -> dict[str, Any]:
    """Get notification system status."""
    return {
        "active_connections": notification_manager.active_connections,
        "status": "active",
    }


# ─── Push subscription (Web Push) ──────────────────────────────────────────────


class PushSubscriptionBody(BaseModel):
    """前端 pushNotificationManager 上报的 subscription 结构"""

    endpoint: str = Field(..., min_length=1)
    keys: PushSubscriptionKeys


class SubscribeRequest(BaseModel):
    """POST /subscribe 请求体, 与前端 sendSubscriptionToServer 契约一致"""

    subscription: PushSubscriptionBody
    user_agent: str | None = None


@router.post("/subscribe", status_code=201)
async def subscribe_push(
    request: SubscribeRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> dict[str, Any]:
    """保存 Web Push subscription 到 JSON 文件存储。

    已认证主体强制 ``notifications:subscribe`` scope; 开发模式的匿名回落
    主体(生产环境已被 get_current_principal 拒绝)按 anonymous 记录。
    """
    if principal.authenticated:
        enforce_scope(principal, "notifications:subscribe")

    store = get_subscription_store()
    record = PushSubscriptionRecord(
        endpoint=request.subscription.endpoint,
        keys=request.subscription.keys,
        user_id=principal.user_id,
        tenant_id=principal.tenant_id,
        user_agent=request.user_agent,
    )
    saved = store.add(record)
    logger.info(f"Push subscription saved: {saved.id} (user={principal.user_id})")
    return {
        "status": "subscribed",
        "subscription_id": saved.id,
        "user_id": saved.user_id,
        "tenant_id": saved.tenant_id,
    }


class TestBroadcastRequest(BaseModel):
    """POST /broadcast/test 请求体"""

    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=2000)
    metadata: dict[str, Any] | None = None


@router.post("/broadcast/test")
async def broadcast_test(
    request: TestBroadcastRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> dict[str, Any]:
    """向所有已连接 WS 客户端真实广播一条测试通知(管理员)。

    无真实推送源时的联调入口: 消息经由 ConnectionManager 实际投递到
    每个活跃 WebSocket 连接, 不伪造投递结果。
    """
    enforce_scope(principal, "notifications:manage")

    await notify_all(
        notification_type="test_broadcast",
        title=request.title,
        body=request.body,
        metadata=request.metadata or {},
    )
    return {
        "status": "broadcast",
        "connections": notification_manager.active_connections,
        "timestamp": time.time(),
    }


# ─── Notification helpers (called from other modules) ──────────────────────────


async def notify_user(
    user_id: str,
    notification_type: str,
    title: str,
    body: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Send a notification to a specific user.

    Args:
        user_id: Target user ID.
        notification_type: Type (agent_complete, workflow_status, system_alert, etc.)
        title: Notification title.
        body: Notification body text.
        metadata: Additional data.
    """
    await notification_manager.send_to_user(user_id, {
        "type": notification_type,
        "title": title,
        "body": body,
        "timestamp": time.time(),
        "metadata": metadata or {},
    })


async def notify_all(
    notification_type: str,
    title: str,
    body: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Broadcast a notification to all connected users."""
    await notification_manager.broadcast({
        "type": notification_type,
        "title": title,
        "body": body,
        "timestamp": time.time(),
        "metadata": metadata or {},
    })
