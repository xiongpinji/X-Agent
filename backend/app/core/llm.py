from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMResponse:
    content: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tokens_used: int = 0
    model: str = "mock"


class BaseLLMBackend:
    name = "base"

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
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


class OpenAIResponsesBackend(BaseLLMBackend):
    """OpenAI Responses API backend.

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
            backends.append(OpenAIResponsesBackend(openai_api_key, openai_model, name="openai"))
        elif name == "deepseek" and deepseek_api_key:
            backends.append(
                OpenAIResponsesBackend(
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
