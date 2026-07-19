"""MCP Manager - 统一管理MCP服务器和工具"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from backend.app.core.mcp.discovery import MCPToolDiscovery, MCPServerConfig
from backend.app.core.mcp.client import MCPClient
from backend.app.core.tool_registry import ToolCatalog

logger = logging.getLogger(__name__)


class MCPManager:
    """MCP管理器 - 统一管理MCP服务器和工具"""

    def __init__(
        self,
        tool_registry: ToolCatalog,
        config_path: Optional[str] = None,
        runtime_registry: Optional[Any] = None,
    ):
        """初始化MCP管理器

        Args:
            tool_registry: 工具 schema 目录（ToolCatalog）
            config_path: 配置文件路径
            runtime_registry: 唯一的运行时 ToolRegistry（core/tools.py）。
                传入后发现的 MCP 工具会桥接进 Agent 主循环执行表；
                缺省时回退 tool_registry.runtime_registry（显式组合绑定）。
        """
        self.tool_registry = tool_registry
        self.config_path = Path(config_path) if config_path else None
        self.config: Dict[str, Any] = {}

        # 初始化组件
        self.discovery = MCPToolDiscovery(tool_registry, runtime_registry=runtime_registry)

        # 状态
        self.initialized = False
        self.health_check_task: Optional[asyncio.Task] = None

    async def initialize(self) -> bool:
        """初始化MCP管理器

        Returns:
            是否成功初始化
        """
        try:
            # 加载配置
            if not self._load_config():
                logger.warning("No MCP configuration found, skipping MCP initialization")
                return False

            # 添加服务器
            servers = self.config.get("mcp_servers", [])
            if not servers:
                logger.warning("No MCP servers configured")
                return False

            logger.info(f"Initializing {len(servers)} MCP servers...")

            success_count = 0
            for server_config in servers:
                config = MCPServerConfig(
                    name=server_config["name"],
                    url=server_config.get("url", ""),
                    transport=server_config.get(
                        "transport",
                        "http" if server_config.get("url") else "stdio",
                    ),
                    command=server_config.get("command"),
                    args=server_config.get("args") or [],
                    env=server_config.get("env"),
                    cwd=server_config.get("cwd"),
                    headers=server_config.get("headers"),
                    enabled=server_config.get("enabled", True),
                    auto_register=server_config.get("auto_register", True),
                    timeout=server_config.get("timeout", 30.0),
                    max_retries=server_config.get("max_retries", 3),
                    tags=server_config.get("tags", []),
                    risk_level=server_config.get("risk_level"),
                )

                if await self.discovery.add_server(config):
                    # 客户端已由 discovery 持有（self.discovery.servers[name]），
                    # execute_tool 时按工具的 mcp_server 元数据路由到对应 client，
                    # 无需再注册到独立的 adapter。
                    success_count += 1

            logger.info(
                f"MCP initialization complete: {success_count}/{len(servers)} servers connected"
            )

            # 启动健康检查（如果启用）
            if self.config.get("monitoring", {}).get("enable_health_check", True):
                self._start_health_check()

            self.initialized = True
            return success_count > 0

        except Exception as e:
            logger.error(f"Failed to initialize MCP manager: {e}")

            # 根据配置决定是否抛出异常
            on_error = self.config.get("global", {}).get("on_discovery_error", "warn")
            if on_error == "fail":
                raise
            return False

    def _load_config(self) -> bool:
        """加载配置文件

        Returns:
            是否成功加载
        """
        if not self.config_path:
            # 尝试默认路径
            default_paths = [
                Path("config/mcp_servers.yaml"),
                Path("config/mcp_servers.yml"),
                Path("mcp_servers.yaml"),
            ]

            for path in default_paths:
                if path.exists():
                    self.config_path = path
                    break

        if not self.config_path or not self.config_path.exists():
            logger.info("No MCP configuration file found")
            return False

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f) or {}

            logger.info(f"Loaded MCP configuration from {self.config_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to load MCP configuration: {e}")
            return False

    async def refresh_tools(
        self,
        server_name: Optional[str] = None,
    ) -> Dict[str, int]:
        """刷新工具列表

        Args:
            server_name: 指定服务器名称，None表示刷新所有

        Returns:
            服务器名称到刷新工具数量的映射
        """
        if not self.initialized:
            logger.warning("MCP manager not initialized")
            return {}

        return await self.discovery.refresh_tools(server_name)

    async def execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
    ) -> Any:
        """执行MCP工具

        Args:
            tool_name: 工具名称
            args: 工具参数

        Returns:
            工具执行结果
        """
        if not self.initialized:
            raise RuntimeError("MCP manager not initialized")

        # 从工具注册表获取工具schema
        tool_schema = self.tool_registry.get(tool_name)
        if not tool_schema:
            raise ValueError(f"Tool {tool_name} not found")

        # 执行路由：首选 discovery 的路由表（注册时写入，唯一事实来源）；
        # 回退到工具 schema 的 metadata（旧调用方/测试使用的契约）。
        server_name: Optional[str] = None
        mcp_tool_name: str = tool_name
        route = self.discovery.resolve_route(tool_name)
        if route is not None:
            server_name, mcp_tool_name = route
        else:
            metadata = getattr(tool_schema, "metadata", None) or {}
            server_name = metadata.get("mcp_server")
            mcp_tool_name = metadata.get("mcp_tool_name", tool_name)
        if not server_name:
            raise ValueError(
                f"Tool {tool_name} is not an MCP-discovered tool "
                f"(no discovery route; missing 'mcp_server' metadata)"
            )

        client = self.discovery.servers.get(server_name)
        if client is None:
            raise ValueError(
                f"MCP server '{server_name}' for tool {tool_name} is not connected"
            )

        return await client.call_tool(mcp_tool_name, args)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息

        Returns:
            统计信息字典
        """
        stats = {
            "initialized": self.initialized,
            "servers": self.discovery.get_server_stats(),
            "tools_registered": len(self.tool_registry.list_all()),
        }

        # 添加MCP工具统计
        mcp_tools = [
            t for t in self.tool_registry.list_all()
            if "mcp" in t.tags
        ]
        stats["mcp_tools_count"] = len(mcp_tools)

        return stats

    async def health_check(self) -> Dict[str, Any]:
        """健康检查

        Returns:
            健康状态
        """
        health = {
            "status": "healthy" if self.initialized else "not_initialized",
            "servers": {},
        }

        if not self.initialized:
            return health

        # 检查每个服务器
        for server_name, client in self.discovery.servers.items():
            try:
                is_healthy = await client.health_check()
                health["servers"][server_name] = {
                    "status": "healthy" if is_healthy else "unhealthy",
                    "stats": client.get_stats(),
                }
            except Exception as e:
                health["servers"][server_name] = {
                    "status": "error",
                    "error": str(e),
                }

        # 更新总体状态
        unhealthy_count = sum(
            1 for s in health["servers"].values()
            if s["status"] != "healthy"
        )

        if unhealthy_count == len(health["servers"]):
            health["status"] = "unhealthy"
        elif unhealthy_count > 0:
            health["status"] = "degraded"

        return health

    def ping(self) -> bool:
        """轻量级存活探测

        与 health_check() 不同，ping() 不发起网络请求，仅返回管理器
        是否已初始化，用于快速、廉价的存活检查（如就绪探针）。

        Returns:
            True 表示管理器已初始化且就绪，否则 False
        """
        return self.initialized

    def pong(self) -> Dict[str, Any]:
        """对 ping 的响应——返回管理器的存活信息

        与 ping() 配对使用：ping() 仅返回布尔值用于快速检查；
        pong() 返回带时间戳和摘要的响应数据，可用于回声测试、
        监控仪表板或诊断输出。同样不发起网络请求。

        Returns:
            包含响应信息的字典：
                - message: 固定字符串 "pong"
                - initialized: 管理器是否已初始化
                - timestamp: ISO 8601 格式的当前时间戳
                - server_count: 已注册服务器数量
        """
        from datetime import datetime, timezone

        return {
            "message": "pong",
            "initialized": self.initialized,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "server_count": len(self.discovery.servers) if self.initialized else 0,
        }

    def _start_health_check(self) -> None:
        """启动健康检查任务"""
        interval = self.config.get("monitoring", {}).get(
            "health_check_interval", 60
        )

        async def health_check_loop():
            while True:
                try:
                    await asyncio.sleep(interval)
                    health = await self.health_check()

                    if health["status"] != "healthy":
                        logger.warning(f"MCP health check: {health['status']}")

                        # 记录不健康的服务器
                        for name, status in health["servers"].items():
                            if status["status"] != "healthy":
                                logger.warning(
                                    f"MCP server {name} is {status['status']}"
                                )

                except Exception as e:
                    logger.error(f"Health check error: {e}")

        self.health_check_task = asyncio.create_task(health_check_loop())
        logger.info(f"Started MCP health check (interval: {interval}s)")

    async def shutdown(self) -> None:
        """关闭MCP管理器"""
        logger.info("Shutting down MCP manager...")

        # 停止健康检查
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass

        # 关闭所有服务器连接
        await self.discovery.close_all()

        self.initialized = False
        logger.info("MCP manager shutdown complete")


# 全局MCP管理器实例
_mcp_manager: Optional[MCPManager] = None


def get_mcp_manager() -> Optional[MCPManager]:
    """获取全局MCP管理器实例

    Returns:
        MCP管理器实例，未初始化返回None
    """
    return _mcp_manager


async def initialize_mcp_manager(
    tool_registry: ToolCatalog,
    config_path: Optional[str] = None,
    runtime_registry: Optional[Any] = None,
) -> Optional[MCPManager]:
    """初始化全局MCP管理器

    Args:
        tool_registry: 工具 schema 目录（ToolCatalog）
        config_path: 配置文件路径
        runtime_registry: 唯一的运行时 ToolRegistry（core/tools.py）。
            传入后 MCP 发现的工具会桥接进 Agent 主循环执行表（P1-01）。

    Returns:
        MCP管理器实例，初始化失败返回None
    """
    global _mcp_manager

    if _mcp_manager is not None:
        logger.warning("MCP manager already initialized")
        return _mcp_manager

    manager = MCPManager(tool_registry, config_path, runtime_registry=runtime_registry)

    if await manager.initialize():
        _mcp_manager = manager
        logger.info("Global MCP manager initialized successfully")
        return manager
    else:
        logger.warning("MCP manager initialization failed or skipped")
        return None


async def shutdown_mcp_manager() -> None:
    """关闭全局MCP管理器"""
    global _mcp_manager

    if _mcp_manager:
        await _mcp_manager.shutdown()
        _mcp_manager = None
