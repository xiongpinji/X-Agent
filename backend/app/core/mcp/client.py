"""MCP Client implementation."""

from __future__ import annotations

from typing import Any, Dict, Optional
import httpx

from backend.app.core.mcp.protocol import MCPRequest, MCPResponse


class MCPClient:
    """MCP client for communicating with MCP servers."""

    def __init__(self, server_url: str, timeout: float = 30.0):
        """Initialize MCP client.

        Args:
            server_url: Base URL of the MCP server
            timeout: Request timeout in seconds
        """
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """Call a tool on the MCP server.

        Args:
            tool_name: Name of the tool to call
            args: Arguments to pass to the tool

        Returns:
            Tool execution result

        Raises:
            httpx.HTTPError: If the request fails
            ValueError: If the response indicates an error
        """
        request = MCPRequest(
            type="request",
            method="tools/call",
            params={"tool": tool_name, "args": args},
        )

        response = await self._send_request(request)

        if response.error:
            raise ValueError(f"Tool call failed: {response.error}")

        return response.result.get("output") if response.result else None

    async def list_tools(self) -> list[Dict[str, Any]]:
        """List all available tools on the MCP server.

        Returns:
            List of tool definitions
        """
        request = MCPRequest(
            type="request",
            method="tools/list",
        )

        response = await self._send_request(request)

        if response.error:
            raise ValueError(f"Failed to list tools: {response.error}")

        return response.result.get("tools", []) if response.result else []

    async def _send_request(self, request: MCPRequest) -> MCPResponse:
        """Send a request to the MCP server.

        Args:
            request: MCP request to send

        Returns:
            MCP response from server
        """
        url = f"{self.server_url}/mcp/request"
        response = await self.client.post(url, json=request.model_dump())
        response.raise_for_status()

        data = response.json()
        return MCPResponse(**data)

    async def close(self) -> None:
        """Close the client connection."""
        await self.client.aclose()

    async def __aenter__(self) -> MCPClient:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
