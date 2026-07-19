"""Agent registry for discovery and capability management."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    """Status of an agent."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"


@dataclass
class AgentCapability:
    """Represents a capability that an agent can perform."""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    estimated_duration: float = 1.0  # seconds
    cost: float = 0.0
    tags: list[str] = field(default_factory=list)

    def matches(self, required_capability: str) -> bool:
        """Check if this capability matches a required capability."""
        return (
            self.name == required_capability
            or required_capability in self.tags
        )


@dataclass
class AgentInfo:
    """Information about an agent."""

    agent_id: str
    name: str
    agent_type: str  # e.g., "analyzer", "executor", "planner"
    status: AgentStatus = AgentStatus.HEALTHY
    capabilities: list[AgentCapability] = field(default_factory=list)
    location: str = "local"  # local or remote URL
    max_concurrent_tasks: int = 5
    current_load: int = 0
    registered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_available(self) -> bool:
        """Check if agent is available for new tasks."""
        return (
            self.status == AgentStatus.HEALTHY
            and self.current_load < self.max_concurrent_tasks
        )

    def get_load_percentage(self) -> float:
        """Get current load as percentage."""
        return (self.current_load / self.max_concurrent_tasks) * 100

    def is_healthy(self, heartbeat_timeout: float = 30.0) -> bool:
        """Check if agent is healthy based on heartbeat."""
        time_since_heartbeat = (datetime.now(UTC) - self.last_heartbeat).total_seconds()
        return time_since_heartbeat < heartbeat_timeout


class AgentRegistry:
    """Registry for agent discovery and capability management."""

    def __init__(self, heartbeat_timeout: float = 30.0) -> None:
        self._agents: dict[str, AgentInfo] = {}
        self._capabilities_index: dict[str, list[str]] = {}
        self._lock = asyncio.Lock()
        self.heartbeat_timeout = heartbeat_timeout

    async def register_agent(
        self,
        name: str,
        agent_type: str,
        capabilities: list[AgentCapability],
        location: str = "local",
        max_concurrent_tasks: int = 5,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AgentInfo:
        """Register a new agent.

        Args:
            name: Agent name
            agent_type: Type of agent
            capabilities: List of capabilities
            location: Agent location (local or remote URL)
            max_concurrent_tasks: Maximum concurrent tasks
            metadata: Additional metadata

        Returns:
            AgentInfo object
        """
        agent_id = str(uuid4())
        agent_info = AgentInfo(
            agent_id=agent_id,
            name=name,
            agent_type=agent_type,
            capabilities=capabilities,
            location=location,
            max_concurrent_tasks=max_concurrent_tasks,
            metadata=metadata or {},
        )

        async with self._lock:
            self._agents[agent_id] = agent_info
            for capability in capabilities:
                if capability.name not in self._capabilities_index:
                    self._capabilities_index[capability.name] = []
                self._capabilities_index[capability.name].append(agent_id)

        logger.info(f"Registered agent {agent_id} ({name}) with {len(capabilities)} capabilities")
        return agent_info

    async def unregister_agent(self, agent_id: str) -> bool:
        """Unregister an agent.

        Args:
            agent_id: ID of the agent

        Returns:
            True if agent was unregistered, False if not found
        """
        async with self._lock:
            if agent_id not in self._agents:
                return False

            agent_info = self._agents.pop(agent_id)
            for capability in agent_info.capabilities:
                if capability.name in self._capabilities_index:
                    self._capabilities_index[capability.name] = [
                        aid for aid in self._capabilities_index[capability.name]
                        if aid != agent_id
                    ]

        logger.info(f"Unregistered agent {agent_id}")
        return True

    async def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Get agent information.

        Args:
            agent_id: ID of the agent

        Returns:
            AgentInfo or None if not found
        """
        return self._agents.get(agent_id)

    async def list_agents(
        self,
        agent_type: Optional[str] = None,
        status: Optional[AgentStatus] = None,
    ) -> list[AgentInfo]:
        """List agents with optional filtering.

        Args:
            agent_type: Filter by agent type
            status: Filter by status

        Returns:
            List of AgentInfo objects
        """
        agents = list(self._agents.values())

        if agent_type:
            agents = [a for a in agents if a.agent_type == agent_type]

        if status:
            agents = [a for a in agents if a.status == status]

        return agents

    async def find_agents_for_capability(
        self,
        capability_name: str,
        available_only: bool = True,
    ) -> list[AgentInfo]:
        """Find agents that can perform a capability.

        Args:
            capability_name: Name of the capability
            available_only: Only return available agents

        Returns:
            List of AgentInfo objects sorted by load
        """
        agent_ids = self._capabilities_index.get(capability_name, [])
        agents = [self._agents[aid] for aid in agent_ids if aid in self._agents]

        if available_only:
            agents = [a for a in agents if a.is_available()]

        agents.sort(key=lambda a: a.current_load)
        return agents

    async def update_agent_load(self, agent_id: str, delta: int) -> bool:
        """Update agent load.

        Args:
            agent_id: ID of the agent
            delta: Change in load (positive or negative)

        Returns:
            True if updated, False if agent not found
        """
        async with self._lock:
            if agent_id not in self._agents:
                return False

            agent = self._agents[agent_id]
            agent.current_load = max(0, agent.current_load + delta)
            return True

    async def update_agent_status(
        self,
        agent_id: str,
        status: AgentStatus,
    ) -> bool:
        """Update agent status.

        Args:
            agent_id: ID of the agent
            status: New status

        Returns:
            True if updated, False if agent not found
        """
        async with self._lock:
            if agent_id not in self._agents:
                return False

            self._agents[agent_id].status = status
            return True

    async def heartbeat(self, agent_id: str) -> bool:
        """Record heartbeat from agent.

        Args:
            agent_id: ID of the agent

        Returns:
            True if heartbeat recorded, False if agent not found
        """
        async with self._lock:
            if agent_id not in self._agents:
                return False

            agent = self._agents[agent_id]
            agent.last_heartbeat = datetime.now(UTC)

            if not agent.is_healthy(self.heartbeat_timeout):
                agent.status = AgentStatus.OFFLINE
            elif agent.status == AgentStatus.OFFLINE:
                agent.status = AgentStatus.HEALTHY

            return True

    async def cleanup_offline_agents(self) -> list[str]:
        """Remove offline agents that haven't sent heartbeat.

        Returns:
            List of removed agent IDs
        """
        removed = []
        async with self._lock:
            now = datetime.now(UTC)
            for agent_id, agent in list(self._agents.items()):
                time_since_heartbeat = (now - agent.last_heartbeat).total_seconds()
                if time_since_heartbeat > self.heartbeat_timeout * 2:
                    self._agents.pop(agent_id)
                    removed.append(agent_id)

        logger.info(f"Cleaned up {len(removed)} offline agents")
        return removed

    async def get_registry_stats(self) -> dict[str, Any]:
        """Get registry statistics."""
        agents = list(self._agents.values())
        return {
            "total_agents": len(agents),
            "healthy_agents": len([a for a in agents if a.status == AgentStatus.HEALTHY]),
            "degraded_agents": len([a for a in agents if a.status == AgentStatus.DEGRADED]),
            "offline_agents": len([a for a in agents if a.status == AgentStatus.OFFLINE]),
            "total_capabilities": len(self._capabilities_index),
            "average_load": sum(a.current_load for a in agents) / len(agents) if agents else 0,
        }
