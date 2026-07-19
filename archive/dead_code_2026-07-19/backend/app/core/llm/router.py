"""Enhanced LLM router with intelligent selection and optimization."""

from __future__ import annotations

from typing import Any, Optional, AsyncIterator
import asyncio

from .selector import ModelSelector, SelectionContext, TaskType, SelectionStrategy
from .cost_optimizer import CostOptimizer, CostTracker, TokenEstimator
from .fallback import FallbackManager, FallbackConfig, FallbackStrategy
from .streaming import StreamManager, StreamChunk
from .prompt_optimizer import PromptOptimizer
from .monitor import PerformanceMonitor
from .adapters import LLMAdapter, OpenAIAdapter, DeepSeekAdapter, LocalAdapter


class EnhancedLLMRouter:
    """Enhanced LLM router with intelligent selection and optimization."""

    def __init__(
        self,
        selector: Optional[ModelSelector] = None,
        cost_tracker: Optional[CostTracker] = None,
        fallback_config: Optional[FallbackConfig] = None,
        prompt_optimizer: Optional[PromptOptimizer] = None,
        monitor: Optional[PerformanceMonitor] = None,
    ):
        """Initialize enhanced LLM router."""
        self.selector = selector or ModelSelector()
        self.cost_tracker = cost_tracker or CostTracker()
        self.cost_optimizer = CostOptimizer(self.cost_tracker)
        self.fallback_manager = FallbackManager(fallback_config or FallbackConfig())
        self.prompt_optimizer = prompt_optimizer or PromptOptimizer()
        self.monitor = monitor or PerformanceMonitor()
        self.stream_manager = StreamManager()

        self.adapters: dict[str, LLMAdapter] = {}

    def register_adapter(self, adapter: LLMAdapter) -> None:
        """Register an LLM adapter."""
        self.adapters[adapter.model] = adapter

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: Optional[list[dict[str, Any]]] = None,
        task_type: TaskType = TaskType.UNKNOWN,
        strategy: SelectionStrategy = SelectionStrategy.BALANCED,
        budget_usd: Optional[float] = None,
        max_latency_ms: Optional[float] = None,
        optimize_prompt: bool = True,
        **kwargs,
    ) -> dict[str, Any]:
        """Execute a chat request with intelligent routing."""
        # Estimate tokens
        user_message = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"),
            ""
        )
        input_tokens = TokenEstimator.estimate_input_tokens(user_message)
        output_tokens = kwargs.get("expected_output_tokens", 200)

        # Create selection context
        context = SelectionContext(
            task_type=task_type,
            strategy=strategy,
            budget_usd=budget_usd,
            max_latency_ms=max_latency_ms,
            input_tokens=input_tokens,
            expected_output_tokens=output_tokens,
            metadata=kwargs.get("metadata", {}),
        )

        # Select model
        selection = self.selector.select(context)

        # Optimize prompt if requested
        if optimize_prompt:
            optimized_messages = []
            for msg in messages:
                if msg["role"] == "user":
                    optimized_content = self.prompt_optimizer.optimize_for_model(
                        msg["content"],
                        selection.selected_model,
                    )
                    optimized_messages.append({**msg, "content": optimized_content})
                else:
                    optimized_messages.append(msg)
            messages = optimized_messages

        # Get adapter
        adapter = self.adapters.get(selection.selected_model)
        if not adapter:
            raise RuntimeError(f"No adapter for model {selection.selected_model}")

        # Execute request
        try:
            response = await adapter.chat(messages, tools, **kwargs)

            # Record metrics
            self.monitor.record_request(
                model_name=selection.selected_model,
                provider=selection.provider,
                success=True,
                latency_ms=response.latency_ms,
                tokens_used=response.tokens_used,
                cost_usd=selection.estimated_cost,
                quality_score=kwargs.get("quality_score"),
            )

            self.cost_tracker.record_call(
                model=selection.selected_model,
                provider=selection.provider,
                input_tokens=input_tokens,
                output_tokens=response.tokens_used - input_tokens,
                cost_usd=selection.estimated_cost,
                success=True,
                latency_ms=response.latency_ms,
                task_type=task_type.value,
            )

            self.selector.record_performance(
                selection.selected_model,
                success=True,
                latency_ms=response.latency_ms,
                tokens_used=response.tokens_used,
            )

            self.fallback_manager.record_success(selection.selected_model)

            return {
                "content": response.content,
                "tool_calls": response.tool_calls,
                "tokens_used": response.tokens_used,
                "model": response.model,
                "latency_ms": response.latency_ms,
                "cost_usd": selection.estimated_cost,
                "selection_reason": selection.reason,
            }

        except Exception as e:
            # Record error
            self.monitor.record_request(
                model_name=selection.selected_model,
                provider=selection.provider,
                success=False,
                latency_ms=0,
                tokens_used=0,
                cost_usd=0,
            )

            error_context = self.fallback_manager.classify_error(e)
            error_context.model = selection.selected_model
            self.fallback_manager.record_error(error_context)

            raise

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        tools: Optional[list[dict[str, Any]]] = None,
        task_type: TaskType = TaskType.UNKNOWN,
        strategy: SelectionStrategy = SelectionStrategy.BALANCED,
        request_id: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream a chat response."""
        import uuid

        request_id = request_id or str(uuid.uuid4())

        # Estimate tokens
        user_message = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"),
            ""
        )
        input_tokens = TokenEstimator.estimate_input_tokens(user_message)

        # Create selection context
        context = SelectionContext(
            task_type=task_type,
            strategy=strategy,
            input_tokens=input_tokens,
            expected_output_tokens=200,
        )

        # Select model
        selection = self.selector.select(context)

        # Create stream
        stream = self.stream_manager.create_stream(
            model=selection.selected_model,
            provider=selection.provider,
            request_id=request_id,
        )

        # Get adapter
        adapter = self.adapters.get(selection.selected_model)
        if not adapter:
            raise RuntimeError(f"No adapter for model {selection.selected_model}")

        # Stream response
        try:
            async for chunk in adapter.stream_chat(messages, tools, **kwargs):
                self.stream_manager.add_chunk(
                    request_id,
                    StreamChunk(content=chunk, chunk_type="text"),
                )
                yield chunk

            self.stream_manager.complete_stream(request_id)

        except Exception as e:
            self.stream_manager.error_stream(request_id, str(e))
            raise

    def get_cost_report(self, hours: int = 24) -> dict[str, Any]:
        """Get cost report."""
        return self.cost_tracker.get_report(hours)

    def get_performance_report(self, hours: int = 24) -> dict[str, Any]:
        """Get performance report."""
        return self.monitor.get_report(hours)

    def get_optimization_recommendations(self) -> list[dict[str, Any]]:
        """Get optimization recommendations."""
        return self.cost_optimizer.get_cost_optimization_recommendations()

    def get_status(self) -> dict[str, Any]:
        """Get router status."""
        return {
            "models": list(self.adapters.keys()),
            "cost_report": self.get_cost_report(hours=1),
            "performance_report": self.get_performance_report(hours=1),
            "circuit_breakers": self.fallback_manager.get_circuit_breaker_status(),
            "streaming_stats": self.stream_manager.get_stats(),
        }
