"""Enhanced Plugin Marketplace - Complete marketplace system with reviews, ratings, versioning"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from threading import RLock
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


# ==================== Enums ====================

class PluginStatus(StrEnum):
    """Plugin publication status"""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    SUSPENDED = "suspended"
    DEPRECATED = "deprecated"
    DELISTED = "delisted"


class PluginInstallStatus(StrEnum):
    """Plugin installation status"""
    NOT_INSTALLED = "not_installed"
    INSTALLING = "installing"
    INSTALLED = "installed"
    UPDATING = "updating"
    UNINSTALLING = "uninstalling"
    ERROR = "error"


class ReviewStatus(StrEnum):
    """Review status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FLAGGED = "flagged"


class RiskLevel(StrEnum):
    """Security risk level"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ==================== Data Models ====================

class PluginVersion(BaseModel):
    """Plugin version information"""
    version: str = Field(..., description="Semantic version")
    release_date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    changelog: str = Field(default="", description="Version changelog")
    download_url: str = Field(..., description="Download URL")
    file_hash: str = Field(..., description="SHA256 hash")
    file_size: int = Field(..., description="File size in bytes")
    dependencies: dict[str, str] = Field(default_factory=dict, description="Version-specific dependencies")
    breaking_changes: list[str] = Field(default_factory=list)
    deprecated_features: list[str] = Field(default_factory=list)


class PluginReview(BaseModel):
    """Plugin review/rating"""
    review_id: str = Field(default_factory=lambda: str(uuid4()))
    plugin_id: str
    user_id: str
    rating: int = Field(..., ge=1, le=5, description="1-5 star rating")
    title: str = Field(..., max_length=200)
    content: str = Field(..., max_length=5000)
    helpful_count: int = Field(default=0)
    unhelpful_count: int = Field(default=0)
    status: ReviewStatus = ReviewStatus.APPROVED
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PluginSecurityScan(BaseModel):
    """Security scan result"""
    scan_id: str = Field(default_factory=lambda: str(uuid4()))
    plugin_id: str
    version: str
    scan_date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    risk_level: RiskLevel = RiskLevel.MEDIUM
    vulnerabilities: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    passed: bool = True
    scanner_version: str = "1.0"


class PluginDependencyInfo(BaseModel):
    """Plugin dependency information"""
    plugin_id: str
    min_version: Optional[str] = None
    max_version: Optional[str] = None
    optional: bool = False


class PluginManifest(BaseModel):
    """Complete plugin manifest"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., description="Plugin name")
    version: str = Field(..., description="Current version")
    author: str = Field(..., description="Author name")
    author_email: Optional[str] = None
    description: str = Field(..., description="Short description")
    long_description: str = Field(default="", description="Detailed description")
    homepage: Optional[str] = None
    repository: Optional[str] = None
    license: str = Field(default="MIT")
    keywords: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    dependencies: dict[str, str] = Field(default_factory=dict)
    entry_point: str = Field(default="")
    icon_url: Optional[str] = None
    screenshots: list[str] = Field(default_factory=list)
    documentation_url: Optional[str] = None
    support_url: Optional[str] = None


class PluginRecord(BaseModel):
    """Complete plugin record in marketplace"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    manifest: PluginManifest
    status: PluginStatus = PluginStatus.DRAFT

    # Statistics
    downloads: int = Field(default=0)
    installs: int = Field(default=0)
    active_installs: int = Field(default=0)
    rating: float = Field(default=0.0, ge=0, le=5)
    rating_count: int = Field(default=0)
    review_count: int = Field(default=0)

    # Security
    risk_level: RiskLevel = RiskLevel.MEDIUM
    last_security_scan: Optional[datetime] = None
    security_issues: list[str] = Field(default_factory=list)

    # Versions
    versions: list[PluginVersion] = Field(default_factory=list)

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    published_at: Optional[datetime] = None
    featured: bool = False
    featured_until: Optional[datetime] = None

    # Publisher info
    publisher_id: str
    publisher_name: str
    publisher_verified: bool = False

    # Moderation
    moderation_notes: str = Field(default="")
    moderation_status: str = Field(default="approved")


class PluginSearchQuery(BaseModel):
    """Plugin search query"""
    query: Optional[str] = None
    category: Optional[str] = None
    sort_by: str = Field(default="relevance", description="relevance|rating|downloads|newest")
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    min_rating: float = Field(default=0, ge=0, le=5)
    risk_level: Optional[RiskLevel] = None


class PluginInstallRequest(BaseModel):
    """Request to install plugin"""
    plugin_id: str
    version: Optional[str] = None
    config: dict[str, Any] = Field(default_factory=dict)
    auto_enable: bool = True


class PluginPublishRequest(BaseModel):
    """Request to publish plugin"""
    manifest: PluginManifest
    version_info: PluginVersion
    category: str


# ==================== Plugin Marketplace Service ====================

class PluginMarketplaceService:
    """Central service for plugin marketplace operations"""

    def __init__(self, storage_path: str | Path | None = None):
        self.storage_path = Path(storage_path) if storage_path else Path("./marketplace")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self._plugins: dict[str, PluginRecord] = {}
        self._reviews: dict[str, list[PluginReview]] = {}
        self._security_scans: dict[str, list[PluginSecurityScan]] = {}
        self._installations: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

        self._load_data()

    def _load_data(self) -> None:
        """Load marketplace data from storage"""
        try:
            plugins_file = self.storage_path / "plugins.json"
            if plugins_file.exists():
                with open(plugins_file) as f:
                    data = json.load(f)
                    for plugin_data in data.get("plugins", []):
                        plugin = PluginRecord(**plugin_data)
                        self._plugins[plugin.id] = plugin
            logger.info(f"Loaded {len(self._plugins)} plugins")
        except Exception as e:
            logger.error(f"Failed to load plugins: {e}")

    def _save_data(self) -> None:
        """Save marketplace data to storage"""
        try:
            plugins_file = self.storage_path / "plugins.json"
            with open(plugins_file, "w") as f:
                data = {
                    "plugins": [
                        json.loads(p.model_dump_json(default=str))
                        for p in self._plugins.values()
                    ]
                }
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save plugins: {e}")

    # ==================== Plugin Management ====================

    def publish_plugin(self, request: PluginPublishRequest, publisher_id: str) -> PluginRecord:
        """Publish a new plugin"""
        with self._lock:
            plugin = PluginRecord(
                manifest=request.manifest,
                publisher_id=publisher_id,
                publisher_name=request.manifest.author,
                status=PluginStatus.PENDING_REVIEW,
                versions=[request.version_info]
            )
            self._plugins[plugin.id] = plugin
            self._save_data()
            logger.info(f"Plugin published: {plugin.manifest.name}")
            return plugin

    def get_plugin(self, plugin_id: str) -> Optional[PluginRecord]:
        """Get plugin by ID"""
        return self._plugins.get(plugin_id)

    def list_plugins(
        self,
        status: Optional[PluginStatus] = None,
        limit: int = 20,
        offset: int = 0
    ) -> tuple[list[PluginRecord], int]:
        """List plugins with pagination"""
        plugins = list(self._plugins.values())

        if status:
            plugins = [p for p in plugins if p.status == status]

        total = len(plugins)
        plugins.sort(key=lambda p: p.updated_at, reverse=True)
        return plugins[offset:offset + limit], total

    def search_plugins(self, query: PluginSearchQuery) -> tuple[list[PluginRecord], int]:
        """Search plugins"""
        results = list(self._plugins.values())

        # Filter by status (only published)
        results = [p for p in results if p.status == PluginStatus.PUBLISHED]

        # Filter by query
        if query.query:
            q = query.query.lower()
            results = [
                p for p in results
                if q in p.manifest.name.lower()
                or q in p.manifest.description.lower()
                or any(q in cap.lower() for cap in p.manifest.capabilities)
            ]

        # Filter by category
        if query.category:
            results = [p for p in results if query.category in p.manifest.categories]

        # Filter by rating
        if query.min_rating > 0:
            results = [p for p in results if p.rating >= query.min_rating]

        # Filter by risk level
        if query.risk_level:
            results = [p for p in results if p.risk_level == query.risk_level]

        # Sort
        if query.sort_by == "rating":
            results.sort(key=lambda p: (p.rating, p.rating_count), reverse=True)
        elif query.sort_by == "downloads":
            results.sort(key=lambda p: p.downloads, reverse=True)
        elif query.sort_by == "newest":
            results.sort(key=lambda p: p.published_at or p.created_at, reverse=True)
        else:  # relevance
            results.sort(key=lambda p: (p.rating, p.downloads), reverse=True)

        total = len(results)
        return results[offset:offset + query.limit], total

    def update_plugin_status(self, plugin_id: str, status: PluginStatus) -> Optional[PluginRecord]:
        """Update plugin status"""
        with self._lock:
            plugin = self._plugins.get(plugin_id)
            if plugin:
                plugin.status = status
                if status == PluginStatus.PUBLISHED and not plugin.published_at:
                    plugin.published_at = datetime.now(UTC)
                plugin.updated_at = datetime.now(UTC)
                self._save_data()
            return plugin

    def add_plugin_version(self, plugin_id: str, version: PluginVersion) -> Optional[PluginRecord]:
        """Add new version to plugin"""
        with self._lock:
            plugin = self._plugins.get(plugin_id)
            if plugin:
                plugin.versions.append(version)
                plugin.manifest.version = version.version
                plugin.updated_at = datetime.now(UTC)
                self._save_data()
            return plugin

    # ==================== Reviews & Ratings ====================

    def add_review(self, plugin_id: str, review: PluginReview) -> PluginReview:
        """Add review to plugin"""
        with self._lock:
            if plugin_id not in self._reviews:
                self._reviews[plugin_id] = []

            self._reviews[plugin_id].append(review)

            # Update plugin rating
            plugin = self._plugins.get(plugin_id)
            if plugin:
                reviews = self._reviews[plugin_id]
                plugin.rating = sum(r.rating for r in reviews) / len(reviews)
                plugin.rating_count = len(reviews)
                plugin.review_count = len([r for r in reviews if r.status == ReviewStatus.APPROVED])
                plugin.updated_at = datetime.now(UTC)
                self._save_data()

            return review

    def get_reviews(self, plugin_id: str, limit: int = 20, offset: int = 0) -> tuple[list[PluginReview], int]:
        """Get reviews for plugin"""
        reviews = self._reviews.get(plugin_id, [])
        reviews = [r for r in reviews if r.status == ReviewStatus.APPROVED]
        reviews.sort(key=lambda r: r.created_at, reverse=True)
        total = len(reviews)
        return reviews[offset:offset + limit], total

    # ==================== Security Scanning ====================

    def record_security_scan(self, scan: PluginSecurityScan) -> PluginSecurityScan:
        """Record security scan result"""
        with self._lock:
            plugin_id = scan.plugin_id
            if plugin_id not in self._security_scans:
                self._security_scans[plugin_id] = []

            self._security_scans[plugin_id].append(scan)

            # Update plugin risk level
            plugin = self._plugins.get(plugin_id)
            if plugin:
                plugin.last_security_scan = scan.scan_date
                plugin.risk_level = scan.risk_level
                plugin.security_issues = scan.vulnerabilities
                plugin.updated_at = datetime.now(UTC)
                self._save_data()

            return scan

    def get_latest_security_scan(self, plugin_id: str) -> Optional[PluginSecurityScan]:
        """Get latest security scan for plugin"""
        scans = self._security_scans.get(plugin_id, [])
        if scans:
            return max(scans, key=lambda s: s.scan_date)
        return None

    # ==================== Installation Tracking ====================

    def record_installation(self, plugin_id: str, user_id: str, config: dict[str, Any]) -> str:
        """Record plugin installation"""
        with self._lock:
            install_id = str(uuid4())
            self._installations[install_id] = {
                "plugin_id": plugin_id,
                "user_id": user_id,
                "config": config,
                "status": PluginInstallStatus.INSTALLED,
                "installed_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC)
            }

            # Update plugin stats
            plugin = self._plugins.get(plugin_id)
            if plugin:
                plugin.installs += 1
                plugin.active_installs += 1
                plugin.downloads += 1
                plugin.updated_at = datetime.now(UTC)
                self._save_data()

            return install_id

    def uninstall_plugin(self, install_id: str) -> bool:
        """Record plugin uninstallation"""
        with self._lock:
            if install_id in self._installations:
                install = self._installations[install_id]
                plugin_id = install["plugin_id"]

                # Update plugin stats
                plugin = self._plugins.get(plugin_id)
                if plugin:
                    plugin.active_installs = max(0, plugin.active_installs - 1)
                    plugin.updated_at = datetime.now(UTC)
                    self._save_data()

                del self._installations[install_id]
                return True
            return False

    # ==================== Statistics ====================

    def get_marketplace_stats(self) -> dict[str, Any]:
        """Get marketplace statistics"""
        plugins = list(self._plugins.values())
        published = [p for p in plugins if p.status == PluginStatus.PUBLISHED]

        return {
            "total_plugins": len(plugins),
            "published_plugins": len(published),
            "total_downloads": sum(p.downloads for p in published),
            "total_installs": sum(p.installs for p in published),
            "active_installs": sum(p.active_installs for p in published),
            "avg_rating": sum(p.rating for p in published) / len(published) if published else 0,
            "total_reviews": sum(p.review_count for p in published),
        }

    def get_featured_plugins(self, limit: int = 10) -> list[PluginRecord]:
        """Get featured plugins"""
        plugins = list(self._plugins.values())
        plugins = [p for p in plugins if p.status == PluginStatus.PUBLISHED and p.featured]
        plugins = [p for p in plugins if not p.featured_until or p.featured_until > datetime.now(UTC)]
        plugins.sort(key=lambda p: (p.rating, p.downloads), reverse=True)
        return plugins[:limit]

    def get_trending_plugins(self, days: int = 7, limit: int = 10) -> list[PluginRecord]:
        """Get trending plugins"""
        cutoff = datetime.now(UTC) - timedelta(days=days)
        plugins = list(self._plugins.values())
        plugins = [p for p in plugins if p.status == PluginStatus.PUBLISHED]
        plugins = [p for p in plugins if p.updated_at > cutoff]
        plugins.sort(key=lambda p: (p.downloads, p.rating), reverse=True)
        return plugins[:limit]
