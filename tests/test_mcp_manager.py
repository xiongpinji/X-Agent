"""Unit tests for MCP Manager module.

Tests cover:
- Manager initialization and configuration loading
- Server management and lifecycle
- Tool execution and registration
- Health checks and monitoring
- Shutdown and cleanup
- Global manager instance management
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from pathlib import Path
from typing import Dict, Any

from backend.app.core.mcp.manager import (
    MCPManager,
    initialize_mcp_manager,
    shutdown_mcp_manager,
    get_mcp_manager,
)
from backend.app.core.mcp.discovery import MCPServerConfig


@pytest.fixture
def mock_tool_registry():
    """Create a mock tool registry."""
    registry = MagicMock()
    registry.register = MagicMock()
    registry.get = MagicMock(return_value=MagicMock())
    registry.list_all = MagicMock(return_value=[])
    return registry


@pytest.fixture
def mock_config_file(tmp_path):
    """Create a temporary config file."""
    config_content = """
mcp_servers:
  - name: test_server
    url: http://localhost:8000
    enabled: true
    auto_register: true
    timeout: 30.0
    max_retries: 3
    tags:
      - test

monitoring:
  enable_health_check: true
  health_check_interval: 60

global:
  on_discovery_error: warn
"""
    config_file = tmp_path / "mcp_servers.yaml"
    config_file.write_text(config_content)
    return config_file


@pytest.fixture
def manager(mock_tool_registry, mock_config_file):
    """Create MCPManager instance."""
    return MCPManager(mock_tool_registry, str(mock_config_file))


@pytest.fixture(autouse=True)
def reset_global_manager():
    """Reset global manager instance before each test."""
    import backend.app.core.mcp.manager as manager_module
    manager_module._mcp_manager = None
    yield
    manager_module._mcp_manager = None


class TestMCPManagerInitialization:
    """Test MCPManager initialization."""

    def test_manager_creation(self, mock_tool_registry):
        """Test creating a manager instance."""
        manager = MCPManager(mock_tool_registry)

        assert manager.tool_registry == mock_tool_registry
        assert manager.initialized is False
        assert manager.health_check_task is None
        assert len(manager.config) == 0

    def test_manager_with_config_path(self, mock_tool_registry, mock_config_file):
        """Test creating a manager with config path."""
        manager = MCPManager(mock_tool_registry, str(mock_config_file))

        assert manager.config_path == mock_config_file

    def test_manager_components_initialized(self, manager):
        """Test that manager components are initialized."""
        assert manager.discovery is not None
        # adapter 已移除：多 server 路由由 execute_tool 按工具元数据
        # 定位到 discovery.servers 中的对应 client，不再经独立 adapter。
        assert manager.tool_registry is not None


class TestLoadConfig:
    """Test configuration loading."""

    def test_load_config_from_file(self, manager):
        """Test loading configuration from file."""
        result = manager._load_config()

        assert result is True
        assert "mcp_servers" in manager.config
        assert len(manager.config["mcp_servers"]) > 0

    def test_load_config_file_not_found(self, mock_tool_registry):
        """Test loading config when file doesn't exist."""
        manager = MCPManager(mock_tool_registry, "/nonexistent/path.yaml")

        result = manager._load_config()

        assert result is False

    def test_load_config_no_path_specified(self, mock_tool_registry, tmp_path, monkeypatch):
        """Test loading config when no path is specified."""
        # 默认搜索路径是相对 CWD 的；隔离到空目录，避免命中仓根 .mcp.json
        monkeypatch.chdir(tmp_path)
        manager = MCPManager(mock_tool_registry)

        result = manager._load_config()

        assert result is False

    def test_load_config_invalid_yaml(self, mock_tool_registry, tmp_path):
        """Test loading invalid YAML configuration."""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text("invalid: yaml: content: [")

        manager = MCPManager(mock_tool_registry, str(config_file))
        result = manager._load_config()

        assert result is False

    def test_load_config_default_paths(self, mock_tool_registry, tmp_path):
        """Test loading config from default paths."""
        # Create config in default location
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "mcp_servers.yaml"
        config_file.write_text("mcp_servers: []")

        # Change to temp directory
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            manager = MCPManager(mock_tool_registry)
            result = manager._load_config()
            assert result is True
        finally:
            os.chdir(original_cwd)


class TestManagerInitialize:
    """Test manager initialization."""

    @pytest.mark.asyncio
    async def test_initialize_success(self, manager):
        """Test successful manager initialization."""
        # add_server populates discovery.servers as a side effect in real code;
        # mocking it means we must seed the registry the manager reads afterward.
        manager.discovery.servers["test_server"] = MagicMock()
        with patch.object(
            manager.discovery, "add_server", new_callable=AsyncMock, return_value=True
        ):
            result = await manager.initialize()

        assert result is True
        assert manager.initialized is True

    @pytest.mark.asyncio
    async def test_initialize_no_config(self, mock_tool_registry):
        """Test initialization when no config is found."""
        manager = MCPManager(mock_tool_registry, "/nonexistent/path.yaml")

        result = await manager.initialize()

        assert result is False
        assert manager.initialized is False

    @pytest.mark.asyncio
    async def test_initialize_no_servers(self, mock_tool_registry, tmp_path):
        """Test initialization when no servers are configured."""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("mcp_servers: []")

        manager = MCPManager(mock_tool_registry, str(config_file))
        result = await manager.initialize()

        assert result is False

    @pytest.mark.asyncio
    async def test_initialize_partial_success(self, manager):
        """Test initialization with partial server success."""
        manager.discovery.servers["test_server"] = MagicMock()
        with patch.object(
            manager.discovery,
            "add_server",
            new_callable=AsyncMock,
            side_effect=[True, False],
        ):
            result = await manager.initialize()

        assert result is True
        assert manager.initialized is True

    @pytest.mark.asyncio
    async def test_initialize_all_servers_fail(self, manager):
        """Test initialization when all servers fail."""
        with patch.object(
            manager.discovery, "add_server", new_callable=AsyncMock, return_value=False
        ):
            result = await manager.initialize()

        assert result is False

    @pytest.mark.asyncio
    async def test_initialize_with_health_check(self, manager):
        """Test that health check is started during initialization."""
        manager.discovery.servers["test_server"] = MagicMock()
        with patch.object(
            manager.discovery, "add_server", new_callable=AsyncMock, return_value=True
        ):
            with patch.object(manager, "_start_health_check") as mock_health_check:
                await manager.initialize()

                mock_health_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_exception_handling_warn(self, manager):
        """Test exception handling with 'warn' error policy."""
        with patch.object(
            manager.discovery,
            "add_server",
            new_callable=AsyncMock,
            side_effect=Exception("Test error"),
        ):
            result = await manager.initialize()

        assert result is False

    @pytest.mark.asyncio
    async def test_initialize_exception_handling_fail(self, mock_tool_registry, tmp_path):
        """Test exception handling with 'fail' error policy."""
        config_content = """
mcp_servers:
  - name: test_server
    url: http://localhost:8000

global:
  on_discovery_error: fail
"""
        config_file = tmp_path / "mcp_servers.yaml"
        config_file.write_text(config_content)

        manager = MCPManager(mock_tool_registry, str(config_file))

        with patch.object(
            manager.discovery,
            "add_server",
            new_callable=AsyncMock,
            side_effect=Exception("Test error"),
        ):
            with pytest.raises(Exception):
                await manager.initialize()


class TestRefreshTools:
    """Test tool refresh functionality."""

    @pytest.mark.asyncio
    async def test_refresh_tools_not_initialized(self, manager):
        """Test refreshing tools when manager is not initialized."""
        result = await manager.refresh_tools()

        assert result == {}

    @pytest.mark.asyncio
    async def test_refresh_specific_server(self, manager):
        """Test refreshing tools for a specific server."""
        manager.initialized = True

        with patch.object(
            manager.discovery,
            "refresh_tools",
            new_callable=AsyncMock,
            return_value={"test_server": 5},
        ):
            result = await manager.refresh_tools("test_server")

        assert result == {"test_server": 5}

    @pytest.mark.asyncio
    async def test_refresh_all_servers(self, manager):
        """Test refreshing tools for all servers."""
        manager.initialized = True

        with patch.object(
            manager.discovery,
            "refresh_tools",
            new_callable=AsyncMock,
            return_value={"server1": 3, "server2": 2},
        ):
            result = await manager.refresh_tools()

        assert len(result) == 2


class TestExecuteTool:
    """Test tool execution."""

    @pytest.mark.asyncio
    async def test_execute_tool_not_initialized(self, manager):
        """Test executing tool when manager is not initialized."""
        with pytest.raises(RuntimeError, match="not initialized"):
            await manager.execute_tool("test_tool", {})

    @pytest.mark.asyncio
    async def test_execute_tool_success(self, manager):
        """Test successfully executing a tool routes to the right MCP client."""
        manager.initialized = True
        # 工具 schema 通过 metadata 标明来源 server 与原始工具名
        mock_tool_schema = MagicMock()
        mock_tool_schema.metadata = {
            "mcp_server": "srv1",
            "mcp_tool_name": "test_tool",
        }
        manager.tool_registry.get = MagicMock(return_value=mock_tool_schema)

        # 对应 server 的 client 由 discovery 持有
        mock_client = MagicMock()
        mock_client.call_tool = AsyncMock(return_value={"result": "success"})
        manager.discovery.servers = {"srv1": mock_client}

        result = await manager.execute_tool("test_tool", {"arg": "value"})

        assert result == {"result": "success"}
        mock_client.call_tool.assert_called_once_with("test_tool", {"arg": "value"})

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self, manager):
        """Test executing a tool that doesn't exist."""
        manager.initialized = True
        manager.tool_registry.get = MagicMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await manager.execute_tool("nonexistent_tool", {})

    @pytest.mark.asyncio
    async def test_execute_tool_with_args(self, manager):
        """Test executing a tool forwards args to the routed MCP client."""
        manager.initialized = True
        mock_tool_schema = MagicMock()
        mock_tool_schema.metadata = {
            "mcp_server": "srv1",
            "mcp_tool_name": "write_file",
        }
        manager.tool_registry.get = MagicMock(return_value=mock_tool_schema)

        test_args = {"path": "/test/path", "content": "test content"}

        mock_client = MagicMock()
        mock_client.call_tool = AsyncMock(return_value={"status": "ok"})
        manager.discovery.servers = {"srv1": mock_client}

        await manager.execute_tool("write_file", test_args)

        mock_client.call_tool.assert_called_once_with("write_file", test_args)


class TestGetStats:
    """Test statistics retrieval."""

    def test_get_stats_not_initialized(self, manager):
        """Test getting stats when manager is not initialized."""
        stats = manager.get_stats()

        assert stats["initialized"] is False
        assert stats["tools_registered"] == 0

    def test_get_stats_initialized(self, manager):
        """Test getting stats when manager is initialized."""
        manager.initialized = True
        mock_tool = MagicMock()
        mock_tool.tags = ["mcp"]

        manager.tool_registry.list_all = MagicMock(return_value=[mock_tool])

        stats = manager.get_stats()

        assert stats["initialized"] is True
        assert stats["mcp_tools_count"] == 1

    def test_get_stats_mixed_tools(self, manager):
        """Test getting stats with mixed tool types."""
        manager.initialized = True

        mcp_tool = MagicMock()
        mcp_tool.tags = ["mcp"]

        other_tool = MagicMock()
        other_tool.tags = ["other"]

        manager.tool_registry.list_all = MagicMock(
            return_value=[mcp_tool, other_tool]
        )

        stats = manager.get_stats()

        assert stats["tools_registered"] == 2
        assert stats["mcp_tools_count"] == 1


class TestHealthCheck:
    """Test health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_not_initialized(self, manager):
        """Test health check when manager is not initialized."""
        health = await manager.health_check()

        assert health["status"] == "not_initialized"
        assert len(health["servers"]) == 0

    @pytest.mark.asyncio
    async def test_health_check_all_healthy(self, manager):
        """Test health check when all servers are healthy."""
        manager.initialized = True

        mock_client = AsyncMock()
        mock_client.health_check = AsyncMock(return_value=True)
        mock_client.get_stats = MagicMock(return_value={})

        manager.discovery.servers = {"server1": mock_client}

        health = await manager.health_check()

        assert health["status"] == "healthy"
        assert health["servers"]["server1"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_all_unhealthy(self, manager):
        """Test health check when all servers are unhealthy."""
        manager.initialized = True

        mock_client = AsyncMock()
        mock_client.health_check = AsyncMock(return_value=False)
        mock_client.get_stats = MagicMock(return_value={})

        manager.discovery.servers = {"server1": mock_client}

        health = await manager.health_check()

        assert health["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_health_check_degraded(self, manager):
        """Test health check with degraded status."""
        manager.initialized = True

        healthy_client = AsyncMock()
        healthy_client.health_check = AsyncMock(return_value=True)
        healthy_client.get_stats = MagicMock(return_value={})

        unhealthy_client = AsyncMock()
        unhealthy_client.health_check = AsyncMock(return_value=False)
        unhealthy_client.get_stats = MagicMock(return_value={})

        manager.discovery.servers = {
            "healthy": healthy_client,
            "unhealthy": unhealthy_client,
        }

        health = await manager.health_check()

        assert health["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_health_check_exception_handling(self, manager):
        """Test health check exception handling."""
        manager.initialized = True

        mock_client = AsyncMock()
        mock_client.health_check = AsyncMock(side_effect=Exception("Connection error"))

        manager.discovery.servers = {"error_server": mock_client}

        health = await manager.health_check()

        assert health["servers"]["error_server"]["status"] == "error"
        assert "error" in health["servers"]["error_server"]


class TestHealthCheckLoop:
    """Test health check background task."""

    @pytest.mark.asyncio
    async def test_start_health_check(self, manager):
        """Test starting health check task."""
        manager.config = {
            "monitoring": {"health_check_interval": 1}
        }

        manager._start_health_check()

        assert manager.health_check_task is not None
        assert not manager.health_check_task.done()

        # Clean up
        manager.health_check_task.cancel()
        try:
            await manager.health_check_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_health_check_loop_execution(self, manager):
        """Test health check loop executes periodically."""
        manager.initialized = True
        manager.config = {
            "monitoring": {"health_check_interval": 0.1}
        }

        mock_client = AsyncMock()
        mock_client.health_check = AsyncMock(return_value=True)
        mock_client.get_stats = MagicMock(return_value={})

        manager.discovery.servers = {"test": mock_client}

        with patch.object(manager, "health_check", new_callable=AsyncMock) as mock_hc:
            manager._start_health_check()

            # Wait for at least one execution
            await asyncio.sleep(0.2)

            # Clean up
            manager.health_check_task.cancel()
            try:
                await manager.health_check_task
            except asyncio.CancelledError:
                pass


class TestShutdown:
    """Test manager shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown_success(self, manager):
        """Test successful manager shutdown."""
        manager.initialized = True

        with patch.object(
            manager.discovery, "close_all", new_callable=AsyncMock
        ) as mock_close:
            await manager.shutdown()

        assert manager.initialized is False
        mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_with_health_check_task(self, manager):
        """Test shutdown with active health check task."""
        manager.initialized = True
        manager.health_check_task = asyncio.create_task(asyncio.sleep(10))

        with patch.object(
            manager.discovery, "close_all", new_callable=AsyncMock
        ):
            await manager.shutdown()

        assert manager.health_check_task.cancelled()

    @pytest.mark.asyncio
    async def test_shutdown_not_initialized(self, manager):
        """Test shutdown when manager is not initialized."""
        manager.initialized = False

        with patch.object(
            manager.discovery, "close_all", new_callable=AsyncMock
        ) as mock_close:
            await manager.shutdown()

        mock_close.assert_called_once()


class TestGlobalManagerFunctions:
    """Test global manager instance functions."""

    def test_get_mcp_manager_none(self):
        """Test getting manager when none is initialized."""
        manager = get_mcp_manager()

        assert manager is None

    @pytest.mark.asyncio
    async def test_initialize_mcp_manager_success(self, mock_tool_registry, mock_config_file):
        """Test initializing global manager."""
        with patch.object(
            MCPManager, "initialize", new_callable=AsyncMock, return_value=True
        ):
            manager = await initialize_mcp_manager(
                mock_tool_registry, str(mock_config_file)
            )

        assert manager is not None
        assert get_mcp_manager() == manager

    @pytest.mark.asyncio
    async def test_initialize_mcp_manager_already_initialized(
        self, mock_tool_registry, mock_config_file
    ):
        """Test initializing when manager is already initialized."""
        with patch.object(
            MCPManager, "initialize", new_callable=AsyncMock, return_value=True
        ):
            manager1 = await initialize_mcp_manager(
                mock_tool_registry, str(mock_config_file)
            )
            manager2 = await initialize_mcp_manager(
                mock_tool_registry, str(mock_config_file)
            )

        assert manager1 == manager2

    @pytest.mark.asyncio
    async def test_initialize_mcp_manager_failure(self, mock_tool_registry, mock_config_file):
        """Test initializing when initialization fails."""
        with patch.object(
            MCPManager, "initialize", new_callable=AsyncMock, return_value=False
        ):
            manager = await initialize_mcp_manager(
                mock_tool_registry, str(mock_config_file)
            )

        assert manager is None
        assert get_mcp_manager() is None

    @pytest.mark.asyncio
    async def test_shutdown_mcp_manager(self, mock_tool_registry, mock_config_file):
        """Test shutting down global manager."""
        with patch.object(
            MCPManager, "initialize", new_callable=AsyncMock, return_value=True
        ):
            await initialize_mcp_manager(mock_tool_registry, str(mock_config_file))

        with patch.object(MCPManager, "shutdown", new_callable=AsyncMock):
            await shutdown_mcp_manager()

        assert get_mcp_manager() is None

    @pytest.mark.asyncio
    async def test_shutdown_mcp_manager_not_initialized(self):
        """Test shutting down when manager is not initialized."""
        await shutdown_mcp_manager()

        assert get_mcp_manager() is None
