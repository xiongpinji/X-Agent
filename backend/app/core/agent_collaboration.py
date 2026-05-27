"""Multi-agent collaboration system with Redis persistence and load balancing."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable
from uuid import uuid4

import redis.asyncio as redis


class MessageType(str, Enum):
    """Types of messages between agents."""
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    STATUS_UPDATE = "status_update"
    ERROR_REPORT = "error_report"
    HEARTBEAT = "heartbeat"


class AgentStatus(str, Enum):
    """Status of an agent."""
    IDLE = "idle"
    BUSY = "busy"
    FAILED = "failed"
    OFFLINE = "offline"


@dataclass
class AgentMessage:
    """Message between agents."""
    id: str = field(default_factory=lambda: str(uuid4()))
    from_agent: str = ""
    to_agent: str = ""
    message_type: MessageType = MessageType.TASK_REQUEST
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    priority: int = 0  # Higher = more important
    retry_count: int = 0
    max_retries: int = 3

    def to_json(self) -> str:
        """Convert message to JSON."""
        data = asdict(self)
        data["message_type"] = self.message_type.value
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str) -> AgentMessage:
        """Create message from JSON."""
        data = json.loads(json_str)
        data["message_type"] = MessageType(data["message_type"])
        return cls(**data)


@dataclass
class AgentInfo:
    """Information about an agent."""
    agent_id: str
    status: AgentStatus = AgentStatus.IDLE
    load: float = 0.0  # 0-1, current workload
    capacity: int = 10  # Max concurrent tasks
    active_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    last_heartbeat: float = field(default_factory=time.time)

    def is_available(self) -> bool:
        """Check if agent is available for new tasks."""
        return (
            self.status == AgentStatus.IDLE
            and self.active_tasks < self.capacity
            and self.load < 0.8
        )

    def get_availability_score(self) -> float:
        """Get availability score (0-1, higher is better)."""
        if self.status != AgentStatus.IDLE:
            return 0.0
        return 1.0 - (self.load + self.active_tasks / self.capacity) / 2


class AgentCollaboration:
    """Multi-agent collaboration system with Redis persistence."""

    def __init__(
        self,
        redis_url: str = "redis://localhost",
        message_queue_prefix: str = "agent:messages",
        agent_registry_key: str = "agent:registry",
        heartbeat_timeout: float = 30.0,
    ):
        """Initialize agent collaboration system.

        Args:
            redis_url: Redis connection URL
            message_queue_prefix: Prefix for message queues
            agent_registry_key: Key for agent registry
            heartbeat_timeout: Timeout for agent heartbeat (seconds)
        """
        self.redis_url = redis_url
        self.message_queue_prefix = message_queue_prefix
        self.agent_registry_key = agent_registry_key
        self.heartbeat_timeout = heartbeat_timeout
        self.redis: redis.Redis | None = None
        self._local_agent_info: dict[str, AgentInfo] = {}
        self._message_handlers: dict[MessageType, Callable] = {}

    async def connect(self) -> None:
        """Connect to Redis."""
        self.redis = await redis.from_url(self.redis_url)

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()

    async def register_agent(self, agent_id: str, capacity: int = 10) -> AgentInfo:
        """Register an agent in the system.

        Args:
            agent_id: Unique agent identifier
            capacity: Maximum concurrent tasks

        Returns:
            Agent information
        """
        if not self.redis:
            await self.connect()

        agent_info = AgentInfo(
            agent_id=agent_id,
            capacity=capacity,
            last_heartbeat=time.time(),
        )

        self._local_agent_info[agent_id] = agent_info

        # Store in Redis
        await self.redis.hset(
            self.agent_registry_key,
            agent_id,
            json.dumps(asdict(agent_info), default=str),
        )

        # Create message queue for this agent
        await self.redis.delete(f"{self.message_queue_prefix}:{agent_id}:inbox")

        return agent_info

    async def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent from the system.

        Args:
            agent_id: Agent identifier
        """
        if not self.redis:
            return

        await self.redis.hdel(self.agent_registry_key, agent_id)
        self._local_agent_info.pop(agent_id, None)

    async def send_message(self, message: AgentMessage) -> bool:
        """Send a message from one agent to another.

        Args:
            message: Message to send

        Returns:
            True if message was sent successfully
        """
        if not self.redis:
            await self.connect()

        try:
            # Store message in Redis queue
            queue_key = f"{self.message_queue_prefix}:{message.to_agent}:inbox"
            await self.redis.lpush(queue_key, message.to_json())

            # Set expiration for message queue
            await self.redis.expire(queue_key, 86400)  # 24 hours

            # Publish to channel for real-time notification
            await self.redis.publish(
                f"{self.message_queue_prefix}:{message.to_agent}",
                message.to_json(),
            )

            return True
        except Exception as e:
            print(f"Failed to send message: {e}")
            return False

    async def receive_messages(
        self,
        agent_id: str,
        limit: int = 10,
    ) -> list[AgentMessage]:
        """Receive messages for an agent.

        Args:
            agent_id: Agent identifier
            limit: Maximum number of messages to retrieve

        Returns:
            List of messages
        """
        if not self.redis:
            await self.connect()

        queue_key = f"{self.message_queue_prefix}:{agent_id}:inbox"
        messages_json = await self.redis.lrange(queue_key, 0, limit - 1)

        messages = []
        for msg_json in messages_json:
            try:
                message = AgentMessage.from_json(msg_json)
                messages.append(message)
            except Exception as e:
                print(f"Failed to parse message: {e}")

        return messages

    async def acknowledge_message(self, agent_id: str, message_id: str) -> bool:
        """Acknowledge receipt of a message.

        Args:
            agent_id: Agent identifier
            message_id: Message identifier

        Returns:
            True if acknowledged successfully
        """
        if not self.redis:
            return False

        queue_key = f"{self.message_queue_prefix}:{agent_id}:inbox"
        messages_json = await self.redis.lrange(queue_key, 0, -1)

        for i, msg_json in enumerate(messages_json):
            try:
                message = AgentMessage.from_json(msg_json)
                if message.id == message_id:
                    await self.redis.lrem(queue_key, 1, msg_json)
                    return True
            except Exception:
                continue

        return False

    async def update_agent_status(
        self,
        agent_id: str,
        status: AgentStatus,
        load: float = 0.0,
        active_tasks: int = 0,
    ) -> None:
        """Update agent status and metrics.

        Args:
            agent_id: Agent identifier
            status: New agent status
            load: Current workload (0-1)
            active_tasks: Number of active tasks
        """
        if not self.redis:
            await self.connect()

        if agent_id in self._local_agent_info:
            agent_info = self._local_agent_info[agent_id]
            agent_info.status = status
            agent_info.load = load
            agent_info.active_tasks = active_tasks
            agent_info.last_heartbeat = time.time()

            # Update in Redis
            await self.redis.hset(
                self.agent_registry_key,
                agent_id,
                json.dumps(asdict(agent_info), default=str),
            )

    async def get_available_agents(self) -> list[AgentInfo]:
        """Get list of available agents for task assignment.

        Returns:
            List of available agents sorted by availability score
        """
        if not self.redis:
            await self.connect()

        # Get all agents from registry
        agents_data = await self.redis.hgetall(self.agent_registry_key)
        available_agents = []

        for agent_id, agent_json in agents_data.items():
            try:
                agent_data = json.loads(agent_json)
                agent_info = AgentInfo(**agent_data)

                # Check if agent is still alive
                if time.time() - agent_info.last_heartbeat > self.heartbeat_timeout:
                    agent_info.status = AgentStatus.OFFLINE
                    continue

                if agent_info.is_available():
                    available_agents.append(agent_info)
            except Exception:
                continue

        # Sort by availability score
        available_agents.sort(
            key=lambda a: a.get_availability_score(),
            reverse=True,
        )

        return available_agents

    async def assign_task(
        self,
        task_payload: dict[str, Any],
        priority: int = 0,
    ) -> str | None:
        """Assign a task to the best available agent.

        Args:
            task_payload: Task payload
            priority: Task priority

        Returns:
            Agent ID if task was assigned, None otherwise
        """
        available_agents = await self.get_available_agents()

        if not available_agents:
            return None

        # Assign to agent with highest availability score
        best_agent = available_agents[0]

        message = AgentMessage(
            from_agent="system",
            to_agent=best_agent.agent_id,
            message_type=MessageType.TASK_REQUEST,
            payload=task_payload,
            priority=priority,
        )

        success = await self.send_message(message)
        return best_agent.agent_id if success else None

    async def handle_message(
        self,
        message: AgentMessage,
        handler: Callable[[AgentMessage], Any],
    ) -> None:
        """Register a handler for a message type.

        Args:
            message: Message to handle
            handler: Handler function
        """
        self._message_handlers[message.message_type] = handler

    async def process_messages(self, agent_id: str) -> None:
        """Process all pending messages for an agent.

        Args:
            agent_id: Agent identifier
        """
        messages = await self.receive_messages(agent_id)

        for message in messages:
            handler = self._message_handlers.get(message.message_type)
            if handler:
                try:
                    await handler(message)
                    await self.acknowledge_message(agent_id, message.id)
                except Exception as e:
                    print(f"Error processing message: {e}")

    async def get_agent_stats(self) -> dict[str, Any]:
        """Get statistics about all agents.

        Returns:
            Dictionary with agent statistics
        """
        if not self.redis:
            await self.connect()

        agents_data = await self.redis.hgetall(self.agent_registry_key)
        agents = []

        for agent_id, agent_json in agents_data.items():
            try:
                agent_data = json.loads(agent_json)
                agents.append(agent_data)
            except Exception:
                continue

        if not agents:
            return {
                "total_agents": 0,
                "available_agents": 0,
                "avg_load": 0.0,
            }

        available = sum(1 for a in agents if a.get("status") == "idle")
        avg_load = sum(a.get("load", 0) for a in agents) / len(agents)

        return {
            "total_agents": len(agents),
            "available_agents": available,
            "avg_load": avg_load,
            "total_completed_tasks": sum(a.get("completed_tasks", 0) for a in agents),
            "total_failed_tasks": sum(a.get("failed_tasks", 0) for a in agents),
        }


# Global instance
agent_collaboration = AgentCollaboration()
