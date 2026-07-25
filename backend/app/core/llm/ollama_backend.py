"""Ollama local-model backend for the production LLMRouter (P1-08).

Talks directly to an Ollama server (default http://localhost:11434) over
httpx — no extra dependency. Tests can inject an ``httpx.AsyncClient`` built
on ``httpx.MockTransport`` to exercise the backend offline.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from backend.app.core.llm.backends import (
    BaseLLMBackend,
    LLMBackendError,
    LLMResponse,
    TokenUsage,
    _normalize_tool_parameters,
)

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"


def _to_ollama_tool(tool: dict[str, Any]) -> dict[str, Any]:
    """Convert a tool definition into Ollama's function-calling shape."""
    if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
        fn = dict(tool["function"])
        fn["parameters"] = _normalize_tool_parameters(fn.get("parameters"))
        return {"type": "function", "function": fn}
    return {
        "type": "function",
        "function": {
            "name": tool.get("name", "unknown"),
            "description": tool.get("description", ""),
            "parameters": _normalize_tool_parameters(tool.get("parameters")),
        },
    }


class OllamaBackend(BaseLLMBackend):
    """Ollama `/api/chat` backend (local models, zero API cost)."""

    def __init__(
        self,
        model: str,
        *,
        base_url: str = DEFAULT_OLLAMA_BASE_URL,
        name: str = "ollama",
        timeout: float = 120.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.name = name
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._http_client = http_client

    def _client_kwargs(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "timeout": httpx.Timeout(self.timeout),
        }

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        """Send a chat request to the Ollama server."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": m.get("role", "user"), "content": m.get("content", "")}
                for m in messages
            ],
            "stream": False,
        }
        if tools:
            payload["tools"] = [_to_ollama_tool(tool) for tool in tools]

        start_time = time.time()
        try:
            if self._http_client is not None:
                response = await self._http_client.post("/api/chat", json=payload)
            else:
                async with httpx.AsyncClient(**self._client_kwargs()) as client:
                    response = await client.post("/api/chat", json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMBackendError(
                f"{self.name} backend failed (base_url={self.base_url}): {exc}"
            ) from exc

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise LLMBackendError(
                f"{self.name} returned a non-JSON response: {exc}"
            ) from exc

        message = data.get("message") or {}
        tool_calls = [
            {
                "name": (tc.get("function") or {}).get("name", "unknown"),
                "arguments": (tc.get("function") or {}).get("arguments") or {},
            }
            for tc in (message.get("tool_calls") or [])
        ]

        prompt_tokens = int(data.get("prompt_eval_count") or 0)
        completion_tokens = int(data.get("eval_count") or 0)
        token_usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
        cost = token_usage.calculate_cost(self.model)  # 0 for local profiles
        latency_ms = (time.time() - start_time) * 1000

        logger.info(
            "%s chat completed: tokens=%s, latency=%.0fms",
            self.name,
            token_usage.total_tokens,
            latency_ms,
        )

        return LLMResponse(
            content=message.get("content") or "",
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
        """Stream chat responses token by token (NDJSON lines)."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": m.get("role", "user"), "content": m.get("content", "")}
                for m in messages
            ],
            "stream": True,
        }
        if tools:
            payload["tools"] = [_to_ollama_tool(tool) for tool in tools]

        owns_client = self._http_client is None
        client = self._http_client or httpx.AsyncClient(**self._client_kwargs())
        try:
            async with client.stream("POST", "/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    text = (chunk.get("message") or {}).get("content")
                    if text:
                        yield text
                    if chunk.get("done"):
                        break
        except httpx.HTTPError as exc:
            raise LLMBackendError(f"{self.name} streaming failed: {exc}") from exc
        finally:
            if owns_client:
                await client.aclose()
