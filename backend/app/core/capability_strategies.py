"""
Capability Strategy Pattern Implementation

This module provides a flexible, extensible strategy pattern for routing
capabilities in the X-Agent orchestrator. Replaces nested if-statements
with composable, testable strategy objects.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.app.core.contracts import CapabilityDecision, OrchestrationContext


class CapabilityStrategy(ABC):
    """Abstract base class for capability strategies."""

    @property
    @abstractmethod
    def priority(self) -> int:
        """Priority for strategy execution (lower = higher priority)."""
        pass

    @abstractmethod
    async def can_handle(self, context: OrchestrationContext) -> bool:
        """
        Determine if this strategy can handle the given context.

        Args:
            context: The orchestration context to evaluate

        Returns:
            True if this strategy should handle the context, False otherwise
        """
        pass

    @abstractmethod
    async def execute(self, context: OrchestrationContext) -> CapabilityDecision:
        """
        Execute the capability and return a decision.

        Args:
            context: The orchestration context to process

        Returns:
            A CapabilityDecision with the routing result
        """
        pass


class ApprovalStrategy(CapabilityStrategy):
    """Strategy for handling approval-required capabilities."""

    @property
    def priority(self) -> int:
        return 0  # Highest priority

    async def can_handle(self, context: OrchestrationContext) -> bool:
        """Check if approval is pending or required."""
        metadata = context.metadata
        approval = metadata.get("approval", {}) if isinstance(metadata.get("approval"), dict) else {}
        return bool(approval.get("pending_count", 0)) or context.task.requires_approval

    async def execute(self, context: OrchestrationContext) -> CapabilityDecision:
        """Route to approval capability."""
        metadata = context.metadata
        workflow = metadata.get("workflow", {}) if isinstance(metadata.get("workflow"), dict) else {}
        approval = metadata.get("approval", {}) if isinstance(metadata.get("approval"), dict) else {}
        browser = metadata.get("browser", {}) if isinstance(metadata.get("browser"), dict) else {}
        desktop = metadata.get("desktop", {}) if isinstance(metadata.get("desktop"), dict) else {}

        return CapabilityDecision(
            name="approval",
            reason="approval boundary detected",
            metadata={"approval": approval, "workflow": workflow, "browser": browser, "desktop": desktop},
        )


class BrowserStrategy(CapabilityStrategy):
    """Strategy for browser automation capabilities."""

    @property
    def priority(self) -> int:
        return 1

    async def can_handle(self, context: OrchestrationContext) -> bool:
        """Check if browser context is active or task mentions browser."""
        metadata = context.metadata
        browser = metadata.get("browser", {}) if isinstance(metadata.get("browser"), dict) else {}
        task_text = f"{context.task.goal} {context.task.description} {metadata.get('task', '')}".lower()
        return bool(browser.get("active_count", 0)) or "browser" in task_text

    async def execute(self, context: OrchestrationContext) -> CapabilityDecision:
        """Route to browser capability."""
        metadata = context.metadata
        workflow = metadata.get("workflow", {}) if isinstance(metadata.get("workflow"), dict) else {}
        approval = metadata.get("approval", {}) if isinstance(metadata.get("approval"), dict) else {}
        browser = metadata.get("browser", {}) if isinstance(metadata.get("browser"), dict) else {}
        desktop = metadata.get("desktop", {}) if isinstance(metadata.get("desktop"), dict) else {}

        return CapabilityDecision(
            name="browser",
            reason="browser context detected",
            metadata={"browser": browser, "workflow": workflow, "approval": approval, "desktop": desktop},
        )


class DesktopStrategy(CapabilityStrategy):
    """Strategy for desktop automation capabilities."""

    @property
    def priority(self) -> int:
        return 2

    async def can_handle(self, context: OrchestrationContext) -> bool:
        """Check if desktop context is active or task mentions desktop."""
        metadata = context.metadata
        desktop = metadata.get("desktop", {}) if isinstance(metadata.get("desktop"), dict) else {}
        task_text = f"{context.task.goal} {context.task.description} {metadata.get('task', '')}".lower()
        return bool(desktop.get("active_count", 0)) or "desktop" in task_text

    async def execute(self, context: OrchestrationContext) -> CapabilityDecision:
        """Route to desktop capability."""
        metadata = context.metadata
        workflow = metadata.get("workflow", {}) if isinstance(metadata.get("workflow"), dict) else {}
        approval = metadata.get("approval", {}) if isinstance(metadata.get("approval"), dict) else {}
        browser = metadata.get("browser", {}) if isinstance(metadata.get("browser"), dict) else {}
        desktop = metadata.get("desktop", {}) if isinstance(metadata.get("desktop"), dict) else {}

        return CapabilityDecision(
            name="desktop",
            reason="desktop context detected",
            metadata={"desktop": desktop, "workflow": workflow, "approval": approval, "browser": browser},
        )


class WorkflowStrategy(CapabilityStrategy):
    """Strategy for workflow execution capabilities."""

    @property
    def priority(self) -> int:
        return 3

    async def can_handle(self, context: OrchestrationContext) -> bool:
        """Check if workflow context exists."""
        metadata = context.metadata
        workflow = metadata.get("workflow", {}) if isinstance(metadata.get("workflow"), dict) else {}
        return bool(workflow)

    async def execute(self, context: OrchestrationContext) -> CapabilityDecision:
        """Route to workflow capability."""
        metadata = context.metadata
        workflow = metadata.get("workflow", {}) if isinstance(metadata.get("workflow"), dict) else {}
        approval = metadata.get("approval", {}) if isinstance(metadata.get("approval"), dict) else {}
        browser = metadata.get("browser", {}) if isinstance(metadata.get("browser"), dict) else {}
        desktop = metadata.get("desktop", {}) if isinstance(metadata.get("desktop"), dict) else {}

        return CapabilityDecision(
            name="workflow",
            reason="workflow context detected",
            metadata={"workflow": workflow, "approval": approval, "browser": browser, "desktop": desktop},
        )


class MemoryStrategy(CapabilityStrategy):
    """Strategy for memory management capabilities."""

    @property
    def priority(self) -> int:
        return 4

    async def can_handle(self, context: OrchestrationContext) -> bool:
        """Check if task mentions memory-related keywords."""
        metadata = context.metadata
        task_text = f"{context.task.goal} {context.task.description} {metadata.get('task', '')}".lower()
        return any(token in task_text for token in ["memory", "remember", "recall"])

    async def execute(self, context: OrchestrationContext) -> CapabilityDecision:
        """Route to memory capability."""
        metadata = context.metadata
        workflow = metadata.get("workflow", {}) if isinstance(metadata.get("workflow"), dict) else {}
        approval = metadata.get("approval", {}) if isinstance(metadata.get("approval"), dict) else {}
        browser = metadata.get("browser", {}) if isinstance(metadata.get("browser"), dict) else {}
        desktop = metadata.get("desktop", {}) if isinstance(metadata.get("desktop"), dict) else {}

        return CapabilityDecision(
            name="memory",
            reason="memory intent detected",
            metadata={
                "memory": metadata.get("memory", {}),
                "workflow": workflow,
                "approval": approval,
                "browser": browser,
                "desktop": desktop,
            },
        )


class ObservabilityStrategy(CapabilityStrategy):
    """Strategy for observability and tracing capabilities."""

    @property
    def priority(self) -> int:
        return 5

    async def can_handle(self, context: OrchestrationContext) -> bool:
        """Check if task mentions observability-related keywords."""
        metadata = context.metadata
        task_text = f"{context.task.goal} {context.task.description} {metadata.get('task', '')}".lower()
        return any(token in task_text for token in ["trace", "audit", "observe", "report"])

    async def execute(self, context: OrchestrationContext) -> CapabilityDecision:
        """Route to observability capability."""
        metadata = context.metadata
        workflow = metadata.get("workflow", {}) if isinstance(metadata.get("workflow"), dict) else {}
        approval = metadata.get("approval", {}) if isinstance(metadata.get("approval"), dict) else {}
        browser = metadata.get("browser", {}) if isinstance(metadata.get("browser"), dict) else {}
        desktop = metadata.get("desktop", {}) if isinstance(metadata.get("desktop"), dict) else {}

        return CapabilityDecision(
            name="observe",
            reason="observability intent detected",
            metadata={
                "trace": metadata.get("trace", {}),
                "workflow": workflow,
                "approval": approval,
                "browser": browser,
                "desktop": desktop,
            },
        )


class DefaultAgentStrategy(CapabilityStrategy):
    """Default fallback strategy for general agent execution."""

    @property
    def priority(self) -> int:
        return 999  # Lowest priority

    async def can_handle(self, context: OrchestrationContext) -> bool:
        """Always handles as fallback."""
        return True

    async def execute(self, context: OrchestrationContext) -> CapabilityDecision:
        """Route to default agent capability."""
        return CapabilityDecision(
            name="agent",
            reason="default agent execution",
            metadata={"task": context.task.model_dump(mode="json")},
        )


class CapabilityRegistry:
    """
    Registry for managing capability strategies.

    Provides dynamic registration, priority-based routing, and extensibility
    for adding new capabilities without modifying existing code.
    """

    def __init__(self) -> None:
        """Initialize the registry with default strategies."""
        self._strategies: list[CapabilityStrategy] = []
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register default strategies in priority order."""
        self.register(ApprovalStrategy())
        self.register(BrowserStrategy())
        self.register(DesktopStrategy())
        self.register(WorkflowStrategy())
        self.register(MemoryStrategy())
        self.register(ObservabilityStrategy())
        self.register(DefaultAgentStrategy())

    def register(self, strategy: CapabilityStrategy) -> None:
        """
        Register a new capability strategy.

        Strategies are automatically sorted by priority after registration.

        Args:
            strategy: The strategy to register
        """
        self._strategies.append(strategy)
        self._strategies.sort(key=lambda s: s.priority)

    def unregister(self, strategy_name: str) -> bool:
        """
        Unregister a strategy by class name.

        Args:
            strategy_name: The class name of the strategy to remove

        Returns:
            True if a strategy was removed, False otherwise
        """
        original_length = len(self._strategies)
        self._strategies = [s for s in self._strategies if s.__class__.__name__ != strategy_name]
        return len(self._strategies) < original_length

    async def route(self, context: OrchestrationContext) -> CapabilityDecision:
        """
        Route a context to the appropriate capability strategy.

        Iterates through registered strategies in priority order and returns
        the decision from the first strategy that can handle the context.

        Args:
            context: The orchestration context to route

        Returns:
            A CapabilityDecision from the first matching strategy

        Raises:
            ValueError: If no strategy can handle the context (should not occur
                       if DefaultAgentStrategy is registered)
        """
        for strategy in self._strategies:
            if await strategy.can_handle(context):
                return await strategy.execute(context)

        raise ValueError("No capability strategy found to handle context")

    def get_strategies(self) -> list[CapabilityStrategy]:
        """
        Get all registered strategies in priority order.

        Returns:
            List of registered strategies sorted by priority
        """
        return self._strategies.copy()

    def clear(self) -> None:
        """Clear all registered strategies."""
        self._strategies.clear()
