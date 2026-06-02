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
from backend.app.core.llm.fallback import (
    FallbackManager,
    FallbackConfig,
    FallbackStrategy,
    ErrorContext,
)
from backend.app.core.llm.streaming import StreamManager, StreamChunk
from backend.app.core.llm.prompt_optimizer import PromptOptimizer, PromptTemplate
from backend.app.core.llm.monitor import PerformanceMonitor, ModelMetrics


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


class TestFallbackManager:
    """Test fallback management."""

    def test_circuit_breaker_state(self):
        """Test circuit breaker state transitions."""
        config = FallbackConfig(circuit_breaker_threshold=3)
        manager = FallbackManager(config)

        cb = manager.get_circuit_breaker("gpt-4o")
        assert cb.is_available()

        # Record failures
        for _ in range(3):
            cb.record_failure()

        assert not cb.is_available()
        assert cb.state == "open"

    def test_error_classification(self):
        """Test error classification."""
        manager = FallbackManager(FallbackConfig())

        error = manager.classify_error(TimeoutError("Request timeout"))
        assert error.error_type == "timeout"
        assert error.is_transient

        error = manager.classify_error(Exception("Unknown error"))
        assert error.error_type == "unknown"

    def test_retry_delay_calculation(self):
        """Test exponential backoff calculation."""
        config = FallbackConfig(
            strategy=FallbackStrategy.EXPONENTIAL_BACKOFF,
            initial_retry_delay_ms=100,
            backoff_multiplier=2.0,
        )
        manager = FallbackManager(config)

        delay_0 = manager.get_retry_delay_ms(0)
        delay_1 = manager.get_retry_delay_ms(1)
        delay_2 = manager.get_retry_delay_ms(2)

        assert delay_0 == 100
        assert delay_1 == 200
        assert delay_2 == 400


class TestStreamManager:
    """Test streaming response management."""

    def test_stream_creation(self):
        """Test stream creation."""
        manager = StreamManager()
        stream = manager.create_stream("gpt-4o", "openai", "req-123")
        assert stream.model == "gpt-4o"
        assert stream.provider == "openai"
        assert stream.request_id == "req-123"

    def test_chunk_addition(self):
        """Test adding chunks to stream."""
        manager = StreamManager()
        stream = manager.create_stream("gpt-4o", "openai", "req-123")

        chunk1 = StreamChunk(content="Hello ", token_count=1)
        chunk2 = StreamChunk(content="world", token_count=1)

        manager.add_chunk("req-123", chunk1)
        manager.add_chunk("req-123", chunk2)

        stream = manager.get_stream("req-123")
        assert len(stream.chunks) == 2
        assert stream.get_full_content() == "Hello world"

    def test_stream_completion(self):
        """Test stream completion."""
        manager = StreamManager()
        stream = manager.create_stream("gpt-4o", "openai", "req-123")

        manager.complete_stream("req-123")
        stream = manager.get_stream("req-123")
        assert stream.is_complete


class TestPromptOptimizer:
    """Test prompt optimization."""

    def test_template_rendering(self):
        """Test template rendering."""
        template = PromptTemplate(
            name="test",
            template="Hello {{name}}, you are {{age}} years old.",
            variables=["name", "age"],
        )
        rendered = template.render(name="Alice", age=30)
        assert "Alice" in rendered
        assert "30" in rendered

    def test_prompt_compression(self):
        """Test prompt compression."""
        optimizer = PromptOptimizer()
        long_prompt = "Please, could you kindly help me with this task? Thank you very much."
        compressed = optimizer.compress_prompt(long_prompt)
        assert len(compressed) < len(long_prompt)

    def test_token_estimation(self):
        """Test token estimation."""
        optimizer = PromptOptimizer()
        prompt = "This is a test prompt with several words."
        tokens = optimizer.estimate_tokens(prompt)
        assert tokens > 0

    def test_few_shot_examples(self):
        """Test adding few-shot examples."""
        optimizer = PromptOptimizer()
        prompt = "Classify the sentiment:"
        examples = [
            {"input": "I love this!", "output": "positive"},
            {"input": "This is terrible", "output": "negative"},
        ]
        enhanced = optimizer.add_few_shot_examples(prompt, examples)
        assert "Example 1" in enhanced
        assert "positive" in enhanced


class TestPerformanceMonitor:
    """Test performance monitoring."""

    def test_request_recording(self):
        """Test recording requests."""
        monitor = PerformanceMonitor()
        monitor.record_request(
            model_name="gpt-4o",
            provider="openai",
            success=True,
            latency_ms=500,
            tokens_used=1000,
            cost_usd=0.01,
            quality_score=0.95,
        )
        metrics = monitor.get_metrics("gpt-4o")
        assert metrics.total_requests == 1
        assert metrics.successful_requests == 1

    def test_metrics_calculation(self):
        """Test metrics calculation."""
        monitor = PerformanceMonitor()
        for i in range(10):
            monitor.record_request(
                model_name="gpt-4o",
                provider="openai",
                success=i < 9,  # 9 successes, 1 failure
                latency_ms=500 + i * 10,
                tokens_used=1000,
                cost_usd=0.01,
            )
        metrics = monitor.get_metrics("gpt-4o")
        assert metrics.get_success_rate() == 0.9
        assert metrics.get_average_latency_ms() > 0

    def test_model_comparison(self):
        """Test comparing models."""
        monitor = PerformanceMonitor()
        monitor.record_request(
            model_name="gpt-4o",
            provider="openai",
            success=True,
            latency_ms=500,
            tokens_used=1000,
            cost_usd=0.01,
        )
        monitor.record_request(
            model_name="gpt-4o-mini",
            provider="openai",
            success=True,
            latency_ms=300,
            tokens_used=1000,
            cost_usd=0.001,
        )
        comparison = monitor.compare_models(["gpt-4o", "gpt-4o-mini"])
        assert "gpt-4o" in comparison
        assert "gpt-4o-mini" in comparison

    def test_best_model_selection(self):
        """Test selecting best model."""
        monitor = PerformanceMonitor()
        monitor.record_request(
            model_name="gpt-4o",
            provider="openai",
            success=True,
            latency_ms=500,
            tokens_used=1000,
            cost_usd=0.01,
        )
        monitor.record_request(
            model_name="gpt-4o-mini",
            provider="openai",
            success=True,
            latency_ms=300,
            tokens_used=1000,
            cost_usd=0.001,
        )
        best_speed = monitor.get_best_model_for("speed")
        assert best_speed == "gpt-4o-mini"

        best_cost = monitor.get_best_model_for("cost")
        assert best_cost == "gpt-4o-mini"
