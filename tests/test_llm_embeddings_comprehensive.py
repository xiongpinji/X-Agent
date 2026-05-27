"""Comprehensive tests for LLM and embeddings components.

Tests cover:
- LLM model selection and routing
- Embedding model creation and validation
- Token counting
- Model configuration
- Error handling
"""

from __future__ import annotations

import pytest

from backend.app.core.llm import LLMRouter
from backend.app.core.embeddings import (
    DeterministicEmbeddingModel,
    EmbeddingModel,
)


class TestEmbeddingModel:
    """Test EmbeddingModel base class."""

    def test_embedding_model_interface(self) -> None:
        """Test that EmbeddingModel defines required interface."""
        model = EmbeddingModel()
        assert hasattr(model, "embed")
        assert hasattr(model, "embed_batch")
        assert hasattr(model, "get_embedding_dimension")

    def test_embedding_dimension(self) -> None:
        """Test embedding dimension property."""
        model = EmbeddingModel()
        dimension = model.get_embedding_dimension()
        assert isinstance(dimension, int)
        assert dimension > 0


class TestDeterministicEmbeddingModel:
    """Test DeterministicEmbeddingModel implementation."""

    def test_deterministic_model_creation(self) -> None:
        """Test creating a deterministic embedding model."""
        model = DeterministicEmbeddingModel()
        assert model is not None

    def test_deterministic_embedding_dimension(self) -> None:
        """Test deterministic model embedding dimension."""
        model = DeterministicEmbeddingModel()
        dimension = model.get_embedding_dimension()
        assert isinstance(dimension, int)
        assert dimension > 0

    def test_deterministic_embedding_consistency(self) -> None:
        """Test that same input produces same embedding."""
        model = DeterministicEmbeddingModel()
        text = "Test text for embedding"

        embedding1 = model.embed(text)
        embedding2 = model.embed(text)

        assert embedding1 == embedding2
        assert len(embedding1) == model.get_embedding_dimension()

    def test_deterministic_embedding_different_inputs(self) -> None:
        """Test that different inputs produce different embeddings."""
        model = DeterministicEmbeddingModel()

        embedding1 = model.embed("First text")
        embedding2 = model.embed("Second text")

        assert embedding1 != embedding2

    def test_deterministic_batch_embedding(self) -> None:
        """Test batch embedding."""
        model = DeterministicEmbeddingModel()
        texts = ["Text 1", "Text 2", "Text 3"]

        embeddings = model.embed_batch(texts)

        assert len(embeddings) == 3
        for embedding in embeddings:
            assert len(embedding) == model.get_embedding_dimension()

    def test_deterministic_batch_consistency(self) -> None:
        """Test batch embedding consistency."""
        model = DeterministicEmbeddingModel()
        texts = ["Text 1", "Text 2"]

        batch1 = model.embed_batch(texts)
        batch2 = model.embed_batch(texts)

        assert batch1 == batch2

    def test_deterministic_empty_text(self) -> None:
        """Test embedding empty text."""
        model = DeterministicEmbeddingModel()
        embedding = model.embed("")
        assert len(embedding) == model.get_embedding_dimension()

    def test_deterministic_long_text(self) -> None:
        """Test embedding long text."""
        model = DeterministicEmbeddingModel()
        long_text = "word " * 1000
        embedding = model.embed(long_text)
        assert len(embedding) == model.get_embedding_dimension()

    def test_deterministic_special_characters(self) -> None:
        """Test embedding text with special characters."""
        model = DeterministicEmbeddingModel()
        special_text = "!@#$%^&*()_+-=[]{}|;:',.<>?/~`"
        embedding = model.embed(special_text)
        assert len(embedding) == model.get_embedding_dimension()

    def test_deterministic_unicode_text(self) -> None:
        """Test embedding unicode text."""
        model = DeterministicEmbeddingModel()
        unicode_text = "你好世界 مرحبا بالعالم Привет мир"
        embedding = model.embed(unicode_text)
        assert len(embedding) == model.get_embedding_dimension()


class TestLLMRouter:
    """Test LLMRouter functionality."""

    def test_llm_router_creation(self) -> None:
        """Test creating an LLM router."""
        router = LLMRouter()
        assert router is not None

    def test_llm_router_has_models(self) -> None:
        """Test that router has available models."""
        router = LLMRouter()
        assert hasattr(router, "get_available_models")

    def test_llm_router_select_model(self) -> None:
        """Test selecting a model from router."""
        router = LLMRouter()
        # Should have at least one model available
        models = router.get_available_models()
        assert len(models) > 0

    def test_llm_router_default_model(self) -> None:
        """Test getting default model."""
        router = LLMRouter()
        default_model = router.get_default_model()
        assert default_model is not None

    def test_llm_router_model_by_name(self) -> None:
        """Test getting model by name."""
        router = LLMRouter()
        models = router.get_available_models()
        if models:
            model_name = models[0]
            model = router.get_model(model_name)
            assert model is not None

    def test_llm_router_token_counting(self) -> None:
        """Test token counting."""
        router = LLMRouter()
        text = "This is a test message for token counting."
        token_count = router.count_tokens(text)
        assert isinstance(token_count, int)
        assert token_count > 0

    def test_llm_router_token_counting_empty(self) -> None:
        """Test token counting for empty text."""
        router = LLMRouter()
        token_count = router.count_tokens("")
        assert isinstance(token_count, int)
        assert token_count >= 0

    def test_llm_router_token_counting_long_text(self) -> None:
        """Test token counting for long text."""
        router = LLMRouter()
        long_text = "word " * 1000
        token_count = router.count_tokens(long_text)
        assert isinstance(token_count, int)
        assert token_count > 100

    def test_llm_router_model_capabilities(self) -> None:
        """Test checking model capabilities."""
        router = LLMRouter()
        models = router.get_available_models()
        for model_name in models:
            capabilities = router.get_model_capabilities(model_name)
            assert isinstance(capabilities, dict)

    def test_llm_router_model_context_window(self) -> None:
        """Test getting model context window."""
        router = LLMRouter()
        default_model = router.get_default_model()
        context_window = router.get_context_window(default_model)
        assert isinstance(context_window, int)
        assert context_window > 0

    def test_llm_router_model_cost(self) -> None:
        """Test getting model cost information."""
        router = LLMRouter()
        default_model = router.get_default_model()
        cost_info = router.get_cost_info(default_model)
        assert isinstance(cost_info, dict)

    def test_llm_router_select_by_capability(self) -> None:
        """Test selecting model by capability."""
        router = LLMRouter()
        # Should be able to select a model with vision capability
        model = router.select_by_capability("vision")
        # May return None if no vision model available
        if model:
            assert isinstance(model, str)

    def test_llm_router_select_by_cost(self) -> None:
        """Test selecting cheapest model."""
        router = LLMRouter()
        model = router.select_cheapest()
        assert model is not None
        assert isinstance(model, str)

    def test_llm_router_select_by_speed(self) -> None:
        """Test selecting fastest model."""
        router = LLMRouter()
        model = router.select_fastest()
        assert model is not None
        assert isinstance(model, str)

    def test_llm_router_model_fallback(self) -> None:
        """Test model fallback mechanism."""
        router = LLMRouter()
        # Request a model that might not exist
        model = router.get_model_with_fallback("nonexistent-model")
        assert model is not None

    def test_llm_router_batch_token_counting(self) -> None:
        """Test batch token counting."""
        router = LLMRouter()
        texts = [
            "First message",
            "Second message",
            "Third message",
        ]
        token_counts = router.count_tokens_batch(texts)
        assert len(token_counts) == 3
        for count in token_counts:
            assert isinstance(count, int)
            assert count > 0

    def test_llm_router_model_comparison(self) -> None:
        """Test comparing models."""
        router = LLMRouter()
        models = router.get_available_models()
        if len(models) >= 2:
            comparison = router.compare_models(models[0], models[1])
            assert isinstance(comparison, dict)
            assert "cost" in comparison or "speed" in comparison

    def test_llm_router_rate_limiting(self) -> None:
        """Test rate limiting configuration."""
        router = LLMRouter()
        rate_limit = router.get_rate_limit()
        assert isinstance(rate_limit, dict)

    def test_llm_router_retry_policy(self) -> None:
        """Test retry policy configuration."""
        router = LLMRouter()
        retry_policy = router.get_retry_policy()
        assert isinstance(retry_policy, dict)
        assert "max_retries" in retry_policy or "backoff" in retry_policy
