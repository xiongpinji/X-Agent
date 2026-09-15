from types import SimpleNamespace

import pytest

from backend.app.core.llm import (
    BaseLLMBackend,
    LLMBackendError,
    LLMResponse,
    MockLLMBackend,
    build_llm_router,
)


class FailingBackend(BaseLLMBackend):
    name = "failing"

    async def chat(self, messages, tools, *, response_format=None):
        raise LLMBackendError("boom")


class StaticBackend(BaseLLMBackend):
    name = "static"

    async def chat(self, messages, tools, *, response_format=None):
        return LLMResponse(content="static-ok", model="static")


async def test_router_falls_back_after_provider_error() -> None:
    router = build_llm_router(
        llm_backend="mock",
        fallback_order="openai,deepseek,mock",
        openai_api_key=None,
        openai_model="gpt-5.2",
        deepseek_api_key=None,
        deepseek_model="deepseek-chat",
        deepseek_base_url="https://api.deepseek.com/v1",
    )

    response = await router.chat([{"role": "user", "content": "hello"}], [])

    assert response.model == "mock"
    assert "X-Agent Phase 0 mock response" in response.content


async def test_router_tries_backends_in_order() -> None:
    from backend.app.core.llm import LLMRouter

    router = LLMRouter(backends=[FailingBackend(), StaticBackend()])

    response = await router.chat([{"role": "user", "content": "hello"}], [])

    assert response.content == "static-ok"


async def test_router_raises_when_all_backends_fail() -> None:
    from backend.app.core.llm import LLMRouter

    router = LLMRouter(backends=[FailingBackend()])

    with pytest.raises(LLMBackendError):
        await router.chat([{"role": "user", "content": "hello"}], [])


def test_auto_router_without_keys_keeps_mock_available() -> None:
    router = build_llm_router(
        llm_backend="auto",
        fallback_order="openai,deepseek,mock",
        openai_api_key=None,
        openai_model="gpt-5.2",
        deepseek_api_key=None,
        deepseek_model="deepseek-chat",
        deepseek_base_url="https://api.deepseek.com/v1",
    )

    assert isinstance(router._backends[-1], MockLLMBackend)


def _auto_kwargs() -> dict:
    """Default `auto` routing (openai,deepseek,anthropic,ollama) with no credentials."""
    return dict(
        llm_backend="auto",
        fallback_order="openai,deepseek,anthropic,ollama",
        openai_api_key=None,
        openai_model="gpt-5.2",
        deepseek_api_key=None,
        deepseek_model="deepseek-chat",
        deepseek_base_url="https://api.deepseek.com/v1",
    )


def test_auto_router_without_keys_degrades_to_mock_in_development(monkeypatch) -> None:
    """P0-2: dev/test 无任何凭据时必须追加 mock 兜底，保证零配置能跑出结果。"""
    import backend.app.settings as settings_mod

    monkeypatch.setattr(
        settings_mod, "get_settings", lambda: SimpleNamespace(app_mode="development")
    )

    router = build_llm_router(**_auto_kwargs())

    assert isinstance(router._backends[-1], MockLLMBackend)


def test_auto_router_without_keys_raises_in_production(monkeypatch) -> None:
    """P0-2: production 无凭据必须 fail-fast，绝不静默降级到 mock。"""
    import backend.app.settings as settings_mod

    monkeypatch.setattr(
        settings_mod, "get_settings", lambda: SimpleNamespace(app_mode="production")
    )

    with pytest.raises(RuntimeError, match="No LLM API key configured"):
        build_llm_router(**_auto_kwargs())

