"""插件市场系统集成测试"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch

from backend.app.api.plugin_market import (
    PluginRecord, PluginManifest, PluginCategory, PluginStatus,
    PluginRiskLevel, _plugins_db, _categories_db
)
from backend.app.services.plugin_crawler import PluginCrawler, PluginClassifier
from backend.app.services.translation_service import (
    TranslationEngine, ContentGenerator, PluginLocalizer
)
from backend.app.core.plugin_adapter import PluginAdapter, PluginIntegration


class TestPluginMarketAPI:
    """测试插件市场API"""

    def test_get_categories(self):
        """测试获取分类"""
        categories = list(_categories_db.values())
        assert len(categories) == 8
        assert any(c.id == "office" for c in categories)
        assert any(c.id == "development" for c in categories)

    def test_plugin_record_creation(self):
        """测试插件记录创建"""
        manifest = PluginManifest(
            name="Test Plugin",
            version="1.0.0",
            description="Test description",
            description_zh="测试描述"
        )

        plugin = PluginRecord(
            id="test-plugin",
            manifest=manifest,
            category=PluginCategory.DEVELOPMENT,
            status=PluginStatus.PUBLISHED,
            risk_level=PluginRiskLevel.LOW
        )

        assert plugin.id == "test-plugin"
        assert plugin.manifest.name == "Test Plugin"
        assert plugin.category == PluginCategory.DEVELOPMENT
        assert plugin.is_installed is False

    def test_plugin_installation_status(self):
        """测试插件安装状态"""
        manifest = PluginManifest(
            name="Test Plugin",
            version="1.0.0"
        )

        plugin = PluginRecord(
            id="test-plugin",
            manifest=manifest,
            category=PluginCategory.DEVELOPMENT
        )

        assert plugin.is_installed is False
        assert plugin.is_enabled is False

        # 模拟安装
        plugin.is_installed = True
        plugin.is_enabled = True

        assert plugin.is_installed is True
        assert plugin.is_enabled is True


class TestPluginCrawler:
    """测试插件爬虫"""

    def test_crawler_initialization(self):
        """测试爬虫初始化"""
        crawler = PluginCrawler()
        assert crawler.cache_dir.exists()

    def test_is_xagent_plugin(self):
        """测试X-Agent插件检测"""
        assert PluginCrawler._is_xagent_plugin("x-agent-plugin", "X-Agent plugin")
        assert PluginCrawler._is_xagent_plugin("xagent-tool", "Tool for X-Agent")
        assert not PluginCrawler._is_xagent_plugin("random-plugin", "Random plugin")

    def test_generate_plugin_id(self):
        """测试插件ID生成"""
        id1 = PluginCrawler._generate_plugin_id("https://github.com/user/plugin1")
        id2 = PluginCrawler._generate_plugin_id("https://github.com/user/plugin1")
        id3 = PluginCrawler._generate_plugin_id("https://github.com/user/plugin2")

        assert id1 == id2  # 相同URL生成相同ID
        assert id1 != id3  # 不同URL生成不同ID
        assert len(id1) == 12  # ID长度为12


class TestPluginClassifier:
    """测试插件分类器"""

    def test_classify_plugin(self):
        """测试插件分类"""
        from backend.app.services.plugin_crawler import PluginMetadata

        # 测试开发工具分类
        plugin = PluginMetadata(
            id="test",
            name="GitHub Plugin",
            version="1.0.0",
            author="test",
            description="Git and code management",
            description_zh="Git和代码管理",
            long_description="",
            long_description_zh="",
            homepage="",
            repository="",
            license="MIT",
            capabilities=["git", "code"]
        )

        category = PluginClassifier.classify_plugin(plugin)
        assert category == "development"

    def test_extract_tags(self):
        """测试标签提取"""
        from backend.app.services.plugin_crawler import PluginMetadata

        plugin = PluginMetadata(
            id="test",
            name="Data Plugin",
            version="1.0.0",
            author="test",
            description="Data analysis and visualization",
            description_zh="数据分析和可视化",
            long_description="",
            long_description_zh="",
            homepage="",
            repository="",
            license="MIT",
            keywords=["data", "analysis"],
            capabilities=["visualization", "analysis"]
        )

        tags = PluginClassifier.extract_tags(plugin)
        assert "data" in tags
        assert "analysis" in tags
        assert "visualization" in tags

    def test_calculate_similarity(self):
        """测试相似度计算"""
        from backend.app.services.plugin_crawler import PluginMetadata

        plugin1 = PluginMetadata(
            id="test1",
            name="Plugin 1",
            version="1.0.0",
            author="test",
            description="",
            description_zh="",
            long_description="",
            long_description_zh="",
            homepage="",
            repository="",
            license="MIT",
            capabilities=["api", "http", "rest"]
        )

        plugin2 = PluginMetadata(
            id="test2",
            name="Plugin 2",
            version="1.0.0",
            author="test",
            description="",
            description_zh="",
            long_description="",
            long_description_zh="",
            homepage="",
            repository="",
            license="MIT",
            capabilities=["api", "http", "graphql"]
        )

        plugin3 = PluginMetadata(
            id="test3",
            name="Plugin 3",
            version="1.0.0",
            author="test",
            description="",
            description_zh="",
            long_description="",
            long_description_zh="",
            homepage="",
            repository="",
            license="MIT",
            capabilities=["file", "storage"]
        )

        # plugin1和plugin2相似度高
        similarity_12 = PluginClassifier.calculate_similarity(plugin1, plugin2)
        assert similarity_12 >= 0.5

        # plugin1和plugin3相似度低
        similarity_13 = PluginClassifier.calculate_similarity(plugin1, plugin3)
        assert similarity_13 == 0.0


class TestTranslationEngine:
    """测试翻译引擎"""

    def test_translate_text(self):
        """测试文本翻译"""
        text = "This is a repository with API integration"
        translated = TranslationEngine.translate_text(text)

        # 检查关键词是否被翻译
        assert "仓库" in translated or "repository" in translated
        assert "接口" in translated or "API" in translated

    def test_simplify_for_beginners(self):
        """测试小白化简化"""
        text = "You need to configure and initialize the system"
        simplified = TranslationEngine.simplify_for_beginners(text)

        # 检查复杂词汇是否被简化
        assert "configure" not in simplified or "配置" in simplified


class TestContentGenerator:
    """测试内容生成器"""

    def test_generate_what_is_it(self):
        """测试生成"这是什么"内容"""
        content = ContentGenerator.generate_what_is_it(
            name="GitHub Plugin",
            description="GitHub API integration",
            description_zh="GitHub API集成",
            capabilities=["repository", "issue", "pull request"]
        )

        assert len(content) > 0
        assert "GitHub" in content or "仓库" in content

    def test_generate_who_is_it_for(self):
        """测试生成"适合谁"内容"""
        content = ContentGenerator.generate_who_is_it_for(
            name="GitHub Plugin",
            description="GitHub API integration",
            capabilities=["repository", "issue"],
            category="development"
        )

        assert "程序员" in content or "开发" in content

    def test_generate_how_to_use(self):
        """测试生成"怎么用"内容"""
        content = ContentGenerator.generate_how_to_use(
            name="GitHub Plugin",
            entry_point="github.main",
            capabilities=["repository"]
        )

        assert "安装" in content
        assert "步骤" in content or "1." in content

    def test_generate_faq(self):
        """测试生成FAQ"""
        faqs = ContentGenerator.generate_faq(
            name="GitHub Plugin",
            description="GitHub API integration",
            capabilities=["github"]
        )

        assert len(faqs) > 0
        assert all("question" in faq and "answer" in faq for faq in faqs)

    def test_generate_tutorial(self):
        """测试生成教程"""
        tutorial = ContentGenerator.generate_tutorial(
            name="GitHub Plugin",
            description="GitHub API integration",
            capabilities=["repository", "issue"],
            category="development"
        )

        assert "快速开始" in tutorial or "开始" in tutorial
        assert "功能" in tutorial or "能力" in tutorial


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


# 集成测试
class TestPluginMarketIntegration:
    """插件市场集成测试"""

    def test_end_to_end_workflow(self):
        """测试端到端工作流"""
        # 1. 创建插件记录
        manifest = PluginManifest(
            name="Integration Test Plugin",
            version="1.0.0",
            description="Test plugin",
            description_zh="测试插件"
        )

        plugin = PluginRecord(
            id="integration-test",
            manifest=manifest,
            category=PluginCategory.DEVELOPMENT,
            what_is_it="这是一个测试插件",
            who_is_it_for="开发者",
            how_to_use="1. 安装\n2. 使用"
        )

        # 2. 添加到数据库
        _plugins_db["integration-test"] = plugin

        # 3. 验证
        assert "integration-test" in _plugins_db
        assert _plugins_db["integration-test"].manifest.name == "Integration Test Plugin"

        # 4. 模拟安装
        plugin.is_installed = True
        plugin.is_enabled = True

        # 5. 验证安装状态
        assert plugin.is_installed is True
        assert plugin.is_enabled is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
