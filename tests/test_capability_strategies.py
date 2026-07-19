"""
Tests for capability strategies and registry.

Comprehensive test coverage for the strategy pattern implementation,
including individual strategies, registry routing, and integration scenarios.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.app.core.contracts import TaskFrame, RiskLevel
from backend.app.core.orchestrator import OrchestrationContext, CapabilityDecision
from backend.app.core.capability_strategies import (
    CapabilityRegistry,
    CapabilityStrategy,
    ApprovalStrategy,
    BrowserStrategy,
    DesktopStrategy,
    WorkflowStrategy,
    MemoryStrategy,
    ObservabilityStrategy,
    DefaultAgentStrategy,
)


class TestApprovalStrategy:
    """Tests for ApprovalStrategy."""

    @pytest.mark.asyncio
    async def test_can_handle_with_pending_approval(self):
        """Should handle context with pending approval."""
        strategy = ApprovalStrategy()
        task = TaskFrame(goal="test", description="test task")
        context = OrchestrationContext(
            task=task,
            metadata={"approval": {"pending_count": 1}},
        )
        assert await strategy.can_handle(context) is True

    @pytest.mark.asyncio
    async def test_can_handle_with_requires_approval(self):
        """Should handle context where task requires approval."""
        strategy = ApprovalStrategy()
        task = TaskFrame(goal="test", description="test task", requires_approval=True)
        context = OrchestrationContext(task=task, metadata={})
        assert await strategy.can_handle(context) is True

    @pytest.mark.asyncio
    async def test_cannot_handle_without_approval(self):
        """Should not handle context without approval requirements."""
        strategy = ApprovalStrategy()
        task = TaskFrame(goal="test", description="test task")
        context = OrchestrationContext(task=task, metadata={})
        assert await strategy.can_handle(context) is False

    @pytest.mark.asyncio
    async def test_execute_returns_approval_decision(self):
        """Should return approval capability decision."""
        strategy = ApprovalStrategy()
        task = TaskFrame(goal="test", description="test task", requires_approval=True)
        context = OrchestrationContext(task=task, metadata={})
        decision = await strategy.execute(context)
        assert decision.name == "approval"
        assert decision.reason == "approval boundary detected"

    def test_priority(self):
        """Should have highest priority."""
        strategy = ApprovalStrategy()
        assert strategy.priority == 0


class TestBrowserStrategy:
    """Tests for BrowserStrategy."""

    @pytest.mark.asyncio
    async def test_can_handle_with_active_browser(self):
        """Should handle context with active browser."""
        strategy = BrowserStrategy()
        task = TaskFrame(goal="test", description="test task")
        context = OrchestrationContext(
            task=task,
            metadata={"browser": {"active_count": 1}},
        )
        assert await strategy.can_handle(context) is True

    @pytest.mark.asyncio
    async def test_can_handle_with_browser_keyword(self):
        """Should handle context with 'browser' in task text."""
        strategy = BrowserStrategy()
        task = TaskFrame(goal="open browser", description="test task")
        context = OrchestrationContext(task=task, metadata={})
        assert await strategy.can_handle(context) is True

    @pytest.mark.asyncio
    async def test_cannot_handle_without_browser(self):
        """Should not handle context without browser context."""
        strategy = BrowserStrategy()
        task = TaskFrame(goal="test", description="test task")
        context = OrchestrationContext(task=task, metadata={})
        assert await strategy.can_handle(context) is False

    @pytest.mark.asyncio
    async def test_execute_returns_browser_decision(self):
        """Should return browser capability decision."""
        strategy = BrowserStrategy()
        task = TaskFrame(goal="open browser", description="test task")
        context = OrchestrationContext(task=task, metadata={})
        decision = await strategy.execute(context)
        assert decision.name == "browser"
        assert decision.reason == "browser context detected"

    def test_priority(self):
        """Should have priority 1."""
        strategy = BrowserStrategy()
        assert strategy.priority == 1


class TestDesktopStrategy:
    """Tests for DesktopStrategy."""

    @pytest.mark.asyncio
    async def test_can_handle_with_active_desktop(self):
        """Should handle context with active desktop."""
        strategy = DesktopStrategy()
        task = TaskFrame(goal="test", description="test task")
        context = OrchestrationContext(
            task=task,
            metadata={"desktop": {"active_count": 1}},
        )
        assert await strategy.can_handle(context) is True

    @pytest.mark.asyncio
    async def test_can_handle_with_desktop_keyword(self):
        """Should handle context with 'desktop' in task text."""
        strategy = DesktopStrategy()
        task = TaskFrame(goal="automate desktop", description="test task")
        context = OrchestrationContext(task=task, metadata={})
        assert await strategy.can_handle(context) is True

    @pytest.mark.asyncio
    async def test_execute_returns_desktop_decision(self):
        """Should return desktop capability decision."""
        strategy = DesktopStrategy()
        task = TaskFrame(goal="automate desktop", description="test task")
        context = OrchestrationContext(task=task, metadata={})
        decision = await strategy.execute(context)
        assert decision.name == "desktop"
        assert decision.reason == "desktop context detected"

    def test_priority(self):
        """Should have priority 2."""
        strategy = DesktopStrategy()
        assert strategy.priority == 2


class TestWorkflowStrategy:
    """Tests for WorkflowStrategy."""

    @pytest.mark.asyncio
    async def test_can_handle_with_workflow_context(self):
        """Should handle context with workflow metadata."""
        strategy = WorkflowStrategy()
        task = TaskFrame(goal="test", description="test task")
        context = OrchestrationContext(
            task=task,
            metadata={"workflow": {"id": "wf123"}},
        )
        assert await strategy.can_handle(context) is True

    @pytest.mark.asyncio
    async def test_cannot_handle_without_workflow(self):
        """Should not handle context without workflow."""
        strategy = WorkflowStrategy()
        task = TaskFrame(goal="test", description="test task")
        context = OrchestrationContext(task=task, metadata={})
        assert await strategy.can_handle(context) is False

    @pytest.mark.asyncio
    async def test_execute_returns_workflow_decision(self):
        """Should return workflow capability decision."""
        strategy = WorkflowStrategy()
        task = TaskFrame(goal="test", description="test task")
        context = OrchestrationContext(
            task=task,
            metadata={"workflow": {"id": "wf123"}},
        )
        decision = await strategy.execute(context)
        assert decision.name == "workflow"
        assert decision.reason == "workflow context detected"

    def test_priority(self):
        """Should have priority 3."""
        strategy = WorkflowStrategy()
        assert strategy.priority == 3


class TestMemoryStrategy:
    """Tests for MemoryStrategy."""

    @pytest.mark.asyncio
    async def test_can_handle_with_memory_keyword(self):
        """Should handle context with memory-related keywords."""
        strategy = MemoryStrategy()
        task = TaskFrame(goal="remember this", description="test task")
        context = OrchestrationContext(task=task, metadata={})
        assert await strategy.can_handle(context) is True

    @pytest.mark.asyncio
    async def test_can_handle_with_recall_keyword(self):
        """Should handle context with recall keyword."""
        strategy = MemoryStrategy()
        task = TaskFrame(goal="test", description="recall previous data")
        context = OrchestrationContext(task=task, metadata={})
        assert await strategy.can_handle(context) is True

    @pytest.mark.asyncio
    async def test_cannot_handle_without_memory_keywords(self):
        """Should not handle context without memory keywords."""
        strategy = MemoryStrategy()
        task = TaskFrame(goal="test", description="test task")
        context = OrchestrationContext(task=task, metadata={})
        assert await strategy.can_handle(context) is False

    @pytest.mark.asyncio
    async def test_execute_returns_memory_decision(self):
        """Should return memory capability decision."""
        strategy = MemoryStrategy()
        task = TaskFrame(goal="remember this", description="test task")
        context = OrchestrationContext(task=task, metadata={})
        decision = await strategy.execute(context)
        assert decision.name == "memory"
        assert decision.reason == "memory intent detected"

    def test_priority(self):
        """Should have priority 4."""
        strategy = MemoryStrategy()
        assert strategy.priority == 4


class TestObservabilityStrategy:
    """Tests for ObservabilityStrategy."""

    @pytest.mark.asyncio
    async def test_can_handle_with_trace_keyword(self):
        """Should handle context with trace keyword."""
        strategy = ObservabilityStrategy()
        task = TaskFrame(goal="trace execution", description="test task")
        context = OrchestrationContext(task=task, metadata={})
        assert await strategy.can_handle(context) is True

    @pytest.mark.asyncio
    async def test_can_handle_with_audit_keyword(self):
        """Should handle context with audit keyword."""
        strategy = ObservabilityStrategy()
        task = TaskFrame(goal="test", description="audit the system")
        context = OrchestrationContext(task=task, metadata={})
        assert await strategy.can_handle(context) is True

    @pytest.mark.asyncio
    async def test_can_handle_with_observe_keyword(self):
        """Should handle context with observe keyword."""
        strategy = ObservabilityStrategy()
        task = TaskFrame(goal="observe", description="test task")
        context = OrchestrationContext(task=task, metadata={})
        assert await strategy.can_handle(context) is True

    @pytest.mark.asyncio
    async def test_can_handle_with_report_keyword(self):
        """Should handle context with report keyword."""
        strategy = ObservabilityStrategy()
        task = TaskFrame(goal="test", description="generate report")
        context = OrchestrationContext(task=task, metadata={})
        assert await strategy.can_handle(context) is True

    @pytest.mark.asyncio
    async def test_execute_returns_observe_decision(self):
        """Should return observability capability decision."""
        strategy = ObservabilityStrategy()
        task = TaskFrame(goal="trace execution", description="test task")
        context = OrchestrationContext(task=task, metadata={})
        decision = await strategy.execute(context)
        assert decision.name == "observe"
        assert decision.reason == "observability intent detected"

    def test_priority(self):
        """Should have priority 5."""
        strategy = ObservabilityStrategy()
        assert strategy.priority == 5


class TestDefaultAgentStrategy:
    """Tests for DefaultAgentStrategy."""

    @pytest.mark.asyncio
    async def test_always_handles(self):
        """Should always handle any context."""
        strategy = DefaultAgentStrategy()
        task = TaskFrame(goal="test", description="test task")
        context = OrchestrationContext(task=task, metadata={})
        assert await strategy.can_handle(context) is True

    @pytest.mark.asyncio
    async def test_execute_returns_agent_decision(self):
        """Should return default agent capability decision."""
        strategy = DefaultAgentStrategy()
        task = TaskFrame(goal="test", description="test task")
        context = OrchestrationContext(task=task, metadata={})
        decision = await strategy.execute(context)
        assert decision.name == "agent"
        assert decision.reason == "default agent execution"

    def test_priority(self):
        """Should have lowest priority."""
        strategy = DefaultAgentStrategy()
        assert strategy.priority == 999


class TestCapabilityRegistry:
    """Tests for CapabilityRegistry."""

    def test_initialization_registers_defaults(self):
        """Should register default strategies on initialization."""
        registry = CapabilityRegistry()
        strategies = registry.get_strategies()
        assert len(strategies) == 7
        assert isinstance(strategies[0], ApprovalStrategy)
        assert isinstance(strategies[-1], DefaultAgentStrategy)

    def test_strategies_sorted_by_priority(self):
        """Should maintain strategies sorted by priority."""
        registry = CapabilityRegistry()
        strategies = registry.get_strategies()
        priorities = [s.priority for s in strategies]
        assert priorities == sorted(priorities)

    def test_register_custom_strategy(self):
        """Should register custom strategies."""
        registry = CapabilityRegistry()
        initial_count = len(registry.get_strategies())

        class CustomStrategy(CapabilityStrategy):
            @property
            def priority(self) -> int:
                return 10

            async def can_handle(self, context: OrchestrationContext) -> bool:
                return False

            async def execute(self, context: OrchestrationContext) -> CapabilityDecision:
                return CapabilityDecision(name="custom", reason="custom strategy")

        registry.register(CustomStrategy())
        assert len(registry.get_strategies()) == initial_count + 1

    def test_unregister_strategy(self):
        """Should unregister strategies by name."""
        registry = CapabilityRegistry()
        initial_count = len(registry.get_strategies())
        removed = registry.unregister("BrowserStrategy")
        assert removed is True
        assert len(registry.get_strategies()) == initial_count - 1

    def test_unregister_nonexistent_strategy(self):
        """Should return False when unregistering nonexistent strategy."""
        registry = CapabilityRegistry()
        removed = registry.unregister("NonexistentStrategy")
        assert removed is False

    @pytest.mark.asyncio
    async def test_route_to_first_matching_strategy(self):
        """Should route to first strategy that can handle context."""
        registry = CapabilityRegistry()
        task = TaskFrame(goal="open browser", description="test task")
        context = OrchestrationContext(task=task, metadata={})
        decision = await registry.route(context)
        assert decision.name == "browser"

    @pytest.mark.asyncio
    async def test_route_respects_priority(self):
        """Should route based on strategy priority."""
        registry = CapabilityRegistry()
        task = TaskFrame(goal="test", description="test task", requires_approval=True)
        context = OrchestrationContext(
            task=task,
            metadata={"browser": {"active_count": 1}},
        )
        decision = await registry.route(context)
        assert decision.name == "approval"  # Approval has higher priority

    @pytest.mark.asyncio
    async def test_route_to_default_agent(self):
        """Should route to default agent when no other strategy matches."""
        registry = CapabilityRegistry()
        task = TaskFrame(goal="generic task", description="test task")
        context = OrchestrationContext(task=task, metadata={})
        decision = await registry.route(context)
        assert decision.name == "agent"

    def test_clear_strategies(self):
        """Should clear all registered strategies."""
        registry = CapabilityRegistry()
        registry.clear()
        assert len(registry.get_strategies()) == 0

    @pytest.mark.asyncio
    async def test_route_raises_when_no_strategies(self):
        """Should raise ValueError when no strategies can handle context."""
        registry = CapabilityRegistry()
        registry.clear()
        task = TaskFrame(goal="test", description="test task")
        context = OrchestrationContext(task=task, metadata={})
        with pytest.raises(ValueError, match="No capability strategy found"):
            await registry.route(context)


class TestCapabilityRouterIntegration:
    """Integration tests for CapabilityRouter with strategies."""

    @pytest.mark.asyncio
    async def test_router_uses_registry(self):
        """Should use registry for routing."""
        from backend.app.core.orchestrator import CapabilityRouter

        router = CapabilityRouter()
        task = TaskFrame(goal="open browser", description="test task")
        context = OrchestrationContext(task=task, metadata={})
        decision = await router.route(context)
        assert decision.name == "browser"

    @pytest.mark.asyncio
    async def test_router_with_custom_registry(self):
        """Should accept custom registry."""
        from backend.app.core.orchestrator import CapabilityRouter

        registry = CapabilityRegistry()
        router = CapabilityRouter(registry=registry)
        assert router.get_registry() is registry

    def test_router_register_strategy(self):
        """Should allow registering strategies."""
        from backend.app.core.orchestrator import CapabilityRouter

        router = CapabilityRouter()

        class CustomStrategy(CapabilityStrategy):
            @property
            def priority(self) -> int:
                return 10

            async def can_handle(self, context: OrchestrationContext) -> bool:
                return False

            async def execute(self, context: OrchestrationContext) -> CapabilityDecision:
                return CapabilityDecision(name="custom", reason="custom")

        router.register_strategy(CustomStrategy())
        strategies = router.get_registry().get_strategies()
        assert any(isinstance(s, CustomStrategy) for s in strategies)


class TestStrategyMetadata:
    """Tests for strategy metadata handling."""

    @pytest.mark.asyncio
    async def test_approval_strategy_includes_all_contexts(self):
        """Should include all context metadata in decision."""
        strategy = ApprovalStrategy()
        task = TaskFrame(goal="test", description="test task", requires_approval=True)
        context = OrchestrationContext(
            task=task,
            metadata={
                "approval": {"pending_count": 1},
                "browser": {"active_count": 1},
                "workflow": {"id": "wf123"},
                "desktop": {"active_count": 1},
            },
        )
        decision = await strategy.execute(context)
        assert "approval" in decision.metadata
        assert "browser" in decision.metadata
        assert "workflow" in decision.metadata
        assert "desktop" in decision.metadata

    @pytest.mark.asyncio
    async def test_default_agent_includes_task_data(self):
        """Should include task data in default agent decision."""
        strategy = DefaultAgentStrategy()
        task = TaskFrame(goal="test goal", description="test description")
        context = OrchestrationContext(task=task, metadata={})
        decision = await strategy.execute(context)
        assert "task" in decision.metadata
        assert decision.metadata["task"]["goal"] == "test goal"
