"""
从 tests/test_plugin_market.py 移除的 plugin_adapter 相关测试（2026-07-19 归档）。

被测对象 backend/app/core/plugin_adapter.py 为死代码，已归档至
archive/dead_code_2026-07-19/backend/app/core/plugin_adapter.py。
移除内容：TestPluginAdapter、TestPluginIntegration 两个测试类。
原文件其余测试（api.plugin_market / services.plugin_crawler /
services.translation_service，这些模块仍在 backend 原位）
不受影响，仍在原文件运行。
"""

from backend.app.core.plugin_adapter import PluginAdapter, PluginIntegration


class TestPluginAdapter:
    """测试插件适配器"""

    def test_adapter_initialization(self):
        """测试适配器初始化"""
        adapter = PluginAdapter()
        assert adapter.plugins_dir.exists()

    def test_is_valid_version(self):
        """测试版本验证"""
        assert PluginAdapter._is_valid_version("1.0.0")
        assert PluginAdapter._is_valid_version("2.1.3")
        assert PluginAdapter._is_valid_version("1.0.0-beta")
        assert not PluginAdapter._is_valid_version("1.0")
        assert not PluginAdapter._is_valid_version("invalid")

    def test_validate_manifest(self):
        """测试manifest验证"""
        adapter = PluginAdapter()

        # 有效的manifest
        valid_manifest = {
            "name": "Test Plugin",
            "version": "1.0.0",
            "entry_point": "test.main"
        }
        report = adapter.validate_manifest(valid_manifest)
        assert report.status.value == "compatible"

        # 缺少必需字段
        invalid_manifest = {
            "name": "Test Plugin"
        }
        report = adapter.validate_manifest(invalid_manifest)
        assert report.status.value == "incompatible"
        assert len(report.issues) > 0


class TestPluginIntegration:
    """测试插件整合系统"""

    def test_integration_initialization(self):
        """测试整合系统初始化"""
        integration = PluginIntegration()
        assert integration.plugins_dir.exists()

    def test_register_plugin(self):
        """测试插件注册"""
        integration = PluginIntegration()

        plugin_info = {
            "name": "Test Plugin",
            "version": "1.0.0"
        }

        success = integration.register_plugin("test-plugin", plugin_info)
        assert success is True
        assert "test-plugin" in integration._loaded_plugins

    def test_plugin_status(self):
        """测试插件状态"""
        integration = PluginIntegration()

        plugin_info = {
            "name": "Test Plugin",
            "version": "1.0.0"
        }

        integration.register_plugin("test-plugin", plugin_info)

        # 初始状态应该是None
        status = integration.get_plugin_status("test-plugin")
        assert status is None

        # 加载后应该有状态
        integration._plugin_instances["test-plugin"] = {
            "id": "test-plugin",
            "status": "loaded"
        }
        status = integration.get_plugin_status("test-plugin")
        assert status is not None
        assert status["status"] == "loaded"
