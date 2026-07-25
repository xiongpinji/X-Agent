"""Notification system for collaboration with WebSocket, email, and push support."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from threading import RLock
from typing import Any
from uuid import uuid4


class NotificationType(StrEnum):
    """Types of notifications."""
    DOCUMENT_SHARED = "document_shared"
    PERMISSION_GRANTED = "permission_granted"
    COMMENT_ADDED = "comment_added"
    COMMENT_REPLIED = "comment_replied"
    MENTION = "mention"
    CONFLICT_DETECTED = "conflict_detected"
    CONFLICT_RESOLVED = "conflict_resolved"
    DOCUMENT_UPDATED = "document_updated"
    INVITATION_RECEIVED = "invitation_received"
    ACTIVITY_SUMMARY = "activity_summary"


class NotificationChannel(StrEnum):
    """Notification delivery channels."""
    WEBSOCKET = "websocket"
    EMAIL = "email"
    PUSH = "push"
    IN_APP = "in_app"


class NotificationPriority(StrEnum):
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class NotificationPreference:
    """User notification preferences."""
    user_id: str
    enabled: bool = True
    channels: dict[NotificationType, list[NotificationChannel]] = field(default_factory=dict)
    frequency: str = "immediate"  # "immediate", "hourly", "daily", "weekly"
    quiet_hours_start: str | None = None  # "HH:MM"
    quiet_hours_end: str | None = None
    aggregate_similar: bool = True
    max_notifications_per_day: int = 100
    metadata: dict[str, Any] = field(default_factory=dict)

    def should_notify(self, notification_type: NotificationType, channel: NotificationChannel) -> bool:
        """Check if notification should be sent."""
        if not self.enabled:
            return False

        channels = self.channels.get(notification_type, [NotificationChannel.IN_APP])
        return channel in channels

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "enabled": self.enabled,
            "channels": {k.value: [c.value for c in v] for k, v in self.channels.items()},
            "frequency": self.frequency,
            "quiet_hours_start": self.quiet_hours_start,
            "quiet_hours_end": self.quiet_hours_end,
            "aggregate_similar": self.aggregate_similar,
            "max_notifications_per_day": self.max_notifications_per_day,
            "metadata": self.metadata,
        }


@dataclass
class Notification:
    """Represents a notification."""
    notification_id: str
    user_id: str
    notification_type: NotificationType
    title: str
    content: str
    created_at: datetime
    read_at: datetime | None = None
    priority: NotificationPriority = NotificationPriority.NORMAL
    related_resource_id: str | None = None
    related_resource_type: str | None = None
    action_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    delivery_status: dict[NotificationChannel, str] = field(default_factory=dict)

    def is_read(self) -> bool:
        return self.read_at is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "user_id": self.user_id,
            "notification_type": self.notification_type.value,
            "title": self.title,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "priority": self.priority.value,
            "related_resource_id": self.related_resource_id,
            "related_resource_type": self.related_resource_type,
            "action_url": self.action_url,
            "metadata": self.metadata,
            "delivery_status": self.delivery_status,
        }


@dataclass
class NotificationBatch:
    """Batch of notifications for aggregation."""
    batch_id: str
    user_id: str
    notification_type: NotificationType
    notifications: list[Notification] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    sent_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_notification(self, notification: Notification) -> None:
        """Add a notification to the batch."""
        self.notifications.append(notification)

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "user_id": self.user_id,
            "notification_type": self.notification_type.value,
            "notification_count": len(self.notifications),
            "created_at": self.created_at.isoformat(),
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "notifications": [n.to_dict() for n in self.notifications],
            "metadata": self.metadata,
        }


class NotificationStore:
    """Store for managing notifications."""

    def __init__(self):
        self._notifications: dict[str, Notification] = {}
        self._user_notifications: dict[str, list[str]] = {}
        self._preferences: dict[str, NotificationPreference] = {}
        self._batches: dict[str, NotificationBatch] = {}
        self._delivery_queue: list[tuple[Notification, NotificationChannel]] = []
        self._lock = RLock()

    def create_notification(
        self,
        user_id: str,
        notification_type: NotificationType,
        title: str,
        content: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        related_resource_id: str | None = None,
        related_resource_type: str | None = None,
        action_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Notification:
        """Create a new notification."""
        with self._lock:
            notification = Notification(
                notification_id=str(uuid4()),
                user_id=user_id,
                notification_type=notification_type,
                title=title,
                content=content,
                created_at=datetime.now(UTC),
                priority=priority,
                related_resource_id=related_resource_id,
                related_resource_type=related_resource_type,
                action_url=action_url,
                metadata=metadata or {},
            )
            self._notifications[notification.notification_id] = notification

            if user_id not in self._user_notifications:
                self._user_notifications[user_id] = []
            self._user_notifications[user_id].append(notification.notification_id)

            return notification

    def get_notification(self, notification_id: str) -> Notification | None:
        """Get a notification by ID."""
        return self._notifications.get(notification_id)

    def get_user_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Notification]:
        """Get notifications for a user."""
        with self._lock:
            notification_ids = self._user_notifications.get(user_id, [])
            notifications = [self._notifications[nid] for nid in notification_ids if nid in self._notifications]

            if unread_only:
                notifications = [n for n in notifications if not n.is_read()]

            notifications.sort(key=lambda n: n.created_at, reverse=True)
            return notifications[offset : offset + limit]

    def mark_as_read(self, notification_id: str) -> bool:
        """Mark a notification as read."""
        with self._lock:
            notification = self._notifications.get(notification_id)
            if notification:
                notification.read_at = datetime.now(UTC)
                return True
            return False

    def mark_all_as_read(self, user_id: str) -> int:
        """Mark all notifications for a user as read."""
        with self._lock:
            notification_ids = self._user_notifications.get(user_id, [])
            count = 0
            for nid in notification_ids:
                notification = self._notifications.get(nid)
                if notification and not notification.is_read():
                    notification.read_at = datetime.now(UTC)
                    count += 1
            return count

    def delete_notification(self, notification_id: str) -> bool:
        """Delete a notification."""
        with self._lock:
            if notification_id in self._notifications:
                notification = self._notifications[notification_id]
                del self._notifications[notification_id]

                if notification.user_id in self._user_notifications:
                    self._user_notifications[notification.user_id].remove(notification_id)
                return True
            return False

    def get_unread_count(self, user_id: str) -> int:
        """Get unread notification count for a user."""
        with self._lock:
            notification_ids = self._user_notifications.get(user_id, [])
            return sum(1 for nid in notification_ids if nid in self._notifications and not self._notifications[nid].is_read())

    def set_preference(self, preference: NotificationPreference) -> None:
        """Set notification preferences for a user."""
        with self._lock:
            self._preferences[preference.user_id] = preference

    def get_preference(self, user_id: str) -> NotificationPreference:
        """Get notification preferences for a user."""
        with self._lock:
            if user_id not in self._preferences:
                self._preferences[user_id] = NotificationPreference(user_id=user_id)
            return self._preferences[user_id]

    def should_send_notification(
        self,
        user_id: str,
        notification_type: NotificationType,
        channel: NotificationChannel,
    ) -> bool:
        """Check if a notification should be sent."""
        with self._lock:
            preference = self.get_preference(user_id)
            return preference.should_notify(notification_type, channel)

    def queue_delivery(self, notification: Notification, channel: NotificationChannel) -> None:
        """Queue a notification for delivery."""
        with self._lock:
            self._delivery_queue.append((notification, channel))

    def get_delivery_queue(self) -> list[tuple[Notification, NotificationChannel]]:
        """Get the delivery queue."""
        with self._lock:
            queue = list(self._delivery_queue)
            self._delivery_queue.clear()
            return queue

    def create_batch(
        self,
        user_id: str,
        notification_type: NotificationType,
    ) -> NotificationBatch:
        """Create a notification batch."""
        with self._lock:
            batch = NotificationBatch(
                batch_id=str(uuid4()),
                user_id=user_id,
                notification_type=notification_type,
            )
            self._batches[batch.batch_id] = batch
            return batch

    def get_batch(self, batch_id: str) -> NotificationBatch | None:
        """Get a batch by ID."""
        return self._batches.get(batch_id)

    def mark_batch_sent(self, batch_id: str) -> bool:
        """Mark a batch as sent."""
        with self._lock:
            batch = self._batches.get(batch_id)
            if batch:
                batch.sent_at = datetime.now(UTC)
                return True
            return False


notification_store = NotificationStore()


class NotificationService:
    """Service for managing notifications."""

    def __init__(self, store: NotificationStore):
        self.store = store
        self._websocket_handlers: dict[str, list[Callable]] = {}
        self._email_handler: Callable | None = None
        self._push_handler: Callable | None = None
        self._lock = RLock()

    def register_websocket_handler(self, user_id: str, handler: Callable) -> None:
        """Register a WebSocket handler for a user."""
        with self._lock:
            if user_id not in self._websocket_handlers:
                self._websocket_handlers[user_id] = []
            self._websocket_handlers[user_id].append(handler)

    def unregister_websocket_handler(self, user_id: str, handler: Callable) -> None:
        """Unregister a WebSocket handler."""
        with self._lock:
            if user_id in self._websocket_handlers:
                self._websocket_handlers[user_id] = [h for h in self._websocket_handlers[user_id] if h != handler]

    def set_email_handler(self, handler: Callable) -> None:
        """Set the email notification handler."""
        self._email_handler = handler

    def set_push_handler(self, handler: Callable) -> None:
        """Set the push notification handler."""
        self._push_handler = handler

    async def send_notification(
        self,
        user_id: str,
        notification_type: NotificationType,
        title: str,
        content: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        related_resource_id: str | None = None,
        related_resource_type: str | None = None,
        action_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Notification:
        """Send a notification to a user."""
        notification = self.store.create_notification(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            content=content,
            priority=priority,
            related_resource_id=related_resource_id,
            related_resource_type=related_resource_type,
            action_url=action_url,
            metadata=metadata,
        )

        preference = self.store.get_preference(user_id)

        channels = preference.channels.get(notification_type, [NotificationChannel.IN_APP])

        for channel in channels:
            if self.store.should_send_notification(user_id, notification_type, channel):
                await self._deliver_notification(notification, channel)

        return notification

    async def _deliver_notification(self, notification: Notification, channel: NotificationChannel) -> None:
        """Deliver a notification via a specific channel."""
        try:
            if channel == NotificationChannel.WEBSOCKET:
                await self._deliver_websocket(notification)
            elif channel == NotificationChannel.EMAIL:
                await self._deliver_email(notification)
            elif channel == NotificationChannel.PUSH:
                await self._deliver_push(notification)
            elif channel == NotificationChannel.IN_APP:
                pass

            notification.delivery_status[channel] = "delivered"
        except Exception as e:
            notification.delivery_status[channel] = f"failed: {e!s}"

    async def _deliver_websocket(self, notification: Notification) -> None:
        """Deliver notification via WebSocket."""
        with self._lock:
            handlers = self._websocket_handlers.get(notification.user_id, [])

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(notification)
                else:
                    handler(notification)
            except Exception:
                pass

    async def _deliver_email(self, notification: Notification) -> None:
        """Deliver notification via email."""
        if self._email_handler:
            if asyncio.iscoroutinefunction(self._email_handler):
                await self._email_handler(notification)
            else:
                self._email_handler(notification)

    async def _deliver_push(self, notification: Notification) -> None:
        """Deliver notification via push."""
        if self._push_handler:
            if asyncio.iscoroutinefunction(self._push_handler):
                await self._push_handler(notification)
            else:
                self._push_handler(notification)

    async def send_batch_notification(
        self,
        user_id: str,
        notification_type: NotificationType,
        notifications: list[Notification],
        channel: NotificationChannel = NotificationChannel.EMAIL,
    ) -> NotificationBatch:
        """Send a batch of notifications."""
        batch = self.store.create_batch(user_id, notification_type)
        for notification in notifications:
            batch.add_notification(notification)

        await self._deliver_notification(batch.notifications[0] if batch.notifications else None, channel)
        self.store.mark_batch_sent(batch.batch_id)

        return batch


notification_service = NotificationService(notification_store)
