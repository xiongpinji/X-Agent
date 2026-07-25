"""Anthropic Claude backend for the production LLMRouter (P1-08).

Uses the official ``anthropic`` SDK when installed. The SDK is an optional
import: if it is missing, constructing the backend still succeeds but any call
raises :class:`LLMBackendError` with an explicit remediation message (no silent
degrade). Tests can inject an ``httpx.AsyncClient`` built on
``httpx.MockTransport`` to exercise the full request/response path offline.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

from backend.app.core.llm.backends import (
    BaseLLMBackend,
    LLMBackendError,
    LLMResponse,
    TokenUsage,
    _normalize_tool_parameters,
)

logger = logging.getLogger(__name__)


def _to_anthropic_tool(tool: dict[str, Any]) -> dict[str, Any]:
    """Convert a tool definition into Anthropic's tool shape."""
    if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
        fn = tool["function"]
        return {
            "name": fn.get("name", "unknown"),
            "description": fn.get("description", ""),
            "input_schema": _normalize_tool_parameters(fn.get("parameters")),
        }
    return {
        "name": tool.get("name", "unknown"),
        "description": tool.get("description", ""),
        "input_schema": _normalize_tool_parameters(tool.get("parameters")),
    }


def _split_system_messages(
    messages: list[dict[str, str]],
) -> tuple[str, list[dict[str, Any]]]:
    """Split system messages out; Anthropic takes `system` separately.

    Remaining roles map to user/assistant turns. Tool results are folded into
    user turns as plain text, the same provider-neutral approach the
    OpenAIResponses backend uses.
    """
    system_parts: list[str] = []
    conversation: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "") or ""
        if role == "system":
            system_parts.append(content)
        elif role == "assistant":
            conversation.append({"role": "assistant", "content": content})
        elif role == "tool":
            conversation.append({"role": "user", "content": f"Tool output:\n{content}"})
        else:
            conversation.append({"role": "user", "content": content})

    # Anthropic requires at least one non-system message.
    if not conversation:
        conversation.append({"role": "user", "content": ""})
    return "\n\n".join(part for part in system_parts if part), conversation


class AnthropicBackend(BaseLLMBackend):
    """Anthropic Messages API backend with tool-use and usage accounting.
    
    Uses a persistent AsyncAnthropic client with connection pooling for efficiency.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str | None = None,
        name: str = "anthropic",
        max_tokens: int = 4096,
        timeout: float = 60.0,
        max_retries: int = 2,
        http_client: Any | None = None,
        max_connections: int = 100,
    ) -> None:
        self.name = name
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries
        self._http_client = http_client
        self.max_connections = max_connections
        self._client: Any = None
        self._client_lock = asyncio.Lock()

    async def _get_client(self) -> Any:
        """Get or create the persistent AsyncAnthropic client with connection pooling."""
        if self._client is None:
            async with self._client_lock:
                if self._client is None:
                    try:
                        import httpx
                        from anthropic import AsyncAnthropic
                        
                        # Create HTTP client with connection pooling if not provided
                        http_client = self._http_client
                        if http_client is None:
                            http_client = httpx.AsyncClient(
                                limits=httpx.Limits(
                                    max_connections=self.max_connections,
                                    max_keepalive_connections=20,
                                    keepalive_expiry=30,
                                ),
                                timeout=httpx.Timeout(self.timeout, connect=10.0),
                            )
                        
                        kwargs: dict[str, Any] = {
                            "api_key": self.api_key,
                            "timeout": self.timeout,
                            "max_retries": self.max_retries,
                            "http_client": http_client,
                        }
                        if self.base_url:
                            kwargs["base_url"] = self.base_url
                        
                        self._client = AsyncAnthropic(**kwargs)
                        logger.info(f"Anthropic client initialized with connection pool (max_connections={self.max_connections})")
                    except ImportError as exc:
                        raise LLMBackendError(
                            "anthropic package is not installed; run "
                            "`pip install anthropic` or remove 'anthropic' from the LLM "
                            "fallback order"
                        ) from exc
        return self._client

    async def close(self) -> None:
        """Close the persistent client and release connections."""
        if self._client:
            with contextlib.suppress(Exception):
                await self._client.close()
            self._client = None

    def _make_client(self) -> Any:
        """Legacy sync method - creates a new client (deprecated, use _get_client)."""
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:
            raise LLMBackendError(
                "anthropic package is not installed; run "
                "`pip install anthropic` or remove 'anthropic' from the LLM "
                "fallback order"
            ) from exc

        kwargs: dict[str, Any] = {
            "api_key": self.api_key,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
        }
        if self.base_url:
            kwargs["base_url"] = self.base_url
        if self._http_client is not None:
            kwargs["http_client"] = self._http_client
        return AsyncAnthropic(**kwargs)

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        """Send a chat request to the Anthropic Messages API using persistent connection pool."""
        client = await self._get_client()
        system, conversation = _split_system_messages(messages)

        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": conversation,
            "max_tokens": self.max_tokens,
        }
        if system:
            request_kwargs["system"] = system
        if tools:
            request_kwargs["tools"] = [_to_anthropic_tool(tool) for tool in tools]

        start_time = time.time()
        try:
            response = await client.messages.create(**request_kwargs)
        except Exception as exc:
            raise LLMBackendError(f"{self.name} backend failed: {exc}") from exc

        content_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        for block in getattr(response, "content", []) or []:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                content_parts.append(getattr(block, "text", "") or "")
            elif block_type == "tool_use":
                arguments = getattr(block, "input", None)
                tool_calls.append(
                    {
                        "name": getattr(block, "name", "unknown"),
                        "arguments": arguments if isinstance(arguments, dict) else {},
                    }
                )

        usage = getattr(response, "usage", None)
        token_usage = TokenUsage(
            prompt_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
            completion_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
            total_tokens=(
                (getattr(usage, "input_tokens", 0) or 0)
                + (getattr(usage, "output_tokens", 0) or 0)
            )
            if usage
            else 0,
        )
        cost = token_usage.calculate_cost(self.model)
        latency_ms = (time.time() - start_time) * 1000

        logger.info(
            "%s chat completed: tokens=%s, cost=$%.4f, latency=%.0fms",
            self.name,
            token_usage.total_tokens,
            cost,
            latency_ms,
        )

        return LLMResponse(
            content="".join(content_parts),
            tool_calls=tool_calls,
            tokens_used=token_usage.total_tokens,
            model=self.model,
            cost=cost,
            latency_ms=latency_ms,
        )

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
    ) -> AsyncGenerator[str, None]:
        """Stream chat responses token by token."""
        client = self._make_client()
        system, conversation = _split_system_messages(messages)

        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": conversation,
            "max_tokens": self.max_tokens,
        }
        if system:
            request_kwargs["system"] = system
        if tools:
            request_kwargs["tools"] = [_to_anthropic_tool(tool) for tool in tools]

        try:
            async with client.messages.stream(**request_kwargs) as stream:
                async for text in stream.text_stream:
                    if text:
                        yield text
        except Exception as exc:
            raise LLMBackendError(f"{self.name} streaming failed: {exc}") from exc
