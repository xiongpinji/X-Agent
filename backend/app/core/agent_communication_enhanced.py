"""
Agent通信协议 - 支持异步消息传递、状态同步、协作管理
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Callable, Awaitable
from collections import defaultdict

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """消息类型"""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    STATE_SYNC = "state_sync"
    TASK_DISPATCH = "task_dispatch"
    TASK_RESULT = "task_result"


class MessagePriority(str, Enum):
    """消息优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Message:
    """通信消息"""
    message_id: str
    message_type: MessageType
    sender_id: str
    receiver_id: str
    content: dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: float = field(default_factory=time.time)
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    ttl_seconds: int = 300
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """检查消息是否过期"""
        return time.time() - self.timestamp > self.ttl_seconds

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "message_id": self.message_id,
            "message_type": self.message_type.value,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "content": self.content,
            "priority": self.priority.value,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to,
            "ttl_seconds": self.ttl_seconds,
            "metadata": self.metadata,
        }


@dataclass
class AgentState:
    """Agent状态"""
    agent_id: str
    status: str  # idle, busy, error, offline
    current_task: Optional[str] = None
    task_progress: float = 0.0
    last_heartbeat: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "agent_id": self.agent_id,
            "status": self.status,
            "current_task": self.current_task,
            "task_progress": self.task_progress,
            "last_heartbeat": self.last_heartbeat,
            "metadata": self.metadata,
        }


class MessageQueue:
    """消息队列"""

    def __init__(self, max_size: int = 1000):
        """初始化消息队列"""
        self.max_size = max_size
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_size)
        self._messages: dict[str, Message] = {}

    async def put(self, message: Message) -> bool:
        """放入消息"""
        if len(self._messages) >= self.max_size:
            logger.warning("Message queue is full")
            return False

        try:
            # 根据优先级排序
            priority_value = {
                MessagePriority.CRITICAL: 0,
                MessagePriority.HIGH: 1,
                MessagePriority.NORMAL: 2,
                MessagePriority.LOW: 3,
            }[message.priority]

            await self._queue.put((priority_value, message.timestamp, message))
            self._messages[message.message_id] = message
            return True
        except asyncio.QueueFull:
            logger.error("Failed to put message in queue")
            return False

    async def get(self, timeout_seconds: Optional[float] = None) -> Optional[Message]:
        """获取消息"""
        try:
            _, _, message = await asyncio.wait_for(
                self._queue.get(),
                timeout=timeout_seconds
            )
            self._messages.pop(message.message_id, None)
            return message
        except asyncio.TimeoutError:
            return None

    def get_message(self, message_id: str) -> Optional[Message]:
        """获取特定消息"""
        return self._messages.get(message_id)

    def size(self) -> int:
        """获取队列大小"""
        return len(self._messages)


class AgentCommunicationBus:
    """Agent通信总线"""

    def __init__(self):
        """初始化通信总线"""
        self.agent_queues: dict[str, MessageQueue] = defaultdict(lambda: MessageQueue())
        self.agent_states: dict[str, AgentState] = {}
        self.message_handlers: dict[MessageType, list[Callable]] = defaultdict(list)
        self._running = False
        self._tasks: dict[str, asyncio.Task] = {}

    def register_agent(self, agent_id: str) -> None:
        """注册Agent"""
        if agent_id not in self.agent_states:
            self.agent_states[agent_id] = AgentState(agent_id=agent_id, status="idle")
            logger.info(f"Registered agent: {agent_id}")

    def unregister_agent(self, agent_id: str) -> None:
        """注销Agent"""
        if agent_id in self.agent_states:
            del self.agent_states[agent_id]
            if agent_id in self.agent_queues:
                del self.agent_queues[agent_id]
            logger.info(f"Unregistered agent: {agent_id}")

    def register_handler(
        self,
        message_type: MessageType,
        handler: Callable[[Message], Awaitable[None]]
    ) -> None:
        """注册消息处理器"""
        self.message_handlers[message_type].append(handler)

    async def send_message(self, message: Message) -> bool:
        """发送消息"""
        if message.receiver_id not in self.agent_states:
            logger.warning(f"Receiver agent not found: {message.receiver_id}")
            return False

        queue = self.agent_queues[message.receiver_id]
        success = await queue.put(message)

        if success:
            logger.debug(f"Message sent: {message.message_id} from {message.sender_id} to {message.receiver_id}")
        else:
            logger.error(f"Failed to send message: {message.message_id}")

        return success

    async def receive_message(
        self,
        agent_id: str,
        timeout_seconds: Optional[float] = None
    ) -> Optional[Message]:
        """接收消息"""
        if agent_id not in self.agent_states:
            logger.warning(f"Agent not found: {agent_id}")
            return None

        queue = self.agent_queues[agent_id]
        message = await queue.get(timeout_seconds)

        if message:
            logger.debug(f"Message received: {message.message_id} by {agent_id}")

        return message

    async def broadcast_message(
        self,
        message: Message,
        exclude_agent_id: Optional[str] = None
    ) -> int:
        """广播消息"""
        count = 0
        for agent_id in self.agent_states.keys():
            if agent_id != exclude_agent_id:
                message.receiver_id = agent_id
                if await self.send_message(message):
                    count += 1

        logger.info(f"Broadcast message to {count} agents")
        return count

    def update_agent_state(
        self,
        agent_id: str,
        status: Optional[str] = None,
        current_task: Optional[str] = None,
        task_progress: Optional[float] = None,
        metadata: Optional[dict[str, Any]] = None
    ) -> bool:
        """更新Agent状态"""
        if agent_id not in self.agent_states:
            return False

        state = self.agent_states[agent_id]
        if status is not None:
            state.status = status
        if current_task is not None:
            state.current_task = current_task
        if task_progress is not None:
            state.task_progress = task_progress
        if metadata is not None:
            state.metadata.update(metadata)

        state.last_heartbeat = time.time()
        return True

    def get_agent_state(self, agent_id: str) -> Optional[AgentState]:
        """获取Agent状态"""
        return self.agent_states.get(agent_id)

    def get_all_agent_states(self) -> dict[str, AgentState]:
        """获取所有Agent状态"""
        return dict(self.agent_states)

    async def handle_message(self, message: Message) -> None:
        """处理消息"""
        handlers = self.message_handlers.get(message.message_type, [])

        for handler in handlers:
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"Error handling message: {e}")

    async def start(self) -> None:
        """启动通信总线"""
        self._running = True
        logger.info("Communication bus started")

    async def stop(self) -> None:
        """停止通信总线"""
        self._running = False
        logger.info("Communication bus stopped")

    def get_bus_status(self) -> dict[str, Any]:
        """获取总线状态"""
        return {
            "running": self._running,
            "total_agents": len(self.agent_states),
            "agent_states": {
                agent_id: state.to_dict()
                for agent_id, state in self.agent_states.items()
            },
            "queue_sizes": {
                agent_id: queue.size()
                for agent_id, queue in self.agent_queues.items()
            },
        }


class CollaborationCoordinator:
    """协作协调器"""

    def __init__(self, bus: AgentCommunicationBus):
        """初始化协调器"""
        self.bus = bus
        self.collaborations: dict[str, dict[str, Any]] = {}
        self.task_assignments: dict[str, dict[str, Any]] = {}

    async def create_collaboration(
        self,
        collaboration_id: str,
        agent_ids: list[str],
        task_description: str,
        metadata: Optional[dict[str, Any]] = None
    ) -> bool:
        """创建协作"""
        self.collaborations[collaboration_id] = {
            "collaboration_id": collaboration_id,
            "agent_ids": agent_ids,
            "task_description": task_description,
            "status": "active",
            "created_at": time.time(),
            "metadata": metadata or {},
        }

        logger.info(f"Created collaboration: {collaboration_id} with agents: {agent_ids}")
        return True

    async def assign_task(
        self,
        collaboration_id: str,
        agent_id: str,
        task_description: str,
        task_id: Optional[str] = None
    ) -> Optional[str]:
        """分配任务"""
        if task_id is None:
            task_id = str(uuid.uuid4())

        self.task_assignments[task_id] = {
            "task_id": task_id,
            "collaboration_id": collaboration_id,
            "agent_id": agent_id,
            "task_description": task_description,
            "status": "assigned",
            "created_at": time.time(),
        }

        # 发送任务分配消息
        message = Message(
            message_id=str(uuid.uuid4()),
            message_type=MessageType.TASK_DISPATCH,
            sender_id="coordinator",
            receiver_id=agent_id,
            content={
                "task_id": task_id,
                "collaboration_id": collaboration_id,
                "task_description": task_description,
            },
            priority=MessagePriority.HIGH,
        )

        await self.bus.send_message(message)
        logger.info(f"Assigned task {task_id} to agent {agent_id}")
        return task_id

    async def sync_state(self, collaboration_id: str) -> None:
        """同步协作状态"""
        collaboration = self.collaborations.get(collaboration_id)
        if not collaboration:
            return

        # 收集所有Agent的状态
        states = {}
        for agent_id in collaboration["agent_ids"]:
            state = self.bus.get_agent_state(agent_id)
            if state:
                states[agent_id] = state.to_dict()

        # 广播状态同步消息
        message = Message(
            message_id=str(uuid.uuid4()),
            message_type=MessageType.STATE_SYNC,
            sender_id="coordinator",
            receiver_id="",  # 将被广播覆盖
            content={
                "collaboration_id": collaboration_id,
                "states": states,
            },
            priority=MessagePriority.NORMAL,
        )

        await self.bus.broadcast_message(message)
        logger.debug(f"Synced state for collaboration: {collaboration_id}")

    def get_collaboration_status(self, collaboration_id: str) -> Optional[dict[str, Any]]:
        """获取协作状态"""
        collaboration = self.collaborations.get(collaboration_id)
        if not collaboration:
            return None

        # 收集任务状态
        tasks = [
            task for task in self.task_assignments.values()
            if task["collaboration_id"] == collaboration_id
        ]

        return {
            "collaboration_id": collaboration_id,
            "status": collaboration["status"],
            "agent_ids": collaboration["agent_ids"],
            "task_count": len(tasks),
            "tasks": tasks,
            "created_at": collaboration["created_at"],
        }


# 全局通信总线实例
_bus: Optional[AgentCommunicationBus] = None


def get_communication_bus() -> AgentCommunicationBus:
    """获取全局通信总线"""
    global _bus
    if _bus is None:
        _bus = AgentCommunicationBus()
    return _bus


def get_collaboration_coordinator() -> CollaborationCoordinator:
    """获取协作协调器"""
    bus = get_communication_bus()
    return CollaborationCoordinator(bus)
