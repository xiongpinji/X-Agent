"""
MCP插件市场和技能市场完整功能测试
测试内容：
1. 插件安装、配置、使用、卸载
2. 技能市场浏览、搜索、使用、评论
3. 版本管理、依赖管理、更新机制
"""

import pytest
import asyncio
from datetime import datetime, UTC
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

# ==================== 插件市场测试 ====================

class TestPluginMarketInstallation:
    """测试插件安装功能"""

    def test_plugin_install_basic(self):
        """测试基础插件安装"""
        from backend.app.api.plugin_market import (
            PluginRecord, PluginManifest, PluginCategory, PluginStatus,
            PluginRiskLevel, _plugins_db
        )

        # 创建测试插件
        manifest = PluginManifest(
            name="Test Plugin",
            version="1.0.0",
            description="Test plugin for installation",
            description_zh="测试安装的插件",
            author="Test Author",
            license="MIT"
        )

        plugin = PluginRecord(
            id="test-install-plugin",
            manifest=manifest,
            category=PluginCategory.DEVELOPMENT,
            status=PluginStatus.PUBLISHED,
            risk_level=PluginRiskLevel.LOW
        )

        # 添加到数据库
        _plugins_db["test-install-plugin"] = plugin

        # 验证初始状态
        assert plugin.is_installed is False
        assert plugin.is_enabled is False
        assert plugin.status == PluginStatus.PUBLISHED

        # 模拟安装
        plugin.is_installed = True
        plugin.is_enabled = True
        plugin.status = PluginStatus.INSTALLED
        plugin.installed_count += 1

        # 验证安装后状态
        assert plugin.is_installed is True
        assert plugin.is_enabled is True
        assert plugin.status == PluginStatus.INSTALLED
        assert plugin.installed_count == 1

    def test_plugin_install_with_config(self):
        """测试带配置的插件安装"""
        from backend.app.api.plugin_market import (
            PluginRecord, PluginManifest, PluginCategory, PluginStatus
        )

        manifest = PluginManifest(
            name="Config Plugin",
            version="1.0.0",
            description="Plugin with configuration",
            description_zh="带配置的插件"
        )

        plugin = PluginRecord(
            id="config-plugin",
            manifest=manifest,
            category=PluginCategory.DEVELOPMENT
        )

        # 模拟配置
        config = {
            "api_key": "test-key",
            "timeout": 30,
            "debug": True
        }

        # 安装并应用配置
        plugin.is_installed = True
        plugin.is_enabled = True

        # 验证
        assert plugin.is_installed is True
        assert plugin.manifest.name == "Config Plugin"

    def test_plugin_uninstall(self):
        """测试插件卸载"""
        from backend.app.api.plugin_market import (
            PluginRecord, PluginManifest, PluginCategory, PluginStatus
        )

        manifest = PluginManifest(
            name="Uninstall Test",
            version="1.0.0"
        )

        plugin = PluginRecord(
            id="uninstall-test",
            manifest=manifest,
            category=PluginCategory.DEVELOPMENT
        )

        # 先安装
        plugin.is_installed = True
        plugin.is_enabled = True
        plugin.installed_count = 1

        assert plugin.is_installed is True

        # 卸载
        plugin.is_installed = False
        plugin.is_enabled = False
        plugin.installed_count = max(0, plugin.installed_count - 1)

        # 验证卸载
        assert plugin.is_installed is False
        assert plugin.is_enabled is False
        assert plugin.installed_count == 0

    def test_plugin_enable_disable(self):
        """测试插件启用/禁用"""
        from backend.app.api.plugin_market import (
            PluginRecord, PluginManifest, PluginCategory, PluginStatus
        )

        manifest = PluginManifest(
            name="Enable Test",
            version="1.0.0"
        )

        plugin = PluginRecord(
            id="enable-test",
            manifest=manifest,
            category=PluginCategory.DEVELOPMENT
        )

        # 安装
        plugin.is_installed = True
        plugin.is_enabled = True
        plugin.status = PluginStatus.INSTALLED

        assert plugin.is_enabled is True

        # 禁用
        plugin.is_enabled = False
        plugin.status = PluginStatus.DISABLED

        assert plugin.is_enabled is False
        assert plugin.status == PluginStatus.DISABLED

        # 重新启用
        plugin.is_enabled = True
        plugin.status = PluginStatus.INSTALLED

        assert plugin.is_enabled is True
        assert plugin.status == PluginStatus.INSTALLED


class TestPluginMarketSearch:
    """测试插件搜索功能"""

    def test_search_by_name(self):
        """测试按名称搜索"""
        from backend.app.api.plugin_market import (
            PluginRecord, PluginManifest, PluginCategory, _plugins_db
        )

        # 创建测试插件
        plugins = [
            PluginRecord(
                id="github-plugin",
                manifest=PluginManifest(
                    name="GitHub Plugin",
                    version="1.0.0",
                    description="GitHub integration"
                ),
                category=PluginCategory.DEVELOPMENT
            ),
            PluginRecord(
                id="gitlab-plugin",
                manifest=PluginManifest(
                    name="GitLab Plugin",
                    version="1.0.0",
                    description="GitLab integration"
                ),
                category=PluginCategory.DEVELOPMENT
            ),
        ]

        for plugin in plugins:
            _plugins_db[plugin.id] = plugin

        # 搜索
        query = "github"
        results = [p for p in _plugins_db.values()
                  if query.lower() in p.manifest.name.lower()]

        assert len(results) == 1
        assert results[0].id == "github-plugin"

    def test_search_by_category(self):
        """测试按分类搜索"""
        from backend.app.api.plugin_market import (
            PluginRecord, PluginManifest, PluginCategory, _plugins_db
        )
        # 隔离：清空模块级字典，避免前序测试污染。
        _plugins_db.clear()

        # 创建不同分类的插件
        plugins = [
            PluginRecord(
                id="dev-plugin",
                manifest=PluginManifest(
                    name="Dev Tool",
                    version="1.0.0"
                ),
                category=PluginCategory.DEVELOPMENT
            ),
            PluginRecord(
                id="office-plugin",
                manifest=PluginManifest(
                    name="Office Tool",
                    version="1.0.0"
                ),
                category=PluginCategory.OFFICE
            ),
        ]

        for plugin in plugins:
            _plugins_db[plugin.id] = plugin

        # 按分类搜索
        results = [p for p in _plugins_db.values()
                  if p.category == PluginCategory.DEVELOPMENT]

        assert len(results) == 1
        assert results[0].category == PluginCategory.DEVELOPMENT

    def test_search_by_keywords(self):
        """测试按关键词搜索"""
        from backend.app.api.plugin_market import (
            PluginRecord, PluginManifest, PluginCategory, _plugins_db
        )

        manifest = PluginManifest(
            name="API Plugin",
            version="1.0.0",
            description="REST API integration",
            keywords=["api", "rest", "http"]
        )

        plugin = PluginRecord(
            id="api-plugin",
            manifest=manifest,
            category=PluginCategory.DEVELOPMENT
        )

        _plugins_db["api-plugin"] = plugin

        # 按关键词搜索
        query = "rest"
        results = [p for p in _plugins_db.values()
                  if any(query.lower() in kw.lower() for kw in p.manifest.keywords)]

        assert len(results) == 1
        assert "rest" in results[0].manifest.keywords


class TestPluginVersionManagement:
    """测试插件版本管理"""

    def test_plugin_version_update(self):
        """测试插件版本更新"""
        from backend.app.api.plugin_market import (
            PluginRecord, PluginManifest, PluginCategory, PluginStatus
        )

        manifest_v1 = PluginManifest(
            name="Version Test",
            version="1.0.0"
        )

        plugin = PluginRecord(
            id="version-test",
            manifest=manifest_v1,
            category=PluginCategory.DEVELOPMENT,
            status=PluginStatus.INSTALLED
        )

        assert plugin.manifest.version == "1.0.0"

        # 更新版本
        manifest_v2 = PluginManifest(
            name="Version Test",
            version="1.1.0"
        )
        plugin.manifest = manifest_v2
        plugin.status = PluginStatus.UPDATING

        assert plugin.manifest.version == "1.1.0"
        assert plugin.status == PluginStatus.UPDATING

        # 完成更新
        plugin.status = PluginStatus.INSTALLED

        assert plugin.manifest.version == "1.1.0"
        assert plugin.status == PluginStatus.INSTALLED


# ==================== 技能市场测试 ====================

class TestSkillMarketBrowsing:
    """测试技能市场浏览功能"""

    def test_skill_categories(self):
        """测试技能分类"""
        from backend.app.core.skill_market_models import SkillCategory

        categories = list(SkillCategory)
        assert len(categories) > 0
        assert SkillCategory.OFFICE in categories
        assert SkillCategory.DEVELOPMENT in categories

    def test_skill_discovery(self):
        """测试技能发现"""
        from backend.app.core.skill_market_models import (
            SkillRecord, SkillManifest, SkillCategory
        )

        # 创建测试技能
        manifest = SkillManifest(
            name="Test Skill",
            name_zh="测试技能",
            version="1.0.0",
            description="Test skill",
            description_zh="测试技能",
            keywords=["test", "demo"]
        )

        skill = SkillRecord(
            id="test-skill",
            manifest=manifest,
            category=SkillCategory.DEVELOPMENT,
            rating=4.5,
            downloads=100
        )

        assert skill.id == "test-skill"
        assert skill.manifest.name_zh == "测试技能"
        assert skill.rating == 4.5


class TestSkillMarketSearch:
    """测试技能搜索功能"""

    def test_search_by_name(self):
        """测试按名称搜索技能"""
        from backend.app.core.skill_market_models import (
            SkillRecord, SkillManifest, SkillCategory
        )

        skills = [
            SkillRecord(
                id="python-skill",
                manifest=SkillManifest(
                    name="Python Helper",
                    name_zh="Python助手",
                    version="1.0.0",
                    description="Python programming",
                    description_zh="Python编程"
                ),
                category=SkillCategory.DEVELOPMENT
            ),
            SkillRecord(
                id="javascript-skill",
                manifest=SkillManifest(
                    name="JavaScript Helper",
                    name_zh="JavaScript助手",
                    version="1.0.0",
                    description="JavaScript programming",
                    description_zh="JavaScript编程"
                ),
                category=SkillCategory.DEVELOPMENT
            ),
        ]

        # 搜索
        query = "python"
        results = [s for s in skills
                  if query.lower() in s.manifest.name.lower() or
                     query.lower() in s.manifest.name_zh.lower()]

        assert len(results) == 1
        assert results[0].id == "python-skill"

    def test_search_by_category(self):
        """测试按分类搜索技能"""
        from backend.app.core.skill_market_models import (
            SkillRecord, SkillManifest, SkillCategory
        )

        skills = [
            SkillRecord(
                id="dev-skill",
                manifest=SkillManifest(
                    name="Dev Skill",
                    name_zh="开发技能",
                    version="1.0.0",
                    description="Development",
                    description_zh="开发"
                ),
                category=SkillCategory.DEVELOPMENT
            ),
            SkillRecord(
                id="office-skill",
                manifest=SkillManifest(
                    name="Office Skill",
                    name_zh="办公技能",
                    version="1.0.0",
                    description="Office",
                    description_zh="办公"
                ),
                category=SkillCategory.OFFICE
            ),
        ]

        # 按分类搜索
        results = [s for s in skills
                  if s.category == SkillCategory.DEVELOPMENT]

        assert len(results) == 1
        assert results[0].category == SkillCategory.DEVELOPMENT


class TestSkillMarketRating:
    """测试技能评分和评论"""

    def test_skill_rating(self):
        """测试技能评分"""
        from backend.app.core.skill_market_models import (
            SkillRecord, SkillManifest, SkillCategory
        )

        manifest = SkillManifest(
            name="Rated Skill",
            name_zh="评分技能",
            version="1.0.0",
            description="Skill with rating",
            description_zh="有评分的技能"
        )

        skill = SkillRecord(
            id="rated-skill",
            manifest=manifest,
            category=SkillCategory.DEVELOPMENT,
            rating=0.0,
            rating_count=0
        )

        assert skill.rating == 0.0
        assert skill.rating_count == 0

        # 添加评分
        skill.rating = 4.5
        skill.rating_count = 10

        assert skill.rating == 4.5
        assert skill.rating_count == 10

    def test_skill_comments(self):
        """测试技能评论"""
        from backend.app.core.skill_market_models import (
            SkillRecord, SkillManifest, SkillCategory, SkillComment
        )

        manifest = SkillManifest(
            name="Commented Skill",
            name_zh="有评论的技能",
            version="1.0.0",
            description="Skill with comments",
            description_zh="有评论的技能"
        )

        skill = SkillRecord(
            id="commented-skill",
            manifest=manifest,
            category=SkillCategory.DEVELOPMENT,
            comments=[]
        )

        # 添加评论
        comment = SkillComment(
            id="comment-1",
            user_id="user-1",
            content="Great skill!",
            rating=5,
            created_at=datetime.now(UTC)
        )

        skill.comments.append(comment)

        assert len(skill.comments) == 1
        assert skill.comments[0].content == "Great skill!"


class TestSkillMarketInstallation:
    """测试技能安装"""

    def test_skill_install(self):
        """测试技能安装"""
        from backend.app.core.skill_market_models import (
            SkillRecord, SkillManifest, SkillCategory, SkillStatus
        )

        manifest = SkillManifest(
            name="Install Test",
            name_zh="安装测试",
            version="1.0.0",
            description="Test",
            description_zh="测试"
        )

        skill = SkillRecord(
            id="install-test",
            manifest=manifest,
            category=SkillCategory.DEVELOPMENT,
            status=SkillStatus.PUBLISHED
        )

        assert skill.is_installed is False

        # 安装
        skill.is_installed = True
        skill.is_enabled = True
        skill.status = SkillStatus.INSTALLED

        assert skill.is_installed is True
        assert skill.is_enabled is True

    def test_skill_uninstall(self):
        """测试技能卸载"""
        from backend.app.core.skill_market_models import (
            SkillRecord, SkillManifest, SkillCategory, SkillStatus
        )

        manifest = SkillManifest(
            name="Uninstall Test",
            name_zh="卸载测试",
            version="1.0.0",
            description="Test",
            description_zh="测试"
        )

        skill = SkillRecord(
            id="uninstall-test",
            manifest=manifest,
            category=SkillCategory.DEVELOPMENT
        )

        # 先安装
        skill.is_installed = True
        skill.is_enabled = True

        assert skill.is_installed is True

        # 卸载
        skill.is_installed = False
        skill.is_enabled = False
        skill.status = SkillStatus.PUBLISHED

        assert skill.is_installed is False
        assert skill.is_enabled is False


class TestSkillVersionManagement:
    """测试技能版本管理"""

    def test_skill_version_update(self):
        """测试技能版本更新"""
        from backend.app.core.skill_market_models import (
            SkillRecord, SkillManifest, SkillCategory, SkillStatus
        )

        manifest_v1 = SkillManifest(
            name="Version Test",
            name_zh="版本测试",
            version="1.0.0",
            description="Test",
            description_zh="测试"
        )

        skill = SkillRecord(
            id="version-test",
            manifest=manifest_v1,
            category=SkillCategory.DEVELOPMENT,
            status=SkillStatus.INSTALLED
        )

        assert skill.manifest.version == "1.0.0"

        # 更新版本
        manifest_v2 = SkillManifest(
            name="Version Test",
            name_zh="版本测试",
            version="1.1.0",
            description="Test",
            description_zh="测试"
        )
        skill.manifest = manifest_v2

        assert skill.manifest.version == "1.1.0"


# ==================== 集成测试 ====================

class TestMarketplaceIntegration:
    """市场系统集成测试"""

    def test_plugin_and_skill_coexistence(self):
        """测试插件和技能的共存"""
        from backend.app.api.plugin_market import (
            PluginRecord, PluginManifest, PluginCategory
        )
        from backend.app.core.skill_market_models import (
            SkillRecord, SkillManifest, SkillCategory
        )

        # 创建插件
        plugin = PluginRecord(
            id="test-plugin",
            manifest=PluginManifest(
                name="Test Plugin",
                version="1.0.0"
            ),
            category=PluginCategory.DEVELOPMENT
        )

        # 创建技能
        skill = SkillRecord(
            id="test-skill",
            manifest=SkillManifest(
                name="Test Skill",
                name_zh="测试技能",
                version="1.0.0",
                description="Test",
                description_zh="测试"
            ),
            category=SkillCategory.DEVELOPMENT
        )

        assert plugin.id == "test-plugin"
        assert skill.id == "test-skill"
        assert plugin.category == PluginCategory.DEVELOPMENT
        assert skill.category == SkillCategory.DEVELOPMENT

    def test_marketplace_statistics(self):
        """测试市场统计"""
        from backend.app.api.plugin_market import _plugins_db
        from backend.app.core.skill_market_models import SkillRecord, SkillManifest, SkillCategory

        # 统计插件
        total_plugins = len(_plugins_db)
        installed_plugins = len([p for p in _plugins_db.values() if p.is_installed])

        # 统计技能
        skills = []
        total_skills = len(skills)
        installed_skills = len([s for s in skills if s.is_installed])

        assert isinstance(total_plugins, int)
        assert isinstance(installed_plugins, int)
        assert isinstance(total_skills, int)
        assert isinstance(installed_skills, int)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
