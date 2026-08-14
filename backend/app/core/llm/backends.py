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
import contextlib
import logging
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# OpenAI SDK is an optional dependency; import gracefully.
try:
    from openai import APIError as _OpenAIAPIError
except ImportError:  # pragma: no cover
    _OpenAIAPIError = None  # type: ignore[assignment,misc]


def _normalize_tool_parameters(parameters: Any) -> dict[str, Any]:
    """Coerce a tool's JSON-Schema parameters into a valid object schema.

    Strict providers (DeepSeek/OpenAI function calling) reject a function whose
    `parameters` is null or lacks `type: "object"` with:
        "schema must be a JSON Schema of 'type: object', got 'type: null'".
    A tool that takes no arguments must still send an empty object schema, not
    null. This normalizes None / missing-type / non-dict into a safe shape.
    """
    if not isinstance(parameters, dict) or not parameters:
        return {"type": "object", "properties": {}}
    # If a schema was provided but omits/!= object type, force object and keep
    # any declared properties.
    if parameters.get("type") != "object":
        normalized = dict(parameters)
        normalized["type"] = "object"
        normalized.setdefault("properties", {})
        return normalized
    parameters.setdefault("properties", {})
    return parameters


def _to_openai_tool(tool: dict[str, Any]) -> dict[str, Any]:
    """Convert a tool definition into OpenAI function-calling shape.

    definitions_for_llm() already emits {"type":"function","function":{...}};
    pass those through (normalizing the nested parameters). Only bare
    {name, description, parameters} dicts get wrapped. This fixes the bug where
    every tool came through as name=null -> "Tool names must be unique".
    """
    if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
        fn = dict(tool["function"])
        fn["parameters"] = _normalize_tool_parameters(fn.get("parameters"))
        # strip non-standard x- keys the provider may reject
        fn = {k: v for k, v in fn.items() if not k.startswith("x-")}
        return {"type": "function", "function": fn}
    return {
        "type": "function",
        "function": {
            "name": tool.get("name", "unknown"),
            "description": tool.get("description", ""),
            "parameters": _normalize_tool_parameters(tool.get("parameters")),
        },
    }


def _parse_tool_arguments(raw: Any) -> dict[str, Any]:
    """Parse a tool call's arguments into a dict.

    OpenAI/DeepSeek return function-call arguments as a JSON STRING. The agent
    loop expects a dict (it does `args["path"]` etc.), so an unparsed string
    surfaced as "Missing required argument: path". Handle string/None/dict.
    """
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    if isinstance(raw, str):
        import json as _json
        try:
            parsed = _json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            return {}
    return {}


@dataclass
class LLMResponse:
    content: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tokens_used: int = 0
    model: str = "mock"
    cost: float = 0.0
    latency_ms: float = 0.0


# Historical built-in pricing, used only when config/model_profiles.yaml is
# absent (explicit degrade, logged once by the profiles loader).
_BUILTIN_PRICING: dict[str, dict[str, float]] = {
    "gpt-4": {"prompt": 0.03, "completion": 0.06},
    "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
    "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
    "gpt-4o": {"prompt": 0.005, "completion": 0.015},
}

_PRICING_TABLE_CACHE: dict[str, dict[str, float]] | None = None


def get_pricing_table() -> dict[str, dict[str, float]]:
    """Return the model pricing table (USD per 1K tokens).

    Source of truth is ``config/model_profiles.yaml`` (P1-08 externalization).
    If the file is missing or malformed, the historical built-in table is used
    — a missing file logs a warning via the profiles loader; a malformed file
    would raise ModelProfileLoadError at load time, so here we explicitly
    degrade to the built-in table and log the reason.
    """
    global _PRICING_TABLE_CACHE
    if _PRICING_TABLE_CACHE is not None:
        return _PRICING_TABLE_CACHE
    try:
        from backend.app.core.llm.profiles import (
            load_model_profiles,
            pricing_table_from_profiles,
        )

        config = load_model_profiles()
        table = pricing_table_from_profiles(config)
        if table:
            _PRICING_TABLE_CACHE = table
            return _PRICING_TABLE_CACHE
    except Exception as exc:
        logger.warning(
            "Falling back to built-in LLM pricing table: %s", exc
        )
    _PRICING_TABLE_CACHE = dict(_BUILTIN_PRICING)
    return _PRICING_TABLE_CACHE


def reset_pricing_table_cache() -> None:
    """Clear the cached pricing table (tests / profile hot-reload)."""
    global _PRICING_TABLE_CACHE
    _PRICING_TABLE_CACHE = None


@dataclass
class TokenUsage:
    """Token usage tracking for cost calculation."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def calculate_cost(self, model: str) -> float:
        """Calculate cost based on model pricing (config/model_profiles.yaml)."""
        pricing = get_pricing_table()
        rates = pricing.get(model, {"prompt": 0.0, "completion": 0.0})
        return (self.prompt_tokens * rates["prompt"] +
                self.completion_tokens * rates["completion"]) / 1000
class BaseLLMBackend:
    name = "base"

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        *,
        response_format: dict[str, Any] | None = None,
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
        *,
        response_format: dict[str, Any] | None = None,
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
    """Full-featured OpenAI API backend with streaming, retries, rate limiting, and cost tracking.
    
    Uses a persistent AsyncOpenAI client with connection pooling for efficiency.
    """

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
        max_connections: int = 100,
    ) -> None:
        self.name = name
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.rate_limit_rpm = rate_limit_rpm
        self.timeout = timeout
        self.max_connections = max_connections
        self._request_times: list[float] = []
        self._lock = asyncio.Lock()
        self._client: Any = None  # Persistent client with connection pool
        self._client_lock = asyncio.Lock()

    async def _get_client(self) -> Any:
        """Get or create the persistent AsyncOpenAI client with connection pooling."""
        if self._client is None:
            async with self._client_lock:
                if self._client is None:
                    try:
                        import httpx
                        from openai import AsyncOpenAI
                        
                        # Create HTTP client with connection pooling
                        http_client = httpx.AsyncClient(
                            limits=httpx.Limits(
                                max_connections=self.max_connections,
                                max_keepalive_connections=20,
                                keepalive_expiry=30,
                            ),
                            timeout=httpx.Timeout(self.timeout, connect=10.0),
                        )
                        
                        client_kwargs: dict[str, Any] = {
                            "api_key": self.api_key,
                            "http_client": http_client,
                            "max_retries": 0,  # We handle retries ourselves
                        }
                        if self.base_url:
                            client_kwargs["base_url"] = self.base_url
                        
                        self._client = AsyncOpenAI(**client_kwargs)
                        logger.info(f"OpenAI client initialized with connection pool (max_connections={self.max_connections})")
                    except ImportError as exc:
                        raise LLMBackendError("openai package is not installed") from exc
        return self._client

    async def close(self) -> None:
        """Close the persistent client and release connections."""
        if self._client:
            with contextlib.suppress(Exception):
                await self._client.close()
            self._client = None

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
        coro_factory,
        attempt: int = 0,
    ) -> Any:
        """Retry with exponential backoff.

        `coro_factory` MUST be a zero-arg callable returning a FRESH awaitable
        on every call. A coroutine object can only be awaited once, so retries
        must rebuild it (previously this reused an exhausted coroutine and every
        retry failed with 'cannot reuse already awaited coroutine').
        """
        try:
            await self._check_rate_limit()
            return await asyncio.wait_for(coro_factory(), timeout=self.timeout)
        except (TimeoutError, Exception) as exc:
            if attempt < self.max_retries:
                delay = self.retry_delay * (2 ** attempt)
                logger.warning(
                    f"Attempt {attempt + 1} failed: {exc}. Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
                return await self._retry_with_backoff(coro_factory, attempt + 1)
            raise LLMBackendError(f"{self.name} failed after {self.max_retries} retries: {exc}") from exc
    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        *,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Send a chat request to OpenAI API using persistent connection pool."""
        client = await self._get_client()
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
                    _to_openai_tool(tool) for tool in tools
                ]

            # Codex-style structured output enforcement
            if response_format:
                request_kwargs["response_format"] = response_format

            # Make request with retry logic
            response = await self._retry_with_backoff(
                lambda: client.chat.completions.create(**request_kwargs)
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
                            "arguments": _parse_tool_arguments(
                                tc.function.arguments
                            ),
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

        except Exception as exc:
            if _OpenAIAPIError is not None and isinstance(exc, _OpenAIAPIError):
                raise LLMBackendError(f"{self.name} API error: {exc}") from exc
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
                lambda: client.chat.completions.create(**request_kwargs)
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
            from openai import AsyncOpenAI
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
        except Exception as exc:
            if _OpenAIAPIError is not None and isinstance(exc, _OpenAIAPIError):
                raise LLMBackendError(f"{self.name} API error: {exc}") from exc
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
    """Sequential-fallback router — the production shell for all LLM calls.

    Optional quota enforcement: when a ``quota_manager`` (see llm/quota.py) is
    attached, every chat checks tenant/user token quotas BEFORE any provider
    call (raising ``QuotaExceededError``) and accumulates actual usage after a
    successful call. QuotaExceededError is a RuntimeError, not an
    LLMBackendError, so it is never swallowed by the provider fallback loop.
    """

    def __init__(
        self,
        backend: BaseLLMBackend | None = None,
        backends: list[BaseLLMBackend] | None = None,
        *,
        quota_manager: Any | None = None,
    ) -> None:
        if backend and backends:
            raise ValueError("Pass either backend or backends, not both.")
        self._backends = backends or [backend or MockLLMBackend()]
        self._quota_manager = quota_manager

    @property
    def quota_manager(self) -> Any | None:
        return self._quota_manager

    def _order_backends(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        *,
        task_type: Any = None,
        strategy: Any = None,
    ) -> list[BaseLLMBackend]:
        """Return the backend try-order for this request (sequential default).

        SmartLLMRouter overrides this hook to reorder by task/cost/latency.
        """
        return list(self._backends)

    def _on_backend_success(self, backend: BaseLLMBackend, response: LLMResponse) -> None:
        """Hook invoked after a backend completes successfully (observability)."""

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        *,
        tenant_id: str | None = None,
        user_id: str | None = None,
        task_type: Any = None,
        strategy: Any = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        if self._quota_manager is not None:
            await self._quota_manager.check_quota(tenant_id, user_id)

        # ─── MoA 路径: 多模型并行推理 + 聚合 ────────────────────────────────
        try:
            from backend.app.settings import get_settings
            _s = get_settings()
            if _s.moa_enabled and len(self._backends) >= 2:
                from backend.app.core.llm.moa import MoAConfig, MoAEngine
                moa_engine = MoAEngine(backends=list(self._backends))
                moa_cfg = MoAConfig(
                    enabled=True,
                    strategy=_s.moa_strategy,
                    timeout_per_model=_s.moa_timeout,
                    min_responses=_s.moa_min_responses,
                )
                response = await moa_engine.generate(messages, tools, moa_cfg)
                if self._quota_manager is not None:
                    await self._quota_manager.record_usage(
                        tenant_id, user_id, response.tokens_used, response.cost
                    )
                return response
        except ImportError:
            pass  # MoA 模块不可用时降级到顺序路由
        except Exception as moa_exc:
            logger.warning("MoA path failed, falling back to sequential: %s", moa_exc)

        last_error: Exception | None = None
        for backend in self._order_backends(
            messages, tools, task_type=task_type, strategy=strategy
        ):
            try:
                response = await backend.chat(messages, tools, response_format=response_format)
            except LLMBackendError as exc:
                last_error = exc
                continue
            if self._quota_manager is not None:
                await self._quota_manager.record_usage(
                    tenant_id, user_id, response.tokens_used, response.cost
                )
            self._on_backend_success(backend, response)
            # P1-04: Prometheus metrics — record LLM call
            try:
                from backend.app.core.metrics import metrics_collector
                metrics_collector.record_llm_call(
                    model=response.model,
                    status="success",
                    duration_seconds=response.latency_ms / 1000 if response.latency_ms else 0,
                    input_tokens=response.tokens_used.get("input", 0) if isinstance(response.tokens_used, dict) else 0,
                    output_tokens=response.tokens_used.get("output", 0) if isinstance(response.tokens_used, dict) else 0,
                )
            except Exception:
                pass  # Metrics must never break LLM calls
            # P2-06: OTel metrics — record LLM call
            try:
                from backend.app.core.otel_exporter import get_otel_exporter
                _exporter = get_otel_exporter()
                if _exporter.is_active:
                    _exporter.record_llm_call(
                        model=response.model,
                        tokens_used=response.tokens_used,
                        latency_ms=response.latency_ms,
                        tenant_id=tenant_id or "",
                    )
            except Exception:
                pass  # OTel must never break LLM calls
            return response
        raise LLMBackendError(f"No LLM backend completed successfully: {last_error}")


def build_llm_router(
    *,
    llm_backend: str,
    fallback_order: str,
    openai_api_key: str | None,
    openai_model: str,
    openai_base_url: str | None = None,
    deepseek_api_key: str | None = None,
    deepseek_model: str,
    deepseek_base_url: str,
    anthropic_api_key: str | None = None,
    anthropic_model: str | None = None,
    anthropic_base_url: str | None = None,
    ollama_base_url: str | None = None,
    ollama_model: str | None = None,
    routing_mode: str | None = None,
    smart_strategy: str | None = None,
    model_profiles_path: str | None = None,
    quota_manager: Any | None = None,
    quota_enabled: bool | None = None,
    selector: Any | None = None,
) -> LLMRouter:
    """Build provider router from settings — the single construction entry point.

    The explicit `llm_backend` selects a single backend unless it is `auto`.
    `auto` follows `fallback_order` and skips providers without credentials.

    P1-08 convergence:
    - provider names now also include ``anthropic`` (needs an API key) and
      ``ollama`` (local server, no key required);
    - ``routing_mode="smart"`` wraps the same sequential shell in a
      SmartLLMRouter that reorders backends per request via ModelSelector,
      with model profiles loaded from config/model_profiles.yaml;
    - when quotas are enabled (``quota_enabled`` or XAGENT_LLM_QUOTA_ENABLED),
      a TokenQuotaManager backed by the existing cache abstraction is
      attached. Any parameter left as None falls back to the XAGENT_*
      environment sub-settings in llm/llm_settings.py.
    """
    from backend.app.core.llm.llm_settings import get_llm_feature_settings

    features = get_llm_feature_settings()

    anthropic_api_key = anthropic_api_key if anthropic_api_key is not None else features.anthropic_api_key
    anthropic_model = anthropic_model or features.anthropic_model
    anthropic_base_url = anthropic_base_url if anthropic_base_url is not None else features.anthropic_base_url
    ollama_base_url = ollama_base_url or features.ollama_base_url
    ollama_model = ollama_model or features.ollama_model

    requested = [llm_backend] if llm_backend != "auto" else [
        item.strip() for item in fallback_order.split(",") if item.strip()
    ]

    backends: list[BaseLLMBackend] = []
    for name in requested:
        if name == "openai" and openai_api_key:
            backends.append(
                OpenAIBackend(
                    openai_api_key,
                    openai_model,
                    base_url=openai_base_url,
                    name="openai",
                )
            )
        elif name == "deepseek" and deepseek_api_key:
            backends.append(
                OpenAIBackend(
                    deepseek_api_key,
                    deepseek_model,
                    base_url=deepseek_base_url,
                    name="deepseek",
                )
            )
        elif name == "anthropic" and anthropic_api_key:
            from backend.app.core.llm.anthropic_backend import AnthropicBackend

            backends.append(
                AnthropicBackend(
                    anthropic_api_key,
                    anthropic_model,
                    base_url=anthropic_base_url,
                    name="anthropic",
                )
            )
        elif name == "ollama":
            from backend.app.core.llm.ollama_backend import OllamaBackend

            backends.append(
                OllamaBackend(ollama_model, base_url=ollama_base_url, name="ollama")
            )
        elif name == "mock":
            backends.append(MockLLMBackend())

    if not backends:
        if llm_backend == "mock" or "mock" in requested:
            backends.append(MockLLMBackend())
        else:
            raise RuntimeError(
                "No LLM API key configured. Set XAGENT_OPENAI_API_KEY or "
                "XAGENT_DEEPSEEK_API_KEY or XAGENT_ANTHROPIC_API_KEY. "
                "Use XAGENT_LLM_BACKEND=mock for testing."
            )

    # --- Quota wiring (token-metered, stored in the existing cache layer) ---
    if quota_manager is None:
        effective_quota_enabled = (
            quota_enabled if quota_enabled is not None else features.llm_quota_enabled
        )
        if effective_quota_enabled:
            from backend.app.core.llm.profiles import load_model_profiles
            from backend.app.core.llm.quota import build_quota_manager_from_config

            profile_config = load_model_profiles(
                model_profiles_path or features.llm_model_profiles_path
            )
            quota_manager = build_quota_manager_from_config(
                enabled=True,
                period=features.llm_quota_period,
                default_tenant_tokens=features.llm_quota_default_tenant_tokens,
                default_user_tokens=features.llm_quota_default_user_tokens,
                tenant_overrides=profile_config.quota.tenant_overrides,
                user_overrides=profile_config.quota.user_overrides,
            )

    # --- Routing mode ---
    mode = (routing_mode or features.llm_routing_mode or "sequential").strip().lower()
    if mode == "sequential":
        return LLMRouter(backends=backends, quota_manager=quota_manager)
    if mode == "smart":
        from backend.app.core.llm.profiles import build_selector, load_model_profiles
        from backend.app.core.llm.smart_router import SmartLLMRouter

        if selector is None:
            profile_config = load_model_profiles(
                model_profiles_path or features.llm_model_profiles_path
            )
            selector = build_selector(profile_config)
        return SmartLLMRouter(
            backends=backends,
            selector=selector,
            strategy=smart_strategy or features.llm_smart_strategy,
            quota_manager=quota_manager,
        )
    raise ValueError(
        f"unknown llm routing mode '{mode}'; valid: 'sequential', 'smart'"
    )




