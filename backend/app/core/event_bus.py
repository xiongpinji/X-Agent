"""
Event Bus for decoupling Agent execution from external systems.

Implements publish-subscribe pattern to reduce module coupling.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import uuid4

logger = logging.getLogger(__name__)


class EventType(StrEnum):
    """Event types in the system."""

    # Agent execution events
    AGENT_STARTED = "agent.started"
    AGENT_STEP_COMPLETED = "agent.step_completed"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"

    # Workflow events
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_STEP_COMPLETED = "workflow.step_completed"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"

    # Tool execution events
    TOOL_EXECUTED = "tool.executed"
    TOOL_FAILED = "tool.failed"

    # Memory events
    MEMORY_UPDATED = "memory.updated"
    MEMORY_RETRIEVED = "memory.retrieved"

    # Security events
    AUTHENTICATION_FAILED = "auth.failed"
    AUTHORIZATION_FAILED = "auth.unauthorized"
    SUSPICIOUS_ACTIVITY = "security.suspicious"

    # System events
    SYSTEM_ERROR = "system.error"
    SYSTEM_WARNING = "system.warning"


@dataclass
class Event:
    """Base event class."""

    event_type: EventType
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    event_id: str = field(default_factory=lambda: str(uuid4()))
    source: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
    user_id: str | None = None
    tenant_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "event_id": self.event_id,
            "source": self.source,
            "data": self.data,
            "correlation_id": self.correlation_id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
        }


class EventHandler(Protocol):
    """Protocol for event handlers."""

    async def __call__(self, event: Event) -> None:
        """Handle an event."""
        ...


class EventBus:
    """
    Publish-subscribe event bus for decoupling system components.

    Features:
    - Async event handling
    - Multiple subscribers per event type
    - Error handling and logging
    - Event filtering by type and source
    """

    def __init__(self) -> None:
        self._subscribers: dict[EventType, list[EventHandler]] = {}
        self._event_history: list[Event] = []
        self._max_history: int = 10000
        self._lock = asyncio.Lock()

    async def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Subscribe to an event type."""
        async with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(handler)
            logger.debug(f"Subscribed handler to {event_type.value}")

    async def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Unsubscribe from an event type."""
        async with self._lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(handler)
                    logger.debug(f"Unsubscribed handler from {event_type.value}")
                except ValueError:
                    pass

    async def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""
        async with self._lock:
            # Store in history
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history.pop(0)

            # Get subscribers for this event type
            handlers = self._subscribers.get(event.event_type, [])

        # Execute handlers (outside lock to avoid blocking)
        if handlers:
            logger.debug(f"Publishing event {event.event_type.value} to {len(handlers)} handlers")
            tasks = [self._safe_call_handler(handler, event) for handler in handlers]
            await asyncio.gather(*tasks, return_exceptions=True)
        else:
            logger.debug(f"No handlers for event {event.event_type.value}")

    async def _safe_call_handler(self, handler: EventHandler, event: Event) -> None:
        """Safely call a handler, catching any exceptions."""
        try:
            await handler(event)
        except Exception as e:
            logger.error(f"Error in event handler for {event.event_type.value}: {e}", exc_info=True)

    def get_history(self, event_type: EventType | None = None, limit: int = 100) -> list[Event]:
        """Get event history, optionally filtered by type."""
        if event_type is None:
            return self._event_history[-limit:]
        return [e for e in self._event_history if e.event_type == event_type][-limit:]

    def clear_history(self) -> None:
        """Clear event history."""
        self._event_history.clear()


# Global event bus instance
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get or create the global event bus."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
