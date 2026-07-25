"""DeepSeek LLM Provider Implementation

Supports DeepSeek models via OpenAI-compatible API.
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


class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek LLM Provider.

    Uses OpenAI-compatible API for DeepSeek models.
    """

    DEFAULT_BASE_URL = "https://api.deepseek.com"

    def __init__(self, config: LLMConfig) -> None:
        """Initialize DeepSeek provider."""
        super().__init__(config)
        if not config.base_url:
            config.base_url = self.DEFAULT_BASE_URL
        self._client = None
        self._async_client = None

    def _get_client(self) -> Any:
        """Get or create DeepSeek client."""
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError("openai package is not installed") from exc

            if not self.config.api_key:
                raise LLMProviderAuthError("DeepSeek API key is required")

            self._client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url or self.DEFAULT_BASE_URL,
                timeout=self.config.timeout,
            )

        return self._client

    def _get_async_client(self) -> Any:
        """Get or create async DeepSeek client."""
        if self._async_client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:
                raise RuntimeError("openai package is not installed") from exc

            if not self.config.api_key:
                raise LLMProviderAuthError("DeepSeek API key is required")

            self._async_client = AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url or self.DEFAULT_BASE_URL,
                timeout=self.config.timeout,
            )

        return self._async_client

    async def complete(
        self,
        messages: list[LLMMessage],
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion using DeepSeek API."""
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
                provider="deepseek",
                usage=usage,
                finish_reason=response.choices[0].finish_reason or "stop",
                raw_response=response.model_dump(),
                latency_ms=latency_ms,
                cost_usd=cost,
            )

        except Exception as e:
            self._handle_error(e)

    async def stream(
        self,
        messages: list[LLMMessage],
        **kwargs: Any,
    ) -> AsyncGenerator[LLMStreamResponse, None]:
        """Stream a completion using DeepSeek API."""
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
                            provider="deepseek",
                            finish_reason=chunk.choices[0].finish_reason,
                        )

            self._record_request()

        except Exception as e:
            self._handle_error(e)

    def _calculate_cost(self, usage: dict[str, int]) -> float:
        """Calculate cost for DeepSeek API call.

        Pricing as of 2024:
        - DeepSeek-V3: $0.27 per 1M prompt tokens, $1.10 per 1M completion tokens
        - DeepSeek-R1: $0.55 per 1M prompt tokens, $2.19 per 1M completion tokens
        """
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        if "r1" in self.config.model.lower():
            prompt_cost = (prompt_tokens / 1_000_000) * 0.55
            completion_cost = (completion_tokens / 1_000_000) * 2.19
        else:
            # Default to V3 pricing
            prompt_cost = (prompt_tokens / 1_000_000) * 0.27
            completion_cost = (completion_tokens / 1_000_000) * 1.10

        return prompt_cost + completion_cost

    def _handle_error(self, error: Exception) -> None:
        """Handle and convert DeepSeek errors to provider errors."""
        error_str = str(error).lower()

        if "authentication" in error_str or "invalid api key" in error_str or "unauthorized" in error_str:
            raise LLMProviderAuthError(f"DeepSeek authentication failed: {error}") from error

        if "rate limit" in error_str or "429" in error_str:
            raise LLMProviderRateLimitError(f"DeepSeek rate limit exceeded: {error}") from error

        if "timeout" in error_str or "timed out" in error_str:
            raise LLMProviderTimeoutError(f"DeepSeek request timeout: {error}") from error

        raise LLMProviderError(f"DeepSeek API error: {error}") from error
