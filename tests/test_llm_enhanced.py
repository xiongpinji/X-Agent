"""Comprehensive tests for enhanced LLM routing system."""

import pytest
from datetime import datetime, timedelta

from backend.app.core.llm.selector import (
    ModelSelector,
    SelectionContext,
    TaskType,
    SelectionStrategy,
    ModelProfile,
)
from backend.app.core.llm.cost_optimizer import (
    CostTracker,
    CostOptimizer,
    TokenEstimator,
)

# 注：fallback/streaming/prompt_optimizer/monitor 四类测试已随死代码归档
# （archive/dead_code_2026-08/tests/test_llm_enhanced_dead.py）


class TestModelSelector:
    """Test model selection."""

    def test_selector_initialization(self):
        """Test selector initializes with default models."""
        selector = ModelSelector()
        assert len(selector.models) > 0
        assert "gpt-4o" in selector.models
        assert "deepseek-chat" in selector.models

    def test_cost_optimized_selection(self):
        """Test cost-optimized model selection."""
        selector = ModelSelector()
        context = SelectionContext(
            strategy=SelectionStrategy.COST_OPTIMIZED,
            input_tokens=1000,
            expected_output_tokens=500,
        )
        result = selector.select(context)
        assert result.selected_model is not None
        assert result.confidence > 0

    def test_performance_optimized_selection(self):
        """Test performance-optimized selection."""
        selector = ModelSelector()
        context = SelectionContext(
            strategy=SelectionStrategy.PERFORMANCE_OPTIMIZED,
            input_tokens=1000,
        )
        result = selector.select(context)
        assert result.selected_model is not None
        assert result.quality_score > 0

    def test_latency_optimized_selection(self):
        """Test latency-optimized selection."""
        selector = ModelSelector()
        context = SelectionContext(
            strategy=SelectionStrategy.LATENCY_OPTIMIZED,
            input_tokens=1000,
        )
        result = selector.select(context)
        assert result.selected_model is not None
        assert result.estimated_latency_ms > 0

    def test_budget_constraint(self):
        """Test budget constraint filtering."""
        selector = ModelSelector()
        context = SelectionContext(
            strategy=SelectionStrategy.COST_OPTIMIZED,
            budget_usd=0.001,  # Very low budget
            input_tokens=1000,
            expected_output_tokens=500,
        )
        result = selector.select(context)
        assert result.estimated_cost <= 0.001

    def test_task_type_filtering(self):
        """Test task type filtering."""
        selector = ModelSelector()
        context = SelectionContext(
            task_type=TaskType.CODE_GENERATION,
            strategy=SelectionStrategy.PERFORMANCE_OPTIMIZED,
        )
        result = selector.select(context)
        assert result.selected_model is not None

    def test_performance_recording(self):
        """Test recording model performance."""
        selector = ModelSelector()
        selector.record_performance(
            "gpt-4o",
            success=True,
            latency_ms=500,
            tokens_used=1000,
            quality_score=0.95,
        )
        # _performance_history is a real attribute on ModelSelector
        assert hasattr(selector, "_performance_history")
        assert isinstance(selector._performance_history, dict)


class TestCostOptimizer:
    """Test cost optimization."""

    def test_token_estimation(self):
        """Test token estimation."""
        text = "Hello world, this is a test."
        tokens = TokenEstimator.estimate_input_tokens(text)
        assert tokens > 0

    def test_cost_tracking(self):
        """Test cost tracking."""
        tracker = CostTracker()
        tracker.record_call(
            model="gpt-4o",
            provider="openai",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.01,
            success=True,
            latency_ms=500,
        )
        total_cost = tracker.get_total_cost(hours=24)
        assert total_cost == 0.01

    def test_cost_by_model(self):
        """Test cost breakdown by model."""
        tracker = CostTracker()
        tracker.record_call(
            model="gpt-4o",
            provider="openai",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.01,
            success=True,
            latency_ms=500,
        )
        tracker.record_call(
            model="gpt-4o-mini",
            provider="openai",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.001,
            success=True,
            latency_ms=300,
        )
        costs = tracker.get_cost_by_model(hours=24)
        assert costs["gpt-4o"] == 0.01
        assert costs["gpt-4o-mini"] == 0.001

    def test_success_rate(self):
        """Test success rate calculation."""
        tracker = CostTracker()
        tracker.record_call(
            model="gpt-4o",
            provider="openai",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.01,
            success=True,
            latency_ms=500,
        )
        tracker.record_call(
            model="gpt-4o",
            provider="openai",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.01,
            success=False,
            latency_ms=500,
        )
        success_rate = tracker.get_success_rate(hours=24)
        assert success_rate == 0.5


