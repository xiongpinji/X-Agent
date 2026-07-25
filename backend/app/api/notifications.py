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
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("xagent.notifications")

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


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
        await notification_manager.disconnect(websocket, user_id)


@router.get("/status")
async def notification_status() -> dict[str, Any]:
    """Get notification system status."""
    return {
        "active_connections": notification_manager.active_connections,
        "status": "active",
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
