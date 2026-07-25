"""技能依赖管理系统 - 支持依赖声明、自动安装、冲突检测、依赖树可视化"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class DependencyType(StrEnum):
    """依赖类型"""
    REQUIRED = "required"  # 必需依赖
    OPTIONAL = "optional"  # 可选依赖
    DEV = "dev"  # 开发依赖


class ConflictType(StrEnum):
    """冲突类型"""
    VERSION_CONFLICT = "version_conflict"  # 版本冲突
    INCOMPATIBLE = "incompatible"  # 不兼容
    CIRCULAR = "circular"  # 循环依赖


@dataclass
class SkillDependency:
    """技能依赖"""
    skill_id: str
    dep_skill_id: str
    version_spec: str = "*"  # 版本规范 (e.g., ">=1.0.0", "1.x", "*")
    dep_type: DependencyType = DependencyType.REQUIRED
    optional: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "skill_id": self.skill_id,
            "dep_skill_id": self.dep_skill_id,
            "version_spec": self.version_spec,
            "dep_type": self.dep_type.value,
            "optional": self.optional,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class DependencyConflict:
    """依赖冲突"""
    conflict_type: ConflictType
    skill_ids: list[str]
    description: str
    resolution_suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "conflict_type": self.conflict_type.value,
            "skill_ids": self.skill_ids,
            "description": self.description,
            "resolution_suggestions": self.resolution_suggestions,
        }


class SkillDependencyManager:
    """技能依赖管理器"""

    def __init__(self):
        self.dependencies: dict[str, list[SkillDependency]] = {}  # skill_id -> [deps]
        self.reverse_dependencies: dict[str, list[str]] = {}  # skill_id -> [dependent_skill_ids]
        self.installed_skills: dict[str, str] = {}  # skill_id -> version
        self.conflicts: list[DependencyConflict] = []

    def add_dependency(
        self,
        skill_id: str,
        dep_skill_id: str,
        version_spec: str = "*",
        dep_type: DependencyType = DependencyType.REQUIRED,
        optional: bool = False,
    ) -> tuple[bool, str | None]:
        """添加依赖"""
        try:
            # 检查循环依赖
            if self._has_circular_dependency(skill_id, dep_skill_id):
                return False, "检测到循环依赖"

            # 创建依赖
            dependency = SkillDependency(
                skill_id=skill_id,
                dep_skill_id=dep_skill_id,
                version_spec=version_spec,
                dep_type=dep_type,
                optional=optional,
            )

            # 添加到依赖列表
            if skill_id not in self.dependencies:
                self.dependencies[skill_id] = []

            # 检查是否已存在
            existing = [
                d for d in self.dependencies[skill_id]
                if d.dep_skill_id == dep_skill_id
            ]
            if existing:
                return False, f"依赖 {dep_skill_id} 已存在"

            self.dependencies[skill_id].append(dependency)

            # 更新反向依赖
            if dep_skill_id not in self.reverse_dependencies:
                self.reverse_dependencies[dep_skill_id] = []
            self.reverse_dependencies[dep_skill_id].append(skill_id)

            logger.info(f"添加依赖: {skill_id} -> {dep_skill_id}")
            return True, None

        except Exception as e:
            error = f"添加依赖失败: {e!s}"
            logger.error(error, exc_info=True)
            return False, error

    def get_dependencies(self, skill_id: str) -> list[SkillDependency]:
        """获取依赖列表"""
        return self.dependencies.get(skill_id, [])

    def get_required_dependencies(self, skill_id: str) -> list[SkillDependency]:
        """获取必需依赖"""
        deps = self.dependencies.get(skill_id, [])
        return [d for d in deps if d.dep_type == DependencyType.REQUIRED]

    def get_optional_dependencies(self, skill_id: str) -> list[SkillDependency]:
        """获取可选依赖"""
        deps = self.dependencies.get(skill_id, [])
        return [d for d in deps if d.dep_type == DependencyType.OPTIONAL]

    def get_dependents(self, skill_id: str) -> list[str]:
        """获取依赖此技能的技能列表"""
        return self.reverse_dependencies.get(skill_id, [])

    def check_dependencies(self, skill_id: str) -> tuple[bool, str | None, list[str] | None]:
        """检查依赖是否满足"""
        try:
            deps = self.get_required_dependencies(skill_id)
            missing = []

            for dep in deps:
                if dep.dep_skill_id not in self.installed_skills:
                    missing.append(dep.dep_skill_id)
                else:
                    # 检查版本兼容性
                    installed_version = self.installed_skills[dep.dep_skill_id]
                    if not self._check_version_compatibility(installed_version, dep.version_spec):
                        missing.append(f"{dep.dep_skill_id}@{dep.version_spec}")

            if missing:
                return False, f"缺少依赖: {', '.join(missing)}", missing

            return True, None, None

        except Exception as e:
            error = f"检查依赖失败: {e!s}"
            logger.error(error, exc_info=True)
            return False, error, None

    def install_dependencies(
        self,
        skill_id: str,
        installer_func=None,
    ) -> tuple[bool, str | None, list[str]]:
        """安装依赖"""
        try:
            deps = self.get_required_dependencies(skill_id)
            installed = []

            for dep in deps:
                if dep.dep_skill_id not in self.installed_skills:
                    # 调用安装函数
                    if installer_func:
                        success = installer_func(dep.dep_skill_id, dep.version_spec)
                        if success:
                            installed.append(dep.dep_skill_id)
                        else:
                            return False, f"安装依赖 {dep.dep_skill_id} 失败", installed
                    else:
                        # 模拟安装
                        self.installed_skills[dep.dep_skill_id] = dep.version_spec
                        installed.append(dep.dep_skill_id)

            logger.info(f"安装依赖: {skill_id} -> {installed}")
            return True, None, installed

        except Exception as e:
            error = f"安装依赖失败: {e!s}"
            logger.error(error, exc_info=True)
            return False, error, []

    def resolve_conflicts(self, skill_ids: list[str]) -> tuple[bool, str | None, list[DependencyConflict]]:
        """解决依赖冲突"""
        try:
            conflicts = []

            # 检查版本冲突
            for i, skill_id1 in enumerate(skill_ids):
                for skill_id2 in skill_ids[i + 1:]:
                    conflict = self._check_version_conflict(skill_id1, skill_id2)
                    if conflict:
                        conflicts.append(conflict)

            # 检查循环依赖
            for skill_id in skill_ids:
                for dep in self.get_dependencies(skill_id):
                    if dep.dep_skill_id in skill_ids:
                        # 检查是否形成循环
                        if self._has_circular_dependency(skill_id, dep.dep_skill_id):
                            conflict = DependencyConflict(
                                conflict_type=ConflictType.CIRCULAR,
                                skill_ids=[skill_id, dep.dep_skill_id],
                                description=f"检测到循环依赖: {skill_id} <-> {dep.dep_skill_id}",
                                resolution_suggestions=[
                                    "移除其中一个依赖",
                                    "重构技能架构以消除循环依赖",
                                ],
                            )
                            conflicts.append(conflict)

            if conflicts:
                return False, f"检测到 {len(conflicts)} 个冲突", conflicts

            return True, None, []

        except Exception as e:
            error = f"解决冲突失败: {e!s}"
            logger.error(error, exc_info=True)
            return False, error, []

    def get_dependency_tree(self, skill_id: str, depth: int = 0, max_depth: int = 5) -> dict[str, Any]:
        """获取依赖树"""
        if depth > max_depth:
            return {"skill_id": skill_id, "truncated": True}

        deps = self.get_dependencies(skill_id)
        children = []

        for dep in deps:
            child_tree = self.get_dependency_tree(
                dep.dep_skill_id,
                depth + 1,
                max_depth
            )
            children.append({
                "skill_id": dep.dep_skill_id,
                "version_spec": dep.version_spec,
                "dep_type": dep.dep_type.value,
                "installed": dep.dep_skill_id in self.installed_skills,
                "children": child_tree.get("children", []),
            })

        return {
            "skill_id": skill_id,
            "depth": depth,
            "children": children,
        }

    def visualize_dependency_tree(self, skill_id: str) -> str:
        """可视化依赖树"""
        tree = self.get_dependency_tree(skill_id)
        return self._tree_to_string(tree)

    def _tree_to_string(self, tree: dict[str, Any], prefix: str = "") -> str:
        """将依赖树转换为字符串"""
        lines = []
        skill_id = tree["skill_id"]
        children = tree.get("children", [])

        lines.append(f"{prefix}{skill_id}")

        for i, child in enumerate(children):
            is_last = i == len(children) - 1
            child_prefix = prefix + ("└── " if is_last else "├── ")
            next_prefix = prefix + ("    " if is_last else "│   ")

            child_str = self._tree_to_string(child, next_prefix)
            lines.append(child_prefix + child_str.split("\n")[0].lstrip())

            for line in child_str.split("\n")[1:]:
                if line:
                    lines.append(next_prefix + line)

        return "\n".join(lines)

    def remove_dependency(self, skill_id: str, dep_skill_id: str) -> tuple[bool, str | None]:
        """移除依赖"""
        try:
            if skill_id not in self.dependencies:
                return False, "技能不存在"

            deps = self.dependencies[skill_id]
            original_len = len(deps)

            self.dependencies[skill_id] = [
                d for d in deps if d.dep_skill_id != dep_skill_id
            ]

            if len(self.dependencies[skill_id]) == original_len:
                return False, "依赖不存在"

            # 更新反向依赖
            if dep_skill_id in self.reverse_dependencies:
                self.reverse_dependencies[dep_skill_id] = [
                    s for s in self.reverse_dependencies[dep_skill_id]
                    if s != skill_id
                ]

            logger.info(f"移除依赖: {skill_id} -> {dep_skill_id}")
            return True, None

        except Exception as e:
            error = f"移除依赖失败: {e!s}"
            logger.error(error, exc_info=True)
            return False, error

    def _has_circular_dependency(self, skill_id: str, dep_skill_id: str, visited: set[str] | None = None) -> bool:
        """检查是否存在循环依赖"""
        if visited is None:
            visited = set()

        if skill_id in visited:
            return True

        visited.add(skill_id)

        # 获取dep_skill_id的依赖
        deps = self.get_dependencies(dep_skill_id)
        for dep in deps:
            if dep.dep_skill_id == skill_id:
                return True
            if self._has_circular_dependency(skill_id, dep.dep_skill_id, visited.copy()):
                return True

        return False

    def _check_version_compatibility(self, installed_version: str, version_spec: str) -> bool:
        """检查版本兼容性"""
        if version_spec == "*":
            return True

        # 简化的版本检查逻辑
        if version_spec.startswith(">="):
            required = version_spec[2:]
            return self._compare_versions(installed_version, required) >= 0
        elif version_spec.startswith("<="):
            required = version_spec[2:]
            return self._compare_versions(installed_version, required) <= 0
        elif version_spec.startswith("="):
            required = version_spec[1:]
            return installed_version == required
        elif "x" in version_spec:
            # 处理 1.x 格式
            parts = version_spec.split(".")
            installed_parts = installed_version.split(".")
            for i, part in enumerate(parts):
                if part != "x" and i < len(installed_parts):
                    if part != installed_parts[i]:
                        return False
            return True

        return True

    def _compare_versions(self, v1: str, v2: str) -> int:
        """比较版本 (返回 1, 0, -1)"""
        try:
            parts1 = [int(x) for x in v1.split(".")]
            parts2 = [int(x) for x in v2.split(".")]

            for p1, p2 in zip(parts1, parts2, strict=False):
                if p1 > p2:
                    return 1
                elif p1 < p2:
                    return -1
            return 0
        except Exception:
            return 0

    def _check_version_conflict(self, skill_id1: str, skill_id2: str) -> DependencyConflict | None:
        """检查两个技能之间的版本冲突"""
        # 简化实现：检查是否有相同的依赖但版本不兼容
        deps1 = self.get_dependencies(skill_id1)
        deps2 = self.get_dependencies(skill_id2)

        for dep1 in deps1:
            for dep2 in deps2:
                if dep1.dep_skill_id == dep2.dep_skill_id:
                    if not self._are_version_specs_compatible(dep1.version_spec, dep2.version_spec):
                        return DependencyConflict(
                            conflict_type=ConflictType.VERSION_CONFLICT,
                            skill_ids=[skill_id1, skill_id2],
                            description=f"版本冲突: {skill_id1} 需要 {dep1.dep_skill_id}@{dep1.version_spec}, "
                                       f"{skill_id2} 需要 {dep2.dep_skill_id}@{dep2.version_spec}",
                            resolution_suggestions=[
                                f"升级 {skill_id1} 或 {skill_id2}",
                                "使用兼容的版本",
                            ],
                        )

        return None

    def _are_version_specs_compatible(self, spec1: str, spec2: str) -> bool:
        """检查两个版本规范是否兼容"""
        if spec1 == "*" or spec2 == "*":
            return True
        return spec1 == spec2


# 全局实例
_skill_dependency_manager: SkillDependencyManager | None = None


def get_skill_dependency_manager() -> SkillDependencyManager:
    """获取技能依赖管理器实例"""
    global _skill_dependency_manager
    if _skill_dependency_manager is None:
        _skill_dependency_manager = SkillDependencyManager()
    return _skill_dependency_manager


__all__ = [
    "ConflictType",
    "DependencyConflict",
    "DependencyType",
    "SkillDependency",
    "SkillDependencyManager",
    "get_skill_dependency_manager",
]
