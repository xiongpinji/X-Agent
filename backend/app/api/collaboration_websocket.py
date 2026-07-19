"""WebSocket handlers for real-time collaboration."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any, Optional
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect

from backend.app.core.collaboration_enhanced import (
    CollaborativeDocument,
    Operation,
    collaboration_store,
)
from backend.app.core.notification_system import (
    NotificationChannel,
    NotificationPriority,
    NotificationType,
    notification_service,
)

logger = logging.getLogger(__name__)


class CollaborationWebSocketManager:
    """Manages WebSocket connections for real-time collaboration."""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}
        self.user_connections: dict[str, list[tuple[str, WebSocket]]] = {}
        self.connection_metadata: dict[WebSocket, dict[str, Any]] = {}
        self._lock = asyncio.Lock()  # Thread-safe lock for concurrent operations

    async def connect(self, websocket: WebSocket, doc_id: str, user_id: str) -> None:
        """Register a new WebSocket connection (thread-safe)."""
        await websocket.accept()

        async with self._lock:
            if doc_id not in self.active_connections:
                self.active_connections[doc_id] = []
            self.active_connections[doc_id].append(websocket)

            if user_id not in self.user_connections:
                self.user_connections[user_id] = []
            self.user_connections[user_id].append((doc_id, websocket))

            self.connection_metadata[websocket] = {
                "doc_id": doc_id,
                "user_id": user_id,
                "connected_at": datetime.now(UTC),
                "last_activity": datetime.now(UTC),
            }

        logger.info(f"User {user_id} connected to document {doc_id}")

    async def disconnect(self, websocket: WebSocket) -> None:
        """Unregister a WebSocket connection (thread-safe)."""
        async with self._lock:
            if websocket not in self.connection_metadata:
                return

            metadata = self.connection_metadata[websocket]
            doc_id = metadata["doc_id"]
            user_id = metadata["user_id"]

            if doc_id in self.active_connections:
                try:
                    self.active_connections[doc_id].remove(websocket)
                except ValueError:
                    logger.warning(f"WebSocket not found in active_connections for {doc_id}")
                if not self.active_connections[doc_id]:
                    del self.active_connections[doc_id]

            if user_id in self.user_connections:
                self.user_connections[user_id] = [
                    (d, ws) for d, ws in self.user_connections[user_id] if ws != websocket
                ]
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]

            del self.connection_metadata[websocket]
            logger.info(f"User {user_id} disconnected from document {doc_id}")

    async def broadcast_to_document(
        self,
        doc_id: str,
        message: dict[str, Any],
        exclude_websocket: Optional[WebSocket] = None,
    ) -> None:
        """Broadcast a message to all users in a document (thread-safe)."""
        async with self._lock:
            if doc_id not in self.active_connections:
                return
            # Create a copy to avoid modification during iteration
            connections_copy = list(self.active_connections[doc_id])

        disconnected = []
        for websocket in connections_copy:
            if exclude_websocket and websocket == exclude_websocket:
                continue

            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(
                    f"Error sending message to doc {doc_id}: {type(e).__name__}: {e}",
                    extra={"doc_id": doc_id, "user_id": self.connection_metadata.get(websocket, {}).get("user_id")},
                )
                disconnected.append(websocket)

        # Clean up disconnected websockets
        for websocket in disconnected:
            await self.disconnect(websocket)

    async def broadcast_to_user(
        self,
        user_id: str,
        message: dict[str, Any],
    ) -> None:
        """Broadcast a message to all connections of a user (thread-safe)."""
        async with self._lock:
            if user_id not in self.user_connections:
                return
            # Create a copy to avoid modification during iteration
            connections_copy = list(self.user_connections[user_id])

        disconnected = []
        for doc_id, websocket in connections_copy:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(
                    f"Error sending message to user {user_id} in doc {doc_id}: {type(e).__name__}: {e}",
                    extra={"user_id": user_id, "doc_id": doc_id},
                )
                disconnected.append(websocket)

        # Clean up disconnected websockets
        for websocket in disconnected:
            await self.disconnect(websocket)

    def get_active_users(self, doc_id: str) -> list[str]:
        """Get list of active users in a document."""
        if doc_id not in self.active_connections:
            return []

        users = set()
        for websocket in self.active_connections[doc_id]:
            if websocket in self.connection_metadata:
                users.add(self.connection_metadata[websocket]["user_id"])
        return list(users)

    def get_connection_count(self, doc_id: str) -> int:
        """Get number of active connections for a document."""
        return len(self.active_connections.get(doc_id, []))


ws_manager = CollaborationWebSocketManager()


class CollaborationWebSocketHandler:
    """Handles WebSocket messages for real-time collaboration."""

    # Configuration constants
    MESSAGE_TIMEOUT_SECONDS = 300  # 5 minutes
    HEARTBEAT_INTERVAL_SECONDS = 30  # 30 seconds
    MAX_IDLE_TIME_SECONDS = 600  # 10 minutes

    def __init__(self, websocket: WebSocket, doc_id: str, user_id: str):
        self.websocket = websocket
        self.doc_id = doc_id
        self.user_id = user_id
        self.doc: Optional[CollaborativeDocument] = None
        self.last_activity = datetime.now(UTC)

    async def handle(self) -> None:
        """Main WebSocket message handler with timeout and heartbeat."""
        try:
            await ws_manager.connect(self.websocket, self.doc_id, self.user_id)

            self.doc = collaboration_store.get_document(self.doc_id)
            if not self.doc:
                await self.websocket.send_json({
                    "type": "error",
                    "message": "Document not found",
                })
                return

            await self._send_initial_state()
            await self._broadcast_user_joined()

            # Start heartbeat task
            heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            try:
                while True:
                    try:
                        # Receive message with timeout
                        data = await asyncio.wait_for(
                            self.websocket.receive_json(),
                            timeout=self.MESSAGE_TIMEOUT_SECONDS,
                        )
                        self.last_activity = datetime.now(UTC)
                        await self._handle_message(data)
                    except asyncio.TimeoutError:
                        # Check if connection is idle
                        idle_time = (datetime.now(UTC) - self.last_activity).total_seconds()
                        if idle_time > self.MAX_IDLE_TIME_SECONDS:
                            logger.warning(
                                f"WebSocket connection idle for {idle_time}s, closing",
                                extra={"user_id": self.user_id, "doc_id": self.doc_id},
                            )
                            break
                        # Otherwise, continue waiting
                        continue
            finally:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

        except WebSocketDisconnect:
            await ws_manager.disconnect(self.websocket)
            await self._broadcast_user_left()
        except Exception as e:
            logger.error(
                f"WebSocket error: {type(e).__name__}: {e}",
                extra={"user_id": self.user_id, "doc_id": self.doc_id},
            )
            await ws_manager.disconnect(self.websocket)

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat messages to keep connection alive."""
        try:
            while True:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL_SECONDS)
                try:
                    await self.websocket.send_json({"type": "heartbeat"})
                except Exception as e:
                    logger.debug(f"Failed to send heartbeat: {e}")
                    break
        except asyncio.CancelledError:
            pass

    async def _send_initial_state(self) -> None:
        """Send initial document state to the client."""
        if not self.doc:
            return

        active_users = ws_manager.get_active_users(self.doc_id)

        await self.websocket.send_json({
            "type": "initial_state",
            "document": self.doc.to_dict(),
            "active_users": active_users,
            "cursors": [
                {
                    "user_id": c.user_id,
                    "position": c.position,
                    "color": c.color,
                    "name": c.name,
                }
                for c in self.doc.get_active_cursors()
            ],
        })

    async def _handle_message(self, data: dict[str, Any]) -> None:
        """Handle incoming WebSocket message."""
        message_type = data.get("type")

        if message_type == "operation":
            await self._handle_operation(data)
        elif message_type == "cursor":
            await self._handle_cursor_update(data)
        elif message_type == "comment":
            await self._handle_comment(data)
        elif message_type == "ping":
            await self.websocket.send_json({"type": "pong"})
        else:
            logger.warning(f"Unknown message type: {message_type}")

    async def _handle_operation(self, data: dict[str, Any]) -> None:
        """Handle operation message."""
        if not self.doc:
            return

        try:
            operation = Operation(
                op_id=str(uuid4()),
                user_id=self.user_id,
                timestamp=datetime.now(UTC),
                op_type=data.get("op_type", "insert"),
                position=data.get("position", 0),
                content=data.get("content", ""),
                version=self.doc.version_number,
            )

            conflicts = self.doc.detect_conflicts(operation)

            if conflicts:
                await self.websocket.send_json({
                    "type": "conflict_detected",
                    "conflicts": [c.to_dict() for c in conflicts],
                    "operation": operation.to_dict(),
                })
                return

            if self.doc.apply_operation(operation):
                await ws_manager.broadcast_to_document(
                    self.doc_id,
                    {
                        "type": "operation_applied",
                        "operation": operation.to_dict(),
                        "document_state": self.doc.content,
                    },
                    exclude_websocket=self.websocket,
                )

                await self.websocket.send_json({
                    "type": "operation_ack",
                    "op_id": operation.op_id,
                    "status": "applied",
                })
            else:
                await self.websocket.send_json({
                    "type": "error",
                    "message": "Failed to apply operation",
                })

        except Exception as e:
            logger.error(f"Error handling operation: {e}")
            await self.websocket.send_json({
                "type": "error",
                "message": str(e),
            })

    async def _handle_cursor_update(self, data: dict[str, Any]) -> None:
        """Handle cursor update message."""
        if not self.doc:
            return

        try:
            cursor = self.doc.update_cursor(
                user_id=self.user_id,
                position=data.get("position", 0),
                selection_start=data.get("selection_start", 0),
                selection_end=data.get("selection_end", 0),
                color=data.get("color", ""),
                name=data.get("name", self.user_id),
            )

            await ws_manager.broadcast_to_document(
                self.doc_id,
                {
                    "type": "cursor_updated",
                    "cursor": {
                        "user_id": cursor.user_id,
                        "position": cursor.position,
                        "selection_start": cursor.selection_start,
                        "selection_end": cursor.selection_end,
                        "color": cursor.color,
                        "name": cursor.name,
                        "updated_at": cursor.updated_at.isoformat(),
                    },
                },
                exclude_websocket=self.websocket,
            )

        except Exception as e:
            logger.error(f"Error handling cursor update: {e}")

    async def _handle_comment(self, data: dict[str, Any]) -> None:
        """Handle comment message."""
        if not self.doc:
            return

        try:
            comment = self.doc.add_comment(
                user_id=self.user_id,
                content=data.get("content", ""),
                position=data.get("position", 0),
                parent_comment_id=data.get("parent_comment_id"),
            )

            await ws_manager.broadcast_to_document(
                self.doc_id,
                {
                    "type": "comment_added",
                    "comment": comment.to_dict(),
                },
            )

            await notification_service.send_notification(
                user_id=self.doc.owner_id,
                notification_type=NotificationType.COMMENT_ADDED,
                title="New Comment",
                content=f"{self.user_id} commented on your document",
                related_resource_id=self.doc_id,
                related_resource_type="document",
                action_url=f"/documents/{self.doc_id}#comment-{comment.comment_id}",
            )

        except Exception as e:
            logger.error(f"Error handling comment: {e}")
            await self.websocket.send_json({
                "type": "error",
                "message": str(e),
            })

    async def _broadcast_user_joined(self) -> None:
        """Broadcast user joined message."""
        active_users = ws_manager.get_active_users(self.doc_id)

        await ws_manager.broadcast_to_document(
            self.doc_id,
            {
                "type": "user_joined",
                "user_id": self.user_id,
                "active_users": active_users,
            },
            exclude_websocket=self.websocket,
        )

    async def _broadcast_user_left(self) -> None:
        """Broadcast user left message."""
        active_users = ws_manager.get_active_users(self.doc_id)

        await ws_manager.broadcast_to_document(
            self.doc_id,
            {
                "type": "user_left",
                "user_id": self.user_id,
                "active_users": active_users,
            },
        )


async def collaboration_websocket_endpoint(
    websocket: WebSocket,
    doc_id: str,
    user_id: str,
) -> None:
    """WebSocket endpoint for real-time collaboration."""
    handler = CollaborationWebSocketHandler(websocket, doc_id, user_id)
    await handler.handle()
