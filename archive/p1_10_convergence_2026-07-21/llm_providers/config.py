"""Example LLM Provider Configuration

This file demonstrates how to configure and use multiple LLM providers.
"""

import os

from backend.app.core.llm_providers import (
    LLMConfig,
    ProviderType,
)
from backend.app.core.llm_providers.factory import LLMRouter


def create_llm_router() -> LLMRouter:
    """Create and configure LLM router with all providers.

    Returns:
        Configured LLM router

    Environment Variables:
        OPENAI_API_KEY: OpenAI API key
        ANTHROPIC_API_KEY: Anthropic API key
        DEEPSEEK_API_KEY: DeepSeek API key
        OLLAMA_BASE_URL: Ollama base URL (default: http://localhost:11434)
    """
    router = LLMRouter()

    # Configure OpenAI
    if os.getenv("OPENAI_API_KEY"):
        openai_config = LLMConfig(
            provider=ProviderType.OPENAI,
            model=os.getenv("OPENAI_MODEL", "gpt-4"),
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.7,
            max_tokens=2000,
            timeout=30,
        )
        router.register("openai", openai_config)

    # Configure Anthropic
    if os.getenv("ANTHROPIC_API_KEY"):
        anthropic_config = LLMConfig(
            provider=ProviderType.ANTHROPIC,
            model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            temperature=0.7,
            max_tokens=4096,
            timeout=30,
        )
        router.register("anthropic", anthropic_config)

    # Configure DeepSeek
    if os.getenv("DEEPSEEK_API_KEY"):
        deepseek_config = LLMConfig(
            provider=ProviderType.DEEPSEEK,
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com",
            temperature=0.7,
            max_tokens=2000,
            timeout=30,
        )
        router.register("deepseek", deepseek_config)

    # Configure Ollama (always available if running locally)
    ollama_config = LLMConfig(
        provider=ProviderType.OLLAMA,
        model=os.getenv("OLLAMA_MODEL", "llama2"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0.7,
        max_tokens=2000,
        timeout=60,
    )
    router.register("ollama", ollama_config)

    # Set default provider
    default_provider = os.getenv("DEFAULT_LLM_PROVIDER", "openai")
    if default_provider in router.list_providers():
        router.set_default(default_provider)

    return router


def get_provider_config(provider_name: str) -> LLMConfig:
    """Get configuration for a specific provider.

    Args:
        provider_name: Name of the provider (openai, anthropic, deepseek, ollama)

    Returns:
        LLM configuration

    Raises:
        ValueError: If provider is not supported
    """
    provider_name = provider_name.lower()

    if provider_name == "openai":
        return LLMConfig(
            provider=ProviderType.OPENAI,
            model=os.getenv("OPENAI_MODEL", "gpt-4"),
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.7,
            max_tokens=2000,
        )

    elif provider_name == "anthropic":
        return LLMConfig(
            provider=ProviderType.ANTHROPIC,
            model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            temperature=0.7,
            max_tokens=4096,
        )

    elif provider_name == "deepseek":
        return LLMConfig(
            provider=ProviderType.DEEPSEEK,
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com",
            temperature=0.7,
            max_tokens=2000,
        )

    elif provider_name == "ollama":
        return LLMConfig(
            provider=ProviderType.OLLAMA,
            model=os.getenv("OLLAMA_MODEL", "llama2"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=0.7,
            max_tokens=2000,
        )

    else:
        raise ValueError(f"Unknown provider: {provider_name}")


# Example environment variables (.env file)
EXAMPLE_ENV = """
# OpenAI Configuration
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4

# Anthropic Configuration
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# DeepSeek Configuration
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_MODEL=deepseek-chat

# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2

# Default Provider
DEFAULT_LLM_PROVIDER=openai
"""


if __name__ == "__main__":
    # Example usage
    print("LLM Provider Configuration Examples")
    print("=" * 50)

    # Create router
    router = create_llm_router()

    # List available providers
    print("\nAvailable providers:")
    for provider in router.list_providers():
        print(f"  - {provider}")

    # Get stats
    print("\nProvider statistics:")
    stats = router.get_stats()
    for provider, provider_stats in stats.items():
        print(f"  {provider}:")
        print(f"    Model: {provider_stats['model']}")
        print(f"    Requests: {provider_stats['request_count']}")
        print(f"    Total cost: ${provider_stats['total_cost_usd']:.2f}")

    print("\n" + "=" * 50)
    print("Example .env file:")
    print(EXAMPLE_ENV)
