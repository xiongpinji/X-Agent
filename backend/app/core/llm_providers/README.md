# LLM Providers Module

Multi-LLM provider integration for X-Agent with support for OpenAI, Anthropic, DeepSeek, and Ollama.

## File Structure

```
backend/app/core/llm_providers/
├── __init__.py              # Module exports
├── base.py                  # Base classes and interfaces
├── openai.py               # OpenAI provider implementation
├── anthropic.py            # Anthropic provider implementation
├── deepseek.py             # DeepSeek provider implementation
├── ollama.py               # Ollama provider implementation
├── factory.py              # Factory and router classes
└── config.py               # Configuration examples
```

## Key Components

### Base Module (`base.py`)
- `ProviderType`: Enum for supported providers
- `MessageRole`: Enum for message roles
- `LLMMessage`: Message data class
- `LLMConfig`: Configuration data class
- `LLMResponse`: Response data class
- `LLMStreamResponse`: Streaming response data class
- `BaseLLMProvider`: Abstract base class for all providers
- Exception classes: `LLMProviderError`, `LLMProviderAuthError`, `LLMProviderRateLimitError`, `LLMProviderTimeoutError`

### Provider Implementations
- `OpenAIProvider`: GPT-4, GPT-3.5-turbo support
- `AnthropicProvider`: Claude 3.5 Sonnet, Claude 3 Opus support
- `DeepSeekProvider`: DeepSeek-V3, DeepSeek-R1 support
- `OllamaProvider`: Local model support

### Factory and Router (`factory.py`)
- `LLMProviderFactory`: Creates provider instances
- `LLMRouter`: Manages multiple providers

## Features

### Unified Interface
All providers implement the same interface:
- `complete()`: Generate completion
- `stream()`: Stream completion
- `complete_with_retry()`: Complete with automatic retry
- `get_stats()`: Get provider statistics

### Error Handling
- Automatic retry on rate limit and timeout
- Specific exception types for different errors
- Exponential backoff for retries

### Cost Tracking
- Per-request cost calculation
- Provider statistics with total cost
- Usage tracking (prompt/completion tokens)

### Streaming Support
- Async streaming for all providers
- Chunk-based response handling

## Usage Examples

### Basic Usage
```python
from backend.app.core.llm_providers import LLMConfig, LLMMessage, MessageRole, ProviderType
from backend.app.core.llm_providers.factory import LLMProviderFactory

config = LLMConfig(
    provider=ProviderType.OPENAI,
    model="gpt-4",
    api_key="your-key",
)
provider = LLMProviderFactory.create(config)

messages = [
    LLMMessage(role=MessageRole.USER, content="Hello"),
]
response = await provider.complete(messages)
print(response.content)
```

### Using Router
```python
from backend.app.core.llm_providers.factory import LLMRouter

router = LLMRouter()
router.register("openai", openai_config)
router.register("anthropic", anthropic_config)

provider = router.get("openai")
response = await provider.complete(messages)
```

## Testing

### Unit Tests
```bash
pytest tests/test_llm_providers.py -v
```

### Integration Tests
```bash
export OPENAI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"
pytest tests/test_llm_providers_integration.py -v
```

## Configuration

See `config.py` for example configurations and environment variables.

## Documentation

See `docs/LLM_INTEGRATION.md` for comprehensive documentation.

## Supported Models

### OpenAI
- gpt-4
- gpt-4-turbo
- gpt-3.5-turbo

### Anthropic
- claude-3-5-sonnet-20241022
- claude-3-opus-20240229
- claude-3-haiku-20240307

### DeepSeek
- deepseek-chat
- deepseek-coder

### Ollama
- llama2
- mistral
- neural-chat
- Any model available via Ollama

## Cost Pricing (as of 2024)

### OpenAI
- GPT-4: $0.03/1K prompt, $0.06/1K completion
- GPT-3.5: $0.0005/1K prompt, $0.0015/1K completion

### Anthropic
- Claude 3.5 Sonnet: $3/1M prompt, $15/1M completion
- Claude 3 Opus: $15/1M prompt, $75/1M completion
- Claude 3 Haiku: $0.8/1M prompt, $4/1M completion

### DeepSeek
- DeepSeek-V3: $0.27/1M prompt, $1.10/1M completion
- DeepSeek-R1: $0.55/1M prompt, $2.19/1M completion

### Ollama
- Free (local)

## Future Enhancements

- [ ] Response caching
- [ ] Load balancing
- [ ] Provider health checks
- [ ] Advanced retry strategies
- [ ] Batch processing
- [ ] Custom provider support
- [ ] Cost optimization
