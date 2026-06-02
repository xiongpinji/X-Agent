"""Unit tests for LLM providers."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.core.llm_providers.base import (
    LLMConfig,
    LLMMessage,
    LLMProviderAuthError,
    LLMProviderError,
    LLMProviderRateLimitError,
    LLMProviderTimeoutError,
    LLMResponse,
    MessageRole,
    ProviderType,
)
from backend.app.core.llm_providers.factory import LLMProviderFactory, LLMRouter
from backend.app.core.llm_providers.openai import OpenAIProvider
from backend.app.core.llm_providers.anthropic import AnthropicProvider
from backend.app.core.llm_providers.deepseek import DeepSeekProvider
from backend.app.core.llm_providers.ollama import OllamaProvider


class TestLLMConfig:
    """Test LLMConfig validation."""

    def test_valid_config(self):
        """Test creating valid config."""
        config = LLMConfig(
            provider=ProviderType.OPENAI,
            model="gpt-4",
            api_key="test-key",
        )
        assert config.provider == ProviderType.OPENAI
        assert config.model == "gpt-4"

    def test_invalid_temperature(self):
        """Test invalid temperature."""
        with pytest.raises(ValueError, match="temperature must be between 0 and 2"):
            LLMConfig(
                provider=ProviderType.OPENAI,
                model="gpt-4",
                temperature=3.0,
            )

    def test_invalid_top_p(self):
        """Test invalid top_p."""
        with pytest.raises(ValueError, match="top_p must be between 0 and 1"):
            LLMConfig(
                provider=ProviderType.OPENAI,
                model="gpt-4",
                top_p=1.5,
            )

    def test_string_provider_conversion(self):
        """Test string provider conversion."""
        config = LLMConfig(
            provider="openai",
            model="gpt-4",
        )
        assert config.provider == ProviderType.OPENAI


class TestLLMMessage:
    """Test LLMMessage."""

    def test_message_creation(self):
        """Test creating message."""
        msg = LLMMessage(role=MessageRole.USER, content="Hello")
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello"

    def test_message_to_dict(self):
        """Test converting message to dict."""
        msg = LLMMessage(role=MessageRole.USER, content="Hello")
        data = msg.to_dict()
        assert data["role"] == "user"
        assert data["content"] == "Hello"


class TestOpenAIProvider:
    """Test OpenAI provider."""

    def test_provider_creation(self):
        """Test creating OpenAI provider."""
        config = LLMConfig(
            provider=ProviderType.OPENAI,
            model="gpt-4",
            api_key="test-key",
        )
        provider = OpenAIProvider(config)
        assert provider.config.model == "gpt-4"

    def test_missing_api_key(self):
        """Test missing API key."""
        config = LLMConfig(
            provider=ProviderType.OPENAI,
            model="gpt-4",
        )
        provider = OpenAIProvider(config)
        with pytest.raises(LLMProviderAuthError):
            provider._get_async_client()

    @pytest.mark.asyncio
    async def test_complete_with_mock(self):
        """Test complete with mocked client."""
        config = LLMConfig(
            provider=ProviderType.OPENAI,
            model="gpt-4",
            api_key="test-key",
        )
        provider = OpenAIProvider(config)

        # Mock the async client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30
        mock_response.model_dump.return_value = {}

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        provider._async_client = mock_client

        messages = [LLMMessage(role=MessageRole.USER, content="Hello")]
        response = await provider.complete(messages)

        assert response.content == "Test response"
        assert response.provider == "openai"
        assert response.usage["prompt_tokens"] == 10

    def test_cost_calculation_gpt4(self):
        """Test cost calculation for GPT-4."""
        config = LLMConfig(
            provider=ProviderType.OPENAI,
            model="gpt-4",
        )
        provider = OpenAIProvider(config)

        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 1000,
        }
        cost = provider._calculate_cost(usage)
        # GPT-4: 0.03 per 1K prompt + 0.06 per 1K completion = 0.09
        assert cost == pytest.approx(0.09, rel=0.01)

    def test_cost_calculation_gpt35(self):
        """Test cost calculation for GPT-3.5."""
        config = LLMConfig(
            provider=ProviderType.OPENAI,
            model="gpt-3.5-turbo",
        )
        provider = OpenAIProvider(config)

        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 1000,
        }
        cost = provider._calculate_cost(usage)
        # GPT-3.5: 0.0005 per 1K prompt + 0.0015 per 1K completion = 0.002
        assert cost == pytest.approx(0.002, rel=0.01)


class TestAnthropicProvider:
    """Test Anthropic provider."""

    def test_provider_creation(self):
        """Test creating Anthropic provider."""
        config = LLMConfig(
            provider=ProviderType.ANTHROPIC,
            model="claude-3-5-sonnet-20241022",
            api_key="test-key",
        )
        provider = AnthropicProvider(config)
        assert provider.config.model == "claude-3-5-sonnet-20241022"

    def test_cost_calculation_sonnet(self):
        """Test cost calculation for Claude Sonnet."""
        config = LLMConfig(
            provider=ProviderType.ANTHROPIC,
            model="claude-3-5-sonnet-20241022",
        )
        provider = AnthropicProvider(config)

        usage = {
            "prompt_tokens": 1_000_000,
            "completion_tokens": 1_000_000,
        }
        cost = provider._calculate_cost(usage)
        # Sonnet: $3 per 1M prompt + $15 per 1M completion = $18
        assert cost == pytest.approx(18.0, rel=0.01)

    def test_cost_calculation_opus(self):
        """Test cost calculation for Claude Opus."""
        config = LLMConfig(
            provider=ProviderType.ANTHROPIC,
            model="claude-3-opus-20240229",
        )
        provider = AnthropicProvider(config)

        usage = {
            "prompt_tokens": 1_000_000,
            "completion_tokens": 1_000_000,
        }
        cost = provider._calculate_cost(usage)
        # Opus: $15 per 1M prompt + $75 per 1M completion = $90
        assert cost == pytest.approx(90.0, rel=0.01)


class TestDeepSeekProvider:
    """Test DeepSeek provider."""

    def test_provider_creation(self):
        """Test creating DeepSeek provider."""
        config = LLMConfig(
            provider=ProviderType.DEEPSEEK,
            model="deepseek-chat",
            api_key="test-key",
        )
        provider = DeepSeekProvider(config)
        assert provider.config.base_url == "https://api.deepseek.com"

    def test_cost_calculation_v3(self):
        """Test cost calculation for DeepSeek V3."""
        config = LLMConfig(
            provider=ProviderType.DEEPSEEK,
            model="deepseek-chat",
        )
        provider = DeepSeekProvider(config)

        usage = {
            "prompt_tokens": 1_000_000,
            "completion_tokens": 1_000_000,
        }
        cost = provider._calculate_cost(usage)
        # V3: $0.27 per 1M prompt + $1.10 per 1M completion = $1.37
        assert cost == pytest.approx(1.37, rel=0.01)


class TestOllamaProvider:
    """Test Ollama provider."""

    def test_provider_creation(self):
        """Test creating Ollama provider."""
        config = LLMConfig(
            provider=ProviderType.OLLAMA,
            model="llama2",
        )
        provider = OllamaProvider(config)
        assert provider.config.base_url == "http://localhost:11434"

    def test_cost_calculation(self):
        """Test cost calculation for Ollama (should be 0)."""
        config = LLMConfig(
            provider=ProviderType.OLLAMA,
            model="llama2",
        )
        provider = OllamaProvider(config)

        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 1000,
        }
        cost = provider._calculate_cost(usage)
        assert cost == 0.0


class TestLLMProviderFactory:
    """Test LLM provider factory."""

    def test_create_openai_provider(self):
        """Test creating OpenAI provider."""
        config = LLMConfig(
            provider=ProviderType.OPENAI,
            model="gpt-4",
            api_key="test-key",
        )
        provider = LLMProviderFactory.create(config)
        assert isinstance(provider, OpenAIProvider)

    def test_create_anthropic_provider(self):
        """Test creating Anthropic provider."""
        config = LLMConfig(
            provider=ProviderType.ANTHROPIC,
            model="claude-3-5-sonnet-20241022",
            api_key="test-key",
        )
        provider = LLMProviderFactory.create(config)
        assert isinstance(provider, AnthropicProvider)

    def test_create_deepseek_provider(self):
        """Test creating DeepSeek provider."""
        config = LLMConfig(
            provider=ProviderType.DEEPSEEK,
            model="deepseek-chat",
            api_key="test-key",
        )
        provider = LLMProviderFactory.create(config)
        assert isinstance(provider, DeepSeekProvider)

    def test_create_ollama_provider(self):
        """Test creating Ollama provider."""
        config = LLMConfig(
            provider=ProviderType.OLLAMA,
            model="llama2",
        )
        provider = LLMProviderFactory.create(config)
        assert isinstance(provider, OllamaProvider)

    def test_unsupported_provider(self):
        """Test unsupported provider."""
        config = LLMConfig(
            provider="unsupported",
            model="test",
        )
        with pytest.raises(ValueError):
            LLMProviderFactory.create(config)


class TestLLMRouter:
    """Test LLM router."""

    def test_register_provider(self):
        """Test registering provider."""
        router = LLMRouter()
        config = LLMConfig(
            provider=ProviderType.OPENAI,
            model="gpt-4",
            api_key="test-key",
        )
        provider = router.register("openai", config)
        assert isinstance(provider, OpenAIProvider)

    def test_get_default_provider(self):
        """Test getting default provider."""
        router = LLMRouter()
        config = LLMConfig(
            provider=ProviderType.OPENAI,
            model="gpt-4",
            api_key="test-key",
        )
        router.register("openai", config)
        provider = router.get()
        assert isinstance(provider, OpenAIProvider)

    def test_get_named_provider(self):
        """Test getting named provider."""
        router = LLMRouter()
        config1 = LLMConfig(
            provider=ProviderType.OPENAI,
            model="gpt-4",
            api_key="test-key",
        )
        config2 = LLMConfig(
            provider=ProviderType.ANTHROPIC,
            model="claude-3-5-sonnet-20241022",
            api_key="test-key",
        )
        router.register("openai", config1)
        router.register("anthropic", config2)

        openai_provider = router.get("openai")
        assert isinstance(openai_provider, OpenAIProvider)

        anthropic_provider = router.get("anthropic")
        assert isinstance(anthropic_provider, AnthropicProvider)

    def test_set_default_provider(self):
        """Test setting default provider."""
        router = LLMRouter()
        config1 = LLMConfig(
            provider=ProviderType.OPENAI,
            model="gpt-4",
            api_key="test-key",
        )
        config2 = LLMConfig(
            provider=ProviderType.ANTHROPIC,
            model="claude-3-5-sonnet-20241022",
            api_key="test-key",
        )
        router.register("openai", config1)
        router.register("anthropic", config2)

        router.set_default("anthropic")
        provider = router.get()
        assert isinstance(provider, AnthropicProvider)

    def test_list_providers(self):
        """Test listing providers."""
        router = LLMRouter()
        config1 = LLMConfig(
            provider=ProviderType.OPENAI,
            model="gpt-4",
            api_key="test-key",
        )
        config2 = LLMConfig(
            provider=ProviderType.ANTHROPIC,
            model="claude-3-5-sonnet-20241022",
            api_key="test-key",
        )
        router.register("openai", config1)
        router.register("anthropic", config2)

        providers = router.list_providers()
        assert "openai" in providers
        assert "anthropic" in providers

    def test_get_stats(self):
        """Test getting stats."""
        router = LLMRouter()
        config = LLMConfig(
            provider=ProviderType.OPENAI,
            model="gpt-4",
            api_key="test-key",
        )
        router.register("openai", config)

        stats = router.get_stats()
        assert "openai" in stats
        assert "provider" in stats["openai"]
        assert "model" in stats["openai"]
