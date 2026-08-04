"""插件市场API - 完整的插件发现、搜索、安装、管理功能"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/plugin-market", tags=["plugin-market"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# ==================== 数据模型 ====================

class PluginCategory(StrEnum):
    """插件分类"""
    OFFICE = "office"  # 办公助手
    DESIGN = "design"  # 设计工具
    DEVELOPMENT = "development"  # 开发工具
    DATA = "data"  # 数据分析
    AUTOMATION = "automation"  # 自动化
    NETWORK = "network"  # 网络工具
    SYSTEM = "system"  # 系统工具
    LEARNING = "learning"  # 学习助手


class PluginStatus(StrEnum):
    """插件状态"""
    DRAFT = "draft"  # 草稿
    PUBLISHED = "published"  # 已发布
    INSTALLING = "installing"  # 安装中
    INSTALLED = "installed"  # 已安装
    UPDATING = "updating"  # 更新中
    DISABLED = "disabled"  # 已禁用
    ERROR = "error"  # 错误


class PluginRiskLevel(StrEnum):
    """风险等级"""
    LOW = "low"  # 低
    MEDIUM = "medium"  # 中
    HIGH = "high"  # 高
    CRITICAL = "critical"  # 严重


class PluginManifest(BaseModel):
    """插件清单"""
    name: str = Field(..., description="插件名称")
    version: str = Field(..., description="版本号")
    author: str = Field(default="", description="作者")
    description: str = Field(default="", description="简短描述")
    description_zh: str = Field(default="", description="中文描述")
    long_description: str = Field(default="", description="详细描述")
    long_description_zh: str = Field(default="", description="中文详细描述")
    homepage: str = Field(default="", description="主页")
    repository: str = Field(default="", description="仓库地址")
    license: str = Field(default="MIT", description="许可证")
    keywords: list[str] = Field(default_factory=list, description="关键词")
    capabilities: list[str] = Field(default_factory=list, description="能力列表")
    dependencies: dict[str, str] = Field(default_factory=dict, description="依赖")
    permissions: list[str] = Field(default_factory=list, description="权限")
    entry_point: str = Field(default="", description="入口点")
    icon_url: str = Field(default="", description="图标URL")
    screenshots: list[str] = Field(default_factory=list, description="截图")


class PluginRecord(BaseModel):
    """插件记录"""
    id: str = Field(..., description="插件ID")
    manifest: PluginManifest = Field(..., description="插件清单")
    category: PluginCategory = Field(..., description="分类")
    status: PluginStatus = Field(default=PluginStatus.PUBLISHED, description="状态")
    risk_level: PluginRiskLevel = Field(default=PluginRiskLevel.MEDIUM, description="风险等级")

    # 中文化内容
    what_is_it: str = Field(default="", description="这个插件是干什么的")
    who_is_it_for: str = Field(default="", description="适合谁用")
    how_to_use: str = Field(default="", description="怎么用（步骤化）")
    faq: list[dict[str, str]] = Field(default_factory=list, description="常见问题")
    tutorial: str = Field(default="", description="使用教程")

    # 统计信息
    downloads: int = Field(default=0, description="下载次数")
    rating: float = Field(default=0.0, description="评分")
    rating_count: int = Field(default=0, description="评分数")
    installed_count: int = Field(default=0, description="安装数")

    # 时间戳
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="创建时间")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="更新时间")
    published_at: datetime | None = Field(default=None, description="发布时间")

    # 用户相关
    is_installed: bool = Field(default=False, description="是否已安装")
    is_enabled: bool = Field(default=False, description="是否已启用")
    install_path: str | None = Field(default=None, description="安装路径")


class PluginCategoryInfo(BaseModel):
    """分类信息"""
    id: str = Field(..., description="分类ID")
    name: str = Field(..., description="分类名称")
    name_zh: str = Field(..., description="中文名称")
    icon: str = Field(..., description="图标")
    description: str = Field(..., description="描述")
    description_zh: str = Field(..., description="中文描述")
    plugin_count: int = Field(default=0, description="插件数量")


class PluginInstallRequest(BaseModel):
    """安装请求"""
    plugin_id: str = Field(..., description="插件ID")
    version: str | None = Field(default=None, description="版本")
    config: dict = Field(default_factory=dict, description="配置")
    auto_enable: bool = Field(default=True, description="自动启用")


class PluginUninstallRequest(BaseModel):
    """卸载请求"""
    plugin_id: str = Field(..., description="插件ID")
    remove_config: bool = Field(default=False, description="删除配置")


class PluginSearchRequest(BaseModel):
    """搜索请求"""
    query: str = Field(..., description="搜索词")
    category: PluginCategory | None = Field(default=None, description="分类")
    sort_by: str = Field(default="rating", description="排序方式")
    limit: int = Field(default=20, description="限制数量")
    offset: int = Field(default=0, description="偏移量")


class PluginInstallationProgress(BaseModel):
    """安装进度"""
    plugin_id: str = Field(..., description="插件ID")
    status: str = Field(..., description="状态")
    progress: int = Field(default=0, description="进度百分比")
    message: str = Field(default="", description="消息")
    error: str | None = Field(default=None, description="错误信息")


# ==================== 模拟数据存储 ====================

# 在实际应用中，这些应该存储在数据库中
_plugins_db: dict[str, PluginRecord] = {}
_categories_db: dict[str, PluginCategoryInfo] = {}
_installation_progress: dict[str, PluginInstallationProgress] = {}

# 初始化分类
_categories_db = {
    "office": PluginCategoryInfo(
        id="office",
        name="Office Assistant",
        name_zh="办公助手",
        icon="📝",
        description="Document processing, spreadsheet operations, presentation creation",
        description_zh="文档处理、表格操作、PPT制作"
    ),
    "design": PluginCategoryInfo(
        id="design",
        name="Design Tools",
        name_zh="设计工具",
        icon="🎨",
        description="Image processing, video editing, UI design",
        description_zh="图片处理、视频编辑、UI设计"
    ),
    "development": PluginCategoryInfo(
        id="development",
        name="Development Tools",
        name_zh="开发工具",
        icon="💻",
        description="Code generation, debugging assistant, Git tools",
        description_zh="代码生成、调试助手、Git工具"
    ),
    "data": PluginCategoryInfo(
        id="data",
        name="Data Analysis",
        name_zh="数据分析",
        icon="📊",
        description="Data cleaning, visualization, report generation",
        description_zh="数据清洗、可视化、报表生成"
    ),
    "automation": PluginCategoryInfo(
        id="automation",
        name="Automation",
        name_zh="自动化",
        icon="🤖",
        description="Web automation, desktop automation, scheduled tasks",
        description_zh="网页自动化、桌面自动化、定时任务"
    ),
    "network": PluginCategoryInfo(
        id="network",
        name="Network Tools",
        name_zh="网络工具",
        icon="🌐",
        description="Web scraping, API testing, network monitoring",
        description_zh="爬虫、API测试、网络监控"
    ),
    "system": PluginCategoryInfo(
        id="system",
        name="System Tools",
        name_zh="系统工具",
        icon="🔧",
        description="File management, system monitoring, performance optimization",
        description_zh="文件管理、系统监控、性能优化"
    ),
    "learning": PluginCategoryInfo(
        id="learning",
        name="Learning Assistant",
        name_zh="学习助手",
        icon="🎓",
        description="Note taking, knowledge management, learning planning",
        description_zh="笔记整理、知识管理、学习计划"
    ),
}


# ==================== API 端点 ====================

@router.get("/categories", response_model=list[PluginCategoryInfo])
async def get_categories(principal: PrincipalDependency) -> list[PluginCategoryInfo]:
    """获取所有分类"""
    enforce_scope(principal, "market:read")
    categories = list(_categories_db.values())
    # 更新插件数量
    for category in categories:
        category.plugin_count = len([p for p in _plugins_db.values() if p.category.value == category.id])
    return categories


@router.get("/plugins", response_model=list[PluginRecord])
async def list_plugins(
    principal: PrincipalDependency,
    category: str | None = Query(None, description="分类"),
    installed_only: bool = Query(False, description="仅已安装"),
    sort_by: str = Query("rating", description="排序方式"),
    limit: int = Query(20, ge=1, le=100, description="限制数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
) -> list[PluginRecord]:
    """获取插件列表"""
    enforce_scope(principal, "market:read")

    plugins = list(_plugins_db.values())

    # 过滤
    if category:
        plugins = [p for p in plugins if p.category.value == category]
    if installed_only:
        plugins = [p for p in plugins if p.is_installed]

    # 排序
    if sort_by == "rating":
        plugins.sort(key=lambda p: p.rating, reverse=True)
    elif sort_by == "downloads":
        plugins.sort(key=lambda p: p.downloads, reverse=True)
    elif sort_by == "newest":
        plugins.sort(key=lambda p: p.created_at, reverse=True)

    # 分页
    return plugins[offset:offset + limit]


@router.get("/plugins/{plugin_id}", response_model=PluginRecord)
async def get_plugin_detail(plugin_id: str, principal: PrincipalDependency) -> PluginRecord:
    """获取插件详情"""
    enforce_scope(principal, "market:read")

    plugin = _plugins_db.get(plugin_id)
    if not plugin:
        raise api_error(404, "PLUGIN_NOT_FOUND", "插件未找到")

    return plugin


@router.post("/plugins/{plugin_id}/install", response_model=PluginInstallationProgress)
async def install_plugin(
    plugin_id: str,
    request: PluginInstallRequest,
    principal: PrincipalDependency,
) -> PluginInstallationProgress:
    """安装插件"""
    enforce_scope(principal, "market:write")

    plugin = _plugins_db.get(plugin_id)
    if not plugin:
        raise api_error(404, "PLUGIN_NOT_FOUND", "插件未找到")

    if plugin.is_installed:
        raise api_error(400, "ALREADY_INSTALLED", "插件已安装")

    # 创建安装进度记录
    progress = PluginInstallationProgress(
        plugin_id=plugin_id,
        status="installing",
        progress=0,
        message="开始安装..."
    )
    _installation_progress[plugin_id] = progress

    # 更新插件状态
    plugin.status = PluginStatus.INSTALLING
    plugin.is_installed = True
    if request.auto_enable:
        plugin.is_enabled = True
        plugin.status = PluginStatus.INSTALLED

    # 更新安装数
    plugin.installed_count += 1
    plugin.updated_at = datetime.now(UTC)

    # 更新进度
    progress.progress = 100
    progress.status = "completed"
    progress.message = "安装完成！"

    return progress


@router.post("/plugins/{plugin_id}/uninstall", response_model=dict)
async def uninstall_plugin(
    plugin_id: str,
    request: PluginUninstallRequest,
    principal: PrincipalDependency,
) -> dict:
    """卸载插件"""
    enforce_scope(principal, "market:write")

    plugin = _plugins_db.get(plugin_id)
    if not plugin:
        raise api_error(404, "PLUGIN_NOT_FOUND", "插件未找到")

    if not plugin.is_installed:
        raise api_error(400, "NOT_INSTALLED", "插件未安装")

    # 更新插件状态
    plugin.is_installed = False
    plugin.is_enabled = False
    plugin.status = PluginStatus.PUBLISHED
    plugin.install_path = None
    plugin.installed_count = max(0, plugin.installed_count - 1)
    plugin.updated_at = datetime.now(UTC)

    return {"success": True, "message": "插件已卸载"}


@router.post("/plugins/{plugin_id}/enable", response_model=PluginRecord)
async def enable_plugin(plugin_id: str, principal: PrincipalDependency) -> PluginRecord:
    """启用插件"""
    enforce_scope(principal, "market:write")

    plugin = _plugins_db.get(plugin_id)
    if not plugin:
        raise api_error(404, "PLUGIN_NOT_FOUND", "插件未找到")

    if not plugin.is_installed:
        raise api_error(400, "NOT_INSTALLED", "插件未安装")

    plugin.is_enabled = True
    plugin.status = PluginStatus.INSTALLED
    plugin.updated_at = datetime.now(UTC)

    return plugin


@router.post("/plugins/{plugin_id}/disable", response_model=PluginRecord)
async def disable_plugin(plugin_id: str, principal: PrincipalDependency) -> PluginRecord:
    """禁用插件"""
    enforce_scope(principal, "market:write")

    plugin = _plugins_db.get(plugin_id)
    if not plugin:
        raise api_error(404, "PLUGIN_NOT_FOUND", "插件未找到")

    plugin.is_enabled = False
    plugin.status = PluginStatus.DISABLED
    plugin.updated_at = datetime.now(UTC)

    return plugin


@router.post("/search", response_model=list[PluginRecord])
async def search_plugins(
    request: PluginSearchRequest,
    principal: PrincipalDependency,
) -> list[PluginRecord]:
    """搜索插件"""
    enforce_scope(principal, "market:read")

    query = request.query.lower()
    results = []

    for plugin in _plugins_db.values():
        # 搜索匹配
        if (query in plugin.manifest.name.lower() or
            query in plugin.manifest.description.lower() or
            query in plugin.manifest.description_zh.lower() or
            any(query in cap.lower() for cap in plugin.manifest.capabilities)):

            # 分类过滤
            if request.category and plugin.category != request.category:
                continue

            results.append(plugin)

    # 排序
    if request.sort_by == "rating":
        results.sort(key=lambda p: p.rating, reverse=True)
    elif request.sort_by == "downloads":
        results.sort(key=lambda p: p.downloads, reverse=True)
    elif request.sort_by == "newest":
        results.sort(key=lambda p: p.created_at, reverse=True)

    # 分页
    return results[request.offset:request.offset + request.limit]


@router.get("/plugins/{plugin_id}/installation-progress", response_model=PluginInstallationProgress)
async def get_installation_progress(
    plugin_id: str,
    principal: PrincipalDependency,
) -> PluginInstallationProgress:
    """获取安装进度"""
    enforce_scope(principal, "market:read")

    progress = _installation_progress.get(plugin_id)
    if not progress:
        raise api_error(404, "PROGRESS_NOT_FOUND", "安装进度未找到")

    return progress


@router.get("/recommendations", response_model=list[PluginRecord])
async def get_recommendations(
    principal: PrincipalDependency,
    limit: int = Query(10, ge=1, le=50, description="限制数量"),
) -> list[PluginRecord]:
    """获取推荐插件"""
    enforce_scope(principal, "market:read")

    # 按评分和下载量推荐
    plugins = list(_plugins_db.values())
    plugins.sort(key=lambda p: (p.rating, p.downloads), reverse=True)

    return plugins[:limit]


@router.get("/trending", response_model=list[PluginRecord])
async def get_trending_plugins(
    principal: PrincipalDependency,
    limit: int = Query(10, ge=1, le=50, description="限制数量"),
) -> list[PluginRecord]:
    """获取热门插件"""
    enforce_scope(principal, "market:read")

    # 按下载量排序
    plugins = list(_plugins_db.values())
    plugins.sort(key=lambda p: p.downloads, reverse=True)

    return plugins[:limit]


@router.get("/installed", response_model=list[PluginRecord])
async def get_installed_plugins(principal: PrincipalDependency) -> list[PluginRecord]:
    """获取已安装的插件"""
    enforce_scope(principal, "market:read")

    return [p for p in _plugins_db.values() if p.is_installed]
