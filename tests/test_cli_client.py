"""Unit tests for CLI client abstraction layer.

Tests HTTPClient, LocalClient, create_client factory, and exception handling.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from cli.client import (
    APIError,
    AuthError,
    BaseClient,
    ConnectionError,
    HTTPClient,
    LocalClient,
    XAgentCLIError,
    create_client,
)
from cli.config import CLIConfig


class TestCreateClientFactory:
    """Test create_client factory function."""

    def test_create_client_http_mode(self):
        """Test create_client returns HTTPClient for http mode."""
        config = CLIConfig(mode="http")
        client = create_client(config)
        assert isinstance(client, HTTPClient)

    def test_create_client_local_mode(self):
        """Test create_client returns LocalClient for local mode."""
        config = CLIConfig(mode="local")
        client = create_client(config)
        assert isinstance(client, LocalClient)

    def test_create_client_invalid_mode(self):
        """Test create_client raises ValueError for invalid mode."""
        config = CLIConfig(mode="http")
        config.mode = "invalid"  # Bypass pydantic validation
        with pytest.raises(ValueError, match="Invalid client mode"):
            create_client(config)


class TestHTTPClient:
    """Test HTTPClient implementation."""

    def test_http_client_init(self):
        """Test HTTPClient initializes with config."""
        config = CLIConfig(
            api_base_url="http://api.example.com:8000",
            api_key="test-key",
            timeout=60,
        )
        client = HTTPClient(config)
        assert client.base_url == "http://api.example.com:8000"
        assert client.api_key == "test-key"
        assert client.timeout == 60

    def test_http_client_strips_trailing_slash(self):
        """Test HTTPClient strips trailing slash from base_url."""
        config = CLIConfig(api_base_url="http://localhost:8000/")
        client = HTTPClient(config)
        assert client.base_url == "http://localhost:8000"

    @pytest.mark.asyncio
    async def test_http_client_get_client_creates_async_client(self):
        """Test _get_client creates httpx.AsyncClient."""
        config = CLIConfig(api_base_url="http://localhost:8000", api_key="key")
        client = HTTPClient(config)
        async_client = await client._get_client()
        assert isinstance(async_client, httpx.AsyncClient)
        await client.close()

    @pytest.mark.asyncio
    async def test_http_client_get_client_reuses_instance(self):
        """Test _get_client reuses same instance."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)
        client1 = await client._get_client()
        client2 = await client._get_client()
        assert client1 is client2
        await client.close()

    @pytest.mark.asyncio
    async def test_http_client_close(self):
        """Test close method closes async client."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)
        await client._get_client()
        assert client._client is not None
        await client.close()
        assert client._client is None

    @pytest.mark.asyncio
    async def test_http_client_request_success(self):
        """Test _request handles successful response."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await client._request("GET", "/api/test")
            assert result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_http_client_request_401_auth_error(self):
        """Test _request raises AuthError for 401 status."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)

        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            with pytest.raises(AuthError, match="invalid or missing API key"):
                await client._request("GET", "/api/test")

    @pytest.mark.asyncio
    async def test_http_client_request_403_auth_error(self):
        """Test _request raises AuthError for 403 status."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)

        mock_response = MagicMock()
        mock_response.status_code = 403

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            with pytest.raises(AuthError, match="insufficient permissions"):
                await client._request("GET", "/api/test")

    @pytest.mark.asyncio
    async def test_http_client_request_500_api_error(self):
        """Test _request raises APIError for 5xx status."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"detail": "Internal server error"}

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            with pytest.raises(APIError, match="Internal server error"):
                await client._request("GET", "/api/test")

    @pytest.mark.asyncio
    async def test_http_client_request_connect_error(self):
        """Test _request raises ConnectionError on httpx.ConnectError."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            with pytest.raises(ConnectionError, match="Failed to connect"):
                await client._request("GET", "/api/test")

    @pytest.mark.asyncio
    async def test_http_client_request_timeout_error(self):
        """Test _request raises ConnectionError on httpx.TimeoutException."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("Request timeout"),
        ):
            with pytest.raises(ConnectionError, match="Request timeout"):
                await client._request("GET", "/api/test")

    @pytest.mark.asyncio
    async def test_http_client_run_agent(self):
        """Test run_agent sends correct payload."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"trace_id": "123", "status": "completed"}

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_request:
            result = await client.run_agent(
                task="test task",
                permission_scope=["read", "write"],
                extra_context={"key": "value"},
                stream=True,
            )

            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[0][0] == "POST"
            assert call_args[0][1] == "/api/v1/agents/run"
            assert call_args[1]["json"]["task"] == "test task"
            assert result["trace_id"] == "123"

    @pytest.mark.asyncio
    async def test_http_client_list_agents(self):
        """Test list_agents calls correct endpoint."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": "agent1"}]}

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_request:
            result = await client.list_agents()

            mock_request.assert_called_once_with("GET", "/api/v1/agents")
            assert result["data"][0]["id"] == "agent1"

    @pytest.mark.asyncio
    async def test_http_client_list_tools(self):
        """Test list_tools returns list."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"name": "tool1"}]

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await client.list_tools()
            assert isinstance(result, list)
            assert result[0]["name"] == "tool1"

    @pytest.mark.asyncio
    async def test_http_client_list_workflows(self):
        """Test list_workflows returns list."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": "wf1"}]}

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await client.list_workflows()
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_http_client_create_workflow(self):
        """Test create_workflow sends spec."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)

        spec = {"name": "test-wf", "nodes": []}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "wf123", "name": "test-wf"}

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_request:
            result = await client.create_workflow(spec)

            call_args = mock_request.call_args
            assert call_args[0][0] == "POST"
            assert call_args[0][1] == "/api/v1/workflows"
            assert call_args[1]["json"] == spec

    @pytest.mark.asyncio
    async def test_http_client_run_workflow(self):
        """Test run_workflow sends workflow_id and inputs."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"run_id": "run123"}

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_request:
            result = await client.run_workflow("wf123", inputs={"param": "value"})

            call_args = mock_request.call_args
            assert "/api/v1/workflows/wf123/run" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_http_client_get_workflow_status(self):
        """Test get_workflow_status calls correct endpoint."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "running"}

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_request:
            result = await client.get_workflow_status("wf123")

            call_args = mock_request.call_args
            assert "/api/v1/workflows/wf123/status" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_http_client_health_check_healthy(self):
        """Test health_check returns healthy status."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy"}

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await client.health_check()
            assert result["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_http_client_health_check_unhealthy(self):
        """Test health_check handles errors gracefully."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = await client.health_check()
            assert result["status"] == "unhealthy"
            assert "error" in result


class TestLocalClient:
    """Test LocalClient implementation."""

    def test_local_client_init(self):
        """Test LocalClient initializes with config."""
        config = CLIConfig(mode="local")
        client = LocalClient(config)
        assert client.config == config
        assert client._initialized is False

    @pytest.mark.asyncio
    async def test_local_client_ensure_initialized_success(self):
        """Test _ensure_initialized imports backend successfully."""
        config = CLIConfig(mode="local")
        client = LocalClient(config)

        mock_agent = MagicMock()
        with patch(
            "backend.app.dependencies.get_agent",
            return_value=mock_agent,
        ):
            await client._ensure_initialized()
            assert client._initialized is True
            assert client._agent == mock_agent

    @pytest.mark.asyncio
    async def test_local_client_ensure_initialized_failure(self):
        """Test _ensure_initialized raises ConnectionError on import failure."""
        config = CLIConfig(mode="local")
        client = LocalClient(config)

        with patch(
            "backend.app.dependencies.get_agent",
            side_effect=ImportError("backend not found"),
        ):
            with pytest.raises(ConnectionError, match="Failed to initialize"):
                await client._ensure_initialized()

    @pytest.mark.asyncio
    async def test_local_client_run_agent(self):
        """Test run_agent executes task locally."""
        from backend.app.core.agent.loop import AgentRunResponse, RunContext

        config = CLIConfig(mode="local")
        client = LocalClient(config)

        # Wave A: AgentLoop.run(context, task, extra_context) returns
        # AgentRunResponse; permission_scope travels on the RunContext.
        mock_agent = AsyncMock()
        mock_agent.run.return_value = AgentRunResponse(
            trace_id="trace-test",
            agent_id="agent-test",
            status="completed",
            answer="result",
            iterations=1,
            memory_hits=0,
            tool_calls=[],
            events=[],
            plan=[],
            execution_summary={},
        )

        with patch(
            "backend.app.dependencies.get_agent",
            return_value=mock_agent,
        ):
            result = await client.run_agent(
                task="test",
                permission_scope=["read"],
                extra_context={"key": "val"},
            )

            assert result["task"] == "test"
            assert result["mode"] == "local"
            assert result["trace_id"] == "trace-test"
            assert result["status"] == "completed"
            mock_agent.run.assert_called_once()
            call_args = mock_agent.run.call_args
            assert isinstance(call_args.args[0], RunContext)
            assert call_args.args[0].permission_scope == ["read"]
            assert call_args.args[1] == "test"
            assert call_args.args[2] == {"key": "val"}

    @pytest.mark.asyncio
    async def test_local_client_list_agents(self):
        """Test list_agents returns mock agent list."""
        config = CLIConfig(mode="local")
        client = LocalClient(config)

        mock_agent = MagicMock()
        with patch(
            "backend.app.dependencies.get_agent",
            return_value=mock_agent,
        ):
            result = await client.list_agents()
            assert "data" in result
            assert len(result["data"]) > 0
            assert result["data"][0]["id"] == "local-agent"

    @pytest.mark.asyncio
    async def test_local_client_list_tools_not_implemented(self):
        """Test list_tools raises NotImplementedError."""
        config = CLIConfig(mode="local")
        client = LocalClient(config)

        mock_agent = MagicMock()
        with patch(
            "backend.app.dependencies.get_agent",
            return_value=mock_agent,
        ):
            with pytest.raises(NotImplementedError):
                await client.list_tools()

    @pytest.mark.asyncio
    async def test_local_client_list_workflows_not_implemented(self):
        """Test list_workflows raises NotImplementedError."""
        config = CLIConfig(mode="local")
        client = LocalClient(config)

        mock_agent = MagicMock()
        with patch(
            "backend.app.dependencies.get_agent",
            return_value=mock_agent,
        ):
            with pytest.raises(NotImplementedError):
                await client.list_workflows()

    @pytest.mark.asyncio
    async def test_local_client_create_workflow_not_implemented(self):
        """Test create_workflow raises NotImplementedError."""
        config = CLIConfig(mode="local")
        client = LocalClient(config)

        with pytest.raises(NotImplementedError):
            await client.create_workflow({"name": "test"})

    @pytest.mark.asyncio
    async def test_local_client_run_workflow_not_implemented(self):
        """Test run_workflow raises NotImplementedError."""
        config = CLIConfig(mode="local")
        client = LocalClient(config)

        with pytest.raises(NotImplementedError):
            await client.run_workflow("wf123")

    @pytest.mark.asyncio
    async def test_local_client_get_workflow_status_not_implemented(self):
        """Test get_workflow_status raises NotImplementedError."""
        config = CLIConfig(mode="local")
        client = LocalClient(config)

        with pytest.raises(NotImplementedError):
            await client.get_workflow_status("wf123")

    @pytest.mark.asyncio
    async def test_local_client_health_check_healthy(self):
        """Test health_check returns healthy status."""
        config = CLIConfig(mode="local")
        client = LocalClient(config)

        mock_agent = MagicMock()
        with patch(
            "backend.app.dependencies.get_agent",
            return_value=mock_agent,
        ):
            result = await client.health_check()
            assert result["status"] == "healthy"
            assert result["mode"] == "local"

    @pytest.mark.asyncio
    async def test_local_client_health_check_unhealthy(self):
        """Test health_check returns unhealthy on error."""
        config = CLIConfig(mode="local")
        client = LocalClient(config)

        with patch(
            "backend.app.dependencies.get_agent",
            side_effect=Exception("Backend error"),
        ):
            result = await client.health_check()
            assert result["status"] == "unhealthy"
            assert "error" in result


class TestExceptions:
    """Test exception hierarchy."""

    def test_xagent_cli_error_is_exception(self):
        """Test XAgentCLIError is Exception subclass."""
        assert issubclass(XAgentCLIError, Exception)

    def test_connection_error_is_xagent_cli_error(self):
        """Test ConnectionError is XAgentCLIError subclass."""
        assert issubclass(ConnectionError, XAgentCLIError)

    def test_auth_error_is_xagent_cli_error(self):
        """Test AuthError is XAgentCLIError subclass."""
        assert issubclass(AuthError, XAgentCLIError)

    def test_api_error_is_xagent_cli_error(self):
        """Test APIError is XAgentCLIError subclass."""
        assert issubclass(APIError, XAgentCLIError)
