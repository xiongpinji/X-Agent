# LLM Provider Integration Guide

## Overview

X-Agent supports multiple LLM providers through a unified interface. This allows you to seamlessly switch between different providers or use multiple providers simultaneously.

## Supported Providers

### 1. OpenAI
- **Models**: GPT-4, GPT-3.5-turbo, and other OpenAI models
- **API Key**: Required
- **Base URL**: https://api.openai.com/v1
- **Pricing**: Variable by model

### 2. Anthropic
- **Models**: Claude 3.5 Sonnet, Claude 3 Opus, Claude 3 Haiku
- **API Key**: Required
- **Base URL**: https://api.anthropic.com
- **Pricing**: Variable by model

### 3. DeepSeek
- **Models**: DeepSeek-V3, DeepSeek-R1
- **API Key**: Required
- **Base URL**: https://api.deepseek.com
- **Pricing**: Competitive pricing

### 4. Ollama
- **Models**: Local models (Llama 2, Mistral, etc.)
- **API Key**: Not required
- **Base URL**: http://localhost:11434 (default)
- **Pricing**: Free (local)

## Installation

### Prerequisites
```bash
pip install -r requirements.txt
```

### Optional Dependencies
```bash
# For OpenAI
pip install openai>=1.0.0

# For Anthropic
pip install anthropic>=0.7.0

# For Ollama (uses httpx which is already installed)
# No additional dependencies needed
```

## Quick Start

### Basic Usage

```python
from backend.app.core.llm_providers import (
    LLMConfig,
    LLMMessage,
    MessageRole,
    ProviderType,
)
from backend.app.core.llm_providers.factory import LLMProviderFactory

# Create configuration
config = LLMConfig(
    provider=ProviderType.OPENAI,
    model="gpt-4",
    api_key="your-api-key",
    temperature=0.7,
    max_tokens=1000,
)

# Create provider
provider = LLMProviderFactory.create(config)

# Prepare messages
messages = [
    LLMMessage(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
    LLMMessage(role=MessageRole.USER, content="What is Python?"),
]

# Get completion
response = await provider.complete(messages)
print(response.content)
print(f"Cost: ${response.cost_usd:.4f}")
```

### Streaming

```python
# Stream completion
async for chunk in provider.stream(messages):
    print(chunk.content, end="", flush=True)
```

### Using Router

```python
from backend.app.core.llm_providers.factory import LLMRouter

# Create router
router = LLMRouter()

# Register multiple providers
openai_config = LLMConfig(
    provider=ProviderType.OPENAI,
    model="gpt-4",
    api_key="openai-key",
)
router.register("openai", openai_config)

anthropic_config = LLMConfig(
    provider=ProviderType.ANTHROPIC,
    model="claude-3-5-sonnet-20241022",
    api_key="anthropic-key",
)
router.register("anthropic", anthropic_config)

# Use default provider
provider = router.get()
response = await provider.complete(messages)

# Use specific provider
provider = router.get("anthropic")
response = await provider.complete(messages)

# Switch default
router.set_default("anthropic")

# Get statistics
stats = router.get_stats()
print(stats)
```

## Configuration

### LLMConfig Parameters

```python
LLMConfig(
    provider: ProviderType | str,      # Provider type
    model: str,                         # Model name
    api_key: Optional[str] = None,     # API key (required for cloud providers)
    base_url: Optional[str] = None,    # Custom base URL
    temperature: float = 0.7,           # Sampling temperature (0-2)
    max_tokens: Optional[int] = None,  # Max tokens in response
    top_p: float = 1.0,                # Nucleus sampling (0-1)
    timeout: int = 30,                 # Request timeout in seconds
    retry_attempts: int = 3,           # Number of retry attempts
    retry_delay: float = 1.0,          # Delay between retries in seconds
)
```

## Error Handling

```python
from backend.app.core.llm_providers.base import (
    LLMProviderError,
    LLMProviderAuthError,
    LLMProviderRateLimitError,
    LLMProviderTimeoutError,
)

try:
    response = await provider.complete(messages)
except LLMProviderAuthError:
    print("Authentication failed. Check your API key.")
except LLMProviderRateLimitError:
    print("Rate limit exceeded. Retrying...")
except LLMProviderTimeoutError:
    print("Request timeout. Try again later.")
except LLMProviderError as e:
    print(f"Provider error: {e}")
```

## Retry Logic

Providers automatically retry on rate limit and timeout errors:

```python
# Automatic retry with exponential backoff
response = await provider.complete_with_retry(messages)
```

## Cost Tracking

Each response includes cost information:

```python
response = await provider.complete(messages)
print(f"Prompt tokens: {response.usage['prompt_tokens']}")
print(f"Completion tokens: {response.usage['completion_tokens']}")
print(f"Cost: ${response.cost_usd:.4f}")
print(f"Latency: {response.latency_ms:.2f}ms")

# Get provider statistics
stats = provider.get_stats()
print(f"Total requests: {stats['request_count']}")
print(f"Total cost: ${stats['total_cost_usd']:.2f}")
```

## Provider-Specific Configuration

### OpenAI

```python
config = LLMConfig(
    provider=ProviderType.OPENAI,
    model="gpt-4",
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0.7,
    max_tokens=2000,
)
```

### Anthropic

```python
config = LLMConfig(
    provider=ProviderType.ANTHROPIC,
    model="claude-3-5-sonnet-20241022",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    temperature=0.7,
    max_tokens=4096,  # Anthropic requires this
)
```

### DeepSeek

```python
config = LLMConfig(
    provider=ProviderType.DEEPSEEK,
    model="deepseek-chat",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",  # Optional, uses default if not set
)
```

### Ollama

```python
config = LLMConfig(
    provider=ProviderType.OLLAMA,
    model="llama2",
    base_url="http://localhost:11434",  # Optional, uses default if not set
)
```

## Testing

### Unit Tests

```bash
pytest tests/test_llm_providers.py -v
```

### Integration Tests

```bash
# Set API keys
export OPENAI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"
export DEEPSEEK_API_KEY="your-key"
export OLLAMA_BASE_URL="http://localhost:11434"

# Run integration tests
pytest tests/test_llm_providers_integration.py -v
```

## Architecture

### Class Hierarchy

```
BaseLLMProvider (abstract)
├── OpenAIProvider
├── AnthropicProvider
├── DeepSeekProvider
└── OllamaProvider

LLMProviderFactory
└── Creates provider instances

LLMRouter
└── Manages multiple providers
```

### Key Classes

- **LLMConfig**: Configuration for a provider
- **LLMMessage**: Single message in conversation
- **LLMResponse**: Complete response from provider
- **LLMStreamResponse**: Streaming response chunk
- **BaseLLMProvider**: Abstract base class for all providers
- **LLMProviderFactory**: Factory for creating providers
- **LLMRouter**: Router for managing multiple providers

## Best Practices

1. **Use environment variables for API keys**
   ```python
   api_key = os.getenv("OPENAI_API_KEY")
   ```

2. **Set appropriate timeouts**
   ```python
   config = LLMConfig(..., timeout=60)
   ```

3. **Handle errors gracefully**
   ```python
   try:
       response = await provider.complete(messages)
   except LLMProviderError as e:
       logger.error(f"LLM error: {e}")
   ```

4. **Monitor costs**
   ```python
   stats = provider.get_stats()
   logger.info(f"Total cost: ${stats['total_cost_usd']:.2f}")
   ```

5. **Use streaming for long responses**
   ```python
   async for chunk in provider.stream(messages):
       # Process chunk
   ```

6. **Implement fallback providers**
   ```python
   try:
       response = await router.get("primary").complete(messages)
   except LLMProviderError:
       response = await router.get("fallback").complete(messages)
   ```

## Troubleshooting

### Authentication Error
- Verify API key is correct
- Check API key has required permissions
- Ensure API key is not expired

### Rate Limit Error
- Implement exponential backoff
- Use `complete_with_retry()` method
- Consider using a different provider

### Timeout Error
- Increase timeout value
- Check network connectivity
- Verify provider service is running

### Ollama Connection Error
- Ensure Ollama is running: `ollama serve`
- Verify base URL is correct
- Check model is pulled: `ollama pull llama2`

## Future Enhancements

- [ ] Caching layer for responses
- [ ] Load balancing across providers
- [ ] Advanced retry strategies
- [ ] Provider health checks
- [ ] Cost optimization
- [ ] Custom provider support
- [ ] Batch processing
- [ ] Async streaming improvements
