"""Skill Marketplace - Marketplace for discovering, installing, and managing skills"""

from __future__ import annotations

import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any
from pathlib import Path
import json

from .skills_core import SkillMetadata, SkillCapability
from .skills_registry import get_skill_registry

logger = logging.getLogger(__name__)


@dataclass
class SkillPackage:
    """A packaged skill ready for distribution"""
    skill_id: str
    name: str
    version: str
    description: str
    author: str
    license: str
    file_path: str
    file_size_bytes: int
    checksum: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class SkillInstallation:
    """Record of a skill installation"""
    skill_id: str
    version: str
    installed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    installed_by: str = ""
    install_path: str = ""
    enabled: bool = True


class SkillMarketplace:
    """Marketplace for discovering and managing skills"""

    def __init__(self, marketplace_path: str | None = None):
        self.marketplace_path = Path(marketplace_path or "./skills_marketplace")
        self.marketplace_path.mkdir(parents=True, exist_ok=True)

        self.registry = get_skill_registry()
        self.packages: dict[str, SkillPackage] = {}
        self.installations: dict[str, SkillInstallation] = {}
        self._lock = asyncio.Lock()

        # Create subdirectories
        (self.marketplace_path / "packages").mkdir(exist_ok=True)
        (self.marketplace_path / "installed").mkdir(exist_ok=True)
        (self.marketplace_path / "metadata").mkdir(exist_ok=True)

    async def publish_skill(
        self,
        metadata: SkillMetadata,
        skill_file_path: str,
        author: str = "",
    ) -> tuple[bool, str | None]:
        """Publish a skill to the marketplace"""
        async with self._lock:
            try:
                skill_id = metadata.skill_id
                file_path = Path(skill_file_path)

                if not file_path.exists():
                    return False, f"Skill file not found: {skill_file_path}"

                # Calculate checksum
                import hashlib
                with open(file_path, "rb") as f:
                    checksum = hashlib.sha256(f.read()).hexdigest()

                # Create package
                package = SkillPackage(
                    skill_id=skill_id,
                    name=metadata.name,
                    version=metadata.version,
                    description=metadata.description,
                    author=author or metadata.author,
                    license=metadata.license,
                    file_path=str(file_path),
                    file_size_bytes=file_path.stat().st_size,
                    checksum=checksum,
                )

                # Store package
                self.packages[skill_id] = package

                # Save metadata
                metadata_file = self.marketplace_path / "metadata" / f"{skill_id}.json"
                with open(metadata_file, "w") as f:
                    json.dump(metadata.to_dict(), f, indent=2, default=str)

                # Register in registry
                await self.registry.register_skill(metadata)

                logger.info(f"Published skill: {metadata.name} ({skill_id})")
                return True, None

            except Exception as e:
                error = f"Error publishing skill: {str(e)}"
                logger.error(error, exc_info=True)
                return False, error

    async def unpublish_skill(self, skill_id: str) -> tuple[bool, str | None]:
        """Unpublish a skill from the marketplace"""
        async with self._lock:
            try:
                if skill_id not in self.packages:
                    return False, f"Skill not found: {skill_id}"

                # Remove from registry
                await self.registry.unregister_skill(skill_id)

                # Remove package
                del self.packages[skill_id]

                # Remove metadata file
                metadata_file = self.marketplace_path / "metadata" / f"{skill_id}.json"
                if metadata_file.exists():
                    metadata_file.unlink()

                logger.info(f"Unpublished skill: {skill_id}")
                return True, None

            except Exception as e:
                error = f"Error unpublishing skill: {str(e)}"
                logger.error(error, exc_info=True)
                return False, error

    async def install_skill(
        self,
        skill_id: str,
        install_path: str | None = None,
        user_id: str = "",
    ) -> tuple[bool, str | None]:
        """Install a skill from the marketplace"""
        async with self._lock:
            try:
                if skill_id not in self.packages:
                    return False, f"Skill not found in marketplace: {skill_id}"

                package = self.packages[skill_id]
                install_dir = Path(install_path or self.marketplace_path / "installed" / skill_id)
                install_dir.mkdir(parents=True, exist_ok=True)

                # Copy skill file
                import shutil
                dest_file = install_dir / Path(package.file_path).name
                shutil.copy2(package.file_path, dest_file)

                # Record installation
                installation = SkillInstallation(
                    skill_id=skill_id,
                    version=package.version,
                    installed_by=user_id,
                    install_path=str(install_dir),
                )
                self.installations[skill_id] = installation

                logger.info(f"Installed skill: {package.name} ({skill_id})")
                return True, None

            except Exception as e:
                error = f"Error installing skill: {str(e)}"
                logger.error(error, exc_info=True)
                return False, error

    async def uninstall_skill(self, skill_id: str) -> tuple[bool, str | None]:
        """Uninstall a skill"""
        async with self._lock:
            try:
                if skill_id not in self.installations:
                    return False, f"Skill not installed: {skill_id}"

                installation = self.installations[skill_id]

                # Remove installation directory
                import shutil
                install_path = Path(installation.install_path)
                if install_path.exists():
                    shutil.rmtree(install_path)

                # Remove installation record
                del self.installations[skill_id]

                logger.info(f"Uninstalled skill: {skill_id}")
                return True, None

            except Exception as e:
                error = f"Error uninstalling skill: {str(e)}"
                logger.error(error, exc_info=True)
                return False, error

    async def upgrade_skill(
        self,
        skill_id: str,
        new_version: str,
    ) -> tuple[bool, str | None]:
        """Upgrade a skill to a new version"""
        # Uninstall old version
        success, error = await self.uninstall_skill(skill_id)
        if not success:
            return False, error

        # Install new version
        return await self.install_skill(skill_id)

    def get_package(self, skill_id: str) -> SkillPackage | None:
        """Get package information"""
        return self.packages.get(skill_id)

    def get_installation(self, skill_id: str) -> SkillInstallation | None:
        """Get installation information"""
        return self.installations.get(skill_id)

    def list_packages(self) -> list[SkillPackage]:
        """List all available packages"""
        return list(self.packages.values())

    def list_installations(self) -> list[SkillInstallation]:
        """List all installed skills"""
        return list(self.installations.values())

    def is_installed(self, skill_id: str) -> bool:
        """Check if a skill is installed"""
        return skill_id in self.installations

    async def check_updates(self) -> list[tuple[str, str, str]]:
        """Check for available updates (skill_id, current_version, new_version)"""
        updates = []

        for skill_id, installation in self.installations.items():
            if skill_id in self.packages:
                package = self.packages[skill_id]
                if self._compare_versions(package.version, installation.version) > 0:
                    updates.append((skill_id, installation.version, package.version))

        return updates

    def _compare_versions(self, v1: str, v2: str) -> int:
        """Compare two version strings. Returns -1, 0, or 1"""
        try:
            parts1 = [int(x) for x in v1.split(".")]
            parts2 = [int(x) for x in v2.split(".")]

            for p1, p2 in zip(parts1, parts2):
                if p1 < p2:
                    return -1
                if p1 > p2:
                    return 1
            return 0
        except Exception:
            return 0

    def get_marketplace_stats(self) -> dict[str, Any]:
        """Get marketplace statistics"""
        return {
            "total_packages": len(self.packages),
            "total_installed": len(self.installations),
            "total_size_mb": sum(p.file_size_bytes for p in self.packages.values()) / (1024 * 1024),
        }


# Global marketplace instance
_skill_marketplace: SkillMarketplace | None = None


def get_skill_marketplace(marketplace_path: str | None = None) -> SkillMarketplace:
    """Get or create the global skill marketplace"""
    global _skill_marketplace
    if _skill_marketplace is None:
        _skill_marketplace = SkillMarketplace(marketplace_path)
    return _skill_marketplace


__all__ = [
    "SkillMarketplace",
    "SkillPackage",
    "SkillInstallation",
    "get_skill_marketplace",
]
