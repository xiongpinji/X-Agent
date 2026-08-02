"""技能市场完整API - 发布、审核、搜索、安装、评分、版本管理"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel

from backend.app.api.errors import api_error
from backend.app.core.security import Principal
from backend.app.core.skill_market_complete import (
    SkillMarketDB,
    SkillPublishRequest,
    SkillRatingRequest,
    get_skill_market_db,
)
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/skill-market", tags=["skill-market"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# ==================== 数据模型 ====================

class SkillDetailResponse(BaseModel):
    """技能详情响应"""
    id: str
    name: str
    name_zh: str
    version: str
    category: str
    status: str
    rating: float
    rating_count: int
    downloads: int
    installed_count: int
    usage_count: int
    description_zh: str
    icon_emoji: str
    keywords: list[str]
    tags: list[str]


class SkillListResponse(BaseModel):
    """技能列表响应"""
    skills: list[SkillDetailResponse]
    total: int
    limit: int
    offset: int


class ReviewResponse(BaseModel):
    """评论响应"""
    id: str
    user_name: str
    rating: int
    title: str
    comment: str | None
    created_at: str


class VersionResponse(BaseModel):
    """版本响应"""
    version: str
    release_date: str
    changelog: str | None
    download_count: int


class DependencyResponse(BaseModel):
    """依赖响应"""
    dep_skill_id: str
    name: str
    name_zh: str
    version: str
    version_spec: str | None
    dep_type: str


class MarketStatsResponse(BaseModel):
    """市场统计响应"""
    total_skills: int
    installed_skills: int
    total_downloads: int
    total_usage: int
    average_rating: float
    categories: dict[str, int]


# ==================== 技能发布API ====================

@router.post("/skills/publish", response_model=dict)
async def publish_skill(
    request: SkillPublishRequest,
    principal: PrincipalDependency,
    db: Annotated[SkillMarketDB, Depends(get_skill_market_db)],
) -> dict:
    """发布新技能"""
    enforce_scope(principal, "skill-market:publish")

    try:
        result = await db.publish_skill(
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            request=request,
        )
        return result
    except Exception as e:
        raise api_error(400, f"发布失败: {e!s}")


@router.post("/skills/{skill_id}/submit-review", response_model=dict)
async def submit_for_review(
    skill_id: str,
    principal: PrincipalDependency,
    db: Annotated[SkillMarketDB, Depends(get_skill_market_db)],
) -> dict:
    """提交技能审核"""
    enforce_scope(principal, "skill-market:publish")

    try:
        result = await db.submit_for_review(skill_id, principal.user_id)
        return result
    except Exception as e:
        raise api_error(400, f"提交失败: {e!s}")


@router.post("/skills/{skill_id}/approve", response_model=dict)
async def approve_skill(
    skill_id: str,
    reason: str | None = Body(None),
    principal: PrincipalDependency = PrincipalDependency,
    db: Annotated[SkillMarketDB, Depends(get_skill_market_db)] = None,
) -> dict:
    """批准技能"""
    enforce_scope(principal, "skill-market:review")

    try:
        result = await db.approve_skill(skill_id, principal.user_id, reason)
        return result
    except Exception as e:
        raise api_error(400, f"批准失败: {e!s}")


@router.post("/skills/{skill_id}/reject", response_model=dict)
async def reject_skill(
    skill_id: str,
    reason: str = Body(...),
    principal: PrincipalDependency = PrincipalDependency,
    db: Annotated[SkillMarketDB, Depends(get_skill_market_db)] = None,
) -> dict:
    """拒绝技能"""
    enforce_scope(principal, "skill-market:review")

    try:
        result = await db.reject_skill(skill_id, principal.user_id, reason)
        return result
    except Exception as e:
        raise api_error(400, f"拒绝失败: {e!s}")


# ==================== 技能搜索API ====================

@router.get("/skills/search", response_model=SkillListResponse)
async def search_skills(
    query: str = Query(..., min_length=1),
    category: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    principal: PrincipalDependency = PrincipalDependency,
    db: Annotated[SkillMarketDB, Depends(get_skill_market_db)] = None,
) -> SkillListResponse:
    """搜索技能"""
    enforce_scope(principal, "skill-market:read")

    try:
        skills, total = await db.search_skills(query, category, limit, offset)
        return SkillListResponse(
            skills=[SkillDetailResponse(**s) for s in skills],
            total=total,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        raise api_error(400, f"搜索失败: {e!s}")


@router.get("/skills/{skill_id}", response_model=SkillDetailResponse)
async def get_skill_detail(
    skill_id: str,
    principal: PrincipalDependency = PrincipalDependency,
    db: Annotated[SkillMarketDB, Depends(get_skill_market_db)] = None,
) -> SkillDetailResponse:
    """获取技能详情"""
    enforce_scope(principal, "skill-market:read")

    try:
        skill = await db.get_skill_by_id(skill_id)
        if not skill:
            raise api_error(404, "技能不存在")
        return SkillDetailResponse(**skill)
    except Exception as e:
        raise api_error(400, f"获取失败: {e!s}")


@router.get("/categories/{category}/skills", response_model=SkillListResponse)
async def list_skills_by_category(
    category: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    principal: PrincipalDependency = PrincipalDependency,
    db: Annotated[SkillMarketDB, Depends(get_skill_market_db)] = None,
) -> SkillListResponse:
    """按分类列出技能"""
    enforce_scope(principal, "skill-market:read")

    try:
        skills, total = await db.list_skills_by_category(category, limit, offset)
        return SkillListResponse(
            skills=[SkillDetailResponse(**s) for s in skills],
            total=total,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        raise api_error(400, f"列出失败: {e!s}")


# ==================== 技能评分API ====================

@router.post("/skills/{skill_id}/reviews", response_model=dict)
async def add_review(
    skill_id: str,
    request: SkillRatingRequest,
    principal: PrincipalDependency = PrincipalDependency,
    db: Annotated[SkillMarketDB, Depends(get_skill_market_db)] = None,
) -> dict:
    """添加评论"""
    enforce_scope(principal, "skill-market:review")

    if not 1 <= request.rating <= 5:
        raise api_error(400, "评分必须在1-5之间")

    try:
        result = await db.add_review(
            skill_id, principal.user_id, principal.user_id,
            request
        )
        return result
    except Exception as e:
        raise api_error(400, f"添加评论失败: {e!s}")


@router.get("/skills/{skill_id}/reviews", response_model=dict)
async def get_reviews(
    skill_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    principal: PrincipalDependency = PrincipalDependency,
    db: Annotated[SkillMarketDB, Depends(get_skill_market_db)] = None,
) -> dict:
    """获取技能评论"""
    enforce_scope(principal, "skill-market:read")

    try:
        reviews, total = await db.get_skill_reviews(skill_id, limit, offset)
        return {
            "reviews": [ReviewResponse(**r) for r in reviews],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        raise api_error(400, f"获取评论失败: {e!s}")


# ==================== 技能版本API ====================

@router.post("/skills/{skill_id}/versions", response_model=dict)
async def create_version(
    skill_id: str,
    version: str = Body(...),
    changelog: str = Body(...),
    principal: PrincipalDependency = PrincipalDependency,
    db: Annotated[SkillMarketDB, Depends(get_skill_market_db)] = None,
) -> dict:
    """创建新版本"""
    enforce_scope(principal, "skill-market:publish")

    try:
        result = await db.create_version(skill_id, version, changelog)
        return result
    except Exception as e:
        raise api_error(400, f"创建版本失败: {e!s}")


@router.get("/skills/{skill_id}/versions", response_model=dict)
async def get_versions(
    skill_id: str,
    principal: PrincipalDependency = PrincipalDependency,
    db: Annotated[SkillMarketDB, Depends(get_skill_market_db)] = None,
) -> dict:
    """获取技能版本列表"""
    enforce_scope(principal, "skill-market:read")

    try:
        versions = await db.get_skill_versions(skill_id)
        return {
            "versions": [VersionResponse(**v) for v in versions],
            "total": len(versions),
        }
    except Exception as e:
        raise api_error(400, f"获取版本失败: {e!s}")


# ==================== 技能依赖API ====================

@router.post("/skills/{skill_id}/dependencies", response_model=dict)
async def add_dependency(
    skill_id: str,
    dep_skill_id: str = Body(...),
    version_spec: str | None = Body(None),
    dep_type: str = Body(default="required"),
    principal: PrincipalDependency = PrincipalDependency,
    db: Annotated[SkillMarketDB, Depends(get_skill_market_db)] = None,
) -> dict:
    """添加依赖"""
    enforce_scope(principal, "skill-market:publish")

    try:
        result = await db.add_dependency(skill_id, dep_skill_id, version_spec, dep_type)
        return result
    except Exception as e:
        raise api_error(400, f"添加依赖失败: {e!s}")


@router.get("/skills/{skill_id}/dependencies", response_model=dict)
async def get_dependencies(
    skill_id: str,
    principal: PrincipalDependency = PrincipalDependency,
    db: Annotated[SkillMarketDB, Depends(get_skill_market_db)] = None,
) -> dict:
    """获取技能依赖"""
    enforce_scope(principal, "skill-market:read")

    try:
        dependencies = await db.get_skill_dependencies(skill_id)
        return {
            "dependencies": [DependencyResponse(**d) for d in dependencies],
            "total": len(dependencies),
        }
    except Exception as e:
        raise api_error(400, f"获取依赖失败: {e!s}")


# ==================== 技能安装API ====================

@router.post("/skills/{skill_id}/install", response_model=dict)
async def install_skill(
    skill_id: str,
    version: str | None = Body(None),
    config: dict = Body(default_factory=dict),
    principal: PrincipalDependency = PrincipalDependency,
    db: Annotated[SkillMarketDB, Depends(get_skill_market_db)] = None,
) -> dict:
    """安装技能"""
    enforce_scope(principal, "skill-market:install")

    try:
        # 获取最新版本
        if not version:
            skill = await db.get_skill_by_id(skill_id)
            if not skill:
                raise api_error(404, "技能不存在")
            version = skill["version"]

        result = await db.install_skill(
            principal.tenant_id, principal.user_id, skill_id, version, config
        )
        return result
    except Exception as e:
        raise api_error(400, f"安装失败: {e!s}")


@router.post("/skills/{skill_id}/uninstall", response_model=dict)
async def uninstall_skill(
    skill_id: str,
    principal: PrincipalDependency = PrincipalDependency,
    db: Annotated[SkillMarketDB, Depends(get_skill_market_db)] = None,
) -> dict:
    """卸载技能"""
    enforce_scope(principal, "skill-market:install")

    try:
        result = await db.uninstall_skill(principal.tenant_id, principal.user_id, skill_id)
        return result
    except Exception as e:
        raise api_error(400, f"卸载失败: {e!s}")


@router.get("/my-skills", response_model=dict)
async def get_my_skills(
    principal: PrincipalDependency = PrincipalDependency,
    db: Annotated[SkillMarketDB, Depends(get_skill_market_db)] = None,
) -> dict:
    """获取我的已安装技能"""
    enforce_scope(principal, "skill-market:read")

    try:
        skills = await db.get_user_installations(principal.tenant_id, principal.user_id)
        return {
            "skills": skills,
            "total": len(skills),
        }
    except Exception as e:
        raise api_error(400, f"获取失败: {e!s}")


# ==================== 技能使用记录API ====================

@router.post("/skills/{skill_id}/usage", response_model=dict)
async def record_usage(
    skill_id: str,
    input_data: dict = Body(default_factory=dict),
    output_data: dict = Body(default_factory=dict),
    status: str = Body(default="success"),
    error: str | None = Body(None),
    duration_ms: int = Body(default=0),
    principal: PrincipalDependency = PrincipalDependency,
    db: Annotated[SkillMarketDB, Depends(get_skill_market_db)] = None,
) -> dict:
    """记录技能使用"""
    enforce_scope(principal, "skill-market:read")

    try:
        result = await db.record_usage(
            principal.tenant_id, principal.user_id, skill_id,
            input_data, output_data, status, error, duration_ms
        )
        return result
    except Exception as e:
        raise api_error(400, f"记录失败: {e!s}")


@router.get("/skills/{skill_id}/usage-stats", response_model=dict)
async def get_usage_stats(
    skill_id: str,
    days: int = Query(30, ge=1, le=365),
    principal: PrincipalDependency = PrincipalDependency,
    db: Annotated[SkillMarketDB, Depends(get_skill_market_db)] = None,
) -> dict:
    """获取技能使用统计"""
    enforce_scope(principal, "skill-market:read")

    try:
        stats = await db.get_skill_usage_stats(skill_id, days)
        return stats
    except Exception as e:
        raise api_error(400, f"获取统计失败: {e!s}")


# ==================== 技能推荐API ====================

@router.get("/recommendations", response_model=dict)
async def get_recommendations(
    limit: int = Query(10, ge=1, le=50),
    principal: PrincipalDependency = PrincipalDependency,
    db: Annotated[SkillMarketDB, Depends(get_skill_market_db)] = None,
) -> dict:
    """获取技能推荐"""
    enforce_scope(principal, "skill-market:read")

    try:
        recommendations = await db.get_recommendations(
            principal.tenant_id, principal.user_id, limit
        )
        return {
            "recommendations": recommendations,
            "total": len(recommendations),
        }
    except Exception as e:
        raise api_error(400, f"获取推荐失败: {e!s}")


# ==================== 市场统计API ====================

@router.get("/stats", response_model=MarketStatsResponse)
async def get_market_stats(
    principal: PrincipalDependency = PrincipalDependency,
    db: Annotated[SkillMarketDB, Depends(get_skill_market_db)] = None,
) -> MarketStatsResponse:
    """获取市场统计"""
    enforce_scope(principal, "skill-market:read")

    try:
        stats = await db.get_market_stats(principal.tenant_id)
        return MarketStatsResponse(**stats)
    except Exception as e:
        raise api_error(400, f"获取统计失败: {e!s}")
