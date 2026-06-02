"""Enhanced Plugin Marketplace API - Complete marketplace endpoints"""

from __future__ import annotations

from typing import Annotated, Optional
from datetime import datetime, UTC

from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal
from backend.app.api.errors import api_error
from backend.app.core.plugin_marketplace_enhanced import (
    PluginMarketplaceService,
    PluginRecord,
    PluginReview,
    PluginSecurityScan,
    PluginSearchQuery,
    PluginPublishRequest,
    PluginInstallRequest,
    PluginStatus,
    ReviewStatus,
    RiskLevel,
    PluginVersion,
)

router = APIRouter(prefix="/api/v1/plugin-marketplace", tags=["plugin-marketplace"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# Global marketplace service instance
_marketplace: Optional[PluginMarketplaceService] = None


def get_marketplace() -> PluginMarketplaceService:
    """Get marketplace service instance"""
    global _marketplace
    if _marketplace is None:
        _marketplace = PluginMarketplaceService()
    return _marketplace


# ==================== Response Models ====================

class PluginListResponse(BaseModel):
    """Plugin list response"""
    plugins: list[PluginRecord]
    total: int
    limit: int
    offset: int


class ReviewListResponse(BaseModel):
    """Review list response"""
    reviews: list[PluginReview]
    total: int
    limit: int
    offset: int


class MarketplaceStatsResponse(BaseModel):
    """Marketplace statistics"""
    total_plugins: int
    published_plugins: int
    total_downloads: int
    total_installs: int
    active_installs: int
    avg_rating: float
    total_reviews: int


class PluginInstallResponse(BaseModel):
    """Plugin installation response"""
    install_id: str
    plugin_id: str
    status: str
    installed_at: datetime


# ==================== Browse & Search ====================

@router.get("/plugins", response_model=PluginListResponse)
async def list_plugins(
    principal: PrincipalDependency,
    category: Optional[str] = Query(None),
    sort_by: str = Query("relevance", description="relevance|rating|downloads|newest"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    min_rating: float = Query(0, ge=0, le=5),
) -> PluginListResponse:
    """List published plugins"""
    enforce_scope(principal, "marketplace:read")

    marketplace = get_marketplace()
    query = PluginSearchQuery(
        category=category,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
        min_rating=min_rating,
    )

    plugins, total = marketplace.search_plugins(query)
    return PluginListResponse(
        plugins=plugins,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/plugins/search", response_model=PluginListResponse)
async def search_plugins(
    principal: PrincipalDependency,
    q: str = Query(..., description="Search query"),
    category: Optional[str] = Query(None),
    sort_by: str = Query("relevance"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> PluginListResponse:
    """Search plugins by query"""
    enforce_scope(principal, "marketplace:read")

    marketplace = get_marketplace()
    query = PluginSearchQuery(
        query=q,
        category=category,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
    )

    plugins, total = marketplace.search_plugins(query)
    return PluginListResponse(
        plugins=plugins,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/plugins/{plugin_id}", response_model=PluginRecord)
async def get_plugin_detail(
    plugin_id: str,
    principal: PrincipalDependency,
) -> PluginRecord:
    """Get plugin details"""
    enforce_scope(principal, "marketplace:read")

    marketplace = get_marketplace()
    plugin = marketplace.get_plugin(plugin_id)

    if not plugin:
        raise api_error(404, "PLUGIN_NOT_FOUND", "Plugin not found")

    return plugin


@router.get("/featured", response_model=list[PluginRecord])
async def get_featured_plugins(
    principal: PrincipalDependency,
    limit: int = Query(10, ge=1, le=50),
) -> list[PluginRecord]:
    """Get featured plugins"""
    enforce_scope(principal, "marketplace:read")

    marketplace = get_marketplace()
    return marketplace.get_featured_plugins(limit)


@router.get("/trending", response_model=list[PluginRecord])
async def get_trending_plugins(
    principal: PrincipalDependency,
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(10, ge=1, le=50),
) -> list[PluginRecord]:
    """Get trending plugins"""
    enforce_scope(principal, "marketplace:read")

    marketplace = get_marketplace()
    return marketplace.get_trending_plugins(days, limit)


# ==================== Reviews & Ratings ====================

@router.get("/plugins/{plugin_id}/reviews", response_model=ReviewListResponse)
async def get_plugin_reviews(
    plugin_id: str,
    principal: PrincipalDependency,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> ReviewListResponse:
    """Get plugin reviews"""
    enforce_scope(principal, "marketplace:read")

    marketplace = get_marketplace()
    plugin = marketplace.get_plugin(plugin_id)

    if not plugin:
        raise api_error(404, "PLUGIN_NOT_FOUND", "Plugin not found")

    reviews, total = marketplace.get_reviews(plugin_id, limit, offset)
    return ReviewListResponse(
        reviews=reviews,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/plugins/{plugin_id}/reviews", response_model=PluginReview)
async def add_plugin_review(
    plugin_id: str,
    rating: int = Query(..., ge=1, le=5),
    title: str = Query(..., max_length=200),
    content: str = Query(..., max_length=5000),
    *,
    principal: PrincipalDependency,
) -> PluginReview:
    """Add review to plugin"""
    enforce_scope(principal, "marketplace:write")

    marketplace = get_marketplace()
    plugin = marketplace.get_plugin(plugin_id)

    if not plugin:
        raise api_error(404, "PLUGIN_NOT_FOUND", "Plugin not found")

    review = PluginReview(
        plugin_id=plugin_id,
        user_id=principal.user_id,
        rating=rating,
        title=title,
        content=content,
    )

    return marketplace.add_review(plugin_id, review)


# ==================== Installation ====================

@router.post("/plugins/{plugin_id}/install", response_model=PluginInstallResponse)
async def install_plugin(
    plugin_id: str,
    request: PluginInstallRequest,
    principal: PrincipalDependency,
    background_tasks: BackgroundTasks,
) -> PluginInstallResponse:
    """Install plugin"""
    enforce_scope(principal, "marketplace:write")

    marketplace = get_marketplace()
    plugin = marketplace.get_plugin(plugin_id)

    if not plugin:
        raise api_error(404, "PLUGIN_NOT_FOUND", "Plugin not found")

    if plugin.status != PluginStatus.PUBLISHED:
        raise api_error(400, "PLUGIN_NOT_AVAILABLE", "Plugin is not available for installation")

    # Record installation
    install_id = marketplace.record_installation(
        plugin_id=plugin_id,
        user_id=principal.user_id,
        config=request.config,
    )

    return PluginInstallResponse(
        install_id=install_id,
        plugin_id=plugin_id,
        status="installed",
        installed_at=datetime.now(UTC),
    )


@router.post("/plugins/{plugin_id}/uninstall")
async def uninstall_plugin(
    plugin_id: str,
    install_id: str = Query(...),
    *,
    principal: PrincipalDependency,
) -> dict:
    """Uninstall plugin"""
    enforce_scope(principal, "marketplace:write")

    marketplace = get_marketplace()
    success = marketplace.uninstall_plugin(install_id)

    if not success:
        raise api_error(404, "INSTALLATION_NOT_FOUND", "Installation not found")

    return {"success": True, "message": "Plugin uninstalled"}


# ==================== Publisher APIs ====================

@router.post("/plugins/publish", response_model=PluginRecord)
async def publish_plugin(
    request: PluginPublishRequest,
    principal: PrincipalDependency,
) -> PluginRecord:
    """Publish new plugin"""
    enforce_scope(principal, "marketplace:publish")

    marketplace = get_marketplace()
    plugin = marketplace.publish_plugin(request, principal.user_id)

    return plugin


@router.put("/plugins/{plugin_id}/versions", response_model=PluginRecord)
async def add_plugin_version(
    plugin_id: str,
    version: PluginVersion,
    principal: PrincipalDependency,
) -> PluginRecord:
    """Add new version to plugin"""
    enforce_scope(principal, "marketplace:publish")

    marketplace = get_marketplace()
    plugin = marketplace.get_plugin(plugin_id)

    if not plugin:
        raise api_error(404, "PLUGIN_NOT_FOUND", "Plugin not found")

    if plugin.publisher_id != principal.user_id:
        raise api_error(403, "FORBIDDEN", "Only plugin publisher can add versions")

    updated = marketplace.add_plugin_version(plugin_id, version)
    return updated


# ==================== Admin APIs ====================

@router.put("/plugins/{plugin_id}/status", response_model=PluginRecord)
async def update_plugin_status(
    plugin_id: str,
    status: PluginStatus = Query(...),
    *,
    principal: PrincipalDependency,
) -> PluginRecord:
    """Update plugin status (admin only)"""
    enforce_scope(principal, "marketplace:admin")

    marketplace = get_marketplace()
    plugin = marketplace.update_plugin_status(plugin_id, status)

    if not plugin:
        raise api_error(404, "PLUGIN_NOT_FOUND", "Plugin not found")

    return plugin


@router.post("/plugins/{plugin_id}/security-scan", response_model=PluginSecurityScan)
async def record_security_scan(
    plugin_id: str,
    risk_level: RiskLevel = Query(...),
    vulnerabilities: list[dict] = Query(default_factory=list),
    *,
    principal: PrincipalDependency,
) -> PluginSecurityScan:
    """Record security scan result (admin only)"""
    enforce_scope(principal, "marketplace:admin")

    marketplace = get_marketplace()
    plugin = marketplace.get_plugin(plugin_id)

    if not plugin:
        raise api_error(404, "PLUGIN_NOT_FOUND", "Plugin not found")

    scan = PluginSecurityScan(
        plugin_id=plugin_id,
        version=plugin.manifest.version,
        risk_level=risk_level,
        vulnerabilities=vulnerabilities,
        passed=risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM],
    )

    return marketplace.record_security_scan(scan)


# ==================== Statistics ====================

@router.get("/stats", response_model=MarketplaceStatsResponse)
async def get_marketplace_stats(
    principal: PrincipalDependency,
) -> MarketplaceStatsResponse:
    """Get marketplace statistics"""
    enforce_scope(principal, "marketplace:read")

    marketplace = get_marketplace()
    stats = marketplace.get_marketplace_stats()

    return MarketplaceStatsResponse(**stats)


@router.get("/plugins/{plugin_id}/stats")
async def get_plugin_stats(
    plugin_id: str,
    principal: PrincipalDependency,
) -> dict:
    """Get plugin statistics"""
    enforce_scope(principal, "marketplace:read")

    marketplace = get_marketplace()
    plugin = marketplace.get_plugin(plugin_id)

    if not plugin:
        raise api_error(404, "PLUGIN_NOT_FOUND", "Plugin not found")

    return {
        "plugin_id": plugin_id,
        "downloads": plugin.downloads,
        "installs": plugin.installs,
        "active_installs": plugin.active_installs,
        "rating": plugin.rating,
        "rating_count": plugin.rating_count,
        "review_count": plugin.review_count,
    }
