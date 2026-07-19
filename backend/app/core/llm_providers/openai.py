"""OpenAI LLM Provider Implementation

Supports GPT-4, GPT-3.5-turbo, and other OpenAI models.
"""

from __future__ import annotations

import time
from typing import Any, AsyncGenerator, Optional

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


class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM Provider.

    Supports GPT-4, GPT-3.5-turbo, and other OpenAI models.
    """

    def __init__(self, config: LLMConfig) -> None:
        """Initialize OpenAI provider."""
        super().__init__(config)
        self._client = None
        self._async_client = None

    def _get_client(self) -> Any:
        """Get or create OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError("openai package is not installed") from exc

            if not self.config.api_key:
                raise LLMProviderAuthError("OpenAI API key is required")

            self._client = OpenAI(
                api_key=self.config.api_key,
                timeout=self.config.timeout,
            )

        return self._client

    def _get_async_client(self) -> Any:
        """Get or create async OpenAI client."""
        if self._async_client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:
                raise RuntimeError("openai package is not installed") from exc

            if not self.config.api_key:
                raise LLMProviderAuthError("OpenAI API key is required")

            self._async_client = AsyncOpenAI(
                api_key=self.config.api_key,
                timeout=self.config.timeout,
            )

        return self._async_client

    async def complete(
        self,
        messages: list[LLMMessage],
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion using OpenAI API."""
        client = self._get_async_client()
        start_time = time.time()

        try:
            # Prepare request parameters
            request_params = {
                "model": self.config.model,
                "messages": [msg.to_dict() for msg in messages],
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
            }

            if self.config.max_tokens:
                request_params["max_tokens"] = self.config.max_tokens

            # Merge with kwargs
            request_params.update(kwargs)

            # Make request
            response = await client.chat.completions.create(**request_params)

            # Extract response data
            content = response.choices[0].message.content or ""
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

            # Calculate cost
            cost = self._calculate_cost(usage)
            self._record_request(cost)

            latency_ms = (time.time() - start_time) * 1000

            return LLMResponse(
                content=content,
                model=self.config.model,
                provider="openai",
                usage=usage,
                finish_reason=response.choices[0].finish_reason or "stop",
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
        """Stream a completion using OpenAI API."""
        client = self._get_async_client()

        try:
            # Prepare request parameters
            request_params = {
                "model": self.config.model,
                "messages": [msg.to_dict() for msg in messages],
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
                "stream": True,
            }

            if self.config.max_tokens:
                request_params["max_tokens"] = self.config.max_tokens

            # Merge with kwargs
            request_params.update(kwargs)

            # Make streaming request
            async with await client.chat.completions.create(**request_params) as response:
                async for chunk in response:
                    if chunk.choices[0].delta.content:
                        yield LLMStreamResponse(
                            content=chunk.choices[0].delta.content,
                            model=self.config.model,
                            provider="openai",
                            finish_reason=chunk.choices[0].finish_reason,
                        )

            self._record_request()

        except Exception as e:
            raise self._handle_error(e)

    def _calculate_cost(self, usage: dict[str, int]) -> float:
        """Calculate cost for OpenAI API call.

        Pricing as of 2024:
        - GPT-4: $0.03 per 1K prompt tokens, $0.06 per 1K completion tokens
        - GPT-3.5-turbo: $0.0005 per 1K prompt tokens, $0.0015 per 1K completion tokens
        """
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        if "gpt-4" in self.config.model.lower():
            prompt_cost = (prompt_tokens / 1000) * 0.03
            completion_cost = (completion_tokens / 1000) * 0.06
        elif "gpt-3.5" in self.config.model.lower():
            prompt_cost = (prompt_tokens / 1000) * 0.0005
            completion_cost = (completion_tokens / 1000) * 0.0015
        else:
            # Default to GPT-3.5 pricing for unknown models
            prompt_cost = (prompt_tokens / 1000) * 0.0005
            completion_cost = (completion_tokens / 1000) * 0.0015

        return prompt_cost + completion_cost

    def _handle_error(self, error: Exception) -> LLMProviderError:
        """Handle and convert OpenAI errors to provider errors."""
        error_str = str(error).lower()

        if "authentication" in error_str or "invalid api key" in error_str:
            return LLMProviderAuthError(f"OpenAI authentication failed: {error}")

        if "rate limit" in error_str or "429" in error_str:
            return LLMProviderRateLimitError(f"OpenAI rate limit exceeded: {error}")

        if "timeout" in error_str or "timed out" in error_str:
            return LLMProviderTimeoutError(f"OpenAI request timeout: {error}")

        return LLMProviderError(f"OpenAI API error: {error}")
