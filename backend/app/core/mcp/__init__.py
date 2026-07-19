"""MCP (Model Context Protocol) integration module."""

from backend.app.core.mcp.protocol import MCPMessage, MCPServer, MCPRequest, MCPResponse
from backend.app.core.mcp.client import MCPClient

__all__ = [
    "MCPMessage",
    "MCPServer",
    "MCPRequest",
    "MCPResponse",
    "MCPClient",
]
