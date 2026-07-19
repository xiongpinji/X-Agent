"""Edge case and error scenario tests for LLM module."""

import pytest
from backend.app.core.llm import (
    BaseLLMBackend,
    LLMBackendError,
    LLMResponse,
    MockLLMBackend,
    OpenAIBackend,
    OpenAIResponsesBackend,
    LLMRouter,
    build_llm_router,
)


class TimeoutBackend(BaseLLMBackend):
    """Backend that simulates timeout."""
    name = "timeout"

    async def chat(self, messages, tools):
        raise LLMBackendError("Request timeout after 30s")


class PartialFailureBackend(BaseLLMBackend):
    """Backend that fails on first call, succeeds on second."""
    name = "partial"
    call_count = 0

    async def chat(self, messages, tools):
        self.call_count += 1
        if self.call_count == 1:
            raise LLMBackendError("Temporary failure")
        return LLMResponse(content="recovered", model="partial")


class TestMockLLMBackend:
    """Test MockLLMBackend edge cases."""

    async def test_mock_backend_with_empty_messages(self):
        """Test mock backend with empty message list."""
        backend = MockLLMBackend()
        response = await backend.chat([], [])
        assert response.content == "X-Agent Phase 0 mock response: "
        assert response.tokens_used == 0

    async def test_mock_backend_with_tool_message(self):
        """Test mock backend handling tool response."""
        backend = MockLLMBackend()
        messages = [
            {"role": "user", "content": "Do something"},
            {"role": "tool", "content": "Tool executed successfully"},
        ]
        response = await backend.chat(messages, [])
        assert "Tool result observed" in response.content
        assert response.tokens_used > 0

    async def test_mock_backend_with_echo_command(self):
        """Test mock backend echo tool call."""
        backend = MockLLMBackend()
        messages = [{"role": "user", "content": "Task: echo: hello world"}]
        response = await backend.chat(messages, [])
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]["name"] == "echo"
        assert response.tool_calls[0]["arguments"]["text"] == "hello world"

    async def test_mock_backend_with_multiline_task(self):
        """Test mock backend with multiline task description."""
        backend = MockLLMBackend()
        messages = [
            {
                "role": "user",
                "content": "Some context\nTask: analyze data\nMore context",
            }
        ]
        response = await backend.chat(messages, [])
        assert "analyze data" in response.content

    async def test_mock_backend_with_multiple_user_messages(self):
        """Test mock backend picks last user message."""
        backend = MockLLMBackend()
        messages = [
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "Response"},
            {"role": "user", "content": "Second message"},
        ]
        response = await backend.chat(messages, [])
        assert "Second message" in response.content

    async def test_mock_backend_token_counting(self):
        """Test mock backend token counting."""
        backend = MockLLMBackend()
        messages = [{"role": "user", "content": "one two three four five"}]
        response = await backend.chat(messages, [])
        assert response.tokens_used == 5


class TestOpenAIResponsesBackend:
    """Test OpenAIResponsesBackend edge cases."""

    def test_openai_backend_initialization(self):
        """Test OpenAI backend initialization."""
        backend = OpenAIResponsesBackend(
            api_key="test-key",
            model="gpt-4",
            base_url="https://api.openai.com/v1",
        )
        assert backend.api_key == "test-key"
        assert backend.model == "gpt-4"
        assert backend.base_url == "https://api.openai.com/v1"
        assert backend.name == "openai"

    def test_openai_backend_custom_name(self):
        """Test OpenAI backend with custom name."""
        backend = OpenAIResponsesBackend(
            api_key="test-key",
            model="gpt-4",
            name="custom-openai",
        )
        assert backend.name == "custom-openai"

    def test_openai_backend_without_base_url(self):
        """Test OpenAI backend without custom base URL."""
        backend = OpenAIResponsesBackend(
            api_key="test-key",
            model="gpt-4",
        )
        assert backend.base_url is None

    def test_to_response_input_with_tool_message(self):
        """Test message conversion with tool role."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "tool", "content": "Tool output"},
        ]
        result = OpenAIResponsesBackend._to_response_input(messages)
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "user"
        assert "Tool output:" in result[1]["content"]

    def test_to_response_input_with_system_message(self):
        """Test message conversion with system role."""
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
        ]
        result = OpenAIResponsesBackend._to_response_input(messages)
        assert result[0]["role"] == "system"
        assert result[1]["role"] == "user"

    def test_to_response_input_with_developer_message(self):
        """Test message conversion with developer role."""
        messages = [
            {"role": "developer", "content": "Developer instructions"},
            {"role": "user", "content": "Hello"},
        ]
        result = OpenAIResponsesBackend._to_response_input(messages)
        assert result[0]["role"] == "developer"

    def test_to_response_input_with_unknown_role(self):
        """Test message conversion with unknown role."""
        messages = [
            {"role": "unknown", "content": "Unknown role"},
        ]
        result = OpenAIResponsesBackend._to_response_input(messages)
        assert result[0]["role"] == "user"

    def test_to_response_input_with_missing_fields(self):
        """Test message conversion with missing fields."""
        messages = [
            {"role": "user"},  # missing content
            {"content": "Hello"},  # missing role
        ]
        result = OpenAIResponsesBackend._to_response_input(messages)
        assert result[0]["content"] == ""
        assert result[1]["role"] == "user"


class TestLLMRouter:
    """Test LLMRouter edge cases."""

    async def test_router_with_single_backend(self):
        """Test router with single backend."""
        backend = MockLLMBackend()
        router = LLMRouter(backend=backend)
        response = await router.chat([{"role": "user", "content": "test"}], [])
        assert response.model == "mock"

    async def test_router_with_multiple_backends(self):
        """Test router with multiple backends."""
        backends = [MockLLMBackend(), MockLLMBackend()]
        router = LLMRouter(backends=backends)
        response = await router.chat([{"role": "user", "content": "test"}], [])
        assert response.model == "mock"

    def test_router_initialization_conflict(self):
        """Test router raises error when both backend and backends provided."""
        with pytest.raises(ValueError, match="Pass either backend or backends"):
            LLMRouter(backend=MockLLMBackend(), backends=[MockLLMBackend()])

    def test_router_default_backend(self):
        """Test router uses MockLLMBackend by default."""
        router = LLMRouter()
        assert len(router._backends) == 1
        assert isinstance(router._backends[0], MockLLMBackend)

    async def test_router_fallback_on_timeout(self):
        """Test router falls back after timeout."""
        backends = [TimeoutBackend(), MockLLMBackend()]
        router = LLMRouter(backends=backends)
        response = await router.chat([{"role": "user", "content": "test"}], [])
        assert response.model == "mock"

    async def test_router_all_backends_fail(self):
        """Test router raises error when all backends fail."""
        backends = [TimeoutBackend(), TimeoutBackend()]
        router = LLMRouter(backends=backends)
        with pytest.raises(LLMBackendError, match="No LLM backend completed"):
            await router.chat([{"role": "user", "content": "test"}], [])

    async def test_router_preserves_last_error(self):
        """Test router preserves last error message."""
        backends = [TimeoutBackend()]
        router = LLMRouter(backends=backends)
        with pytest.raises(LLMBackendError) as exc_info:
            await router.chat([{"role": "user", "content": "test"}], [])
        assert "timeout" in str(exc_info.value).lower()


class TestBuildLLMRouter:
    """Test build_llm_router factory function."""

    def test_build_router_with_explicit_backend(self):
        """Test building router with explicit backend."""
        router = build_llm_router(
            llm_backend="mock",
            fallback_order="openai,deepseek,mock",
            openai_api_key=None,
            openai_model="gpt-4",
            deepseek_api_key=None,
            deepseek_model="deepseek-chat",
            deepseek_base_url="https://api.deepseek.com/v1",
        )
        assert len(router._backends) == 1
        assert isinstance(router._backends[0], MockLLMBackend)

    def test_build_router_with_openai_key(self):
        """Test building router with OpenAI API key."""
        router = build_llm_router(
            llm_backend="openai",
            fallback_order="openai,mock",
            openai_api_key="test-key",
            openai_model="gpt-4",
            deepseek_api_key=None,
            deepseek_model="deepseek-chat",
            deepseek_base_url="https://api.deepseek.com/v1",
        )
        assert len(router._backends) == 1
        assert isinstance(router._backends[0], OpenAIBackend)

    def test_build_router_with_deepseek_key(self):
        """Test building router with DeepSeek API key."""
        router = build_llm_router(
            llm_backend="deepseek",
            fallback_order="deepseek,mock",
            openai_api_key=None,
            openai_model="gpt-4",
            deepseek_api_key="test-key",
            deepseek_model="deepseek-chat",
            deepseek_base_url="https://api.deepseek.com/v1",
        )
        assert len(router._backends) == 1
        assert isinstance(router._backends[0], OpenAIBackend)
        assert router._backends[0].name == "deepseek"

    def test_build_router_auto_mode_with_keys(self):
        """Test building router in auto mode with multiple keys."""
        router = build_llm_router(
            llm_backend="auto",
            fallback_order="openai,deepseek,mock",
            openai_api_key="openai-key",
            openai_model="gpt-4",
            deepseek_api_key="deepseek-key",
            deepseek_model="deepseek-chat",
            deepseek_base_url="https://api.deepseek.com/v1",
        )
        assert len(router._backends) == 3
        assert isinstance(router._backends[0], OpenAIBackend)
        assert isinstance(router._backends[1], OpenAIBackend)
        assert isinstance(router._backends[2], MockLLMBackend)

    def test_build_router_auto_mode_without_keys(self):
        """Test building router in auto mode without keys."""
        router = build_llm_router(
            llm_backend="auto",
            fallback_order="openai,deepseek,mock",
            openai_api_key=None,
            openai_model="gpt-4",
            deepseek_api_key=None,
            deepseek_model="deepseek-chat",
            deepseek_base_url="https://api.deepseek.com/v1",
        )
        assert len(router._backends) == 1
        assert isinstance(router._backends[0], MockLLMBackend)

    def test_build_router_with_empty_fallback_order(self):
        """Test building router with empty fallback order."""
        router = build_llm_router(
            llm_backend="auto",
            fallback_order="",
            openai_api_key=None,
            openai_model="gpt-4",
            deepseek_api_key=None,
            deepseek_model="deepseek-chat",
            deepseek_base_url="https://api.deepseek.com/v1",
        )
        assert len(router._backends) == 1
        assert isinstance(router._backends[0], MockLLMBackend)

    def test_build_router_with_whitespace_fallback_order(self):
        """Test building router with whitespace in fallback order."""
        router = build_llm_router(
            llm_backend="auto",
            fallback_order="  openai  ,  deepseek  ,  mock  ",
            openai_api_key=None,
            openai_model="gpt-4",
            deepseek_api_key=None,
            deepseek_model="deepseek-chat",
            deepseek_base_url="https://api.deepseek.com/v1",
        )
        assert len(router._backends) == 1
        assert isinstance(router._backends[0], MockLLMBackend)

    def test_build_router_with_unknown_backend(self):
        """Test building router with unknown backend name."""
        router = build_llm_router(
            llm_backend="unknown",
            fallback_order="unknown,mock",
            openai_api_key=None,
            openai_model="gpt-4",
            deepseek_api_key=None,
            deepseek_model="deepseek-chat",
            deepseek_base_url="https://api.deepseek.com/v1",
        )
        assert len(router._backends) == 1
        assert isinstance(router._backends[0], MockLLMBackend)
