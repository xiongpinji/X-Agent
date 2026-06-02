"""Intelligent model selection based on task characteristics and performance."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import random
from datetime import datetime, timedelta


class TaskType(Enum):
    """Task classification for model selection."""

    SIMPLE_QA = "simple_qa"  # Simple question answering
    COMPLEX_REASONING = "complex_reasoning"  # Multi-step reasoning
    CODE_GENERATION = "code_generation"  # Code writing and analysis
    CREATIVE = "creative"  # Creative writing and brainstorming
    ANALYSIS = "analysis"  # Data analysis and insights
    TRANSLATION = "translation"  # Language translation
    SUMMARIZATION = "summarization"  # Text summarization
    UNKNOWN = "unknown"  # Unknown task type


class SelectionStrategy(Enum):
    """Model selection strategies."""

    COST_OPTIMIZED = "cost_optimized"  # Minimize cost
    PERFORMANCE_OPTIMIZED = "performance_optimized"  # Maximize quality
    BALANCED = "balanced"  # Balance cost and performance
    LATENCY_OPTIMIZED = "latency_optimized"  # Minimize latency
    AVAILABILITY = "availability"  # Maximize availability
    A_B_TEST = "a_b_test"  # A/B testing


@dataclass
class ModelProfile:
    """Profile of a model's capabilities and costs."""

    name: str
    provider: str
    cost_per_1k_input: float  # USD per 1K input tokens
    cost_per_1k_output: float  # USD per 1K output tokens
    latency_ms: float  # Average latency in milliseconds
    quality_score: float  # Quality score 0-100
    max_tokens: int  # Maximum context length
    supported_tasks: set[TaskType] = field(default_factory=set)
    availability: float = 0.99  # Uptime percentage
    rate_limit_rpm: int = 3500  # Requests per minute
    rate_limit_tpm: int = 90000  # Tokens per minute

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for a request."""
        input_cost = (input_tokens / 1000) * self.cost_per_1k_input
        output_cost = (output_tokens / 1000) * self.cost_per_1k_output
        return input_cost + output_cost


@dataclass
class SelectionContext:
    """Context for model selection decision."""

    task_type: TaskType = TaskType.UNKNOWN
    strategy: SelectionStrategy = SelectionStrategy.BALANCED
    budget_usd: Optional[float] = None
    max_latency_ms: Optional[float] = None
    required_quality_score: float = 0.0
    input_tokens: int = 0
    expected_output_tokens: int = 100
    prefer_providers: list[str] = field(default_factory=list)
    avoid_providers: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SelectionResult:
    """Result of model selection."""

    selected_model: str
    provider: str
    estimated_cost: float
    estimated_latency_ms: float
    quality_score: float
    confidence: float  # 0-1, how confident we are in this selection
    reason: str
    alternatives: list[tuple[str, float]] = field(default_factory=list)  # (model_name, score)


class ModelSelector:
    """Intelligent model selector based on task characteristics and constraints."""

    def __init__(self):
        """Initialize model selector with default model profiles."""
        self.models: dict[str, ModelProfile] = {}
        self._performance_history: dict[str, list[dict[str, Any]]] = {}
        self._ab_test_assignments: dict[str, str] = {}
        self._initialize_default_models()

    def _initialize_default_models(self) -> None:
        """Initialize default model profiles."""
        # OpenAI models
        self.register_model(ModelProfile(
            name="gpt-4o",
            provider="openai",
            cost_per_1k_input=0.005,
            cost_per_1k_output=0.015,
            latency_ms=800,
            quality_score=95,
            max_tokens=128000,
            supported_tasks={
                TaskType.COMPLEX_REASONING,
                TaskType.CODE_GENERATION,
                TaskType.ANALYSIS,
                TaskType.CREATIVE,
            },
            availability=0.999,
        ))

        self.register_model(ModelProfile(
            name="gpt-4o-mini",
            provider="openai",
            cost_per_1k_input=0.00015,
            cost_per_1k_output=0.0006,
            latency_ms=400,
            quality_score=85,
            max_tokens=128000,
            supported_tasks={
                TaskType.SIMPLE_QA,
                TaskType.SUMMARIZATION,
                TaskType.TRANSLATION,
            },
            availability=0.999,
        ))

        # DeepSeek models
        self.register_model(ModelProfile(
            name="deepseek-chat",
            provider="deepseek",
            cost_per_1k_input=0.0014,
            cost_per_1k_output=0.0042,
            latency_ms=600,
            quality_score=88,
            max_tokens=64000,
            supported_tasks={
                TaskType.COMPLEX_REASONING,
                TaskType.CODE_GENERATION,
                TaskType.ANALYSIS,
            },
            availability=0.98,
        ))

        self.register_model(ModelProfile(
            name="deepseek-coder",
            provider="deepseek",
            cost_per_1k_input=0.0014,
            cost_per_1k_output=0.0042,
            latency_ms=700,
            quality_score=92,
            max_tokens=64000,
            supported_tasks={
                TaskType.CODE_GENERATION,
            },
            availability=0.98,
        ))

    def register_model(self, profile: ModelProfile) -> None:
        """Register a new model profile."""
        self.models[profile.name] = profile
        self._performance_history[profile.name] = []

    def select(self, context: SelectionContext) -> SelectionResult:
        """Select the best model based on context."""
        candidates = self._filter_candidates(context)

        if not candidates:
            # Fallback to best available model
            candidates = list(self.models.values())

        if context.strategy == SelectionStrategy.A_B_TEST:
            return self._select_ab_test(candidates, context)
        elif context.strategy == SelectionStrategy.COST_OPTIMIZED:
            return self._select_cost_optimized(candidates, context)
        elif context.strategy == SelectionStrategy.PERFORMANCE_OPTIMIZED:
            return self._select_performance_optimized(candidates, context)
        elif context.strategy == SelectionStrategy.LATENCY_OPTIMIZED:
            return self._select_latency_optimized(candidates, context)
        elif context.strategy == SelectionStrategy.AVAILABILITY:
            return self._select_availability(candidates, context)
        else:  # BALANCED
            return self._select_balanced(candidates, context)

    def _filter_candidates(self, context: SelectionContext) -> list[ModelProfile]:
        """Filter models based on constraints."""
        candidates = []

        for model in self.models.values():
            # Check provider preferences
            if context.avoid_providers and model.provider in context.avoid_providers:
                continue

            if context.prefer_providers and model.provider not in context.prefer_providers:
                continue

            # Check task support
            if context.task_type != TaskType.UNKNOWN:
                if model.supported_tasks and context.task_type not in model.supported_tasks:
                    continue

            # Check budget
            if context.budget_usd is not None:
                estimated_cost = model.estimate_cost(
                    context.input_tokens,
                    context.expected_output_tokens
                )
                if estimated_cost > context.budget_usd:
                    continue

            # Check latency requirement
            if context.max_latency_ms is not None:
                if model.latency_ms > context.max_latency_ms:
                    continue

            # Check quality requirement
            if model.quality_score < context.required_quality_score:
                continue

            # Check context length
            if context.input_tokens > model.max_tokens:
                continue

            candidates.append(model)

        return candidates

    def _select_cost_optimized(
        self,
        candidates: list[ModelProfile],
        context: SelectionContext
    ) -> SelectionResult:
        """Select model with lowest cost."""
        if not candidates:
            return self._create_fallback_result()

        best_model = min(
            candidates,
            key=lambda m: m.estimate_cost(
                context.input_tokens,
                context.expected_output_tokens
            )
        )

        cost = best_model.estimate_cost(
            context.input_tokens,
            context.expected_output_tokens
        )

        alternatives = [
            (m.name, m.estimate_cost(context.input_tokens, context.expected_output_tokens))
            for m in sorted(candidates, key=lambda x: x.estimate_cost(
                context.input_tokens,
                context.expected_output_tokens
            ))[:3]
        ]

        return SelectionResult(
            selected_model=best_model.name,
            provider=best_model.provider,
            estimated_cost=cost,
            estimated_latency_ms=best_model.latency_ms,
            quality_score=best_model.quality_score,
            confidence=0.95,
            reason=f"Selected for lowest cost: ${cost:.4f}",
            alternatives=alternatives,
        )

    def _select_performance_optimized(
        self,
        candidates: list[ModelProfile],
        context: SelectionContext
    ) -> SelectionResult:
        """Select model with highest quality."""
        if not candidates:
            return self._create_fallback_result()

        best_model = max(candidates, key=lambda m: m.quality_score)
        cost = best_model.estimate_cost(
            context.input_tokens,
            context.expected_output_tokens
        )

        alternatives = [
            (m.name, m.quality_score)
            for m in sorted(candidates, key=lambda x: x.quality_score, reverse=True)[:3]
        ]

        return SelectionResult(
            selected_model=best_model.name,
            provider=best_model.provider,
            estimated_cost=cost,
            estimated_latency_ms=best_model.latency_ms,
            quality_score=best_model.quality_score,
            confidence=0.95,
            reason=f"Selected for highest quality: {best_model.quality_score}/100",
            alternatives=alternatives,
        )

    def _select_latency_optimized(
        self,
        candidates: list[ModelProfile],
        context: SelectionContext
    ) -> SelectionResult:
        """Select model with lowest latency."""
        if not candidates:
            return self._create_fallback_result()

        best_model = min(candidates, key=lambda m: m.latency_ms)
        cost = best_model.estimate_cost(
            context.input_tokens,
            context.expected_output_tokens
        )

        alternatives = [
            (m.name, m.latency_ms)
            for m in sorted(candidates, key=lambda x: x.latency_ms)[:3]
        ]

        return SelectionResult(
            selected_model=best_model.name,
            provider=best_model.provider,
            estimated_cost=cost,
            estimated_latency_ms=best_model.latency_ms,
            quality_score=best_model.quality_score,
            confidence=0.95,
            reason=f"Selected for lowest latency: {best_model.latency_ms}ms",
            alternatives=alternatives,
        )

    def _select_availability(
        self,
        candidates: list[ModelProfile],
        context: SelectionContext
    ) -> SelectionResult:
        """Select model with highest availability."""
        if not candidates:
            return self._create_fallback_result()

        best_model = max(candidates, key=lambda m: m.availability)
        cost = best_model.estimate_cost(
            context.input_tokens,
            context.expected_output_tokens
        )

        alternatives = [
            (m.name, m.availability)
            for m in sorted(candidates, key=lambda x: x.availability, reverse=True)[:3]
        ]

        return SelectionResult(
            selected_model=best_model.name,
            provider=best_model.provider,
            estimated_cost=cost,
            estimated_latency_ms=best_model.latency_ms,
            quality_score=best_model.quality_score,
            confidence=0.95,
            reason=f"Selected for highest availability: {best_model.availability*100:.2f}%",
            alternatives=alternatives,
        )

    def _select_balanced(
        self,
        candidates: list[ModelProfile],
        context: SelectionContext
    ) -> SelectionResult:
        """Select model balancing cost, quality, and latency."""
        if not candidates:
            return self._create_fallback_result()

        # Calculate composite score
        def score_model(m: ModelProfile) -> float:
            cost = m.estimate_cost(
                context.input_tokens,
                context.expected_output_tokens
            )
            # Normalize scores (lower is better for cost and latency)
            cost_score = 1.0 / (1.0 + cost)  # Inverse cost
            quality_score = m.quality_score / 100.0
            latency_score = 1.0 / (1.0 + m.latency_ms / 1000.0)  # Inverse latency

            # Weighted average
            return (cost_score * 0.3 + quality_score * 0.5 + latency_score * 0.2)

        best_model = max(candidates, key=score_model)
        cost = best_model.estimate_cost(
            context.input_tokens,
            context.expected_output_tokens
        )

        alternatives = [
            (m.name, score_model(m))
            for m in sorted(candidates, key=score_model, reverse=True)[:3]
        ]

        return SelectionResult(
            selected_model=best_model.name,
            provider=best_model.provider,
            estimated_cost=cost,
            estimated_latency_ms=best_model.latency_ms,
            quality_score=best_model.quality_score,
            confidence=0.90,
            reason="Selected for balanced cost, quality, and latency",
            alternatives=alternatives,
        )

    def _select_ab_test(
        self,
        candidates: list[ModelProfile],
        context: SelectionContext
    ) -> SelectionResult:
        """Select model for A/B testing."""
        if not candidates:
            return self._create_fallback_result()

        # Use consistent hashing for same user/session
        session_id = context.metadata.get("session_id", "default")

        if session_id not in self._ab_test_assignments:
            # Randomly assign to one of top 2 models
            top_models = sorted(
                candidates,
                key=lambda m: m.quality_score,
                reverse=True
            )[:2]
            self._ab_test_assignments[session_id] = random.choice(top_models).name

        selected_name = self._ab_test_assignments[session_id]
        best_model = self.models[selected_name]
        cost = best_model.estimate_cost(
            context.input_tokens,
            context.expected_output_tokens
        )

        return SelectionResult(
            selected_model=best_model.name,
            provider=best_model.provider,
            estimated_cost=cost,
            estimated_latency_ms=best_model.latency_ms,
            quality_score=best_model.quality_score,
            confidence=0.85,
            reason="Selected for A/B testing",
            alternatives=[],
        )

    def _create_fallback_result(self) -> SelectionResult:
        """Create fallback result when no candidates available."""
        # Use cheapest available model
        cheapest = min(
            self.models.values(),
            key=lambda m: m.cost_per_1k_input + m.cost_per_1k_output
        )

        return SelectionResult(
            selected_model=cheapest.name,
            provider=cheapest.provider,
            estimated_cost=0.0,
            estimated_latency_ms=cheapest.latency_ms,
            quality_score=cheapest.quality_score,
            confidence=0.5,
            reason="Fallback selection due to no matching candidates",
            alternatives=[],
        )

    def record_performance(
        self,
        model_name: str,
        success: bool,
        latency_ms: float,
        tokens_used: int,
        quality_score: Optional[float] = None,
    ) -> None:
        """Record model performance for future selection."""
        if model_name not in self._performance_history:
            return

        record = {
            "timestamp": datetime.now(),
            "success": success,
            "latency_ms": latency_ms,
            "tokens_used": tokens_used,
            "quality_score": quality_score,
        }

        self._performance_history[model_name].append(record)

        # Keep only last 1000 records
        if len(self._performance_history[model_name]) > 1000:
            self._performance_history[model_name] = self._performance_history[model_name][-1000:]

    def get_model_stats(self, model_name: str) -> dict[str, Any]:
        """Get performance statistics for a model."""
        if model_name not in self._performance_history:
            return {}

        history = self._performance_history[model_name]
        if not history:
            return {}

        # Filter last 24 hours
        cutoff = datetime.now() - timedelta(hours=24)
        recent = [r for r in history if r["timestamp"] > cutoff]

        if not recent:
            return {}

        success_count = sum(1 for r in recent if r["success"])
        success_rate = success_count / len(recent)

        latencies = [r["latency_ms"] for r in recent]
        avg_latency = sum(latencies) / len(latencies)

        return {
            "success_rate": success_rate,
            "avg_latency_ms": avg_latency,
            "total_requests": len(recent),
            "min_latency_ms": min(latencies),
            "max_latency_ms": max(latencies),
        }
