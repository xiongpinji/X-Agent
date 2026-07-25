"""
Agent Communication Bus - Enables inter-agent messaging and coordination.

Features:
- Point-to-point messaging
- Broadcast messaging
- Topic-based pub/sub
- Message queuing
- Message prioritization
- Message persistence (optional)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from heapq import heappop, heappush
from typing import Any

logger = logging.getLogger(__name__)


class MessagePriority(StrEnum):
    """Message priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class MessageType(StrEnum):
    """Types of messages."""
    DIRECT = "direct"
    BROADCAST = "broadcast"
    TOPIC = "topic"
    COMMAND = "command"
    RESPONSE = "response"
    EVENT = "event"


@dataclass
class Message:
    """Represents a message in the communication bus."""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    from_agent: str = ""
    to_agent: str | None = None
    message_type: MessageType = MessageType.DIRECT
    topic: str | None = None
    content: Any = None
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    reply_to: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    ttl_seconds: int | None = None
    delivered: bool = False
    delivery_attempts: int = 0

    def __lt__(self, other: Message) -> bool:
        """Compare messages by priority for heap operations."""
        priority_order = {
            MessagePriority.CRITICAL: 0,
            MessagePriority.HIGH: 1,
            MessagePriority.NORMAL: 2,
            MessagePriority.LOW: 3,
        }
        return priority_order[self.priority] < priority_order[other.priority]

    def is_expired(self) -> bool:
        """Check if message has expired."""
        if self.ttl_seconds is None:
            return False
        age = (datetime.now(UTC) - self.timestamp).total_seconds()
        return age > self.ttl_seconds

    def to_dict(self) -> dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "message_id": self.message_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "message_type": self.message_type.value,
            "topic": self.topic,
            "content": self.content,
            "priority": self.priority.value,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to,
            "metadata": self.metadata,
            "ttl_seconds": self.ttl_seconds,
            "delivered": self.delivered,
            "delivery_attempts": self.delivery_attempts,
        }


@dataclass
class MessageQueue:
    """Priority queue for messages."""
    messages: list[tuple[int, int, Message]] = field(default_factory=list)
    _counter: int = 0

    def put(self, message: Message):
        """Add message to queue."""
        # 堆排序键必须把优先级放在首位，counter 仅作同优先级下的
        # 稳定先到先出（FIFO）裁决项。此前误用 (counter, message) 导致
        # counter 永不相等，message.__lt__ 从不被调用，优先级被完全忽略。
        priority_rank = {
            MessagePriority.CRITICAL: 0,
            MessagePriority.HIGH: 1,
            MessagePriority.NORMAL: 2,
            MessagePriority.LOW: 3,
        }[message.priority]
        heappush(self.messages, (priority_rank, self._counter, message))
        self._counter += 1

    def get(self) -> Message | None:
        """Get highest priority message from queue."""
        if not self.messages:
            return None
        _, _, message = heappop(self.messages)
        return message

    def size(self) -> int:
        """Get queue size."""
        return len(self.messages)

    def clear(self):
        """Clear all messages."""
        self.messages.clear()
        self._counter = 0


class AgentCommunicationBus:
    """
    Central message bus for inter-agent communication.

    Supports:
    - Direct point-to-point messaging
    - Broadcast messaging to all agents
    - Topic-based pub/sub
    - Message prioritization
    - Message expiration (TTL)
    - Delivery tracking
    """

    def __init__(self, enable_persistence: bool = False, max_queue_size: int = 10000):
        """
        Initialize the communication bus.

        Args:
            enable_persistence: Enable message persistence
            max_queue_size: Maximum messages in queue
        """
        self.enable_persistence = enable_persistence
        self.max_queue_size = max_queue_size

        # Message storage
        self.message_queues: dict[str, MessageQueue] = defaultdict(MessageQueue)
        self.broadcast_queue = MessageQueue()
        self.topic_queues: dict[str, MessageQueue] = defaultdict(MessageQueue)

        # Subscriptions
        self.topic_subscribers: dict[str, set[str]] = defaultdict(set)
        self.agent_subscriptions: dict[str, set[str]] = defaultdict(set)

        # Message history
        self.message_history: list[Message] = []
        self.max_history_size = 10000

        # Callbacks
        self.message_handlers: dict[str, list[Callable]] = defaultdict(list)
        self.topic_handlers: dict[str, list[Callable]] = defaultdict(list)

        # Locks for thread safety
        self._lock = asyncio.Lock()
        self._queue_lock = asyncio.Lock()

        # Statistics
        self.stats = {
            "total_messages": 0,
            "delivered_messages": 0,
            "failed_messages": 0,
            "expired_messages": 0,
        }

    async def send_message(
        self,
        from_agent: str,
        to_agent: str,
        content: Any,
        priority: MessagePriority = MessagePriority.NORMAL,
        correlation_id: str | None = None,
        reply_to: str | None = None,
        ttl_seconds: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Send a direct message from one agent to another.

        Args:
            from_agent: Sender agent ID
            to_agent: Recipient agent ID
            content: Message content
            priority: Message priority
            correlation_id: Correlation ID for tracking
            reply_to: Message ID to reply to
            ttl_seconds: Time to live in seconds
            metadata: Additional metadata

        Returns:
            Message ID
        """
        message = Message(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=MessageType.DIRECT,
            content=content,
            priority=priority,
            correlation_id=correlation_id or str(uuid.uuid4()),
            reply_to=reply_to,
            ttl_seconds=ttl_seconds,
            metadata=metadata or {},
        )

        async with self._queue_lock:
            if len(self.message_queues[to_agent].messages) >= self.max_queue_size:
                logger.warning(f"Message queue for {to_agent} is full")
                self.stats["failed_messages"] += 1
                raise RuntimeError(f"Message queue for {to_agent} is full")

            self.message_queues[to_agent].put(message)
            self.stats["total_messages"] += 1

        # Store in history
        await self._add_to_history(message)

        # Call handlers
        await self._call_handlers(to_agent, message)

        logger.debug(
            f"Message {message.message_id} sent from {from_agent} to {to_agent}"
        )

        return message.message_id

    async def broadcast(
        self,
        from_agent: str,
        content: Any,
        priority: MessagePriority = MessagePriority.NORMAL,
        exclude_agents: list[str] | None = None,
        ttl_seconds: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Broadcast a message to all agents.

        Args:
            from_agent: Sender agent ID
            content: Message content
            priority: Message priority
            exclude_agents: Agents to exclude from broadcast
            ttl_seconds: Time to live in seconds
            metadata: Additional metadata

        Returns:
            Message ID
        """
        message = Message(
            from_agent=from_agent,
            message_type=MessageType.BROADCAST,
            content=content,
            priority=priority,
            ttl_seconds=ttl_seconds,
            metadata=metadata or {},
        )

        async with self._queue_lock:
            self.broadcast_queue.put(message)
            self.stats["total_messages"] += 1

        await self._add_to_history(message)

        logger.debug(f"Broadcast message {message.message_id} from {from_agent}")

        return message.message_id

    async def publish(
        self,
        topic: str,
        content: Any,
        from_agent: str | None = None,
        priority: MessagePriority = MessagePriority.NORMAL,
        ttl_seconds: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Publish a message to a topic.

        Args:
            topic: Topic name
            content: Message content
            from_agent: Publisher agent ID
            priority: Message priority
            ttl_seconds: Time to live in seconds
            metadata: Additional metadata

        Returns:
            Message ID
        """
        message = Message(
            from_agent=from_agent or "system",
            message_type=MessageType.TOPIC,
            topic=topic,
            content=content,
            priority=priority,
            ttl_seconds=ttl_seconds,
            metadata=metadata or {},
        )

        async with self._queue_lock:
            self.topic_queues[topic].put(message)
            self.stats["total_messages"] += 1

        await self._add_to_history(message)

        # Call topic handlers
        await self._call_topic_handlers(topic, message)

        logger.debug(f"Message published to topic {topic}")

        return message.message_id

    async def subscribe(
        self,
        agent_id: str,
        topic: str,
        handler: Callable | None = None,
    ) -> None:
        """
        Subscribe an agent to a topic.

        Args:
            agent_id: Agent ID
            topic: Topic name
            handler: Optional callback handler
        """
        async with self._lock:
            self.topic_subscribers[topic].add(agent_id)
            self.agent_subscriptions[agent_id].add(topic)

            if handler:
                self.topic_handlers[topic].append(handler)

        logger.debug(f"Agent {agent_id} subscribed to topic {topic}")

    async def unsubscribe(self, agent_id: str, topic: str) -> None:
        """
        Unsubscribe an agent from a topic.

        Args:
            agent_id: Agent ID
            topic: Topic name
        """
        async with self._lock:
            self.topic_subscribers[topic].discard(agent_id)
            self.agent_subscriptions[agent_id].discard(topic)

        logger.debug(f"Agent {agent_id} unsubscribed from topic {topic}")

    async def receive_message(self, agent_id: str) -> Message | None:
        """
        Receive the next message for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            Next message or None if queue is empty
        """
        async with self._queue_lock:
            message = self.message_queues[agent_id].get()

            if message:
                message.delivered = True
                message.delivery_attempts += 1
                self.stats["delivered_messages"] += 1

        return message

    async def receive_broadcast(self) -> Message | None:
        """
        Receive the next broadcast message.

        Returns:
            Next broadcast message or None if queue is empty
        """
        async with self._queue_lock:
            message = self.broadcast_queue.get()

            if message:
                message.delivered = True
                self.stats["delivered_messages"] += 1

        return message

    async def receive_topic_message(self, topic: str) -> Message | None:
        """
        Receive the next message for a topic.

        Args:
            topic: Topic name

        Returns:
            Next message or None if queue is empty
        """
        async with self._queue_lock:
            message = self.topic_queues[topic].get()

            if message:
                message.delivered = True
                self.stats["delivered_messages"] += 1

        return message

    async def register_handler(
        self,
        agent_id: str,
        handler: Callable[[Message], Any],
    ) -> None:
        """
        Register a message handler for an agent.

        Args:
            agent_id: Agent ID
            handler: Callback function
        """
        async with self._lock:
            self.message_handlers[agent_id].append(handler)

    async def register_topic_handler(
        self,
        topic: str,
        handler: Callable[[Message], Any],
    ) -> None:
        """
        Register a message handler for a topic.

        Args:
            topic: Topic name
            handler: Callback function
        """
        async with self._lock:
            self.topic_handlers[topic].append(handler)

    async def get_queue_size(self, agent_id: str) -> int:
        """Get the size of an agent's message queue."""
        async with self._queue_lock:
            return self.message_queues[agent_id].size()

    async def get_topic_queue_size(self, topic: str) -> int:
        """Get the size of a topic's message queue."""
        async with self._queue_lock:
            return self.topic_queues[topic].size()

    async def get_subscribers(self, topic: str) -> set[str]:
        """Get all subscribers for a topic."""
        async with self._lock:
            return self.topic_subscribers[topic].copy()

    async def get_subscriptions(self, agent_id: str) -> set[str]:
        """Get all topics an agent is subscribed to."""
        async with self._lock:
            return self.agent_subscriptions[agent_id].copy()

    async def get_stats(self) -> dict[str, Any]:
        """Get communication bus statistics."""
        async with self._lock:
            return {
                **self.stats,
                "total_agents": len(self.message_queues),
                "total_topics": len(self.topic_queues),
                "history_size": len(self.message_history),
            }

    async def get_message_history(
        self,
        limit: int = 100,
        agent_id: str | None = None,
        topic: str | None = None,
    ) -> list[Message]:
        """
        Get message history with optional filtering.

        Args:
            limit: Maximum number of messages to return
            agent_id: Filter by agent ID
            topic: Filter by topic

        Returns:
            List of messages
        """
        async with self._lock:
            messages = self.message_history[-limit:]

            if agent_id:
                messages = [
                    m for m in messages
                    if m.from_agent == agent_id or m.to_agent == agent_id
                ]

            if topic:
                messages = [m for m in messages if m.topic == topic]

            return messages

    async def clear_expired_messages(self) -> int:
        """
        Remove expired messages from all queues.

        Returns:
            Number of messages removed
        """
        removed = 0

        async with self._queue_lock:
            # Clear from direct queues
            for queue in self.message_queues.values():
                original_size = queue.size()
                queue.messages = [
                    (rank, counter, msg) for rank, counter, msg in queue.messages
                    if not msg.is_expired()
                ]
                removed += original_size - queue.size()

            # Clear from broadcast queue
            original_size = self.broadcast_queue.size()
            self.broadcast_queue.messages = [
                (rank, counter, msg) for rank, counter, msg in self.broadcast_queue.messages
                if not msg.is_expired()
            ]
            removed += original_size - self.broadcast_queue.size()

            # Clear from topic queues
            for queue in self.topic_queues.values():
                original_size = queue.size()
                queue.messages = [
                    (rank, counter, msg) for rank, counter, msg in queue.messages
                    if not msg.is_expired()
                ]
                removed += original_size - queue.size()

        self.stats["expired_messages"] += removed
        logger.info(f"Cleared {removed} expired messages")

        return removed

    async def _add_to_history(self, message: Message) -> None:
        """Add message to history."""
        if not self.enable_persistence:
            return

        async with self._lock:
            self.message_history.append(message)

            # Trim history if too large
            if len(self.message_history) > self.max_history_size:
                self.message_history = self.message_history[-self.max_history_size:]

    async def _call_handlers(self, agent_id: str, message: Message) -> None:
        """Call registered handlers for an agent."""
        handlers = self.message_handlers.get(agent_id, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                logger.error(f"Error calling handler for {agent_id}: {e}", exc_info=True)

    async def _call_topic_handlers(self, topic: str, message: Message) -> None:
        """Call registered handlers for a topic."""
        handlers = self.topic_handlers.get(topic, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                logger.error(f"Error calling topic handler for {topic}: {e}", exc_info=True)

    async def shutdown(self) -> None:
        """Shutdown the communication bus."""
        async with self._lock:
            self.message_queues.clear()
            self.broadcast_queue.clear()
            self.topic_queues.clear()
            self.message_history.clear()

        logger.info("AgentCommunicationBus shutdown complete")
