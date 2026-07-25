"""P1-01 端到端连通测试：真实 stdio MCP server → 发现 → 双写注册 → 主循环可调用。

链路验证：
1. MCPClient 以 stdio 传输拉起官方 SDK 写的最小 MCP server（
   tests/mcp_fixtures/stdio_echo_server.py），完成 initialize 握手与
   tools/list 发现；
2. 发现的工具同时写入 ToolCatalog（schema 目录）与运行时 ToolRegistry
   （Agent 主循环执行表）——P1-01 的核心断点修复；
3. 经 ``ToolRegistry.execute``（AgentLoop 主循环同一咽喉点）真实调用
   远端工具并拿到结果；``definitions_for_llm`` 可见（LLM 可选中）；
4. 风险映射单轨：名称含破坏性关键词的工具在目录侧为 ToolRiskLevel.HIGH、
   运行时侧为 RiskLevel.HIGH；默认策略（enable_high_risk_tools=False）
   下被策略引擎拦截并要求审批（审批策略统一裁决，无第二套权限轨道）；
5. remove_server 后桥接工具从两侧清理，主循环不会再调到断连服务器。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from backend.app.core.contracts import RiskLevel, RunContext
from backend.app.core.mcp.discovery import MCPServerConfig, MCPToolDiscovery
from backend.app.core.mcp.manager import MCPManager
from backend.app.core.tool_registry import ToolCatalog
from backend.app.core.tool_schema import ToolRiskLevel
from backend.app.core.tools import ToolRegistry

SERVER_SCRIPT = (
    Path(__file__).resolve().parent / "mcp_fixtures" / "stdio_echo_server.py"
)


@pytest.fixture
def catalog() -> ToolCatalog:
    return ToolCatalog()


@pytest.fixture
def runtime_registry() -> ToolRegistry:
    # 默认策略引擎：enable_high_risk_tools=False —— 高风险工具须审批，
    # 用于验证 MCP 工具的审批策略由运行时策略引擎统一裁决。
    return ToolRegistry()


@pytest.fixture
def stdio_config() -> MCPServerConfig:
    return MCPServerConfig(
        name="e2e_stdio",
        transport="stdio",
        command=sys.executable,
        args=[str(SERVER_SCRIPT)],
        auto_register=True,
        timeout=30.0,
        max_retries=1,
    )


@pytest.mark.timeout(45)
class TestStdioEndToEnd:
    """发现 → 注册（双写）→ Agent 主循环可调用 的全链路。"""

    @pytest.mark.asyncio
    async def test_stdio_config_validation(self):
        """stdio 配置缺 command 时显式报错（不静默降级）。"""
        with pytest.raises(ValueError, match="command is required"):
            MCPServerConfig(name="bad", transport="stdio")
        with pytest.raises(ValueError, match="url is required"):
            MCPServerConfig(name="bad2", transport="http")

    @pytest.mark.asyncio
    async def test_discover_register_and_call_via_main_loop(
        self, catalog, runtime_registry, stdio_config
    ):
        discovery = MCPToolDiscovery(catalog, runtime_registry=runtime_registry)
        try:
            ok = await discovery.add_server(stdio_config)
            assert ok is True, "stdio MCP server 连接/握手失败"

            # --- 1. 目录侧：schema 已注册，风险/参数未静默丢弃 ---
            catalog_tool = catalog.get("mcp_e2e_stdio_echo")
            assert catalog_tool is not None
            assert catalog_tool.risk_level == ToolRiskLevel.LOW
            param_names = [p.name for p in catalog_tool.parameters]
            assert "text" in param_names, "input_schema 应转换为 parameters"

            # --- 2. 运行时侧：工具桥接进主循环执行表，LLM 可见 ---
            assert runtime_registry.get("mcp_e2e_stdio_echo") is not None
            llm_names = [
                d["function"]["name"]
                for d in runtime_registry.definitions_for_llm()
            ]
            assert "mcp_e2e_stdio_echo" in llm_names
            assert "mcp_e2e_stdio_add" in llm_names
            assert "mcp_e2e_stdio_delete_file" in llm_names

            # --- 3. 主循环同一咽喉点 execute 真实调用远端工具 ---
            context = RunContext()
            record = await runtime_registry.execute(
                context, "mcp_e2e_stdio_echo", {"text": "hello-mcp"}
            )
            assert record.success, f"echo 调用失败: {record.error}"
            assert "hello-mcp" in str(record.output)

            add_record = await runtime_registry.execute(
                context, "mcp_e2e_stdio_add", {"a": 2, "b": 40}
            )
            assert add_record.success, f"add 调用失败: {add_record.error}"
            assert "42" in str(add_record.output)

            # --- 4. 风险模型统一：目录/运行时两侧一致映射为 HIGH ---
            assert (
                catalog.get("mcp_e2e_stdio_delete_file").risk_level
                == ToolRiskLevel.HIGH
            )
            assert (
                runtime_registry.get("mcp_e2e_stdio_delete_file").risk_level
                == RiskLevel.HIGH
            )

            # --- 5. 审批策略统一：默认策略拦截 HIGH 风险并要求审批 ---
            blocked = await runtime_registry.execute(
                context, "mcp_e2e_stdio_delete_file", {"path": "/tmp/x"}
            )
            assert blocked.success is False
            assert "requires approval" in (blocked.error or "")
            assert blocked.policy.requires_approval is True
        finally:
            await discovery.close_all()

        # --- 6. 服务器下线后：两侧工具清理，主循环调不到 ---
        assert runtime_registry.get("mcp_e2e_stdio_echo") is None
        assert catalog.get("mcp_e2e_stdio_echo") is None

    @pytest.mark.asyncio
    async def test_manager_execute_tool_uses_discovery_route(
        self, catalog, runtime_registry, stdio_config
    ):
        """MCPManager.execute_tool 经发现层路由表（非 metadata）执行。"""
        manager = MCPManager(catalog, runtime_registry=runtime_registry)
        manager.initialized = True
        try:
            ok = await manager.discovery.add_server(stdio_config)
            assert ok is True

            result = await manager.execute_tool(
                "mcp_e2e_stdio_echo", {"text": "via-manager"}
            )
            assert "via-manager" in str(result)

            # 未知工具显式报错
            with pytest.raises(ValueError, match="not found"):
                await manager.execute_tool("mcp_e2e_stdio_nope", {})
        finally:
            await manager.shutdown()

    @pytest.mark.asyncio
    async def test_catalog_binding_fallback(self, stdio_config):
        """不显式传 runtime_registry 时回退到目录的显式组合绑定。"""
        bound_catalog = ToolCatalog()
        runtime = ToolRegistry()
        bound_catalog.bind_runtime_registry(runtime)

        discovery = MCPToolDiscovery(bound_catalog)  # 未显式传 runtime_registry
        try:
            ok = await discovery.add_server(stdio_config)
            assert ok is True
            # 经 bind 的运行时注册表同样收到桥接工具
            assert runtime.get("mcp_e2e_stdio_echo") is not None
        finally:
            await discovery.close_all()

    @pytest.mark.asyncio
    async def test_refresh_is_idempotent(self, catalog, runtime_registry, stdio_config):
        """重复发现/刷新不报错（目录走 upgrade，运行时覆盖注册）。"""
        discovery = MCPToolDiscovery(catalog, runtime_registry=runtime_registry)
        try:
            assert await discovery.add_server(stdio_config) is True
            first = await discovery.discover_and_register_tools("e2e_stdio")
            second = await discovery.refresh_tools("e2e_stdio")
            assert first >= 3
            assert second["e2e_stdio"] >= 3
            # 目录中同一工具仍只有一条当前版本
            names = [t.name for t in catalog.list_all()]
            assert names.count("mcp_e2e_stdio_echo") == 1
        finally:
            await discovery.close_all()


@pytest.mark.timeout(45)
class TestStreamableHttpEndToEnd:
    """Streamable HTTP 传输的真实连通验证（uvicorn + FastMCP HTTP app）。"""

    @pytest.mark.asyncio
    async def test_http_transport_discover_and_call(
        self, catalog, runtime_registry
    ):
        import asyncio

        import uvicorn

        # 复用夹具里的 FastMCP 实例（模块级定义，导入无副作用）
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from mcp_fixtures.stdio_echo_server import mcp as fastmcp_app

        app = fastmcp_app.streamable_http_app()
        config = uvicorn.Config(
            app, host="127.0.0.1", port=0, log_level="error"
        )
        server = uvicorn.Server(config)
        serve_task = asyncio.create_task(server.serve())
        try:
            # 等待监听就绪并取到实际端口
            for _ in range(200):
                if server.started:
                    break
                await asyncio.sleep(0.05)
            assert server.started, "uvicorn 未能启动"
            socket = server.servers[0].sockets[0]
            port = socket.getsockname()[1]
            url = f"http://127.0.0.1:{port}/mcp"

            discovery = MCPToolDiscovery(
                catalog, runtime_registry=runtime_registry
            )
            try:
                ok = await discovery.add_server(
                    MCPServerConfig(
                        name="e2e_http",
                        transport="http",
                        url=url,
                        auto_register=True,
                        timeout=15.0,
                        max_retries=1,
                    )
                )
                assert ok is True, "Streamable HTTP MCP server 连接/握手失败"

                # 发现 + 双写注册
                assert catalog.get("mcp_e2e_http_echo") is not None
                assert runtime_registry.get("mcp_e2e_http_echo") is not None

                # 主循环咽喉点真实调用
                record = await runtime_registry.execute(
                    RunContext(), "mcp_e2e_http_echo", {"text": "over-http"}
                )
                assert record.success, f"HTTP 传输调用失败: {record.error}"
                assert "over-http" in str(record.output)
            finally:
                await discovery.close_all()
        finally:
            server.should_exit = True
            await asyncio.wait_for(serve_task, timeout=15)
            # 给 sse_starlette 的 shutdown watcher 一个收尾窗口（仅降噪）。
            await asyncio.sleep(0.1)
