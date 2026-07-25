"""Base LLM Provider Interface

Defines the abstract interface that all LLM providers must implement.
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ProviderType(StrEnum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"


class MessageRole(StrEnum):
    """Message roles in conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class LLMMessage:
    """Represents a single message in a conversation."""
    role: MessageRole | str
    content: str

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary format."""
        return {
            "role": self.role if isinstance(self.role, str) else self.role.value,
            "content": self.content,
        }


@dataclass
class LLMConfig:
    """Configuration for LLM provider."""
    provider: ProviderType | str
    model: str
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None
    top_p: float = 1.0
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0

    def __post_init__(self) -> None:
        """Validate configuration."""
        if isinstance(self.provider, str):
            try:
                self.provider = ProviderType(self.provider)
            except ValueError:
                raise ValueError(f"Unknown provider: {self.provider}")

        if self.temperature < 0 or self.temperature > 2:
            raise ValueError("temperature must be between 0 and 2")

        if self.top_p < 0 or self.top_p > 1:
            raise ValueError("top_p must be between 0 and 1")


@dataclass
class LLMResponse:
    """Response from LLM provider."""
    content: str
    model: str
    provider: str
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"
    raw_response: dict[str, Any] | None = None
    latency_ms: float = 0.0
    cost_usd: float = 0.0


@dataclass
class LLMStreamResponse:
    """Streaming response chunk from LLM provider."""
    content: str
    model: str
    provider: str
    finish_reason: str | None = None
    raw_response: dict[str, Any] | None = None


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""
    pass


class LLMProviderAuthError(LLMProviderError):
    """Authentication error."""
    pass


class LLMProviderRateLimitError(LLMProviderError):
    """Rate limit error."""
    pass


class LLMProviderTimeoutError(LLMProviderError):
    """Timeout error."""
    pass


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: LLMConfig) -> None:
        """Initialize provider with configuration."""
        self.config = config
        self._request_count = 0
        self._total_cost = 0.0
        self._last_request_time = 0.0

    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion for the given messages.

        Args:
            messages: List of messages in the conversation
            **kwargs: Provider-specific parameters

        Returns:
            LLMResponse with the generated content

        Raises:
            LLMProviderError: If the request fails
        """
        pass

    @abstractmethod
    async def stream(
        self,
        messages: list[LLMMessage],
        **kwargs: Any,
    ) -> AsyncGenerator[LLMStreamResponse, None]:
        """Stream a completion for the given messages.

        Args:
            messages: List of messages in the conversation
            **kwargs: Provider-specific parameters

        Yields:
            LLMStreamResponse chunks

        Raises:
            LLMProviderError: If the request fails
        """
        pass

    async def complete_with_retry(
        self,
        messages: list[LLMMessage],
        **kwargs: Any,
    ) -> LLMResponse:
        """Complete with automatic retry on failure.

        Args:
            messages: List of messages in the conversation
            **kwargs: Provider-specific parameters

        Returns:
            LLMResponse with the generated content

        Raises:
            LLMProviderError: If all retry attempts fail
        """
        last_error = None

        for attempt in range(self.config.retry_attempts):
            try:
                return await self.complete(messages, **kwargs)
            except LLMProviderRateLimitError as e:
                last_error = e
                if attempt < self.config.retry_attempts - 1:
                    delay = self.config.retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
            except LLMProviderTimeoutError as e:
                last_error = e
                if attempt < self.config.retry_attempts - 1:
                    delay = self.config.retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
            except LLMProviderAuthError as e:
                raise e
            except LLMProviderError as e:
                last_error = e
                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay)

        raise last_error or LLMProviderError("Failed to complete request after retries")

    def get_stats(self) -> dict[str, Any]:
        """Get provider statistics.

        Returns:
            Dictionary with request count, total cost, etc.
        """
        return {
            "provider": self.config.provider.value if isinstance(self.config.provider, ProviderType) else self.config.provider,
            "model": self.config.model,
            "request_count": self._request_count,
            "total_cost_usd": self._total_cost,
        }

    def _record_request(self, cost: float = 0.0) -> None:
        """Record a request for statistics."""
        self._request_count += 1
        self._total_cost += cost
        self._last_request_time = time.time()

    def _calculate_cost(self, usage: dict[str, int]) -> float:
        """Calculate cost for a request. Override in subclasses."""
        return 0.0
