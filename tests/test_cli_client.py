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
            "status": "sdk_runtime_implementation_final_decision_workflow_ready",
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
                "runtime_implementation_preflight": {
                    "preflight_status": "ready_but_disabled",
                    "adapter_module_boundary": {
                        "module": "backend.app.core.agent.coordinator",
                        "callable": "AgentCoordinator.run",
                        "import_allowed": False,
                    },
                    "dependency_injection_contract": {"required": True, "default_factory_enabled": False},
                    "idempotency_lock_contract": {"required": True, "lock_enabled": False},
                    "receipt_persistence_interface": {"required": True, "persistence_enabled": False},
                    "approval_postcondition_contract": {"mark_executed_enabled": False},
                    "failure_handling_contract": {"mark_executed_on_failure": False},
                    "write_runner_enabled": False,
                    "agent_execution_enabled": False,
                    "runner_invoked": False,
                    "mark_executed": False,
                    "mutation_performed": False,
                },
                "runtime_implementation_owner_pack": {
                    "pack_status": "ready_but_disabled",
                    "readback_contract": {
                        "evidence_type": "sdk_write_runner_runtime_implementation_readiness_lock",
                    },
                    "owner_decision_policy": {
                        "can_enable_runtime_flag_after_pack": False,
                        "can_invoke_write_runner_after_pack": False,
                    },
                    "runtime_flag_enabled": False,
                    "write_runner_enabled": False,
                    "agent_execution_enabled": False,
                    "runner_invoked": False,
                    "mutation_performed": False,
                },
                "runtime_implementation_final_decision_workflow": {
                    "workflow_status": "ready_but_disabled",
                    "endpoint": "/api/v1/control-plane/sdk/runtime-implementation/final-decision/record",
                    "audit_action": "sdk.write_runner.runtime_implementation_final_decision_recorded",
                    "decision_effect": {
                        "enables_runtime_flag": False,
                        "starts_agent_execution": False,
                        "marks_approval_executed": False,
                    },
                    "runtime_flag_enabled": False,
                    "implementation_enabled": False,
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
            assert result["status"] == "sdk_runtime_implementation_final_decision_workflow_ready"
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
            assert result["sdk"]["runtime_implementation_preflight"]["preflight_status"] == "ready_but_disabled"
            assert (
                result["sdk"]["runtime_implementation_preflight"]["adapter_module_boundary"]["module"]
                == "backend.app.core.agent.coordinator"
            )
            assert (
                result["sdk"]["runtime_implementation_preflight"]["adapter_module_boundary"]["import_allowed"]
                is False
            )
            assert result["sdk"]["runtime_implementation_preflight"]["idempotency_lock_contract"]["lock_enabled"] is False
            assert (
                result["sdk"]["runtime_implementation_preflight"]["receipt_persistence_interface"]["persistence_enabled"]
                is False
            )
            assert (
                result["sdk"]["runtime_implementation_preflight"]["approval_postcondition_contract"][
                    "mark_executed_enabled"
                ]
                is False
            )
            assert result["sdk"]["runtime_implementation_preflight"]["write_runner_enabled"] is False
            assert result["sdk"]["runtime_implementation_preflight"]["agent_execution_enabled"] is False
            assert result["sdk"]["runtime_implementation_preflight"]["runner_invoked"] is False
            assert result["sdk"]["runtime_implementation_preflight"]["mark_executed"] is False
            assert result["sdk"]["runtime_implementation_preflight"]["mutation_performed"] is False
            assert result["sdk"]["runtime_implementation_owner_pack"]["pack_status"] == "ready_but_disabled"
            assert (
                result["sdk"]["runtime_implementation_owner_pack"]["readback_contract"]["evidence_type"]
                == "sdk_write_runner_runtime_implementation_readiness_lock"
            )
            assert result["sdk"]["runtime_implementation_owner_pack"]["runtime_flag_enabled"] is False
            assert result["sdk"]["runtime_implementation_owner_pack"]["write_runner_enabled"] is False
            assert result["sdk"]["runtime_implementation_owner_pack"]["runner_invoked"] is False
            assert result["sdk"]["runtime_implementation_owner_pack"]["mutation_performed"] is False
            final_decision = result["sdk"]["runtime_implementation_final_decision_workflow"]
            assert final_decision["workflow_status"] == "ready_but_disabled"
            assert (
                final_decision["endpoint"]
                == "/api/v1/control-plane/sdk/runtime-implementation/final-decision/record"
            )
            assert final_decision["decision_effect"]["enables_runtime_flag"] is False
            assert final_decision["decision_effect"]["starts_agent_execution"] is False
            assert final_decision["decision_effect"]["marks_approval_executed"] is False
            assert final_decision["runtime_flag_enabled"] is False
            assert final_decision["implementation_enabled"] is False
            assert final_decision["write_runner_enabled"] is False
            assert final_decision["runner_invoked"] is False
            assert final_decision["mark_executed"] is False
            assert final_decision["mutation_performed"] is False

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
    async def test_http_client_record_sdk_runtime_enablement_receipt_calls_owner_gated_stub(self):
        """Test SDK runtime readiness receipt record uses the backend evidence stub."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)
        payload = {
            "readiness_receipt_id": "readiness-1",
            "approval_id": "approval-1",
            "owner_acceptance_id": "acceptance-1",
            "owner_acceptance_audit_id": "audit-acceptance-1",
            "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
            "smoke_runbook_version": "v1",
            "rollback_runbook_version": "v1",
            "accepted_by": "owner",
            "accepted_at": "2026-06-08T00:00:00Z",
            "expires_at": "2026-06-09T00:00:00Z",
            "smoke_runbook_acknowledged": True,
            "rollback_runbook_acknowledged": True,
            "failure_receipt_reviewed": True,
            "acceptance_hash": "hash-readiness-1",
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "status": "sdk_runtime_enablement_receipt_record_workflow_ready",
            "runtime_enablement_receipt": {
                "audit_event_recorded": True,
                "runtime_flag_enabled": False,
                "write_runner_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
        }

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_request:
            result = await client.record_sdk_runtime_enablement_receipt(payload)

            call_args = mock_request.call_args
            assert call_args[0][0] == "POST"
            assert call_args[0][1] == "/api/v1/control-plane/sdk/runtime-enablement/receipt/record"
            assert call_args[1]["json"] == payload
            assert result["status"] == "sdk_runtime_enablement_receipt_record_workflow_ready"
            assert result["runtime_enablement_receipt"]["runtime_flag_enabled"] is False
            assert result["runtime_enablement_receipt"]["write_runner_enabled"] is False
            assert result["runtime_enablement_receipt"]["runner_invoked"] is False
            assert result["runtime_enablement_receipt"]["mutation_performed"] is False

    @pytest.mark.asyncio
    async def test_http_client_record_sdk_runtime_enablement_owner_pack_decision_calls_owner_gated_stub(self):
        """Test SDK runtime owner pack decision record uses the backend evidence stub."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)
        payload = {
            "owner_pack_decision_id": "decision-1",
            "decision": "accepted",
            "approval_id": "approval-1",
            "readiness_receipt_id": "readiness-1",
            "readiness_receipt_audit_id": "audit-readiness-1",
            "owner_acceptance_id": "acceptance-1",
            "owner_acceptance_audit_id": "audit-acceptance-1",
            "decided_by": "owner",
            "decided_at": "2026-06-08T00:00:00Z",
            "reason": "owner accepted pack",
            "decision_hash": "hash-decision-1",
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "status": "sdk_runtime_enablement_owner_pack_decision_workflow_ready",
            "owner_pack_decision": {
                "audit_event_recorded": True,
                "runtime_flag_enabled": False,
                "write_runner_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
        }

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_request:
            result = await client.record_sdk_runtime_enablement_owner_pack_decision(payload)

            call_args = mock_request.call_args
            assert call_args[0][0] == "POST"
            assert call_args[0][1] == "/api/v1/control-plane/sdk/runtime-enablement/owner-pack/decision/record"
            assert call_args[1]["json"] == payload
            assert result["status"] == "sdk_runtime_enablement_owner_pack_decision_workflow_ready"
            assert result["owner_pack_decision"]["runtime_flag_enabled"] is False
            assert result["owner_pack_decision"]["write_runner_enabled"] is False
            assert result["owner_pack_decision"]["runner_invoked"] is False
            assert result["owner_pack_decision"]["mutation_performed"] is False

    @pytest.mark.asyncio
    async def test_http_client_record_sdk_runtime_implementation_readiness_lock_calls_owner_gated_stub(self):
        """Test SDK runtime implementation readiness lock uses the backend evidence stub."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)
        payload = {
            "implementation_lock_id": "lock-1",
            "idempotency_key": "sdk-write-runner-lock-1",
            "idempotency_hash": "hash-idempotency-1",
            "approval_id": "approval-1",
            "readiness_receipt_id": "readiness-1",
            "readiness_receipt_audit_id": "audit-readiness-1",
            "owner_pack_decision_id": "decision-1",
            "owner_pack_decision_audit_id": "audit-decision-1",
            "operator_id": "operator",
            "locked_at": "2026-06-08T00:00:00Z",
            "lock_reason": "owner accepted readiness lock",
            "lock_hash": "hash-lock-1",
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "status": "sdk_runtime_implementation_readiness_lock_workflow_ready",
            "readiness_lock": {
                "audit_event_recorded": True,
                "runtime_flag_enabled": False,
                "write_runner_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
        }

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_request:
            result = await client.record_sdk_runtime_implementation_readiness_lock(payload)

            call_args = mock_request.call_args
            assert call_args[0][0] == "POST"
            assert call_args[0][1] == "/api/v1/control-plane/sdk/runtime-implementation/readiness-lock/record"
            assert call_args[1]["json"] == payload
            assert result["status"] == "sdk_runtime_implementation_readiness_lock_workflow_ready"
            assert result["readiness_lock"]["runtime_flag_enabled"] is False
            assert result["readiness_lock"]["write_runner_enabled"] is False
            assert result["readiness_lock"]["runner_invoked"] is False
            assert result["readiness_lock"]["mutation_performed"] is False

    @pytest.mark.asyncio
    async def test_http_client_record_sdk_runtime_implementation_final_decision_calls_owner_gated_stub(self):
        """Test SDK runtime implementation final decision uses the backend evidence stub."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)
        payload = {
            "final_decision_id": "final-decision-1",
            "decision": "accepted",
            "approval_id": "approval-1",
            "implementation_lock_id": "lock-1",
            "implementation_lock_audit_id": "audit-lock-1",
            "readiness_receipt_id": "readiness-1",
            "owner_pack_decision_id": "decision-1",
            "decided_by": "owner",
            "decided_at": "2026-06-08T00:00:00Z",
            "reason": "owner accepted final decision",
            "decision_hash": "hash-final-decision-1",
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "status": "sdk_runtime_implementation_final_decision_workflow_ready",
            "final_decision": {
                "audit_event_recorded": True,
                "runtime_flag_enabled": False,
                "implementation_enabled": False,
                "write_runner_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
        }

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_request:
            result = await client.record_sdk_runtime_implementation_final_decision(payload)

            call_args = mock_request.call_args
            assert call_args[0][0] == "POST"
            assert call_args[0][1] == "/api/v1/control-plane/sdk/runtime-implementation/final-decision/record"
            assert call_args[1]["json"] == payload
            assert result["status"] == "sdk_runtime_implementation_final_decision_workflow_ready"
            assert result["final_decision"]["runtime_flag_enabled"] is False
            assert result["final_decision"]["implementation_enabled"] is False
            assert result["final_decision"]["write_runner_enabled"] is False
            assert result["final_decision"]["runner_invoked"] is False
            assert result["final_decision"]["mutation_performed"] is False

    @pytest.mark.asyncio
    async def test_http_client_record_sdk_runtime_flag_enablement_calls_owner_gated_stub(self):
        """Test SDK runtime flag enablement intent uses the backend evidence stub."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)
        payload = {
            "runtime_flag_enablement_id": "flag-enable-1",
            "approval_id": "approval-1",
            "final_decision_id": "final-decision-1",
            "final_decision_audit_id": "audit-final-decision-1",
            "implementation_lock_id": "lock-1",
            "readiness_receipt_id": "readiness-1",
            "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
            "requested_by": "owner",
            "requested_at": "2026-06-08T00:00:00Z",
            "enablement_reason": "owner requested runtime flag enablement",
            "enablement_hash": "hash-flag-enable-1",
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "status": "sdk_runtime_flag_enablement_record_workflow_ready",
            "runtime_flag_enablement": {
                "audit_event_recorded": True,
                "runtime_flag_enabled": False,
                "implementation_enabled": False,
                "write_runner_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
        }

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_request:
            result = await client.record_sdk_runtime_flag_enablement(payload)

            call_args = mock_request.call_args
            assert call_args[0][0] == "POST"
            assert call_args[0][1] == "/api/v1/control-plane/sdk/runtime-flag/enablement/record"
            assert call_args[1]["json"] == payload
            assert result["status"] == "sdk_runtime_flag_enablement_record_workflow_ready"
            assert result["runtime_flag_enablement"]["runtime_flag_enabled"] is False
            assert result["runtime_flag_enablement"]["implementation_enabled"] is False
            assert result["runtime_flag_enablement"]["write_runner_enabled"] is False
            assert result["runtime_flag_enablement"]["runner_invoked"] is False
            assert result["runtime_flag_enablement"]["mutation_performed"] is False

    @pytest.mark.asyncio
    async def test_http_client_record_sdk_runtime_flag_application_preflight_calls_owner_gated_stub(self):
        """Test SDK runtime flag application preflight uses the backend evidence stub."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)
        payload = {
            "runtime_flag_preflight_id": "flag-preflight-1",
            "approval_id": "approval-1",
            "runtime_flag_enablement_id": "flag-enable-1",
            "runtime_flag_enablement_audit_id": "audit-flag-enable-1",
            "final_decision_id": "final-decision-1",
            "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
            "target_state": "enabled",
            "requested_by": "owner",
            "requested_at": "2026-06-08T00:00:00Z",
            "preflight_reason": "owner requested runtime flag application preflight",
            "rollback_plan_ref": "runbooks/sdk-write-runner-rollback.md",
            "smoke_runbook_ref": "runbooks/sdk-write-runner-smoke.md",
            "preflight_hash": "hash-flag-preflight-1",
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "status": "sdk_runtime_flag_application_preflight_workflow_ready",
            "runtime_flag_preflight": {
                "audit_event_recorded": True,
                "runtime_flag_enabled": False,
                "flag_application_performed": False,
                "implementation_enabled": False,
                "write_runner_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
        }

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_request:
            result = await client.record_sdk_runtime_flag_application_preflight(payload)

            call_args = mock_request.call_args
            assert call_args[0][0] == "POST"
            assert call_args[0][1] == "/api/v1/control-plane/sdk/runtime-flag/application-preflight/record"
            assert call_args[1]["json"] == payload
            assert result["status"] == "sdk_runtime_flag_application_preflight_workflow_ready"
            assert result["runtime_flag_preflight"]["runtime_flag_enabled"] is False
            assert result["runtime_flag_preflight"]["flag_application_performed"] is False
            assert result["runtime_flag_preflight"]["write_runner_enabled"] is False
            assert result["runtime_flag_preflight"]["runner_invoked"] is False
            assert result["runtime_flag_preflight"]["mutation_performed"] is False

    @pytest.mark.asyncio
    async def test_http_client_record_sdk_runtime_flag_application_owner_approval_calls_owner_gated_stub(self):
        """Test SDK runtime flag application owner approval uses the backend evidence stub."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)
        payload = {
            "runtime_flag_approval_id": "flag-approval-1",
            "approval_id": "approval-1",
            "runtime_flag_preflight_id": "flag-preflight-1",
            "runtime_flag_preflight_audit_id": "audit-flag-preflight-1",
            "runtime_flag_enablement_id": "flag-enable-1",
            "final_decision_id": "final-decision-1",
            "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
            "decision": "accepted",
            "decided_by": "owner",
            "decided_at": "2026-06-08T00:00:00Z",
            "approval_reason": "owner approved runtime flag application preflight",
            "approval_hash": "hash-flag-approval-1",
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "status": "sdk_runtime_flag_application_owner_approval_workflow_ready",
            "runtime_flag_approval": {
                "audit_event_recorded": True,
                "runtime_flag_enabled": False,
                "flag_application_performed": False,
                "implementation_enabled": False,
                "write_runner_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
        }

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_request:
            result = await client.record_sdk_runtime_flag_application_owner_approval(payload)

            call_args = mock_request.call_args
            assert call_args[0][0] == "POST"
            assert call_args[0][1] == "/api/v1/control-plane/sdk/runtime-flag/application-approval/record"
            assert call_args[1]["json"] == payload
            assert result["status"] == "sdk_runtime_flag_application_owner_approval_workflow_ready"
            assert result["runtime_flag_approval"]["runtime_flag_enabled"] is False
            assert result["runtime_flag_approval"]["flag_application_performed"] is False
            assert result["runtime_flag_approval"]["write_runner_enabled"] is False
            assert result["runtime_flag_approval"]["runner_invoked"] is False
            assert result["runtime_flag_approval"]["mutation_performed"] is False

    @pytest.mark.asyncio
    async def test_http_client_record_sdk_runtime_flag_application_execute_contract_calls_owner_gated_stub(self):
        """Test SDK runtime flag application execute contract uses the backend evidence stub."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)
        payload = {
            "runtime_flag_execute_contract_id": "flag-execute-contract-1",
            "approval_id": "approval-1",
            "runtime_flag_approval_id": "flag-approval-1",
            "runtime_flag_approval_audit_id": "audit-flag-approval-1",
            "runtime_flag_preflight_id": "flag-preflight-1",
            "runtime_flag_enablement_id": "flag-enable-1",
            "final_decision_id": "final-decision-1",
            "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
            "operator_id": "operator",
            "locked_at": "2026-06-08T00:00:00Z",
            "execute_contract_reason": "owner requested live runtime flag application contract",
            "idempotency_key": "idem-flag-execute-1",
            "idempotency_hash": "hash-idem-flag-execute-1",
            "rollback_plan_ref": "runbooks/sdk-write-runner-rollback.md",
            "smoke_runbook_ref": "runbooks/sdk-write-runner-smoke.md",
            "execute_contract_hash": "hash-flag-execute-contract-1",
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "status": "sdk_runtime_flag_application_execute_contract_workflow_ready",
            "runtime_flag_execute_contract": {
                "audit_event_recorded": True,
                "runtime_flag_enabled": False,
                "flag_application_performed": False,
                "implementation_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "adapter_execution_enabled": False,
                "agent_execution_enabled": False,
                "write_execution_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
        }

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_request:
            result = await client.record_sdk_runtime_flag_application_execute_contract(payload)

            call_args = mock_request.call_args
            assert call_args[0][0] == "POST"
            assert call_args[0][1] == "/api/v1/control-plane/sdk/runtime-flag/application-execute-contract/record"
            assert call_args[1]["json"] == payload
            assert result["status"] == "sdk_runtime_flag_application_execute_contract_workflow_ready"
            assert result["runtime_flag_execute_contract"]["runtime_flag_enabled"] is False
            assert result["runtime_flag_execute_contract"]["flag_application_performed"] is False
            assert result["runtime_flag_execute_contract"]["execute_enabled"] is False
            assert result["runtime_flag_execute_contract"]["write_runner_enabled"] is False
            assert result["runtime_flag_execute_contract"]["runner_invoked"] is False
            assert result["runtime_flag_execute_contract"]["mutation_performed"] is False

    @pytest.mark.asyncio
    async def test_http_client_record_sdk_runtime_flag_application_readiness_plan_decision_calls_owner_gated_stub(self):
        """Test SDK runtime flag readiness plan decision uses the backend evidence stub."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)
        payload = {
            "readiness_plan_decision_id": "readiness-plan-decision-1",
            "approval_id": "approval-1",
            "runtime_flag_execute_contract_id": "flag-execute-contract-1",
            "runtime_flag_execute_contract_audit_id": "audit-flag-execute-contract-1",
            "runtime_flag_approval_id": "flag-approval-1",
            "runtime_flag_preflight_id": "flag-preflight-1",
            "runtime_flag_enablement_id": "flag-enable-1",
            "final_decision_id": "final-decision-1",
            "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
            "decision": "accepted",
            "decided_by": "owner",
            "decided_at": "2026-06-08T00:00:00Z",
            "reason": "owner accepted readiness plan",
            "decision_hash": "hash-readiness-plan-decision-1",
            "dry_run": True,
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "status": "sdk_live_runtime_flag_application_readiness_plan_decision_workflow_ready",
            "readiness_plan_decision": {
                "audit_event_recorded": True,
                "runtime_flag_enabled": False,
                "flag_application_performed": False,
                "implementation_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "adapter_execution_enabled": False,
                "agent_execution_enabled": False,
                "write_execution_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
        }

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_request:
            result = await client.record_sdk_runtime_flag_application_readiness_plan_decision(payload)

            call_args = mock_request.call_args
            assert call_args[0][0] == "POST"
            assert call_args[0][1] == (
                "/api/v1/control-plane/sdk/runtime-flag/application-readiness-plan/decision/record"
            )
            assert call_args[1]["json"] == payload
            assert result["status"] == "sdk_live_runtime_flag_application_readiness_plan_decision_workflow_ready"
            assert result["readiness_plan_decision"]["runtime_flag_enabled"] is False
            assert result["readiness_plan_decision"]["flag_application_performed"] is False
            assert result["readiness_plan_decision"]["execute_enabled"] is False
            assert result["readiness_plan_decision"]["write_runner_enabled"] is False
            assert result["readiness_plan_decision"]["runner_invoked"] is False
            assert result["readiness_plan_decision"]["mutation_performed"] is False

    @pytest.mark.asyncio
    async def test_http_client_record_sdk_runtime_flag_application_adapter_implementation_request_calls_owner_gated_stub(self):
        """Test SDK runtime flag adapter implementation request uses the backend evidence stub."""
        config = CLIConfig(api_base_url="http://localhost:8000")
        client = HTTPClient(config)
        payload = {
            "adapter_implementation_request_id": "adapter-implementation-request-1",
            "approval_id": "approval-1",
            "readiness_plan_decision_id": "readiness-plan-decision-1",
            "readiness_plan_decision_audit_id": "audit-readiness-plan-decision-1",
            "runtime_flag_execute_contract_id": "flag-execute-contract-1",
            "runtime_flag_approval_id": "flag-approval-1",
            "runtime_flag_preflight_id": "flag-preflight-1",
            "runtime_flag_enablement_id": "flag-enable-1",
            "final_decision_id": "final-decision-1",
            "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
            "requested_by": "owner",
            "requested_at": "2026-06-08T00:00:00Z",
            "implementation_request_reason": "owner requested adapter implementation",
            "adapter_design_ref": "docs/runbooks/sdk-write-runner-runtime-flag-adapter-design.md",
            "rollback_plan_ref": "docs/runbooks/sdk-write-runner-rollback.md",
            "smoke_runbook_ref": "docs/runbooks/sdk-write-runner-smoke.md",
            "request_hash": "hash-adapter-implementation-request-1",
            "dry_run": True,
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "status": "sdk_live_runtime_flag_application_adapter_implementation_request_workflow_ready",
            "adapter_implementation_request": {
                "audit_event_recorded": True,
                "runtime_flag_enabled": False,
                "flag_application_performed": False,
                "implementation_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "adapter_execution_enabled": False,
                "agent_execution_enabled": False,
                "write_execution_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
                "adapter_import_allowed": False,
                "adapter_execution_allowed": False,
            },
        }

        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_request:
            result = await client.record_sdk_runtime_flag_application_adapter_implementation_request(payload)

            call_args = mock_request.call_args
            assert call_args[0][0] == "POST"
            assert call_args[0][1] == (
                "/api/v1/control-plane/sdk/runtime-flag/application-adapter/implementation-request/record"
            )
            assert call_args[1]["json"] == payload
            assert result["status"] == (
                "sdk_live_runtime_flag_application_adapter_implementation_request_workflow_ready"
            )
            assert result["adapter_implementation_request"]["runtime_flag_enabled"] is False
            assert result["adapter_implementation_request"]["flag_application_performed"] is False
            assert result["adapter_implementation_request"]["implementation_enabled"] is False
            assert result["adapter_implementation_request"]["execute_enabled"] is False
            assert result["adapter_implementation_request"]["write_runner_enabled"] is False
            assert result["adapter_implementation_request"]["adapter_execution_enabled"] is False
            assert result["adapter_implementation_request"]["runner_invoked"] is False
            assert result["adapter_implementation_request"]["mutation_performed"] is False
            assert result["adapter_implementation_request"]["adapter_import_allowed"] is False
            assert result["adapter_implementation_request"]["adapter_execution_allowed"] is False

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
    async def test_local_client_record_sdk_runtime_enablement_receipt_not_implemented(self):
        """Test SDK runtime enablement receipt recording is HTTP-only."""
        config = CLIConfig(mode="local")
        client = LocalClient(config)

        with pytest.raises(NotImplementedError, match="SDK runtime enablement receipt recording"):
            await client.record_sdk_runtime_enablement_receipt({"approval_id": "approval-1"})

    @pytest.mark.asyncio
    async def test_local_client_record_sdk_runtime_enablement_owner_pack_decision_not_implemented(self):
        """Test SDK runtime enablement owner pack decision recording is HTTP-only."""
        config = CLIConfig(mode="local")
        client = LocalClient(config)

        with pytest.raises(NotImplementedError, match="SDK runtime enablement owner pack decision recording"):
            await client.record_sdk_runtime_enablement_owner_pack_decision({"approval_id": "approval-1"})

    @pytest.mark.asyncio
    async def test_local_client_record_sdk_runtime_implementation_readiness_lock_not_implemented(self):
        """Test SDK runtime implementation readiness lock recording is HTTP-only."""
        config = CLIConfig(mode="local")
        client = LocalClient(config)

        with pytest.raises(NotImplementedError, match="SDK runtime implementation readiness lock recording"):
            await client.record_sdk_runtime_implementation_readiness_lock({"approval_id": "approval-1"})

    @pytest.mark.asyncio
    async def test_local_client_record_sdk_runtime_implementation_final_decision_not_implemented(self):
        """Test SDK runtime implementation final decision recording is HTTP-only."""
        config = CLIConfig(mode="local")
        client = LocalClient(config)

        with pytest.raises(NotImplementedError, match="SDK runtime implementation final decision recording"):
            await client.record_sdk_runtime_implementation_final_decision({"approval_id": "approval-1"})

    @pytest.mark.asyncio
    async def test_local_client_record_sdk_runtime_flag_enablement_not_implemented(self):
        """Test SDK runtime flag enablement recording is HTTP-only."""
        config = CLIConfig(mode="local")
        client = LocalClient(config)

        with pytest.raises(NotImplementedError, match="SDK runtime flag enablement recording"):
            await client.record_sdk_runtime_flag_enablement({"approval_id": "approval-1"})

    @pytest.mark.asyncio
    async def test_local_client_record_sdk_runtime_flag_application_preflight_not_implemented(self):
        """Test SDK runtime flag application preflight recording is HTTP-only."""
        config = CLIConfig(mode="local")
        client = LocalClient(config)

        with pytest.raises(NotImplementedError, match="SDK runtime flag application preflight recording"):
            await client.record_sdk_runtime_flag_application_preflight({"approval_id": "approval-1"})

    @pytest.mark.asyncio
    async def test_local_client_record_sdk_runtime_flag_application_owner_approval_not_implemented(self):
        """Test SDK runtime flag application owner approval recording is HTTP-only."""
        config = CLIConfig(mode="local")
        client = LocalClient(config)

        with pytest.raises(NotImplementedError, match="SDK runtime flag application owner approval recording"):
            await client.record_sdk_runtime_flag_application_owner_approval({"approval_id": "approval-1"})

    @pytest.mark.asyncio
    async def test_local_client_record_sdk_runtime_flag_application_execute_contract_not_implemented(self):
        """Test SDK runtime flag application execute contract recording is HTTP-only."""
        config = CLIConfig(mode="local")
        client = LocalClient(config)

        with pytest.raises(NotImplementedError, match="SDK runtime flag application execute contract recording"):
            await client.record_sdk_runtime_flag_application_execute_contract({"approval_id": "approval-1"})

    @pytest.mark.asyncio
    async def test_local_client_record_sdk_runtime_flag_application_readiness_plan_decision_not_implemented(self):
        """Test SDK runtime flag readiness plan decision recording is HTTP-only."""
        config = CLIConfig(mode="local")
        client = LocalClient(config)

        with pytest.raises(NotImplementedError, match="SDK runtime flag application readiness plan decision recording"):
            await client.record_sdk_runtime_flag_application_readiness_plan_decision({"approval_id": "approval-1"})

    @pytest.mark.asyncio
    async def test_local_client_record_sdk_runtime_flag_application_adapter_implementation_request_not_implemented(self):
        """Test SDK runtime flag adapter implementation request recording is HTTP-only."""
        config = CLIConfig(mode="local")
        client = LocalClient(config)

        with pytest.raises(
            NotImplementedError,
            match="SDK runtime flag application adapter implementation request recording",
        ):
            await client.record_sdk_runtime_flag_application_adapter_implementation_request({"approval_id": "approval-1"})

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
