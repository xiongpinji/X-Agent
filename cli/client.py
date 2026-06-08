"""CLI client abstraction layer.

Provides unified interface for both HTTP-based remote API calls and local
direct module imports. All clients implement BaseClient interface.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx

from cli.config import CLIConfig

logger = logging.getLogger("xagent.cli.client")


class XAgentCLIError(Exception):
    """Base exception for CLI errors."""

    pass


class ConnectionError(XAgentCLIError):
    """Raised when unable to connect to API or backend."""

    pass


class AuthError(XAgentCLIError):
    """Raised when authentication fails."""

    pass


class APIError(XAgentCLIError):
    """Raised when API returns an error."""

    pass


class BaseClient(ABC):
    """Abstract base class defining unified client interface.

    All client implementations (HTTP, Local) must implement these methods
    with identical signatures and return types to ensure compatibility.
    """

    @abstractmethod
    async def run_agent(
        self,
        task: str,
        permission_scope: list[str] | None = None,
        extra_context: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Run an agent with the given task.

        Args:
            task: Task description (required)
            permission_scope: List of permission scopes
            extra_context: Additional context dictionary
            stream: Whether to stream results

        Returns:
            Dictionary with run result

        Raises:
            ConnectionError: If unable to connect
            AuthError: If authentication fails
            APIError: If API returns error
        """
        pass

    @abstractmethod
    async def list_agents(self) -> dict[str, Any]:
        """List all available agents.

        Returns:
            Dictionary with agents list

        Raises:
            ConnectionError: If unable to connect
            AuthError: If authentication fails
            APIError: If API returns error
        """
        pass

    @abstractmethod
    async def list_tools(self) -> list[dict[str, Any]]:
        """List all available tools.

        Returns:
            List of tool manifest dictionaries

        Raises:
            ConnectionError: If unable to connect
            AuthError: If authentication fails
            APIError: If API returns error
        """
        pass

    @abstractmethod
    async def list_workflows(self) -> list[dict[str, Any]]:
        """List all workflows.

        Returns:
            List of workflow dictionaries

        Raises:
            ConnectionError: If unable to connect
            AuthError: If authentication fails
            APIError: If API returns error
        """
        pass

    @abstractmethod
    async def create_workflow(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Create a new workflow.

        Args:
            spec: Workflow specification dictionary

        Returns:
            Created workflow dictionary

        Raises:
            ConnectionError: If unable to connect
            AuthError: If authentication fails
            APIError: If API returns error
        """
        pass

    @abstractmethod
    async def run_workflow(
        self,
        workflow_id: str,
        inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run a workflow.

        Args:
            workflow_id: ID of workflow to run
            inputs: Input parameters for workflow

        Returns:
            Workflow run result dictionary

        Raises:
            ConnectionError: If unable to connect
            AuthError: If authentication fails
            APIError: If API returns error
        """
        pass

    @abstractmethod
    async def get_workflow_status(self, workflow_id: str) -> dict[str, Any]:
        """Get workflow status.

        Args:
            workflow_id: ID of workflow

        Returns:
            Workflow status dictionary

        Raises:
            ConnectionError: If unable to connect
            AuthError: If authentication fails
            APIError: If API returns error
        """
        pass

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Check backend health.

        Returns:
            Health status dictionary

        Raises:
            ConnectionError: If unable to connect
        """
        pass

    @abstractmethod
    async def list_approvals(
        self,
        status: str | None = None,
        tenant_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List approval requests.

        Args:
            status: Optional status filter (pending/approved/rejected/executed)
            tenant_id: Optional tenant filter
            limit: Maximum number of records to return

        Returns:
            List of approval request dictionaries

        Raises:
            ConnectionError: If unable to connect
            AuthError: If authentication fails
            APIError: If API returns error
        """
        pass

    @abstractmethod
    async def get_approval(self, approval_id: str) -> dict[str, Any]:
        """Get a single approval request by id.

        Args:
            approval_id: Approval request identifier

        Returns:
            Approval request dictionary

        Raises:
            ConnectionError: If unable to connect
            AuthError: If authentication fails
            APIError: If API returns error (including 404)
        """
        pass

    @abstractmethod
    async def approve_request(
        self,
        approval_id: str,
        decided_by: str = "anonymous",
        reason: str = "",
    ) -> dict[str, Any]:
        """Approve a pending approval request.

        Args:
            approval_id: Approval request identifier
            decided_by: Identity of the approver
            reason: Optional decision reason

        Returns:
            Updated approval request dictionary

        Raises:
            ConnectionError: If unable to connect
            AuthError: If authentication fails
            APIError: If API returns error (including 404)
        """
        pass

    @abstractmethod
    async def reject_request(
        self,
        approval_id: str,
        decided_by: str = "anonymous",
        reason: str = "",
    ) -> dict[str, Any]:
        """Reject a pending approval request.

        Args:
            approval_id: Approval request identifier
            decided_by: Identity of the approver
            reason: Optional decision reason

        Returns:
            Updated approval request dictionary

        Raises:
            ConnectionError: If unable to connect
            AuthError: If authentication fails
            APIError: If API returns error (including 404)
        """
        pass

    @abstractmethod
    async def execute_approved(self, approval_id: str) -> dict[str, Any]:
        """Execute a tool whose approval has been granted.

        Args:
            approval_id: Approval request identifier (must be approved)

        Returns:
            Tool call record dictionary

        Raises:
            ConnectionError: If unable to connect
            AuthError: If authentication fails
            APIError: If API returns error (including 404)
        """
        pass

    @abstractmethod
    async def invoke_sdk_contract(self, contract: dict[str, Any]) -> dict[str, Any]:
        """Invoke an SDK control-plane contract through the backend stub.

        Args:
            contract: SDK envelope produced by ``ControlPlaneSDK``.

        Returns:
            Backend SDK invoke response dictionary.

        Raises:
            ConnectionError: If unable to connect
            AuthError: If authentication fails
            APIError: If API returns error
        """
        pass

    @abstractmethod
    async def record_sdk_owner_acceptance(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK owner acceptance evidence through the backend stub."""
        pass

    @abstractmethod
    async def record_sdk_runtime_enablement_receipt(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK runtime enablement readiness receipt through the backend stub."""
        pass

    @abstractmethod
    async def record_sdk_runtime_enablement_owner_pack_decision(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK runtime enablement owner pack decision through the backend stub."""
        pass

    @abstractmethod
    async def record_sdk_runtime_implementation_readiness_lock(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK runtime implementation readiness lock through the backend stub."""
        pass

    @abstractmethod
    async def record_sdk_runtime_implementation_final_decision(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK runtime implementation final decision through the backend stub."""
        pass

    @abstractmethod
    async def record_sdk_runtime_flag_enablement(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK runtime flag enablement intent through the backend stub."""
        pass

    @abstractmethod
    async def record_sdk_runtime_flag_application_preflight(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK runtime flag application preflight through the backend stub."""
        pass

    @abstractmethod
    async def record_sdk_runtime_flag_application_owner_approval(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK runtime flag application owner approval through the backend stub."""
        pass

    @abstractmethod
    async def record_sdk_runtime_flag_application_execute_contract(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK runtime flag application execute contract through the backend stub."""
        pass

    @abstractmethod
    async def record_sdk_runtime_flag_application_readiness_plan_decision(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Record SDK runtime flag readiness plan owner decision through the backend stub."""
        pass

    @abstractmethod
    async def record_sdk_runtime_flag_application_adapter_implementation_request(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Record SDK runtime flag adapter implementation request through the backend stub."""
        pass

    @abstractmethod
    async def record_sdk_runtime_flag_application_adapter_design_review(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Record SDK runtime flag adapter design review through the backend stub."""
        pass


class HTTPClient(BaseClient):
    """HTTP-based client for remote API calls.

    Communicates with X-Agent backend via HTTP/HTTPS using httpx.
    Handles authentication via x-api-key header and error handling.
    """

    def __init__(self, config: CLIConfig) -> None:
        """Initialize HTTP client.

        Args:
            config: CLI configuration
        """
        self.config = config
        self.base_url = config.api_base_url.rstrip("/")
        self.api_key = config.api_key
        self.timeout = config.timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client.

        Returns:
            httpx.AsyncClient instance
        """
        if self._client is None:
            headers = {}
            if self.api_key:
                headers["x-api-key"] = self.api_key
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client connection."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make HTTP request with error handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (without base URL)
            **kwargs: Additional arguments for httpx

        Returns:
            Response JSON as dictionary

        Raises:
            ConnectionError: If connection fails
            AuthError: If authentication fails
            APIError: If API returns error
        """
        client = await self._get_client()
        try:
            response = await client.request(method, path, **kwargs)
        except httpx.ConnectError as e:
            raise ConnectionError(f"Failed to connect to {self.base_url}: {e}") from e
        except httpx.TimeoutException as e:
            raise ConnectionError(f"Request timeout: {e}") from e

        if response.status_code == 401:
            raise AuthError("Authentication failed: invalid or missing API key")
        if response.status_code == 403:
            raise AuthError("Authorization failed: insufficient permissions")

        if response.status_code >= 400:
            try:
                error_data = response.json()
                detail = error_data.get("detail", "Unknown error")
            except Exception:
                detail = response.text or f"HTTP {response.status_code}"
            raise APIError(f"API error: {detail}")

        try:
            return response.json()
        except Exception as e:
            raise APIError(f"Failed to parse response: {e}") from e

    async def run_agent(
        self,
        task: str,
        permission_scope: list[str] | None = None,
        extra_context: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Run an agent via HTTP API.

        POST /api/v1/agents/run
        """
        payload = {
            "task": task,
            "permission_scope": permission_scope or [],
            "extra_context": extra_context or {},
            "stream": stream,
        }
        return await self._request("POST", "/api/v1/agents/run", json=payload)

    async def list_agents(self) -> dict[str, Any]:
        """List agents via HTTP API.

        GET /api/v1/agents
        """
        return await self._request("GET", "/api/v1/agents")

    async def list_tools(self) -> list[dict[str, Any]]:
        """List tools via HTTP API.

        GET /api/v1/tools
        """
        result = await self._request("GET", "/api/v1/tools")
        return result if isinstance(result, list) else result.get("data", [])

    async def list_workflows(self) -> list[dict[str, Any]]:
        """List workflows via HTTP API.

        GET /api/v1/workflows
        """
        result = await self._request("GET", "/api/v1/workflows")
        return result if isinstance(result, list) else result.get("data", [])

    async def create_workflow(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Create workflow via HTTP API.

        POST /api/v1/workflows
        """
        return await self._request("POST", "/api/v1/workflows", json=spec)

    async def run_workflow(
        self,
        workflow_id: str,
        inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run workflow via HTTP API.

        POST /api/v1/workflows/{workflow_id}/run
        """
        payload = {"inputs": inputs or {}}
        return await self._request(
            "POST",
            f"/api/v1/workflows/{workflow_id}/run",
            json=payload,
        )

    async def get_workflow_status(self, workflow_id: str) -> dict[str, Any]:
        """Get workflow status via HTTP API.

        GET /api/v1/workflows/{workflow_id}/status
        """
        return await self._request("GET", f"/api/v1/workflows/{workflow_id}/status")

    async def health_check(self) -> dict[str, Any]:
        """Check backend health via HTTP API.

        GET /health
        """
        try:
            return await self._request("GET", "/health")
        except (ConnectionError, APIError) as e:
            return {"status": "unhealthy", "error": str(e)}

    async def list_approvals(
        self,
        status: str | None = None,
        tenant_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List approvals via HTTP API.

        GET /api/v1/approvals
        """
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        if tenant_id:
            params["tenant_id"] = tenant_id
        result = await self._request("GET", "/api/v1/approvals", params=params)
        return result if isinstance(result, list) else result.get("data", [])

    async def get_approval(self, approval_id: str) -> dict[str, Any]:
        """Get a single approval via HTTP API.

        GET /api/v1/approvals/{approval_id}
        """
        return await self._request("GET", f"/api/v1/approvals/{approval_id}")

    async def approve_request(
        self,
        approval_id: str,
        decided_by: str = "anonymous",
        reason: str = "",
    ) -> dict[str, Any]:
        """Approve an approval request via HTTP API.

        POST /api/v1/approvals/{approval_id}/approve
        """
        payload = {"decided_by": decided_by, "reason": reason}
        return await self._request(
            "POST", f"/api/v1/approvals/{approval_id}/approve", json=payload
        )

    async def reject_request(
        self,
        approval_id: str,
        decided_by: str = "anonymous",
        reason: str = "",
    ) -> dict[str, Any]:
        """Reject an approval request via HTTP API.

        POST /api/v1/approvals/{approval_id}/reject
        """
        payload = {"decided_by": decided_by, "reason": reason}
        return await self._request(
            "POST", f"/api/v1/approvals/{approval_id}/reject", json=payload
        )

    async def execute_approved(self, approval_id: str) -> dict[str, Any]:
        """Execute an approved tool via HTTP API.

        POST /api/v1/approvals/{approval_id}/execute
        """
        return await self._request(
            "POST", f"/api/v1/approvals/{approval_id}/execute"
        )

    async def invoke_sdk_contract(self, contract: dict[str, Any]) -> dict[str, Any]:
        """Invoke SDK envelope through the owner-gated control-plane stub.

        POST /api/v1/control-plane/sdk/invoke
        """
        return await self._request(
            "POST",
            "/api/v1/control-plane/sdk/invoke",
            json=contract,
        )

    async def record_sdk_owner_acceptance(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK owner acceptance evidence without executing the runner.

        POST /api/v1/control-plane/sdk/owner-acceptance/record
        """
        return await self._request(
            "POST",
            "/api/v1/control-plane/sdk/owner-acceptance/record",
            json=payload,
        )

    async def record_sdk_runtime_enablement_receipt(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK runtime enablement readiness receipt without executing the runner.

        POST /api/v1/control-plane/sdk/runtime-enablement/receipt/record
        """
        return await self._request(
            "POST",
            "/api/v1/control-plane/sdk/runtime-enablement/receipt/record",
            json=payload,
        )

    async def record_sdk_runtime_enablement_owner_pack_decision(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK runtime enablement owner pack decision without executing the runner.

        POST /api/v1/control-plane/sdk/runtime-enablement/owner-pack/decision/record
        """
        return await self._request(
            "POST",
            "/api/v1/control-plane/sdk/runtime-enablement/owner-pack/decision/record",
            json=payload,
        )

    async def record_sdk_runtime_implementation_readiness_lock(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK runtime implementation readiness lock without executing the runner.

        POST /api/v1/control-plane/sdk/runtime-implementation/readiness-lock/record
        """
        return await self._request(
            "POST",
            "/api/v1/control-plane/sdk/runtime-implementation/readiness-lock/record",
            json=payload,
        )

    async def record_sdk_runtime_implementation_final_decision(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK runtime implementation final decision without executing the runner.

        POST /api/v1/control-plane/sdk/runtime-implementation/final-decision/record
        """
        return await self._request(
            "POST",
            "/api/v1/control-plane/sdk/runtime-implementation/final-decision/record",
            json=payload,
        )

    async def record_sdk_runtime_flag_enablement(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK runtime flag enablement intent without enabling the flag.

        POST /api/v1/control-plane/sdk/runtime-flag/enablement/record
        """
        return await self._request(
            "POST",
            "/api/v1/control-plane/sdk/runtime-flag/enablement/record",
            json=payload,
        )

    async def record_sdk_runtime_flag_application_preflight(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK runtime flag application preflight without applying the flag.

        POST /api/v1/control-plane/sdk/runtime-flag/application-preflight/record
        """
        return await self._request(
            "POST",
            "/api/v1/control-plane/sdk/runtime-flag/application-preflight/record",
            json=payload,
        )

    async def record_sdk_runtime_flag_application_owner_approval(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK runtime flag application owner approval without applying the flag.

        POST /api/v1/control-plane/sdk/runtime-flag/application-approval/record
        """
        return await self._request(
            "POST",
            "/api/v1/control-plane/sdk/runtime-flag/application-approval/record",
            json=payload,
        )

    async def record_sdk_runtime_flag_application_execute_contract(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK runtime flag application execute contract without applying the flag.

        POST /api/v1/control-plane/sdk/runtime-flag/application-execute-contract/record
        """
        return await self._request(
            "POST",
            "/api/v1/control-plane/sdk/runtime-flag/application-execute-contract/record",
            json=payload,
        )

    async def record_sdk_runtime_flag_application_readiness_plan_decision(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Record SDK runtime flag readiness plan owner decision without applying the flag.

        POST /api/v1/control-plane/sdk/runtime-flag/application-readiness-plan/decision/record
        """
        return await self._request(
            "POST",
            "/api/v1/control-plane/sdk/runtime-flag/application-readiness-plan/decision/record",
            json=payload,
        )

    async def record_sdk_runtime_flag_application_adapter_implementation_request(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Record SDK runtime flag adapter implementation request without enabling the adapter.

        POST /api/v1/control-plane/sdk/runtime-flag/application-adapter/implementation-request/record
        """
        return await self._request(
            "POST",
            "/api/v1/control-plane/sdk/runtime-flag/application-adapter/implementation-request/record",
            json=payload,
        )

    async def record_sdk_runtime_flag_application_adapter_design_review(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Record SDK runtime flag adapter design review without enabling the adapter.

        POST /api/v1/control-plane/sdk/runtime-flag/application-adapter/design-review/record
        """
        return await self._request(
            "POST",
            "/api/v1/control-plane/sdk/runtime-flag/application-adapter/design-review/record",
            json=payload,
        )


class LocalClient(BaseClient):
    """Local client for direct backend module imports.

    Directly imports and uses backend core modules without HTTP overhead.
    Useful for development and testing.

    Note: Some operations may not be fully supported in local mode.
    """

    def __init__(self, config: CLIConfig) -> None:
        """Initialize local client.

        Args:
            config: CLI configuration
        """
        self.config = config
        self._agent: Any = None
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Initialize backend dependencies.

        Raises:
            ConnectionError: If initialization fails
        """
        if self._initialized:
            return

        try:
            from backend.app.dependencies import get_agent

            self._agent = get_agent()
            self._initialized = True
        except Exception as e:
            raise ConnectionError(
                f"Failed to initialize local backend: {e}"
            ) from e

    async def run_agent(
        self,
        task: str,
        permission_scope: list[str] | None = None,
        extra_context: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Run agent locally.

        Note: Streaming not supported in local mode.
        """
        await self._ensure_initialized()
        if self._agent is None:
            raise ConnectionError("Agent not initialized")

        try:
            result = await self._agent.run(
                task=task,
                permission_scope=permission_scope or [],
                extra_context=extra_context or {},
            )
            return {
                "task": task,
                "result": result,
                "mode": "local",
            }
        except Exception as e:
            raise APIError(f"Agent execution failed: {e}") from e

    async def list_agents(self) -> dict[str, Any]:
        """List agents locally.

        Returns mock agent list for local mode.
        """
        await self._ensure_initialized()
        return {
            "data": [
                {
                    "id": "local-agent",
                    "name": "Local Agent",
                    "status": "active",
                    "mode": "local",
                }
            ]
        }

    async def list_tools(self) -> list[dict[str, Any]]:
        """List tools locally.

        Note: Returns placeholder. Full implementation requires
        backend tool registry access.
        """
        await self._ensure_initialized()
        raise NotImplementedError(
            "Tool listing not yet supported in local mode. "
            "Use HTTP mode to access tool manifest."
        )

    async def list_workflows(self) -> list[dict[str, Any]]:
        """List workflows locally.

        Note: Returns placeholder. Full implementation requires
        backend workflow repository access.
        """
        await self._ensure_initialized()
        raise NotImplementedError(
            "Workflow listing not yet supported in local mode. "
            "Use HTTP mode to access workflow repository."
        )

    async def create_workflow(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Create workflow locally.

        Note: Not supported in local mode.
        """
        raise NotImplementedError(
            "Workflow creation not supported in local mode. "
            "Use HTTP mode to create workflows."
        )

    async def run_workflow(
        self,
        workflow_id: str,
        inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run workflow locally.

        Note: Not supported in local mode.
        """
        raise NotImplementedError(
            "Workflow execution not supported in local mode. "
            "Use HTTP mode to run workflows."
        )

    async def get_workflow_status(self, workflow_id: str) -> dict[str, Any]:
        """Get workflow status locally.

        Note: Not supported in local mode.
        """
        raise NotImplementedError(
            "Workflow status not supported in local mode. "
            "Use HTTP mode to check workflow status."
        )

    async def health_check(self) -> dict[str, Any]:
        """Check local backend health."""
        try:
            await self._ensure_initialized()
            return {"status": "healthy", "mode": "local"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e), "mode": "local"}

    async def list_approvals(
        self,
        status: str | None = None,
        tenant_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List approvals locally.

        Note: Not supported in local mode; approvals are backend state.
        """
        raise NotImplementedError(
            "Approval listing not supported in local mode. "
            "Use HTTP mode to access approval requests."
        )

    async def get_approval(self, approval_id: str) -> dict[str, Any]:
        """Get approval locally.

        Note: Not supported in local mode.
        """
        raise NotImplementedError(
            "Approval lookup not supported in local mode. "
            "Use HTTP mode to access approval requests."
        )

    async def approve_request(
        self,
        approval_id: str,
        decided_by: str = "anonymous",
        reason: str = "",
    ) -> dict[str, Any]:
        """Approve locally.

        Note: Not supported in local mode.
        """
        raise NotImplementedError(
            "Approval decisions not supported in local mode. "
            "Use HTTP mode to approve requests."
        )

    async def reject_request(
        self,
        approval_id: str,
        decided_by: str = "anonymous",
        reason: str = "",
    ) -> dict[str, Any]:
        """Reject locally.

        Note: Not supported in local mode.
        """
        raise NotImplementedError(
            "Approval decisions not supported in local mode. "
            "Use HTTP mode to reject requests."
        )

    async def execute_approved(self, approval_id: str) -> dict[str, Any]:
        """Execute approved tool locally.

        Note: Not supported in local mode.
        """
        raise NotImplementedError(
            "Approved execution not supported in local mode. "
            "Use HTTP mode to execute approved tools."
        )

    async def invoke_sdk_contract(self, contract: dict[str, Any]) -> dict[str, Any]:
        """Invoke SDK envelope locally.

        SDK backend invocation is HTTP-only so it stays behind the API audit
        and approval/sandbox/admin contract.
        """
        raise NotImplementedError(
            "SDK backend invocation is not supported in local mode. "
            "Use HTTP mode to call the owner-gated control-plane stub."
        )

    async def record_sdk_owner_acceptance(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK owner acceptance locally.

        Owner acceptance evidence recording is HTTP-only so it stays behind
        the API audit and approval/sandbox/admin contract.
        """
        raise NotImplementedError(
            "SDK owner acceptance recording is not supported in local mode. "
            "Use HTTP mode to call the owner-gated control-plane stub."
        )

    async def record_sdk_runtime_enablement_receipt(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK runtime enablement readiness locally.

        Runtime enablement readiness recording is HTTP-only so it stays behind
        the API audit and approval/sandbox/admin contract.
        """
        raise NotImplementedError(
            "SDK runtime enablement receipt recording is not supported in local mode. "
            "Use HTTP mode to call the owner-gated control-plane stub."
        )

    async def record_sdk_runtime_enablement_owner_pack_decision(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK runtime enablement owner pack decision locally.

        Owner pack decision recording is HTTP-only so it stays behind
        the API audit and approval/sandbox/admin contract.
        """
        raise NotImplementedError(
            "SDK runtime enablement owner pack decision recording is not supported in local mode. "
            "Use HTTP mode to call the owner-gated control-plane stub."
        )

    async def record_sdk_runtime_implementation_readiness_lock(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK runtime implementation readiness lock locally.

        Runtime implementation readiness lock recording is HTTP-only so it
        stays behind the API audit and approval/sandbox/admin contract.
        """
        raise NotImplementedError(
            "SDK runtime implementation readiness lock recording is not supported in local mode. "
            "Use HTTP mode to call the owner-gated control-plane stub."
        )

    async def record_sdk_runtime_implementation_final_decision(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK runtime implementation final decision locally.

        Runtime implementation final decision recording is HTTP-only so it
        stays behind the API audit and approval/sandbox/admin contract.
        """
        raise NotImplementedError(
            "SDK runtime implementation final decision recording is not supported in local mode. "
            "Use HTTP mode to call the owner-gated control-plane stub."
        )

    async def record_sdk_runtime_flag_enablement(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK runtime flag enablement intent locally.

        Runtime flag enablement intent recording is HTTP-only so it stays
        behind the API audit and approval/sandbox/admin contract.
        """
        raise NotImplementedError(
            "SDK runtime flag enablement recording is not supported in local mode. "
            "Use HTTP mode to call the owner-gated control-plane stub."
        )

    async def record_sdk_runtime_flag_application_preflight(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK runtime flag application preflight locally.

        Runtime flag application preflight recording is HTTP-only so it stays
        behind the API audit and approval/sandbox/admin contract.
        """
        raise NotImplementedError(
            "SDK runtime flag application preflight recording is not supported in local mode. "
            "Use HTTP mode to call the owner-gated control-plane stub."
        )

    async def record_sdk_runtime_flag_application_owner_approval(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK runtime flag application owner approval locally.

        Runtime flag application owner approval recording is HTTP-only so it
        stays behind the API audit and approval/sandbox/admin contract.
        """
        raise NotImplementedError(
            "SDK runtime flag application owner approval recording is not supported in local mode. "
            "Use HTTP mode to call the owner-gated control-plane stub."
        )

    async def record_sdk_runtime_flag_application_execute_contract(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record SDK runtime flag application execute contract locally.

        Runtime flag application execute contract recording is HTTP-only so it
        stays behind the API audit and approval/sandbox/admin contract.
        """
        raise NotImplementedError(
            "SDK runtime flag application execute contract recording is not supported in local mode. "
            "Use HTTP mode to call the owner-gated control-plane stub."
        )

    async def record_sdk_runtime_flag_application_readiness_plan_decision(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Record SDK runtime flag readiness plan owner decision locally.

        Runtime flag readiness plan owner decision recording is HTTP-only so it
        stays behind the API audit and approval/sandbox/admin contract.
        """
        raise NotImplementedError(
            "SDK runtime flag application readiness plan decision recording is not supported in local mode. "
            "Use HTTP mode to call the owner-gated control-plane stub."
        )

    async def record_sdk_runtime_flag_application_adapter_implementation_request(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Record SDK runtime flag adapter implementation request locally.

        Runtime flag adapter implementation request recording is HTTP-only so it
        stays behind the API audit and approval/sandbox/admin contract.
        """
        raise NotImplementedError(
            "SDK runtime flag application adapter implementation request recording is not supported in local mode. "
            "Use HTTP mode to call the owner-gated control-plane stub."
        )

    async def record_sdk_runtime_flag_application_adapter_design_review(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Record SDK runtime flag adapter design review locally.

        Runtime flag adapter design review recording is HTTP-only so it
        stays behind the API audit and approval/sandbox/admin contract.
        """
        raise NotImplementedError(
            "SDK runtime flag application adapter design review recording is not supported in local mode. "
            "Use HTTP mode to call the owner-gated control-plane stub."
        )


def create_client(config: CLIConfig) -> BaseClient:
    """Factory function to create appropriate client.

    Args:
        config: CLI configuration

    Returns:
        HTTPClient if mode is 'http', LocalClient if mode is 'local'

    Raises:
        ValueError: If mode is invalid
    """
    if config.mode == "http":
        return HTTPClient(config)
    elif config.mode == "local":
        return LocalClient(config)
    else:
        raise ValueError(f"Invalid client mode: {config.mode}")
