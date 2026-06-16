"""Task handle for polling and state tracking."""

import asyncio
import time
from typing import TYPE_CHECKING, Optional

from xagent_sdk.exceptions import TaskCancelledError, TaskTimeoutError
from xagent_sdk.models import TaskResult, TaskStatus

if TYPE_CHECKING:
    from xagent_sdk.async_client import AsyncXAgent
    from xagent_sdk.client import XAgent


class TaskHandle:
    """Synchronous task handle for polling and cancellation.

    Provides methods to poll task status, wait for completion, and cancel tasks.

    Example:
        >>> task = client.submit_task("Analyze code")
        >>> if not task.is_done:
        ...     result = task.wait(timeout=300, poll_interval=2)
        ... else:
        ...     result = task.result()
    """

    def __init__(self, task_id: str, client: "XAgent"):
        """Initialize TaskHandle.

        Args:
            task_id: Unique task identifier.
            client: XAgent client instance.
        """
        self.task_id = task_id
        self.client = client
        self._cached_result: Optional[TaskResult] = None

    @property
    def is_done(self) -> bool:
        """Check if task is complete.

        Returns:
            True if task status is COMPLETED, FAILED, CANCELLED, or TIMEOUT.
        """
        result = self.poll()
        return result.status in (
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.TIMEOUT,
        )

    def poll(self) -> TaskResult:
        """Poll task status without blocking.

        Returns:
            TaskResult with current task status.

        Raises:
            TaskNotFoundError: If task does not exist.
            XAgentError: If request fails.
        """
        result = self.client.get_task(self.task_id)
        self._cached_result = result
        return result

    def wait(
        self,
        timeout: int = 300,
        poll_interval: int = 5,
    ) -> TaskResult:
        """Wait for task completion with polling.

        Blocks until task completes or timeout is reached. Uses exponential
        backoff with jitter for polling to avoid thundering herd.

        Args:
            timeout: Maximum wait time in seconds (default 300).
            poll_interval: Initial poll interval in seconds (default 5).

        Returns:
            TaskResult with final task status and output.

        Raises:
            TaskTimeoutError: If timeout is exceeded.
            TaskCancelledError: If task was cancelled.
            XAgentError: If request fails.

        Example:
            >>> result = task.wait(timeout=600, poll_interval=10)
            >>> print(f"Status: {result.status}")
            >>> print(f"Result: {result.result}")
        """
        start_time = time.time()
        current_interval = poll_interval
        max_interval = 60  # Cap polling at 1 minute

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TaskTimeoutError(
                    f"Task {self.task_id} did not complete within {timeout}s"
                )

            result = self.poll()

            if result.status == TaskStatus.COMPLETED:
                self._cached_result = result
                return result
            elif result.status == TaskStatus.FAILED:
                self._cached_result = result
                error_msg = result.error or "Task failed"
                raise RuntimeError(f"Task failed: {error_msg}")
            elif result.status == TaskStatus.CANCELLED:
                self._cached_result = result
                raise TaskCancelledError(self.task_id)
            elif result.status == TaskStatus.TIMEOUT:
                self._cached_result = result
                raise TaskTimeoutError(f"Task execution timed out")

            # Exponential backoff with jitter
            remaining = timeout - elapsed
            wait_time = min(current_interval, remaining)
            if wait_time > 0:
                time.sleep(wait_time)
                current_interval = min(current_interval * 1.5, max_interval)

    def cancel(self) -> bool:
        """Cancel the task.

        Returns:
            True if cancellation was successful.

        Raises:
            TaskNotFoundError: If task does not exist.
            XAgentError: If request fails.
        """
        return self.client.cancel_task(self.task_id)

    def result(self, timeout: Optional[int] = None) -> TaskResult:
        """Get task result, waiting if necessary.

        Convenience method equivalent to wait().

        Args:
            timeout: Maximum wait time in seconds (optional).

        Returns:
            TaskResult with task output.

        Raises:
            TaskTimeoutError: If timeout is exceeded.
            XAgentError: If request fails.
        """
        if self._cached_result:
            return self._cached_result
        return self.wait(timeout=timeout or 300)


class AsyncTaskHandle:
    """Asynchronous task handle for polling and cancellation.

    Provides async methods to poll task status, wait for completion, and cancel tasks.

    Example:
        >>> task = await client.submit_task("Analyze code")
        >>> if not await task.is_done:
        ...     result = await task.wait(timeout=300)
        ... else:
        ...     result = await task.result()
    """

    def __init__(self, task_id: str, client: "AsyncXAgent"):
        """Initialize AsyncTaskHandle.

        Args:
            task_id: Unique task identifier.
            client: AsyncXAgent client instance.
        """
        self.task_id = task_id
        self.client = client
        self._cached_result: Optional[TaskResult] = None

    @property
    async def is_done(self) -> bool:
        """Check if task is complete.

        Returns:
            True if task status is COMPLETED, FAILED, CANCELLED, or TIMEOUT.
        """
        result = await self.poll()
        return result.status in (
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.TIMEOUT,
        )

    async def poll(self) -> TaskResult:
        """Poll task status without blocking.

        Returns:
            TaskResult with current task status.

        Raises:
            TaskNotFoundError: If task does not exist.
            XAgentError: If request fails.
        """
        result = await self.client.get_task(self.task_id)
        self._cached_result = result
        return result

    async def wait(
        self,
        timeout: int = 300,
        poll_interval: int = 5,
    ) -> TaskResult:
        """Wait for task completion with polling (async).

        Blocks until task completes or timeout is reached. Uses exponential
        backoff with jitter for polling.

        Args:
            timeout: Maximum wait time in seconds (default 300).
            poll_interval: Initial poll interval in seconds (default 5).

        Returns:
            TaskResult with final task status and output.

        Raises:
            TaskTimeoutError: If timeout is exceeded.
            TaskCancelledError: If task was cancelled.
            XAgentError: If request fails.

        Example:
            >>> result = await task.wait(timeout=600)
            >>> print(f"Status: {result.status}")
        """
        start_time = time.time()
        current_interval = poll_interval
        max_interval = 60

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TaskTimeoutError(
                    f"Task {self.task_id} did not complete within {timeout}s"
                )

            result = await self.poll()

            if result.status == TaskStatus.COMPLETED:
                self._cached_result = result
                return result
            elif result.status == TaskStatus.FAILED:
                self._cached_result = result
                error_msg = result.error or "Task failed"
                raise RuntimeError(f"Task failed: {error_msg}")
            elif result.status == TaskStatus.CANCELLED:
                self._cached_result = result
                raise TaskCancelledError(self.task_id)
            elif result.status == TaskStatus.TIMEOUT:
                self._cached_result = result
                raise TaskTimeoutError(f"Task execution timed out")

            # Exponential backoff
            remaining = timeout - elapsed
            wait_time = min(current_interval, remaining)
            if wait_time > 0:
                await asyncio.sleep(wait_time)
                current_interval = min(current_interval * 1.5, max_interval)

    async def cancel(self) -> bool:
        """Cancel the task asynchronously.

        Returns:
            True if cancellation was successful.

        Raises:
            TaskNotFoundError: If task does not exist.
            XAgentError: If request fails.
        """
        return await self.client.cancel_task(self.task_id)

    async def result(self, timeout: Optional[int] = None) -> TaskResult:
        """Get task result, waiting if necessary (async).

        Convenience method equivalent to wait().

        Args:
            timeout: Maximum wait time in seconds (optional).

        Returns:
            TaskResult with task output.

        Raises:
            TaskTimeoutError: If timeout is exceeded.
            XAgentError: If request fails.
        """
        if self._cached_result:
            return self._cached_result
        return await self.wait(timeout=timeout or 300)
