"""X-Agent Python SDK

A production-quality SDK for interacting with the X-Agent enterprise autonomous agent framework.

Example:
    >>> from xagent_sdk import XAgent
    >>> client = XAgent(base_url="http://localhost:8000", api_key="your-api-key")
    >>> result = client.chat("Analyze this codebase")
    >>> print(result.content)

    For async usage:
    >>> import asyncio
    >>> from xagent_sdk import AsyncXAgent
    >>> async def main():
    ...     async with AsyncXAgent(api_key="your-api-key") as client:
    ...         result = await client.chat("Analyze this codebase")
    ...         print(result.content)
    >>> asyncio.run(main())
"""

__version__ = "0.1.0"
__author__ = "X-Agent Contributors"
__license__ = "MIT"

from xagent_sdk.async_client import AsyncXAgent
from xagent_sdk.client import XAgent
from xagent_sdk.exceptions import (
    AuthenticationError,
    ServerError,
    TaskTimeoutError,
    ValidationError,
    XAgentError,
)
from xagent_sdk.models import AgentResponse, HealthStatus, Task, TaskResult, TaskSubmission
from xagent_sdk.task import TaskHandle

__all__ = [
    "XAgent",
    "AsyncXAgent",
    "Task",
    "TaskHandle",
    "TaskResult",
    "TaskSubmission",
    "AgentResponse",
    "HealthStatus",
    "XAgentError",
    "AuthenticationError",
    "TaskTimeoutError",
    "ServerError",
    "ValidationError",
]
