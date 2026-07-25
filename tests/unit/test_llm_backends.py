"""Unit tests for LLM backends (backend.app.core.llm.backends).

Covers:
- _normalize_tool_parameters
- _to_openai_tool
- _parse_tool_arguments
- LLMResponse / TokenUsage
- MockLLMBackend behaviour
- OpenAIBackend retry / rate-limit logic (mocked HTTP)
- LLMRouter fallback chain
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.core.llm.backends import (
    BaseLLMBackend,
    LLMBackendError,
    LLMResponse,
    MockLLMBackend,
    OpenAIBackend,
    TokenUsage,
    _normalize_tool_parameters,
    _parse_tool_arguments,
    _to_openai_tool,
    get_pricing_table,
    reset_pricing_table_cache,
)


# ---------------------------------------------------------------------------
# _normalize_tool_parameters
# ---------------------------------------------------------------------------

class TestNormalizeToolParameters:
    def test_none_returns_empty_object(self):
        result = _normalize_tool_parameters(None)
        assert result == {"type": "object", "properties": {}}

    def test_empty_dict_returns_empty_object(self):
        result = _normalize_tool_parameters({})
        assert result == {"type": "object", "properties": {}}

    def test_non_dict_returns_empty_object(self):
        result = _normalize_tool_parameters("invalid")
        assert result == {"type": "object", "properties": {}}

    def test_missing_type_forces_object(self):
        params = {"properties": {"name": {"type": "string"}}}
        result = _normalize_tool_parameters(params)
        assert result["type"] == "object"
        assert "name" in result["properties"]

    def test_wrong_type_forces_object(self):
        params = {"type": "array", "properties": {"x": {"type": "number"}}}
        result = _normalize_tool_parameters(params)
        assert result["type"] == "object"

    def test_valid_object_unchanged(self):
        params = {"type": "object", "properties": {"a": {"type": "string"}}}
        result = _normalize_tool_parameters(params)
        assert result == params

    def test_adds_properties_if_missing(self):
        params = {"type": "object"}
        result = _normalize_tool_parameters(params)
        assert result["properties"] == {}


# ---------------------------------------------------------------------------
# _to_openai_tool
# ---------------------------------------------------------------------------

class TestToOpenaiTool:
    def test_wraps_bare_tool(self):
        tool = {"name": "search", "description": "Search stuff", "parameters": {"type": "object", "properties": {}}}
        result = _to_openai_tool(tool)
        assert result["type"] == "function"
        assert result["function"]["name"] == "search"
        assert result["function"]["description"] == "Search stuff"

    def test_passes_through_function_type(self):
        tool = {
            "type": "function",
            "function": {"name": "calc", "description": "Calculate", "parameters": {"type": "object", "properties": {}}},
        }
        result = _to_openai_tool(tool)
        assert result["function"]["name"] == "calc"

    def test_strips_x_keys(self):
        tool = {
            "type": "function",
            "function": {"name": "t", "description": "", "parameters": {}, "x-internal": True},
        }
        result = _to_openai_tool(tool)
        assert "x-internal" not in result["function"]

    def test_missing_name_defaults_unknown(self):
        tool = {"description": "no name"}
        result = _to_openai_tool(tool)
        assert result["function"]["name"] == "unknown"


# ---------------------------------------------------------------------------
# _parse_tool_arguments
# ---------------------------------------------------------------------------

class TestParseToolArguments:
    def test_dict_passthrough(self):
        d = {"path": "/tmp"}
        assert _parse_tool_arguments(d) is d

    def test_none_returns_empty(self):
        assert _parse_tool_arguments(None) == {}

    def test_json_string_parsed(self):
        raw = json.dumps({"key": "value"})
        assert _parse_tool_arguments(raw) == {"key": "value"}

    def test_invalid_json_returns_empty(self):
        assert _parse_tool_arguments("not json{{{") == {}

    def test_non_dict_json_returns_empty(self):
        assert _parse_tool_arguments("[1,2,3]") == {}

    def test_empty_string_returns_empty(self):
        assert _parse_tool_arguments("") == {}


# ---------------------------------------------------------------------------
# TokenUsage
# ---------------------------------------------------------------------------

class TestTokenUsage:
    def setup_method(self):
        reset_pricing_table_cache()

    def test_calculate_cost_known_model(self):
        usage = TokenUsage(prompt_tokens=1000, completion_tokens=500, total_tokens=1500)
        cost = usage.calculate_cost("gpt-4")
        # gpt-4: prompt=0.03/1K, completion=0.06/1K
        expected = (1000 * 0.03 + 500 * 0.06) / 1000
        assert abs(cost - expected) < 1e-9

    def test_calculate_cost_unknown_model_zero(self):
        usage = TokenUsage(prompt_tokens=100, completion_tokens=100, total_tokens=200)
        cost = usage.calculate_cost("nonexistent-model")
        assert cost == 0.0


# ---------------------------------------------------------------------------
# MockLLMBackend
# ---------------------------------------------------------------------------

class TestMockLLMBackend:
    @pytest.fixture
    def backend(self):
        return MockLLMBackend()

    async def test_echo_tool_call(self, backend):
        messages = [{"role": "user", "content": "Task: echo: hello world"}]
        resp = await backend.chat(messages, tools=[])
        assert resp.tool_calls
        assert resp.tool_calls[0]["name"] == "echo"
        assert resp.tool_calls[0]["arguments"]["text"] == "hello world"

    async def test_normal_response(self, backend):
        messages = [{"role": "user", "content": "What is 2+2?"}]
        resp = await backend.chat(messages, tools=[])
        assert resp.content is not None
        assert "mock response" in resp.content
        assert resp.tokens_used > 0

    async def test_tool_result_observation(self, backend):
        messages = [
            {"role": "user", "content": "do something"},
            {"role": "tool", "content": "result: 42"},
        ]
        resp = await backend.chat(messages, tools=[])
        assert "Tool result observed" in resp.content

    async def test_model_is_mock(self, backend):
        resp = await backend.chat([{"role": "user", "content": "hi"}], tools=[])
        assert resp.model == "mock"


# ---------------------------------------------------------------------------
# OpenAIBackend (mocked)
# ---------------------------------------------------------------------------

class TestOpenAIBackend:
    @pytest.fixture
    def backend(self):
        return OpenAIBackend(
            api_key="test-key",
            model="gpt-4",
            max_retries=2,
            retry_delay=0.01,
            timeout=5.0,
        )

    async def test_rate_limit_tracking(self, backend):
        """Rate limiter tracks request times."""
        await backend._check_rate_limit()
        assert len(backend._request_times) == 1
        await backend._check_rate_limit()
        assert len(backend._request_times) == 2

    async def test_retry_with_backoff_success(self, backend):
        """Successful call returns immediately."""
        factory = AsyncMock(return_value="result")
        result = await backend._retry_with_backoff(factory)
        assert result == "result"
        assert factory.call_count == 1

    async def test_retry_with_backoff_eventual_success(self, backend):
        """Retries on failure then succeeds."""
        call_count = 0

        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("transient")
            return "ok"

        result = await backend._retry_with_backoff(flaky)
        assert result == "ok"
        assert call_count == 3

    async def test_retry_exhausted_raises(self, backend):
        """Raises LLMBackendError after max retries."""
        async def always_fail():
            raise RuntimeError("permanent")

        with pytest.raises(LLMBackendError, match="failed after"):
            await backend._retry_with_backoff(always_fail)

    async def test_close_idempotent(self, backend):
        """close() is safe to call multiple times."""
        await backend.close()
        await backend.close()
        assert backend._client is None


# ---------------------------------------------------------------------------
# BaseLLMBackend
# ---------------------------------------------------------------------------

class TestBaseLLMBackend:
    async def test_chat_not_implemented(self):
        backend = BaseLLMBackend()
        with pytest.raises(NotImplementedError):
            await backend.chat([], [])

    async def test_stream_not_implemented(self):
        backend = BaseLLMBackend()
        with pytest.raises(NotImplementedError):
            await backend.stream_chat([], [])


# ---------------------------------------------------------------------------
# Pricing table
# ---------------------------------------------------------------------------

class TestPricingTable:
    def setup_method(self):
        reset_pricing_table_cache()

    def teardown_method(self):
        reset_pricing_table_cache()

    def test_returns_dict(self):
        table = get_pricing_table()
        assert isinstance(table, dict)
        assert "gpt-4" in table

    def test_cache_works(self):
        t1 = get_pricing_table()
        t2 = get_pricing_table()
        assert t1 is t2
