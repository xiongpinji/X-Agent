"""
从 tests/test_capability_improvements.py 移除的 TestToolSystem 测试类（2026-07-19 归档）。

被测对象 backend/app/core/tool_system.py 为实验性子系统、生产零调用，
已归档至 archive/dead_code_2026-07-19/backend/app/core/tool_system.py。
原文件其余测试类（code_editor / plugin_manager / performance / i18n /
advanced_features）仍在原位运行，不受影响。
"""

import pytest

from backend.app.core.tool_system import (
    ToolManager, ToolMetadata, ToolPermission, Tool
)


class TestToolSystem:
    """Test enhanced tool system."""

    @pytest.mark.asyncio
    async def test_tool_registry(self):
        """Test tool registry."""
        manager = ToolManager()

        # Create mock tool
        class MockTool(Tool):
            async def execute(self, **kwargs):
                return "mock_result"

        metadata = ToolMetadata(
            name="mock_tool",
            version="1.0.0",
            description="Mock tool",
            author="Test",
            category="test",
            entry_point="mock_tool.py",
        )

        tool = MockTool(metadata)
        await manager.registry.register(tool)

        retrieved = await manager.registry.get_tool("mock_tool")
        assert retrieved is not None

    @pytest.mark.asyncio
    async def test_tool_permissions(self):
        """Test tool permissions."""
        manager = ToolManager()

        permission = ToolPermission(
            resource="file_system",
            action="read",
        )

        manager.permission_manager.grant_permission("test_tool", permission)
        has_perm = manager.permission_manager.has_permission("test_tool", "file_system", "read")
        assert has_perm is True

    @pytest.mark.asyncio
    async def test_tool_statistics(self):
        """Test tool statistics."""
        manager = ToolManager()

        class MockTool(Tool):
            async def execute(self, **kwargs):
                return "result"

        metadata = ToolMetadata(
            name="stat_tool",
            version="1.0.0",
            description="Tool for stats",
            author="Test",
            category="test",
            entry_point="stat_tool.py",
        )

        tool = MockTool(metadata)
        await manager.registry.register(tool)

        stats = await manager.registry.get_stats("stat_tool")
        assert stats is not None
