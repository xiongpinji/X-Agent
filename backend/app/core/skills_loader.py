"""Skill Loader - Dynamic skill loading with dependency resolution"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import logging
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .skills_core import SkillMetadata

logger = logging.getLogger(__name__)


@dataclass
class SkillLoadError:
    """Error information for skill loading"""
    skill_id: str
    error_type: str
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class DependencyInfo:
    """Information about skill dependencies"""
    skill_name: str
    version_spec: str
    resolved_version: str | None = None
    satisfied: bool = False


class SkillLoader:
    """Dynamically loads and manages skill modules"""

    def __init__(self, skill_paths: list[str] | None = None):
        self.skill_paths = skill_paths or []
        self.loaded_skills: dict[str, Any] = {}
        self.skill_metadata: dict[str, SkillMetadata] = {}
        self.load_errors: list[SkillLoadError] = []
        self._lock = asyncio.Lock()

    def add_skill_path(self, path: str) -> None:
        """Add a path to search for skills"""
        if path not in self.skill_paths:
            self.skill_paths.append(path)
            if path not in sys.path:
                sys.path.insert(0, path)

    async def load_skill(self, skill_module_path: str, skill_name: str) -> tuple[bool, str | None]:
        """Load a skill from a module path"""
        async with self._lock:
            try:
                # Check if already loaded
                if skill_name in self.loaded_skills:
                    return True, None

                # Load the module
                spec = importlib.util.spec_from_file_location(skill_name, skill_module_path)
                if spec is None or spec.loader is None:
                    error = f"Cannot load skill module: {skill_module_path}"
                    self._record_error(skill_name, "load_error", error)
                    return False, error

                module = importlib.util.module_from_spec(spec)
                sys.modules[skill_name] = module
                spec.loader.exec_module(module)

                # Get the skill class (convention: SkillName class in module)
                skill_class = self._find_skill_class(module)
                if skill_class is None:
                    error = f"No skill class found in module: {skill_module_path}"
                    self._record_error(skill_name, "class_not_found", error)
                    return False, error

                # Instantiate the skill
                skill_instance = skill_class()

                # Validate skill interface
                if not self._validate_skill_interface(skill_instance):
                    error = f"Skill does not implement required interface: {skill_name}"
                    self._record_error(skill_name, "interface_error", error)
                    return False, error

                # Store the skill
                self.loaded_skills[skill_name] = skill_instance
                self.skill_metadata[skill_name] = skill_instance.metadata

                logger.info(f"Successfully loaded skill: {skill_name}")
                return True, None

            except Exception as e:
                error = f"Error loading skill {skill_name}: {e!s}"
                self._record_error(skill_name, "exception", error)
                logger.error(error, exc_info=True)
                return False, error

    async def unload_skill(self, skill_name: str) -> tuple[bool, str | None]:
        """Unload a skill"""
        async with self._lock:
            try:
                if skill_name not in self.loaded_skills:
                    return True, None

                skill = self.loaded_skills[skill_name]

                # Call cleanup if available
                if hasattr(skill, "cleanup"):
                    await skill.cleanup()

                # Remove from tracking
                del self.loaded_skills[skill_name]
                if skill_name in self.skill_metadata:
                    del self.skill_metadata[skill_name]

                # Remove from sys.modules
                if skill_name in sys.modules:
                    del sys.modules[skill_name]

                logger.info(f"Successfully unloaded skill: {skill_name}")
                return True, None

            except Exception as e:
                error = f"Error unloading skill {skill_name}: {e!s}"
                logger.error(error, exc_info=True)
                return False, error

    async def reload_skill(self, skill_name: str, skill_module_path: str) -> tuple[bool, str | None]:
        """Reload a skill (hot reload)"""
        # Unload first
        await self.unload_skill(skill_name)
        # Then load
        return await self.load_skill(skill_module_path, skill_name)

    def get_skill(self, skill_name: str) -> Any | None:
        """Get a loaded skill instance"""
        return self.loaded_skills.get(skill_name)

    def get_skill_metadata(self, skill_name: str) -> SkillMetadata | None:
        """Get skill metadata"""
        return self.skill_metadata.get(skill_name)

    def list_loaded_skills(self) -> list[str]:
        """List all loaded skill names"""
        return list(self.loaded_skills.keys())

    def list_skill_metadata(self) -> dict[str, SkillMetadata]:
        """Get all skill metadata"""
        return dict(self.skill_metadata)

    async def resolve_dependencies(
        self, skill_metadata: SkillMetadata
    ) -> tuple[bool, list[DependencyInfo]]:
        """Resolve and validate skill dependencies"""
        dependencies = []

        for dep_name, version_spec in skill_metadata.dependencies.items():
            dep_info = DependencyInfo(
                skill_name=dep_name,
                version_spec=version_spec,
            )

            # Check if dependency is loaded
            if dep_name in self.loaded_skills:
                dep_metadata = self.skill_metadata.get(dep_name)
                if dep_metadata:
                    dep_info.resolved_version = dep_metadata.version
                    dep_info.satisfied = self._check_version_compatibility(
                        dep_metadata.version, version_spec
                    )

            dependencies.append(dep_info)

        # Check if all dependencies are satisfied
        all_satisfied = all(d.satisfied for d in dependencies)
        return all_satisfied, dependencies

    def _find_skill_class(self, module: Any) -> type | None:
        """Find the skill class in a module"""
        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, type) and hasattr(obj, "metadata"):
                return obj
        return None

    def _validate_skill_interface(self, skill_instance: Any) -> bool:
        """Validate that skill implements required interface"""
        required_methods = ["initialize", "execute", "validate_input", "cleanup"]
        required_attrs = ["metadata"]

        for attr in required_attrs:
            if not hasattr(skill_instance, attr):
                return False

        for method in required_methods:
            if not hasattr(skill_instance, method) or not callable(getattr(skill_instance, method)):
                return False

        return True

    def _check_version_compatibility(self, installed_version: str, version_spec: str) -> bool:
        """Check if installed version satisfies version spec"""
        # Simple version checking (can be enhanced with semver library)
        if version_spec == "*":
            return True
        if version_spec.startswith(">="):
            required = version_spec[2:]
            return self._compare_versions(installed_version, required) >= 0
        if version_spec.startswith("=="):
            required = version_spec[2:]
            return installed_version == required
        return True

    def _compare_versions(self, v1: str, v2: str) -> int:
        """Compare two version strings. Returns -1, 0, or 1"""
        parts1 = [int(x) for x in v1.split(".")]
        parts2 = [int(x) for x in v2.split(".")]

        for p1, p2 in zip(parts1, parts2, strict=False):
            if p1 < p2:
                return -1
            if p1 > p2:
                return 1
        return 0

    def _record_error(self, skill_id: str, error_type: str, message: str) -> None:
        """Record a skill loading error"""
        error = SkillLoadError(
            skill_id=skill_id,
            error_type=error_type,
            message=message,
        )
        self.load_errors.append(error)

    def get_load_errors(self) -> list[SkillLoadError]:
        """Get all recorded load errors"""
        return list(self.load_errors)

    def clear_load_errors(self) -> None:
        """Clear load error history"""
        self.load_errors.clear()


# Global skill loader instance
_skill_loader: SkillLoader | None = None


def get_skill_loader() -> SkillLoader:
    """Get or create the global skill loader"""
    global _skill_loader
    if _skill_loader is None:
        _skill_loader = SkillLoader()
    return _skill_loader


__all__ = [
    "DependencyInfo",
    "SkillLoadError",
    "SkillLoader",
    "get_skill_loader",
]
