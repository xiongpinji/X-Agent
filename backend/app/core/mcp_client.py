"""MCP Client — official SDK integration for tool discovery and execution.

P1-01: 高层 MCPClientManager 封装，提供统一的服务器连接管理、工具发现与调用接口。
底层复用 ``backend.app.core.mcp.client.MCPClient``（官方 ``mcp`` Python SDK）。

使用方式::

    from backend.app.core.mcp_client import get_mcp_client_manager

    manager = get_mcp_client_manager()
    server_id = await manager.connect_server({"name": "my-server", "url": "http://..."})
    tools = await manager.list_tools(server_id)
    result = await manager.call_tool(server_id, "tool_name", {"arg": "value"})
    await manager.disconnect_server(server_id)
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from backend.app.core.mcp.client import MCP_SDK_AVAILABLE, MCPClient, MCPUnavailableError

logger = logging.getLogger(__name__)


class MCPClientManager:
    """Manages MCP server connections using the official SDK.

    提供服务器连接的生命周期管理（connect / disconnect）、工具发现（list_tools /
    discover_all）以及工具调用（call_tool）。每个连接以唯一 server_id 标识。

    向后兼容：若官方 ``mcp`` SDK 未安装，connect_server 会显式抛出
    ``MCPUnavailableError``，不静默降级。
    """

    def __init__(self) -> None:
        self._connections: dict[str, MCPClient] = {}
        self._server_metadata: dict[str, dict[str, Any]] = {}

    @property
    def sdk_available(self) -> bool:
        """官方 MCP SDK 是否可用。"""
        return MCP_SDK_AVAILABLE

    @property
    def connected_servers(self) -> list[str]:
        """当前已连接的 server_id 列表。"""
        return list(self._connections.keys())

    async def connect_server(self, server_config: dict) -> str:
        """Connect to an MCP server and return its server_id.

        Args:
            server_config: 服务器配置字典，支持的键：
                - name (str): 服务器名称（可选，用于标识）
                - url (str): Streamable HTTP 端点（transport=http 时必填）
                - transport (str): "http" 或 "stdio"（默认 "http"）
                - command (str): stdio 传输的命令
                - args (list[str]): stdio 命令参数
                - env (dict): stdio 子进程环境变量
                - cwd (str): stdio 工作目录
                - headers (dict): HTTP 额外请求头
                - timeout (float): 请求超时秒数（默认 30）
                - max_retries (int): 最大重试次数（默认 3）
                - enable_cache (bool): 是否启用结果缓存（默认 True）

        Returns:
            server_id: 唯一标识此连接的 ID

        Raises:
            MCPUnavailableError: 官方 mcp SDK 未安装
            ValueError: 配置无效
            ConnectionError: 连接失败
        """
        if not MCP_SDK_AVAILABLE:
            raise MCPUnavailableError(
                "官方 mcp Python SDK 未安装，无法建立 MCP 连接。"
                "请执行 `pip install mcp` 或 `pip install x-agent-core[mcp]`。"
            )

        transport = server_config.get("transport", "http")
        name = server_config.get("name", f"server-{uuid.uuid4().hex[:8]}")

        client = MCPClient(
            server_url=server_config.get("url"),
            timeout=server_config.get("timeout", 30.0),
            max_retries=server_config.get("max_retries", 3),
            enable_cache=server_config.get("enable_cache", True),
            transport=transport,
            command=server_config.get("command"),
            args=server_config.get("args"),
            env=server_config.get("env"),
            cwd=server_config.get("cwd"),
            headers=server_config.get("headers"),
        )

        # 验证连接可用（执行 initialize 握手 + tools/list）
        try:
            await client.connect()
        except Exception as e:
            logger.error("Failed to connect to MCP server '%s': %s", name, e)
            raise ConnectionError(
                f"Cannot connect to MCP server '{name}': {e}"
            ) from e

        server_id = f"{name}-{uuid.uuid4().hex[:8]}"
        self._connections[server_id] = client
        self._server_metadata[server_id] = {
            "name": name,
            "transport": transport,
            "url": server_config.get("url", ""),
            "command": server_config.get("command", ""),
            "connected_at": datetime.now(UTC).isoformat(),
            "config": {k: v for k, v in server_config.items() if k != "env"},
        }

        logger.info("MCP server connected: id=%s, name=%s, transport=%s", server_id, name, transport)
        return server_id

    async def disconnect_server(self, server_id: str) -> None:
        """Disconnect from an MCP server.

        Args:
            server_id: 要断开的服务器 ID

        Raises:
            KeyError: server_id 不存在
        """
        client = self._connections.pop(server_id, None)
        if client is None:
            raise KeyError(f"MCP server not found: {server_id}")

        self._server_metadata.pop(server_id, None)
        await client.close()
        logger.info("MCP server disconnected: %s", server_id)

    async def list_tools(self, server_id: str | None = None) -> list[dict]:
        """List tools from a specific server or all connected servers.

        Args:
            server_id: 指定服务器 ID。None 表示列出所有已连接服务器的工具。

        Returns:
            工具信息字典列表，每个包含 name, description, input_schema, server_id 等。

        Raises:
            KeyError: 指定的 server_id 不存在
        """
        if server_id is not None:
            client = self._connections.get(server_id)
            if client is None:
                raise KeyError(f"MCP server not found: {server_id}")
            return await self._list_tools_from_client(server_id, client)

        # 列出所有服务器的工具
        all_tools: list[dict] = []
        for sid, client in self._connections.items():
            try:
                tools = await self._list_tools_from_client(sid, client)
                all_tools.extend(tools)
            except Exception as e:
                logger.warning("Failed to list tools from server %s: %s", sid, e)
        return all_tools

    async def call_tool(self, server_id: str, tool_name: str, arguments: dict) -> dict:
        """Call a tool on a specific MCP server.

        Args:
            server_id: 服务器 ID
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            包含 success, result, server_id, tool_name, timestamp 的字典

        Raises:
            KeyError: server_id 不存在
            ValueError: 工具执行失败（远端返回 isError）
        """
        client = self._connections.get(server_id)
        if client is None:
            raise KeyError(f"MCP server not found: {server_id}")

        try:
            result = await client.call_tool(tool_name, arguments)
            return {
                "success": True,
                "server_id": server_id,
                "tool_name": tool_name,
                "result": result,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        except ValueError:
            raise
        except Exception as e:
            logger.error("MCP tool call failed: server=%s, tool=%s, error=%s", server_id, tool_name, e)
            return {
                "success": False,
                "server_id": server_id,
                "tool_name": tool_name,
                "error": str(e),
                "timestamp": datetime.now(UTC).isoformat(),
            }

    async def discover_all(self) -> dict[str, list[dict]]:
        """Discover tools from all connected servers.

        Returns:
            server_id → 工具列表的映射
        """
        results: dict[str, list[dict]] = {}
        for server_id, client in self._connections.items():
            try:
                tools = await self._list_tools_from_client(server_id, client)
                results[server_id] = tools
            except Exception as e:
                logger.warning("Discovery failed for server %s: %s", server_id, e)
                results[server_id] = []
        return results

    def get_server_info(self, server_id: str) -> dict[str, Any] | None:
        """Get metadata for a connected server.

        Args:
            server_id: 服务器 ID

        Returns:
            服务器元数据字典，不存在返回 None
        """
        return self._server_metadata.get(server_id)

    def get_all_server_info(self) -> list[dict[str, Any]]:
        """Get metadata for all connected servers."""
        infos = []
        for server_id, meta in self._server_metadata.items():
            client = self._connections.get(server_id)
            info = dict(meta)
            info["server_id"] = server_id
            info["connected"] = client is not None and client.connected
            if client:
                info["stats"] = client.get_stats()
            infos.append(info)
        return infos

    async def health_check(self) -> dict[str, Any]:
        """Check health of all connected servers.

        Returns:
            健康状态字典
        """
        health: dict[str, Any] = {
            "status": "healthy",
            "sdk_available": MCP_SDK_AVAILABLE,
            "servers": {},
            "timestamp": datetime.now(UTC).isoformat(),
        }

        if not self._connections:
            health["status"] = "no_connections"
            return health

        unhealthy_count = 0
        for server_id, client in self._connections.items():
            try:
                is_healthy = await client.health_check()
                health["servers"][server_id] = {
                    "status": "healthy" if is_healthy else "unhealthy",
                    "name": self._server_metadata.get(server_id, {}).get("name", ""),
                }
                if not is_healthy:
                    unhealthy_count += 1
            except Exception as e:
                health["servers"][server_id] = {
                    "status": "error",
                    "error": str(e),
                    "name": self._server_metadata.get(server_id, {}).get("name", ""),
                }
                unhealthy_count += 1

        if unhealthy_count == len(self._connections):
            health["status"] = "unhealthy"
        elif unhealthy_count > 0:
            health["status"] = "degraded"

        return health

    async def shutdown(self) -> None:
        """Disconnect all servers and clean up resources."""
        for server_id in list(self._connections.keys()):
            try:
                await self.disconnect_server(server_id)
            except Exception as e:
                logger.warning("Error disconnecting server %s during shutdown: %s", server_id, e)
        logger.info("MCPClientManager shutdown complete")

    async def _list_tools_from_client(self, server_id: str, client: MCPClient) -> list[dict]:
        """从单个客户端获取工具列表并附加 server_id 元数据。"""
        raw_tools = await client.list_tools()
        tools = []
        for tool in raw_tools:
            tools.append({
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "input_schema": tool.get("input_schema", {}),
                "output_schema": tool.get("output_schema"),
                "annotations": tool.get("annotations", {}),
                "server_id": server_id,
                "server_name": self._server_metadata.get(server_id, {}).get("name", ""),
            })
        return tools


# ─── 全局单例 ─────────────────────────────────────────────────────────────────

_client_manager: MCPClientManager | None = None


def get_mcp_client_manager() -> MCPClientManager:
    """获取全局 MCPClientManager 实例（惰性初始化）。"""
    global _client_manager
    if _client_manager is None:
        _client_manager = MCPClientManager()
    return _client_manager


async def shutdown_mcp_client_manager() -> None:
    """关闭全局 MCPClientManager 并释放资源。"""
    global _client_manager
    if _client_manager is not None:
        await _client_manager.shutdown()
        _client_manager = None


__all__ = [
    "MCPClientManager",
    "get_mcp_client_manager",
    "shutdown_mcp_client_manager",
]
