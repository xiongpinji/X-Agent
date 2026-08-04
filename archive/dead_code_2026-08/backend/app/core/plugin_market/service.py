"""P2-07: 插件生态市场核心服务.

功能:
- 插件发布流水线: 提交 → 审核 → 上架
- 发现与搜索: 关键词/分类/排序
- 安装生命周期: 安装/卸载/版本管理
- 评价与统计: 评分/评论/下载量
- 安全评估: 风险评分/权限审查

设计原则:
- 内存存储 (dev), 生产可替换为 DB
- 审核门控: 未审核插件不可安装
- 风险评分: 基于权限数量/网络访问/文件系统访问
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class PluginStatus(StrEnum):
    """插件状态."""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"
    INSTALLED = "installed"
    DISABLED = "disabled"


class PluginCategory(StrEnum):
    """插件分类."""

    DEVELOPMENT = "development"
    DATA = "data"
    AUTOMATION = "automation"
    INTEGRATION = "integration"
    SECURITY = "security"
    PRODUCTIVITY = "productivity"
    OTHER = "other"


class RiskLevel(StrEnum):
    """风险等级."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PluginManifest:
    """插件清单."""

    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    category: PluginCategory = PluginCategory.OTHER
    permissions: list[str] = field(default_factory=list)
    requires_network: bool = False
    requires_filesystem: bool = False
    dependencies: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class PluginListing:
    """插件目录条目."""

    plugin_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    manifest: PluginManifest | None = None
    status: PluginStatus = PluginStatus.DRAFT
    risk_level: RiskLevel = RiskLevel.LOW
    risk_score: float = 0.0
    rating: float = 0.0
    rating_count: int = 0
    downloads: int = 0
    installed_count: int = 0
    is_installed: bool = False
    is_enabled: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    published_at: str | None = None
    reviewer: str | None = None
    review_note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.manifest.name if self.manifest else "",
            "version": self.manifest.version if self.manifest else "",
            "description": self.manifest.description if self.manifest else "",
            "author": self.manifest.author if self.manifest else "",
            "category": self.manifest.category.value if self.manifest else "other",
            "status": self.status.value,
            "risk_level": self.risk_level.value,
            "risk_score": self.risk_score,
            "rating": self.rating,
            "rating_count": self.rating_count,
            "downloads": self.downloads,
            "installed_count": self.installed_count,
            "is_installed": self.is_installed,
            "is_enabled": self.is_enabled,
            "created_at": self.created_at,
            "published_at": self.published_at,
        }


@dataclass
class PluginReview:
    """插件评价."""

    review_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    plugin_id: str = ""
    user_id: str = ""
    rating: int = 5  # 1-5
    comment: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class PluginStats:
    """插件统计."""

    plugin_id: str = ""
    total_downloads: int = 0
    total_installs: int = 0
    active_installs: int = 0
    avg_rating: float = 0.0
    total_reviews: int = 0
    risk_score: float = 0.0


@dataclass
class RiskAssessment:
    """风险评估."""

    risk_level: RiskLevel = RiskLevel.LOW
    risk_score: float = 0.0
    factors: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


@dataclass
class InstallResult:
    """安装结果."""

    success: bool
    plugin_id: str = ""
    message: str = ""
    version: str = ""


class PluginMarketService:
    """插件生态市场服务.

    提供插件发布审核流水线、发现搜索、安装生命周期、
    评价统计和安全评估的完整功能。
    """

    def __init__(self):
        self._registry: dict[str, PluginListing] = {}
        self._reviews: dict[str, list[PluginReview]] = {}
        self._installed: dict[str, PluginListing] = {}

    # ─── 发布流水线 ─────────────────────────────────────────────────────────

    def submit_plugin(self, manifest: PluginManifest) -> PluginListing:
        """提交插件 (进入待审核状态)."""
        listing = PluginListing(
            manifest=manifest,
            status=PluginStatus.PENDING_REVIEW,
        )
        # 自动风险评估
        assessment = self.compute_risk_score(manifest)
        listing.risk_level = assessment.risk_level
        listing.risk_score = assessment.risk_score

        self._registry[listing.plugin_id] = listing
        logger.info("Plugin submitted: %s (%s)", manifest.name, listing.plugin_id)
        return listing

    def review_plugin(self, plugin_id: str, reviewer: str, verdict: str, note: str = "") -> bool:
        """审核插件.

        Args:
            plugin_id: 插件 ID
            reviewer: 审核人
            verdict: "approve" 或 "reject"
            note: 审核备注
        """
        listing = self._registry.get(plugin_id)
        if not listing or listing.status != PluginStatus.PENDING_REVIEW:
            return False

        listing.reviewer = reviewer
        listing.review_note = note
        listing.updated_at = datetime.now(UTC).isoformat()

        if verdict == "approve":
            listing.status = PluginStatus.APPROVED
        elif verdict == "reject":
            listing.status = PluginStatus.REJECTED
        else:
            return False

        logger.info("Plugin reviewed: %s -> %s by %s", plugin_id, verdict, reviewer)
        return True

    def publish_plugin(self, plugin_id: str) -> bool:
        """上架插件 (需已审核通过)."""
        listing = self._registry.get(plugin_id)
        if not listing or listing.status != PluginStatus.APPROVED:
            return False

        listing.status = PluginStatus.PUBLISHED
        listing.published_at = datetime.now(UTC).isoformat()
        listing.updated_at = datetime.now(UTC).isoformat()
        logger.info("Plugin published: %s", plugin_id)
        return True

    # ─── 发现与搜索 ─────────────────────────────────────────────────────────

    def search(
        self,
        query: str | None = None,
        category: str | None = None,
        sort_by: str = "rating",
        limit: int = 20,
    ) -> list[PluginListing]:
        """搜索已发布插件."""
        results = [
            listing
            for listing in self._registry.values()
            if listing.status == PluginStatus.PUBLISHED
        ]

        # 关键词过滤
        if query:
            q = query.lower()
            results = [
                listing
                for listing in results
                if listing.manifest
                and (
                    q in listing.manifest.name.lower()
                    or q in listing.manifest.description.lower()
                    or any(q in tag.lower() for tag in listing.manifest.tags)
                )
            ]

        # 分类过滤
        if category:
            results = [
                listing
                for listing in results
                if listing.manifest and listing.manifest.category.value == category
            ]

        # 排序
        if sort_by == "rating":
            results.sort(key=lambda x: x.rating, reverse=True)
        elif sort_by == "downloads":
            results.sort(key=lambda x: x.downloads, reverse=True)
        elif sort_by == "newest":
            results.sort(key=lambda x: x.published_at or "", reverse=True)

        return results[:limit]

    def get_plugin(self, plugin_id: str) -> PluginListing | None:
        """获取插件详情."""
        return self._registry.get(plugin_id)

    # ─── 安装生命周期 ─────────────────────────────────────────────────────────

    def install(self, plugin_id: str, version: str | None = None) -> InstallResult:
        """安装插件."""
        listing = self._registry.get(plugin_id)
        if not listing:
            return InstallResult(success=False, plugin_id=plugin_id, message="Plugin not found")
        if listing.status != PluginStatus.PUBLISHED:
            return InstallResult(success=False, plugin_id=plugin_id, message="Plugin not published")
        if listing.is_installed:
            return InstallResult(success=False, plugin_id=plugin_id, message="Already installed")

        listing.is_installed = True
        listing.is_enabled = True
        listing.status = PluginStatus.INSTALLED
        listing.installed_count += 1
        listing.downloads += 1
        listing.updated_at = datetime.now(UTC).isoformat()

        self._installed[plugin_id] = listing
        logger.info("Plugin installed: %s", plugin_id)
        return InstallResult(
            success=True,
            plugin_id=plugin_id,
            message="Installed successfully",
            version=listing.manifest.version if listing.manifest else "1.0.0",
        )

    def uninstall(self, plugin_id: str) -> bool:
        """卸载插件."""
        listing = self._registry.get(plugin_id)
        if not listing or not listing.is_installed:
            return False

        listing.is_installed = False
        listing.is_enabled = False
        listing.status = PluginStatus.PUBLISHED
        listing.updated_at = datetime.now(UTC).isoformat()

        self._installed.pop(plugin_id, None)
        logger.info("Plugin uninstalled: %s", plugin_id)
        return True

    # ─── 评价与统计 ─────────────────────────────────────────────────────────

    def rate_plugin(self, plugin_id: str, user_id: str, rating: int, comment: str = "") -> bool:
        """评价插件."""
        listing = self._registry.get(plugin_id)
        if not listing:
            return False

        review = PluginReview(
            plugin_id=plugin_id,
            user_id=user_id,
            rating=max(1, min(5, rating)),
            comment=comment,
        )

        if plugin_id not in self._reviews:
            self._reviews[plugin_id] = []
        self._reviews[plugin_id].append(review)

        # 更新平均评分
        reviews = self._reviews[plugin_id]
        listing.rating = sum(r.rating for r in reviews) / len(reviews)
        listing.rating_count = len(reviews)
        listing.updated_at = datetime.now(UTC).isoformat()

        return True

    def get_stats(self, plugin_id: str) -> PluginStats | None:
        """获取插件统计."""
        listing = self._registry.get(plugin_id)
        if not listing:
            return None

        reviews = self._reviews.get(plugin_id, [])
        return PluginStats(
            plugin_id=plugin_id,
            total_downloads=listing.downloads,
            total_installs=listing.installed_count,
            active_installs=1 if listing.is_installed else 0,
            avg_rating=listing.rating,
            total_reviews=len(reviews),
            risk_score=listing.risk_score,
        )

    # ─── 安全评估 ─────────────────────────────────────────────────────────

    def compute_risk_score(self, manifest: PluginManifest) -> RiskAssessment:
        """计算插件风险评分.

        评分因子:
        - 权限数量 (每个 +10)
        - 网络访问 (+25)
        - 文件系统访问 (+20)
        - 依赖数量 (每个 +5)
        """
        score = 0.0
        factors: list[str] = []
        recommendations: list[str] = []

        # 权限
        perm_score = len(manifest.permissions) * 10
        if perm_score > 0:
            score += perm_score
            factors.append(f"请求 {len(manifest.permissions)} 项权限 (+{perm_score})")

        # 网络
        if manifest.requires_network:
            score += 25
            factors.append("需要网络访问 (+25)")
            recommendations.append("建议限制出站域名白名单")

        # 文件系统
        if manifest.requires_filesystem:
            score += 20
            factors.append("需要文件系统访问 (+20)")
            recommendations.append("建议限制访问路径范围")

        # 依赖
        dep_score = len(manifest.dependencies) * 5
        if dep_score > 0:
            score += dep_score
            factors.append(f"{len(manifest.dependencies)} 个依赖 (+{dep_score})")

        # 风险等级
        if score < 20:
            level = RiskLevel.LOW
        elif score < 50:
            level = RiskLevel.MEDIUM
        elif score < 80:
            level = RiskLevel.HIGH
        else:
            level = RiskLevel.CRITICAL

        return RiskAssessment(
            risk_level=level,
            risk_score=score,
            factors=factors,
            recommendations=recommendations,
        )

    # ─── 辅助 ─────────────────────────────────────────────────────────────

    def list_all(self, status: str | None = None) -> list[PluginListing]:
        """列出所有插件."""
        if status:
            return [l for l in self._registry.values() if l.status.value == status]
        return list(self._registry.values())

    def get_reviews(self, plugin_id: str) -> list[PluginReview]:
        """获取插件评价列表."""
        return self._reviews.get(plugin_id, [])

    # ─── 热加载引擎 (K1) ────────────────────────────────────────────────────

    def hot_reload(self, plugin_id: str) -> dict[str, object]:
        """Hot-reload a plugin without system restart.

        Unloads the current module, clears cache, and reloads from source.
        Returns status dict with timing info.
        """
        import importlib
        import time

        listing = self._registry.get(plugin_id)
        if not listing:
            return {"success": False, "error": "Plugin not found"}
        if not listing.is_installed:
            return {"success": False, "error": "Plugin not installed"}

        start = time.perf_counter()
        module_path = f"plugins.{plugin_id}.main"

        try:
            # Unload
            import sys
            if module_path in sys.modules:
                del sys.modules[module_path]

            # Reload
            try:
                mod = importlib.import_module(module_path)
                if hasattr(mod, "activate"):
                    mod.activate()
                listing.is_enabled = True
                listing.updated_at = datetime.now(UTC).isoformat()
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.info("Plugin hot-reloaded: %s (%.1fms)", plugin_id, elapsed_ms)
                return {"success": True, "plugin_id": plugin_id, "reload_time_ms": round(elapsed_ms, 1)}
            except ImportError as e:
                return {"success": False, "error": f"Import failed: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def hot_unload(self, plugin_id: str) -> dict[str, object]:
        """Unload a plugin module from memory without uninstalling."""
        import sys

        listing = self._registry.get(plugin_id)
        if not listing:
            return {"success": False, "error": "Plugin not found"}

        module_path = f"plugins.{plugin_id}.main"
        try:
            mod = sys.modules.get(module_path)
            if mod and hasattr(mod, "deactivate"):
                mod.deactivate()
            if module_path in sys.modules:
                del sys.modules[module_path]
            listing.is_enabled = False
            listing.updated_at = datetime.now(UTC).isoformat()
            logger.info("Plugin unloaded: %s", plugin_id)
            return {"success": True, "plugin_id": plugin_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─── 版本管理 (K2) ──────────────────────────────────────────────────────

    def check_version_compatibility(self, plugin_id: str, target_version: str) -> dict[str, object]:
        """Check if upgrading to target_version is compatible.

        Uses semver rules: major version changes are breaking,
        minor/patch are backward-compatible.
        """
        listing = self._registry.get(plugin_id)
        if not listing or not listing.manifest:
            return {"compatible": False, "reason": "Plugin not found"}

        current = listing.manifest.version
        try:
            cur_parts = [int(x) for x in current.split("-")[0].split(".")]
            tgt_parts = [int(x) for x in target_version.split("-")[0].split(".")]
        except ValueError:
            return {"compatible": False, "reason": "Invalid version format"}

        cur_major, _cur_minor, _cur_patch = ([*cur_parts, 0, 0, 0])[:3]
        tgt_major, _tgt_minor, _tgt_patch = ([*tgt_parts, 0, 0, 0])[:3]

        if tgt_major > cur_major:
            return {
                "compatible": True,
                "breaking": True,
                "reason": f"Major version upgrade {current} → {target_version} may contain breaking changes",
                "recommendation": "Review changelog before upgrading",
            }
        if tgt_major < cur_major:
            return {
                "compatible": False,
                "breaking": True,
                "reason": f"Downgrade across major versions not supported ({current} → {target_version})",
            }
        # Same major: minor/patch upgrades are compatible
        return {
            "compatible": True,
            "breaking": False,
            "reason": f"Compatible upgrade {current} → {target_version}",
        }

    def upgrade_plugin(self, plugin_id: str, target_version: str) -> dict[str, object]:
        """Upgrade plugin to a new version with rollback support."""
        listing = self._registry.get(plugin_id)
        if not listing or not listing.manifest:
            return {"success": False, "error": "Plugin not found"}

        compat = self.check_version_compatibility(plugin_id, target_version)
        if not compat.get("compatible"):
            return {"success": False, "error": compat.get("reason", "Incompatible")}

        old_version = listing.manifest.version

        # Store rollback point
        if not hasattr(listing, "_version_history"):
            listing._version_history = []
        listing._version_history.append({
            "version": old_version,
            "timestamp": datetime.now(UTC).isoformat(),
        })

        # Apply upgrade
        listing.manifest.version = target_version
        listing.updated_at = datetime.now(UTC).isoformat()

        # Hot-reload if installed
        reload_result = None
        if listing.is_installed:
            reload_result = self.hot_reload(plugin_id)

        logger.info("Plugin upgraded: %s %s → %s", plugin_id, old_version, target_version)
        return {
            "success": True,
            "plugin_id": plugin_id,
            "old_version": old_version,
            "new_version": target_version,
            "breaking": compat.get("breaking", False),
            "reload": reload_result,
        }

    def rollback_plugin(self, plugin_id: str) -> dict[str, object]:
        """Rollback plugin to the previous version."""
        listing = self._registry.get(plugin_id)
        if not listing or not listing.manifest:
            return {"success": False, "error": "Plugin not found"}

        history = getattr(listing, "_version_history", [])
        if not history:
            return {"success": False, "error": "No version history available for rollback"}

        prev = history.pop()
        current = listing.manifest.version
        listing.manifest.version = prev["version"]
        listing.updated_at = datetime.now(UTC).isoformat()

        # Hot-reload if installed
        reload_result = None
        if listing.is_installed:
            reload_result = self.hot_reload(plugin_id)

        logger.info("Plugin rolled back: %s %s → %s", plugin_id, current, prev["version"])
        return {
            "success": True,
            "plugin_id": plugin_id,
            "from_version": current,
            "to_version": prev["version"],
            "reload": reload_result,
        }

    def get_version_history(self, plugin_id: str) -> list[dict[str, object]]:
        """Get version history for a plugin."""
        listing = self._registry.get(plugin_id)
        if not listing:
            return []
        return getattr(listing, "_version_history", [])


# ─── 单例 ─────────────────────────────────────────────────────────────────────

_service: PluginMarketService | None = None


def get_plugin_market_service() -> PluginMarketService:
    """获取插件市场服务单例."""
    global _service
    if _service is None:
        _service = PluginMarketService()
    return _service


def reset_plugin_market_service() -> None:
    """重置服务 (测试用)."""
    global _service
    _service = None
