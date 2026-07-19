"""
MCP端到端集成测试 - 验证完整的工具发现、注册和调用流程

测试场景：
1. MCP服务器连接和工具发现
2. 工具注册到ToolRegistry
3. 工具调用和结果返回
4. 多服务器场景
5. 错误恢复场景
6. 资源清理验证
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import yaml

from backend.app.core.mcp.manager import MCPManager
from backend.app.core.mcp.discovery import MCPToolDiscovery, MCPServerConfig
from backend.app.core.mcp.client import MCPClient
from backend.app.core.mcp.protocol import MCPTool, MCPRequest, MCPResponse
from backend.app.core.tool_registry import ToolRegistry
from backend.app.core.tool_schema import (
    ToolSchema,
    ToolCategory,
    ToolRiskLevel,
    ToolStatus,
)

logger = logging.getLogger(__name__)


class MockMCPServer:
    """模拟MCP服务器用于测试"""

    def __init__(self, name: str = "test_server", tools: Optional[List[Dict[str, Any]]] = None):
        self.name = name
        self.tools = tools or self._default_tools()
        self.call_history: List[Dict[str, Any]] = []

    def _default_tools(self) -> List[Dict[str, Any]]:
        """返回默认的测试工具"""
        return [
            {
                "name": "read_file",
                "description": "Read file content",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path"}
                    },
                    "required": ["path"],
                },
                "output_schema": {"type": "string"},
                "tags": ["file", "read"],
            },
            {
                "name": "write_file",
                "description": "Write content to file",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
                "output_schema": {"type": "boolean"},
                "tags": ["file", "write"],
            },
            {
                "name": "search_web",
                "description": "Search the web",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"],
                },
                "output_schema": {"type": "array"},
                "tags": ["search", "web"],
            },
        ]

    async def list_tools(self) -> List[Dict[str, Any]]:
        """返回工具列表"""
        return self.tools

    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """调用工具"""
        self.call_history.append({"tool": tool_name, "args": args})

        # 模拟不同工具的返回值
        if tool_name == "read_file":
            return f"Content of {args.get('path', 'unknown')}"
        elif tool_name == "write_file":
            return True
        elif tool_name == "search_web":
            return [
                {"title": "Result 1", "url": "http://example.com/1"},
                {"title": "Result 2", "url": "http://example.com/2"},
            ]
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    async def health_check(self) -> bool:
        """健康检查"""
        return True


@pytest_asyncio.fixture
async def tool_registry():
    """创建工具注册表"""
    registry = ToolRegistry()
    yield registry


@pytest_asyncio.fixture
async def mock_mcp_client():
    """创建模拟MCP客户端"""
    client = AsyncMock(spec=MCPClient)
    client.server_url = "http://localhost:8001"
    client.timeout = 30.0
    client.max_retries = 3

    # 模拟list_tools
    client.list_tools = AsyncMock(
        return_value=[
            {
                "name": "read_file",
                "description": "Read file content",
                "input_schema": {"type": "object"},
                "output_schema": {"type": "string"},
                "tags": ["file"],
            },
            {
                "name": "write_file",
                "description": "Write content to file",
                "input_schema": {"type": "object"},
                "output_schema": {"type": "boolean"},
                "tags": ["file"],
            },
        ]
    )

    # 模拟call_tool
    async def mock_call_tool(tool_name: str, args: Dict[str, Any]) -> Any:
        if tool_name == "read_file":
            return f"Content of {args.get('path')}"
        elif tool_name == "write_file":
            return True
        raise ValueError(f"Unknown tool: {tool_name}")

    client.call_tool = AsyncMock(side_effect=mock_call_tool)

    # 模拟health_check
    client.health_check = AsyncMock(return_value=True)

    # 模拟close
    client.close = AsyncMock()

    # 模拟get_stats
    client.get_stats = MagicMock(
        return_value={
            "connection_pool": {"active": 0, "max": 10, "available": 10},
            "cache": {"size": 0, "ttl_seconds": 300},
        }
    )

    yield client


@pytest_asyncio.fixture
async def mcp_manager(tool_registry):
    """创建MCP管理器"""
    manager = MCPManager(tool_registry)
    yield manager
    await manager.shutdown()


class TestMCPServerConnection:
    """测试MCP服务器连接"""

    @pytest.mark.asyncio
    async def test_add_single_server(self, tool_registry, mock_mcp_client):
        """测试添加单个MCP服务器"""
        discovery = MCPToolDiscovery(tool_registry)

        config = MCPServerConfig(
            name="test_server",
            url="http://localhost:8001",
            enabled=True,
            auto_register=False,
        )

        with patch(
            "backend.app.core.mcp.discovery.MCPClient",
            return_value=mock_mcp_client,
        ):
            result = await discovery.add_server(config)

        assert result is True
        assert "test_server" in discovery.servers
        assert discovery.servers["test_server"] == mock_mcp_client

    @pytest.mark.asyncio
    async def test_add_disabled_server(self, tool_registry):
        """测试添加禁用的服务器"""
        discovery = MCPToolDiscovery(tool_registry)

        config = MCPServerConfig(
            name="disabled_server",
            url="http://localhost:8002",
            enabled=False,
        )

        result = await discovery.add_server(config)

        assert result is False
        assert "disabled_server" not in discovery.servers

    @pytest.mark.asyncio
    async def test_add_server_health_check_failure(self, tool_registry):
        """测试服务器健康检查失败"""
        discovery = MCPToolDiscovery(tool_registry)

        mock_client = AsyncMock(spec=MCPClient)
        mock_client.health_check = AsyncMock(return_value=False)

        config = MCPServerConfig(
            name="unhealthy_server",
            url="http://localhost:8003",
            enabled=True,
        )

        with patch(
            "backend.app.core.mcp.discovery.MCPClient",
            return_value=mock_client,
        ):
            result = await discovery.add_server(config)

        assert result is False
        assert "unhealthy_server" not in discovery.servers


class TestToolDiscovery:
    """测试工具发现"""

    @pytest.mark.asyncio
    async def test_discover_tools_from_server(self, tool_registry, mock_mcp_client):
        """测试从服务器发现工具"""
        discovery = MCPToolDiscovery(tool_registry)
        discovery.servers["test_server"] = mock_mcp_client

        tools = await discovery.discover_tools("test_server")

        assert len(tools) == 2
        assert tools[0].name == "read_file"
        assert tools[1].name == "write_file"
        assert "file" in tools[0].tags

    @pytest.mark.asyncio
    async def test_discover_tools_caching(self, tool_registry, mock_mcp_client):
        """测试工具发现缓存"""
        discovery = MCPToolDiscovery(tool_registry)
        discovery.servers["test_server"] = mock_mcp_client

        # 第一次发现
        tools1 = await discovery.discover_tools("test_server")
        assert len(tools1) == 2

        # 验证缓存
        assert "test_server:read_file" in discovery.discovered_tools
        assert "test_server:write_file" in discovery.discovered_tools

        # 第二次发现应该使用缓存
        tools2 = await discovery.discover_tools("test_server")
        assert len(tools2) == 2

    @pytest.mark.asyncio
    async def test_discover_tools_from_nonexistent_server(self, tool_registry):
        """测试从不存在的服务器发现工具"""
        discovery = MCPToolDiscovery(tool_registry)

        with pytest.raises(ValueError, match="Server .* not found"):
            await discovery.discover_tools("nonexistent_server")

    @pytest.mark.asyncio
    async def test_discover_all_tools(self, tool_registry, mock_mcp_client):
        """测试从所有服务器发现工具"""
        discovery = MCPToolDiscovery(tool_registry)

        mock_client2 = AsyncMock(spec=MCPClient)
        mock_client2.list_tools = AsyncMock(
            return_value=[
                {
                    "name": "search_web",
                    "description": "Search the web",
                    "input_schema": {"type": "object"},
                    "tags": ["search"],
                }
            ]
        )

        discovery.servers["server1"] = mock_mcp_client
        discovery.servers["server2"] = mock_client2

        results = await discovery.discover_all_tools()

        assert "server1" in results
        assert "server2" in results
        assert len(results["server1"]) == 2
        assert len(results["server2"]) == 1


class TestToolRegistration:
    """测试工具注册"""

    @pytest.mark.asyncio
    async def test_register_single_tool(self, tool_registry, mock_mcp_client):
        """测试注册单个工具"""
        discovery = MCPToolDiscovery(tool_registry)
        discovery.servers["test_server"] = mock_mcp_client

        mcp_tool = MCPTool(
            name="read_file",
            description="Read file content",
            input_schema={"type": "object"},
            tags=["file"],
        )

        result = await discovery.register_tool("test_server", mcp_tool)

        assert result is not None
        assert result.name == "mcp_test_server_read_file"
        assert "mcp" in result.tags
        assert "mcp:test_server" in result.tags

    @pytest.mark.asyncio
    async def test_register_tool_category_inference(self, tool_registry, mock_mcp_client):
        """测试工具类别推断"""
        discovery = MCPToolDiscovery(tool_registry)
        discovery.servers["test_server"] = mock_mcp_client

        # 文件操作工具
        file_tool = MCPTool(
            name="read_file",
            description="Read file content",
            input_schema={"type": "object"},
        )

        result = await discovery.register_tool("test_server", file_tool)
        assert result.category == ToolCategory.FILE_SYSTEM

        # 数据库工具
        db_tool = MCPTool(
            name="query_database",
            description="Execute SQL query",
            input_schema={"type": "object"},
        )

        result = await discovery.register_tool("test_server", db_tool)
        assert result.category == ToolCategory.DATABASE

    @pytest.mark.asyncio
    async def test_register_tool_risk_level_inference(self, tool_registry, mock_mcp_client):
        """测试工具风险级别推断"""
        discovery = MCPToolDiscovery(tool_registry)
        discovery.servers["test_server"] = mock_mcp_client

        # 低风险工具
        read_tool = MCPTool(
            name="read_file",
            description="Read file content",
            input_schema={"type": "object"},
        )

        result = await discovery.register_tool("test_server", read_tool)
        assert result.risk_level == ToolRiskLevel.LOW

        # 中风险工具
        write_tool = MCPTool(
            name="write_file",
            description="Write content to file",
            input_schema={"type": "object"},
        )

        result = await discovery.register_tool("test_server", write_tool)
        assert result.risk_level == ToolRiskLevel.MEDIUM

        # 高风险工具
        delete_tool = MCPTool(
            name="delete_file",
            description="Delete file from system",
            input_schema={"type": "object"},
        )

        result = await discovery.register_tool("test_server", delete_tool)
        assert result.risk_level == ToolRiskLevel.HIGH

    @pytest.mark.asyncio
    async def test_discover_and_register_tools(self, tool_registry, mock_mcp_client):
        """测试发现并注册工具"""
        discovery = MCPToolDiscovery(tool_registry)
        discovery.servers["test_server"] = mock_mcp_client

        count = await discovery.discover_and_register_tools("test_server")

        assert count == 2
        assert len(tool_registry.list_all()) == 2

        # 验证工具已注册
        tools = tool_registry.list_all()
        tool_names = [t.name for t in tools]
        assert "mcp_test_server_read_file" in tool_names
        assert "mcp_test_server_write_file" in tool_names


class TestMultiServerScenario:
    """测试多服务器场景"""

    @pytest.mark.asyncio
    async def test_multiple_servers_initialization(self, tool_registry):
        """测试多个服务器初始化"""
        discovery = MCPToolDiscovery(tool_registry)

        mock_client1 = AsyncMock(spec=MCPClient)
        mock_client1.list_tools = AsyncMock(
            return_value=[
                {
                    "name": "read_file",
                    "description": "Read file",
                    "input_schema": {},
                    "tags": ["file"],
                }
            ]
        )
        mock_client1.health_check = AsyncMock(return_value=True)

        mock_client2 = AsyncMock(spec=MCPClient)
        mock_client2.list_tools = AsyncMock(
            return_value=[
                {
                    "name": "search_web",
                    "description": "Search web",
                    "input_schema": {},
                    "tags": ["search"],
                }
            ]
        )
        mock_client2.health_check = AsyncMock(return_value=True)

        configs = [
            MCPServerConfig(
                name="filesystem",
                url="http://localhost:8001",
                auto_register=True,
            ),
            MCPServerConfig(
                name="search",
                url="http://localhost:8002",
                auto_register=True,
            ),
        ]

        with patch(
            "backend.app.core.mcp.discovery.MCPClient",
            side_effect=[mock_client1, mock_client2],
        ):
            for config in configs:
                await discovery.add_server(config)

        assert len(discovery.servers) == 2
        assert "filesystem" in discovery.servers
        assert "search" in discovery.servers

    @pytest.mark.asyncio
    async def test_discover_and_register_all_servers(self, tool_registry):
        """测试从所有服务器发现并注册工具"""
        discovery = MCPToolDiscovery(tool_registry)

        mock_client1 = AsyncMock(spec=MCPClient)
        mock_client1.list_tools = AsyncMock(
            return_value=[
                {
                    "name": "read_file",
                    "description": "Read file",
                    "input_schema": {},
                    "tags": ["file"],
                }
            ]
        )

        mock_client2 = AsyncMock(spec=MCPClient)
        mock_client2.list_tools = AsyncMock(
            return_value=[
                {
                    "name": "search_web",
                    "description": "Search web",
                    "input_schema": {},
                    "tags": ["search"],
                }
            ]
        )

        discovery.servers["server1"] = mock_client1
        discovery.servers["server2"] = mock_client2

        results = await discovery.discover_and_register_all()

        assert results["server1"] == 1
        assert results["server2"] == 1
        assert len(tool_registry.list_all()) == 2


class TestToolExecution:
    """测试工具执行"""

    @pytest.mark.asyncio
    async def test_execute_tool_success(self, tool_registry, mock_mcp_client):
        """测试成功执行工具"""
        discovery = MCPToolDiscovery(tool_registry)
        discovery.servers["test_server"] = mock_mcp_client

        # 注册工具
        mcp_tool = MCPTool(
            name="read_file",
            description="Read file content",
            input_schema={"type": "object"},
        )
        await discovery.register_tool("test_server", mcp_tool)

        # 执行工具
        result = await mock_mcp_client.call_tool("read_file", {"path": "/tmp/test.txt"})

        assert result == "Content of /tmp/test.txt"
        mock_mcp_client.call_tool.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_tool_with_error(self, tool_registry, mock_mcp_client):
        """测试工具执行错误处理"""
        mock_client = AsyncMock(spec=MCPClient)
        mock_client.call_tool = AsyncMock(
            side_effect=ValueError("Tool execution failed")
        )

        with pytest.raises(ValueError, match="Tool execution failed"):
            await mock_client.call_tool("unknown_tool", {})


class TestErrorRecovery:
    """测试错误恢复"""

    @pytest.mark.asyncio
    async def test_server_connection_retry(self, tool_registry):
        """测试服务器连接重试"""
        discovery = MCPToolDiscovery(tool_registry)

        mock_client = AsyncMock(spec=MCPClient)
        # 第一次失败，第二次成功
        mock_client.health_check = AsyncMock(side_effect=[False, True])

        config = MCPServerConfig(
            name="retry_server",
            url="http://localhost:8001",
            max_retries=3,
        )

        with patch(
            "backend.app.core.mcp.discovery.MCPClient",
            return_value=mock_client,
        ):
            # 第一次添加失败
            result1 = await discovery.add_server(config)
            assert result1 is False

            # 重置mock并重试
            mock_client.health_check = AsyncMock(return_value=True)
            result2 = await discovery.add_server(config)
            assert result2 is True

    @pytest.mark.asyncio
    async def test_remove_server(self, tool_registry, mock_mcp_client):
        """测试移除服务器"""
        discovery = MCPToolDiscovery(tool_registry)
        discovery.servers["test_server"] = mock_mcp_client

        result = await discovery.remove_server("test_server")

        assert result is True
        assert "test_server" not in discovery.servers
        mock_mcp_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_nonexistent_server(self, tool_registry):
        """测试移除不存在的服务器"""
        discovery = MCPToolDiscovery(tool_registry)

        result = await discovery.remove_server("nonexistent")

        assert result is False


class TestMCPManagerIntegration:
    """测试MCP管理器集成"""

    @pytest.mark.asyncio
    async def test_manager_initialization_with_config(self, tool_registry, tmp_path):
        """测试使用配置文件初始化管理器"""
        # 创建临时配置文件
        config_file = tmp_path / "mcp_servers.yaml"
        config_data = {
            "mcp_servers": [
                {
                    "name": "test_server",
                    "url": "http://localhost:8001",
                    "enabled": True,
                    "auto_register": True,
                    "timeout": 30.0,
                    "max_retries": 3,
                    "tags": ["test"],
                }
            ],
            "monitoring": {"enable_health_check": False},
        }

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        manager = MCPManager(tool_registry, str(config_file))

        # 验证配置加载
        assert manager._load_config() is True
        assert "mcp_servers" in manager.config

    @pytest.mark.asyncio
    async def test_manager_health_check(self, tool_registry, mock_mcp_client):
        """测试管理器健康检查"""
        manager = MCPManager(tool_registry)
        manager.initialized = True
        manager.discovery.servers["test_server"] = mock_mcp_client

        health = await manager.health_check()

        assert health["status"] in ["healthy", "degraded", "unhealthy"]
        assert "servers" in health
        assert "test_server" in health["servers"]

    @pytest.mark.asyncio
    async def test_manager_get_stats(self, tool_registry, mock_mcp_client):
        """测试获取管理器统计信息"""
        manager = MCPManager(tool_registry)
        manager.initialized = True
        manager.discovery.servers["test_server"] = mock_mcp_client

        # 注册一些工具
        mcp_tool = MCPTool(
            name="test_tool",
            description="Test tool",
            input_schema={},
        )
        await manager.discovery.register_tool("test_server", mcp_tool)

        stats = manager.get_stats()

        assert stats["initialized"] is True
        assert stats["tools_registered"] >= 1
        assert "mcp_tools_count" in stats


class TestResourceCleanup:
    """测试资源清理"""

    @pytest.mark.asyncio
    async def test_close_all_servers(self, tool_registry):
        """测试关闭所有服务器"""
        discovery = MCPToolDiscovery(tool_registry)

        mock_client1 = AsyncMock(spec=MCPClient)
        mock_client2 = AsyncMock(spec=MCPClient)

        discovery.servers["server1"] = mock_client1
        discovery.servers["server2"] = mock_client2

        await discovery.close_all()

        assert len(discovery.servers) == 0
        mock_client1.close.assert_called_once()
        mock_client2.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_manager_shutdown(self, tool_registry, mock_mcp_client):
        """测试管理器关闭"""
        manager = MCPManager(tool_registry)
        manager.initialized = True
        manager.discovery.servers["test_server"] = mock_mcp_client

        await manager.shutdown()

        assert manager.initialized is False
        assert len(manager.discovery.servers) == 0

    @pytest.mark.asyncio
    async def test_manager_shutdown_with_health_check_task(self, tool_registry):
        """测试关闭带有健康检查任务的管理器"""
        manager = MCPManager(tool_registry)
        manager.initialized = True

        # 创建一个模拟的健康检查任务
        async def dummy_health_check():
            await asyncio.sleep(10)

        manager.health_check_task = asyncio.create_task(dummy_health_check())

        await manager.shutdown()

        assert manager.initialized is False
        assert manager.health_check_task.cancelled()


class TestEndToEndFlow:
    """端到端流程测试"""

    @pytest.mark.asyncio
    async def test_complete_mcp_workflow(self, tool_registry):
        """测试完整的MCP工作流"""
        # 1. 创建发现器
        discovery = MCPToolDiscovery(tool_registry)

        # 2. 创建模拟客户端
        mock_client = AsyncMock(spec=MCPClient)
        mock_client.list_tools = AsyncMock(
            return_value=[
                {
                    "name": "read_file",
                    "description": "Read file content",
                    "input_schema": {"type": "object"},
                    "tags": ["file"],
                },
                {
                    "name": "write_file",
                    "description": "Write content to file",
                    "input_schema": {"type": "object"},
                    "tags": ["file"],
                },
            ]
        )
        mock_client.health_check = AsyncMock(return_value=True)
        mock_client.close = AsyncMock()

        # 3. 添加服务器
        config = MCPServerConfig(
            name="filesystem",
            url="http://localhost:8001",
            auto_register=True,
        )

        with patch(
            "backend.app.core.mcp.discovery.MCPClient",
            return_value=mock_client,
        ):
            result = await discovery.add_server(config)
            assert result is True

        # 4. 验证工具已注册
        tools = tool_registry.list_all()
        assert len(tools) == 2

        tool_names = [t.name for t in tools]
        assert "mcp_filesystem_read_file" in tool_names
        assert "mcp_filesystem_write_file" in tool_names

        # 5. 验证工具属性
        read_tool = tool_registry.get("mcp_filesystem_read_file")
        assert read_tool is not None
        assert read_tool.category == ToolCategory.FILE_SYSTEM
        assert read_tool.risk_level == ToolRiskLevel.LOW
        assert "mcp" in read_tool.tags
        assert "mcp:filesystem" in read_tool.tags

        write_tool = tool_registry.get("mcp_filesystem_write_file")
        assert write_tool is not None
        assert write_tool.risk_level == ToolRiskLevel.MEDIUM

        # 6. 清理资源
        await discovery.close_all()
        assert len(discovery.servers) == 0

    @pytest.mark.asyncio
    async def test_multi_server_complete_workflow(self, tool_registry):
        """测试多服务器完整工作流"""
        discovery = MCPToolDiscovery(tool_registry)

        # 创建两个模拟客户端
        mock_fs_client = AsyncMock(spec=MCPClient)
        mock_fs_client.list_tools = AsyncMock(
            return_value=[
                {
                    "name": "read_file",
                    "description": "Read file",
                    "input_schema": {},
                    "tags": ["file"],
                }
            ]
        )
        mock_fs_client.health_check = AsyncMock(return_value=True)
        mock_fs_client.close = AsyncMock()

        mock_search_client = AsyncMock(spec=MCPClient)
        mock_search_client.list_tools = AsyncMock(
            return_value=[
                {
                    "name": "search_web",
                    "description": "Search web",
                    "input_schema": {},
                    "tags": ["search"],
                }
            ]
        )
        mock_search_client.health_check = AsyncMock(return_value=True)
        mock_search_client.close = AsyncMock()

        configs = [
            MCPServerConfig(
                name="filesystem",
                url="http://localhost:8001",
                auto_register=True,
            ),
            MCPServerConfig(
                name="search",
                url="http://localhost:8002",
                auto_register=True,
            ),
        ]

        with patch(
            "backend.app.core.mcp.discovery.MCPClient",
            side_effect=[mock_fs_client, mock_search_client],
        ):
            for config in configs:
                result = await discovery.add_server(config)
                assert result is True

        # 验证所有工具已注册
        tools = tool_registry.list_all()
        assert len(tools) == 2

        # 验证服务器统计
        stats = discovery.get_server_stats()
        assert stats["total_servers"] == 2
        assert "filesystem" in stats["servers"]
        assert "search" in stats["servers"]

        # 清理
        await discovery.close_all()
        assert len(discovery.servers) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
