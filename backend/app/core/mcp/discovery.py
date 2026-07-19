"""MCP Tool Discovery - 自动发现和注册MCP工具"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from backend.app.core.mcp.client import MCPClient
from backend.app.core.mcp.protocol import MCPTool
from backend.app.core.tool_registry import ToolCatalog
from backend.app.core.tool_schema import (
    ToolSchema,
    ToolCategory,
    ToolRiskLevel,
    ToolStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """MCP服务器配置"""

    name: str
    url: str
    enabled: bool = True
    auto_register: bool = True
    timeout: float = 30.0
    max_retries: int = 3
    tags: List[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class MCPToolDiscovery:
    """自动发现和注册MCP工具"""

    def __init__(self, tool_registry: ToolCatalog):
        """初始化MCP工具发现器

        Args:
            tool_registry: 工具注册表实例
        """
        self.tool_registry = tool_registry
        self.servers: Dict[str, MCPClient] = {}
        self.discovered_tools: Dict[str, MCPTool] = {}

    async def add_server(self, config: MCPServerConfig) -> bool:
        """添加MCP服务器

        Args:
            config: 服务器配置

        Returns:
            是否成功添加
        """
        if not config.enabled:
            logger.info(f"Server {config.name} is disabled, skipping")
            return False

        try:
            client = MCPClient(
                server_url=config.url,
                timeout=config.timeout,
                max_retries=config.max_retries,
            )

            # 健康检查
            if not await client.health_check():
                logger.error(f"Health check failed for server {config.name}")
                return False

            self.servers[config.name] = client
            logger.info(f"Added MCP server: {config.name} at {config.url}")

            # 自动注册工具
            if config.auto_register:
                await self.discover_and_register_tools(config.name, config.tags)

            return True

        except Exception as e:
            logger.error(f"Failed to add server {config.name}: {e}")
            return False

    async def discover_tools(self, server_name: str) -> List[MCPTool]:
        """从指定服务器发现工具

        Args:
            server_name: 服务器名称

        Returns:
            发现的工具列表
        """
        if server_name not in self.servers:
            raise ValueError(f"Server {server_name} not found")

        client = self.servers[server_name]

        try:
            tools_data = await client.list_tools()
            tools = []

            for tool_data in tools_data:
                tool = MCPTool(
                    name=tool_data.get("name"),
                    description=tool_data.get("description", ""),
                    input_schema=tool_data.get("input_schema", {}),
                    output_schema=tool_data.get("output_schema"),
                    tags=tool_data.get("tags", []),
                )
                tools.append(tool)

                # 缓存工具定义
                tool_key = f"{server_name}:{tool.name}"
                self.discovered_tools[tool_key] = tool

            logger.info(f"Discovered {len(tools)} tools from {server_name}")
            return tools

        except Exception as e:
            logger.error(f"Failed to discover tools from {server_name}: {e}")
            return []

    async def discover_all_tools(self) -> Dict[str, List[MCPTool]]:
        """从所有服务器发现工具

        Returns:
            服务器名称到工具列表的映射
        """
        results = {}

        for server_name in self.servers:
            tools = await self.discover_tools(server_name)
            results[server_name] = tools

        return results

    async def register_tool(
        self,
        server_name: str,
        mcp_tool: MCPTool,
        tags: Optional[List[str]] = None,
    ) -> Optional[ToolSchema]:
        """注册单个MCP工具到工具注册表

        Args:
            server_name: 服务器名称
            mcp_tool: MCP工具定义
            tags: 额外的标签

        Returns:
            注册的工具schema，失败返回None
        """
        try:
            # 转换为ToolSchema
            tool_schema = self._convert_to_tool_schema(
                server_name, mcp_tool, tags
            )

            # 注册到工具注册表
            registered = self.tool_registry.register(tool_schema)

            logger.info(
                f"Registered MCP tool: {mcp_tool.name} from {server_name}"
            )
            return registered

        except Exception as e:
            logger.error(
                f"Failed to register tool {mcp_tool.name} from {server_name}: {e}"
            )
            return None

    async def discover_and_register_tools(
        self,
        server_name: str,
        tags: Optional[List[str]] = None,
    ) -> int:
        """发现并注册指定服务器的所有工具

        Args:
            server_name: 服务器名称
            tags: 额外的标签

        Returns:
            成功注册的工具数量
        """
        tools = await self.discover_tools(server_name)
        registered_count = 0

        for tool in tools:
            if await self.register_tool(server_name, tool, tags):
                registered_count += 1

        logger.info(
            f"Registered {registered_count}/{len(tools)} tools from {server_name}"
        )
        return registered_count

    async def discover_and_register_all(
        self,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, int]:
        """发现并注册所有服务器的工具

        Args:
            tags: 额外的标签

        Returns:
            服务器名称到注册工具数量的映射
        """
        results = {}

        for server_name in self.servers:
            count = await self.discover_and_register_tools(server_name, tags)
            results[server_name] = count

        return results

    def _convert_to_tool_schema(
        self,
        server_name: str,
        mcp_tool: MCPTool,
        extra_tags: Optional[List[str]] = None,
    ) -> ToolSchema:
        """将MCP工具转换为ToolSchema

        Args:
            server_name: 服务器名称
            mcp_tool: MCP工具定义
            extra_tags: 额外的标签

        Returns:
            ToolSchema实例
        """
        # 合并标签
        tags = ["mcp", f"mcp:{server_name}"] + mcp_tool.tags
        if extra_tags:
            tags.extend(extra_tags)

        # 推断工具类别
        category = self._infer_category(mcp_tool)

        # 推断风险级别
        risk_level = self._infer_risk_level(mcp_tool)

        # 创建ToolSchema
        tool_schema = ToolSchema(
            name=f"mcp_{server_name}_{mcp_tool.name}",
            display_name=mcp_tool.name,
            description=mcp_tool.description,
            version="1.0.0",
            category=category,
            risk_level=risk_level,
            status=ToolStatus.ACTIVE,
            input_schema=mcp_tool.input_schema,
            output_schema=mcp_tool.output_schema or {},
            tags=tags,
            metadata={
                "mcp_server": server_name,
                "mcp_tool_name": mcp_tool.name,
                "source": "mcp_discovery",
            },
        )

        return tool_schema

    def _infer_category(self, mcp_tool: MCPTool) -> ToolCategory:
        """根据工具信息推断类别

        Args:
            mcp_tool: MCP工具定义

        Returns:
            工具类别
        """
        name_lower = mcp_tool.name.lower()
        desc_lower = mcp_tool.description.lower()

        # 基于名称和描述的关键词匹配
        if any(kw in name_lower or kw in desc_lower for kw in ["file", "read", "write", "directory"]):
            return ToolCategory.FILE_SYSTEM
        elif any(kw in name_lower or kw in desc_lower for kw in ["database", "sql", "query"]):
            return ToolCategory.DATABASE
        elif any(kw in name_lower or kw in desc_lower for kw in ["http", "api", "request", "web"]):
            return ToolCategory.WEB
        elif any(kw in name_lower or kw in desc_lower for kw in ["search", "find", "lookup"]):
            return ToolCategory.SEARCH
        elif any(kw in name_lower or kw in desc_lower for kw in ["code", "execute", "run"]):
            return ToolCategory.CODE_EXECUTION
        else:
            return ToolCategory.UTILITY

    def _infer_risk_level(self, mcp_tool: MCPTool) -> ToolRiskLevel:
        """根据工具信息推断风险级别

        Args:
            mcp_tool: MCP工具定义

        Returns:
            风险级别
        """
        name_lower = mcp_tool.name.lower()
        desc_lower = mcp_tool.description.lower()

        # 高风险操作
        high_risk_keywords = ["delete", "remove", "drop", "execute", "run", "shell"]
        if any(kw in name_lower or kw in desc_lower for kw in high_risk_keywords):
            return ToolRiskLevel.HIGH

        # 中风险操作
        medium_risk_keywords = ["write", "update", "modify", "create"]
        if any(kw in name_lower or kw in desc_lower for kw in medium_risk_keywords):
            return ToolRiskLevel.MEDIUM

        # 默认低风险
        return ToolRiskLevel.LOW

    async def refresh_tools(self, server_name: Optional[str] = None) -> Dict[str, int]:
        """刷新工具列表

        Args:
            server_name: 指定服务器名称，None表示刷新所有

        Returns:
            服务器名称到刷新工具数量的映射
        """
        if server_name:
            if server_name not in self.servers:
                raise ValueError(f"Server {server_name} not found")
            count = await self.discover_and_register_tools(server_name)
            return {server_name: count}
        else:
            return await self.discover_and_register_all()

    async def remove_server(self, server_name: str) -> bool:
        """移除MCP服务器

        Args:
            server_name: 服务器名称

        Returns:
            是否成功移除
        """
        if server_name not in self.servers:
            return False

        # 关闭客户端
        client = self.servers[server_name]
        await client.close()

        # 移除服务器
        del self.servers[server_name]

        # 移除相关工具（可选）
        # TODO: 实现工具清理逻辑

        logger.info(f"Removed MCP server: {server_name}")
        return True

    def get_server_stats(self) -> Dict[str, Any]:
        """获取服务器统计信息

        Returns:
            统计信息字典
        """
        stats = {
            "total_servers": len(self.servers),
            "servers": {},
        }

        for server_name, client in self.servers.items():
            stats["servers"][server_name] = client.get_stats()

        return stats

    async def close_all(self) -> None:
        """关闭所有服务器连接"""
        for server_name in list(self.servers.keys()):
            await self.remove_server(server_name)

        logger.info("Closed all MCP server connections")
