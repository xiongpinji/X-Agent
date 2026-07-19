"""Agent Communication Bus - Enables inter-agent messaging and coordination."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import StrEnum
from typing import Any, Callable, Optional
from collections import defaultdict
from heapq import heappush, heappop

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
    to_agent: Optional[str] = None
    message_type: MessageType = MessageType.DIRECT
    topic: Optional[str] = None
    content: Any = None
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    ttl_seconds: Optional[int] = None
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

    def put(self, message: Message) -> None:
        """Add message to queue."""
        # 堆排序键必须把优先级放在首位，counter 仅作同优先级下的
        # 稳定 FIFO 裁决项。此前误用 (counter, message)，counter 永不
        # 相等，message.__lt__ 从不被调用，优先级被完全忽略。
        priority_rank = {
            MessagePriority.CRITICAL: 0,
            MessagePriority.HIGH: 1,
            MessagePriority.NORMAL: 2,
            MessagePriority.LOW: 3,
        }[message.priority]
        heappush(self.messages, (priority_rank, self._counter, message))
        self._counter += 1

    def get(self) -> Optional[Message]:
        """Get highest priority message from queue."""
        if not self.messages:
            return None
        _, _, message = heappop(self.messages)
        return message

    def size(self) -> int:
        """Get queue size."""
        return len(self.messages)

    def clear(self) -> None:
        """Clear all messages."""
        self.messages.clear()
        self._counter = 0


@dataclass
class RPCRequest:
    """Represents an RPC request."""

    rpc_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    from_agent: str = ""
    to_agent: str = ""
    method: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float = 30.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class RPCResponse:
    """Represents an RPC response."""

    rpc_id: str
    result: Any = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    duration_ms: float = 0.0


class AgentCommunicationBus:
    """Central message bus for inter-agent communication.

    Supports:
    - Direct point-to-point messaging
    - Broadcast messaging to all agents
    - Topic-based pub/sub
    - Message prioritization
    - Message expiration (TTL)
    - Delivery tracking
    - RPC calls between agents
    - Event publishing and subscription
    """

    def __init__(self, enable_persistence: bool = False, max_queue_size: int = 10000) -> None:
        """Initialize the communication bus.

        Args:
            enable_persistence: Enable message persistence
            max_queue_size: Maximum queue size
        """
        self._enable_persistence = enable_persistence
        self._max_queue_size = max_queue_size

        # Message queues
        self._direct_queues: dict[str, MessageQueue] = defaultdict(MessageQueue)
        self._broadcast_queue = MessageQueue()
        self._topic_queues: dict[str, MessageQueue] = defaultdict(MessageQueue)

        # Subscriptions
        self._topic_subscribers: dict[str, set[str]] = defaultdict(set)
        self._broadcast_subscribers: set[str] = set()

        # RPC
        self._rpc_responses: dict[str, RPCResponse] = {}
        self._rpc_handlers: dict[str, Callable] = {}

        # Events
        self._event_handlers: dict[str, list[Callable]] = defaultdict(list)

        # Message history
        self._message_history: list[Message] = []

        # Lock for thread safety
        self._lock = asyncio.Lock()

    async def send_direct(
        self,
        from_agent: str,
        to_agent: str,
        content: Any,
        priority: MessagePriority = MessagePriority.NORMAL,
        correlation_id: Optional[str] = None,
        reply_to: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ) -> str:
        """Send a direct message to an agent.

        Args:
            from_agent: Sender agent ID
            to_agent: Recipient agent ID
            content: Message content
            priority: Message priority
            correlation_id: Correlation ID for tracking
            reply_to: ID of message being replied to
            ttl_seconds: Time-to-live for message

        Returns:
            Message ID
        """
        message = Message(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=MessageType.DIRECT,
            content=content,
            priority=priority,
            correlation_id=correlation_id,
            reply_to=reply_to,
            ttl_seconds=ttl_seconds,
        )

        async with self._lock:
            self._direct_queues[to_agent].put(message)
            self._message_history.append(message)

            if len(self._message_history) > self._max_queue_size:
                self._message_history.pop(0)

        logger.debug(f"Direct message sent from {from_agent} to {to_agent}: {message.message_id}")
        return message.message_id

    async def send_broadcast(
        self,
        from_agent: str,
        content: Any,
        priority: MessagePriority = MessagePriority.NORMAL,
        ttl_seconds: Optional[int] = None,
    ) -> str:
        """Send a broadcast message to all agents.

        Args:
            from_agent: Sender agent ID
            content: Message content
            priority: Message priority
            ttl_seconds: Time-to-live for message

        Returns:
            Message ID
        """
        message = Message(
            from_agent=from_agent,
            message_type=MessageType.BROADCAST,
            content=content,
            priority=priority,
            ttl_seconds=ttl_seconds,
        )

        async with self._lock:
            self._broadcast_queue.put(message)
            self._message_history.append(message)

            if len(self._message_history) > self._max_queue_size:
                self._message_history.pop(0)

        logger.debug(f"Broadcast message sent from {from_agent}: {message.message_id}")
        return message.message_id

    async def publish_topic(
        self,
        from_agent: str,
        topic: str,
        content: Any,
        priority: MessagePriority = MessagePriority.NORMAL,
        ttl_seconds: Optional[int] = None,
    ) -> str:
        """Publish a message to a topic.

        Args:
            from_agent: Publisher agent ID
            topic: Topic name
            content: Message content
            priority: Message priority
            ttl_seconds: Time-to-live for message

        Returns:
            Message ID
        """
        message = Message(
            from_agent=from_agent,
            message_type=MessageType.TOPIC,
            topic=topic,
            content=content,
            priority=priority,
            ttl_seconds=ttl_seconds,
        )

        async with self._lock:
            self._topic_queues[topic].put(message)
            self._message_history.append(message)

            if len(self._message_history) > self._max_queue_size:
                self._message_history.pop(0)

        logger.debug(f"Topic message published to {topic}: {message.message_id}")
        return message.message_id

    async def subscribe_topic(self, agent_id: str, topic: str) -> None:
        """Subscribe an agent to a topic.

        Args:
            agent_id: Agent ID
            topic: Topic name
        """
        async with self._lock:
            self._topic_subscribers[topic].add(agent_id)

        logger.debug(f"Agent {agent_id} subscribed to topic {topic}")

    async def unsubscribe_topic(self, agent_id: str, topic: str) -> None:
        """Unsubscribe an agent from a topic.

        Args:
            agent_id: Agent ID
            topic: Topic name
        """
        async with self._lock:
            self._topic_subscribers[topic].discard(agent_id)

        logger.debug(f"Agent {agent_id} unsubscribed from topic {topic}")

    async def subscribe_broadcast(self, agent_id: str) -> None:
        """Subscribe an agent to broadcast messages.

        Args:
            agent_id: Agent ID
        """
        async with self._lock:
            self._broadcast_subscribers.add(agent_id)

        logger.debug(f"Agent {agent_id} subscribed to broadcast")

    async def unsubscribe_broadcast(self, agent_id: str) -> None:
        """Unsubscribe an agent from broadcast messages.

        Args:
            agent_id: Agent ID
        """
        async with self._lock:
            self._broadcast_subscribers.discard(agent_id)

        logger.debug(f"Agent {agent_id} unsubscribed from broadcast")

    async def receive_direct(self, agent_id: str, timeout_seconds: float = 5.0) -> Optional[Message]:
        """Receive a direct message for an agent.

        Args:
            agent_id: Agent ID
            timeout_seconds: Timeout for receiving

        Returns:
            Message or None if timeout
        """
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            async with self._lock:
                message = self._direct_queues[agent_id].get()

            if message:
                if not message.is_expired():
                    message.delivered = True
                    return message
                else:
                    logger.debug(f"Message {message.message_id} expired")
                    continue

            await asyncio.sleep(0.1)

        return None

    async def receive_broadcast(self, agent_id: str, timeout_seconds: float = 5.0) -> Optional[Message]:
        """Receive a broadcast message.

        Args:
            agent_id: Agent ID
            timeout_seconds: Timeout for receiving

        Returns:
            Message or None if timeout
        """
        if agent_id not in self._broadcast_subscribers:
            return None

        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            async with self._lock:
                message = self._broadcast_queue.get()

            if message:
                if not message.is_expired():
                    message.delivered = True
                    return message
                else:
                    logger.debug(f"Message {message.message_id} expired")
                    continue

            await asyncio.sleep(0.1)

        return None

    async def receive_topic(self, agent_id: str, topic: str, timeout_seconds: float = 5.0) -> Optional[Message]:
        """Receive a topic message.

        Args:
            agent_id: Agent ID
            topic: Topic name
            timeout_seconds: Timeout for receiving

        Returns:
            Message or None if timeout
        """
        if agent_id not in self._topic_subscribers.get(topic, set()):
            return None

        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            async with self._lock:
                message = self._topic_queues[topic].get()

            if message:
                if not message.is_expired():
                    message.delivered = True
                    return message
                else:
                    logger.debug(f"Message {message.message_id} expired")
                    continue

            await asyncio.sleep(0.1)

        return None

    async def call_rpc(
        self,
        from_agent: str,
        to_agent: str,
        method: str,
        params: dict[str, Any],
        timeout_seconds: float = 30.0,
    ) -> RPCResponse:
        """Make an RPC call to another agent.

        Args:
            from_agent: Caller agent ID
            to_agent: Callee agent ID
            method: Method name
            params: Method parameters
            timeout_seconds: Timeout for RPC call

        Returns:
            RPCResponse with result or error
        """
        request = RPCRequest(
            from_agent=from_agent,
            to_agent=to_agent,
            method=method,
            params=params,
            timeout_seconds=timeout_seconds,
        )

        # Send RPC request as direct message
        await self.send_direct(
            from_agent=from_agent,
            to_agent=to_agent,
            content={"type": "rpc_request", "request": request},
            priority=MessagePriority.HIGH,
            correlation_id=request.rpc_id,
        )

        # Wait for response
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            if request.rpc_id in self._rpc_responses:
                response = self._rpc_responses.pop(request.rpc_id)
                return response

            await asyncio.sleep(0.1)

        return RPCResponse(
            rpc_id=request.rpc_id,
            error="RPC call timed out",
            error_type="TimeoutError",
        )

    async def register_rpc_handler(self, method: str, handler: Callable) -> None:
        """Register an RPC handler for a method.

        Args:
            method: Method name
            handler: Handler function
        """
        self._rpc_handlers[method] = handler
        logger.debug(f"RPC handler registered for method {method}")

    async def handle_rpc_request(self, request: RPCRequest) -> RPCResponse:
        """Handle an RPC request.

        Args:
            request: RPC request

        Returns:
            RPC response
        """
        handler = self._rpc_handlers.get(request.method)
        if not handler:
            return RPCResponse(
                rpc_id=request.rpc_id,
                error=f"Method {request.method} not found",
                error_type="MethodNotFoundError",
            )

        try:
            start_time = time.time()
            result = await handler(**request.params) if asyncio.iscoroutinefunction(handler) else handler(**request.params)
            duration_ms = (time.time() - start_time) * 1000

            response = RPCResponse(
                rpc_id=request.rpc_id,
                result=result,
                duration_ms=duration_ms,
            )

            # Store response for caller
            self._rpc_responses[request.rpc_id] = response
            return response

        except Exception as e:
            return RPCResponse(
                rpc_id=request.rpc_id,
                error=str(e),
                error_type=type(e).__name__,
            )

    async def publish_event(
        self,
        from_agent: str,
        event_type: str,
        event_data: dict[str, Any],
    ) -> None:
        """Publish an event.

        Args:
            from_agent: Publisher agent ID
            event_type: Event type
            event_data: Event data
        """
        message = Message(
            from_agent=from_agent,
            message_type=MessageType.EVENT,
            topic=event_type,
            content=event_data,
        )

        # Call event handlers
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                logger.error(f"Error in event handler for {event_type}: {e}")

    async def subscribe_event(self, event_type: str, handler: Callable) -> None:
        """Subscribe to an event.

        Args:
            event_type: Event type
            handler: Handler function
        """
        self._event_handlers[event_type].append(handler)
        logger.debug(f"Event handler registered for {event_type}")

    async def get_message_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get message history.

        Args:
            limit: Maximum number of messages to return

        Returns:
            List of messages
        """
        async with self._lock:
            messages = self._message_history[-limit:]
            return [msg.to_dict() for msg in messages]

    async def get_stats(self) -> dict[str, Any]:
        """Get bus statistics.

        Returns:
            Dictionary with statistics
        """
        async with self._lock:
            return {
                "total_messages": len(self._message_history),
                "direct_queues": len(self._direct_queues),
                "broadcast_queue_size": self._broadcast_queue.size(),
                "topic_queues": len(self._topic_queues),
                "topic_subscribers": {topic: len(subs) for topic, subs in self._topic_subscribers.items()},
                "broadcast_subscribers": len(self._broadcast_subscribers),
                "rpc_handlers": len(self._rpc_handlers),
                "event_handlers": len(self._event_handlers),
            }

    async def clear(self) -> None:
        """Clear all messages and queues."""
        async with self._lock:
            self._direct_queues.clear()
            self._broadcast_queue.clear()
            self._topic_queues.clear()
            self._message_history.clear()
            self._rpc_responses.clear()

        logger.info("Communication bus cleared")
