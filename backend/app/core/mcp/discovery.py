"""MCP Tool Discovery - 自动发现和注册MCP工具

P1-01 / P1-10 裁决：

* 发现层通过真实 MCP 协议客户端（官方 SDK，见 ``client.py``）拉取工具列表；
* 每个发现的工具**双写**：
  1. ``ToolCatalog``（schema 目录：版本/状态/生命周期）；
  2. 唯一的运行时 ``ToolRegistry``（``core/tools.py``，Agent 主循环执行表），
     以可执行 handler 形式桥接——主循环由此真正调得到 MCP 工具；
* 风险等级经 ``catalog_risk_to_runtime`` 唯一换算入口映射，审批策略由运行时
  注册表的策略引擎/审批存储统一裁决（不再存在第二套权限轨道）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from backend.app.core.mcp.client import MCPClient
from backend.app.core.mcp.protocol import MCPTool
from backend.app.core.tool_registry import (
    ToolCatalog,
    catalog_risk_to_runtime,
    max_catalog_risk,
)
from backend.app.core.tool_schema import (
    ToolCategory,
    ToolParameter,
    ToolReturn,
    ToolRiskLevel,
    ToolSchema,
    ToolStatus,
)

logger = logging.getLogger(__name__)

_VALID_TRANSPORTS = ("http", "stdio")


@dataclass
class MCPServerConfig:
    """MCP服务器配置

    transport:
        ``"http"`` — Streamable HTTP（需 ``url``）；
        ``"stdio"`` — 子进程 stdio（需 ``command``，可配 ``args``/``env``/``cwd``）。
    risk_level:
        可选的整站风险等级下限（如 ``"high"``），与按工具推断值取较高者；
        审批策略由运行时 ToolRegistry 的策略引擎统一决定。
    """

    name: str
    url: str = ""
    transport: str = "http"
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None
    cwd: str | None = None
    headers: dict[str, str] | None = None
    enabled: bool = True
    auto_register: bool = True
    timeout: float = 30.0
    max_retries: int = 3
    tags: list[str] = None
    risk_level: str | None = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        self.transport = (self.transport or "http").lower()
        if self.transport not in _VALID_TRANSPORTS:
            raise ValueError(
                f"MCP server '{self.name}': unsupported transport "
                f"{self.transport!r} (expected one of {_VALID_TRANSPORTS})"
            )
        if self.transport == "http" and not self.url:
            raise ValueError(
                f"MCP server '{self.name}': url is required for http transport"
            )
        if self.transport == "stdio" and not self.command:
            raise ValueError(
                f"MCP server '{self.name}': command is required for stdio transport"
            )


class MCPToolDiscovery:
    """自动发现和注册MCP工具（目录 + 运行时注册表双写）"""

    def __init__(
        self,
        tool_registry: ToolCatalog,
        runtime_registry: Any | None = None,
        server_whitelist: list[str] | None = None,
    ):
        """初始化MCP工具发现器

        Args:
            tool_registry: 工具 schema 目录（ToolCatalog）
            runtime_registry: 唯一的运行时 ToolRegistry（core/tools.py）。
                缺省时尝试 ``tool_registry.runtime_registry``（显式组合绑定）；
                仍为 None 则只写目录、不桥接（向后兼容，但主循环调不到）。
            server_whitelist: P2-04 服务器白名单。None=允许所有（向后兼容），
                非空列表则仅允许列表中的服务器名连接。
        """
        self.tool_registry = tool_registry
        if runtime_registry is None:
            runtime_registry = getattr(tool_registry, "runtime_registry", None)
        self.runtime_registry = runtime_registry
        self._server_whitelist = set(server_whitelist) if server_whitelist is not None else None
        self.servers: dict[str, MCPClient] = {}
        self.discovered_tools: dict[str, MCPTool] = {}
        # registered_name -> (server_name, mcp_tool_name)：执行路由的唯一事实来源。
        self._tool_routes: dict[str, tuple[str, str]] = {}
        # server_name -> [registered_name]：用于服务器下线时的工具清理。
        self._server_tools: dict[str, list[str]] = {}
        # server_name -> MCPServerConfig：整站配置（含风险等级下限）。
        self._server_configs: dict[str, MCPServerConfig] = {}

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

        # P2-04: MCP 服务器白名单 — 仅允许已配置的服务器连接
        if self._server_whitelist is not None and config.name not in self._server_whitelist:
            logger.warning(
                "P2-04: MCP server '%s' rejected — not in whitelist %s",
                config.name, self._server_whitelist,
            )
            return False

        try:
            client = MCPClient(
                server_url=config.url or None,
                timeout=config.timeout,
                max_retries=config.max_retries,
                transport=config.transport,
                command=config.command,
                args=list(config.args),
                env=config.env,
                cwd=config.cwd,
                headers=config.headers,
            )

            # 健康检查（initialize 握手 + tools/list）
            if not await client.health_check():
                logger.error(f"Health check failed for server {config.name}")
                return False

            self.servers[config.name] = client
            self._server_configs[config.name] = config
            logger.info(
                f"Added MCP server: {config.name} "
                f"(transport={config.transport}, target={config.url or config.command})"
            )

            # 自动注册工具
            if config.auto_register:
                await self.discover_and_register_tools(config.name, config.tags)

            return True

        except Exception as e:
            logger.error(f"Failed to add server {config.name}: {e}")
            return False

    async def discover_tools(self, server_name: str) -> list[MCPTool]:
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
                    annotations=tool_data.get("annotations") or {},
                )

                # P2-04: PromptGuard — scan MCP tool description for injection
                from backend.app.core.prompt_guard.engine import get_prompt_guard
                _guard = get_prompt_guard()
                desc_scan = _guard.scan_mcp_description(server_name, tool.description)
                if desc_scan.is_malicious:
                    logger.warning(
                        "P2-04 PromptGuard rejected MCP tool '%s' from '%s': "
                        "description injection detected (confidence=%.2f)",
                        tool.name, server_name, desc_scan.confidence,
                    )
                    continue  # skip this tool

                tools.append(tool)

                # 缓存工具定义
                tool_key = f"{server_name}:{tool.name}"
                self.discovered_tools[tool_key] = tool

            logger.info(f"Discovered {len(tools)} tools from {server_name}")
            return tools

        except Exception as e:
            logger.error(f"Failed to discover tools from {server_name}: {e}")
            return []

    async def discover_all_tools(self) -> dict[str, list[MCPTool]]:
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
        tags: list[str] | None = None,
    ) -> ToolSchema | None:
        """注册单个MCP工具：目录（ToolCatalog）+ 运行时注册表（桥接）

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

            # 注册到工具目录（重复注册走 upgrade，保证 refresh 幂等）
            registered = self._register_into_catalog(tool_schema)

            # 记录执行路由（唯一事实来源，替代易丢失的 metadata 字段）。
            # 用本地构建的 tool_schema.name 而非注册表返回值（mock 注册表
            # 的返回对象可能没有 .name 属性）。
            self._tool_routes[tool_schema.name] = (server_name, mcp_tool.name)
            server_tools = self._server_tools.setdefault(server_name, [])
            if tool_schema.name not in server_tools:
                server_tools.append(tool_schema.name)

            # 桥接进运行时 ToolRegistry —— Agent 主循环由此可调用
            self._bridge_into_runtime_registry(server_name, mcp_tool, tool_schema)

            logger.info(
                f"Registered MCP tool: {mcp_tool.name} from {server_name}"
            )
            return registered

        except Exception as e:
            logger.error(
                f"Failed to register tool {mcp_tool.name} from {server_name}: {e}"
            )
            return None

    def _register_into_catalog(self, tool_schema: ToolSchema) -> ToolSchema:
        """写入 ToolCatalog；同版本重复注册时按 upgrade 处理（refresh 幂等）。"""
        try:
            return self.tool_registry.register(tool_schema)
        except ValueError as exc:
            if "already registered" not in str(exc):
                raise
            if not self.tool_registry.upgrade(tool_schema.name, tool_schema):
                raise
            return tool_schema

    def _bridge_into_runtime_registry(
        self,
        server_name: str,
        mcp_tool: MCPTool,
        tool_schema: ToolSchema,
    ) -> None:
        """把 MCP 工具以可执行 handler 注册进运行时 ToolRegistry。

        风险等级经唯一换算入口映射；审批/策略由运行时注册表的策略引擎统一
        裁决（高/危风险工具的审批单轨：ApprovalStore）。
        """
        if self.runtime_registry is None:
            logger.warning(
                "runtime_registry 未绑定：MCP 工具 %s 仅写入目录，"
                "Agent 主循环将无法调用（请经 MCPManager/initialize_mcp_manager "
                "传入 runtime_registry）",
                tool_schema.name,
            )
            return

        handler = self._make_tool_handler(server_name, mcp_tool.name)
        input_schema = (
            mcp_tool.input_schema
            if isinstance(mcp_tool.input_schema, dict) and mcp_tool.input_schema
            else {"type": "object", "properties": {}}
        )
        self.runtime_registry.register(
            tool_schema.name,
            mcp_tool.description
            or f"MCP tool {mcp_tool.name} (server: {server_name})",
            handler,
            risk_level=catalog_risk_to_runtime(tool_schema.risk_level),
            required_scope=f"tool:{tool_schema.name}",
            parameters_schema=input_schema,
        )

    def _make_tool_handler(self, server_name: str, mcp_tool_name: str):
        """生成运行时 handler：经执行路由定位 client 并发起真实 MCP 调用。"""

        async def _mcp_tool_handler(**arguments: Any) -> Any:
            client = self.servers.get(server_name)
            if client is None:
                raise RuntimeError(
                    f"MCP server '{server_name}' is not connected; "
                    f"tool '{mcp_tool_name}' is unavailable"
                )
            return await client.call_tool(mcp_tool_name, arguments)

        _mcp_tool_handler.__name__ = f"mcp_handler_{server_name}_{mcp_tool_name}"
        return _mcp_tool_handler

    def resolve_route(self, registered_name: str) -> tuple[str, str] | None:
        """查询注册工具名的执行路由 (server_name, mcp_tool_name)。"""
        return self._tool_routes.get(registered_name)

    async def discover_and_register_tools(
        self,
        server_name: str,
        tags: list[str] | None = None,
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
        tags: list[str] | None = None,
    ) -> dict[str, int]:
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
        extra_tags: list[str] | None = None,
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
        tags = ["mcp", f"mcp:{server_name}", *mcp_tool.tags]
        if extra_tags:
            tags.extend(extra_tags)

        # 推断工具类别
        category = self._infer_category(mcp_tool)

        # 推断风险级别（annotations + 关键词 + 整站下限，取保守值）
        risk_level = self._infer_risk_level(mcp_tool)
        server_cfg = self._server_configs.get(server_name)
        if server_cfg and server_cfg.risk_level:
            try:
                floor = ToolRiskLevel(server_cfg.risk_level.lower())
                risk_level = max_catalog_risk(risk_level, floor)
            except ValueError:
                logger.warning(
                    "MCP server %s: invalid risk_level override %r, ignored",
                    server_name,
                    server_cfg.risk_level,
                )

        registered_name = f"mcp_{server_name}_{mcp_tool.name}"

        # input_schema (JSON Schema) → parameters 列表，不再静默丢弃。
        parameters = self._json_schema_to_parameters(mcp_tool.input_schema)
        returns = ToolReturn(
            type=(
                str(mcp_tool.output_schema.get("type", "object"))
                if isinstance(mcp_tool.output_schema, dict)
                else "object"
            ),
            result_schema=(
                mcp_tool.output_schema
                if isinstance(mcp_tool.output_schema, dict)
                else {}
            ),
        )

        # 创建ToolSchema。
        # 注意：ToolSchema 没有 display_name / metadata 字段，MCP 来源信息
        # 由 discovery 的 _tool_routes 映射权威持有（tags 亦含 mcp:<server>），
        # 不在此处传递会被 pydantic 静默丢弃的多余字段。
        tool_schema = ToolSchema(
            name=registered_name,
            description=mcp_tool.description,
            version="1.0.0",
            category=category,
            parameters=parameters,
            returns=returns,
            risk_level=risk_level,
            permissions=[f"tool:{registered_name}"],
            requires_approval=risk_level
            in (ToolRiskLevel.HIGH, ToolRiskLevel.CRITICAL),
            # MCP 工具在远端服务器进程内执行，不受本进程沙箱约束：
            # 标注 restricted 而非 isolated，避免虚构隔离保证。
            sandbox_level="restricted",
            status=ToolStatus.ACTIVE,
            tags=tags,
        )

        return tool_schema

    @staticmethod
    def _json_schema_to_parameters(
        input_schema: Any,
    ) -> list[ToolParameter]:
        """JSON Schema object → ToolParameter 列表（保留字段名/类型/必填）。"""
        if not isinstance(input_schema, dict):
            return []
        properties = input_schema.get("properties") or {}
        if not isinstance(properties, dict):
            return []
        required = set(input_schema.get("required") or [])
        parameters: list[ToolParameter] = []
        for prop_name, prop_schema in properties.items():
            if not isinstance(prop_schema, dict):
                prop_schema = {}
            parameters.append(
                ToolParameter(
                    name=str(prop_name),
                    type=str(prop_schema.get("type", "string")),
                    description=str(prop_schema.get("description", "")),
                    required=prop_name in required,
                    default=prop_schema.get("default"),
                )
            )
        return parameters

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
        """根据工具信息推断风险级别（保守：多来源信号取最高）

        信号来源：
        * 官方 ToolAnnotations（destructiveHint / readOnlyHint，服务器声明）；
        * 名称/描述关键词（本地兜底，防止服务器虚报低风险）。

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

        # 服务器声明的破坏性操作
        annotations = getattr(mcp_tool, "annotations", None) or {}
        if annotations.get("destructiveHint") is True:
            return ToolRiskLevel.HIGH

        # 中风险操作
        medium_risk_keywords = ["write", "update", "modify", "create"]
        if any(kw in name_lower or kw in desc_lower for kw in medium_risk_keywords):
            return ToolRiskLevel.MEDIUM

        # 服务器声明只读 → LOW；否则默认 LOW
        return ToolRiskLevel.LOW

    async def refresh_tools(self, server_name: str | None = None) -> dict[str, int]:
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
        """移除MCP服务器（含其桥接工具的清理）

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
        self._server_configs.pop(server_name, None)

        # 清理该服务器注册的工具：运行时注册表 + 目录 + 路由，
        # 保证主循环不会调到已断连的服务器。
        for registered_name in self._server_tools.pop(server_name, []):
            if self.runtime_registry is not None:
                try:
                    self.runtime_registry.unregister(registered_name)
                except Exception as e:
                    logger.warning(
                        "Failed to unregister %s from runtime registry: %s",
                        registered_name,
                        e,
                    )
            try:
                self.tool_registry.unregister(registered_name)
            except Exception as e:
                logger.warning(
                    "Failed to unregister %s from tool catalog: %s",
                    registered_name,
                    e,
                )
            self._tool_routes.pop(registered_name, None)

        # 清理发现缓存
        for key in [k for k in self.discovered_tools if k.startswith(f"{server_name}:")]:
            del self.discovered_tools[key]

        logger.info(f"Removed MCP server: {server_name}")
        return True

    def get_server_stats(self) -> dict[str, Any]:
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
