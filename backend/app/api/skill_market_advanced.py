"""技能市场高级功能API - 集成版本管理、评论评分、搜索、依赖、更新"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel

from backend.app.api.errors import api_error
from backend.app.core.security import Principal
from backend.app.core.skill_dependency_manager import (
    DependencyType,
    get_skill_dependency_manager,
)
from backend.app.core.skill_review_system import (
    ReviewStatus,
    get_skill_review_system,
)
from backend.app.core.skill_search_engine import get_skill_search_engine
from backend.app.core.skill_update_manager import (
    get_skill_update_manager,
)

# 导入各个管理器
from backend.app.core.skill_version_manager import (
    VersionCompatibility,
    get_skill_version_manager,
)
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/skill-market/advanced", tags=["skill-market-advanced"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# ==================== 数据模型 ====================

class VersionResponse(BaseModel):
    """版本响应"""
    skill_id: str
    version: str
    release_date: str
    changes: str
    compatibility: str
    deprecated: bool
    download_count: int


class ReviewResponse(BaseModel):
    """评论响应"""
    id: str
    skill_id: str
    user_name: str
    rating: int
    title: str
    comment: str
    status: str
    helpful_count: int
    unhelpful_count: int
    created_at: str


class SearchResponse(BaseModel):
    """搜索响应"""
    skill_id: str
    name: str
    name_zh: str
    description: str
    relevance_score: float
    match_type: str


class DependencyResponse(BaseModel):
    """依赖响应"""
    skill_id: str
    dep_skill_id: str
    version_spec: str
    dep_type: str
    optional: bool


class UpdateResponse(BaseModel):
    """更新响应"""
    skill_id: str
    current_version: str
    new_version: str
    priority: str
    status: str
    progress: int
    changelog: str


# ==================== 版本管理API ====================

@router.post("/versions/{skill_id}")
async def create_version(
    skill_id: str,
    version: str = Body(...),
    changes: str = Body(...),
    compatibility: str = Body(default="compatible"),
    *,
    principal: PrincipalDependency,
) -> VersionResponse:
    """创建新版本"""
    enforce_scope(principal, "skill-market:admin")

    manager = get_skill_version_manager()

    try:
        compat = VersionCompatibility(compatibility)
    except ValueError:
        raise api_error(400, "INVALID_COMPATIBILITY", "无效的兼容性值")

    success, error, skill_version = manager.create_version(
        skill_id=skill_id,
        version=version,
        changes=changes,
        compatibility=compat,
    )

    if not success:
        raise api_error(400, "CREATE_VERSION_FAILED", error)

    return VersionResponse(
        skill_id=skill_version.skill_id,
        version=skill_version.version,
        release_date=skill_version.release_date.isoformat(),
        changes=skill_version.changes,
        compatibility=skill_version.compatibility.value,
        deprecated=skill_version.deprecated,
        download_count=skill_version.download_count,
    )


@router.get("/versions/{skill_id}")
async def get_versions(
    skill_id: str,
    principal: PrincipalDependency,
) -> list[VersionResponse]:
    """获取所有版本"""
    enforce_scope(principal, "skill-market:read")

    manager = get_skill_version_manager()
    versions = manager.get_versions(skill_id)

    return [
        VersionResponse(
            skill_id=v.skill_id,
            version=v.version,
            release_date=v.release_date.isoformat(),
            changes=v.changes,
            compatibility=v.compatibility.value,
            deprecated=v.deprecated,
            download_count=v.download_count,
        )
        for v in versions
    ]


@router.post("/versions/{skill_id}/{version}/rollback")
async def rollback_version(
    skill_id: str,
    version: str,
    principal: PrincipalDependency,
) -> dict:
    """回滚到指定版本"""
    enforce_scope(principal, "skill-market:admin")

    manager = get_skill_version_manager()
    success, error = manager.rollback_version(skill_id, version)

    if not success:
        raise api_error(400, "ROLLBACK_FAILED", error)

    return {"success": True, "message": f"已回滚到版本 {version}"}


# ==================== 评论评分API ====================

@router.post("/reviews/{skill_id}")
async def add_review(
    skill_id: str,
    rating: int = Body(...),
    title: str = Body(default=""),
    comment: str = Body(default=""),
    *,
    principal: PrincipalDependency,
) -> ReviewResponse:
    """添加评论"""
    enforce_scope(principal, "skill-market:write")

    system = get_skill_review_system()

    success, error, review = system.add_review(
        skill_id=skill_id,
        user_id=principal.user_id,
        user_name=principal.user_id,  # 简化实现
        rating=rating,
        title=title,
        comment=comment,
    )

    if not success:
        raise api_error(400, "ADD_REVIEW_FAILED", error)

    return ReviewResponse(
        id=review.id,
        skill_id=review.skill_id,
        user_name=review.user_name,
        rating=review.rating,
        title=review.title,
        comment=review.comment,
        status=review.status.value,
        helpful_count=review.helpful_count,
        unhelpful_count=review.unhelpful_count,
        created_at=review.created_at.isoformat(),
    )


@router.get("/reviews/{skill_id}")
async def get_reviews(
    skill_id: str,
    limit: int = Query(10, ge=1, le=100),
    sort_by: str = Query("helpful"),
    *,
    principal: PrincipalDependency,
) -> list[ReviewResponse]:
    """获取评论列表"""
    enforce_scope(principal, "skill-market:read")

    system = get_skill_review_system()
    reviews = system.get_reviews(
        skill_id=skill_id,
        limit=limit,
        sort_by=sort_by,
        status=ReviewStatus.APPROVED,
    )

    return [
        ReviewResponse(
            id=r.id,
            skill_id=r.skill_id,
            user_name=r.user_name,
            rating=r.rating,
            title=r.title,
            comment=r.comment,
            status=r.status.value,
            helpful_count=r.helpful_count,
            unhelpful_count=r.unhelpful_count,
            created_at=r.created_at.isoformat(),
        )
        for r in reviews
    ]


@router.get("/reviews/{skill_id}/rating")
async def get_average_rating(
    skill_id: str,
    principal: PrincipalDependency,
) -> dict:
    """获取平均评分"""
    enforce_scope(principal, "skill-market:read")

    system = get_skill_review_system()
    avg_rating = system.get_average_rating(skill_id)
    distribution = system.get_rating_distribution(skill_id)

    return {
        "skill_id": skill_id,
        "average_rating": avg_rating,
        "distribution": distribution,
    }


@router.post("/reviews/{review_id}/helpful")
async def mark_helpful(
    review_id: str,
    principal: PrincipalDependency,
) -> dict:
    """标记评论为有用"""
    enforce_scope(principal, "skill-market:write")

    system = get_skill_review_system()
    success, error = system.mark_helpful(review_id, principal.user_id)

    if not success:
        raise api_error(400, "MARK_HELPFUL_FAILED", error)

    return {"success": True, "message": "已标记为有用"}


# ==================== 搜索API ====================

@router.get("/search")
async def advanced_search(
    query: str = Query(...),
    category: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    *,
    principal: PrincipalDependency,
) -> list[SearchResponse]:
    """高级搜索"""
    enforce_scope(principal, "skill-market:read")

    engine = get_skill_search_engine()

    filters = {}
    if category:
        filters["category"] = category

    results = engine.search(query, filters=filters, limit=limit)

    return [
        SearchResponse(
            skill_id=r.skill_id,
            name=r.name,
            name_zh=r.name_zh,
            description=r.description,
            relevance_score=r.relevance_score,
            match_type=r.match_type,
        )
        for r in results
    ]


@router.get("/search/suggestions")
async def get_search_suggestions(
    query: str = Query(...),
    limit: int = Query(10, ge=1, le=50),
    *,
    principal: PrincipalDependency,
) -> dict:
    """获取搜索建议"""
    enforce_scope(principal, "skill-market:read")

    engine = get_skill_search_engine()
    suggestions = engine.get_suggestions(query, limit=limit)

    return {
        "query": query,
        "suggestions": suggestions,
    }


# ==================== 依赖管理API ====================

@router.post("/dependencies/{skill_id}")
async def add_dependency(
    skill_id: str,
    dep_skill_id: str = Body(...),
    version_spec: str = Body(default="*"),
    dep_type: str = Body(default="required"),
    *,
    principal: PrincipalDependency,
) -> DependencyResponse:
    """添加依赖"""
    enforce_scope(principal, "skill-market:admin")

    manager = get_skill_dependency_manager()

    try:
        dep_enum = DependencyType(dep_type)
    except ValueError:
        raise api_error(400, "INVALID_DEP_TYPE", "无效的依赖类型")

    success, error = manager.add_dependency(
        skill_id=skill_id,
        dep_skill_id=dep_skill_id,
        version_spec=version_spec,
        dep_type=dep_enum,
    )

    if not success:
        raise api_error(400, "ADD_DEPENDENCY_FAILED", error)

    return DependencyResponse(
        skill_id=skill_id,
        dep_skill_id=dep_skill_id,
        version_spec=version_spec,
        dep_type=dep_type,
        optional=False,
    )


@router.get("/dependencies/{skill_id}")
async def get_dependencies(
    skill_id: str,
    principal: PrincipalDependency,
) -> list[DependencyResponse]:
    """获取依赖列表"""
    enforce_scope(principal, "skill-market:read")

    manager = get_skill_dependency_manager()
    deps = manager.get_dependencies(skill_id)

    return [
        DependencyResponse(
            skill_id=d.skill_id,
            dep_skill_id=d.dep_skill_id,
            version_spec=d.version_spec,
            dep_type=d.dep_type.value,
            optional=d.optional,
        )
        for d in deps
    ]


@router.get("/dependencies/{skill_id}/tree")
async def get_dependency_tree(
    skill_id: str,
    principal: PrincipalDependency,
) -> dict:
    """获取依赖树"""
    enforce_scope(principal, "skill-market:read")

    manager = get_skill_dependency_manager()
    tree = manager.get_dependency_tree(skill_id)

    return tree


# ==================== 更新管理API ====================

@router.get("/updates/{skill_id}")
async def check_update(
    skill_id: str,
    principal: PrincipalDependency,
) -> UpdateResponse | None:
    """检查更新"""
    enforce_scope(principal, "skill-market:read")

    manager = get_skill_update_manager()
    success, error, update = manager.check_updates(skill_id)

    if not success:
        raise api_error(400, "CHECK_UPDATE_FAILED", error)

    if not update:
        return None

    return UpdateResponse(
        skill_id=update.skill_id,
        current_version=update.current_version,
        new_version=update.new_version,
        priority=update.priority.value,
        status=update.status.value,
        progress=update.progress,
        changelog=update.changelog,
    )


@router.post("/updates/{skill_id}/install")
async def install_update(
    skill_id: str,
    version: str = Body(...),
    *,
    principal: PrincipalDependency,
) -> UpdateResponse:
    """安装更新"""
    enforce_scope(principal, "skill-market:write")

    manager = get_skill_update_manager()
    success, error, update = manager.update_skill(
        skill_id=skill_id,
        new_version=version,
        user_id=principal.user_id,
    )

    if not success:
        raise api_error(400, "INSTALL_UPDATE_FAILED", error)

    return UpdateResponse(
        skill_id=update.skill_id,
        current_version=update.current_version,
        new_version=update.new_version,
        priority=update.priority.value,
        status=update.status.value,
        progress=update.progress,
        changelog=update.changelog,
    )


@router.post("/updates/{skill_id}/auto-update")
async def toggle_auto_update(
    skill_id: str,
    enabled: bool = Body(...),
    *,
    principal: PrincipalDependency,
) -> dict:
    """切换自动更新"""
    enforce_scope(principal, "skill-market:write")

    manager = get_skill_update_manager()

    if enabled:
        success, error = manager.enable_auto_update(skill_id)
    else:
        success, error = manager.disable_auto_update(skill_id)

    if not success:
        raise api_error(400, "TOGGLE_AUTO_UPDATE_FAILED", error)

    return {
        "success": True,
        "skill_id": skill_id,
        "auto_update_enabled": enabled,
    }


@router.get("/updates/history/{skill_id}")
async def get_update_history(
    skill_id: str,
    limit: int = Query(20, ge=1, le=100),
    *,
    principal: PrincipalDependency,
) -> list[UpdateResponse]:
    """获取更新历史"""
    enforce_scope(principal, "skill-market:read")

    manager = get_skill_update_manager()
    history = manager.get_update_history(skill_id, limit=limit)

    return [
        UpdateResponse(
            skill_id=u.skill_id,
            current_version=u.current_version,
            new_version=u.new_version,
            priority=u.priority.value,
            status=u.status.value,
            progress=u.progress,
            changelog=u.changelog,
        )
        for u in history
    ]


__all__ = ["router"]
