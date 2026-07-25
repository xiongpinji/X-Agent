"""MCP (Model Context Protocol) integration module.

P1-01 起：客户端基于官方 ``mcp`` Python SDK（stdio + Streamable HTTP），
发现的工具经 ``MCPToolDiscovery`` 双写 ToolCatalog 与运行时 ToolRegistry。
``MCPMessage`` / ``MCPServer`` / ``MCPRequest`` / ``MCPResponse`` 为旧私有
协议的兼容保留（见 protocol.py 的弃用说明）。
"""

from backend.app.core.mcp.client import MCP_SDK_AVAILABLE, MCPClient, MCPUnavailableError
from backend.app.core.mcp.discovery import MCPServerConfig, MCPToolDiscovery
from backend.app.core.mcp.manager import (
    MCPManager,
    get_mcp_manager,
    initialize_mcp_manager,
    shutdown_mcp_manager,
)
from backend.app.core.mcp.protocol import MCPMessage, MCPRequest, MCPResponse, MCPServer

__all__ = [
    "MCP_SDK_AVAILABLE",
    "MCPClient",
    "MCPManager",
    "MCPMessage",
    "MCPRequest",
    "MCPResponse",
    "MCPServer",
    "MCPServerConfig",
    "MCPToolDiscovery",
    "MCPUnavailableError",
    "get_mcp_manager",
    "initialize_mcp_manager",
    "shutdown_mcp_manager",
]
