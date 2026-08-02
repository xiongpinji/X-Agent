"""Offline tests for P1-08 LLM routing convergence.

Covers:
- externalized model profiles (config/model_profiles.yaml) loading & errors
- pricing table externalization (TokenUsage.calculate_cost)
- Anthropic / Ollama backends via httpx.MockTransport (fully offline)
- build_llm_router wiring for anthropic / ollama / smart mode / quotas
- SmartLLMRouter ordering + explicit degrade paths
- TokenQuotaManager enforcement (token-metered, cache-backed)
"""

from __future__ import annotations

import json

import httpx
import pytest

from backend.app.core.cache import CacheManager
from backend.app.core.llm import (
    AnthropicBackend,
    BaseLLMBackend,
    LLMBackendError,
    LLMResponse,
    LLMRouter,
    MockLLMBackend,
    OllamaBackend,
    QuotaExceededError,
    SmartLLMRouter,
    TokenQuotaManager,
    TokenUsage,
    build_llm_router,
    load_model_profiles,
)
from backend.app.core.llm.backends import (
    get_pricing_table,
    reset_pricing_table_cache,
)
from backend.app.core.llm.profiles import (
    ModelProfileLoadError,
    build_selector,
)
from backend.app.core.llm.selector import ModelSelector, SelectionStrategy

MESSAGES = [{"role": "user", "content": "hello"}]


def _router_kwargs(**overrides):
    base = dict(
        llm_backend="auto",
        fallback_order="openai,deepseek,mock",
        openai_api_key=None,
        openai_model="gpt-4o-mini",
        deepseek_api_key=None,
        deepseek_model="deepseek-chat",
        deepseek_base_url="https://api.deepseek.com/v1",
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Model profiles externalization
# ---------------------------------------------------------------------------


class TestModelProfiles:
    def test_shipped_yaml_loads(self):
        config = load_model_profiles()
        assert not config.used_builtin_fallback
        names = {m.name for m in config.models}
        assert {"gpt-4o", "gpt-4o-mini", "deepseek-chat", "llama3.1"} <= names
        assert any(m.provider == "anthropic" for m in config.models)
        assert any(m.provider == "ollama" for m in config.models)

    def test_missing_file_is_explicit_fallback(self, tmp_path):
        config = load_model_profiles(tmp_path / "does-not-exist.yaml")
        assert config.used_builtin_fallback
        assert config.models == []
        selector = build_selector(config)
        # built-in catalog retained
        assert "gpt-4o" in selector.models

    def test_malformed_yaml_raises(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("models: [unclosed", encoding="utf-8")
        with pytest.raises(ModelProfileLoadError):
            load_model_profiles(bad)

    def test_missing_required_field_raises(self, tmp_path):
        bad = tmp_path / "incomplete.yaml"
        bad.write_text(
            "models:\n  - name: x\n    provider: openai\n",
            encoding="utf-8",
        )
        with pytest.raises(ModelProfileLoadError, match="missing required fields"):
            load_model_profiles(bad)

    def test_unknown_task_type_raises(self, tmp_path):
        bad = tmp_path / "badtask.yaml"
        bad.write_text(
            """
models:
  - name: x
    provider: openai
    cost_per_1k_input: 0.1
    cost_per_1k_output: 0.2
    latency_ms: 100
    quality_score: 50
    max_tokens: 1000
    supported_tasks: [not_a_task]
""",
            encoding="utf-8",
        )
        with pytest.raises(ModelProfileLoadError, match="supported_task"):
            load_model_profiles(bad)

    def test_selector_uses_external_profiles(self):
        config = load_model_profiles()
        selector = build_selector(config)
        assert "claude-3-5-haiku-20241022" in selector.models
        assert "llama3.1" in selector.models

    def test_pricing_table_externalized(self):
        reset_pricing_table_cache()
        try:
            table = get_pricing_table()
            # legacy rates preserved
            assert table["gpt-4"] == {"prompt": 0.03, "completion": 0.06}
            # anthropic profile now priced from YAML
            assert table["claude-3-5-haiku-20241022"]["prompt"] == 0.0008
            usage = TokenUsage(prompt_tokens=1000, completion_tokens=1000, total_tokens=2000)
            assert usage.calculate_cost("gpt-4") == pytest.approx(0.09)
            assert usage.calculate_cost("claude-3-5-haiku-20241022") == pytest.approx(0.0048)
        finally:
            reset_pricing_table_cache()


# ---------------------------------------------------------------------------
# Anthropic backend (MockTransport, offline)
# ---------------------------------------------------------------------------


def _anthropic_payload(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content.decode())
    # system must be a top-level param, not a message
    assert body["system"] == "you are concise"
    assert all(m["role"] != "system" for m in body["messages"])
    # tools converted to anthropic shape with input_schema
    assert body["tools"][0]["input_schema"]["type"] == "object"
    return httpx.Response(
        200,
        json={
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": body["model"],
            "content": [
                {"type": "text", "text": "Hi from Claude"},
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "echo",
                    "input": {"text": "hi"},
                },
            ],
            "stop_reason": "tool_use",
            "stop_sequence": None,
            "usage": {"input_tokens": 12, "output_tokens": 7},
        },
    )


class TestAnthropicBackend:
    async def test_chat_via_mock_transport(self):
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(_anthropic_payload),
            base_url="https://api.anthropic.com",
        )
        backend = AnthropicBackend(
            "test-key",
            "claude-3-5-haiku-20241022",
            http_client=client,
        )
        messages = [
            {"role": "system", "content": "you are concise"},
            {"role": "user", "content": "hello"},
        ]
        tools = [{"name": "echo", "description": "echo back", "parameters": None}]
        response = await backend.chat(messages, tools)

        assert response.content == "Hi from Claude"
        assert response.tool_calls == [{"name": "echo", "arguments": {"text": "hi"}}]
        assert response.tokens_used == 19
        assert response.model == "claude-3-5-haiku-20241022"
        assert response.cost == pytest.approx((12 * 0.0008 + 7 * 0.004) / 1000)

    async def test_http_error_becomes_backend_error(self):
        def fail(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": {"message": "bad key"}})

        client = httpx.AsyncClient(
            transport=httpx.MockTransport(fail),
            base_url="https://api.anthropic.com",
        )
        backend = AnthropicBackend("bad-key", "claude-3-5-haiku-20241022", http_client=client)
        with pytest.raises(LLMBackendError):
            await backend.chat(MESSAGES, [])


# ---------------------------------------------------------------------------
# Ollama backend (MockTransport, offline)
# ---------------------------------------------------------------------------


def _ollama_payload(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content.decode())
    assert request.url.path == "/api/chat"
    assert body["stream"] is False
    return httpx.Response(
        200,
        json={
            "model": body["model"],
            "message": {
                "role": "assistant",
                "content": "local says hi",
                "tool_calls": [
                    {"function": {"name": "echo", "arguments": {"text": "yo"}}}
                ],
            },
            "done": True,
            "prompt_eval_count": 9,
            "eval_count": 4,
        },
    )


class TestOllamaBackend:
    async def test_chat_via_mock_transport(self):
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(_ollama_payload),
            base_url="http://localhost:11434",
        )
        backend = OllamaBackend("llama3.1", http_client=client)
        response = await backend.chat(
            MESSAGES,
            [{"name": "echo", "description": "echo", "parameters": {}}],
        )
        assert response.content == "local says hi"
        assert response.tool_calls == [{"name": "echo", "arguments": {"text": "yo"}}]
        assert response.tokens_used == 13
        assert response.cost == 0.0  # local model, zero API cost

    async def test_connection_error_becomes_backend_error(self):
        def refuse(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        client = httpx.AsyncClient(
            transport=httpx.MockTransport(refuse),
            base_url="http://localhost:11434",
        )
        backend = OllamaBackend("llama3.1", http_client=client)
        with pytest.raises(LLMBackendError, match="ollama"):
            await backend.chat(MESSAGES, [])

    async def test_non_json_response_raises(self):
        def garbage(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="not json")

        client = httpx.AsyncClient(
            transport=httpx.MockTransport(garbage),
            base_url="http://localhost:11434",
        )
        backend = OllamaBackend("llama3.1", http_client=client)
        with pytest.raises(LLMBackendError, match="non-JSON"):
            await backend.chat(MESSAGES, [])


# ---------------------------------------------------------------------------
# build_llm_router wiring
# ---------------------------------------------------------------------------


class TestBuildRouterConvergence:
    def test_anthropic_in_fallback_order_with_key(self):
        router = build_llm_router(
            **_router_kwargs(
                fallback_order="anthropic,mock",
                anthropic_api_key="ak-test",
                anthropic_model="claude-3-5-haiku-20241022",
            )
        )
        assert isinstance(router._backends[0], AnthropicBackend)
        assert isinstance(router._backends[1], MockLLMBackend)

    def test_anthropic_skipped_without_key(self):
        router = build_llm_router(
            **_router_kwargs(fallback_order="anthropic,mock", anthropic_api_key=None)
        )
        assert len(router._backends) == 1
        assert isinstance(router._backends[0], MockLLMBackend)

    def test_ollama_in_fallback_order_needs_no_key(self):
        router = build_llm_router(
            **_router_kwargs(
                fallback_order="ollama,mock",
                ollama_model="llama3.1",
                ollama_base_url="http://localhost:11434",
            )
        )
        assert isinstance(router._backends[0], OllamaBackend)
        assert router._backends[0].model == "llama3.1"

    def test_unknown_routing_mode_raises(self):
        with pytest.raises(ValueError, match="routing mode"):
            build_llm_router(**_router_kwargs(routing_mode="telepathic"))

    def test_smart_mode_returns_smart_router(self):
        router = build_llm_router(**_router_kwargs(routing_mode="smart"))
        assert isinstance(router, SmartLLMRouter)
        # externalized catalog loaded into the selector
        assert "llama3.1" in router.selector.models

    def test_quota_enabled_attaches_manager(self):
        router = build_llm_router(
            **_router_kwargs(
                quota_enabled=True,
                quota_manager=TokenQuotaManager(
                    cache_manager=CacheManager(), enabled=True
                ),
            )
        )
        assert router.quota_manager is not None

    def test_default_sequential_behavior_unchanged(self):
        router = build_llm_router(**_router_kwargs())
        assert type(router) is LLMRouter
        assert router.quota_manager is None


# ---------------------------------------------------------------------------
# Smart routing
# ---------------------------------------------------------------------------


class _StubBackend(BaseLLMBackend):
    def __init__(self, model: str, provider: str, fail: bool = False) -> None:
        self.model = model
        self.name = provider
        self.fail = fail
        self.calls = 0

    async def chat(self, messages, tools, *, response_format=None):
        self.calls += 1
        if self.fail:
            raise LLMBackendError(f"{self.name} down")
        return LLMResponse(
            content=f"ok:{self.model}",
            model=self.model,
            tokens_used=5,
            latency_ms=10.0,
        )


class TestSmartRouter:
    def _selector(self) -> ModelSelector:
        return build_selector(load_model_profiles())

    async def test_cost_optimized_picks_cheapest_first(self):
        expensive = _StubBackend("gpt-4", "openai")
        cheap = _StubBackend("gpt-4o-mini", "openai-mini")
        router = SmartLLMRouter(
            backends=[expensive, cheap],
            selector=self._selector(),
            strategy=SelectionStrategy.COST_OPTIMIZED,
        )
        response = await router.chat(
            [{"role": "user", "content": "translate this for me"}], []
        )
        assert response.model == "gpt-4o-mini"
        assert cheap.calls == 1
        assert expensive.calls == 0

    async def test_fallback_still_sequential_after_smart_ordering(self):
        failing = _StubBackend("gpt-4o-mini", "openai-mini", fail=True)
        backup = _StubBackend("gpt-4", "openai")
        router = SmartLLMRouter(
            backends=[backup, failing],
            selector=self._selector(),
            strategy=SelectionStrategy.COST_OPTIMIZED,
        )
        response = await router.chat(MESSAGES, [])
        assert response.model == "gpt-4"
        assert failing.calls == 1  # smart order tried the cheap one first

    async def test_explicit_task_type_overrides_heuristic(self):
        coder = _StubBackend("deepseek-coder", "deepseek")
        cheap = _StubBackend("gpt-4o-mini", "openai-mini")
        router = SmartLLMRouter(
            backends=[cheap, coder],
            selector=self._selector(),
            strategy=SelectionStrategy.PERFORMANCE_OPTIMIZED,
        )
        response = await router.chat(MESSAGES, [], task_type="code_generation")
        assert response.model == "deepseek-coder"

    async def test_unknown_task_type_raises_explicitly(self):
        router = SmartLLMRouter(
            backends=[_StubBackend("gpt-4o-mini", "openai-mini")],
            selector=self._selector(),
        )
        with pytest.raises(ValueError, match="task_type"):
            await router.chat(MESSAGES, [], task_type="mind_reading")

    async def test_selected_model_without_backend_degrades_to_configured_order(self):
        # Selector catalog has no model matching this backend -> configured order.
        alien = _StubBackend("alien-model", "alien")
        router = SmartLLMRouter(
            backends=[alien],
            selector=self._selector(),
            strategy=SelectionStrategy.COST_OPTIMIZED,
        )
        response = await router.chat(MESSAGES, [])
        assert response.model == "alien-model"
        assert alien.calls == 1

    async def test_success_feeds_back_into_selector_history(self):
        backend = _StubBackend("gpt-4o-mini", "openai-mini")
        selector = self._selector()
        router = SmartLLMRouter(backends=[backend], selector=selector)
        await router.chat(MESSAGES, [])
        history = selector._performance_history.get("gpt-4o-mini")
        assert history and history[-1]["success"] is True


# ---------------------------------------------------------------------------
# Quota enforcement
# ---------------------------------------------------------------------------


class _CountingBackend(BaseLLMBackend):
    name = "counting"

    def __init__(self, tokens: int = 10) -> None:
        self.calls = 0
        self._tokens = tokens

    async def chat(self, messages, tools, *, response_format=None):
        self.calls += 1
        return LLMResponse(content="ok", model="counting", tokens_used=self._tokens, cost=0.001)


class TestQuotaEnforcement:
    def _manager(self, **kwargs) -> TokenQuotaManager:
        params = dict(
            cache_manager=CacheManager(),
            enabled=True,
            period="day",
            default_tenant_tokens=1000,
            default_user_tokens=25,
        )
        params.update(kwargs)
        return TokenQuotaManager(**params)

    async def test_usage_accumulates_per_user(self):
        manager = self._manager()
        router = LLMRouter(backend=_CountingBackend(tokens=10), quota_manager=manager)
        await router.chat(MESSAGES, [], tenant_id="t1", user_id="u1")
        await router.chat(MESSAGES, [], tenant_id="t1", user_id="u1")
        status = await manager.get_status("t1", "u1")
        assert status["user"]["used_tokens"] == 20
        assert status["tenant"]["used_tokens"] == 20
        assert status["user"]["cost_usd"] == pytest.approx(0.002)

    async def test_over_quota_rejects_before_provider_call(self):
        # Post-metered semantics: a bucket at used >= limit is exhausted and
        # the NEXT request is rejected before reaching any provider.
        manager = self._manager(default_user_tokens=10)
        backend = _CountingBackend(tokens=10)
        router = LLMRouter(backend=backend, quota_manager=manager)

        await router.chat(MESSAGES, [], tenant_id="t1", user_id="u1")  # 10 tokens
        with pytest.raises(QuotaExceededError) as exc_info:
            await router.chat(MESSAGES, [], tenant_id="t1", user_id="u1")

        message = str(exc_info.value)
        assert "u1" in message and "10/10" in message and "day" in message
        assert backend.calls == 1  # second call never reached the provider

    async def test_tenant_quota_enforced_independently(self):
        manager = self._manager(default_tenant_tokens=10, default_user_tokens=1000)
        router = LLMRouter(backend=_CountingBackend(tokens=10), quota_manager=manager)
        await router.chat(MESSAGES, [], tenant_id="t1", user_id="u1")
        with pytest.raises(QuotaExceededError, match="tenant"):
            await router.chat(MESSAGES, [], tenant_id="t1", user_id="u2")

    async def test_quota_error_not_swallowed_by_fallback(self):
        manager = self._manager(default_user_tokens=5)
        healthy = _CountingBackend(tokens=1)
        router = LLMRouter(
            backends=[_CountingBackend(tokens=1), healthy],
            quota_manager=manager,
        )
        await router.chat(MESSAGES, [], tenant_id="t1", user_id="u1")  # uses 1
        manager.set_user_quota("u1", 1)  # now exhausted
        with pytest.raises(QuotaExceededError):
            await router.chat(MESSAGES, [], tenant_id="t1", user_id="u1")
        # fallback backend must NOT be used to bypass the quota
        assert healthy.calls == 0

    async def test_per_user_override_from_manager(self):
        # Override tightens the vip bucket to 5 tokens. Post-metered: the
        # first call is allowed (0 < 5) and lands 10; the next is rejected.
        manager = self._manager(default_user_tokens=100)
        manager.set_user_quota("vip", 5)
        router = LLMRouter(backend=_CountingBackend(tokens=10), quota_manager=manager)
        await router.chat(MESSAGES, [], tenant_id="t1", user_id="vip")
        with pytest.raises(QuotaExceededError, match="vip"):
            await router.chat(MESSAGES, [], tenant_id="t1", user_id="vip")
        # a regular user on the default limit is unaffected
        response = await router.chat(MESSAGES, [], tenant_id="t1", user_id="regular")
        assert response.content == "ok"

    async def test_disabled_manager_never_blocks(self):
        manager = self._manager(enabled=False, default_user_tokens=0)
        router = LLMRouter(backend=_CountingBackend(tokens=999), quota_manager=manager)
        response = await router.chat(MESSAGES, [], tenant_id="t1", user_id="u1")
        assert response.content == "ok"

    async def test_no_manager_is_zero_overhead(self):
        router = LLMRouter(backend=_CountingBackend(tokens=10))
        response = await router.chat(MESSAGES, [])
        assert response.content == "ok"
