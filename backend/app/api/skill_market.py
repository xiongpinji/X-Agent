"""技能市场API - 完整的技能发现、搜索、安装、管理功能"""

from __future__ import annotations

from typing import Annotated, Optional
from datetime import datetime, UTC

from fastapi import APIRouter, Depends, Query, HTTPException, Body
from pydantic import BaseModel, Field

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal
from backend.app.api.errors import api_error
from backend.app.core.skill_market_models import (
    SkillRecord, SkillCategory, SkillCategoryInfo, SkillInstallRequest,
    SkillUninstallRequest, SkillExecuteRequest, SkillSearchRequest,
    SkillInstallationProgress, SkillUsageRecord, SkillRecommendation,
)
from backend.app.core.skill_market_manager import get_skill_market_manager

router = APIRouter(prefix="/api/v1/skill-market", tags=["skill-market"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# ==================== 数据模型 ====================

class SkillListResponse(BaseModel):
    """技能列表响应"""
    skills: list[SkillRecord]
    total: int
    limit: int
    offset: int


class SkillSearchResponse(BaseModel):
    """搜索响应"""
    results: list[SkillRecord]
    total: int
    query: str


class SkillStatisticsResponse(BaseModel):
    """统计信息响应"""
    total_skills: int
    installed_skills: int
    total_downloads: int
    total_usage: int
    average_rating: float
    categories: dict[str, int]


# ==================== 分类管理 ====================

@router.get("/categories", response_model=list[SkillCategoryInfo])
async def get_categories(principal: PrincipalDependency) -> list[SkillCategoryInfo]:
    """获取所有分类"""
    enforce_scope(principal, "skill-market:read")

    categories = [
        SkillCategoryInfo(
            id="office",
            name="Office Assistant",
            name_zh="📝 办公助手",
            icon="📝",
            description="Document processing, spreadsheet operations, presentation creation",
            description_zh="文档处理、表格操作、PPT制作",
        ),
        SkillCategoryInfo(
            id="design",
            name="Design Tools",
            name_zh="🎨 设计助手",
            icon="🎨",
            description="Image processing, video editing, UI design",
            description_zh="图片处理、视频编辑、UI设计",
        ),
        SkillCategoryInfo(
            id="development",
            name="Development Tools",
            name_zh="💻 编程助手",
            icon="💻",
            description="Code generation, debugging assistant, Git tools",
            description_zh="代码生成、调试助手、Git工具",
        ),
        SkillCategoryInfo(
            id="data",
            name="Data Analysis",
            name_zh="📊 数据助手",
            icon="📊",
            description="Data cleaning, visualization, report generation",
            description_zh="数据清洗、可视化、报表生成",
        ),
        SkillCategoryInfo(
            id="automation",
            name="Automation",
            name_zh="🤖 自动化助手",
            icon="🤖",
            description="Web automation, desktop automation, scheduled tasks",
            description_zh="网页自动化、桌面自动化、定时任务",
        ),
        SkillCategoryInfo(
            id="learning",
            name="Learning Assistant",
            name_zh="📚 学习助手",
            icon="📚",
            description="Note taking, knowledge management, learning planning",
            description_zh="笔记整理、知识管理、学习计划",
        ),
        SkillCategoryInfo(
            id="search",
            name="Search Tools",
            name_zh="🔍 搜索助手",
            icon="🔍",
            description="Information gathering, content aggregation, research",
            description_zh="信息搜集、资料整理、内容聚合",
        ),
        SkillCategoryInfo(
            id="creativity",
            name="Creativity Tools",
            name_zh="💡 创意助手",
            icon="💡",
            description="Brainstorming, idea generation, creative writing",
            description_zh="头脑风暴、创意生成、创意写作",
        ),
    ]

    manager = get_skill_market_manager()
    stats = await manager.get_statistics()

    # 更新分类中的技能数量
    for category in categories:
        category.skill_count = stats["categories"].get(category.id, 0)

    return categories


# ==================== 技能列表 ====================

@router.get("/skills", response_model=SkillListResponse)
async def list_skills(
    principal: PrincipalDependency,
    category: Optional[str] = Query(None, description="分类"),
    installed_only: bool = Query(False, description="仅已安装"),
    sort_by: str = Query("rating", description="排序方式"),
    limit: int = Query(20, ge=1, le=100, description="限制数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
) -> SkillListResponse:
    """获取技能列表"""
    enforce_scope(principal, "skill-market:read")

    manager = get_skill_market_manager()

    # 获取技能
    cat_enum = None
    if category:
        try:
            cat_enum = SkillCategory(category)
        except ValueError:
            raise api_error(400, "INVALID_CATEGORY", f"无效的分类: {category}")

    skills = await manager.discover_skills(category=cat_enum, limit=1000)

    # 过滤已安装
    if installed_only:
        skills = [s for s in skills if s.is_installed]

    # 排序
    if sort_by == "rating":
        skills.sort(key=lambda s: s.rating, reverse=True)
    elif sort_by == "downloads":
        skills.sort(key=lambda s: s.downloads, reverse=True)
    elif sort_by == "newest":
        skills.sort(key=lambda s: s.created_at, reverse=True)
    elif sort_by == "usage":
        skills.sort(key=lambda s: s.usage_count, reverse=True)

    total = len(skills)
    skills = skills[offset:offset + limit]

    return SkillListResponse(
        skills=skills,
        total=total,
        limit=limit,
        offset=offset,
    )


# ==================== 技能搜索 ====================

@router.get("/search", response_model=SkillSearchResponse)
async def search_skills(
    principal: PrincipalDependency,
    query: str = Query(..., description="搜索词"),
    limit: int = Query(20, ge=1, le=100, description="限制数量"),
) -> SkillSearchResponse:
    """搜索技能"""
    enforce_scope(principal, "skill-market:read")

    if not query or len(query.strip()) == 0:
        raise api_error(400, "EMPTY_QUERY", "搜索词不能为空")

    manager = get_skill_market_manager()
    results = await manager.search_skills(query, limit)

    return SkillSearchResponse(
        results=results,
        total=len(results),
        query=query,
    )


# ==================== 技能详情 ====================

@router.get("/skills/{skill_id}", response_model=SkillRecord)
async def get_skill_detail(
    skill_id: str,
    principal: PrincipalDependency,
) -> SkillRecord:
    """获取技能详情"""
    enforce_scope(principal, "skill-market:read")

    manager = get_skill_market_manager()
    skill = await manager.get_skill_info(skill_id)

    if not skill:
        raise api_error(404, "SKILL_NOT_FOUND", "技能未找到")

    return skill


# ==================== 技能安装 ====================

@router.post("/skills/{skill_id}/install", response_model=SkillInstallationProgress)
async def install_skill(
    skill_id: str,
    request: SkillInstallRequest,
    principal: PrincipalDependency,
) -> SkillInstallationProgress:
    """安装技能"""
    enforce_scope(principal, "skill-market:write")

    manager = get_skill_market_manager()

    # 验证技能存在
    skill = await manager.get_skill_info(skill_id)
    if not skill:
        raise api_error(404, "SKILL_NOT_FOUND", "技能未找到")

    # 安装技能
    progress = await manager.install_skill(request, user_id=principal.user_id)

    if progress.error:
        raise api_error(400, "INSTALL_FAILED", progress.error)

    return progress


# ==================== 技能卸载 ====================

@router.post("/skills/{skill_id}/uninstall")
async def uninstall_skill(
    skill_id: str,
    request: SkillUninstallRequest,
    principal: PrincipalDependency,
) -> dict:
    """卸载技能"""
    enforce_scope(principal, "skill-market:write")

    manager = get_skill_market_manager()

    # 卸载技能
    success = await manager.uninstall_skill(request, user_id=principal.user_id)

    if not success:
        raise api_error(400, "UNINSTALL_FAILED", "技能卸载失败")

    return {"success": True, "message": "技能已卸载"}


# ==================== 技能执行 ====================

@router.post("/skills/{skill_id}/execute")
async def execute_skill(
    skill_id: str,
    request: SkillExecuteRequest,
    principal: PrincipalDependency,
) -> dict:
    """执行技能"""
    enforce_scope(principal, "skill-market:execute")

    manager = get_skill_market_manager()

    # 执行技能
    result = await manager.execute_skill(request)

    if not result.get("success"):
        raise api_error(400, "EXECUTE_FAILED", result.get("error", "技能执行失败"))

    return result


# ==================== 技能推荐 ====================

@router.get("/skills/{skill_id}/recommendations", response_model=list[SkillRecommendation])
async def get_skill_recommendations(
    skill_id: str,
    principal: PrincipalDependency,
    limit: int = Query(5, ge=1, le=20, description="限制数量"),
) -> list[SkillRecommendation]:
    """获取推荐技能"""
    enforce_scope(principal, "skill-market:read")

    manager = get_skill_market_manager()

    # 验证技能存在
    skill = await manager.get_skill_info(skill_id)
    if not skill:
        raise api_error(404, "SKILL_NOT_FOUND", "技能未找到")

    # 获取推荐
    recommendations = await manager.get_recommendations(skill_id, limit)

    return recommendations


# ==================== 使用历史 ====================

@router.get("/usage-history", response_model=list[SkillUsageRecord])
async def get_usage_history(
    principal: PrincipalDependency,
    limit: int = Query(20, ge=1, le=100, description="限制数量"),
) -> list[SkillUsageRecord]:
    """获取使用历史"""
    enforce_scope(principal, "skill-market:read")

    manager = get_skill_market_manager()

    # 获取使用历史
    history = await manager.get_usage_history(user_id=principal.user_id, limit=limit)

    return history


# ==================== 统计信息 ====================

@router.get("/statistics", response_model=SkillStatisticsResponse)
async def get_statistics(principal: PrincipalDependency) -> SkillStatisticsResponse:
    """获取统计信息"""
    enforce_scope(principal, "skill-market:read")

    manager = get_skill_market_manager()

    # 获取统计
    stats = await manager.get_statistics()

    return SkillStatisticsResponse(**stats)


# ==================== 管理功能 ====================

@router.post("/sync-repositories")
async def sync_repositories(principal: PrincipalDependency) -> dict:
    """从开源仓库同步技能"""
    enforce_scope(principal, "skill-market:admin")

    manager = get_skill_market_manager()

    # 同步技能
    count = await manager.sync_from_repositories()

    return {
        "success": True,
        "message": f"同步完成，共添加 {count} 个技能",
        "count": count,
    }


@router.get("/installed-skills", response_model=list[SkillRecord])
async def get_installed_skills(principal: PrincipalDependency) -> list[SkillRecord]:
    """获取已安装的技能"""
    enforce_scope(principal, "skill-market:read")

    manager = get_skill_market_manager()

    # 返回已安装的技能
    return list(manager.installed_skills.values())
