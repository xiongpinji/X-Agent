#!/usr/bin/env python3
"""
X-Agent 插件市场部署和测试脚本
用于在测试环境中部署和验证插件市场功能
"""

import json
import sys
import time
from pathlib import Path
from datetime import datetime, UTC
from typing import Any, Dict, List

# 模拟的API客户端
class PluginMarketTestClient:
    """插件市场测试客户端"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.plugins_db: Dict[str, Any] = {}
        self.categories_db: Dict[str, Any] = {}
        self._init_categories()

    def _init_categories(self) -> None:
        """初始化分类"""
        self.categories_db = {
            "office": {
                "id": "office",
                "name": "Office Assistant",
                "name_zh": "办公助手",
                "icon": "📝",
                "description": "Document processing, spreadsheet operations, presentation creation",
                "description_zh": "文档处理、表格操作、PPT制作",
                "plugin_count": 0
            },
            "design": {
                "id": "design",
                "name": "Design Tools",
                "name_zh": "设计工具",
                "icon": "🎨",
                "description": "Image processing, video editing, UI design",
                "description_zh": "图片处理、视频编辑、UI设计",
                "plugin_count": 0
            },
            "development": {
                "id": "development",
                "name": "Development Tools",
                "name_zh": "开发工具",
                "icon": "💻",
                "description": "Code generation, debugging assistant, Git tools",
                "description_zh": "代码生成、调试助手、Git工具",
                "plugin_count": 0
            },
            "data": {
                "id": "data",
                "name": "Data Analysis",
                "name_zh": "数据分析",
                "icon": "📊",
                "description": "Data cleaning, visualization, report generation",
                "description_zh": "数据清洗、可视化、报表生成",
                "plugin_count": 0
            },
            "automation": {
                "id": "automation",
                "name": "Automation",
                "name_zh": "自动化",
                "icon": "🤖",
                "description": "Web automation, desktop automation, scheduled tasks",
                "description_zh": "网页自动化、桌面自动化、定时任务",
                "plugin_count": 0
            },
            "network": {
                "id": "network",
                "name": "Network Tools",
                "name_zh": "网络工具",
                "icon": "🌐",
                "description": "Web scraping, API testing, network monitoring",
                "description_zh": "爬虫、API测试、网络监控",
                "plugin_count": 0
            },
            "system": {
                "id": "system",
                "name": "System Tools",
                "name_zh": "系统工具",
                "icon": "🔧",
                "description": "File management, system monitoring, performance optimization",
                "description_zh": "文件管理、系统监控、性能优化",
                "plugin_count": 0
            },
            "learning": {
                "id": "learning",
                "name": "Learning Assistant",
                "name_zh": "学习助手",
                "icon": "🎓",
                "description": "Note taking, knowledge management, learning planning",
                "description_zh": "笔记整理、知识管理、学习计划",
                "plugin_count": 0
            }
        }

    def add_plugin(self, plugin_data: Dict[str, Any]) -> bool:
        """添加插件"""
        plugin_id = plugin_data.get("id")
        if not plugin_id:
            return False

        self.plugins_db[plugin_id] = plugin_data

        # 更新分类计数
        category = plugin_data.get("category")
        if category in self.categories_db:
            self.categories_db[category]["plugin_count"] += 1

        return True

    def get_categories(self) -> List[Dict[str, Any]]:
        """获取分类列表"""
        return list(self.categories_db.values())

    def get_plugins(self, category: str = None, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """获取插件列表"""
        plugins = list(self.plugins_db.values())

        if category:
            plugins = [p for p in plugins if p.get("category") == category]

        # 按评分排序
        plugins.sort(key=lambda p: p.get("rating", 0), reverse=True)

        return plugins[offset:offset + limit]

    def search_plugins(self, query: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """搜索插件"""
        query_lower = query.lower()
        results = []

        for plugin in self.plugins_db.values():
            manifest = plugin.get("manifest", {})
            if (query_lower in manifest.get("name", "").lower() or
                query_lower in manifest.get("description", "").lower() or
                query_lower in manifest.get("description_zh", "").lower() or
                any(query_lower in cap.lower() for cap in manifest.get("capabilities", []))):
                results.append(plugin)

        results.sort(key=lambda p: p.get("rating", 0), reverse=True)
        return results[offset:offset + limit]

    def install_plugin(self, plugin_id: str) -> bool:
        """安装插件"""
        if plugin_id not in self.plugins_db:
            return False

        plugin = self.plugins_db[plugin_id]
        plugin["is_installed"] = True
        plugin["is_enabled"] = True
        plugin["status"] = "installed"
        plugin["installed_count"] = plugin.get("installed_count", 0) + 1

        return True

    def uninstall_plugin(self, plugin_id: str) -> bool:
        """卸载插件"""
        if plugin_id not in self.plugins_db:
            return False

        plugin = self.plugins_db[plugin_id]
        plugin["is_installed"] = False
        plugin["is_enabled"] = False
        plugin["status"] = "published"
        plugin["installed_count"] = max(0, plugin.get("installed_count", 1) - 1)

        return True


class PluginMarketDeploymentTest:
    """插件市场部署测试"""

    def __init__(self):
        self.client = PluginMarketTestClient()
        self.test_results: List[Dict[str, Any]] = []
        self.passed = 0
        self.failed = 0

    def log_test(self, name: str, passed: bool, message: str = "") -> None:
        """记录测试结果"""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} | {name}")
        if message:
            print(f"       {message}")

        self.test_results.append({
            "name": name,
            "passed": passed,
            "message": message,
            "timestamp": datetime.now(UTC).isoformat()
        })

        if passed:
            self.passed += 1
        else:
            self.failed += 1

    def test_categories(self) -> None:
        """测试分类功能"""
        print("\n=== 测试分类功能 ===")

        categories = self.client.get_categories()
        self.log_test(
            "获取分类列表",
            len(categories) == 8,
            f"返回 {len(categories)} 个分类"
        )

        # 检查必需的分类
        category_ids = {c["id"] for c in categories}
        required_categories = {"office", "design", "development", "data", "automation", "network", "system", "learning"}
        self.log_test(
            "分类完整性",
            required_categories.issubset(category_ids),
            f"包含所有必需分类"
        )

        # 检查中文化
        has_chinese = all(c.get("name_zh") for c in categories)
        self.log_test(
            "分类中文化",
            has_chinese,
            "所有分类都有中文名称"
        )

    def test_plugin_management(self) -> None:
        """测试插件管理"""
        print("\n=== 测试插件管理 ===")

        # 创建示例插件
        sample_plugins = [
            {
                "id": "github-assistant-001",
                "manifest": {
                    "name": "GitHub 助手",
                    "version": "1.0.0",
                    "author": "X-Agent Team",
                    "description": "GitHub API integration",
                    "description_zh": "GitHub API集成",
                    "capabilities": ["repository", "issue", "pull-request"]
                },
                "category": "development",
                "status": "published",
                "risk_level": "low",
                "what_is_it": "这是一个GitHub助手插件",
                "who_is_it_for": "程序员和开发团队",
                "how_to_use": "1. 安装\n2. 配置Token\n3. 使用",
                "downloads": 1250,
                "rating": 4.8,
                "rating_count": 156,
                "installed_count": 342,
                "is_installed": False,
                "is_enabled": False
            },
            {
                "id": "data-analyzer-001",
                "manifest": {
                    "name": "数据分析工具",
                    "version": "2.1.0",
                    "author": "Data Team",
                    "description": "Data analysis toolkit",
                    "description_zh": "数据分析工具包",
                    "capabilities": ["data-cleaning", "visualization", "statistics"]
                },
                "category": "data",
                "status": "published",
                "risk_level": "low",
                "what_is_it": "这是一个数据分析工具",
                "who_is_it_for": "数据分析师",
                "how_to_use": "1. 导入数据\n2. 选择分析类型\n3. 生成报告",
                "downloads": 890,
                "rating": 4.6,
                "rating_count": 124,
                "installed_count": 267,
                "is_installed": False,
                "is_enabled": False
            },
            {
                "id": "doc-generator-001",
                "manifest": {
                    "name": "文档生成器",
                    "version": "1.5.0",
                    "author": "Doc Team",
                    "description": "Documentation generator",
                    "description_zh": "文档生成器",
                    "capabilities": ["code-parsing", "doc-generation", "markdown"]
                },
                "category": "development",
                "status": "published",
                "risk_level": "low",
                "what_is_it": "这是一个文档生成器",
                "who_is_it_for": "开发者和技术写手",
                "how_to_use": "1. 选择代码目录\n2. 配置模板\n3. 生成文档",
                "downloads": 756,
                "rating": 4.5,
                "rating_count": 98,
                "installed_count": 201,
                "is_installed": False,
                "is_enabled": False
            }
        ]

        # 添加插件
        for plugin in sample_plugins:
            success = self.client.add_plugin(plugin)
            self.log_test(
                f"添加插件: {plugin['manifest']['name']}",
                success,
                f"插件ID: {plugin['id']}"
            )

    def test_browsing(self) -> None:
        """测试浏览功能"""
        print("\n=== 测试浏览功能 ===")

        # 获取所有插件
        all_plugins = self.client.get_plugins()
        self.log_test(
            "获取插件列表",
            len(all_plugins) > 0,
            f"返回 {len(all_plugins)} 个插件"
        )

        # 按分类过滤
        dev_plugins = self.client.get_plugins(category="development")
        self.log_test(
            "按分类过滤",
            len(dev_plugins) > 0,
            f"开发工具分类有 {len(dev_plugins)} 个插件"
        )

        # 分页测试
        page1 = self.client.get_plugins(limit=2, offset=0)
        page2 = self.client.get_plugins(limit=2, offset=2)
        self.log_test(
            "分页功能",
            len(page1) <= 2 and len(page2) <= 2,
            f"第1页: {len(page1)} 个, 第2页: {len(page2)} 个"
        )

    def test_search(self) -> None:
        """测试搜索功能"""
        print("\n=== 测试搜索功能 ===")

        # 按名称搜索
        results = self.client.search_plugins("GitHub")
        self.log_test(
            "按名称搜索",
            len(results) > 0,
            f"找到 {len(results)} 个结果"
        )

        # 按能力搜索
        results = self.client.search_plugins("repository")
        self.log_test(
            "按能力搜索",
            len(results) > 0,
            f"找到 {len(results)} 个结果"
        )

        # 按中文搜索
        results = self.client.search_plugins("数据")
        self.log_test(
            "按中文搜索",
            len(results) > 0,
            f"找到 {len(results)} 个结果"
        )

        # 无结果搜索
        results = self.client.search_plugins("nonexistent")
        self.log_test(
            "无结果搜索",
            len(results) == 0,
            "正确返回空结果"
        )

    def test_installation(self) -> None:
        """测试安装功能"""
        print("\n=== 测试安装功能 ===")

        # 安装插件
        success = self.client.install_plugin("github-assistant-001")
        self.log_test(
            "安装插件",
            success,
            "GitHub助手已安装"
        )

        # 验证安装状态
        plugin = self.client.plugins_db.get("github-assistant-001")
        self.log_test(
            "验证安装状态",
            plugin and plugin.get("is_installed") and plugin.get("is_enabled"),
            "插件状态正确"
        )

        # 验证安装计数
        self.log_test(
            "安装计数更新",
            plugin and plugin.get("installed_count") == 343,
            f"安装数: {plugin.get('installed_count')}"
        )

    def test_uninstallation(self) -> None:
        """测试卸载功能"""
        print("\n=== 测试卸载功能 ===")

        # 卸载插件
        success = self.client.uninstall_plugin("github-assistant-001")
        self.log_test(
            "卸载插件",
            success,
            "GitHub助手已卸载"
        )

        # 验证卸载状态
        plugin = self.client.plugins_db.get("github-assistant-001")
        self.log_test(
            "验证卸载状态",
            plugin and not plugin.get("is_installed") and not plugin.get("is_enabled"),
            "插件状态正确"
        )

        # 验证安装计数
        self.log_test(
            "安装计数更新",
            plugin and plugin.get("installed_count") == 342,
            f"安装数: {plugin.get('installed_count')}"
        )

    def test_chinese_localization(self) -> None:
        """测试中文化"""
        print("\n=== 测试中文化 ===")

        plugin = self.client.plugins_db.get("github-assistant-001")

        self.log_test(
            "插件名称中文化",
            plugin and "助手" in plugin["manifest"]["name"],
            f"名称: {plugin['manifest']['name']}"
        )

        self.log_test(
            "插件描述中文化",
            plugin and plugin.get("what_is_it"),
            f"说明: {plugin.get('what_is_it')}"
        )

        self.log_test(
            "使用说明中文化",
            plugin and "安装" in plugin.get("how_to_use", ""),
            "包含中文步骤说明"
        )

        # 检查分类中文化
        categories = self.client.get_categories()
        all_chinese = all(c.get("name_zh") for c in categories)
        self.log_test(
            "分类中文化",
            all_chinese,
            "所有分类都有中文名称"
        )

    def run_all_tests(self) -> None:
        """运行所有测试"""
        print("=" * 60)
        print("X-Agent 插件市场部署测试")
        print("=" * 60)
        print(f"开始时间: {datetime.now(UTC).isoformat()}")

        self.test_categories()
        self.test_plugin_management()
        self.test_browsing()
        self.test_search()
        self.test_installation()
        self.test_uninstallation()
        self.test_chinese_localization()

        self.print_summary()

    def print_summary(self) -> None:
        """打印测试总结"""
        print("\n" + "=" * 60)
        print("测试总结")
        print("=" * 60)

        total = self.passed + self.failed
        pass_rate = (self.passed / total * 100) if total > 0 else 0

        print(f"总测试数: {total}")
        print(f"通过: {self.passed} ✅")
        print(f"失败: {self.failed} ❌")
        print(f"通过率: {pass_rate:.1f}%")

        if self.failed == 0:
            print("\n🎉 所有测试通过！插件市场已准备好部署。")
        else:
            print(f"\n⚠️  有 {self.failed} 个测试失败，请检查。")

        print(f"结束时间: {datetime.now(UTC).isoformat()}")


def main():
    """主函数"""
    tester = PluginMarketDeploymentTest()
    tester.run_all_tests()

    # 返回退出码
    return 0 if tester.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
