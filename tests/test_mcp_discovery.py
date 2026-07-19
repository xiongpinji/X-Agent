"""Unit tests for MCP Tool Discovery module.

Tests cover:
- Tool discovery from MCP servers
- Tool registration and conversion
- Category and risk level inference
- Multi-server management
- Error handling and edge cases
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Dict, List, Any

from backend.app.core.mcp.discovery import (
    MCPToolDiscovery,
    MCPServerConfig,
)
from backend.app.core.mcp.protocol import MCPTool
from backend.app.core.tool_schema import (
    ToolSchema,
    ToolCategory,
    ToolRiskLevel,
    ToolStatus,
)


@pytest.fixture
def mock_tool_registry():
    """Create a mock tool registry."""
    registry = MagicMock()
    registry.register = MagicMock(return_value=MagicMock(spec=ToolSchema))
    return registry


@pytest.fixture
def discovery(mock_tool_registry):
    """Create MCPToolDiscovery instance with mock registry."""
    return MCPToolDiscovery(mock_tool_registry)


@pytest.fixture
def mock_mcp_client():
    """Create a mock MCP client."""
    client = AsyncMock()
    client.health_check = AsyncMock(return_value=True)
    client.list_tools = AsyncMock(return_value=[])
    client.close = AsyncMock()
    client.get_stats = MagicMock(return_value={"active": 0, "max": 10})
    return client


class TestMCPServerConfig:
    """Test MCPServerConfig dataclass."""

    def test_server_config_creation(self):
        """Test creating a server configuration."""
        config = MCPServerConfig(
            name="test_server",
            url="http://localhost:8000",
        )
        assert config.name == "test_server"
        assert config.url == "http://localhost:8000"
        assert config.enabled is True
        assert config.auto_register is True
        assert config.timeout == 30.0
        assert config.max_retries == 3
        assert config.tags == []

    def test_server_config_with_custom_values(self):
        """Test creating a server configuration with custom values."""
        config = MCPServerConfig(
            name="custom_server",
            url="http://example.com:9000",
            enabled=False,
            auto_register=False,
            timeout=60.0,
            max_retries=5,
            tags=["custom", "test"],
        )
        assert config.name == "custom_server"
        assert config.enabled is False
        assert config.auto_register is False
        assert config.timeout == 60.0
        assert config.max_retries == 5
        assert config.tags == ["custom", "test"]

    def test_server_config_tags_default(self):
        """Test that tags default to empty list."""
        config = MCPServerConfig(
            name="test",
            url="http://localhost:8000",
        )
        assert isinstance(config.tags, list)
        assert len(config.tags) == 0


class TestAddServer:
    """Test adding MCP servers."""

    @pytest.mark.asyncio
    async def test_add_server_success(self, discovery, mock_mcp_client):
        """Test successfully adding a server."""
        config = MCPServerConfig(
            name="test_server",
            url="http://localhost:8000",
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
    async def test_add_disabled_server(self, discovery):
        """Test adding a disabled server is skipped."""
        config = MCPServerConfig(
            name="disabled_server",
            url="http://localhost:8000",
            enabled=False,
        )

        result = await discovery.add_server(config)

        assert result is False
        assert "disabled_server" not in discovery.servers

    @pytest.mark.asyncio
    async def test_add_server_health_check_fails(self, discovery, mock_mcp_client):
        """Test adding a server when health check fails."""
        mock_mcp_client.health_check = AsyncMock(return_value=False)
        config = MCPServerConfig(
            name="unhealthy_server",
            url="http://localhost:8000",
        )

        with patch(
            "backend.app.core.mcp.discovery.MCPClient",
            return_value=mock_mcp_client,
        ):
            result = await discovery.add_server(config)

        assert result is False
        assert "unhealthy_server" not in discovery.servers

    @pytest.mark.asyncio
    async def test_add_server_with_auto_register(self, discovery, mock_mcp_client):
        """Test adding a server with auto_register enabled."""
        mock_mcp_client.list_tools = AsyncMock(
            return_value=[
                {
                    "name": "tool1",
                    "description": "Test tool",
                    "input_schema": {},
                }
            ]
        )

        config = MCPServerConfig(
            name="auto_register_server",
            url="http://localhost:8000",
            auto_register=True,
        )

        with patch(
            "backend.app.core.mcp.discovery.MCPClient",
            return_value=mock_mcp_client,
        ):
            result = await discovery.add_server(config)

        assert result is True
        discovery.tool_registry.register.assert_called()

    @pytest.mark.asyncio
    async def test_add_server_exception_handling(self, discovery):
        """Test exception handling when adding a server."""
        config = MCPServerConfig(
            name="error_server",
            url="http://localhost:8000",
        )

        with patch(
            "backend.app.core.mcp.discovery.MCPClient",
            side_effect=Exception("Connection failed"),
        ):
            result = await discovery.add_server(config)

        assert result is False
        assert "error_server" not in discovery.servers


class TestDiscoverTools:
    """Test tool discovery from servers."""

    @pytest.mark.asyncio
    async def test_discover_tools_success(self, discovery, mock_mcp_client):
        """Test successfully discovering tools from a server."""
        tools_data = [
            {
                "name": "read_file",
                "description": "Read a file",
                "input_schema": {"path": "string"},
                "output_schema": {"content": "string"},
                "tags": ["file"],
            },
            {
                "name": "write_file",
                "description": "Write to a file",
                "input_schema": {"path": "string", "content": "string"},
                "tags": ["file"],
            },
        ]
        mock_mcp_client.list_tools = AsyncMock(return_value=tools_data)
        discovery.servers["test_server"] = mock_mcp_client

        tools = await discovery.discover_tools("test_server")

        assert len(tools) == 2
        assert tools[0].name == "read_file"
        assert tools[1].name == "write_file"
        assert "test_server:read_file" in discovery.discovered_tools
        assert "test_server:write_file" in discovery.discovered_tools

    @pytest.mark.asyncio
    async def test_discover_tools_server_not_found(self, discovery):
        """Test discovering tools from non-existent server."""
        with pytest.raises(ValueError, match="Server nonexistent not found"):
            await discovery.discover_tools("nonexistent")

    @pytest.mark.asyncio
    async def test_discover_tools_empty_list(self, discovery, mock_mcp_client):
        """Test discovering tools when server returns empty list."""
        mock_mcp_client.list_tools = AsyncMock(return_value=[])
        discovery.servers["empty_server"] = mock_mcp_client

        tools = await discovery.discover_tools("empty_server")

        assert len(tools) == 0

    @pytest.mark.asyncio
    async def test_discover_tools_exception_handling(self, discovery, mock_mcp_client):
        """Test exception handling during tool discovery."""
        mock_mcp_client.list_tools = AsyncMock(
            side_effect=Exception("API error")
        )
        discovery.servers["error_server"] = mock_mcp_client

        tools = await discovery.discover_tools("error_server")

        assert len(tools) == 0

    @pytest.mark.asyncio
    async def test_discover_tools_caching(self, discovery, mock_mcp_client):
        """Test that discovered tools are cached."""
        tools_data = [
            {
                "name": "test_tool",
                "description": "Test",
                "input_schema": {},
            }
        ]
        mock_mcp_client.list_tools = AsyncMock(return_value=tools_data)
        discovery.servers["cache_server"] = mock_mcp_client

        await discovery.discover_tools("cache_server")

        assert "cache_server:test_tool" in discovery.discovered_tools
        assert discovery.discovered_tools["cache_server:test_tool"].name == "test_tool"


class TestDiscoverAllTools:
    """Test discovering tools from all servers."""

    @pytest.mark.asyncio
    async def test_discover_all_tools(self, discovery, mock_mcp_client):
        """Test discovering tools from multiple servers."""
        server1_tools = [
            {"name": "tool1", "description": "Tool 1", "input_schema": {}}
        ]
        server2_tools = [
            {"name": "tool2", "description": "Tool 2", "input_schema": {}}
        ]

        client1 = AsyncMock()
        client1.list_tools = AsyncMock(return_value=server1_tools)
        client2 = AsyncMock()
        client2.list_tools = AsyncMock(return_value=server2_tools)

        discovery.servers["server1"] = client1
        discovery.servers["server2"] = client2

        results = await discovery.discover_all_tools()

        assert len(results) == 2
        assert "server1" in results
        assert "server2" in results
        assert len(results["server1"]) == 1
        assert len(results["server2"]) == 1

    @pytest.mark.asyncio
    async def test_discover_all_tools_empty_servers(self, discovery):
        """Test discovering tools when no servers are configured."""
        results = await discovery.discover_all_tools()

        assert len(results) == 0


class TestRegisterTool:
    """Test tool registration."""

    @pytest.mark.asyncio
    async def test_register_tool_success(self, discovery):
        """Test successfully registering a tool."""
        mcp_tool = MCPTool(
            name="test_tool",
            description="A test tool",
            input_schema={"arg": "string"},
        )

        result = await discovery.register_tool("test_server", mcp_tool)

        assert result is not None
        discovery.tool_registry.register.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_tool_with_tags(self, discovery):
        """Test registering a tool with additional tags."""
        mcp_tool = MCPTool(
            name="tagged_tool",
            description="A tagged tool",
            input_schema={},
            tags=["original"],
        )

        await discovery.register_tool(
            "test_server",
            mcp_tool,
            tags=["extra"],
        )

        call_args = discovery.tool_registry.register.call_args
        tool_schema = call_args[0][0]
        assert "mcp" in tool_schema.tags
        assert "mcp:test_server" in tool_schema.tags
        assert "original" in tool_schema.tags
        assert "extra" in tool_schema.tags

    @pytest.mark.asyncio
    async def test_register_tool_exception_handling(self, discovery):
        """Test exception handling during tool registration."""
        discovery.tool_registry.register.side_effect = Exception("Registration failed")
        mcp_tool = MCPTool(
            name="error_tool",
            description="Tool that fails",
            input_schema={},
        )

        result = await discovery.register_tool("test_server", mcp_tool)

        assert result is None


class TestConvertToToolSchema:
    """Test conversion from MCPTool to ToolSchema."""

    def test_convert_file_tool(self, discovery):
        """Test converting a file operation tool."""
        mcp_tool = MCPTool(
            name="read_file",
            description="Read file contents",
            input_schema={"path": "string"},
        )

        schema = discovery._convert_to_tool_schema("file_server", mcp_tool)

        assert schema.name == "mcp_file_server_read_file"
        assert schema.category == ToolCategory.FILE_SYSTEM
        assert schema.risk_level == ToolRiskLevel.LOW

    def test_convert_database_tool(self, discovery):
        """Test converting a database tool."""
        mcp_tool = MCPTool(
            name="query_database",
            description="Execute SQL query",
            input_schema={"sql": "string"},
        )

        schema = discovery._convert_to_tool_schema("db_server", mcp_tool)

        assert schema.category == ToolCategory.DATABASE

    def test_convert_web_tool(self, discovery):
        """Test converting a web/API tool."""
        mcp_tool = MCPTool(
            name="http_request",
            description="Make HTTP API request",
            input_schema={"url": "string"},
        )

        schema = discovery._convert_to_tool_schema("web_server", mcp_tool)

        assert schema.category == ToolCategory.WEB

    def test_convert_high_risk_tool(self, discovery):
        """Test converting a high-risk tool."""
        mcp_tool = MCPTool(
            name="delete_file",
            description="Delete a file from disk",
            input_schema={"path": "string"},
        )

        schema = discovery._convert_to_tool_schema("fs_server", mcp_tool)

        assert schema.risk_level == ToolRiskLevel.HIGH

    def test_convert_medium_risk_tool(self, discovery):
        """Test converting a medium-risk tool."""
        mcp_tool = MCPTool(
            name="write_file",
            description="Write content to file",
            input_schema={"path": "string", "content": "string"},
        )

        schema = discovery._convert_to_tool_schema("fs_server", mcp_tool)

        assert schema.risk_level == ToolRiskLevel.MEDIUM

    def test_convert_tool_with_metadata(self, discovery):
        """Test that converted tool includes proper metadata."""
        mcp_tool = MCPTool(
            name="test_tool",
            description="Test tool",
            input_schema={},
        )

        schema = discovery._convert_to_tool_schema("test_server", mcp_tool)

        assert schema.name == "mcp_test_server_test_tool"
        assert schema.description == "Test tool"
        assert ToolCategory.UTILITY in [schema.category]


class TestInferCategory:
    """Test category inference."""

    def test_infer_file_category(self, discovery):
        """Test inferring file system category."""
        tool = MCPTool(
            name="read_directory",
            description="List files in directory",
            input_schema={},
        )
        assert discovery._infer_category(tool) == ToolCategory.FILE_SYSTEM

    def test_infer_database_category(self, discovery):
        """Test inferring database category."""
        tool = MCPTool(
            name="execute_query",
            description="Execute SQL query",
            input_schema={},
        )
        assert discovery._infer_category(tool) == ToolCategory.DATABASE

    def test_infer_search_category(self, discovery):
        """Test inferring search category."""
        tool = MCPTool(
            name="search_documents",
            description="Find documents matching criteria",
            input_schema={},
        )
        assert discovery._infer_category(tool) == ToolCategory.SEARCH

    def test_infer_code_execution_category(self, discovery):
        """Test inferring code execution category."""
        tool = MCPTool(
            name="execute_python",
            description="Run Python code",
            input_schema={},
        )
        assert discovery._infer_category(tool) == ToolCategory.CODE_EXECUTION

    def test_infer_utility_category(self, discovery):
        """Test inferring utility category for unknown tools."""
        tool = MCPTool(
            name="unknown_tool",
            description="Some unknown operation",
            input_schema={},
        )
        assert discovery._infer_category(tool) == ToolCategory.UTILITY


class TestInferRiskLevel:
    """Test risk level inference."""

    def test_infer_high_risk_delete(self, discovery):
        """Test inferring high risk for delete operations."""
        tool = MCPTool(
            name="delete_file",
            description="Delete file",
            input_schema={},
        )
        assert discovery._infer_risk_level(tool) == ToolRiskLevel.HIGH

    def test_infer_high_risk_execute(self, discovery):
        """Test inferring high risk for execute operations."""
        tool = MCPTool(
            name="execute_command",
            description="Execute shell command",
            input_schema={},
        )
        assert discovery._infer_risk_level(tool) == ToolRiskLevel.HIGH

    def test_infer_medium_risk_write(self, discovery):
        """Test inferring medium risk for write operations."""
        tool = MCPTool(
            name="write_file",
            description="Write to file",
            input_schema={},
        )
        assert discovery._infer_risk_level(tool) == ToolRiskLevel.MEDIUM

    def test_infer_medium_risk_update(self, discovery):
        """Test inferring medium risk for update operations."""
        tool = MCPTool(
            name="update_database",
            description="Update database record",
            input_schema={},
        )
        assert discovery._infer_risk_level(tool) == ToolRiskLevel.MEDIUM

    def test_infer_low_risk_read(self, discovery):
        """Test inferring low risk for read operations."""
        tool = MCPTool(
            name="read_file",
            description="Read file contents",
            input_schema={},
        )
        assert discovery._infer_risk_level(tool) == ToolRiskLevel.LOW


class TestDiscoverAndRegisterTools:
    """Test discovering and registering tools together."""

    @pytest.mark.asyncio
    async def test_discover_and_register_tools(self, discovery, mock_mcp_client):
        """Test discovering and registering tools from a server."""
        tools_data = [
            {"name": "tool1", "description": "Tool 1", "input_schema": {}},
            {"name": "tool2", "description": "Tool 2", "input_schema": {}},
        ]
        mock_mcp_client.list_tools = AsyncMock(return_value=tools_data)
        discovery.servers["test_server"] = mock_mcp_client

        count = await discovery.discover_and_register_tools("test_server")

        assert count == 2
        assert discovery.tool_registry.register.call_count == 2

    @pytest.mark.asyncio
    async def test_discover_and_register_all(self, discovery):
        """Test discovering and registering tools from all servers."""
        client1 = AsyncMock()
        client1.list_tools = AsyncMock(
            return_value=[{"name": "tool1", "description": "Tool 1", "input_schema": {}}]
        )
        client2 = AsyncMock()
        client2.list_tools = AsyncMock(
            return_value=[
                {"name": "tool2", "description": "Tool 2", "input_schema": {}},
                {"name": "tool3", "description": "Tool 3", "input_schema": {}},
            ]
        )

        discovery.servers["server1"] = client1
        discovery.servers["server2"] = client2

        results = await discovery.discover_and_register_all()

        assert results["server1"] == 1
        assert results["server2"] == 2


class TestRefreshTools:
    """Test refreshing tool lists."""

    @pytest.mark.asyncio
    async def test_refresh_specific_server(self, discovery, mock_mcp_client):
        """Test refreshing tools for a specific server."""
        mock_mcp_client.list_tools = AsyncMock(
            return_value=[{"name": "tool1", "description": "Tool 1", "input_schema": {}}]
        )
        discovery.servers["test_server"] = mock_mcp_client

        result = await discovery.refresh_tools("test_server")

        assert "test_server" in result
        assert result["test_server"] == 1

    @pytest.mark.asyncio
    async def test_refresh_all_servers(self, discovery):
        """Test refreshing tools for all servers."""
        client1 = AsyncMock()
        client1.list_tools = AsyncMock(
            return_value=[{"name": "tool1", "description": "Tool 1", "input_schema": {}}]
        )
        client2 = AsyncMock()
        client2.list_tools = AsyncMock(
            return_value=[{"name": "tool2", "description": "Tool 2", "input_schema": {}}]
        )

        discovery.servers["server1"] = client1
        discovery.servers["server2"] = client2

        result = await discovery.refresh_tools()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_refresh_nonexistent_server(self, discovery):
        """Test refreshing tools for non-existent server."""
        with pytest.raises(ValueError, match="Server nonexistent not found"):
            await discovery.refresh_tools("nonexistent")


class TestRemoveServer:
    """Test removing servers."""

    @pytest.mark.asyncio
    async def test_remove_server_success(self, discovery, mock_mcp_client):
        """Test successfully removing a server."""
        discovery.servers["test_server"] = mock_mcp_client

        result = await discovery.remove_server("test_server")

        assert result is True
        assert "test_server" not in discovery.servers
        mock_mcp_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_nonexistent_server(self, discovery):
        """Test removing a non-existent server."""
        result = await discovery.remove_server("nonexistent")

        assert result is False


class TestGetServerStats:
    """Test getting server statistics."""

    def test_get_server_stats(self, discovery, mock_mcp_client):
        """Test getting statistics for all servers."""
        discovery.servers["server1"] = mock_mcp_client
        discovery.servers["server2"] = mock_mcp_client

        stats = discovery.get_server_stats()

        assert stats["total_servers"] == 2
        assert "servers" in stats
        assert "server1" in stats["servers"]
        assert "server2" in stats["servers"]

    def test_get_server_stats_empty(self, discovery):
        """Test getting statistics when no servers are configured."""
        stats = discovery.get_server_stats()

        assert stats["total_servers"] == 0
        assert len(stats["servers"]) == 0


class TestCloseAll:
    """Test closing all server connections."""

    @pytest.mark.asyncio
    async def test_close_all_servers(self, discovery, mock_mcp_client):
        """Test closing all server connections."""
        client1 = AsyncMock()
        client2 = AsyncMock()

        discovery.servers["server1"] = client1
        discovery.servers["server2"] = client2

        await discovery.close_all()

        assert len(discovery.servers) == 0
        client1.close.assert_called_once()
        client2.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_all_empty(self, discovery):
        """Test closing when no servers are configured."""
        await discovery.close_all()

        assert len(discovery.servers) == 0
