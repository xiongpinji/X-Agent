"""
Agent recovery module for X-Agent.

Handles failure detection and recovery of agents.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class FailureType(StrEnum):
    """Types of agent failures."""

    TIMEOUT = "timeout"
    CRASH = "crash"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


class RecoveryStrategy(StrEnum):
    """Strategies for recovering from failures."""

    RETRY = "retry"
    FALLBACK = "fallback"
    ESCALATE = "escalate"
    SKIP = "skip"
    ABORT = "abort"


@dataclass
class FailureEvent:
    """Represents a failure event."""

    agent_id: str
    failure_type: FailureType
    error_message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    context: dict[str, Any] = field(default_factory=dict)
    recovery_attempted: bool = False
    recovery_successful: bool = False


@dataclass
class RecoveryPlan:
    """Plan for recovering from a failure."""

    agent_id: str
    failure_event: FailureEvent
    strategy: RecoveryStrategy
    max_retries: int = 3
    retry_delay_seconds: int = 5
    fallback_agent_id: str | None = None
    escalation_handler: Callable | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentRecovery:
    """
    Handles agent failure detection and recovery.

    Monitors agents for failures and executes recovery strategies.
    """

    def __init__(self, health_check_interval_seconds: int = 30):
        """
        Initialize the agent recovery system.

        Args:
            health_check_interval_seconds: Interval for health checks
        """
        self.health_check_interval = health_check_interval_seconds
        self.failure_history: dict[str, list[FailureEvent]] = {}
        self.recovery_plans: dict[str, RecoveryPlan] = {}
        self.monitored_agents: dict[str, Any] = {}
        self.logger = logger

    async def detect_failure(
        self,
        agent_id: str,
        agent: Any,
    ) -> FailureEvent | None:
        """
        Detect if an agent has failed.

        Args:
            agent_id: ID of agent to check
            agent: Agent instance

        Returns:
            FailureEvent if failure detected, None otherwise
        """
        try:
            # Check agent status
            status = getattr(agent, "status", None)

            if status == "failed":
                failure_event = FailureEvent(
                    agent_id=agent_id,
                    failure_type=FailureType.CRASH,
                    error_message=getattr(agent, "error", "Unknown error"),
                )
                self._record_failure(failure_event)
                return failure_event

            # Check for timeout
            if hasattr(agent, "started_at") and hasattr(agent, "timeout_seconds"):
                elapsed = (datetime.now(UTC) - agent.started_at).total_seconds()
                if elapsed > agent.timeout_seconds:
                    failure_event = FailureEvent(
                        agent_id=agent_id,
                        failure_type=FailureType.TIMEOUT,
                        error_message=f"Agent timeout after {elapsed}s",
                    )
                    self._record_failure(failure_event)
                    return failure_event

            # Check for resource exhaustion
            if hasattr(agent, "memory_usage_mb") and hasattr(agent, "memory_limit_mb"):
                if agent.memory_usage_mb > agent.memory_limit_mb * 0.9:
                    failure_event = FailureEvent(
                        agent_id=agent_id,
                        failure_type=FailureType.RESOURCE_EXHAUSTION,
                        error_message=f"Memory usage {agent.memory_usage_mb}MB exceeds limit",
                    )
                    self._record_failure(failure_event)
                    return failure_event

            return None

        except Exception as e:
            self.logger.error(f"Error detecting failure for agent {agent_id}: {e}")
            return None

    async def recover_agent(
        self,
        agent_id: str,
        strategy: RecoveryStrategy = RecoveryStrategy.RETRY,
        **kwargs,
    ) -> bool:
        """
        Recover a failed agent.

        Args:
            agent_id: ID of agent to recover
            strategy: Recovery strategy
            **kwargs: Additional options

        Returns:
            True if recovery successful
        """
        self.logger.info(f"Attempting recovery for agent {agent_id} using {strategy.value}")

        try:
            if strategy == RecoveryStrategy.RETRY:
                return await self._recover_retry(agent_id, **kwargs)

            elif strategy == RecoveryStrategy.FALLBACK:
                return await self._recover_fallback(agent_id, **kwargs)

            elif strategy == RecoveryStrategy.ESCALATE:
                return await self._recover_escalate(agent_id, **kwargs)

            elif strategy == RecoveryStrategy.SKIP:
                return await self._recover_skip(agent_id, **kwargs)

            elif strategy == RecoveryStrategy.ABORT:
                return await self._recover_abort(agent_id, **kwargs)

            else:
                self.logger.error(f"Unknown recovery strategy: {strategy}")
                return False

        except Exception as e:
            self.logger.error(f"Recovery failed for agent {agent_id}: {e}")
            return False

    async def _recover_retry(
        self,
        agent_id: str,
        max_retries: int = 3,
        retry_delay_seconds: int = 5,
        **kwargs,
    ) -> bool:
        """
        Recover by retrying the agent.

        Args:
            agent_id: ID of agent
            max_retries: Maximum retry attempts
            retry_delay_seconds: Delay between retries
            **kwargs: Additional options

        Returns:
            True if recovery successful
        """
        for attempt in range(max_retries):
            try:
                self.logger.info(
                    f"Retry attempt {attempt + 1}/{max_retries} for agent {agent_id}"
                )

                # Wait before retry
                if attempt > 0:
                    await asyncio.sleep(retry_delay_seconds * (2 ** (attempt - 1)))

                # Restart agent
                if agent_id in self.monitored_agents:
                    agent = self.monitored_agents[agent_id]
                    # Reset agent state
                    if hasattr(agent, "reset"):
                        await agent.reset()

                    # Check if recovered
                    if getattr(agent, "status", None) != "failed":
                        self.logger.info(f"Agent {agent_id} recovered successfully")
                        return True

            except Exception as e:
                self.logger.warning(f"Retry attempt {attempt + 1} failed: {e}")

        return False

    async def _recover_fallback(
        self,
        agent_id: str,
        fallback_agent_id: str | None = None,
        **kwargs,
    ) -> bool:
        """
        Recover by switching to fallback agent.

        Args:
            agent_id: ID of failed agent
            fallback_agent_id: ID of fallback agent
            **kwargs: Additional options

        Returns:
            True if recovery successful
        """
        if not fallback_agent_id:
            self.logger.warning(f"No fallback agent specified for {agent_id}")
            return False

        try:
            self.logger.info(f"Switching to fallback agent {fallback_agent_id}")

            if fallback_agent_id in self.monitored_agents:
                fallback_agent = self.monitored_agents[fallback_agent_id]
                if getattr(fallback_agent, "status", None) != "failed":
                    self.logger.info(f"Fallback agent {fallback_agent_id} is ready")
                    return True

        except Exception as e:
            self.logger.error(f"Fallback recovery failed: {e}")

        return False

    async def _recover_escalate(
        self,
        agent_id: str,
        escalation_handler: Callable | None = None,
        **kwargs,
    ) -> bool:
        """
        Recover by escalating to handler.

        Args:
            agent_id: ID of agent
            escalation_handler: Handler for escalation
            **kwargs: Additional options

        Returns:
            True if escalation handled
        """
        try:
            if escalation_handler:
                self.logger.info(f"Escalating agent {agent_id} to handler")
                result = await escalation_handler(agent_id, **kwargs)
                return result

            self.logger.warning(f"No escalation handler for agent {agent_id}")
            return False

        except Exception as e:
            self.logger.error(f"Escalation failed: {e}")
            return False

    async def _recover_skip(
        self,
        agent_id: str,
        **kwargs,
    ) -> bool:
        """
        Recover by skipping the agent.

        Args:
            agent_id: ID of agent
            **kwargs: Additional options

        Returns:
            True (always succeeds)
        """
        self.logger.info(f"Skipping agent {agent_id}")
        return True

    async def _recover_abort(
        self,
        agent_id: str,
        **kwargs,
    ) -> bool:
        """
        Recover by aborting the agent.

        Args:
            agent_id: ID of agent
            **kwargs: Additional options

        Returns:
            True if aborted
        """
        try:
            self.logger.info(f"Aborting agent {agent_id}")

            if agent_id in self.monitored_agents:
                agent = self.monitored_agents[agent_id]
                if hasattr(agent, "abort"):
                    await agent.abort()

            return True

        except Exception as e:
            self.logger.error(f"Abort failed: {e}")
            return False

    def register_agent(self, agent_id: str, agent: Any) -> None:
        """
        Register an agent for monitoring.

        Args:
            agent_id: ID of agent
            agent: Agent instance
        """
        self.monitored_agents[agent_id] = agent
        self.failure_history[agent_id] = []
        self.logger.debug(f"Registered agent {agent_id} for monitoring")

    def unregister_agent(self, agent_id: str) -> None:
        """
        Unregister an agent from monitoring.

        Args:
            agent_id: ID of agent
        """
        if agent_id in self.monitored_agents:
            del self.monitored_agents[agent_id]
            self.logger.debug(f"Unregistered agent {agent_id}")

    def _record_failure(self, failure_event: FailureEvent) -> None:
        """
        Record a failure event.

        Args:
            failure_event: Failure event to record
        """
        agent_id = failure_event.agent_id

        if agent_id not in self.failure_history:
            self.failure_history[agent_id] = []

        self.failure_history[agent_id].append(failure_event)
        self.logger.warning(
            f"Failure recorded for agent {agent_id}: {failure_event.failure_type.value}"
        )

    def get_failure_history(
        self,
        agent_id: str,
        hours: int = 24,
    ) -> list[FailureEvent]:
        """
        Get failure history for an agent.

        Args:
            agent_id: ID of agent
            hours: Look back period in hours

        Returns:
            List of failure events
        """
        if agent_id not in self.failure_history:
            return []

        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        return [
            event for event in self.failure_history[agent_id]
            if event.timestamp >= cutoff
        ]

    def get_recovery_stats(self) -> dict[str, Any]:
        """
        Get recovery statistics.

        Returns:
            Statistics dict
        """
        total_failures = sum(len(events) for events in self.failure_history.values())
        failure_types = {}

        for events in self.failure_history.values():
            for event in events:
                ft = event.failure_type.value
                failure_types[ft] = failure_types.get(ft, 0) + 1

        return {
            "total_failures": total_failures,
            "monitored_agents": len(self.monitored_agents),
            "failure_types": failure_types,
        }


# Global instance
agent_recovery = AgentRecovery()
