"""
Event Bus Integration for X-Agent.

Integrates the event bus into all critical modules:
- Agent execution lifecycle
- Workflow execution
- Tool execution
- Memory operations
- Error handling
"""

from __future__ import annotations

import logging
from typing import Any

from backend.app.core.event_bus import Event, EventBus, EventType, get_event_bus

logger = logging.getLogger(__name__)


class EventBusIntegration:
    """
    Centralized event bus integration for X-Agent.

    Provides methods to publish events from different modules.
    """

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self.event_bus = event_bus or get_event_bus()

    # Agent Events
    async def publish_agent_started(
        self,
        agent_id: str,
        task: str,
        user_id: str | None = None,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Publish agent started event."""
        event = Event(
            event_type=EventType.AGENT_STARTED,
            source="agent",
            data={
                "agent_id": agent_id,
                "task": task,
            },
            user_id=user_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
        await self.event_bus.publish(event)
        logger.debug(f"Published AGENT_STARTED event for agent {agent_id}")

    async def publish_agent_step_completed(
        self,
        agent_id: str,
        step_number: int,
        step_type: str,
        result: Any,
        user_id: str | None = None,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Publish agent step completed event."""
        event = Event(
            event_type=EventType.AGENT_STEP_COMPLETED,
            source="agent",
            data={
                "agent_id": agent_id,
                "step_number": step_number,
                "step_type": step_type,
                "result": str(result)[:1000],  # Truncate large results
            },
            user_id=user_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
        await self.event_bus.publish(event)
        logger.debug(f"Published AGENT_STEP_COMPLETED event for agent {agent_id} step {step_number}")

    async def publish_agent_completed(
        self,
        agent_id: str,
        result: Any,
        duration_seconds: float,
        user_id: str | None = None,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Publish agent completed event."""
        event = Event(
            event_type=EventType.AGENT_COMPLETED,
            source="agent",
            data={
                "agent_id": agent_id,
                "result": str(result)[:1000],
                "duration_seconds": duration_seconds,
            },
            user_id=user_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
        await self.event_bus.publish(event)
        logger.debug(f"Published AGENT_COMPLETED event for agent {agent_id}")

    async def publish_agent_failed(
        self,
        agent_id: str,
        error: str,
        error_type: str,
        user_id: str | None = None,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Publish agent failed event."""
        event = Event(
            event_type=EventType.AGENT_FAILED,
            source="agent",
            data={
                "agent_id": agent_id,
                "error": error,
                "error_type": error_type,
            },
            user_id=user_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
        await self.event_bus.publish(event)
        logger.error(f"Published AGENT_FAILED event for agent {agent_id}: {error}")

    # Workflow Events
    async def publish_workflow_started(
        self,
        workflow_id: str,
        workflow_name: str,
        user_id: str | None = None,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Publish workflow started event."""
        event = Event(
            event_type=EventType.WORKFLOW_STARTED,
            source="workflow",
            data={
                "workflow_id": workflow_id,
                "workflow_name": workflow_name,
            },
            user_id=user_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
        await self.event_bus.publish(event)
        logger.debug(f"Published WORKFLOW_STARTED event for workflow {workflow_id}")

    async def publish_workflow_step_completed(
        self,
        workflow_id: str,
        step_id: str,
        step_name: str,
        result: Any,
        user_id: str | None = None,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Publish workflow step completed event."""
        event = Event(
            event_type=EventType.WORKFLOW_STEP_COMPLETED,
            source="workflow",
            data={
                "workflow_id": workflow_id,
                "step_id": step_id,
                "step_name": step_name,
                "result": str(result)[:1000],
            },
            user_id=user_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
        await self.event_bus.publish(event)
        logger.debug(f"Published WORKFLOW_STEP_COMPLETED event for workflow {workflow_id} step {step_id}")

    async def publish_workflow_completed(
        self,
        workflow_id: str,
        result: Any,
        duration_seconds: float,
        user_id: str | None = None,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Publish workflow completed event."""
        event = Event(
            event_type=EventType.WORKFLOW_COMPLETED,
            source="workflow",
            data={
                "workflow_id": workflow_id,
                "result": str(result)[:1000],
                "duration_seconds": duration_seconds,
            },
            user_id=user_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
        await self.event_bus.publish(event)
        logger.debug(f"Published WORKFLOW_COMPLETED event for workflow {workflow_id}")

    async def publish_workflow_failed(
        self,
        workflow_id: str,
        error: str,
        error_type: str,
        user_id: str | None = None,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Publish workflow failed event."""
        event = Event(
            event_type=EventType.WORKFLOW_FAILED,
            source="workflow",
            data={
                "workflow_id": workflow_id,
                "error": error,
                "error_type": error_type,
            },
            user_id=user_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
        await self.event_bus.publish(event)
        logger.error(f"Published WORKFLOW_FAILED event for workflow {workflow_id}: {error}")

    # Tool Events
    async def publish_tool_executed(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_output: Any,
        duration_seconds: float,
        user_id: str | None = None,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Publish tool executed event."""
        event = Event(
            event_type=EventType.TOOL_EXECUTED,
            source="tool",
            data={
                "tool_name": tool_name,
                "tool_input": str(tool_input)[:500],
                "tool_output": str(tool_output)[:500],
                "duration_seconds": duration_seconds,
            },
            user_id=user_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
        await self.event_bus.publish(event)
        logger.debug(f"Published TOOL_EXECUTED event for tool {tool_name}")

    async def publish_tool_failed(
        self,
        tool_name: str,
        error: str,
        error_type: str,
        user_id: str | None = None,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Publish tool failed event."""
        event = Event(
            event_type=EventType.TOOL_FAILED,
            source="tool",
            data={
                "tool_name": tool_name,
                "error": error,
                "error_type": error_type,
            },
            user_id=user_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
        await self.event_bus.publish(event)
        logger.error(f"Published TOOL_FAILED event for tool {tool_name}: {error}")

    # Memory Events
    async def publish_memory_updated(
        self,
        memory_id: str,
        operation: str,
        data_size: int,
        user_id: str | None = None,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Publish memory updated event."""
        event = Event(
            event_type=EventType.MEMORY_UPDATED,
            source="memory",
            data={
                "memory_id": memory_id,
                "operation": operation,
                "data_size": data_size,
            },
            user_id=user_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
        await self.event_bus.publish(event)
        logger.debug(f"Published MEMORY_UPDATED event for memory {memory_id}")

    async def publish_memory_retrieved(
        self,
        memory_id: str,
        query: str,
        result_count: int,
        user_id: str | None = None,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Publish memory retrieved event."""
        event = Event(
            event_type=EventType.MEMORY_RETRIEVED,
            source="memory",
            data={
                "memory_id": memory_id,
                "query": query[:500],
                "result_count": result_count,
            },
            user_id=user_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
        await self.event_bus.publish(event)
        logger.debug(f"Published MEMORY_RETRIEVED event for memory {memory_id}")

    # Security Events
    async def publish_authentication_failed(
        self,
        reason: str,
        user_id: str | None = None,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Publish authentication failed event."""
        event = Event(
            event_type=EventType.AUTHENTICATION_FAILED,
            source="security",
            data={
                "reason": reason,
            },
            user_id=user_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
        await self.event_bus.publish(event)
        logger.warning(f"Published AUTHENTICATION_FAILED event: {reason}")

    async def publish_authorization_failed(
        self,
        resource: str,
        action: str,
        user_id: str | None = None,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Publish authorization failed event."""
        event = Event(
            event_type=EventType.AUTHORIZATION_FAILED,
            source="security",
            data={
                "resource": resource,
                "action": action,
            },
            user_id=user_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
        await self.event_bus.publish(event)
        logger.warning(f"Published AUTHORIZATION_FAILED event for {resource}:{action}")

    async def publish_suspicious_activity(
        self,
        activity_type: str,
        details: dict[str, Any],
        user_id: str | None = None,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Publish suspicious activity event."""
        event = Event(
            event_type=EventType.SUSPICIOUS_ACTIVITY,
            source="security",
            data={
                "activity_type": activity_type,
                "details": details,
            },
            user_id=user_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
        await self.event_bus.publish(event)
        logger.warning(f"Published SUSPICIOUS_ACTIVITY event: {activity_type}")

    # System Events
    async def publish_system_error(
        self,
        error: str,
        error_type: str,
        component: str,
        user_id: str | None = None,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Publish system error event."""
        event = Event(
            event_type=EventType.SYSTEM_ERROR,
            source=component,
            data={
                "error": error,
                "error_type": error_type,
                "component": component,
            },
            user_id=user_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
        await self.event_bus.publish(event)
        logger.error(f"Published SYSTEM_ERROR event from {component}: {error}")

    async def publish_system_warning(
        self,
        warning: str,
        component: str,
        user_id: str | None = None,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Publish system warning event."""
        event = Event(
            event_type=EventType.SYSTEM_WARNING,
            source=component,
            data={
                "warning": warning,
                "component": component,
            },
            user_id=user_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
        await self.event_bus.publish(event)
        logger.warning(f"Published SYSTEM_WARNING event from {component}: {warning}")


# Global event bus integration instance
_event_bus_integration: EventBusIntegration | None = None


def get_event_bus_integration() -> EventBusIntegration:
    """Get or create the global event bus integration."""
    global _event_bus_integration
    if _event_bus_integration is None:
        _event_bus_integration = EventBusIntegration()
    return _event_bus_integration
