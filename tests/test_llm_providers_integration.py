"""Integration tests for LLM providers.

P1-10: llm_providers 模块已归档收敛至 backend.app.core.llm.backends。
本测试文件保留供参考，跳过收集。
"""

import pytest

pytest.skip(
    "llm_providers 已归档 (P1-10 重复实现收敛), 测试跳过",
    allow_module_level=True,
)

import os
import pytest

from backend.app.core.llm_providers.base import (
    LLMConfig,
    LLMMessage,
    MessageRole,
    ProviderType,
)
from backend.app.core.llm_providers.factory import LLMProviderFactory, LLMRouter


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)
class TestOpenAIIntegration:
    """Integration tests for OpenAI provider."""

    @pytest.mark.asyncio
    async def test_complete_request(self):
        """Test complete request to OpenAI."""
        config = LLMConfig(
            provider=ProviderType.OPENAI,
            model="gpt-3.5-turbo",
            api_key=os.getenv("OPENAI_API_KEY"),
            max_tokens=100,
        )
        provider = LLMProviderFactory.create(config)

        messages = [
            LLMMessage(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
            LLMMessage(role=MessageRole.USER, content="Say 'Hello, World!'"),
        ]

        response = await provider.complete(messages)

        assert response.content
        assert response.provider == "openai"
        assert response.usage["prompt_tokens"] > 0
        assert response.usage["completion_tokens"] > 0
        assert response.cost_usd >= 0

    @pytest.mark.asyncio
    async def test_stream_request(self):
        """Test streaming request to OpenAI."""
        config = LLMConfig(
            provider=ProviderType.OPENAI,
            model="gpt-3.5-turbo",
            api_key=os.getenv("OPENAI_API_KEY"),
            max_tokens=100,
        )
        provider = LLMProviderFactory.create(config)

        messages = [
            LLMMessage(role=MessageRole.USER, content="Count to 5"),
        ]

        content = ""
        async for chunk in provider.stream(messages):
            content += chunk.content

        assert content
        assert len(content) > 0


@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)
class TestAnthropicIntegration:
    """Integration tests for Anthropic provider."""

    @pytest.mark.asyncio
    async def test_complete_request(self):
        """Test complete request to Anthropic."""
        config = LLMConfig(
            provider=ProviderType.ANTHROPIC,
            model="claude-3-5-sonnet-20241022",
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            max_tokens=100,
        )
        provider = LLMProviderFactory.create(config)

        messages = [
            LLMMessage(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
            LLMMessage(role=MessageRole.USER, content="Say 'Hello, World!'"),
        ]

        response = await provider.complete(messages)

        assert response.content
        assert response.provider == "anthropic"
        assert response.usage["prompt_tokens"] > 0
        assert response.usage["completion_tokens"] > 0
        assert response.cost_usd >= 0

    @pytest.mark.asyncio
    async def test_stream_request(self):
        """Test streaming request to Anthropic."""
        config = LLMConfig(
            provider=ProviderType.ANTHROPIC,
            model="claude-3-5-sonnet-20241022",
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            max_tokens=100,
        )
        provider = LLMProviderFactory.create(config)

        messages = [
            LLMMessage(role=MessageRole.USER, content="Count to 5"),
        ]

        content = ""
        async for chunk in provider.stream(messages):
            content += chunk.content

        assert content
        assert len(content) > 0


@pytest.mark.skipif(
    not os.getenv("DEEPSEEK_API_KEY"),
    reason="DEEPSEEK_API_KEY not set",
)
class TestDeepSeekIntegration:
    """Integration tests for DeepSeek provider."""

    @pytest.mark.asyncio
    async def test_complete_request(self):
        """Test complete request to DeepSeek."""
        config = LLMConfig(
            provider=ProviderType.DEEPSEEK,
            model="deepseek-chat",
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            max_tokens=100,
        )
        provider = LLMProviderFactory.create(config)

        messages = [
            LLMMessage(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
            LLMMessage(role=MessageRole.USER, content="Say 'Hello, World!'"),
        ]

        response = await provider.complete(messages)

        assert response.content
        assert response.provider == "deepseek"
        assert response.usage["prompt_tokens"] > 0
        assert response.usage["completion_tokens"] > 0
        assert response.cost_usd >= 0

    @pytest.mark.asyncio
    async def test_stream_request(self):
        """Test streaming request to DeepSeek."""
        config = LLMConfig(
            provider=ProviderType.DEEPSEEK,
            model="deepseek-chat",
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            max_tokens=100,
        )
        provider = LLMProviderFactory.create(config)

        messages = [
            LLMMessage(role=MessageRole.USER, content="Count to 5"),
        ]

        content = ""
        async for chunk in provider.stream(messages):
            content += chunk.content

        assert content
        assert len(content) > 0


@pytest.mark.skipif(
    not os.getenv("OLLAMA_BASE_URL"),
    reason="OLLAMA_BASE_URL not set",
)
class TestOllamaIntegration:
    """Integration tests for Ollama provider."""

    @pytest.mark.asyncio
    async def test_complete_request(self):
        """Test complete request to Ollama."""
        config = LLMConfig(
            provider=ProviderType.OLLAMA,
            model="llama2",
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            max_tokens=100,
        )
        provider = LLMProviderFactory.create(config)

        messages = [
            LLMMessage(role=MessageRole.USER, content="Say 'Hello, World!'"),
        ]

        response = await provider.complete(messages)

        assert response.content
        assert response.provider == "ollama"
        assert response.cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_stream_request(self):
        """Test streaming request to Ollama."""
        config = LLMConfig(
            provider=ProviderType.OLLAMA,
            model="llama2",
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            max_tokens=100,
        )
        provider = LLMProviderFactory.create(config)

        messages = [
            LLMMessage(role=MessageRole.USER, content="Count to 5"),
        ]

        content = ""
        async for chunk in provider.stream(messages):
            content += chunk.content

        assert content
        assert len(content) > 0


class TestLLMRouterIntegration:
    """Integration tests for LLM router."""

    def test_multi_provider_setup(self):
        """Test setting up multiple providers."""
        router = LLMRouter()

        # Always register a local provider so the router mechanism is exercised
        # even without real API keys (provider clients are lazily initialized,
        # so no network call happens at registration time).
        router.register(
            "ollama",
            LLMConfig(
                provider=ProviderType.OLLAMA,
                model="llama3",
            ),
        )

        # Register cloud providers when credentials are available
        if os.getenv("OPENAI_API_KEY"):
            config = LLMConfig(
                provider=ProviderType.OPENAI,
                model="gpt-3.5-turbo",
                api_key=os.getenv("OPENAI_API_KEY"),
            )
            router.register("openai", config)

        if os.getenv("ANTHROPIC_API_KEY"):
            config = LLMConfig(
                provider=ProviderType.ANTHROPIC,
                model="claude-3-5-sonnet-20241022",
                api_key=os.getenv("ANTHROPIC_API_KEY"),
            )
            router.register("anthropic", config)

        if os.getenv("DEEPSEEK_API_KEY"):
            config = LLMConfig(
                provider=ProviderType.DEEPSEEK,
                model="deepseek-chat",
                api_key=os.getenv("DEEPSEEK_API_KEY"),
            )
            router.register("deepseek", config)

        # Verify providers are registered
        providers = router.list_providers()
        assert len(providers) > 0

        # Get stats
        stats = router.get_stats()
        assert len(stats) > 0
