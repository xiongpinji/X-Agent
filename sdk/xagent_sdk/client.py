"""Synchronous client for X-Agent SDK."""

import json
from typing import Any, Dict, Optional

import httpx

from xagent_sdk.exceptions import (
    AuthenticationError,
    ConnectionError,
    RateLimitError,
    ServerError,
    ServiceUnavailableError,
    TaskNotFoundError,
    TimeoutError,
    ValidationError,
    XAgentError,
)
from xagent_sdk.models import AgentResponse, HealthStatus, Task, TaskResult, TaskStatus, TaskSubmission
from xagent_sdk.task import TaskHandle


class XAgent:
    """Synchronous client for X-Agent enterprise autonomous agent framework.

    This client provides methods to interact with the X-Agent API, including
    task submission, polling, cancellation, and interactive chat.

    Example:
        >>> client = XAgent(base_url="http://localhost:8000", api_key="your-key")
        >>> task = client.submit_task("Analyze this codebase")
        >>> result = task.wait(timeout=300)
        >>> print(result.result)

    Attributes:
        base_url: Server base URL (default: http://localhost:8000).
        api_key: API key for authentication (optional).
        timeout: Default request timeout in seconds (default: 30).
        client: Underlying httpx.Client instance.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """Initialize XAgent client.

        Args:
            base_url: Server base URL. Defaults to localhost:8000.
            api_key: Optional API key for authentication.
            timeout: Request timeout in seconds. Defaults to 30.

        Raises:
            ValueError: If base_url is invalid.
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

        headers: Dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": "xagent-sdk/0.1.0",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self.client = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=timeout,
        )

    def __enter__(self) -> "XAgent":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self.client.close()

    def _handle_response(self, response: httpx.Response) -> Any:
        """Handle HTTP response and raise appropriate exceptions.

        Args:
            response: httpx Response object.

        Returns:
            Parsed JSON response.

        Raises:
            AuthenticationError: On 401 status.
            ValidationError: On 400 status.
            RateLimitError: On 429 status.
            ServerError: On 5xx status.
            XAgentError: On other errors.
        """
        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError):
            data = {"error": response.text}

        if 200 <= response.status_code < 300:
            return data

        error_msg = data.get("error", data.get("message", response.text))

        if response.status_code == 401:
            raise AuthenticationError(str(error_msg))
        elif response.status_code == 400:
            raise ValidationError(str(error_msg))
        elif response.status_code == 404:
            raise TaskNotFoundError(str(error_msg))
        elif response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            raise RateLimitError(str(error_msg), retry_after=retry_after)
        elif response.status_code >= 500:
            if response.status_code == 503:
                raise ServiceUnavailableError(str(error_msg))
            raise ServerError(str(error_msg), status_code=response.status_code)
        else:
            raise XAgentError(
                str(error_msg),
                code=f"HTTP_{response.status_code}",
                status_code=response.status_code,
            )

    def health(self) -> HealthStatus:
        """Check server health status.

        Returns:
            HealthStatus object with server status and component info.

        Raises:
            ConnectionError: If unable to connect to server.
            XAgentError: If health check fails.

        Example:
            >>> status = client.health()
            >>> print(f"Server: {status.status}, Version: {status.version}")
        """
        try:
            response = self.client.get("/api/v1/health")
            data = self._handle_response(response)
            return HealthStatus(**data)
        except httpx.ConnectError as e:
            raise ConnectionError(f"Failed to connect to {self.base_url}") from e
        except httpx.TimeoutException as e:
            raise TimeoutError(f"Health check timed out after {self.timeout}s") from e

    def submit_task(
        self,
        description: str,
        repo: Optional[str] = None,
        branch: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout_seconds: int = 300,
    ) -> TaskHandle:
        """Submit an asynchronous task to the agent.

        Args:
            description: Task description or instructions.
            repo: Optional repository URL or path.
            branch: Optional git branch name.
            params: Optional task-specific parameters.
            timeout_seconds: Maximum execution time (10-3600 seconds).

        Returns:
            TaskHandle for polling and cancellation.

        Raises:
            ValidationError: If parameters are invalid.
            AuthenticationError: If authentication fails.
            ServerError: If server error occurs.

        Example:
            >>> task = client.submit_task(
            ...     "Analyze code quality",
            ...     repo="https://github.com/example/project",
            ...     params={"max_issues": 10}
            ... )
            >>> result = task.wait(timeout=600)
        """
        submission = TaskSubmission(
            description=description,
            repo=repo,
            branch=branch,
            params=params or {},
            timeout_seconds=timeout_seconds,
        )

        try:
            response = self.client.post(
                "/api/v1/tasks",
                json=submission.model_dump(),
            )
            data = self._handle_response(response)
            task = Task(**data)
            return TaskHandle(task_id=task.task_id, client=self)
        except httpx.TimeoutException as e:
            raise TimeoutError(f"Request timed out after {self.timeout}s") from e

    def get_task(self, task_id: str) -> TaskResult:
        """Get task result by ID.

        Args:
            task_id: Unique task identifier.

        Returns:
            TaskResult with task status and output.

        Raises:
            TaskNotFoundError: If task does not exist.
            AuthenticationError: If authentication fails.
            ServerError: If server error occurs.
        """
        try:
            response = self.client.get(f"/api/v1/tasks/{task_id}")
            data = self._handle_response(response)
            return TaskResult(**data)
        except httpx.TimeoutException as e:
            raise TimeoutError(f"Request timed out after {self.timeout}s") from e

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task.

        Args:
            task_id: Unique task identifier.

        Returns:
            True if cancellation was successful.

        Raises:
            TaskNotFoundError: If task does not exist.
            AuthenticationError: If authentication fails.
            ServerError: If server error occurs.
        """
        try:
            response = self.client.post(f"/api/v1/tasks/{task_id}/cancel")
            data = self._handle_response(response)
            return data.get("success", False)
        except httpx.TimeoutException as e:
            raise TimeoutError(f"Request timed out after {self.timeout}s") from e

    def chat(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
    ) -> AgentResponse:
        """Interactive chat with the agent.

        Sends a message and receives an immediate response. For long-running
        analysis, use submit_task() instead.

        Args:
            message: User message or query.
            context: Optional context dictionary (e.g., file contents, memory).
            model: Optional model override for this request.

        Returns:
            AgentResponse with response content and metadata.

        Raises:
            ValidationError: If message is invalid.
            AuthenticationError: If authentication fails.
            ServerError: If server error occurs.

        Example:
            >>> response = client.chat(
            ...     "What are the security issues in this code?",
            ...     context={"code": source_code}
            ... )
            >>> print(response.content)
        """
        payload: Dict[str, Any] = {"message": message}
        if context:
            payload["context"] = context
        if model:
            payload["model"] = model

        try:
            response = self.client.post("/api/v1/chat", json=payload)
            data = self._handle_response(response)
            return AgentResponse(**data)
        except httpx.TimeoutException as e:
            raise TimeoutError(f"Request timed out after {self.timeout}s") from e

    def workflow_run(
        self,
        template: str,
        params: Optional[Dict[str, Any]] = None,
        wait: bool = False,
        timeout_seconds: int = 300,
    ) -> TaskResult:
        """Execute a named workflow template.

        Args:
            template: Workflow template name (e.g., "code-review", "security-audit").
            params: Workflow parameters.
            wait: If True, block until workflow completes.
            timeout_seconds: Execution timeout if wait=True.

        Returns:
            TaskResult with workflow output.

        Raises:
            ValidationError: If template or params are invalid.
            AuthenticationError: If authentication fails.
            ServerError: If server error occurs.

        Example:
            >>> result = client.workflow_run(
            ...     "code-review",
            ...     params={"repo": "https://github.com/example/project"},
            ...     wait=True,
            ...     timeout_seconds=600
            ... )
        """
        payload: Dict[str, Any] = {"template": template}
        if params:
            payload["params"] = params

        try:
            response = self.client.post("/api/v1/workflows/run", json=payload)
            data = self._handle_response(response)

            if "task_id" in data and wait:
                task = TaskHandle(task_id=data["task_id"], client=self)
                result = task.wait(timeout=timeout_seconds)
                return result
            else:
                return TaskResult(**data)
        except httpx.TimeoutException as e:
            raise TimeoutError(f"Request timed out after {self.timeout}s") from e
