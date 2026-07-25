"""
Agent communication module for X-Agent.

Implements inter-agent messaging protocol with Redis-based message queue,
supporting both synchronous and asynchronous communication.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class MessageType(StrEnum):
    """Types of messages between agents."""

    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    STATUS_UPDATE = "status_update"
    ERROR_REPORT = "error_report"
    DATA_SHARE = "data_share"
    QUERY = "query"
    ACKNOWLEDGMENT = "acknowledgment"


class MessagePriority(int, Enum):
    """Message priority levels."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class AgentMessage:
    """Represents a message between agents."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    from_agent_id: str = ""
    to_agent_id: str = ""
    message_type: MessageType = MessageType.TASK_REQUEST
    payload: dict = field(default_factory=dict)
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: datetime = field(default_factory=datetime.now)
    correlation_id: str | None = None
    reply_to: str | None = None
    metadata: dict = field(default_factory=dict)
    ttl_seconds: int = 3600

    def to_dict(self) -> dict:
        """Convert message to dictionary."""
        data = asdict(self)
        data["message_type"] = self.message_type.value
        data["priority"] = self.priority.value
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> AgentMessage:
        """Create message from dictionary."""
        data = data.copy()
        data["message_type"] = MessageType(data.get("message_type", "task_request"))
        data["priority"] = MessagePriority(data.get("priority", 2))
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


@dataclass
class MessageQueue:
    """Represents a message queue for an agent."""

    agent_id: str
    messages: list[AgentMessage] = field(default_factory=list)
    max_size: int = 1000

    def enqueue(self, message: AgentMessage) -> bool:
        """Add message to queue."""
        if len(self.messages) >= self.max_size:
            logger.warning(f"Queue full for agent {self.agent_id}")
            return False

        self.messages.append(message)
        # Sort by priority (higher priority first)
        self.messages.sort(key=lambda m: m.priority.value, reverse=True)
        return True

    def dequeue(self) -> AgentMessage | None:
        """Remove and return highest priority message."""
        if self.messages:
            return self.messages.pop(0)
        return None

    def peek(self) -> AgentMessage | None:
        """View highest priority message without removing."""
        if self.messages:
            return self.messages[0]
        return None

    def size(self) -> int:
        """Get queue size."""
        return len(self.messages)

    def clear(self) -> None:
        """Clear all messages."""
        self.messages.clear()


class AgentMessenger:
    """
    Manages inter-agent communication.

    Handles message routing, queuing, and delivery between agents.
    """

    def __init__(self, use_redis: bool = False):
        """
        Initialize the messenger.

        Args:
            use_redis: Whether to use Redis for message persistence
        """
        self.use_redis = use_redis
        self.message_queues: dict[str, MessageQueue] = {}
        self.message_handlers: dict[MessageType, list[Callable]] = {}
        self.pending_responses: dict[str, AgentMessage] = {}
        self.logger = logger

    def register_agent(self, agent_id: str) -> None:
        """Register an agent with the messenger."""
        if agent_id not in self.message_queues:
            self.message_queues[agent_id] = MessageQueue(agent_id=agent_id)
            self.logger.debug(f"Registered agent: {agent_id}")

    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent."""
        if agent_id in self.message_queues:
            del self.message_queues[agent_id]
            self.logger.debug(f"Unregistered agent: {agent_id}")

    async def send_message(
        self,
        from_agent_id: str,
        to_agent_id: str,
        message_type: MessageType,
        payload: dict,
        priority: MessagePriority = MessagePriority.NORMAL,
        correlation_id: str | None = None,
        reply_to: str | None = None,
    ) -> str:
        """
        Send a message from one agent to another.

        Args:
            from_agent_id: ID of sending agent
            to_agent_id: ID of receiving agent
            message_type: Type of message
            payload: Message payload
            priority: Message priority
            correlation_id: Correlation ID for tracking
            reply_to: ID of message this is replying to

        Returns:
            Message ID
        """
        # Ensure agents are registered
        self.register_agent(from_agent_id)
        self.register_agent(to_agent_id)

        # Create message
        message = AgentMessage(
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            message_type=message_type,
            payload=payload,
            priority=priority,
            correlation_id=correlation_id or str(uuid.uuid4()),
            reply_to=reply_to,
        )

        # Enqueue message
        queue = self.message_queues[to_agent_id]
        if queue.enqueue(message):
            self.logger.debug(
                f"Message sent: {from_agent_id} -> {to_agent_id} "
                f"({message_type.value})"
            )
            return message.id
        else:
            self.logger.error(f"Failed to send message to {to_agent_id}")
            return ""

    async def receive_message(self, agent_id: str) -> AgentMessage | None:
        """
        Receive next message for an agent.

        Args:
            agent_id: ID of receiving agent

        Returns:
            Next message or None if queue is empty
        """
        if agent_id not in self.message_queues:
            return None

        message = self.message_queues[agent_id].dequeue()
        if message:
            self.logger.debug(f"Message received by {agent_id}: {message.id}")

        return message

    async def peek_message(self, agent_id: str) -> AgentMessage | None:
        """
        Peek at next message without removing it.

        Args:
            agent_id: ID of agent

        Returns:
            Next message or None
        """
        if agent_id not in self.message_queues:
            return None

        return self.message_queues[agent_id].peek()

    def get_queue_size(self, agent_id: str) -> int:
        """Get message queue size for an agent."""
        if agent_id not in self.message_queues:
            return 0

        return self.message_queues[agent_id].size()

    def register_handler(
        self,
        message_type: MessageType,
        handler: Callable,
    ) -> None:
        """
        Register a handler for a message type.

        Args:
            message_type: Type of message to handle
            handler: Callable to handle the message
        """
        if message_type not in self.message_handlers:
            self.message_handlers[message_type] = []

        self.message_handlers[message_type].append(handler)
        self.logger.debug(f"Registered handler for {message_type.value}")

    async def dispatch_message(self, message: AgentMessage) -> Any:
        """
        Dispatch a message to registered handlers.

        Args:
            message: Message to dispatch

        Returns:
            Result from handler
        """
        handlers = self.message_handlers.get(message.message_type, [])

        if not handlers:
            self.logger.warning(f"No handlers for {message.message_type.value}")
            return None

        results = []
        for handler in handlers:
            try:
                result = await handler(message) if hasattr(handler, "__await__") else handler(message)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Error in message handler: {e}")

        return results[0] if results else None

    async def send_and_wait(
        self,
        from_agent_id: str,
        to_agent_id: str,
        message_type: MessageType,
        payload: dict,
        timeout_seconds: int = 30,
    ) -> AgentMessage | None:
        """
        Send a message and wait for response.

        Args:
            from_agent_id: ID of sending agent
            to_agent_id: ID of receiving agent
            message_type: Type of message
            payload: Message payload
            timeout_seconds: Timeout for response

        Returns:
            Response message or None if timeout
        """
        message_id = await self.send_message(
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            message_type=message_type,
            payload=payload,
        )

        # Wait for response
        import asyncio
        start_time = datetime.now()

        while (datetime.now() - start_time).total_seconds() < timeout_seconds:
            if message_id in self.pending_responses:
                return self.pending_responses.pop(message_id)

            await asyncio.sleep(0.1)

        self.logger.warning(f"Timeout waiting for response to {message_id}")
        return None

    def get_message_stats(self) -> dict:
        """Get statistics about message queues."""
        total_messages = sum(q.size() for q in self.message_queues.values())

        return {
            "total_agents": len(self.message_queues),
            "total_messages": total_messages,
            "avg_queue_size": (
                total_messages / len(self.message_queues)
                if self.message_queues else 0
            ),
            "queue_sizes": {
                agent_id: queue.size()
                for agent_id, queue in self.message_queues.items()
            },
        }

    def export_messages(self) -> dict:
        """Export all messages for persistence."""
        return {
            agent_id: [msg.to_dict() for msg in queue.messages]
            for agent_id, queue in self.message_queues.items()
        }

    def import_messages(self, data: dict) -> None:
        """Import messages from persistence."""
        for agent_id, messages_data in data.items():
            self.register_agent(agent_id)
            for msg_data in messages_data:
                message = AgentMessage.from_dict(msg_data)
                self.message_queues[agent_id].enqueue(message)


# Global instance
agent_messenger = AgentMessenger()
