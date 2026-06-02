"""插件爬虫系统 - 从GitHub、Gitee等开源仓库爬取插件"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import hashlib

logger = logging.getLogger(__name__)


class RepositoryProvider(str, Enum):
    """仓库提供商"""
    GITHUB = "github"
    GITEE = "gitee"
    GITLAB = "gitlab"


@dataclass
class RepositoryConfig:
    """仓库配置"""
    provider: RepositoryProvider
    owner: str
    repo: str
    branch: str = "main"
    token: Optional[str] = None


@dataclass
class PluginMetadata:
    """插件元数据"""
    id: str
    name: str
    version: str
    author: str
    description: str
    description_zh: str
    long_description: str
    long_description_zh: str
    homepage: str
    repository: str
    license: str
    keywords: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    dependencies: dict[str, str] = field(default_factory=dict)
    permissions: list[str] = field(default_factory=list)
    entry_point: str = ""
    icon_url: str = ""
    screenshots: list[str] = field(default_factory=list)
    category: str = "development"
    risk_level: str = "medium"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class PluginCrawler:
    """插件爬虫 - 从开源仓库爬取插件"""

    def __init__(self, cache_dir: str | Path = "./plugin_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_cache: dict[str, PluginMetadata] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """加载缓存"""
        cache_file = self.cache_dir / "manifest_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    data = json.load(f)
                    logger.info(f"Loaded {len(data)} plugins from cache")
            except Exception as e:
                logger.error(f"Failed to load cache: {e}")

    def _save_cache(self) -> None:
        """保存缓存"""
        cache_file = self.cache_dir / "manifest_cache.json"
        try:
            data = {
                plugin_id: {
                    "name": meta.name,
                    "version": meta.version,
                    "description": meta.description,
                    "category": meta.category,
                }
                for plugin_id, meta in self._manifest_cache.items()
            }
            with open(cache_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    async def crawl_github_plugins(
        self,
        query: str = "x-agent-plugin",
        language: str = "python",
        max_results: int = 50,
    ) -> list[PluginMetadata]:
        """从GitHub爬取插件"""
        logger.info(f"Crawling GitHub for plugins: {query}")

        plugins = []
        try:
            # 模拟GitHub API调用
            # 实际应用中应使用 PyGithub 或 httpx
            search_url = (
                f"https://api.github.com/search/repositories?"
                f"q={query}+language:{language}&sort=stars&order=desc&per_page={max_results}"
            )

            # 这里应该进行实际的HTTP请求
            # 为了演示，我们返回模拟数据
            mock_repos = [
                {
                    "name": "github-assistant-plugin",
                    "full_name": "user/github-assistant-plugin",
                    "description": "GitHub API integration for X-Agent",
                    "html_url": "https://github.com/user/github-assistant-plugin",
                    "language": "Python",
                    "stars": 150,
                },
                {
                    "name": "data-processor-plugin",
                    "full_name": "user/data-processor-plugin",
                    "description": "Data processing and analysis plugin",
                    "html_url": "https://github.com/user/data-processor-plugin",
                    "language": "Python",
                    "stars": 120,
                },
            ]

            for repo in mock_repos:
                plugin = await self._extract_plugin_metadata(
                    repo, RepositoryProvider.GITHUB
                )
                if plugin:
                    plugins.append(plugin)
                    self._manifest_cache[plugin.id] = plugin

        except Exception as e:
            logger.error(f"Failed to crawl GitHub: {e}")

        self._save_cache()
        return plugins

    async def crawl_gitee_plugins(
        self,
        query: str = "x-agent-plugin",
        max_results: int = 50,
    ) -> list[PluginMetadata]:
        """从Gitee爬取插件"""
        logger.info(f"Crawling Gitee for plugins: {query}")

        plugins = []
        try:
            # 模拟Gitee API调用
            search_url = (
                f"https://gitee.com/api/v5/search/repositories?"
                f"q={query}&sort=stars_count&order=desc&per_page={max_results}"
            )

            # 这里应该进行实际的HTTP请求
            mock_repos = [
                {
                    "name": "x-agent-plugin-example",
                    "full_name": "user/x-agent-plugin-example",
                    "description": "Example plugin for X-Agent",
                    "html_url": "https://gitee.com/user/x-agent-plugin-example",
                    "language": "Python",
                    "stargazers_count": 100,
                },
            ]

            for repo in mock_repos:
                plugin = await self._extract_plugin_metadata(
                    repo, RepositoryProvider.GITEE
                )
                if plugin:
                    plugins.append(plugin)
                    self._manifest_cache[plugin.id] = plugin

        except Exception as e:
            logger.error(f"Failed to crawl Gitee: {e}")

        self._save_cache()
        return plugins

    async def _extract_plugin_metadata(
        self, repo: dict[str, Any], provider: RepositoryProvider
    ) -> Optional[PluginMetadata]:
        """从仓库提取插件元数据"""
        try:
            repo_name = repo.get("name", "")
            repo_url = repo.get("html_url", "")
            description = repo.get("description", "")

            # 检查是否是X-Agent插件
            if not self._is_xagent_plugin(repo_name, description):
                return None

            # 尝试获取manifest文件
            manifest = await self._fetch_manifest(repo_url, provider)
            if not manifest:
                # 如果没有manifest，从仓库信息生成
                manifest = self._generate_manifest_from_repo(repo)

            # 生成插件ID
            plugin_id = self._generate_plugin_id(repo_url)

            # 创建元数据
            metadata = PluginMetadata(
                id=plugin_id,
                name=manifest.get("name", repo_name),
                version=manifest.get("version", "1.0.0"),
                author=manifest.get("author", ""),
                description=manifest.get("description", description),
                description_zh=manifest.get("description_zh", ""),
                long_description=manifest.get("long_description", ""),
                long_description_zh=manifest.get("long_description_zh", ""),
                homepage=manifest.get("homepage", repo_url),
                repository=repo_url,
                license=manifest.get("license", "MIT"),
                keywords=manifest.get("keywords", []),
                capabilities=manifest.get("capabilities", []),
                dependencies=manifest.get("dependencies", {}),
                permissions=manifest.get("permissions", []),
                entry_point=manifest.get("entry_point", ""),
                icon_url=manifest.get("icon_url", ""),
                screenshots=manifest.get("screenshots", []),
                category=manifest.get("category", "development"),
                risk_level=manifest.get("risk_level", "medium"),
            )

            logger.info(f"Extracted plugin: {metadata.name} from {repo_url}")
            return metadata

        except Exception as e:
            logger.error(f"Failed to extract metadata from {repo}: {e}")
            return None

    @staticmethod
    def _is_xagent_plugin(repo_name: str, description: str) -> bool:
        """检查是否是X-Agent插件"""
        keywords = ["x-agent", "plugin", "xagent"]
        text = f"{repo_name} {description}".lower()
        return any(keyword in text for keyword in keywords)

    async def _fetch_manifest(
        self, repo_url: str, provider: RepositoryProvider
    ) -> Optional[dict[str, Any]]:
        """获取插件manifest文件"""
        try:
            # 构建manifest URL
            if provider == RepositoryProvider.GITHUB:
                manifest_url = (
                    repo_url.replace("github.com", "raw.githubusercontent.com")
                    + "/main/plugin.manifest.json"
                )
            elif provider == RepositoryProvider.GITEE:
                manifest_url = (
                    repo_url + "/raw/main/plugin.manifest.json"
                )
            else:
                return None

            # 这里应该进行实际的HTTP请求
            # 为了演示，返回模拟数据
            logger.debug(f"Fetching manifest from {manifest_url}")
            return None  # 实际应该返回解析的JSON

        except Exception as e:
            logger.error(f"Failed to fetch manifest: {e}")
            return None

    def _generate_manifest_from_repo(self, repo: dict[str, Any]) -> dict[str, Any]:
        """从仓库信息生成manifest"""
        return {
            "name": repo.get("name", ""),
            "version": "1.0.0",
            "description": repo.get("description", ""),
            "description_zh": "",
            "author": repo.get("owner", {}).get("login", ""),
            "license": "MIT",
            "keywords": [],
            "capabilities": [],
            "dependencies": {},
            "permissions": [],
            "category": "development",
            "risk_level": "medium",
        }

    @staticmethod
    def _generate_plugin_id(repo_url: str) -> str:
        """生成插件ID"""
        hash_obj = hashlib.md5(repo_url.encode())
        return hash_obj.hexdigest()[:12]

    async def crawl_all_plugins(self) -> list[PluginMetadata]:
        """爬取所有插件"""
        logger.info("Starting plugin crawl...")

        all_plugins = []

        # 并行爬取
        github_plugins = await self.crawl_github_plugins()
        gitee_plugins = await self.crawl_gitee_plugins()

        all_plugins.extend(github_plugins)
        all_plugins.extend(gitee_plugins)

        logger.info(f"Crawled {len(all_plugins)} plugins total")
        return all_plugins

    def get_cached_plugins(self) -> list[PluginMetadata]:
        """获取缓存的插件"""
        return list(self._manifest_cache.values())


class PluginClassifier:
    """插件分类器 - 自动分类和标签提取"""

    # 分类关键词映射
    CATEGORY_KEYWORDS = {
        "office": ["document", "word", "excel", "ppt", "office", "办公", "文档", "表格"],
        "design": ["image", "photo", "video", "design", "ui", "图片", "视频", "设计"],
        "development": ["code", "git", "debug", "build", "dev", "代码", "调试", "开发"],
        "data": ["data", "analysis", "chart", "report", "数据", "分析", "图表", "报表"],
        "automation": ["auto", "task", "schedule", "workflow", "自动", "任务", "工作流"],
        "network": ["api", "http", "web", "crawler", "爬虫", "网络", "接口"],
        "system": ["file", "system", "monitor", "performance", "文件", "系统", "监控"],
        "learning": ["note", "knowledge", "study", "learn", "笔记", "知识", "学习"],
    }

    @staticmethod
    def classify_plugin(metadata: PluginMetadata) -> str:
        """分类插件"""
        text = (
            f"{metadata.name} {metadata.description} {metadata.description_zh}"
        ).lower()

        # 计算每个分类的匹配分数
        scores = {}
        for category, keywords in PluginClassifier.CATEGORY_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in text)
            scores[category] = score

        # 返回最高分的分类
        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        return "development"  # 默认分类

    @staticmethod
    def extract_tags(metadata: PluginMetadata) -> list[str]:
        """提取标签"""
        tags = []

        # 从关键词提取
        tags.extend(metadata.keywords)

        # 从能力提取
        tags.extend(metadata.capabilities)

        # 从描述提取（简单的关键词提取）
        description = (
            f"{metadata.description} {metadata.description_zh}"
        ).lower()
        common_tags = [
            "automation", "integration", "productivity", "analysis",
            "自动化", "集成", "生产力", "分析"
        ]
        for tag in common_tags:
            if tag in description:
                tags.append(tag)

        # 去重
        return list(set(tags))

    @staticmethod
    def calculate_similarity(
        plugin1: PluginMetadata, plugin2: PluginMetadata
    ) -> float:
        """计算插件相似度"""
        # 基于能力和标签的相似度
        caps1 = set(plugin1.capabilities)
        caps2 = set(plugin2.capabilities)

        if not caps1 or not caps2:
            return 0.0

        intersection = len(caps1 & caps2)
        union = len(caps1 | caps2)

        return intersection / union if union > 0 else 0.0

    @staticmethod
    def recommend_related_plugins(
        plugin: PluginMetadata, all_plugins: list[PluginMetadata], top_n: int = 5
    ) -> list[PluginMetadata]:
        """推荐相关插件"""
        similarities = [
            (other, PluginClassifier.calculate_similarity(plugin, other))
            for other in all_plugins
            if other.id != plugin.id
        ]

        # 按相似度排序
        similarities.sort(key=lambda x: x[1], reverse=True)

        return [plugin for plugin, _ in similarities[:top_n]]
