"""Provider backends and the core LLMRouter for X-Agent.

This module was historically ``backend/app/core/llm.py``. When the ``llm/``
package (model selection, cost optimization, adapters, etc.) was added, the
package began shadowing the module and ``from backend.app.core.llm import
LLMRouter`` started failing at import time. The backend classes now live here
inside the package and are re-exported from ``llm/__init__.py`` so both the
legacy callers and the newer enhanced-routing code share one namespace.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    content: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tokens_used: int = 0
    model: str = "mock"
    cost: float = 0.0
    latency_ms: float = 0.0


@dataclass
class TokenUsage:
    """Token usage tracking for cost calculation."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def calculate_cost(self, model: str) -> float:
        """Calculate cost based on model pricing."""
        pricing = {
            "gpt-4": {"prompt": 0.03, "completion": 0.06},
            "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
            "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
            "gpt-4o": {"prompt": 0.005, "completion": 0.015},
        }
        rates = pricing.get(model, {"prompt": 0.0, "completion": 0.0})
        return (self.prompt_tokens * rates["prompt"] +
                self.completion_tokens * rates["completion"]) / 1000
class BaseLLMBackend:
    name = "base"

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        raise NotImplementedError

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
    ) -> AsyncGenerator[str, None]:
        """Stream chat responses token by token."""
        raise NotImplementedError


class LLMBackendError(RuntimeError):
    """Raised when a provider backend cannot complete a chat request."""


class MockLLMBackend(BaseLLMBackend):
    """Deterministic local LLM substitute for tests and first-run smoke checks."""

    name = "mock"

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        if messages and messages[-1]["role"] == "tool":
            tool_output = messages[-1]["content"]
            return LLMResponse(
                content=f"Tool result observed: {tool_output}",
                tokens_used=len(tool_output.split()),
            )

        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        task_line = next(
            (
                line.removeprefix("Task:").strip()
                for line in last_user.splitlines()
                if line.startswith("Task:")
            ),
            last_user,
        )
        if task_line.lower().startswith("echo:"):
            return LLMResponse(
                tool_calls=[
                    {
                        "name": "echo",
                        "arguments": {"text": task_line.split(":", 1)[1].strip()},
                    }
                ],
                tokens_used=len(task_line.split()),
            )
        return LLMResponse(
            content=f"X-Agent Phase 0 mock response: {task_line}",
            tokens_used=len(task_line.split()),
        )
class OpenAIBackend(BaseLLMBackend):
    """Full-featured OpenAI API backend with streaming, retries, rate limiting, and cost tracking."""

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str | None = None,
        name: str = "openai",
        max_retries: int = 3,
        retry_delay: float = 1.0,
        rate_limit_rpm: int = 3500,
        timeout: float = 30.0,
    ) -> None:
        self.name = name
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.rate_limit_rpm = rate_limit_rpm
        self.timeout = timeout
        self._request_times: list[float] = []
        self._lock = asyncio.Lock()

    async def _check_rate_limit(self) -> None:
        """Check and enforce rate limiting."""
        async with self._lock:
            now = time.time()
            # Remove old requests outside the 1-minute window
            self._request_times = [t for t in self._request_times if now - t < 60]

            if len(self._request_times) >= self.rate_limit_rpm:
                sleep_time = 60 - (now - self._request_times[0])
                if sleep_time > 0:
                    logger.warning(f"Rate limit approaching, sleeping {sleep_time:.1f}s")
                    await asyncio.sleep(sleep_time)

            self._request_times.append(now)

    async def _retry_with_backoff(
        self,
        coro,
        attempt: int = 0,
    ) -> Any:
        """Retry with exponential backoff."""
        try:
            await self._check_rate_limit()
            return await asyncio.wait_for(coro, timeout=self.timeout)
        except (asyncio.TimeoutError, Exception) as exc:
            if attempt < self.max_retries:
                delay = self.retry_delay * (2 ** attempt)
                logger.warning(
                    f"Attempt {attempt + 1} failed: {exc}. Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
                return await self._retry_with_backoff(coro, attempt + 1)
            raise LLMBackendError(f"{self.name} failed after {self.max_retries} retries: {exc}") from exc
    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        """Send a chat request to OpenAI API."""
        try:
            from openai import APIError, AsyncOpenAI
        except ImportError as exc:
            raise LLMBackendError("openai package is not installed") from exc

        client_kwargs: dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url

        client = AsyncOpenAI(**client_kwargs)
        start_time = time.time()

        try:
            # Prepare request
            request_kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.7,
            }

            if tools:
                request_kwargs["tools"] = [
                    {
                        "type": "function",
                        "function": {
                            "name": tool.get("name", "unknown"),
                            "description": tool.get("description", ""),
                            "parameters": tool.get("parameters", {}),
                        },
                    }
                    for tool in tools
                ]

            # Make request with retry logic
            response = await self._retry_with_backoff(
                client.chat.completions.create(**request_kwargs)
            )

            # Extract response data
            content = ""
            tool_calls = []

            if response.choices and response.choices[0].message:
                msg = response.choices[0].message
                content = msg.content or ""

                if msg.tool_calls:
                    tool_calls = [
                        {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                        for tc in msg.tool_calls
                    ]

            # Calculate usage and cost
            usage = response.usage
            token_usage = TokenUsage(
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
            )
            cost = token_usage.calculate_cost(self.model)
            latency_ms = (time.time() - start_time) * 1000

            logger.info(
                f"{self.name} chat completed: "
                f"tokens={token_usage.total_tokens}, cost=${cost:.4f}, latency={latency_ms:.0f}ms"
            )

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                tokens_used=token_usage.total_tokens,
                model=self.model,
                cost=cost,
                latency_ms=latency_ms,
            )

        except APIError as exc:
            raise LLMBackendError(f"{self.name} API error: {exc}") from exc
        except Exception as exc:
            raise LLMBackendError(f"{self.name} backend failed: {exc}") from exc

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
    ) -> AsyncGenerator[str, None]:
        """Stream chat responses token by token."""
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise LLMBackendError("openai package is not installed") from exc

        client_kwargs: dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url

        client = AsyncOpenAI(**client_kwargs)

        try:
            request_kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.7,
                "stream": True,
            }

            if tools:
                request_kwargs["tools"] = [
                    {
                        "type": "function",
                        "function": {
                            "name": tool.get("name", "unknown"),
                            "description": tool.get("description", ""),
                            "parameters": tool.get("parameters", {}),
                        },
                    }
                    for tool in tools
                ]

            stream = await self._retry_with_backoff(
                client.chat.completions.create(**request_kwargs)
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content

        except Exception as exc:
            raise LLMBackendError(f"{self.name} streaming failed: {exc}") from exc
class OpenAIResponsesBackend(BaseLLMBackend):
    """OpenAI Responses API backend (legacy, for compatibility).

    Phase 0 intentionally uses provider text responses only. Tool calls stay inside
    X-Agent's ToolRegistry so policy checks and trace events remain provider-neutral.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str | None = None,
        name: str = "openai",
    ) -> None:
        self.name = name
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        try:
            from openai import APIError, AsyncOpenAI
        except ImportError as exc:  # pragma: no cover - dependency exists in project deps
            raise LLMBackendError("openai package is not installed") from exc

        client_kwargs: dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        client = AsyncOpenAI(**client_kwargs)

        try:
            response = await client.responses.create(
                model=self.model,
                input=self._to_response_input(messages),
            )
        except APIError as exc:
            raise LLMBackendError(f"{self.name} API error: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 - provider failures are normalized for fallback
            raise LLMBackendError(f"{self.name} backend failed: {exc}") from exc

        output_text = getattr(response, "output_text", None)
        if not output_text:
            output_text = str(response.output) if getattr(response, "output", None) else ""

        usage = getattr(response, "usage", None)
        tokens_used = getattr(usage, "total_tokens", 0) if usage else 0
        return LLMResponse(
            content=output_text,
            tokens_used=tokens_used,
            model=self.model,
        )

    @staticmethod
    def _to_response_input(messages: list[dict[str, str]]) -> list[dict[str, str]]:
        response_messages: list[dict[str, str]] = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if role == "tool":
                response_messages.append({"role": "user", "content": f"Tool output:\n{content}"})
            elif role in {"user", "assistant", "system", "developer"}:
                response_messages.append({"role": role, "content": content})
            else:
                response_messages.append({"role": "user", "content": content})
        return response_messages


class LLMRouter:
    def __init__(
        self,
        backend: BaseLLMBackend | None = None,
        backends: list[BaseLLMBackend] | None = None,
    ) -> None:
        if backend and backends:
            raise ValueError("Pass either backend or backends, not both.")
        self._backends = backends or [backend or MockLLMBackend()]

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        last_error: Exception | None = None
        for backend in self._backends:
            try:
                return await backend.chat(messages, tools)
            except LLMBackendError as exc:
                last_error = exc
                continue
        raise LLMBackendError(f"No LLM backend completed successfully: {last_error}")


def build_llm_router(
    *,
    llm_backend: str,
    fallback_order: str,
    openai_api_key: str | None,
    openai_model: str,
    deepseek_api_key: str | None,
    deepseek_model: str,
    deepseek_base_url: str,
) -> LLMRouter:
    """Build provider router from settings.

    The explicit `llm_backend` selects a single backend unless it is `auto`. `auto`
    follows `fallback_order` and skips providers without credentials.
    """

    requested = [llm_backend] if llm_backend != "auto" else [
        item.strip() for item in fallback_order.split(",") if item.strip()
    ]

    backends: list[BaseLLMBackend] = []
    for name in requested:
        if name == "openai" and openai_api_key:
            backends.append(OpenAIBackend(openai_api_key, openai_model, name="openai"))
        elif name == "deepseek" and deepseek_api_key:
            backends.append(
                OpenAIBackend(
                    deepseek_api_key,
                    deepseek_model,
                    base_url=deepseek_base_url,
                    name="deepseek",
                )
            )
        elif name == "mock":
            backends.append(MockLLMBackend())

    if not backends:
        backends.append(MockLLMBackend())
    return LLMRouter(backends=backends)




