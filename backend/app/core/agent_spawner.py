"""
Agent spawner module for X-Agent.

Manages the lifecycle of sub-agents including spawning, termination,
and status tracking.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Optional, Any, Dict, List

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    """Status of an agent."""

    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    FAILED = "failed"
    TERMINATED = "terminated"


class IsolationLevel(str, Enum):
    """Isolation level for agent execution."""

    NONE = "none"
    PROCESS = "process"
    CONTAINER = "container"


@dataclass
class AgentConfig:
    """Configuration for a spawned agent."""

    agent_type: str
    task: str
    context: Dict[str, Any] = field(default_factory=dict)
    isolation: Optional[IsolationLevel] = None
    max_iterations: int = 10
    timeout_seconds: int = 3600
    memory_limit_mb: int = 512
    cpu_limit_percent: int = 100
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentInstance:
    """Represents a spawned agent instance."""

    agent_id: str
    config: AgentConfig
    status: AgentStatus = AgentStatus.INITIALIZING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[Any] = None
    iterations: int = 0
    task_id: Optional[str] = None


class AgentSpawner:
    """
    Manages spawning and lifecycle of sub-agents.

    Handles agent creation, execution, monitoring, and termination.
    """

    def __init__(self, max_concurrent_agents: int = 10):
        """
        Initialize the agent spawner.

        Args:
            max_concurrent_agents: Maximum number of concurrent agents
        """
        self.max_concurrent_agents = max_concurrent_agents
        self.agents: Dict[str, AgentInstance] = {}
        self.agent_tasks: Dict[str, asyncio.Task] = {}
        self.logger = logger

    async def spawn_agent(
        self,
        agent_type: str,
        task: str,
        context: Dict[str, Any],
        isolation: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Spawn a new sub-agent.

        Args:
            agent_type: Type of agent to spawn
            task: Task for the agent to execute
            context: Context data for the agent
            isolation: Isolation level (none, process, container)
            **kwargs: Additional configuration options

        Returns:
            Agent ID

        Raises:
            RuntimeError: If max concurrent agents reached
        """
        # Check concurrent limit
        active_agents = sum(
            1 for a in self.agents.values()
            if a.status in (AgentStatus.INITIALIZING, AgentStatus.READY, AgentStatus.RUNNING)
        )
        if active_agents >= self.max_concurrent_agents:
            raise RuntimeError(
                f"Max concurrent agents ({self.max_concurrent_agents}) reached"
            )

        # Create agent instance
        agent_id = f"agent_{uuid.uuid4().hex[:12]}"
        isolation_level = IsolationLevel(isolation) if isolation else IsolationLevel.NONE

        config = AgentConfig(
            agent_type=agent_type,
            task=task,
            context=context,
            isolation=isolation_level,
            max_iterations=kwargs.get("max_iterations", 10),
            timeout_seconds=kwargs.get("timeout_seconds", 3600),
            memory_limit_mb=kwargs.get("memory_limit_mb", 512),
            cpu_limit_percent=kwargs.get("cpu_limit_percent", 100),
            metadata=kwargs.get("metadata", {}),
        )

        agent = AgentInstance(agent_id=agent_id, config=config)
        self.agents[agent_id] = agent

        self.logger.info(
            f"Spawned agent {agent_id} (type={agent_type}, isolation={isolation_level})"
        )

        # Create execution task
        task_obj = asyncio.create_task(self._execute_agent(agent_id))
        self.agent_tasks[agent_id] = task_obj

        return agent_id

    async def _execute_agent(self, agent_id: str) -> None:
        """
        Execute an agent.

        Args:
            agent_id: ID of agent to execute
        """
        agent = self.agents[agent_id]

        try:
            agent.status = AgentStatus.READY
            agent.started_at = datetime.now(UTC)

            # Simulate agent execution
            agent.status = AgentStatus.RUNNING

            # Wait for task completion or timeout
            timeout = agent.config.timeout_seconds
            await asyncio.sleep(0.1)  # Placeholder for actual execution

            agent.status = AgentStatus.COMPLETED if agent.status == AgentStatus.RUNNING else agent.status
            agent.completed_at = datetime.now(UTC)
            agent.result = {"status": "completed", "iterations": agent.iterations}

            self.logger.info(f"Agent {agent_id} completed successfully")

        except asyncio.TimeoutError:
            agent.status = AgentStatus.FAILED
            agent.error = "Execution timeout"
            agent.completed_at = datetime.now(UTC)
            self.logger.error(f"Agent {agent_id} timed out")

        except Exception as e:
            agent.status = AgentStatus.FAILED
            agent.error = str(e)
            agent.completed_at = datetime.now(UTC)
            self.logger.error(f"Agent {agent_id} failed: {e}")

    async def terminate_agent(self, agent_id: str) -> bool:
        """
        Terminate a running agent.

        Args:
            agent_id: ID of agent to terminate

        Returns:
            True if terminated, False if not found
        """
        if agent_id not in self.agents:
            self.logger.warning(f"Agent {agent_id} not found")
            return False

        agent = self.agents[agent_id]

        # Cancel the task
        if agent_id in self.agent_tasks:
            task = self.agent_tasks[agent_id]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        agent.status = AgentStatus.TERMINATED
        agent.completed_at = datetime.now(UTC)

        self.logger.info(f"Agent {agent_id} terminated")
        return True

    async def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of an agent.

        Args:
            agent_id: ID of agent

        Returns:
            Agent status dict or None if not found
        """
        if agent_id not in self.agents:
            return None

        agent = self.agents[agent_id]

        return {
            "agent_id": agent_id,
            "status": agent.status.value,
            "agent_type": agent.config.agent_type,
            "task": agent.config.task,
            "created_at": agent.created_at.isoformat(),
            "started_at": agent.started_at.isoformat() if agent.started_at else None,
            "completed_at": agent.completed_at.isoformat() if agent.completed_at else None,
            "iterations": agent.iterations,
            "error": agent.error,
            "result": agent.result,
        }

    async def list_agents(
        self,
        status: Optional[str] = None,
        agent_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List agents with optional filtering.

        Args:
            status: Filter by status
            agent_type: Filter by agent type

        Returns:
            List of agent status dicts
        """
        agents = []

        for agent_id, agent in self.agents.items():
            if status and agent.status.value != status:
                continue
            if agent_type and agent.config.agent_type != agent_type:
                continue

            agents.append(
                {
                    "agent_id": agent_id,
                    "status": agent.status.value,
                    "agent_type": agent.config.agent_type,
                    "task": agent.config.task,
                    "created_at": agent.created_at.isoformat(),
                }
            )

        return agents

    async def wait_for_agent(
        self,
        agent_id: str,
        timeout_seconds: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Wait for an agent to complete.

        Args:
            agent_id: ID of agent to wait for
            timeout_seconds: Timeout in seconds

        Returns:
            Agent status dict or None if timeout
        """
        if agent_id not in self.agent_tasks:
            return None

        try:
            await asyncio.wait_for(
                self.agent_tasks[agent_id],
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            self.logger.warning(f"Timeout waiting for agent {agent_id}")
            return None

        return await self.get_agent_status(agent_id)

    def get_agent_count(self, status: Optional[str] = None) -> int:
        """
        Get count of agents.

        Args:
            status: Filter by status

        Returns:
            Count of agents
        """
        if not status:
            return len(self.agents)

        return sum(
            1 for a in self.agents.values()
            if a.status.value == status
        )

    async def cleanup_completed_agents(self, max_age_seconds: int = 3600) -> int:
        """
        Clean up completed agents older than max_age.

        Args:
            max_age_seconds: Maximum age in seconds

        Returns:
            Number of agents cleaned up
        """
        now = datetime.now(UTC)
        cleaned = 0

        agent_ids_to_remove = []
        for agent_id, agent in self.agents.items():
            if agent.status in (AgentStatus.COMPLETED, AgentStatus.FAILED, AgentStatus.TERMINATED):
                if agent.completed_at:
                    age = (now - agent.completed_at).total_seconds()
                    if age > max_age_seconds:
                        agent_ids_to_remove.append(agent_id)

        for agent_id in agent_ids_to_remove:
            del self.agents[agent_id]
            if agent_id in self.agent_tasks:
                del self.agent_tasks[agent_id]
            cleaned += 1

        self.logger.info(f"Cleaned up {cleaned} completed agents")
        return cleaned

    def get_stats(self) -> Dict[str, Any]:
        """
        Get spawner statistics.

        Returns:
            Statistics dict
        """
        statuses = {}
        for agent in self.agents.values():
            status = agent.status.value
            statuses[status] = statuses.get(status, 0) + 1

        return {
            "total_agents": len(self.agents),
            "active_agents": sum(
                1 for a in self.agents.values()
                if a.status in (AgentStatus.INITIALIZING, AgentStatus.READY, AgentStatus.RUNNING)
            ),
            "status_breakdown": statuses,
            "max_concurrent": self.max_concurrent_agents,
        }


# Global instance
agent_spawner = AgentSpawner()
