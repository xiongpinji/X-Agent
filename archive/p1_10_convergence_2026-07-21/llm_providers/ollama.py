"""Ollama LLM Provider Implementation

Supports local models via Ollama.
"""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from typing import Any

from .base import (
    BaseLLMProvider,
    LLMConfig,
    LLMMessage,
    LLMProviderError,
    LLMProviderTimeoutError,
    LLMResponse,
    LLMStreamResponse,
)


class OllamaProvider(BaseLLMProvider):
    """Ollama LLM Provider.

    Supports local models via Ollama API.
    """

    DEFAULT_BASE_URL = "http://localhost:11434"

    def __init__(self, config: LLMConfig) -> None:
        """Initialize Ollama provider."""
        super().__init__(config)
        if not config.base_url:
            config.base_url = self.DEFAULT_BASE_URL
        self._client = None

    def _get_client(self) -> Any:
        """Get or create Ollama client."""
        if self._client is None:
            try:
                import httpx
            except ImportError as exc:
                raise RuntimeError("httpx package is not installed") from exc

            self._client = httpx.AsyncClient(
                base_url=self.config.base_url or self.DEFAULT_BASE_URL,
                timeout=self.config.timeout,
            )

        return self._client

    async def complete(
        self,
        messages: list[LLMMessage],
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion using Ollama API."""
        client = self._get_client()
        start_time = time.time()

        try:
            # Prepare request parameters
            request_params = {
                "model": self.config.model,
                "messages": [msg.to_dict() for msg in messages],
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
                "stream": False,
            }

            if self.config.max_tokens:
                request_params["num_predict"] = self.config.max_tokens

            # Merge with kwargs
            request_params.update(kwargs)

            # Make request
            response = await client.post(
                "/api/chat",
                json=request_params,
            )

            if response.status_code != 200:
                raise LLMProviderError(f"Ollama API error: {response.text}")

            data = response.json()

            # Extract response data
            content = data.get("message", {}).get("content", "")
            usage = {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
            }

            # Calculate cost (Ollama is local, so no cost)
            cost = 0.0
            self._record_request(cost)

            latency_ms = (time.time() - start_time) * 1000

            return LLMResponse(
                content=content,
                model=self.config.model,
                provider="ollama",
                usage=usage,
                finish_reason="stop",
                raw_response=data,
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
        """Stream a completion using Ollama API."""
        client = self._get_client()

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
                request_params["num_predict"] = self.config.max_tokens

            # Merge with kwargs
            request_params.update(kwargs)

            # Make streaming request
            async with await client.stream(
                "POST",
                "/api/chat",
                json=request_params,
            ) as response:
                if response.status_code != 200:
                    raise LLMProviderError(f"Ollama API error: {response.text}")

                async for line in response.aiter_lines():
                    if line:
                        import json
                        try:
                            data = json.loads(line)
                            if "message" in data and "content" in data["message"]:
                                yield LLMStreamResponse(
                                    content=data["message"]["content"],
                                    model=self.config.model,
                                    provider="ollama",
                                    finish_reason="stop" if data.get("done") else None,
                                )
                        except json.JSONDecodeError:
                            continue

            self._record_request()

        except Exception as e:
            self._handle_error(e)

    def _calculate_cost(self, usage: dict[str, int]) -> float:
        """Calculate cost for Ollama (always 0 for local models)."""
        return 0.0

    def _handle_error(self, error: Exception) -> None:
        """Handle and convert Ollama errors to provider errors."""
        error_str = str(error).lower()

        if "connection" in error_str or "refused" in error_str:
            raise LLMProviderError(
                f"Ollama connection failed. Make sure Ollama is running at {self.config.base_url}: {error}"
            ) from error

        if "timeout" in error_str or "timed out" in error_str:
            raise LLMProviderTimeoutError(f"Ollama request timeout: {error}") from error

        if "not found" in error_str or "model" in error_str:
            raise LLMProviderError(
                f"Ollama model not found. Make sure '{self.config.model}' is pulled: {error}"
            ) from error

        raise LLMProviderError(f"Ollama API error: {error}") from error
