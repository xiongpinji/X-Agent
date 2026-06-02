"""
Multi-model manager for intelligent model routing and ensemble.

This module provides intelligent routing of requests to the most suitable LLM
and ensemble methods for combining outputs from multiple models.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol

from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


class ModelType(Enum):
    """Supported model types."""
    GPT4 = "gpt-4"
    GPT4_TURBO = "gpt-4-turbo"
    CLAUDE3_OPUS = "claude-3-opus"
    CLAUDE3_SONNET = "claude-3-sonnet"
    CLAUDE3_HAIKU = "claude-3-haiku"
    GEMINI_PRO = "gemini-pro"
    LLAMA3 = "llama-3"
    MISTRAL = "mistral"
    LOCAL = "local"


class TaskComplexity(Enum):
    """Task complexity levels."""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    VERY_COMPLEX = "very_complex"


class TaskType(Enum):
    """Types of tasks."""
    REASONING = "reasoning"
    CODING = "coding"
    ANALYSIS = "analysis"
    GENERATION = "generation"
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    CLASSIFICATION = "classification"
    PLANNING = "planning"
    VERIFICATION = "verification"


@dataclass
class ModelCapabilities:
    """Capabilities of a model."""
    max_tokens: int
    supports_vision: bool = False
    supports_function_calling: bool = False
    supports_streaming: bool = True
    reasoning_strength: float = 0.5  # 0-1
    coding_strength: float = 0.5  # 0-1
    analysis_strength: float = 0.5  # 0-1
    generation_strength: float = 0.5  # 0-1
    speed: float = 0.5  # 0-1 (higher = faster)
    cost_per_1k_tokens: float = 0.0


@dataclass
class LLMRequest(BaseModel):
    """Request to LLM."""
    task_type: TaskType
    complexity: TaskComplexity
    prompt: str
    system_prompt: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2000
    requires_reasoning: bool = False
    requires_speed: bool = False
    requires_multimodal: bool = False
    requires_function_calling: bool = False
    budget_constraint: Optional[float] = None  # Max cost in dollars
    latency_constraint: Optional[float] = None  # Max latency in seconds
    metadata: Dict[str, Any] = Field(default_factory=dict)


@dataclass
class LLMResponse(BaseModel):
    """Response from LLM."""
    model: str
    content: str
    tokens_used: int
    cost: float
    latency: float
    confidence: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ModelBackend(ABC):
    """Abstract base class for model backends."""

    def __init__(self, model_type: ModelType, capabilities: ModelCapabilities):
        """Initialize model backend.

        Args:
            model_type: Type of model.
            capabilities: Model capabilities.
        """
        self.model_type = model_type
        self.capabilities = capabilities

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate response from model.

        Args:
            request: LLM request.

        Returns:
            LLM response.
        """
        pass

    @abstractmethod
    async def stream_generate(self, request: LLMRequest):
        """Stream response from model.

        Args:
            request: LLM request.

        Yields:
            Response chunks.
        """
        pass


class GPT4Backend(ModelBackend):
    """GPT-4 backend implementation."""

    def __init__(self):
        """Initialize GPT-4 backend."""
        capabilities = ModelCapabilities(
            max_tokens=8192,
            supports_vision=True,
            supports_function_calling=True,
            reasoning_strength=0.95,
            coding_strength=0.9,
            analysis_strength=0.9,
            generation_strength=0.85,
            speed=0.6,
            cost_per_1k_tokens=0.03,
        )
        super().__init__(ModelType.GPT4, capabilities)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate response using GPT-4."""
        # Implementation would call OpenAI API
        logger.info(f"Generating with GPT-4: {request.task_type}")
        # Placeholder implementation
        return LLMResponse(
            model=self.model_type.value,
            content="GPT-4 response",
            tokens_used=100,
            cost=0.003,
            latency=1.5,
        )

    async def stream_generate(self, request: LLMRequest):
        """Stream response using GPT-4."""
        # Implementation would stream from OpenAI API
        yield "GPT-4 streaming response"


class Claude3Backend(ModelBackend):
    """Claude 3 backend implementation."""

    def __init__(self, variant: str = "opus"):
        """Initialize Claude 3 backend.

        Args:
            variant: Claude 3 variant (opus, sonnet, haiku).
        """
        self.variant = variant
        model_type_map = {
            "opus": ModelType.CLAUDE3_OPUS,
            "sonnet": ModelType.CLAUDE3_SONNET,
            "haiku": ModelType.CLAUDE3_HAIKU,
        }
        model_type = model_type_map.get(variant, ModelType.CLAUDE3_OPUS)

        capabilities = ModelCapabilities(
            max_tokens=200000,
            supports_vision=True,
            supports_function_calling=True,
            reasoning_strength=0.92,
            coding_strength=0.88,
            analysis_strength=0.92,
            generation_strength=0.9,
            speed=0.7 if variant == "haiku" else 0.5,
            cost_per_1k_tokens=0.015 if variant == "haiku" else 0.03,
        )
        super().__init__(model_type, capabilities)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate response using Claude 3."""
        logger.info(f"Generating with Claude 3 ({self.variant}): {request.task_type}")
        # Placeholder implementation
        return LLMResponse(
            model=self.model_type.value,
            content="Claude 3 response",
            tokens_used=150,
            cost=0.0045,
            latency=1.2,
        )

    async def stream_generate(self, request: LLMRequest):
        """Stream response using Claude 3."""
        yield "Claude 3 streaming response"


class GeminiBackend(ModelBackend):
    """Google Gemini backend implementation."""

    def __init__(self):
        """Initialize Gemini backend."""
        capabilities = ModelCapabilities(
            max_tokens=32768,
            supports_vision=True,
            supports_function_calling=True,
            reasoning_strength=0.85,
            coding_strength=0.82,
            analysis_strength=0.88,
            generation_strength=0.87,
            speed=0.8,
            cost_per_1k_tokens=0.0005,
        )
        super().__init__(ModelType.GEMINI_PRO, capabilities)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate response using Gemini."""
        logger.info(f"Generating with Gemini: {request.task_type}")
        return LLMResponse(
            model=self.model_type.value,
            content="Gemini response",
            tokens_used=120,
            cost=0.00006,
            latency=0.8,
        )

    async def stream_generate(self, request: LLMRequest):
        """Stream response using Gemini."""
        yield "Gemini streaming response"


class LlamaBackend(ModelBackend):
    """Llama backend implementation."""

    def __init__(self):
        """Initialize Llama backend."""
        capabilities = ModelCapabilities(
            max_tokens=4096,
            supports_vision=False,
            supports_function_calling=False,
            reasoning_strength=0.7,
            coding_strength=0.75,
            analysis_strength=0.72,
            generation_strength=0.78,
            speed=0.9,
            cost_per_1k_tokens=0.0,  # Local model
        )
        super().__init__(ModelType.LLAMA3, capabilities)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate response using Llama."""
        logger.info(f"Generating with Llama: {request.task_type}")
        return LLMResponse(
            model=self.model_type.value,
            content="Llama response",
            tokens_used=100,
            cost=0.0,
            latency=2.0,
        )

    async def stream_generate(self, request: LLMRequest):
        """Stream response using Llama."""
        yield "Llama streaming response"


class MultiModelManager:
    """Manages multiple LLM models with intelligent routing and ensemble."""

    def __init__(self):
        """Initialize multi-model manager."""
        self.models: Dict[ModelType, ModelBackend] = {
            ModelType.GPT4: GPT4Backend(),
            ModelType.CLAUDE3_OPUS: Claude3Backend("opus"),
            ModelType.CLAUDE3_SONNET: Claude3Backend("sonnet"),
            ModelType.CLAUDE3_HAIKU: Claude3Backend("haiku"),
            ModelType.GEMINI_PRO: GeminiBackend(),
            ModelType.LLAMA3: LlamaBackend(),
        }
        self.routing_history: List[Dict[str, Any]] = []

    def _score_model(self, model: ModelBackend, request: LLMRequest) -> float:
        """Score a model for a given request.

        Args:
            model: Model to score.
            request: LLM request.

        Returns:
            Score between 0 and 1 (higher is better).
        """
        score = 0.0
        weights = {
            "reasoning": 0.25,
            "coding": 0.25,
            "analysis": 0.2,
            "generation": 0.15,
            "speed": 0.15,
        }

        # Task-specific scoring
        if request.task_type == TaskType.REASONING:
            score += model.capabilities.reasoning_strength * weights["reasoning"]
        elif request.task_type == TaskType.CODING:
            score += model.capabilities.coding_strength * weights["coding"]
        elif request.task_type == TaskType.ANALYSIS:
            score += model.capabilities.analysis_strength * weights["analysis"]
        elif request.task_type == TaskType.GENERATION:
            score += model.capabilities.generation_strength * weights["generation"]

        # Speed consideration
        if request.requires_speed:
            score += model.capabilities.speed * weights["speed"]

        # Capability requirements
        if request.requires_multimodal and not model.capabilities.supports_vision:
            score *= 0.5
        if request.requires_function_calling and not model.capabilities.supports_function_calling:
            score *= 0.7

        # Budget constraint
        if request.budget_constraint:
            estimated_cost = (request.max_tokens / 1000) * model.capabilities.cost_per_1k_tokens
            if estimated_cost > request.budget_constraint:
                score *= 0.3

        return min(score, 1.0)

    async def route_request(self, request: LLMRequest) -> ModelType:
        """Route request to the best model.

        Args:
            request: LLM request.

        Returns:
            Selected model type.
        """
        scores = {}
        for model_type, model in self.models.items():
            scores[model_type] = self._score_model(model, request)

        # Select model with highest score
        best_model = max(scores, key=scores.get)

        # Log routing decision
        self.routing_history.append({
            "task_type": request.task_type,
            "selected_model": best_model,
            "scores": scores,
        })

        logger.info(f"Routed {request.task_type} to {best_model.value}")
        return best_model

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate response using best model.

        Args:
            request: LLM request.

        Returns:
            LLM response.
        """
        model_type = await self.route_request(request)
        model = self.models[model_type]
        return await model.generate(request)

    async def ensemble(
        self,
        request: LLMRequest,
        num_models: int = 3,
        aggregation_method: str = "voting"
    ) -> LLMResponse:
        """Generate responses from multiple models and aggregate.

        Args:
            request: LLM request.
            num_models: Number of models to use.
            aggregation_method: How to aggregate responses (voting, averaging, etc).

        Returns:
            Aggregated LLM response.
        """
        # Score all models
        scores = {}
        for model_type, model in self.models.items():
            scores[model_type] = self._score_model(model, request)

        # Select top N models
        top_models = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:num_models]
        selected_models = [self.models[model_type] for model_type, _ in top_models]

        # Generate responses in parallel
        responses = await asyncio.gather(*[
            model.generate(request)
            for model in selected_models
        ])

        # Aggregate responses
        if aggregation_method == "voting":
            aggregated_content = self._aggregate_by_voting(responses)
        elif aggregation_method == "averaging":
            aggregated_content = self._aggregate_by_averaging(responses)
        else:
            aggregated_content = self._aggregate_by_consensus(responses)

        # Calculate aggregate metrics
        total_tokens = sum(r.tokens_used for r in responses)
        total_cost = sum(r.cost for r in responses)
        avg_latency = sum(r.latency for r in responses) / len(responses)
        avg_confidence = sum(r.confidence for r in responses) / len(responses)

        return LLMResponse(
            model="ensemble",
            content=aggregated_content,
            tokens_used=total_tokens,
            cost=total_cost,
            latency=avg_latency,
            confidence=avg_confidence,
            metadata={
                "num_models": len(responses),
                "aggregation_method": aggregation_method,
                "individual_responses": [r.content for r in responses],
            }
        )

    def _aggregate_by_voting(self, responses: List[LLMResponse]) -> str:
        """Aggregate responses by voting (majority wins).

        Args:
            responses: List of responses.

        Returns:
            Aggregated response.
        """
        # Simple voting: return the most common response
        response_counts = {}
        for response in responses:
            response_counts[response.content] = response_counts.get(response.content, 0) + 1

        most_common = max(response_counts, key=response_counts.get)
        return most_common

    def _aggregate_by_averaging(self, responses: List[LLMResponse]) -> str:
        """Aggregate responses by averaging (for numeric responses).

        Args:
            responses: List of responses.

        Returns:
            Aggregated response.
        """
        # For text responses, return concatenation with confidence scores
        aggregated = "\n".join([
            f"[Confidence: {r.confidence:.2f}] {r.content}"
            for r in responses
        ])
        return aggregated

    def _aggregate_by_consensus(self, responses: List[LLMResponse]) -> str:
        """Aggregate responses by consensus.

        Args:
            responses: List of responses.

        Returns:
            Aggregated response.
        """
        # Return the response with highest confidence
        best_response = max(responses, key=lambda r: r.confidence)
        return best_response.content

    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing statistics.

        Returns:
            Routing statistics.
        """
        if not self.routing_history:
            return {}

        task_type_counts = {}
        model_usage = {}

        for entry in self.routing_history:
            task_type = entry["task_type"]
            model = entry["selected_model"]

            task_type_counts[task_type] = task_type_counts.get(task_type, 0) + 1
            model_usage[model] = model_usage.get(model, 0) + 1

        return {
            "total_requests": len(self.routing_history),
            "task_type_distribution": task_type_counts,
            "model_usage_distribution": model_usage,
        }
