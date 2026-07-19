"""OpenAI LLM adapter."""

from __future__ import annotations

from typing import Any, Optional, AsyncIterator
import time
from .base import LLMAdapter, AdapterResponse


class OpenAIAdapter(LLMAdapter):
    """Adapter for OpenAI models."""

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: Optional[str] = None,
        **kwargs,
    ):
        """Initialize OpenAI adapter."""
        super().__init__(model, **kwargs)
        self.api_key = api_key
        self.base_url = base_url or "https://api.openai.com/v1"
        self._client = None

    def _get_client(self):
        """Get or create OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError:
                raise ImportError("openai package is required")

            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )

        return self._client

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs,
    ) -> AdapterResponse:
        """Send a chat request to OpenAI."""
        client = self._get_client()
        start_time = time.time()

        try:
            # Convert messages to OpenAI format
            openai_messages = self._convert_messages(messages)

            # Prepare request
            request_kwargs = {
                "model": self.model,
                "messages": openai_messages,
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 2000),
            }

            if tools:
                request_kwargs["tools"] = self._convert_tools(tools)

            # Make request
            response = await client.chat.completions.create(**request_kwargs)

            # Extract response
            content = ""
            tool_calls = []

            if response.choices and response.choices[0].message:
                message = response.choices[0].message
                content = message.content or ""

                if message.tool_calls:
                    tool_calls = [
                        {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                        for tc in message.tool_calls
                    ]

            # Get token usage
            tokens_used = 0
            if response.usage:
                tokens_used = response.usage.total_tokens

            latency_ms = (time.time() - start_time) * 1000

            return AdapterResponse(
                content=content,
                tool_calls=tool_calls,
                tokens_used=tokens_used,
                model=self.model,
                latency_ms=latency_ms,
            )

        except Exception as e:
            raise RuntimeError(f"OpenAI API error: {e}")

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream a chat response from OpenAI."""
        client = self._get_client()

        try:
            openai_messages = self._convert_messages(messages)

            request_kwargs = {
                "model": self.model,
                "messages": openai_messages,
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 2000),
                "stream": True,
            }

            if tools:
                request_kwargs["tools"] = self._convert_tools(tools)

            stream = await client.chat.completions.create(**request_kwargs)

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content

        except Exception as e:
            raise RuntimeError(f"OpenAI streaming error: {e}")

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for OpenAI models."""
        # Rough estimate: 1 token ≈ 4 characters
        return max(1, len(text) // 4)

    def get_model_info(self) -> dict[str, Any]:
        """Get OpenAI model information."""
        model_info = {
            "gpt-4o": {
                "max_tokens": 128000,
                "cost_per_1k_input": 0.005,
                "cost_per_1k_output": 0.015,
            },
            "gpt-4o-mini": {
                "max_tokens": 128000,
                "cost_per_1k_input": 0.00015,
                "cost_per_1k_output": 0.0006,
            },
            "gpt-4-turbo": {
                "max_tokens": 128000,
                "cost_per_1k_input": 0.01,
                "cost_per_1k_output": 0.03,
            },
        }

        return model_info.get(self.model, {
            "max_tokens": 4096,
            "cost_per_1k_input": 0.01,
            "cost_per_1k_output": 0.03,
        })

    def _convert_messages(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """Convert messages to OpenAI format."""
        openai_messages = []

        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")

            if role == "tool":
                # Convert tool messages to user messages
                openai_messages.append({
                    "role": "user",
                    "content": f"Tool output:\n{content}",
                })
            elif role in {"user", "assistant", "system", "developer"}:
                openai_messages.append({
                    "role": role,
                    "content": content,
                })
            else:
                openai_messages.append({
                    "role": "user",
                    "content": content,
                })

        return openai_messages

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert tools to OpenAI format."""
        openai_tools = []

        for tool in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {}),
                },
            })

        return openai_tools
