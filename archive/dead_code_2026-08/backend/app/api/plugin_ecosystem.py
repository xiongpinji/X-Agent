"""P2-07: 插件生态市场 API.

端点:
- GET  /api/v1/plugin-ecosystem/plugins — 搜索/发现插件
- GET  /api/v1/plugin-ecosystem/plugins/{id} — 插件详情
- POST /api/v1/plugin-ecosystem/plugins/submit — 提交插件
- POST /api/v1/plugin-ecosystem/plugins/{id}/review — 审核
- POST /api/v1/plugin-ecosystem/plugins/{id}/install — 安装
- POST /api/v1/plugin-ecosystem/plugins/{id}/uninstall — 卸载
- POST /api/v1/plugin-ecosystem/plugins/{id}/rate — 评价
- GET  /api/v1/plugin-ecosystem/plugins/{id}/stats — 统计
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.core.plugin_market.service import (
    PluginCategory,
    PluginManifest,
    get_plugin_market_service,
)

router = APIRouter(prefix="/api/v1/plugin-ecosystem", tags=["plugin-ecosystem"])


# ─── 请求/响应模型 ─────────────────────────────────────────────────────────────


class SubmitPluginRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    version: str = Field("1.0.0")
    description: str = Field("")
    author: str = Field("")
    category: str = Field("other")
    permissions: list[str] = Field(default_factory=list)
    requires_network: bool = False
    requires_filesystem: bool = False
    dependencies: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class ReviewPluginRequest(BaseModel):
    reviewer: str = Field(..., min_length=1)
    verdict: str = Field(..., description="approve 或 reject")
    note: str = Field("")


class RatePluginRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    rating: int = Field(..., ge=1, le=5)
    comment: str = Field("")


# ─── 端点 ─────────────────────────────────────────────────────────────────────


@router.get("/plugins")
async def search_plugins(
    query: str | None = Query(None, description="搜索关键词"),
    category: str | None = Query(None, description="分类过滤"),
    sort_by: str = Query("rating", description="排序: rating/downloads/newest"),
    limit: int = Query(20, ge=1, le=100),
):
    """搜索/发现插件."""
    service = get_plugin_market_service()
    results = service.search(query=query, category=category, sort_by=sort_by, limit=limit)
    return [listing.to_dict() for listing in results]


@router.get("/plugins/{plugin_id}")
async def get_plugin_detail(plugin_id: str):
    """插件详情."""
    service = get_plugin_market_service()
    listing = service.get_plugin(plugin_id)
    if not listing:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
    result = listing.to_dict()
    result["permissions"] = listing.manifest.permissions if listing.manifest else []
    result["dependencies"] = listing.manifest.dependencies if listing.manifest else []
    result["reviews"] = [
        {"rating": r.rating, "comment": r.comment, "user_id": r.user_id, "created_at": r.created_at}
        for r in service.get_reviews(plugin_id)
    ]
    return result


@router.post("/plugins/submit")
async def submit_plugin(req: SubmitPluginRequest):
    """提交插件."""
    service = get_plugin_market_service()
    try:
        category = PluginCategory(req.category)
    except ValueError:
        category = PluginCategory.OTHER

    manifest = PluginManifest(
        name=req.name,
        version=req.version,
        description=req.description,
        author=req.author,
        category=category,
        permissions=req.permissions,
        requires_network=req.requires_network,
        requires_filesystem=req.requires_filesystem,
        dependencies=req.dependencies,
        tags=req.tags,
    )
    listing = service.submit_plugin(manifest)
    return listing.to_dict()


@router.post("/plugins/{plugin_id}/review")
async def review_plugin(plugin_id: str, req: ReviewPluginRequest):
    """审核插件."""
    service = get_plugin_market_service()
    if not service.review_plugin(plugin_id, req.reviewer, req.verdict, req.note):
        raise HTTPException(status_code=400, detail="Review failed (plugin not found or not pending)")
    listing = service.get_plugin(plugin_id)
    return {"plugin_id": plugin_id, "status": listing.status.value if listing else "unknown"}


@router.post("/plugins/{plugin_id}/publish")
async def publish_plugin(plugin_id: str):
    """上架插件."""
    service = get_plugin_market_service()
    if not service.publish_plugin(plugin_id):
        raise HTTPException(status_code=400, detail="Publish failed (plugin not approved)")
    return {"plugin_id": plugin_id, "status": "published"}


@router.post("/plugins/{plugin_id}/install")
async def install_plugin(plugin_id: str):
    """安装插件."""
    service = get_plugin_market_service()
    result = service.install(plugin_id)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return {"plugin_id": plugin_id, "message": result.message, "version": result.version}


@router.post("/plugins/{plugin_id}/uninstall")
async def uninstall_plugin(plugin_id: str):
    """卸载插件."""
    service = get_plugin_market_service()
    if not service.uninstall(plugin_id):
        raise HTTPException(status_code=400, detail="Uninstall failed (not installed)")
    return {"plugin_id": plugin_id, "status": "uninstalled"}


@router.post("/plugins/{plugin_id}/rate")
async def rate_plugin(plugin_id: str, req: RatePluginRequest):
    """评价插件."""
    service = get_plugin_market_service()
    if not service.rate_plugin(plugin_id, req.user_id, req.rating, req.comment):
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
    listing = service.get_plugin(plugin_id)
    return {"plugin_id": plugin_id, "rating": listing.rating if listing else 0, "rating_count": listing.rating_count if listing else 0}


@router.get("/plugins/{plugin_id}/stats")
async def get_plugin_stats(plugin_id: str):
    """插件统计."""
    service = get_plugin_market_service()
    stats = service.get_stats(plugin_id)
    if not stats:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
    return {
        "plugin_id": stats.plugin_id,
        "total_downloads": stats.total_downloads,
        "total_installs": stats.total_installs,
        "active_installs": stats.active_installs,
        "avg_rating": stats.avg_rating,
        "total_reviews": stats.total_reviews,
        "risk_score": stats.risk_score,
    }


# ─── 热加载 & 版本管理 (K1/K2) ────────────────────────────────────────────────


@router.post("/plugins/{plugin_id}/reload")
async def hot_reload_plugin(plugin_id: str):
    """Hot-reload a plugin without system restart."""
    service = get_plugin_market_service()
    result = service.hot_reload(plugin_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Reload failed"))
    return result


@router.post("/plugins/{plugin_id}/unload")
async def hot_unload_plugin(plugin_id: str):
    """Unload a plugin module from memory."""
    service = get_plugin_market_service()
    result = service.hot_unload(plugin_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Unload failed"))
    return result


class UpgradePluginRequest(BaseModel):
    target_version: str = Field(..., min_length=1)


@router.post("/plugins/{plugin_id}/upgrade")
async def upgrade_plugin(plugin_id: str, req: UpgradePluginRequest):
    """Upgrade plugin to a new version with compatibility check."""
    service = get_plugin_market_service()
    result = service.upgrade_plugin(plugin_id, req.target_version)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Upgrade failed"))
    return result


@router.post("/plugins/{plugin_id}/rollback")
async def rollback_plugin(plugin_id: str):
    """Rollback plugin to the previous version."""
    service = get_plugin_market_service()
    result = service.rollback_plugin(plugin_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Rollback failed"))
    return result


@router.get("/plugins/{plugin_id}/versions")
async def get_plugin_versions(plugin_id: str):
    """Get version history for a plugin."""
    service = get_plugin_market_service()
    listing = service.get_plugin(plugin_id)
    if not listing:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
    return {
        "plugin_id": plugin_id,
        "current_version": listing.manifest.version if listing.manifest else "unknown",
        "history": service.get_version_history(plugin_id),
    }


@router.get("/plugins/{plugin_id}/compatibility/{target_version}")
async def check_compatibility(plugin_id: str, target_version: str):
    """Check version compatibility before upgrading."""
    service = get_plugin_market_service()
    return service.check_version_compatibility(plugin_id, target_version)
