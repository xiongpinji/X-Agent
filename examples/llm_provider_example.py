"""Example script demonstrating LLM routing usage.

Run with: python examples/llm_provider_example.py

Environment variables:
  OPENAI_API_KEY   - OpenAI API key (optional, falls back to mock)
  DEEPSEEK_API_KEY - DeepSeek API key (optional)
  ANTHROPIC_API_KEY - Anthropic API key (optional)
"""

import asyncio
import os

from backend.app.core.llm import (
    LLMResponse,
    LLMRouter,
    MockLLMBackend,
    OpenAIBackend,
    build_llm_router,
)


async def example_basic_chat():
    """Example 1: Basic chat with LLMRouter."""
    print("=" * 60)
    print("Example 1: Basic Chat")
    print("=" * 60)

    # Build router from settings (uses mock if no API keys)
    router = build_llm_router(
        llm_backend="openai",
        fallback_order="openai",
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model="gpt-4o-mini",
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
        deepseek_model="deepseek-chat",
        deepseek_base_url="https://api.deepseek.com",
    )

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is Python in one sentence?"},
    ]

    print("\nSending request...")
    response: LLMResponse = await router.chat(messages, tools=[])

    print(f"\nResponse: {response.content}")
    print(f"Model: {response.model}")
    print(f"Tokens used: {response.tokens_used}")
    print(f"Cost: ${response.cost:.4f}")


async def example_mock_backend():
    """Example 2: Using MockLLMBackend for testing."""
    print("\n" + "=" * 60)
    print("Example 2: Mock Backend (no API key needed)")
    print("=" * 60)

    # Create router with mock backend (useful for testing)
    router = LLMRouter(backend=MockLLMBackend())

    messages = [
        {"role": "user", "content": "Hello, world!"},
    ]

    print("\nSending request to mock backend...")
    response = await router.chat(messages, tools=[])

    print(f"\nResponse: {response.content}")
    print(f"Model: {response.model}")
    print("(Mock backend returns canned responses for testing)")


async def example_multi_backend_fallback():
    """Example 3: Multiple backends with automatic fallback."""
    print("\n" + "=" * 60)
    print("Example 3: Multi-Backend Fallback")
    print("=" * 60)

    backends = []

    # Add OpenAI if key available
    if os.getenv("OPENAI_API_KEY"):
        backends.append(OpenAIBackend(
            api_key=os.getenv("OPENAI_API_KEY"),
            model="gpt-4o-mini",
        ))
        print("Added OpenAI backend")

    # Always add mock as final fallback
    backends.append(MockLLMBackend())
    print("Added Mock backend (fallback)")

    router = LLMRouter(backends=backends)

    messages = [
        {"role": "user", "content": "Explain async/await in one sentence."},
    ]

    print("\nSending request (will fallback if primary fails)...")
    response = await router.chat(messages, tools=[])

    print(f"\nResponse: {response.content}")
    print(f"Model: {response.model}")


async def example_with_tools():
    """Example 4: Chat with tool definitions."""
    print("\n" + "=" * 60)
    print("Example 4: Chat with Tools")
    print("=" * 60)

    router = LLMRouter(backend=MockLLMBackend())

    messages = [
        {"role": "user", "content": "What's the weather in Tokyo?"},
    ]

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get current weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "City name"},
                    },
                    "required": ["location"],
                },
            },
        }
    ]

    print("\nSending request with tool definitions...")
    response = await router.chat(messages, tools=tools)

    print(f"\nResponse: {response.content}")
    if response.tool_calls:
        print(f"Tool calls: {response.tool_calls}")


async def main():
    """Run all examples."""
    print("\nX-Agent LLM Routing Examples")
    print("=" * 60)
    print(f"OPENAI_API_KEY: {'set' if os.getenv('OPENAI_API_KEY') else 'not set'}")
    print(f"DEEPSEEK_API_KEY: {'set' if os.getenv('DEEPSEEK_API_KEY') else 'not set'}")
    print()

    try:
        # Always works (mock backend)
        await example_mock_backend()
        await example_multi_backend_fallback()
        await example_with_tools()

        # Only works with API keys
        if os.getenv("OPENAI_API_KEY"):
            await example_basic_chat()
        else:
            print("\n[Skipped Example 1: Basic Chat - set OPENAI_API_KEY to run]")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("Examples complete!")


if __name__ == "__main__":
    asyncio.run(main())
