"""Example script demonstrating LLM provider usage.

Run with: python examples/llm_provider_example.py
"""

import asyncio
import os
from backend.app.core.llm_providers import (
    LLMConfig,
    LLMMessage,
    ProviderType,
)
# MessageRole 未从包级 __init__ 再导出，需从 base 模块导入
from backend.app.core.llm_providers.base import MessageRole
from backend.app.core.llm_providers.factory import LLMProviderFactory, LLMRouter


async def example_single_provider():
    """Example: Using a single provider."""
    print("=" * 60)
    print("Example 1: Single Provider (OpenAI)")
    print("=" * 60)

    config = LLMConfig(
        provider=ProviderType.OPENAI,
        model="gpt-3.5-turbo",
        api_key=os.getenv("OPENAI_API_KEY"),
        max_tokens=100,
    )

    provider = LLMProviderFactory.create(config)

    messages = [
        LLMMessage(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
        LLMMessage(role=MessageRole.USER, content="What is Python?"),
    ]

    print("\nSending request to OpenAI...")
    response = await provider.complete(messages)

    print(f"\nResponse: {response.content}")
    print(f"Provider: {response.provider}")
    print(f"Model: {response.model}")
    print(f"Tokens - Prompt: {response.usage['prompt_tokens']}, Completion: {response.usage['completion_tokens']}")
    print(f"Cost: ${response.cost_usd:.4f}")
    print(f"Latency: {response.latency_ms:.2f}ms")


async def example_streaming():
    """Example: Streaming responses."""
    print("\n" + "=" * 60)
    print("Example 2: Streaming Response")
    print("=" * 60)

    config = LLMConfig(
        provider=ProviderType.OPENAI,
        model="gpt-3.5-turbo",
        api_key=os.getenv("OPENAI_API_KEY"),
        max_tokens=100,
    )

    provider = LLMProviderFactory.create(config)

    messages = [
        LLMMessage(role=MessageRole.USER, content="Count from 1 to 5"),
    ]

    print("\nStreaming response from OpenAI:")
    async for chunk in provider.stream(messages):
        print(chunk.content, end="", flush=True)
    print("\n")


async def example_multiple_providers():
    """Example: Using multiple providers with router."""
    print("\n" + "=" * 60)
    print("Example 3: Multiple Providers with Router")
    print("=" * 60)

    router = LLMRouter()

    # Register OpenAI
    if os.getenv("OPENAI_API_KEY"):
        openai_config = LLMConfig(
            provider=ProviderType.OPENAI,
            model="gpt-3.5-turbo",
            api_key=os.getenv("OPENAI_API_KEY"),
            max_tokens=100,
        )
        router.register("openai", openai_config)
        print("Registered OpenAI provider")

    # Register Anthropic
    if os.getenv("ANTHROPIC_API_KEY"):
        anthropic_config = LLMConfig(
            provider=ProviderType.ANTHROPIC,
            model="claude-3-5-sonnet-20241022",
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            max_tokens=100,
        )
        router.register("anthropic", anthropic_config)
        print("Registered Anthropic provider")

    # Register Ollama
    ollama_config = LLMConfig(
        provider=ProviderType.OLLAMA,
        model="llama2",
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        max_tokens=100,
    )
    router.register("ollama", ollama_config)
    print("Registered Ollama provider")

    messages = [
        LLMMessage(role=MessageRole.USER, content="What is machine learning?"),
    ]

    # Use each provider
    for provider_name in router.list_providers():
        print(f"\nUsing {provider_name} provider:")
        try:
            provider = router.get(provider_name)
            response = await provider.complete(messages)
            print(f"Response: {response.content[:100]}...")
            print(f"Cost: ${response.cost_usd:.4f}")
        except Exception as e:
            print(f"Error: {e}")


async def example_error_handling():
    """Example: Error handling."""
    print("\n" + "=" * 60)
    print("Example 4: Error Handling")
    print("=" * 60)

    from backend.app.core.llm_providers.base import (
        LLMProviderAuthError,
        LLMProviderError,
    )

    # Try with invalid API key
    config = LLMConfig(
        provider=ProviderType.OPENAI,
        model="gpt-4",
        api_key="invalid-key",
        max_tokens=100,
    )

    provider = LLMProviderFactory.create(config)

    messages = [
        LLMMessage(role=MessageRole.USER, content="Hello"),
    ]

    print("\nTrying with invalid API key...")
    try:
        response = await provider.complete(messages)
    except LLMProviderAuthError as e:
        print(f"Authentication error (expected): {e}")
    except LLMProviderError as e:
        print(f"Provider error: {e}")


async def example_cost_tracking():
    """Example: Cost tracking."""
    print("\n" + "=" * 60)
    print("Example 5: Cost Tracking")
    print("=" * 60)

    config = LLMConfig(
        provider=ProviderType.OPENAI,
        model="gpt-3.5-turbo",
        api_key=os.getenv("OPENAI_API_KEY"),
        max_tokens=100,
    )

    provider = LLMProviderFactory.create(config)

    messages = [
        LLMMessage(role=MessageRole.USER, content="What is AI?"),
    ]

    print("\nMaking requests and tracking costs...")
    for i in range(3):
        response = await provider.complete(messages)
        print(f"Request {i+1}: ${response.cost_usd:.4f}")

    stats = provider.get_stats()
    print(f"\nProvider Statistics:")
    print(f"  Total requests: {stats['request_count']}")
    print(f"  Total cost: ${stats['total_cost_usd']:.4f}")


async def main():
    """Run all examples."""
    print("\nLLM Provider Examples")
    print("=" * 60)

    # Check for API keys
    if not os.getenv("OPENAI_API_KEY"):
        print("Warning: OPENAI_API_KEY not set. Some examples will be skipped.")

    try:
        # Run examples
        if os.getenv("OPENAI_API_KEY"):
            await example_single_provider()
            await example_streaming()
            await example_error_handling()
            await example_cost_tracking()

        await example_multiple_providers()

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
