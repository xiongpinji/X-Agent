"""技能版本管理系统 - 支持语义化版本、发布日志、兼容性信息、版本回滚"""

from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, UTC
from dataclasses import dataclass, field
from enum import Enum
import re

logger = logging.getLogger(__name__)


class VersionCompatibility(str, Enum):
    """版本兼容性"""
    COMPATIBLE = "compatible"  # 完全兼容
    PARTIALLY_COMPATIBLE = "partially_compatible"  # 部分兼容
    BREAKING_CHANGE = "breaking_change"  # 破坏性变更


@dataclass
class SkillVersion:
    """技能版本信息"""
    skill_id: str
    version: str  # 语义化版本 (major.minor.patch)
    release_date: datetime = field(default_factory=lambda: datetime.now(UTC))
    changes: str = ""  # 更新日志
    compatibility: VersionCompatibility = VersionCompatibility.COMPATIBLE
    deprecated: bool = False
    download_count: int = 0
    file_path: str = ""
    file_size_bytes: int = 0
    checksum: str = ""
    min_system_version: str = ""  # 最低系统版本要求
    max_system_version: str = ""  # 最高系统版本要求
    breaking_changes: List[str] = field(default_factory=list)  # 破坏性变更列表
    migration_guide: str = ""  # 迁移指南
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "skill_id": self.skill_id,
            "version": self.version,
            "release_date": self.release_date.isoformat(),
            "changes": self.changes,
            "compatibility": self.compatibility.value,
            "deprecated": self.deprecated,
            "download_count": self.download_count,
            "file_path": self.file_path,
            "file_size_bytes": self.file_size_bytes,
            "checksum": self.checksum,
            "min_system_version": self.min_system_version,
            "max_system_version": self.max_system_version,
            "breaking_changes": self.breaking_changes,
            "migration_guide": self.migration_guide,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class SkillVersionManager:
    """技能版本管理器"""

    def __init__(self):
        self.versions: Dict[str, List[SkillVersion]] = {}  # skill_id -> [versions]
        self.current_versions: Dict[str, str] = {}  # skill_id -> current_version
        self._lock = {}  # 用于并发控制

    def create_version(
        self,
        skill_id: str,
        version: str,
        changes: str,
        compatibility: VersionCompatibility = VersionCompatibility.COMPATIBLE,
        file_path: str = "",
        file_size_bytes: int = 0,
        checksum: str = "",
        min_system_version: str = "",
        max_system_version: str = "",
        breaking_changes: Optional[List[str]] = None,
        migration_guide: str = "",
    ) -> tuple[bool, Optional[str], Optional[SkillVersion]]:
        """创建新版本"""
        try:
            # 验证版本号格式
            if not self._is_valid_semver(version):
                return False, f"无效的版本号格式: {version}", None

            # 检查版本是否已存在
            if skill_id in self.versions:
                existing = [v for v in self.versions[skill_id] if v.version == version]
                if existing:
                    return False, f"版本 {version} 已存在", None

            # 创建版本对象
            skill_version = SkillVersion(
                skill_id=skill_id,
                version=version,
                changes=changes,
                compatibility=compatibility,
                file_path=file_path,
                file_size_bytes=file_size_bytes,
                checksum=checksum,
                min_system_version=min_system_version,
                max_system_version=max_system_version,
                breaking_changes=breaking_changes or [],
                migration_guide=migration_guide,
            )

            # 添加到版本列表
            if skill_id not in self.versions:
                self.versions[skill_id] = []

            self.versions[skill_id].append(skill_version)

            # 按版本号排序
            self.versions[skill_id].sort(
                key=lambda v: self._parse_semver(v.version),
                reverse=True
            )

            # 更新当前版本
            self.current_versions[skill_id] = version

            logger.info(f"创建版本: {skill_id}@{version}")
            return True, None, skill_version

        except Exception as e:
            error = f"创建版本失败: {str(e)}"
            logger.error(error, exc_info=True)
            return False, error, None

    def get_versions(self, skill_id: str) -> List[SkillVersion]:
        """获取所有版本"""
        return self.versions.get(skill_id, [])

    def get_version(self, skill_id: str, version: str) -> Optional[SkillVersion]:
        """获取指定版本"""
        versions = self.versions.get(skill_id, [])
        for v in versions:
            if v.version == version:
                return v
        return None

    def get_current_version(self, skill_id: str) -> Optional[SkillVersion]:
        """获取当前版本"""
        current = self.current_versions.get(skill_id)
        if current:
            return self.get_version(skill_id, current)
        return None

    def rollback_version(self, skill_id: str, version: str) -> tuple[bool, Optional[str]]:
        """回滚到指定版本"""
        try:
            # 检查版本是否存在
            skill_version = self.get_version(skill_id, version)
            if not skill_version:
                return False, f"版本 {version} 不存在"

            # 更新当前版本
            self.current_versions[skill_id] = version

            logger.info(f"回滚版本: {skill_id} -> {version}")
            return True, None

        except Exception as e:
            error = f"版本回滚失败: {str(e)}"
            logger.error(error, exc_info=True)
            return False, error

    def compare_versions(
        self,
        skill_id: str,
        v1: str,
        v2: str,
    ) -> tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """比较两个版本"""
        try:
            version1 = self.get_version(skill_id, v1)
            version2 = self.get_version(skill_id, v2)

            if not version1 or not version2:
                return False, "版本不存在", None

            comparison = {
                "v1": v1,
                "v2": v2,
                "v1_newer": self._compare_semver(v1, v2) > 0,
                "v1_changes": version1.changes,
                "v2_changes": version2.changes,
                "v1_compatibility": version1.compatibility.value,
                "v2_compatibility": version2.compatibility.value,
                "v1_breaking_changes": version1.breaking_changes,
                "v2_breaking_changes": version2.breaking_changes,
                "v1_release_date": version1.release_date.isoformat(),
                "v2_release_date": version2.release_date.isoformat(),
            }

            return True, None, comparison

        except Exception as e:
            error = f"版本比较失败: {str(e)}"
            logger.error(error, exc_info=True)
            return False, error, None

    def deprecate_version(self, skill_id: str, version: str) -> tuple[bool, Optional[str]]:
        """标记版本为废弃"""
        try:
            skill_version = self.get_version(skill_id, version)
            if not skill_version:
                return False, f"版本 {version} 不存在"

            skill_version.deprecated = True
            skill_version.updated_at = datetime.now(UTC)

            logger.info(f"标记版本为废弃: {skill_id}@{version}")
            return True, None

        except Exception as e:
            error = f"标记版本失败: {str(e)}"
            logger.error(error, exc_info=True)
            return False, error

    def get_version_history(
        self,
        skill_id: str,
        limit: int = 10,
        include_deprecated: bool = False,
    ) -> List[SkillVersion]:
        """获取版本历史"""
        versions = self.versions.get(skill_id, [])

        if not include_deprecated:
            versions = [v for v in versions if not v.deprecated]

        return versions[:limit]

    def check_compatibility(
        self,
        skill_id: str,
        from_version: str,
        to_version: str,
    ) -> tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """检查版本兼容性"""
        try:
            from_v = self.get_version(skill_id, from_version)
            to_v = self.get_version(skill_id, to_version)

            if not from_v or not to_v:
                return False, "版本不存在", None

            # 比较版本号
            cmp = self._compare_semver(to_version, from_version)

            result = {
                "from_version": from_version,
                "to_version": to_version,
                "is_upgrade": cmp > 0,
                "is_downgrade": cmp < 0,
                "compatibility": to_v.compatibility.value,
                "breaking_changes": to_v.breaking_changes,
                "migration_guide": to_v.migration_guide,
                "requires_migration": len(to_v.breaking_changes) > 0,
            }

            return True, None, result

        except Exception as e:
            error = f"兼容性检查失败: {str(e)}"
            logger.error(error, exc_info=True)
            return False, error, None

    def increment_download_count(self, skill_id: str, version: str) -> bool:
        """增加下载计数"""
        try:
            skill_version = self.get_version(skill_id, version)
            if skill_version:
                skill_version.download_count += 1
                return True
            return False
        except Exception as e:
            logger.error(f"增加下载计数失败: {str(e)}")
            return False

    def _is_valid_semver(self, version: str) -> bool:
        """验证语义化版本格式"""
        pattern = r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
        return bool(re.match(pattern, version))

    def _parse_semver(self, version: str) -> tuple[int, int, int]:
        """解析语义化版本"""
        try:
            parts = version.split(".")
            return (int(parts[0]), int(parts[1]), int(parts[2]))
        except Exception:
            return (0, 0, 0)

    def _compare_semver(self, v1: str, v2: str) -> int:
        """比较两个语义化版本
        返回: 1 if v1 > v2, -1 if v1 < v2, 0 if v1 == v2
        """
        p1 = self._parse_semver(v1)
        p2 = self._parse_semver(v2)

        if p1 > p2:
            return 1
        elif p1 < p2:
            return -1
        else:
            return 0


# 全局实例
_skill_version_manager: Optional[SkillVersionManager] = None


def get_skill_version_manager() -> SkillVersionManager:
    """获取技能版本管理器实例"""
    global _skill_version_manager
    if _skill_version_manager is None:
        _skill_version_manager = SkillVersionManager()
    return _skill_version_manager


__all__ = [
    "SkillVersionManager",
    "SkillVersion",
    "VersionCompatibility",
    "get_skill_version_manager",
]
