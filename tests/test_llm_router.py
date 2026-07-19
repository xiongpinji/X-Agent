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

    async def chat(self, messages, tools):
        raise LLMBackendError("boom")


class StaticBackend(BaseLLMBackend):
    name = "static"

    async def chat(self, messages, tools):
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

