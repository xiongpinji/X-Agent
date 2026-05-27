"""Communication protocol for inter-agent messaging.

Defines message formats, serialization, and routing for synchronous and
asynchronous communication between agents.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Callable, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """Types of messages in the collaboration protocol."""

    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    ACK = "ack"
    ERROR = "error"


@dataclass
class Message:
    """Base message class for inter-agent communication."""

    message_id: str = field(default_factory=lambda: str(uuid4()))
    message_type: MessageType = MessageType.REQUEST
    sender_id: str = ""
    receiver_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize message to dictionary."""
        data = asdict(self)
        data["message_type"] = self.message_type.value
        data["timestamp"] = self.timestamp.isoformat()
        return data

    def to_json(self) -> str:
        """Serialize message to JSON string."""
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        """Deserialize message from dictionary."""
        data = dict(data)
        if isinstance(data.get("message_type"), str):
            data["message_type"] = MessageType(data["message_type"])
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> Message:
        """Deserialize message from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class Request(Message):
    """Request message for task execution."""

    action: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    timeout: float = 30.0
    priority: int = 0

    def __post_init__(self) -> None:
        self.message_type = MessageType.REQUEST
        if not self.correlation_id:
            self.correlation_id = self.message_id


@dataclass
class Response(Message):
    """Response message with results."""

    status: str = "success"  # success, error, timeout
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0

    def __post_init__(self) -> None:
        self.message_type = MessageType.RESPONSE


@dataclass
class Event(Message):
    """Event message for notifications."""

    event_type: str = ""
    event_data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.message_type = MessageType.EVENT


class MessageRouter:
    """Routes messages between agents with support for sync and async communication."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable]] = {}
        self._pending_responses: dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()
        self._message_queue: asyncio.Queue = asyncio.Queue()

    async def register_handler(
        self,
        agent_id: str,
        handler: Callable[[Message], Any],
    ) -> None:
        """Register a message handler for an agent.

        Args:
            agent_id: ID of the agent
            handler: Async or sync callable that processes messages
        """
        async with self._lock:
            if agent_id not in self._handlers:
                self._handlers[agent_id] = []
            self._handlers[agent_id].append(handler)

    async def send_message(
        self,
        message: Message,
        wait_response: bool = False,
        timeout: float = 30.0,
    ) -> Optional[Response]:
        """Send a message to an agent.

        Args:
            message: Message to send
            wait_response: Whether to wait for response
            timeout: Timeout for waiting response

        Returns:
            Response message if wait_response is True, else None
        """
        await self._message_queue.put(message)

        handlers = self._handlers.get(message.receiver_id, [])
        if not handlers:
            logger.warning(f"No handlers registered for agent {message.receiver_id}")
            return None

        if wait_response:
            future: asyncio.Future = asyncio.Future()
            self._pending_responses[message.message_id] = future

            try:
                for handler in handlers:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(message)
                    else:
                        handler(message)

                response = await asyncio.wait_for(future, timeout=timeout)
                return response
            except asyncio.TimeoutError:
                logger.error(f"Timeout waiting for response to message {message.message_id}")
                return None
            finally:
                self._pending_responses.pop(message.message_id, None)
        else:
            for handler in handlers:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            return None

    async def send_response(
        self,
        request_message: Message,
        result: Any,
        status: str = "success",
        error: Optional[str] = None,
    ) -> None:
        """Send a response to a request message.

        Args:
            request_message: Original request message
            result: Result data
            status: Response status
            error: Error message if any
        """
        response = Response(
            sender_id=request_message.receiver_id,
            receiver_id=request_message.sender_id,
            correlation_id=request_message.correlation_id or request_message.message_id,
            reply_to=request_message.message_id,
            result=result,
            status=status,
            error=error,
        )

        if request_message.message_id in self._pending_responses:
            future = self._pending_responses[request_message.message_id]
            if not future.done():
                future.set_result(response)

        await self._message_queue.put(response)

    async def broadcast_event(
        self,
        sender_id: str,
        event_type: str,
        event_data: dict[str, Any],
        target_agents: Optional[list[str]] = None,
    ) -> None:
        """Broadcast an event to multiple agents.

        Args:
            sender_id: ID of the sender
            event_type: Type of event
            event_data: Event data
            target_agents: List of target agent IDs, None for all
        """
        event = Event(
            sender_id=sender_id,
            event_type=event_type,
            event_data=event_data,
        )

        if target_agents:
            for agent_id in target_agents:
                event.receiver_id = agent_id
                await self._message_queue.put(event)
        else:
            for agent_id in self._handlers.keys():
                event.receiver_id = agent_id
                await self._message_queue.put(event)

    async def get_message_queue(self) -> asyncio.Queue:
        """Get the message queue for processing."""
        return self._message_queue

    async def get_pending_messages(self, agent_id: str) -> list[Message]:
        """Get pending messages for an agent."""
        messages = []
        temp_messages = []

        while not self._message_queue.empty():
            try:
                msg = self._message_queue.get_nowait()
                if msg.receiver_id == agent_id:
                    messages.append(msg)
                else:
                    temp_messages.append(msg)
            except asyncio.QueueEmpty:
                break

        for msg in temp_messages:
            await self._message_queue.put(msg)

        return messages

    def get_stats(self) -> dict[str, Any]:
        """Get router statistics."""
        return {
            "registered_agents": len(self._handlers),
            "pending_responses": len(self._pending_responses),
            "queue_size": self._message_queue.qsize(),
        }
