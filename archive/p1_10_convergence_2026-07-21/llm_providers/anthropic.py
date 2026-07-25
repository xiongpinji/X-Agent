"""Anthropic LLM Provider Implementation

Supports Claude 3.5 Sonnet, Claude 3 Opus, and other Anthropic models.
"""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from typing import Any

from .base import (
    BaseLLMProvider,
    LLMConfig,
    LLMMessage,
    LLMProviderAuthError,
    LLMProviderError,
    LLMProviderRateLimitError,
    LLMProviderTimeoutError,
    LLMResponse,
    LLMStreamResponse,
)


class AnthropicProvider(BaseLLMProvider):
    """Anthropic LLM Provider.

    Supports Claude 3.5 Sonnet, Claude 3 Opus, and other Anthropic models.
    """

    def __init__(self, config: LLMConfig) -> None:
        """Initialize Anthropic provider."""
        super().__init__(config)
        self._client = None
        self._async_client = None

    def _get_client(self) -> Any:
        """Get or create Anthropic client."""
        if self._client is None:
            try:
                from anthropic import Anthropic
            except ImportError as exc:
                raise RuntimeError("anthropic package is not installed") from exc

            if not self.config.api_key:
                raise LLMProviderAuthError("Anthropic API key is required")

            self._client = Anthropic(
                api_key=self.config.api_key,
                timeout=self.config.timeout,
            )

        return self._client

    def _get_async_client(self) -> Any:
        """Get or create async Anthropic client."""
        if self._async_client is None:
            try:
                from anthropic import AsyncAnthropic
            except ImportError as exc:
                raise RuntimeError("anthropic package is not installed") from exc

            if not self.config.api_key:
                raise LLMProviderAuthError("Anthropic API key is required")

            self._async_client = AsyncAnthropic(
                api_key=self.config.api_key,
                timeout=self.config.timeout,
            )

        return self._async_client

    async def complete(
        self,
        messages: list[LLMMessage],
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion using Anthropic API."""
        client = self._get_async_client()
        start_time = time.time()

        try:
            # Separate system message from other messages
            system_message = None
            user_messages = []

            for msg in messages:
                role = msg.role if isinstance(msg.role, str) else msg.role.value
                if role == "system":
                    system_message = msg.content
                else:
                    user_messages.append(msg)

            # Prepare request parameters
            request_params = {
                "model": self.config.model,
                "messages": [msg.to_dict() for msg in user_messages],
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
            }

            if system_message:
                request_params["system"] = system_message

            if self.config.max_tokens:
                request_params["max_tokens"] = self.config.max_tokens
            else:
                # Anthropic requires max_tokens
                request_params["max_tokens"] = 4096

            # Merge with kwargs
            request_params.update(kwargs)

            # Make request
            response = await client.messages.create(**request_params)

            # Extract response data
            content = response.content[0].text if response.content else ""
            usage = {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            }

            # Calculate cost
            cost = self._calculate_cost(usage)
            self._record_request(cost)

            latency_ms = (time.time() - start_time) * 1000

            return LLMResponse(
                content=content,
                model=self.config.model,
                provider="anthropic",
                usage=usage,
                finish_reason=response.stop_reason or "stop",
                raw_response=response.model_dump(),
                latency_ms=latency_ms,
                cost_usd=cost,
            )

        except Exception as e:
            raise self._handle_error(e)

    async def stream(
        self,
        messages: list[LLMMessage],
        **kwargs: Any,
    ) -> AsyncGenerator[LLMStreamResponse, None]:
        """Stream a completion using Anthropic API."""
        client = self._get_async_client()

        try:
            # Separate system message from other messages
            system_message = None
            user_messages = []

            for msg in messages:
                role = msg.role if isinstance(msg.role, str) else msg.role.value
                if role == "system":
                    system_message = msg.content
                else:
                    user_messages.append(msg)

            # Prepare request parameters
            request_params = {
                "model": self.config.model,
                "messages": [msg.to_dict() for msg in user_messages],
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
            }

            if system_message:
                request_params["system"] = system_message

            if self.config.max_tokens:
                request_params["max_tokens"] = self.config.max_tokens
            else:
                request_params["max_tokens"] = 4096

            # Merge with kwargs
            request_params.update(kwargs)

            # Make streaming request
            with await client.messages.stream(**request_params) as stream:
                async for text in stream.text_stream:
                    yield LLMStreamResponse(
                        content=text,
                        model=self.config.model,
                        provider="anthropic",
                    )

            self._record_request()

        except Exception as e:
            raise self._handle_error(e)

    def _calculate_cost(self, usage: dict[str, int]) -> float:
        """Calculate cost for Anthropic API call.

        Pricing as of 2024:
        - Claude 3.5 Sonnet: $3 per 1M prompt tokens, $15 per 1M completion tokens
        - Claude 3 Opus: $15 per 1M prompt tokens, $75 per 1M completion tokens
        """
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        if "sonnet" in self.config.model.lower():
            prompt_cost = (prompt_tokens / 1_000_000) * 3
            completion_cost = (completion_tokens / 1_000_000) * 15
        elif "opus" in self.config.model.lower():
            prompt_cost = (prompt_tokens / 1_000_000) * 15
            completion_cost = (completion_tokens / 1_000_000) * 75
        elif "haiku" in self.config.model.lower():
            prompt_cost = (prompt_tokens / 1_000_000) * 0.8
            completion_cost = (completion_tokens / 1_000_000) * 4
        else:
            # Default to Sonnet pricing for unknown models
            prompt_cost = (prompt_tokens / 1_000_000) * 3
            completion_cost = (completion_tokens / 1_000_000) * 15

        return prompt_cost + completion_cost

    def _handle_error(self, error: Exception) -> LLMProviderError:
        """Handle and convert Anthropic errors to provider errors."""
        error_str = str(error).lower()

        if "authentication" in error_str or "invalid api key" in error_str or "unauthorized" in error_str:
            return LLMProviderAuthError(f"Anthropic authentication failed: {error}")

        if "rate limit" in error_str or "429" in error_str:
            return LLMProviderRateLimitError(f"Anthropic rate limit exceeded: {error}")

        if "timeout" in error_str or "timed out" in error_str:
            return LLMProviderTimeoutError(f"Anthropic request timeout: {error}")

        return LLMProviderError(f"Anthropic API error: {error}")
