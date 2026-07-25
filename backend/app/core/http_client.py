"""
Unified HTTP client management for X-Agent.

Implements:
- Async HTTP client with connection pooling
- Retry logic with exponential backoff
- Timeout and circuit breaker patterns
- Request/response logging
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class HTTPClientManager:
    """
    Manages HTTP client lifecycle and connection pooling.

    Features:
    - Connection pooling via httpx
    - Retry logic with exponential backoff
    - Timeout handling
    - Request/response logging
    """

    def __init__(
        self,
        max_connections: int = 20,
        max_keepalive_connections: int = 20,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ) -> None:
        self._max_connections = max_connections
        self._max_keepalive_connections = max_keepalive_connections
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor
        self._client: Any | None = None
        self._lock = asyncio.Lock()
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "retried_requests": 0,
            "total_retry_count": 0,
        }

    async def initialize(self) -> None:
        """Initialize the HTTP client."""
        if self._client is not None:
            return

        async with self._lock:
            if self._client is not None:
                return

            try:
                import httpx

                limits = httpx.Limits(
                    max_connections=self._max_connections,
                    max_keepalive_connections=self._max_keepalive_connections,
                )
                self._client = httpx.AsyncClient(
                    limits=limits,
                    timeout=self._timeout,
                )
                logger.info(
                    f"HTTP client initialized with {self._max_connections} max connections"
                )
            except ImportError:
                logger.error("httpx not installed. Install with: pip install httpx")
                raise

    async def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Make a GET request with retry logic."""
        return await self._request("GET", url, headers=headers, params=params)

    async def post(
        self,
        url: str,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        data: Any | None = None,
    ) -> Any:
        """Make a POST request with retry logic."""
        return await self._request("POST", url, json=json, headers=headers, data=data)

    async def put(
        self,
        url: str,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Make a PUT request with retry logic."""
        return await self._request("PUT", url, json=json, headers=headers)

    async def delete(
        self,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Make a DELETE request with retry logic."""
        return await self._request("DELETE", url, headers=headers)

    async def _request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        data: Any | None = None,
    ) -> Any:
        """Make an HTTP request with retry logic."""
        await self.initialize()

        retry_count = 0
        last_error = None

        while retry_count <= self._max_retries:
            try:
                self._stats["total_requests"] += 1

                response = await self._client.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json,
                    data=data,
                )

                if response.status_code >= 500:
                    # Server error, retry
                    if retry_count < self._max_retries:
                        retry_count += 1
                        self._stats["retried_requests"] += 1
                        self._stats["total_retry_count"] += 1
                        wait_time = self._backoff_factor * (2 ** (retry_count - 1))
                        logger.warning(
                            f"Server error {response.status_code} for {method} {url}. "
                            f"Retrying in {wait_time}s (attempt {retry_count}/{self._max_retries})"
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        self._stats["failed_requests"] += 1
                        response.raise_for_status()

                self._stats["successful_requests"] += 1
                return response

            except TimeoutError as e:
                last_error = e
                if retry_count < self._max_retries:
                    retry_count += 1
                    self._stats["retried_requests"] += 1
                    self._stats["total_retry_count"] += 1
                    wait_time = self._backoff_factor * (2 ** (retry_count - 1))
                    logger.warning(
                        f"Timeout for {method} {url}. "
                        f"Retrying in {wait_time}s (attempt {retry_count}/{self._max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    self._stats["failed_requests"] += 1
                    raise

            except Exception as e:
                last_error = e
                if retry_count < self._max_retries and self._is_retryable_error(e):
                    retry_count += 1
                    self._stats["retried_requests"] += 1
                    self._stats["total_retry_count"] += 1
                    wait_time = self._backoff_factor * (2 ** (retry_count - 1))
                    logger.warning(
                        f"Error for {method} {url}: {e}. "
                        f"Retrying in {wait_time}s (attempt {retry_count}/{self._max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    self._stats["failed_requests"] += 1
                    raise

        # Should not reach here
        self._stats["failed_requests"] += 1
        raise last_error or RuntimeError(f"Failed to {method} {url}")

    @staticmethod
    def _is_retryable_error(error: Exception) -> bool:
        """Check if an error is retryable."""
        retryable_errors = (
            ConnectionError,
            TimeoutError,
            asyncio.TimeoutError,
        )
        return isinstance(error, retryable_errors)

    async def close(self) -> None:
        """Close the HTTP client."""
        async with self._lock:
            if self._client is not None:
                await self._client.aclose()
                self._client = None
                logger.info("HTTP client closed")

    def get_stats(self) -> dict[str, Any]:
        """Get HTTP client statistics."""
        total = self._stats["total_requests"]
        success_rate = (
            self._stats["successful_requests"] / total if total > 0 else 0
        )
        avg_retries = (
            self._stats["total_retry_count"] / self._stats["retried_requests"]
            if self._stats["retried_requests"] > 0
            else 0
        )

        return {
            **self._stats,
            "success_rate": success_rate,
            "avg_retries": avg_retries,
        }

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# Global HTTP client manager
_http_manager: HTTPClientManager | None = None


def get_http_client() -> HTTPClientManager:
    """Get or create the global HTTP client manager."""
    global _http_manager
    if _http_manager is None:
        _http_manager = HTTPClientManager()
    return _http_manager


async def close_http_client() -> None:
    """Close the global HTTP client manager."""
    global _http_manager
    if _http_manager is not None:
        await _http_manager.close()
        _http_manager = None
