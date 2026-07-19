"""
从 tests/test_marketplace_comprehensive.py 移除的 plugin_manager 相关用例（2026-07-19 归档）。

被测对象 backend/app/core/plugin_manager.py 为死代码，已归档至
archive/dead_code_2026-07-19/backend/app/core/plugin_manager.py。
移除内容：TestPluginVersionManagement.test_version_constraint_matching 方法、
以及整个 TestPluginDependencyManagement 类（两个方法均为方法内延迟导入 plugin_manager）。
原文件其余测试（api.plugin_market / core.skill_market_models，模块仍在 backend 原位）
不受影响，仍在原文件运行。
"""


class TestPluginVersionManagement:
    """测试插件版本管理"""

    def test_version_constraint_matching(self):
        """测试版本约束匹配"""
        from backend.app.core.plugin_manager import VersionConstraint

        # 测试精确匹配
        assert VersionConstraint.matches("1.0.0", "1.0.0")
        assert not VersionConstraint.matches("1.0.1", "1.0.0")

        # 测试大于等于
        assert VersionConstraint.matches("1.0.1", ">=1.0.0")
        assert VersionConstraint.matches("1.0.0", ">=1.0.0")
        assert not VersionConstraint.matches("0.9.9", ">=1.0.0")

        # 测试小于等于
        assert VersionConstraint.matches("1.0.0", "<=1.0.0")
        assert VersionConstraint.matches("0.9.9", "<=1.0.0")
        assert not VersionConstraint.matches("1.0.1", "<=1.0.0")

        # 测试插入符号（^）- 兼容版本
        assert VersionConstraint.matches("1.0.1", "^1.0.0")
        assert VersionConstraint.matches("1.5.0", "^1.0.0")
        assert not VersionConstraint.matches("2.0.0", "^1.0.0")

        # 测试波浪号（~）- 近似等价
        assert VersionConstraint.matches("1.0.1", "~1.0.0")
        assert not VersionConstraint.matches("1.1.0", "~1.0.0")


class TestPluginDependencyManagement:
    """测试插件依赖管理"""

    def test_dependency_resolution(self):
        """测试依赖解析"""
        from backend.app.core.plugin_manager import (
            PluginDependency, PluginMetadata, PluginCategory
        )

        # 创建有依赖的插件
        dep1 = PluginDependency(name="base-plugin", version="^1.0.0")
        dep2 = PluginDependency(name="utils-plugin", version=">=1.0.0", optional=False)

        metadata = PluginMetadata(
            name="dependent-plugin",
            version="1.0.0",
            author="Test",
            description="Plugin with dependencies",
            category=PluginCategory.TOOLS,
            dependencies=[dep1, dep2]
        )

        assert len(metadata.dependencies) == 2
        assert metadata.dependencies[0].name == "base-plugin"
        assert metadata.dependencies[1].optional is False

    def test_optional_dependency(self):
        """测试可选依赖"""
        from backend.app.core.plugin_manager import (
            PluginDependency, PluginMetadata, PluginCategory
        )

        # 创建可选依赖
        optional_dep = PluginDependency(
            name="optional-plugin",
            version="^1.0.0",
            optional=True
        )

        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            author="Test",
            description="Test",
            category=PluginCategory.TOOLS,
            dependencies=[optional_dep]
        )

        assert metadata.dependencies[0].optional is True
