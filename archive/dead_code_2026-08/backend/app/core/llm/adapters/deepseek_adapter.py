"""DeepSeek LLM adapter."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

from .base import AdapterResponse, LLMAdapter


class DeepSeekAdapter(LLMAdapter):
    """Adapter for DeepSeek models."""

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str = "https://api.deepseek.com/v1",
        **kwargs,
    ):
        """Initialize DeepSeek adapter."""
        super().__init__(model, **kwargs)
        self.api_key = api_key
        self.base_url = base_url
        self._client = None

    def _get_client(self):
        """Get or create DeepSeek client."""
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
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> AdapterResponse:
        """Send a chat request to DeepSeek."""
        client = self._get_client()
        start_time = time.time()

        try:
            openai_messages = self._convert_messages(messages)

            request_kwargs = {
                "model": self.model,
                "messages": openai_messages,
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 2000),
            }

            if tools:
                request_kwargs["tools"] = self._convert_tools(tools)

            response = await client.chat.completions.create(**request_kwargs)

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
            raise RuntimeError(f"DeepSeek API error: {e}")

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream a chat response from DeepSeek."""
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
            raise RuntimeError(f"DeepSeek streaming error: {e}")

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for DeepSeek models."""
        return max(1, len(text) // 4)

    def get_model_info(self) -> dict[str, Any]:
        """Get DeepSeek model information."""
        model_info = {
            "deepseek-chat": {
                "max_tokens": 64000,
                "cost_per_1k_input": 0.0014,
                "cost_per_1k_output": 0.0042,
            },
            "deepseek-coder": {
                "max_tokens": 64000,
                "cost_per_1k_input": 0.0014,
                "cost_per_1k_output": 0.0042,
            },
        }

        return model_info.get(self.model, {
            "max_tokens": 64000,
            "cost_per_1k_input": 0.0014,
            "cost_per_1k_output": 0.0042,
        })

    def _convert_messages(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """Convert messages to DeepSeek format."""
        deepseek_messages = []

        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")

            if role == "tool":
                deepseek_messages.append({
                    "role": "user",
                    "content": f"Tool output:\n{content}",
                })
            elif role in {"user", "assistant", "system"}:
                deepseek_messages.append({
                    "role": role,
                    "content": content,
                })
            else:
                deepseek_messages.append({
                    "role": "user",
                    "content": content,
                })

        return deepseek_messages

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert tools to DeepSeek format."""
        deepseek_tools = []

        for tool in tools:
            deepseek_tools.append({
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {}),
                },
            })

        return deepseek_tools
