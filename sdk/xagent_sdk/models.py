"""Pydantic models for X-Agent SDK."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Task execution status enumeration."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TaskSubmission(BaseModel):
    """Task submission request model.

    Attributes:
        description: Task description or instructions for the agent.
        repo: Optional repository URL or path.
        branch: Optional git branch name.
        params: Optional task-specific parameters.
        timeout_seconds: Maximum execution time in seconds.
    """

    description: str = Field(..., min_length=1, max_length=10000)
    repo: Optional[str] = Field(None, max_length=1000)
    branch: Optional[str] = Field(None, max_length=255)
    params: Optional[Dict[str, Any]] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=300, ge=10, le=3600)

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "description": "Analyze the codebase and suggest refactorings",
                "repo": "https://github.com/example/project",
                "branch": "main",
                "params": {"max_suggestions": 5},
                "timeout_seconds": 600,
            }
        }


class TaskResult(BaseModel):
    """Task execution result model.

    Attributes:
        task_id: Unique task identifier.
        status: Current task status.
        result: Task execution result or output.
        pr_url: Pull request URL if applicable.
        diff: Code diff if applicable.
        logs: Execution logs or trace information.
        error: Error message if task failed.
        duration_ms: Total execution time in milliseconds.
        created_at: Task creation timestamp.
        completed_at: Task completion timestamp.
    """

    task_id: str = Field(..., min_length=1)
    status: TaskStatus
    result: Optional[Any] = None
    pr_url: Optional[str] = None
    diff: Optional[str] = None
    logs: Optional[str] = None
    error: Optional[str] = None
    duration_ms: int = Field(default=0, ge=0)
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat()}


class AgentResponse(BaseModel):
    """Agent chat response model.

    Attributes:
        content: Response text content.
        model: Model identifier used for generation.
        usage: Token usage statistics.
        metadata: Optional metadata (e.g., confidence, sources).
    """

    content: str = Field(..., min_length=1)
    model: str = Field(default="x-agent-default")
    usage: Optional[Dict[str, int]] = Field(
        default_factory=lambda: {"input_tokens": 0, "output_tokens": 0}
    )
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "content": "The codebase has good structure...",
                "model": "claude-3-sonnet",
                "usage": {"input_tokens": 150, "output_tokens": 450},
                "metadata": {"source_files": 5, "confidence": 0.95},
            }
        }


class ComponentStatus(str, Enum):
    """Component health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class HealthStatus(BaseModel):
    """Server health status model.

    Attributes:
        status: Overall server status.
        version: Server version string.
        components: Individual component statuses.
        integrations: Available integrations (MCP, webhook, etc.).
        timestamp: Health check timestamp.
    """

    status: ComponentStatus
    version: str
    components: Dict[str, ComponentStatus] = Field(
        default_factory=lambda: {
            "api": ComponentStatus.HEALTHY,
            "database": ComponentStatus.HEALTHY,
            "llm": ComponentStatus.HEALTHY,
            "cache": ComponentStatus.HEALTHY,
        }
    )
    integrations: Dict[str, bool] = Field(
        default_factory=lambda: {
            "mcp": True,
            "webhook": True,
            "slack": False,
            "github": False,
        }
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat()}


class Task(BaseModel):
    """Task handle model for polling and state tracking.

    Attributes:
        task_id: Unique task identifier.
        status: Current task status.
        progress: Execution progress (0-100).
        created_at: Task creation timestamp.
    """

    task_id: str = Field(..., min_length=1)
    status: TaskStatus
    progress: int = Field(default=0, ge=0, le=100)
    created_at: datetime

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat()}
