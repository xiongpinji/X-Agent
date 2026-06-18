"""插件市场系统初始化和集成配置"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from backend.app.api.plugin_market import _plugins_db, _categories_db
from backend.app.services.plugin_crawler import PluginCrawler, PluginClassifier
from backend.app.services.translation_service import PluginLocalizer
from backend.app.core.plugin_adapter import PluginAdapter, PluginIntegration

logger = logging.getLogger(__name__)


class PluginMarketInitializer:
    """插件市场系统初始化器"""

    def __init__(self, base_dir: str | Path = "./"):
        self.base_dir = Path(base_dir)
        self.plugins_dir = self.base_dir / "plugins"
        self.cache_dir = self.base_dir / ".plugin_cache"

        self.crawler = PluginCrawler(cache_dir=self.cache_dir)
        self.adapter = PluginAdapter(plugins_dir=self.plugins_dir)
        self.integration = PluginIntegration(plugins_dir=self.plugins_dir)

    async def initialize_system(self) -> bool:
        """初始化插件市场系统"""
        try:
            logger.info("Initializing plugin market system...")

            # 1. 创建必要的目录
            self._create_directories()

            # 2. 加载本地插件
            self._load_local_plugins()

            # 3. 爬取开源插件（可选）
            # await self._crawl_open_source_plugins()

            # 4. 初始化推荐系统
            self._initialize_recommendations()

            logger.info("Plugin market system initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize plugin market system: {e}")
            return False

    def _create_directories(self) -> None:
        """创建必要的目录"""
        directories = [
            self.plugins_dir,
            self.cache_dir,
            self.plugins_dir / "installed",
            self.plugins_dir / "disabled",
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory: {directory}")

    def _load_local_plugins(self) -> None:
        """加载本地插件"""
        logger.info("Loading local plugins...")

        # 扫描插件目录
        for plugin_dir in self.plugins_dir.glob("*-plugin"):
            if not plugin_dir.is_dir():
                continue

            manifest_file = plugin_dir / "plugin.manifest.json"
            if not manifest_file.exists():
                logger.warning(f"Manifest not found: {manifest_file}")
                continue

            try:
                manifest = self.adapter.parse_manifest(manifest_file)
                if not manifest:
                    continue

                # 验证manifest
                validation_report = self.adapter.validate_manifest(manifest)
                if validation_report.status.value == "incompatible":
                    logger.warning(
                        f"Plugin validation failed: {plugin_dir.name}"
                    )
                    continue

                # 分类插件
                category = PluginClassifier.classify_plugin(
                    self._create_plugin_metadata(manifest)
                )

                # 中文化插件
                localized = PluginLocalizer.localize_plugin(
                    name=manifest.get("name", ""),
                    description=manifest.get("description", ""),
                    description_zh=manifest.get("description_zh", ""),
                    long_description=manifest.get("long_description", ""),
                    long_description_zh=manifest.get("long_description_zh", ""),
                    capabilities=manifest.get("capabilities", []),
                    category=category,
                    entry_point=manifest.get("entry_point", ""),
                )

                # 创建插件记录
                from backend.app.api.plugin_market import PluginRecord, PluginManifest, PluginStatus, PluginRiskLevel

                plugin_manifest = PluginManifest(**manifest)
                plugin_record = PluginRecord(
                    id=self._generate_plugin_id(plugin_dir.name),
                    manifest=plugin_manifest,
                    category=category,
                    status=PluginStatus.PUBLISHED,
                    risk_level=PluginRiskLevel(manifest.get("risk_level", "medium")),
                    what_is_it=localized.get("description_zh", ""),
                    who_is_it_for=localized.get("who_is_it_for", ""),
                    how_to_use=localized.get("how_to_use", ""),
                    faq=localized.get("faq", []),
                    tutorial=localized.get("tutorial", ""),
                )

                _plugins_db[plugin_record.id] = plugin_record
                logger.info(f"Loaded plugin: {manifest.get('name', 'unknown')}")

            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_dir.name}: {e}")

    async def _crawl_open_source_plugins(self) -> None:
        """爬取开源插件"""
        logger.info("Crawling open source plugins...")

        try:
            # 爬取GitHub插件
            github_plugins = await self.crawler.crawl_github_plugins()
            logger.info(f"Crawled {len(github_plugins)} plugins from GitHub")

            # 爬取Gitee插件
            gitee_plugins = await self.crawler.crawl_gitee_plugins()
            logger.info(f"Crawled {len(gitee_plugins)} plugins from Gitee")

            # 处理爬取的插件
            all_plugins = github_plugins + gitee_plugins
            for metadata in all_plugins:
                # 分类
                category = PluginClassifier.classify_plugin(metadata)

                # 中文化
                localized = PluginLocalizer.localize_plugin(
                    name=metadata.name,
                    description=metadata.description,
                    description_zh=metadata.description_zh,
                    long_description=metadata.long_description,
                    long_description_zh=metadata.long_description_zh,
                    capabilities=metadata.capabilities,
                    category=category,
                    entry_point=metadata.entry_point,
                )

                # 创建插件记录
                from backend.app.api.plugin_market import PluginRecord, PluginManifest, PluginStatus, PluginRiskLevel

                plugin_manifest = PluginManifest(
                    name=metadata.name,
                    version=metadata.version,
                    author=metadata.author,
                    description=metadata.description,
                    description_zh=metadata.description_zh,
                    long_description=metadata.long_description,
                    long_description_zh=metadata.long_description_zh,
                    homepage=metadata.homepage,
                    repository=metadata.repository,
                    license=metadata.license,
                    keywords=metadata.keywords,
                    capabilities=metadata.capabilities,
                    dependencies=metadata.dependencies,
                    permissions=metadata.permissions,
                    entry_point=metadata.entry_point,
                    icon_url=metadata.icon_url,
                    screenshots=metadata.screenshots,
                )

                plugin_record = PluginRecord(
                    id=metadata.id,
                    manifest=plugin_manifest,
                    category=category,
                    status=PluginStatus.PUBLISHED,
                    risk_level=PluginRiskLevel(metadata.risk_level),
                    what_is_it=localized.get("description_zh", ""),
                    who_is_it_for=localized.get("who_is_it_for", ""),
                    how_to_use=localized.get("how_to_use", ""),
                    faq=localized.get("faq", []),
                    tutorial=localized.get("tutorial", ""),
                )

                _plugins_db[plugin_record.id] = plugin_record

        except Exception as e:
            logger.error(f"Failed to crawl open source plugins: {e}")

    def _initialize_recommendations(self) -> None:
        """初始化推荐系统"""
        logger.info("Initializing recommendation system...")

        # 计算插件相似度
        plugins = list(_plugins_db.values())
        for plugin in plugins:
            # 这里可以预计算相似度矩阵
            pass

        logger.info(f"Initialized recommendations for {len(plugins)} plugins")

    def _create_plugin_metadata(self, manifest: dict) -> object:
        """从manifest创建插件元数据对象"""
        from backend.app.services.plugin_crawler import PluginMetadata

        return PluginMetadata(
            id=self._generate_plugin_id(manifest.get("name", "")),
            name=manifest.get("name", ""),
            version=manifest.get("version", "1.0.0"),
            author=manifest.get("author", ""),
            description=manifest.get("description", ""),
            description_zh=manifest.get("description_zh", ""),
            long_description=manifest.get("long_description", ""),
            long_description_zh=manifest.get("long_description_zh", ""),
            homepage=manifest.get("homepage", ""),
            repository=manifest.get("repository", ""),
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

    @staticmethod
    def _generate_plugin_id(name: str) -> str:
        """生成插件ID"""
        import hashlib

        hash_obj = hashlib.md5(name.encode(), usedforsecurity=False)
        return hash_obj.hexdigest()[:12]


# 全局初始化器实例
_initializer: Optional[PluginMarketInitializer] = None


def get_plugin_market_initializer() -> PluginMarketInitializer:
    """获取插件市场初始化器"""
    global _initializer
    if _initializer is None:
        _initializer = PluginMarketInitializer()
    return _initializer


async def initialize_plugin_market() -> bool:
    """初始化插件市场"""
    initializer = get_plugin_market_initializer()
    return await initializer.initialize_system()
