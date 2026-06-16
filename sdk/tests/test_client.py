"""Tests for X-Agent SDK client and models."""

import pytest
import respx
from datetime import datetime
from httpx import Response

from xagent_sdk import (
    XAgent,
    AsyncXAgent,
    AgentResponse,
    HealthStatus,
    TaskResult,
    TaskStatus,
)
from xagent_sdk.exceptions import (
    AuthenticationError,
    ConnectionError,
    RateLimitError,
    ServerError,
    TaskNotFoundError,
    TaskTimeoutError,
    TimeoutError,
    ValidationError,
)
from xagent_sdk.models import ComponentStatus


class TestXAgentHealthCheck:
    """Tests for XAgent.health() method."""

    @respx.mock
    def test_health_check_success(self, respx_mock):
        """Test successful health check."""
        health_response = {
            "status": "healthy",
            "version": "0.1.0",
            "components": {
                "api": "healthy",
                "database": "healthy",
                "llm": "healthy",
                "cache": "healthy",
            },
            "integrations": {
                "mcp": True,
                "webhook": True,
                "slack": False,
                "github": False,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
        respx_mock.get("http://localhost:8000/api/v1/health").mock(
            return_value=Response(200, json=health_response)
        )

        client = XAgent()
        health = client.health()

        assert health.status == ComponentStatus.HEALTHY
        assert health.version == "0.1.0"
        assert health.components["api"] == ComponentStatus.HEALTHY
        client.close()

    @respx.mock
    def test_health_check_connection_error(self, respx_mock):
        """Test health check with connection error."""
        respx_mock.get("http://localhost:8000/api/v1/health").mock(side_effect=Exception("Connection refused"))

        client = XAgent()
        with pytest.raises(ConnectionError):
            client.health()
        client.close()


class TestXAgentTaskSubmission:
    """Tests for XAgent.submit_task() method."""

    @respx.mock
    def test_submit_task_success(self, respx_mock):
        """Test successful task submission."""
        task_response = {
            "task_id": "task-123",
            "status": "pending",
            "progress": 0,
            "created_at": datetime.utcnow().isoformat(),
        }
        respx_mock.post("http://localhost:8000/api/v1/tasks").mock(
            return_value=Response(200, json=task_response)
        )

        client = XAgent()
        task = client.submit_task("Analyze code", repo="https://github.com/example/project")

        assert task.task_id == "task-123"
        client.close()

    @respx.mock
    def test_submit_task_validation_error(self, respx_mock):
        """Test task submission with validation error."""
        respx_mock.post("http://localhost:8000/api/v1/tasks").mock(
            return_value=Response(400, json={"error": "Invalid task description"})
        )

        client = XAgent()
        with pytest.raises(ValidationError):
            client.submit_task("")
        client.close()

    @respx.mock
    def test_submit_task_authentication_error(self, respx_mock):
        """Test task submission with authentication error."""
        respx_mock.post("http://localhost:8000/api/v1/tasks").mock(
            return_value=Response(401, json={"error": "Invalid API key"})
        )

        client = XAgent(api_key="invalid-key")
        with pytest.raises(AuthenticationError):
            client.submit_task("Analyze code")
        client.close()


class TestTaskWait:
    """Tests for TaskHandle.wait() method."""

    @respx.mock
    def test_task_wait_success(self, respx_mock):
        """Test task wait with successful completion."""
        # First call: running
        running_response = {
            "task_id": "task-123",
            "status": "running",
            "result": None,
            "pr_url": None,
            "diff": None,
            "logs": None,
            "error": None,
            "duration_ms": 0,
            "created_at": datetime.utcnow().isoformat(),
            "completed_at": None,
        }
        # Second call: completed
        completed_response = {
            "task_id": "task-123",
            "status": "completed",
            "result": {"findings": "Code quality is good"},
            "pr_url": "https://github.com/example/pull/1",
            "diff": "diff content",
            "logs": "task logs",
            "error": None,
            "duration_ms": 5000,
            "created_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
        }

        respx_mock.get("http://localhost:8000/api/v1/tasks/task-123").mock(
            side_effect=[
                Response(200, json=running_response),
                Response(200, json=completed_response),
            ]
        )

        client = XAgent()
        task = client.submit_task("Analyze code")
        task.task_id = "task-123"  # Override for test

        result = task.wait(timeout=60, poll_interval=0.1)

        assert result.status == TaskStatus.COMPLETED
        assert result.task_id == "task-123"
        client.close()

    @respx.mock
    def test_task_wait_timeout(self, respx_mock):
        """Test task wait timeout."""
        running_response = {
            "task_id": "task-123",
            "status": "running",
            "result": None,
            "pr_url": None,
            "diff": None,
            "logs": None,
            "error": None,
            "duration_ms": 0,
            "created_at": datetime.utcnow().isoformat(),
            "completed_at": None,
        }

        respx_mock.get("http://localhost:8000/api/v1/tasks/task-123").mock(
            return_value=Response(200, json=running_response)
        )

        client = XAgent()
        task = client.submit_task("Analyze code")
        task.task_id = "task-123"

        with pytest.raises(TaskTimeoutError):
            task.wait(timeout=0.1, poll_interval=0.05)
        client.close()

    @respx.mock
    def test_task_wait_failure(self, respx_mock):
        """Test task wait with task failure."""
        failed_response = {
            "task_id": "task-123",
            "status": "failed",
            "result": None,
            "pr_url": None,
            "diff": None,
            "logs": "error logs",
            "error": "Task execution failed",
            "duration_ms": 1000,
            "created_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
        }

        respx_mock.get("http://localhost:8000/api/v1/tasks/task-123").mock(
            return_value=Response(200, json=failed_response)
        )

        client = XAgent()
        task = client.submit_task("Analyze code")
        task.task_id = "task-123"

        with pytest.raises(RuntimeError, match="Task failed"):
            task.wait(timeout=10)
        client.close()


class TestXAgentChat:
    """Tests for XAgent.chat() method."""

    @respx.mock
    def test_chat_success(self, respx_mock):
        """Test successful chat interaction."""
        chat_response = {
            "content": "The code has good structure and follows best practices.",
            "model": "claude-3-sonnet",
            "usage": {"input_tokens": 150, "output_tokens": 200},
            "metadata": {"sources": 3},
        }
        respx_mock.post("http://localhost:8000/api/v1/chat").mock(
            return_value=Response(200, json=chat_response)
        )

        client = XAgent()
        response = client.chat("Analyze this code quality")

        assert isinstance(response, AgentResponse)
        assert "good structure" in response.content
        assert response.model == "claude-3-sonnet"
        client.close()

    @respx.mock
    def test_chat_with_context(self, respx_mock):
        """Test chat with context."""
        chat_response = {
            "content": "This is a malicious pattern.",
            "model": "claude-3-sonnet",
            "usage": {"input_tokens": 500, "output_tokens": 100},
            "metadata": None,
        }
        respx_mock.post("http://localhost:8000/api/v1/chat").mock(
            return_value=Response(200, json=chat_response)
        )

        client = XAgent()
        response = client.chat(
            "Is this secure?",
            context={"code": "eval(user_input)"},
        )

        assert "malicious" in response.content
        client.close()


class TestXAgentErrorHandling:
    """Tests for error handling."""

    @respx.mock
    def test_rate_limit_error(self, respx_mock):
        """Test rate limit error handling."""
        respx_mock.get("http://localhost:8000/api/v1/tasks/task-123").mock(
            return_value=Response(
                429,
                json={"error": "Rate limit exceeded"},
                headers={"Retry-After": "60"},
            )
        )

        client = XAgent()
        task = client.submit_task("Analyze code")
        task.task_id = "task-123"

        with pytest.raises(RateLimitError) as exc_info:
            task.poll()

        assert exc_info.value.retry_after == 60
        client.close()

    @respx.mock
    def test_server_error(self, respx_mock):
        """Test server error handling."""
        respx_mock.get("http://localhost:8000/api/v1/health").mock(
            return_value=Response(500, json={"error": "Internal server error"})
        )

        client = XAgent()
        with pytest.raises(ServerError):
            client.health()
        client.close()

    @respx.mock
    def test_task_not_found_error(self, respx_mock):
        """Test task not found error."""
        respx_mock.get("http://localhost:8000/api/v1/tasks/nonexistent").mock(
            return_value=Response(404, json={"error": "Task not found"})
        )

        client = XAgent()
        with pytest.raises(TaskNotFoundError):
            client.get_task("nonexistent")
        client.close()


class TestXAgentWorkflow:
    """Tests for workflow execution."""

    @respx.mock
    def test_workflow_run_success(self, respx_mock):
        """Test successful workflow run."""
        workflow_response = {
            "task_id": "task-456",
            "status": "completed",
            "result": {"analysis": "complete"},
            "pr_url": "https://github.com/example/pull/2",
            "diff": "workflow diff",
            "logs": "workflow logs",
            "error": None,
            "duration_ms": 10000,
            "created_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
        }
        respx_mock.post("http://localhost:8000/api/v1/workflows/run").mock(
            return_value=Response(200, json=workflow_response)
        )

        client = XAgent()
        result = client.workflow_run("code-review", params={"max_issues": 10})

        assert isinstance(result, TaskResult)
        assert result.status == TaskStatus.COMPLETED
        client.close()

    @respx.mock
    def test_workflow_run_with_wait(self, respx_mock):
        """Test workflow run with wait."""
        task_response = {
            "task_id": "task-789",
            "status": "pending",
            "progress": 0,
            "created_at": datetime.utcnow().isoformat(),
        }
        completed_response = {
            "task_id": "task-789",
            "status": "completed",
            "result": {"analysis": "complete"},
            "pr_url": None,
            "diff": None,
            "logs": "logs",
            "error": None,
            "duration_ms": 5000,
            "created_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
        }

        respx_mock.post("http://localhost:8000/api/v1/workflows/run").mock(
            return_value=Response(200, json=task_response)
        )
        respx_mock.get("http://localhost:8000/api/v1/tasks/task-789").mock(
            side_effect=[
                Response(200, json=task_response),
                Response(200, json=completed_response),
            ]
        )

        client = XAgent()
        result = client.workflow_run(
            "code-review",
            wait=True,
            timeout_seconds=60,
        )

        assert result.status == TaskStatus.COMPLETED
        client.close()


class TestXAgentContextManager:
    """Tests for context manager support."""

    @respx.mock
    def test_context_manager(self, respx_mock):
        """Test using XAgent as context manager."""
        health_response = {
            "status": "healthy",
            "version": "0.1.0",
            "components": {},
            "integrations": {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        respx_mock.get("http://localhost:8000/api/v1/health").mock(
            return_value=Response(200, json=health_response)
        )

        with XAgent() as client:
            health = client.health()
            assert health.status == ComponentStatus.HEALTHY


class TestTaskCancellation:
    """Tests for task cancellation."""

    @respx.mock
    def test_cancel_task_success(self, respx_mock):
        """Test successful task cancellation."""
        respx_mock.post("http://localhost:8000/api/v1/tasks/task-123/cancel").mock(
            return_value=Response(200, json={"success": True})
        )

        client = XAgent()
        task = client.submit_task("Analyze code")
        task.task_id = "task-123"

        success = task.cancel()
        assert success is True
        client.close()

    @respx.mock
    def test_cancel_nonexistent_task(self, respx_mock):
        """Test cancelling nonexistent task."""
        respx_mock.post("http://localhost:8000/api/v1/tasks/nonexistent/cancel").mock(
            return_value=Response(404, json={"error": "Task not found"})
        )

        client = XAgent()
        with pytest.raises(TaskNotFoundError):
            client.cancel_task("nonexistent")
        client.close()


# Async tests
@pytest.mark.asyncio
class TestAsyncXAgentHealthCheck:
    """Tests for AsyncXAgent.health() method."""

    @respx.mock
    async def test_async_health_check_success(self, respx_mock):
        """Test successful async health check."""
        health_response = {
            "status": "healthy",
            "version": "0.1.0",
            "components": {"api": "healthy"},
            "integrations": {"mcp": True},
            "timestamp": datetime.utcnow().isoformat(),
        }
        respx_mock.get("http://localhost:8000/api/v1/health").mock(
            return_value=Response(200, json=health_response)
        )

        async with AsyncXAgent() as client:
            health = await client.health()
            assert health.status == ComponentStatus.HEALTHY


@pytest.mark.asyncio
class TestAsyncXAgentChat:
    """Tests for AsyncXAgent.chat() method."""

    @respx.mock
    async def test_async_chat_success(self, respx_mock):
        """Test successful async chat."""
        chat_response = {
            "content": "Async response content",
            "model": "claude-3-sonnet",
            "usage": {"input_tokens": 100, "output_tokens": 150},
            "metadata": None,
        }
        respx_mock.post("http://localhost:8000/api/v1/chat").mock(
            return_value=Response(200, json=chat_response)
        )

        async with AsyncXAgent() as client:
            response = await client.chat("Hello agent")
            assert "Async response" in response.content
