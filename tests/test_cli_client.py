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
    async def test_http_client_invoke_sdk_contract_calls_control_plane_stub(self):
        """Test SDK contract invoke uses the owner-gated backend stub."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)
        contract = {
            "operation": "turn_start",
            "request": {"method": "turn/start", "params": {"thread_id": "thread-1"}},
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "sdk_runtime_enablement_receipt_contract_ready",
            "sdk": {
                "adapter_execution_enabled": False,
                "agent_execution_enabled": False,
                "mutation_performed": False,
                "read_only_runner_contract": {
                    "read_only_runner_enabled": True,
                    "agent_execution_enabled": False,
                    "write_execution_enabled": False,
                },
                "execution_adapter_contract": {
                    "adapter_execution_enabled": False,
                    "mark_executed": False,
                },
                "write_runner_safety_contract": {
                    "runner_invoked": False,
                    "mark_executed": False,
                    "mutation_performed": False,
                },
                "dry_run_executor_stub": {
                    "audit_event_recorded": True,
                    "runner_invoked": False,
                    "mutation_performed": False,
                },
                "write_runner_execute_gate": {
                    "gate_status": "ready_but_disabled",
                    "execute_enabled": False,
                    "write_runner_enabled": False,
                    "agent_execution_enabled": False,
                    "mutation_performed": False,
                },
                "write_runner_adapter_review": {
                    "review_status": "ready_but_disabled",
                    "adapter_target": {"callable": "AgentCoordinator.run"},
                    "implementation_enabled": False,
                    "write_runner_enabled": False,
                    "agent_execution_enabled": False,
                    "mark_executed": False,
                    "mutation_performed": False,
                },
                "write_runner_runtime_flag": {
                    "flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                    "flag_status": "declared_disabled",
                    "runtime_flag_enabled": False,
                    "write_runner_enabled": False,
                    "mutation_performed": False,
                },
                "owner_acceptance_evidence": {
                    "evidence_status": "recording_contract_ready_not_provided",
                    "recording_contract_ready": True,
                    "evidence_type": "sdk_write_runner_owner_acceptance",
                    "execute_enabled": False,
                    "write_runner_enabled": False,
                    "mutation_performed": False,
                },
                "runtime_enablement_review": {
                    "review_status": "ready_but_disabled",
                    "runtime_flag_enabled": False,
                    "write_runner_enabled": False,
                    "agent_execution_enabled": False,
                    "mutation_performed": False,
                },
                "write_runner_implementation_plan": {
                    "plan_status": "ready_but_disabled",
                    "adapter_target": {"callable": "AgentCoordinator.run"},
                    "idempotency_contract": {"required": True},
                    "rollback_plan": {"disable_runtime_flag": True},
                    "implementation_enabled": False,
                    "runtime_flag_enabled": False,
                    "write_runner_enabled": False,
                    "agent_execution_enabled": False,
                    "runner_invoked": False,
                    "mark_executed": False,
                    "mutation_performed": False,
                },
                "runtime_smoke_runbook": {
                    "contract_status": "ready_but_disabled",
                    "smoke_plan": {"requires_runtime_flag": "XAGENT_SDK_WRITE_RUNNER_ENABLED=true"},
                    "rollback_plan": {"failure_receipt_required": True},
                    "failure_receipt_contract": {
                        "audit_action": "sdk.write_runner.failed",
                        "mark_executed_must_be_false_on_failure": True,
                    },
                    "write_runner_enabled": False,
                    "agent_execution_enabled": False,
                    "runner_invoked": False,
                    "mark_executed": False,
                    "mutation_performed": False,
                },
                "runtime_enablement_receipt": {
                    "receipt_status": "ready_but_disabled",
                    "receipt_type": "sdk_write_runner_runtime_enablement_readiness",
                    "receipt_schema": {"runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED"},
                    "owner_review_policy": {"requires_expiry": True},
                    "runtime_flag_enabled": False,
                    "write_runner_enabled": False,
                    "agent_execution_enabled": False,
                    "runner_invoked": False,
                    "mark_executed": False,
                    "mutation_performed": False,
                },
            },
        }

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_request:
            result = await client.invoke_sdk_contract(contract)

            call_args = mock_request.call_args
            assert call_args[0][0] == "POST"
            assert call_args[0][1] == "/api/v1/control-plane/sdk/invoke"
            assert call_args[1]["json"] == contract
            assert result["status"] == "sdk_runtime_enablement_receipt_contract_ready"
            assert result["sdk"]["adapter_execution_enabled"] is False
            assert result["sdk"]["execution_adapter_contract"]["mark_executed"] is False
            assert result["sdk"]["read_only_runner_contract"]["write_execution_enabled"] is False
            assert result["sdk"]["write_runner_safety_contract"]["runner_invoked"] is False
            assert result["sdk"]["dry_run_executor_stub"]["audit_event_recorded"] is True
            assert result["sdk"]["write_runner_execute_gate"]["execute_enabled"] is False
            assert result["sdk"]["write_runner_execute_gate"]["write_runner_enabled"] is False
            assert result["sdk"]["write_runner_adapter_review"]["implementation_enabled"] is False
            assert result["sdk"]["write_runner_adapter_review"]["mark_executed"] is False
            assert result["sdk"]["write_runner_runtime_flag"]["runtime_flag_enabled"] is False
            assert (
                result["sdk"]["owner_acceptance_evidence"]["evidence_status"]
                == "recording_contract_ready_not_provided"
            )
            assert result["sdk"]["owner_acceptance_evidence"]["recording_contract_ready"] is True
            assert result["sdk"]["runtime_enablement_review"]["review_status"] == "ready_but_disabled"
            assert result["sdk"]["runtime_enablement_review"]["write_runner_enabled"] is False
            assert result["sdk"]["runtime_enablement_review"]["mutation_performed"] is False
            assert result["sdk"]["write_runner_implementation_plan"]["plan_status"] == "ready_but_disabled"
            assert (
                result["sdk"]["write_runner_implementation_plan"]["adapter_target"]["callable"]
                == "AgentCoordinator.run"
            )
            assert result["sdk"]["write_runner_implementation_plan"]["idempotency_contract"]["required"] is True
            assert result["sdk"]["write_runner_implementation_plan"]["write_runner_enabled"] is False
            assert result["sdk"]["write_runner_implementation_plan"]["agent_execution_enabled"] is False
            assert result["sdk"]["write_runner_implementation_plan"]["runner_invoked"] is False
            assert result["sdk"]["write_runner_implementation_plan"]["mark_executed"] is False
            assert result["sdk"]["write_runner_implementation_plan"]["mutation_performed"] is False
            assert result["sdk"]["runtime_smoke_runbook"]["contract_status"] == "ready_but_disabled"
            assert (
                result["sdk"]["runtime_smoke_runbook"]["smoke_plan"]["requires_runtime_flag"]
                == "XAGENT_SDK_WRITE_RUNNER_ENABLED=true"
            )
            assert result["sdk"]["runtime_smoke_runbook"]["rollback_plan"]["failure_receipt_required"] is True
            assert result["sdk"]["runtime_smoke_runbook"]["write_runner_enabled"] is False
            assert result["sdk"]["runtime_smoke_runbook"]["agent_execution_enabled"] is False
            assert result["sdk"]["runtime_smoke_runbook"]["runner_invoked"] is False
            assert result["sdk"]["runtime_smoke_runbook"]["mark_executed"] is False
            assert result["sdk"]["runtime_smoke_runbook"]["mutation_performed"] is False
            assert result["sdk"]["runtime_enablement_receipt"]["receipt_status"] == "ready_but_disabled"
            assert (
                result["sdk"]["runtime_enablement_receipt"]["receipt_schema"]["runtime_flag_name"]
                == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
            )
            assert result["sdk"]["runtime_enablement_receipt"]["owner_review_policy"]["requires_expiry"] is True
            assert result["sdk"]["runtime_enablement_receipt"]["write_runner_enabled"] is False
            assert result["sdk"]["runtime_enablement_receipt"]["agent_execution_enabled"] is False
            assert result["sdk"]["runtime_enablement_receipt"]["runner_invoked"] is False
            assert result["sdk"]["runtime_enablement_receipt"]["mark_executed"] is False
            assert result["sdk"]["runtime_enablement_receipt"]["mutation_performed"] is False

    @pytest.mark.asyncio
    async def test_http_client_record_sdk_owner_acceptance_calls_owner_gated_stub(self):
        """Test SDK owner acceptance record uses the backend evidence stub."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)
        payload = {
            "owner_acceptance_id": "acceptance-1",
            "approval_id": "approval-1",
            "accepted_by": "owner",
            "accepted_at": "2026-06-08T00:00:00Z",
            "runbook_acknowledged": True,
            "rollback_plan_acknowledged": True,
            "acceptance_hash": "hash-1",
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "status": "sdk_owner_acceptance_record_workflow_ready",
            "owner_acceptance": {
                "audit_event_recorded": True,
                "write_runner_enabled": False,
                "agent_execution_enabled": False,
                "mutation_performed": False,
            },
        }

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_request:
            result = await client.record_sdk_owner_acceptance(payload)

            call_args = mock_request.call_args
            assert call_args[0][0] == "POST"
            assert call_args[0][1] == "/api/v1/control-plane/sdk/owner-acceptance/record"
            assert call_args[1]["json"] == payload
            assert result["status"] == "sdk_owner_acceptance_record_workflow_ready"
            assert result["owner_acceptance"]["write_runner_enabled"] is False
            assert result["owner_acceptance"]["mutation_performed"] is False

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
        config = CLIConfig(mode="local")
        client = LocalClient(config)

        mock_agent = AsyncMock()
        mock_agent.run.return_value = {"output": "result"}

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
            mock_agent.run.assert_called_once()

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
    async def test_local_client_invoke_sdk_contract_not_implemented(self):
        """Test SDK backend invoke is HTTP-only."""
        config = CLIConfig(mode="local")
        client = LocalClient(config)

        with pytest.raises(NotImplementedError, match="SDK backend invocation"):
            await client.invoke_sdk_contract({"operation": "turn_start"})

    @pytest.mark.asyncio
    async def test_local_client_record_sdk_owner_acceptance_not_implemented(self):
        """Test SDK owner acceptance recording is HTTP-only."""
        config = CLIConfig(mode="local")
        client = LocalClient(config)

        with pytest.raises(NotImplementedError, match="SDK owner acceptance recording"):
            await client.record_sdk_owner_acceptance({"approval_id": "approval-1"})

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
