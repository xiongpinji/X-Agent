"""MCP Client implementation with retry, connection pooling, caching, and batch support."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional, List, Tuple
from datetime import datetime, timedelta
import hashlib
import json

import httpx

from backend.app.core.mcp.protocol import MCPRequest, MCPResponse

logger = logging.getLogger(__name__)


class MCPConnectionPool:
    """Connection pool for managing MCP client connections."""

    def __init__(self, max_connections: int = 10):
        """Initialize connection pool.

        Args:
            max_connections: Maximum number of concurrent connections
        """
        self.max_connections = max_connections
        self.semaphore = asyncio.Semaphore(max_connections)
        self.active_connections = 0

    async def acquire(self) -> None:
        """Acquire a connection slot."""
        await self.semaphore.acquire()
        self.active_connections += 1

    def release(self) -> None:
        """Release a connection slot."""
        self.active_connections -= 1
        self.semaphore.release()

    def get_stats(self) -> Dict[str, int]:
        """Get connection pool statistics."""
        return {
            "active": self.active_connections,
            "max": self.max_connections,
            "available": self.max_connections - self.active_connections,
        }


class MCPResultCache:
    """Simple in-memory cache for tool results."""

    def __init__(self, ttl_seconds: int = 300):
        """Initialize result cache.

        Args:
            ttl_seconds: Time-to-live for cached results in seconds
        """
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Tuple[Any, datetime]] = {}

    def _make_key(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Generate cache key from tool name and arguments."""
        args_str = json.dumps(args, sort_keys=True, default=str)
        key_str = f"{tool_name}:{args_str}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, tool_name: str, args: Dict[str, Any]) -> Optional[Any]:
        """Get cached result if available and not expired.

        Args:
            tool_name: Name of the tool
            args: Tool arguments

        Returns:
            Cached result or None if not found or expired
        """
        key = self._make_key(tool_name, args)
        if key not in self.cache:
            return None

        result, timestamp = self.cache[key]
        if datetime.now() - timestamp > timedelta(seconds=self.ttl_seconds):
            del self.cache[key]
            return None

        logger.debug(f"Cache hit for {tool_name}")
        return result

    def set(self, tool_name: str, args: Dict[str, Any], result: Any) -> None:
        """Cache a tool result.

        Args:
            tool_name: Name of the tool
            args: Tool arguments
            result: Result to cache
        """
        key = self._make_key(tool_name, args)
        self.cache[key] = (result, datetime.now())

    def clear(self) -> None:
        """Clear all cached results."""
        self.cache.clear()

    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {"size": len(self.cache), "ttl_seconds": self.ttl_seconds}


class MCPClient:
    """MCP client with retry, connection pooling, caching, and batch support."""

    def __init__(
        self,
        server_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff_factor: float = 2.0,
        max_connections: int = 10,
        cache_ttl_seconds: int = 300,
        enable_cache: bool = True,
    ):
        """Initialize MCP client.

        Args:
            server_url: Base URL of the MCP server
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_backoff_factor: Exponential backoff factor for retries
            max_connections: Maximum concurrent connections
            cache_ttl_seconds: Cache time-to-live in seconds
            enable_cache: Whether to enable result caching
        """
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff_factor = retry_backoff_factor
        self.enable_cache = enable_cache

        self.client = httpx.AsyncClient(timeout=timeout)
        self.connection_pool = MCPConnectionPool(max_connections)
        self.cache = MCPResultCache(cache_ttl_seconds) if enable_cache else None

        logger.info(
            f"MCPClient initialized: url={server_url}, retries={max_retries}, "
            f"connections={max_connections}, cache={enable_cache}"
        )

    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """Call a tool on the MCP server with retry and caching.

        Args:
            tool_name: Name of the tool to call
            args: Arguments to pass to the tool

        Returns:
            Tool execution result

        Raises:
            ValueError: If the response indicates an error
            httpx.HTTPError: If all retries fail
        """
        # Check cache first
        if self.enable_cache:
            cached = self.cache.get(tool_name, args)
            if cached is not None:
                return cached

        request = MCPRequest(
            type="request",
            method="tools/call",
            params={"tool": tool_name, "args": args},
        )

        response = await self._send_request_with_retry(request)

        if response.error:
            raise ValueError(f"Tool call failed: {response.error}")

        result = response.result.get("output") if response.result else None

        # Cache the result
        if self.enable_cache and result is not None:
            self.cache.set(tool_name, args, result)

        return result

    async def call_tools_batch(
        self, calls: List[Tuple[str, Dict[str, Any]]]
    ) -> List[Any]:
        """Call multiple tools concurrently.

        Args:
            calls: List of (tool_name, args) tuples

        Returns:
            List of results in the same order as input
        """
        tasks = [self.call_tool(tool_name, args) for tool_name, args in calls]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def list_tools(self) -> list[Dict[str, Any]]:
        """List all available tools on the MCP server.

        Returns:
            List of tool definitions
        """
        request = MCPRequest(
            type="request",
            method="tools/list",
        )

        response = await self._send_request_with_retry(request)

        if response.error:
            raise ValueError(f"Failed to list tools: {response.error}")

        return response.result.get("tools", []) if response.result else []

    async def _send_request_with_retry(self, request: MCPRequest) -> MCPResponse:
        """Send a request with exponential backoff retry.

        Args:
            request: MCP request to send

        Returns:
            MCP response from server

        Raises:
            httpx.HTTPError: If all retries fail
        """
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                return await self._send_request(request)
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                last_error = e
                if attempt < self.max_retries:
                    wait_time = (self.retry_backoff_factor ** attempt)
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{self.max_retries + 1}), "
                        f"retrying in {wait_time}s: {e}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Request failed after {self.max_retries + 1} attempts: {e}")

        raise last_error

    async def _send_request(self, request: MCPRequest) -> MCPResponse:
        """Send a request to the MCP server with connection pooling.

        Args:
            request: MCP request to send

        Returns:
            MCP response from server
        """
        await self.connection_pool.acquire()
        try:
            url = f"{self.server_url}/mcp/request"
            response = await self.client.post(url, json=request.model_dump())
            response.raise_for_status()

            data = response.json()
            return MCPResponse(**data)
        finally:
            self.connection_pool.release()

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics.

        Returns:
            Dictionary with connection pool and cache stats
        """
        stats = {
            "connection_pool": self.connection_pool.get_stats(),
        }
        if self.enable_cache:
            stats["cache"] = self.cache.get_stats()
        return stats

    async def health_check(self) -> bool:
        """Check if the MCP server is healthy.

        Returns:
            True if server is reachable, False otherwise
        """
        try:
            tools = await self.list_tools()
            logger.info(f"Health check passed: {len(tools)} tools available")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close the client connection."""
        await self.client.aclose()
        if self.enable_cache:
            self.cache.clear()
        logger.info("MCPClient closed")

    async def __aenter__(self) -> MCPClient:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
