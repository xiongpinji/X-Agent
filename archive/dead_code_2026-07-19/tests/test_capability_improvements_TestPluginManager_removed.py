"""
从 tests/test_capability_improvements.py 移除的 TestPluginManager 测试类（2026-07-19 归档）。

被测对象 backend/app/core/plugin_manager.py 为死代码，已归档至
archive/dead_code_2026-07-19/backend/app/core/plugin_manager.py。
同时移除的还有 TestIntegration.test_full_workflow 中的 PluginManager 初始化、
以及 test_all_modules_importable 中的 PluginManager 断言。
原文件其余测试类（code_editor / performance / i18n / advanced_features）
仍在原位运行，不受影响。
"""

import pytest
from unittest.mock import patch

from backend.app.core.plugin_manager import (
    PluginManager, PluginMetadata, PluginDependency, PluginCategory
)


class TestPluginManager:
    """Test plugin management."""

    @pytest.fixture(autouse=True)
    def _isolate_plugin_registry(self):
        """Prevent PluginRegistry from touching ~/.xagent/plugins/registry.json.

        Real disk I/O causes cross-test pollution: a registry.json left over
        from a prior run makes register() return False (name already exists).
        """
        from backend.app.core.plugin_manager import PluginRegistry
        with patch.object(PluginRegistry, "_load_registry"), \
             patch.object(PluginRegistry, "_save_registry"):
            yield

    @pytest.mark.asyncio
    async def test_plugin_registry(self):
        """Test plugin registry."""
        manager = PluginManager()

        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            author="Test",
            description="Test plugin",
            category=PluginCategory.TOOLS,
        )

        success = await manager.registry.register(metadata)
        assert success is True

        plugin = await manager.registry.get(metadata.name)
        assert plugin is not None
        assert plugin.metadata.name == "test_plugin"

    @pytest.mark.asyncio
    async def test_plugin_search(self):
        """Test plugin search."""
        manager = PluginManager()

        metadata = PluginMetadata(
            name="search_test",
            version="1.0.0",
            author="Test",
            description="Test search functionality",
            category=PluginCategory.TOOLS,
            keywords=["search", "test"],
        )

        await manager.registry.register(metadata)
        results = await manager.registry.search(keyword="search")
        assert len(results) > 0
