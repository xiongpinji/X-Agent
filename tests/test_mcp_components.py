"""Unit tests for MCP components."""

import pytest
import asyncio
from pathlib import Path
import tempfile

from backend.app.core.mcp.client import MCPClient, MCPConnectionPool, MCPResultCache
from backend.app.core.mcp.tools.file_tool import FileOperationTool, PermissionChecker, AuditLog
from backend.app.core.mcp.tools.search_tool import SearchOperationTool, SearchPermissionChecker, SearchAuditLog
from backend.app.core.mcp.tools.browser_tool import BrowserTool, BrowserPermissionChecker, BrowserAuditLog
from backend.app.core.mcp.adapter import MCPToolAdapter
from backend.app.core.mcp.config import MCPConfig, MCPClientConfig, FileToolConfig


class TestMCPConnectionPool:
    """Test MCP connection pool."""

    @pytest.mark.asyncio
    async def test_acquire_release(self):
        """Test acquiring and releasing connections."""
        pool = MCPConnectionPool(max_connections=2)

        await pool.acquire()
        assert pool.active_connections == 1

        await pool.acquire()
        assert pool.active_connections == 2

        pool.release()
        assert pool.active_connections == 1

        pool.release()
        assert pool.active_connections == 0

    def test_get_stats(self):
        """Test getting pool statistics."""
        pool = MCPConnectionPool(max_connections=5)
        stats = pool.get_stats()

        assert stats["max"] == 5
        assert stats["active"] == 0
        assert stats["available"] == 5


class TestMCPResultCache:
    """Test MCP result cache."""

    def test_cache_set_get(self):
        """Test caching results."""
        cache = MCPResultCache(ttl_seconds=300)

        result = {"data": "test"}
        cache.set("test_tool", {"arg": "value"}, result)

        cached = cache.get("test_tool", {"arg": "value"})
        assert cached == result

    def test_cache_expiration(self):
        """Test cache expiration."""
        cache = MCPResultCache(ttl_seconds=0)

        result = {"data": "test"}
        cache.set("test_tool", {"arg": "value"}, result)

        # Wait for expiration
        import time
        time.sleep(0.1)

        cached = cache.get("test_tool", {"arg": "value"})
        assert cached is None

    def test_cache_stats(self):
        """Test cache statistics."""
        cache = MCPResultCache(ttl_seconds=300)
        cache.set("tool1", {"arg": "value"}, {"data": "test"})
        cache.set("tool2", {"arg": "value"}, {"data": "test"})

        stats = cache.get_stats()
        assert stats["size"] == 2
        assert stats["ttl_seconds"] == 300


class TestFileOperationTool:
    """Test file operation tool."""

    @pytest.mark.asyncio
    async def test_read_file(self):
        """Test reading file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            file_path.write_text("test content")

            tool = FileOperationTool(base_path=tmpdir)
            content = await tool.read_file("test.txt")

            assert content == "test content"

    @pytest.mark.asyncio
    async def test_write_file(self):
        """Test writing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileOperationTool(base_path=tmpdir)
            result = await tool.write_file("test.txt", "test content")

            assert result["success"] is True
            assert result["size"] == 12

    @pytest.mark.asyncio
    async def test_list_files(self):
        """Test listing files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir).joinpath("file1.txt").write_text("content1")
            Path(tmpdir).joinpath("file2.txt").write_text("content2")

            tool = FileOperationTool(base_path=tmpdir)
            result = await tool.list_files(".")

            assert result["count"] == 2
            assert len(result["items"]) == 2

    @pytest.mark.asyncio
    async def test_permission_denied(self):
        """Test permission denied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            perms = PermissionChecker({"read": False})
            tool = FileOperationTool(base_path=tmpdir, permission_checker=perms)

            with pytest.raises(PermissionError):
                await tool.read_file("test.txt")

    @pytest.mark.asyncio
    async def test_audit_logging(self):
        """Test audit logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit = AuditLog()
            tool = FileOperationTool(base_path=tmpdir, audit_log=audit)

            Path(tmpdir).joinpath("test.txt").write_text("content")
            await tool.read_file("test.txt")

            logs = audit.get_entries()
            assert len(logs) > 0
            assert logs[-1]["operation"] == "read"
            assert logs[-1]["success"] is True

    @pytest.mark.asyncio
    async def test_rejects_sibling_prefix_escape(self):
        """Reject paths in sibling directories with a shared string prefix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parent = Path(tmpdir)
            base = parent / "workspace"
            sibling = parent / "workspace-evil"
            base.mkdir()
            sibling.mkdir()
            (sibling / "secret.txt").write_text("hidden", encoding="utf-8")

            tool = FileOperationTool(base_path=str(base))

            with pytest.raises(ValueError):
                await tool.read_file("../workspace-evil/secret.txt")

    @pytest.mark.asyncio
    async def test_rejects_symlink_escape(self):
        """Reject symlinks that resolve outside the configured base directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parent = Path(tmpdir)
            base = parent / "workspace"
            outside = parent / "outside"
            base.mkdir()
            outside.mkdir()
            (outside / "secret.txt").write_text("hidden", encoding="utf-8")
            link = base / "outside-link"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                pytest.skip(f"symlink creation unavailable on this platform: {exc}")

            tool = FileOperationTool(base_path=str(base))

            with pytest.raises(ValueError):
                await tool.read_file("outside-link/secret.txt")


class TestSearchOperationTool:
    """Test search operation tool."""

    @pytest.mark.asyncio
    async def test_permission_denied(self):
        """Test permission denied."""
        perms = SearchPermissionChecker({"web_search": False})
        tool = SearchOperationTool(permission_checker=perms)

        result = await tool.search_web("test query")
        assert result["status"] == "permission_denied"

    @pytest.mark.asyncio
    async def test_audit_logging(self):
        """Test audit logging."""
        audit = SearchAuditLog()
        tool = SearchOperationTool(audit_log=audit)

        await tool.search_web("test query")

        logs = audit.get_entries()
        assert len(logs) > 0
        assert logs[-1]["operation"] == "web_search"


class TestBrowserTool:
    """Test browser tool."""

    @pytest.mark.asyncio
    async def test_permission_denied(self):
        """Test permission denied."""
        perms = BrowserPermissionChecker({"navigate": False})
        tool = BrowserTool(permission_checker=perms)

        with pytest.raises(PermissionError):
            await tool.navigate("http://example.com")

    @pytest.mark.asyncio
    async def test_audit_logging(self):
        """Test audit logging."""
        audit = BrowserAuditLog()
        tool = BrowserTool(audit_log=audit)

        await tool.navigate("http://example.com")

        logs = audit.get_entries()
        assert len(logs) > 0
        assert logs[-1]["operation"] == "navigate"


class TestMCPConfig:
    """Test MCP configuration."""

    def test_set_configs(self):
        """Test setting configurations."""
        config = MCPConfig()

        config.set_mcp_client_config(server_url="http://localhost:8001")
        config.set_file_tool_config(base_path="/tmp")

        assert config.mcp_client_config.server_url == "http://localhost:8001"
        assert config.file_tool_config.base_path == "/tmp"

    def test_validate(self):
        """Test configuration validation."""
        config = MCPConfig()

        is_valid, errors = config.validate()
        assert is_valid is False
        assert len(errors) > 0

    def test_get_config_dict(self):
        """Test getting configuration as dictionary."""
        config = MCPConfig()
        config.set_mcp_client_config(server_url="http://localhost:8001")

        config_dict = config.get_config_dict()
        assert "mcp_client" in config_dict
        assert config_dict["mcp_client"]["server_url"] == "http://localhost:8001"


class TestMCPAdapter:
    """Test MCP adapter."""

    @pytest.mark.asyncio
    async def test_get_available_tools(self):
        """Test getting available tools."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_tool = FileOperationTool(base_path=tmpdir)
            search_tool = SearchOperationTool()
            browser_tool = BrowserTool()

            adapter = MCPToolAdapter(
                file_tool=file_tool,
                search_tool=search_tool,
                browser_tool=browser_tool,
            )

            tools = adapter.get_available_tools()
            assert len(tools) > 0

            tool_names = [t["name"] for t in tools]
            assert "file_read" in tool_names
            assert "search_web" in tool_names
            assert "browser_navigate" in tool_names

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_tool = FileOperationTool(base_path=tmpdir)
            adapter = MCPToolAdapter(file_tool=file_tool)

            status = await adapter.health_check()
            assert "file_tool" in status
            assert status["file_tool"] == "ready"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
