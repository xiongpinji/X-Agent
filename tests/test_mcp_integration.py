"""Integration tests for MCP system."""

import pytest
import asyncio
import tempfile
from pathlib import Path

from backend.app.core.mcp.client import MCPClient
from backend.app.core.mcp.adapter import MCPToolAdapter
from backend.app.core.mcp.config import MCPConfig
from backend.app.core.mcp.tools.file_tool import FileOperationTool, PermissionChecker, AuditLog
from backend.app.core.mcp.tools.search_tool import SearchOperationTool, SearchPermissionChecker, SearchAuditLog
from backend.app.core.mcp.tools.browser_tool import BrowserTool, BrowserPermissionChecker, BrowserAuditLog
from backend.app.core.tool_schema import ToolCallInput


@pytest.fixture
def temp_dir():
    """Create temporary directory (module-level so all test classes can resolve it)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mcp_adapter(temp_dir):
    """Create MCP adapter (module-level so TestMCPPerformance can also resolve it;
    class-internal fixtures are not visible across classes)."""
    file_tool = FileOperationTool(base_path=temp_dir)
    search_tool = SearchOperationTool()
    browser_tool = BrowserTool()

    return MCPToolAdapter(
        file_tool=file_tool,
        search_tool=search_tool,
        browser_tool=browser_tool,
    )


class TestMCPIntegration:
    """Integration tests for MCP system."""

    @pytest.mark.asyncio
    async def test_file_operations_workflow(self, temp_dir, mcp_adapter):
        """Test complete file operations workflow."""
        # Write file
        write_input = ToolCallInput(
            tool_id="tool-1",
            tool_name="file_write",
            arguments={"path": "test.txt", "content": "test content"},
        )
        write_output = await mcp_adapter.execute_tool(write_input)
        assert write_output.success is True

        # Read file
        read_input = ToolCallInput(
            tool_id="tool-2",
            tool_name="file_read",
            arguments={"path": "test.txt"},
        )
        read_output = await mcp_adapter.execute_tool(read_input)
        assert read_output.success is True
        assert read_output.result == "test content"

        # List files
        list_input = ToolCallInput(
            tool_id="tool-3",
            tool_name="file_list",
            arguments={"path": "."},
        )
        list_output = await mcp_adapter.execute_tool(list_input)
        assert list_output.success is True
        assert list_output.result["count"] > 0

        # Check file exists
        exists_input = ToolCallInput(
            tool_id="tool-4",
            tool_name="file_exists",
            arguments={"path": "test.txt"},
        )
        exists_output = await mcp_adapter.execute_tool(exists_input)
        assert exists_output.success is True
        assert exists_output.result["exists"] is True

        # Delete file
        delete_input = ToolCallInput(
            tool_id="tool-5",
            tool_name="file_delete",
            arguments={"path": "test.txt"},
        )
        delete_output = await mcp_adapter.execute_tool(delete_input)
        assert delete_output.success is True

    @pytest.mark.asyncio
    async def test_search_operations_workflow(self, mcp_adapter):
        """Test complete search operations workflow."""
        # Web search
        search_input = ToolCallInput(
            tool_id="tool-6",
            tool_name="search_web",
            arguments={"query": "test query", "num_results": 5},
        )
        search_output = await mcp_adapter.execute_tool(search_input)
        assert search_output.success is True

        # News search
        news_input = ToolCallInput(
            tool_id="tool-7",
            tool_name="search_news",
            arguments={"query": "test news", "num_results": 5},
        )
        news_output = await mcp_adapter.execute_tool(news_input)
        assert news_output.success is True

    @pytest.mark.asyncio
    async def test_browser_operations_workflow(self, mcp_adapter):
        """Test complete browser operations workflow."""
        # Navigate
        nav_input = ToolCallInput(
            tool_id="tool-8",
            tool_name="browser_navigate",
            arguments={"url": "http://example.com"},
        )
        nav_output = await mcp_adapter.execute_tool(nav_input)
        assert nav_output.success is True

        # Click
        click_input = ToolCallInput(
            tool_id="tool-9",
            tool_name="browser_click",
            arguments={"selector": ".button"},
        )
        click_output = await mcp_adapter.execute_tool(click_input)
        assert click_output.success is True

        # Type
        type_input = ToolCallInput(
            tool_id="tool-10",
            tool_name="browser_type",
            arguments={"selector": "input", "text": "test"},
        )
        type_output = await mcp_adapter.execute_tool(type_input)
        assert type_output.success is True

        # Screenshot
        screenshot_input = ToolCallInput(
            tool_id="tool-11",
            tool_name="browser_screenshot",
            arguments={},
        )
        screenshot_output = await mcp_adapter.execute_tool(screenshot_input)
        assert screenshot_output.success is True

    @pytest.mark.asyncio
    async def test_batch_execution(self, mcp_adapter):
        """Test batch tool execution."""
        inputs = [
            ToolCallInput(
                tool_id="tool-12",
                tool_name="search_web",
                arguments={"query": "query1", "num_results": 5},
            ),
            ToolCallInput(
                tool_id="tool-13",
                tool_name="search_web",
                arguments={"query": "query2", "num_results": 5},
            ),
            ToolCallInput(
                tool_id="tool-14",
                tool_name="search_web",
                arguments={"query": "query3", "num_results": 5},
            ),
        ]

        outputs = await mcp_adapter.execute_tools_batch(inputs)
        assert len(outputs) == 3
        assert all(output.success for output in outputs)

    @pytest.mark.asyncio
    async def test_permission_enforcement(self, temp_dir):
        """Test permission enforcement."""
        # Create tool with restricted permissions
        perms = PermissionChecker({"read": True, "write": False, "delete": False})
        file_tool = FileOperationTool(base_path=temp_dir, permission_checker=perms)

        adapter = MCPToolAdapter(file_tool=file_tool)

        # Write should fail
        write_input = ToolCallInput(
            tool_id="tool-15",
            tool_name="file_write",
            arguments={"path": "test.txt", "content": "content"},
        )
        write_output = await adapter.execute_tool(write_input)
        assert write_output.success is False
        assert write_output.error_code == "PERMISSION_DENIED"

    @pytest.mark.asyncio
    async def test_audit_logging(self, temp_dir):
        """Test audit logging across operations."""
        audit = AuditLog()
        file_tool = FileOperationTool(base_path=temp_dir, audit_log=audit)

        adapter = MCPToolAdapter(file_tool=file_tool)

        # Perform operations
        await adapter.execute_tool(
            ToolCallInput(
                tool_id="tool-16",
                tool_name="file_write",
                arguments={"path": "test.txt", "content": "content"},
            )
        )
        await adapter.execute_tool(
            ToolCallInput(
                tool_id="tool-17",
                tool_name="file_read",
                arguments={"path": "test.txt"},
            )
        )

        # Check audit logs
        logs = adapter.get_audit_logs("file")
        assert len(logs["file"]) >= 2

    @pytest.mark.asyncio
    async def test_configuration_management(self):
        """Test configuration management."""
        config = MCPConfig()

        # Set configurations
        config.set_mcp_client_config(
            server_url="http://localhost:8001",
            max_retries=3,
            enable_cache=True,
        )
        config.set_file_tool_config(base_path="/tmp")
        config.set_search_tool_config()
        config.set_browser_tool_config()

        # Validate
        is_valid, errors = config.validate()
        assert is_valid is True

        # Get config dict
        config_dict = config.get_config_dict()
        assert "mcp_client" in config_dict
        assert "file_tool" in config_dict

    @pytest.mark.asyncio
    async def test_health_check(self, mcp_adapter):
        """Test health check."""
        status = await mcp_adapter.health_check()

        assert "timestamp" in status
        assert "file_tool" in status
        assert "search_tool" in status
        assert "browser_tool" in status

    @pytest.mark.asyncio
    async def test_error_handling(self, mcp_adapter):
        """Test error handling."""
        # Non-existent tool
        input_data = ToolCallInput(
            tool_id="tool-18",
            tool_name="non_existent_tool",
            arguments={},
        )
        output = await mcp_adapter.execute_tool(input_data)
        assert output.success is False
        assert output.error_code == "TOOL_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, mcp_adapter):
        """Test concurrent operations."""
        tasks = []
        for i in range(10):
            task = mcp_adapter.execute_tool(
                ToolCallInput(
                    tool_id=f"tool-{19+i}",
                    tool_name="search_web",
                    arguments={"query": f"query{i}", "num_results": 5},
                )
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        assert len(results) == 10
        assert all(r.success for r in results)


class TestMCPPerformance:
    """Performance tests for MCP system."""

    @pytest.mark.asyncio
    async def test_response_time(self, mcp_adapter):
        """Test response time."""
        import time

        start = time.time()
        await mcp_adapter.execute_tool(
            ToolCallInput(
                tool_id="tool-29",
                tool_name="search_web",
                arguments={"query": "test", "num_results": 5},
            )
        )
        elapsed = time.time() - start

        # Should complete in less than 100ms
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_throughput(self, mcp_adapter):
        """Test throughput."""
        import time

        start = time.time()
        tasks = []
        for i in range(100):
            task = mcp_adapter.execute_tool(
                ToolCallInput(
                    tool_id=f"tool-{30+i}",
                    tool_name="search_web",
                    arguments={"query": f"query{i}", "num_results": 5},
                )
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start

        # Should handle 100 requests in reasonable time
        assert len(results) == 100
        assert elapsed < 10.0  # 10 seconds for 100 requests


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
