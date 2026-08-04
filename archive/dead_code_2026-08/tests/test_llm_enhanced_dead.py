"""归档自 tests/test_llm_enhanced.py（2026-08-04 死代码收敛）

测试对象 fallback/streaming/prompt_optimizer/monitor 已归档至
archive/dead_code_2026-08/backend/app/core/llm/。
"""
import pytest
from datetime import datetime, timedelta

from backend.app.core.llm.fallback import (
    FallbackManager, FallbackStrategy,  # 归档态不可运行，仅作测试对象记录
)
from backend.app.core.llm.streaming import StreamManager, StreamChunk
from backend.app.core.llm.prompt_optimizer import PromptOptimizer, PromptTemplate
from backend.app.core.llm.monitor import PerformanceMonitor, ModelMetrics
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
