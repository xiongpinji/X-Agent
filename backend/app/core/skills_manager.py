"""Skill System Manager - Unified interface for all skill operations

.. deprecated:: P1-11（2026-07-20）
   LEGACY 管理平面。X-Agent 唯一技能运行时为 ``backend.app.core.skills``
   （目录扫描加载 skills/ 与 custom-skills/，经 ``skill_agent_adapter`` 注入 AgentLoop）。
   本扁平栈（skills_core/loader/registry/executor/sandbox/marketplace）仅保留
   以兼容既有测试与 skills_api.py，不再作为技能运行时入口，待后续版本移除或重定向。
   详见 SKILLS_SYSTEM_README.md。
"""

from __future__ import annotations

import logging
from typing import Any

from .skills_core import (
    SkillCapability,
    SkillExecutionResult,
    SkillMetadata,
)
from .skills_executor import get_skill_executor
from .skills_loader import get_skill_loader
from .skills_marketplace import get_skill_marketplace
from .skills_registry import get_skill_registry
from .skills_sandbox import ResourceLimits, get_sandbox_manager

logger = logging.getLogger(__name__)


class SkillSystemManager:
    """Unified interface for all skill system operations"""

    def __init__(self):
        self.loader = get_skill_loader()
        self.registry = get_skill_registry()
        self.executor = get_skill_executor()
        self.marketplace = get_skill_marketplace()
        self.sandbox_manager = get_sandbox_manager()

    # Discovery Operations

    async def discover_skills(
        self,
        capability: SkillCapability | None = None,
        tag: str | None = None,
    ) -> list[SkillMetadata]:
        """Discover skills by capability or tag"""
        if capability:
            return self.registry.find_by_capability(capability)
        if tag:
            return self.registry.find_by_tag(tag)
        return self.registry.list_skills()

    async def search_skills(self, query: str, limit: int = 20) -> list[Any]:
        """Search for skills"""
        return self.registry.search_skills(query, limit)

    async def get_skill_info(self, skill_id: str) -> dict[str, Any] | None:
        """Get detailed skill information"""
        metadata = self.registry.get_skill(skill_id)
        if not metadata:
            return None

        rating = self.registry.get_skill_rating(skill_id)
        installation = self.marketplace.get_installation(skill_id)
        package = self.marketplace.get_package(skill_id)

        return {
            "metadata": metadata.to_dict(),
            "rating": {
                "average": rating.average_rating if rating else 0.0,
                "total_ratings": rating.total_ratings if rating else 0,
                "download_count": rating.download_count if rating else 0,
            } if rating else None,
            "installation": {
                "installed": True,
                "version": installation.version,
                "installed_at": installation.installed_at.isoformat(),
                "install_path": installation.install_path,
            } if installation else {"installed": False},
            "package": {
                "file_size_mb": package.file_size_bytes / (1024 * 1024),
                "checksum": package.checksum,
            } if package else None,
        }

    # Installation Operations

    async def install_skill(
        self,
        skill_id: str,
        user_id: str = "",
    ) -> tuple[bool, str | None]:
        """Install a skill"""
        return await self.marketplace.install_skill(skill_id, user_id=user_id)

    async def uninstall_skill(self, skill_id: str) -> tuple[bool, str | None]:
        """Uninstall a skill"""
        return await self.marketplace.uninstall_skill(skill_id)

    async def upgrade_skill(
        self,
        skill_id: str,
        new_version: str,
    ) -> tuple[bool, str | None]:
        """Upgrade a skill"""
        return await self.marketplace.upgrade_skill(skill_id, new_version)

    async def list_installed_skills(self) -> list[dict[str, Any]]:
        """List all installed skills"""
        installations = self.marketplace.list_installations()
        result = []

        for installation in installations:
            metadata = self.registry.get_skill(installation.skill_id)
            if metadata:
                result.append({
                    "skill_id": installation.skill_id,
                    "name": metadata.name,
                    "version": installation.version,
                    "installed_at": installation.installed_at.isoformat(),
                    "enabled": installation.enabled,
                })

        return result

    # Execution Operations

    async def execute_skill(
        self,
        skill_name: str,
        input_data: dict[str, Any],
        user_id: str = "",
        tenant_id: str = "",
        sandbox_id: str | None = None,
    ) -> SkillExecutionResult:
        """Execute a skill"""
        return await self.executor.execute_skill(
            skill_name=skill_name,
            input_data=input_data,
            user_id=user_id,
            tenant_id=tenant_id,
            sandbox_id=sandbox_id,
        )

    async def execute_skill_batch(
        self,
        skill_name: str,
        batch_inputs: list[dict[str, Any]],
        user_id: str = "",
        tenant_id: str = "",
    ) -> list[SkillExecutionResult]:
        """Execute a skill multiple times"""
        return await self.executor.execute_skill_batch(
            skill_name=skill_name,
            batch_inputs=batch_inputs,
            user_id=user_id,
            tenant_id=tenant_id,
        )

    # Sandbox Operations

    async def create_sandbox(
        self,
        sandbox_id: str,
        timeout_seconds: int = 300,
        max_memory_mb: int = 512,
        max_cpu_percent: float = 50.0,
    ) -> tuple[bool, str | None]:
        """Create a sandbox for skill execution"""
        limits = ResourceLimits(
            timeout_seconds=timeout_seconds,
            max_memory_mb=max_memory_mb,
            max_cpu_percent=max_cpu_percent,
        )
        return await self.sandbox_manager.create_sandbox(sandbox_id, limits)

    async def destroy_sandbox(self, sandbox_id: str) -> tuple[bool, str | None]:
        """Destroy a sandbox"""
        return await self.sandbox_manager.destroy_sandbox(sandbox_id)

    # Skill Loading Operations

    async def load_skill(
        self,
        skill_module_path: str,
        skill_name: str,
    ) -> tuple[bool, str | None]:
        """Load a skill from a module"""
        return await self.loader.load_skill(skill_module_path, skill_name)

    async def unload_skill(self, skill_name: str) -> tuple[bool, str | None]:
        """Unload a skill"""
        return await self.loader.unload_skill(skill_name)

    async def reload_skill(
        self,
        skill_name: str,
        skill_module_path: str,
    ) -> tuple[bool, str | None]:
        """Reload a skill (hot reload)"""
        return await self.loader.reload_skill(skill_name, skill_module_path)

    def list_loaded_skills(self) -> list[str]:
        """List all loaded skills"""
        return self.loader.list_loaded_skills()

    # Rating and Feedback

    async def rate_skill(self, skill_id: str, rating: float) -> tuple[bool, str | None]:
        """Rate a skill"""
        return await self.registry.rate_skill(skill_id, rating)

    # Statistics and Monitoring

    def get_marketplace_stats(self) -> dict[str, Any]:
        """Get marketplace statistics"""
        return self.marketplace.get_marketplace_stats()

    def get_registry_stats(self) -> dict[str, Any]:
        """Get registry statistics"""
        return self.registry.get_statistics()

    def get_top_skills(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get top-rated skills"""
        results = []
        for metadata, rating in self.registry.get_top_skills(limit):
            results.append({
                "name": metadata.name,
                "version": metadata.version,
                "rating": rating.average_rating,
                "downloads": rating.download_count,
            })
        return results

    def get_trending_skills(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get trending skills"""
        results = []
        for metadata, rating in self.registry.get_trending_skills(limit):
            results.append({
                "name": metadata.name,
                "version": metadata.version,
                "downloads": rating.download_count,
            })
        return results

    # Audit and Logging

    def get_execution_logs(
        self,
        skill_id: str | None = None,
        user_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get execution audit logs"""
        logs = self.executor.get_audit_logs(skill_id, user_id, limit)
        return [
            {
                "execution_id": log.execution_id,
                "skill_id": log.skill_id,
                "user_id": log.user_id,
                "status": log.status,
                "start_time": log.start_time.isoformat(),
                "end_time": log.end_time.isoformat() if log.end_time else None,
                "duration_ms": log.duration_ms,
                "error": log.error,
            }
            for log in logs
        ]

    # System Health

    async def get_system_health(self) -> dict[str, Any]:
        """Get skill system health status"""
        return {
            "loaded_skills": len(self.loader.list_loaded_skills()),
            "registered_skills": len(self.registry.list_skills()),
            "installed_skills": len(self.marketplace.list_installations()),
            "active_sandboxes": len(self.sandbox_manager.list_sandboxes()),
            "load_errors": len(self.loader.get_load_errors()),
            "marketplace_stats": self.marketplace.get_marketplace_stats(),
            "registry_stats": self.registry.get_statistics(),
        }


# Global manager instance
_skill_system_manager: SkillSystemManager | None = None


def get_skill_system_manager() -> SkillSystemManager:
    """Get or create the global skill system manager"""
    global _skill_system_manager
    if _skill_system_manager is None:
        _skill_system_manager = SkillSystemManager()
    return _skill_system_manager


__all__ = [
    "SkillSystemManager",
    "get_skill_system_manager",
]
