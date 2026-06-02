"""技能市场数据模型 - 定义技能、分类、安装等数据结构"""

from __future__ import annotations

from datetime import datetime, UTC
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field


class SkillCategory(str, Enum):
    """技能分类"""
    OFFICE = "office"  # 办公助手
    DESIGN = "design"  # 设计助手
    DEVELOPMENT = "development"  # 编程助手
    DATA = "data"  # 数据助手
    AUTOMATION = "automation"  # 自动化助手
    LEARNING = "learning"  # 学习助手
    SEARCH = "search"  # 搜索助手
    CREATIVITY = "creativity"  # 创意助手


class SkillStatus(str, Enum):
    """技能状态"""
    DRAFT = "draft"  # 草稿
    PUBLISHED = "published"  # 已发布
    INSTALLING = "installing"  # 安装中
    INSTALLED = "installed"  # 已安装
    UPDATING = "updating"  # 更新中
    DISABLED = "disabled"  # 已禁用
    ERROR = "error"  # 错误


class SkillRiskLevel(str, Enum):
    """风险等级"""
    LOW = "low"  # 低
    MEDIUM = "medium"  # 中
    HIGH = "high"  # 高
    CRITICAL = "critical"  # 严重


class SkillManifest(BaseModel):
    """技能清单 - 从SKILL.md解析"""
    name: str = Field(..., description="技能名称")
    name_zh: str = Field(..., description="中文名称")
    version: str = Field(..., description="版本号")
    author: str = Field(default="", description="作者")
    description: str = Field(default="", description="英文简短描述")
    description_zh: str = Field(default="", description="中文简短描述")
    long_description: str = Field(default="", description="英文详细描述")
    long_description_zh: str = Field(default="", description="中文详细描述")
    homepage: str = Field(default="", description="主页")
    repository: str = Field(default="", description="仓库地址")
    license: str = Field(default="MIT", description="许可证")
    keywords: list[str] = Field(default_factory=list, description="关键词")
    tags: list[str] = Field(default_factory=list, description="标签")
    capabilities: list[str] = Field(default_factory=list, description="能力列表")
    dependencies: dict[str, str] = Field(default_factory=dict, description="依赖")
    permissions: list[str] = Field(default_factory=list, description="权限")
    entry_point: str = Field(default="", description="入口点")
    icon_url: str = Field(default="", description="图标URL")
    icon_emoji: str = Field(default="", description="图标emoji")
    screenshots: list[str] = Field(default_factory=list, description="截图")


class SkillRecord(BaseModel):
    """技能记录"""
    id: str = Field(..., description="技能ID")
    manifest: SkillManifest = Field(..., description="技能清单")
    category: SkillCategory = Field(..., description="分类")
    status: SkillStatus = Field(default=SkillStatus.PUBLISHED, description="状态")
    risk_level: SkillRiskLevel = Field(default=SkillRiskLevel.MEDIUM, description="风险等级")

    # 中文化内容
    what_is_it: str = Field(default="", description="这个技能是干什么的")
    who_is_it_for: str = Field(default="", description="适合谁用")
    how_to_use: str = Field(default="", description="怎么用（步骤化）")
    use_cases: list[str] = Field(default_factory=list, description="使用场景")
    faq: list[dict[str, str]] = Field(default_factory=list, description="常见问题")
    tutorial: str = Field(default="", description="使用教程")
    examples: list[dict[str, str]] = Field(default_factory=list, description="使用示例")

    # 统计信息
    downloads: int = Field(default=0, description="下载次数")
    rating: float = Field(default=0.0, description="评分")
    rating_count: int = Field(default=0, description="评分数")
    installed_count: int = Field(default=0, description="安装数")
    usage_count: int = Field(default=0, description="使用次数")

    # 时间戳
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="创建时间")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="更新时间")
    published_at: Optional[datetime] = Field(default=None, description="发布时间")

    # 用户相关
    is_installed: bool = Field(default=False, description="是否已安装")
    is_enabled: bool = Field(default=False, description="是否已启用")
    is_favorite: bool = Field(default=False, description="是否已收藏")
    install_path: Optional[str] = Field(default=None, description="安装路径")
    install_time: Optional[datetime] = Field(default=None, description="安装时间")
    comments: list = Field(default_factory=list, description="评论列表")

    # 源信息
    source_repo: str = Field(default="", description="源仓库")
    source_url: str = Field(default="", description="源URL")
    source_type: str = Field(default="github", description="源类型")


class SkillCategoryInfo(BaseModel):
    """分类信息"""
    id: str = Field(..., description="分类ID")
    name: str = Field(..., description="分类名称")
    name_zh: str = Field(..., description="中文名称")
    icon: str = Field(..., description="图标emoji")
    description: str = Field(..., description="英文描述")
    description_zh: str = Field(..., description="中文描述")
    skill_count: int = Field(default=0, description="技能数量")


class SkillInstallRequest(BaseModel):
    """安装请求"""
    skill_id: str = Field(..., description="技能ID")
    version: Optional[str] = Field(default=None, description="版本")
    config: dict = Field(default_factory=dict, description="配置")
    auto_enable: bool = Field(default=True, description="自动启用")


class SkillUninstallRequest(BaseModel):
    """卸载请求"""
    skill_id: str = Field(..., description="技能ID")
    remove_config: bool = Field(default=False, description="删除配置")


class SkillExecuteRequest(BaseModel):
    """执行请求"""
    skill_id: str = Field(..., description="技能ID")
    input_data: dict[str, Any] = Field(default_factory=dict, description="输入数据")
    user_id: str = Field(default="", description="用户ID")
    tenant_id: str = Field(default="", description="租户ID")


class SkillSearchRequest(BaseModel):
    """搜索请求"""
    query: str = Field(..., description="搜索词")
    category: Optional[SkillCategory] = Field(default=None, description="分类")
    sort_by: str = Field(default="rating", description="排序方式")
    limit: int = Field(default=20, description="限制数量")
    offset: int = Field(default=0, description="偏移量")


class SkillInstallationProgress(BaseModel):
    """安装进度"""
    skill_id: str = Field(..., description="技能ID")
    status: str = Field(..., description="状态")
    progress: int = Field(default=0, description="进度百分比")
    message: str = Field(default="", description="消息")
    error: Optional[str] = Field(default=None, description="错误信息")


class SkillUsageRecord(BaseModel):
    """使用记录"""
    id: str = Field(..., description="记录ID")
    skill_id: str = Field(..., description="技能ID")
    user_id: str = Field(..., description="用户ID")
    input_data: dict[str, Any] = Field(default_factory=dict, description="输入数据")
    output_data: dict[str, Any] = Field(default_factory=dict, description="输出数据")
    status: str = Field(..., description="状态")
    error: Optional[str] = Field(default=None, description="错误信息")
    duration_ms: int = Field(default=0, description="执行时间（毫秒）")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="创建时间")


class SkillRecommendation(BaseModel):
    """技能推荐"""
    skill_id: str = Field(..., description="技能ID")
    name_zh: str = Field(..., description="中文名称")
    reason: str = Field(..., description="推荐原因")
    similarity_score: float = Field(..., description="相似度分数")


class SkillComment(BaseModel):
    """技能评论"""
    id: str = Field(..., description="评论ID")
    user_id: str = Field(..., description="用户ID")
    content: str = Field(..., description="评论内容")
    rating: int = Field(default=5, description="评分 1-5")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="创建时间")
