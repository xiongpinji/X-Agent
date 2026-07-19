"""Plugin Update Management System

Provides:
- Version checking
- Update downloading
- Rollback capability
- Update scheduling
- Changelog management
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class UpdateStatus(StrEnum):
    """Update status"""
    AVAILABLE = "available"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    INSTALLING = "installing"
    INSTALLED = "installed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class UpdatePriority(StrEnum):
    """Update priority level"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PluginVersion(BaseModel):
    """Plugin version information"""
    version: str
    release_date: datetime
    changelog: str
    download_url: str
    file_hash: str
    file_size: int
    priority: UpdatePriority = UpdatePriority.MEDIUM
    breaking_changes: bool = False
    deprecated_features: list[str] = Field(default_factory=list)
    new_features: list[str] = Field(default_factory=list)
    bug_fixes: list[str] = Field(default_factory=list)


class UpdateRecord(BaseModel):
    """Update record"""
    update_id: str = Field(default_factory=lambda: str(uuid4()))
    plugin_id: str
    from_version: str
    to_version: str
    status: UpdateStatus = UpdateStatus.AVAILABLE
    priority: UpdatePriority = UpdatePriority.MEDIUM
    download_url: str
    file_hash: str
    file_size: int
    changelog: str
    download_progress: int = 0
    installation_progress: int = 0
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    backup_path: Optional[Path] = None


class VersionComparator:
    """Compare semantic versions"""

    @staticmethod
    def parse_version(version: str) -> tuple[int, ...]:
        """Parse semantic version"""
        try:
            return tuple(map(int, version.split(".")))
        except (ValueError, AttributeError):
            return (0, 0, 0)

    @staticmethod
    def is_newer(new_version: str, current_version: str) -> bool:
        """Check if new version is newer"""
        new = VersionComparator.parse_version(new_version)
        current = VersionComparator.parse_version(current_version)
        return new > current

    @staticmethod
    def is_compatible(new_version: str, current_version: str) -> bool:
        """Check if versions are compatible (same major version)"""
        new = VersionComparator.parse_version(new_version)
        current = VersionComparator.parse_version(current_version)
        return new[0] == current[0]  # Same major version


class PluginVersionRegistry:
    """Registry of available plugin versions"""

    def __init__(self, storage_path: Optional[str | Path] = None):
        self.storage_path = Path(storage_path) if storage_path else Path("./plugin_versions")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._versions: dict[str, list[PluginVersion]] = {}
        self._load_versions()

    def _load_versions(self) -> None:
        """Load versions from storage"""
        versions_file = self.storage_path / "versions.json"
        if versions_file.exists():
            try:
                with open(versions_file) as f:
                    data = json.load(f)
                    for plugin_id, versions in data.items():
                        self._versions[plugin_id] = [
                            PluginVersion(**v) for v in versions
                        ]
                logger.info(f"Loaded versions for {len(self._versions)} plugins")
            except Exception as e:
                logger.error(f"Failed to load versions: {e}")

    def _save_versions(self) -> None:
        """Save versions to storage"""
        versions_file = self.storage_path / "versions.json"
        try:
            with open(versions_file, "w") as f:
                data = {
                    plugin_id: [json.loads(v.model_dump_json(default=str)) for v in versions]
                    for plugin_id, versions in self._versions.items()
                }
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save versions: {e}")

    def register_version(self, plugin_id: str, version: PluginVersion) -> None:
        """Register new version"""
        if plugin_id not in self._versions:
            self._versions[plugin_id] = []

        # Remove if already exists
        self._versions[plugin_id] = [
            v for v in self._versions[plugin_id] if v.version != version.version
        ]

        self._versions[plugin_id].append(version)
        self._versions[plugin_id].sort(
            key=lambda v: VersionComparator.parse_version(v.version),
            reverse=True
        )
        self._save_versions()
        logger.info(f"Version registered: {plugin_id} v{version.version}")

    def get_latest_version(self, plugin_id: str) -> Optional[PluginVersion]:
        """Get latest version"""
        versions = self._versions.get(plugin_id, [])
        return versions[0] if versions else None

    def get_version(self, plugin_id: str, version: str) -> Optional[PluginVersion]:
        """Get specific version"""
        versions = self._versions.get(plugin_id, [])
        for v in versions:
            if v.version == version:
                return v
        return None

    def list_versions(self, plugin_id: str) -> list[PluginVersion]:
        """List all versions"""
        return self._versions.get(plugin_id, []).copy()

    def get_available_updates(
        self,
        plugin_id: str,
        current_version: str
    ) -> list[PluginVersion]:
        """Get available updates"""
        versions = self._versions.get(plugin_id, [])
        return [
            v for v in versions
            if VersionComparator.is_newer(v.version, current_version)
        ]


class PluginUpdateManager:
    """Manage plugin updates"""

    def __init__(self, storage_path: Optional[str | Path] = None):
        self.storage_path = Path(storage_path) if storage_path else Path("./plugin_updates")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.version_registry = PluginVersionRegistry(self.storage_path / "versions")
        self._updates: dict[str, UpdateRecord] = {}
        self._backups: dict[str, list[Path]] = {}
        self._load_updates()

    def _load_updates(self) -> None:
        """Load updates from storage"""
        updates_file = self.storage_path / "updates.json"
        if updates_file.exists():
            try:
                with open(updates_file) as f:
                    data = json.load(f)
                    for update_data in data.get("updates", []):
                        update = UpdateRecord(**update_data)
                        self._updates[update.update_id] = update
                logger.info(f"Loaded {len(self._updates)} updates")
            except Exception as e:
                logger.error(f"Failed to load updates: {e}")

    def _save_updates(self) -> None:
        """Save updates to storage"""
        updates_file = self.storage_path / "updates.json"
        try:
            with open(updates_file, "w") as f:
                data = {
                    "updates": [
                        json.loads(u.model_dump_json(default=str))
                        for u in self._updates.values()
                    ]
                }
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save updates: {e}")

    def check_updates(self, plugin_id: str, current_version: str) -> list[PluginVersion]:
        """Check for available updates"""
        return self.version_registry.get_available_updates(plugin_id, current_version)

    def create_update(
        self,
        plugin_id: str,
        from_version: str,
        to_version: str,
        download_url: str,
        file_hash: str,
        file_size: int,
        changelog: str,
        priority: UpdatePriority = UpdatePriority.MEDIUM
    ) -> UpdateRecord:
        """Create update record"""
        update = UpdateRecord(
            plugin_id=plugin_id,
            from_version=from_version,
            to_version=to_version,
            status=UpdateStatus.AVAILABLE,
            priority=priority,
            download_url=download_url,
            file_hash=file_hash,
            file_size=file_size,
            changelog=changelog
        )

        self._updates[update.update_id] = update
        self._save_updates()

        logger.info(f"Update created: {plugin_id} {from_version} -> {to_version}")
        return update

    def start_update(self, update_id: str) -> Optional[UpdateRecord]:
        """Start update process"""
        update = self._updates.get(update_id)
        if not update:
            return None

        update.status = UpdateStatus.DOWNLOADING
        update.started_at = datetime.now(UTC)
        self._save_updates()

        logger.info(f"Update started: {update_id}")
        return update

    def update_download_progress(self, update_id: str, progress: int) -> None:
        """Update download progress"""
        update = self._updates.get(update_id)
        if update:
            update.download_progress = min(100, max(0, progress))
            self._save_updates()

    def update_installation_progress(self, update_id: str, progress: int) -> None:
        """Update installation progress"""
        update = self._updates.get(update_id)
        if update:
            update.installation_progress = min(100, max(0, progress))
            self._save_updates()

    def complete_update(self, update_id: str) -> Optional[UpdateRecord]:
        """Mark update as completed"""
        update = self._updates.get(update_id)
        if not update:
            return None

        update.status = UpdateStatus.INSTALLED
        update.completed_at = datetime.now(UTC)
        self._save_updates()

        logger.info(f"Update completed: {update_id}")
        return update

    def fail_update(self, update_id: str, error_message: str) -> Optional[UpdateRecord]:
        """Mark update as failed"""
        update = self._updates.get(update_id)
        if not update:
            return None

        update.status = UpdateStatus.FAILED
        update.error_message = error_message
        update.completed_at = datetime.now(UTC)
        self._save_updates()

        logger.error(f"Update failed: {update_id} - {error_message}")
        return update

    def create_backup(
        self,
        plugin_id: str,
        plugin_path: Path
    ) -> Optional[Path]:
        """Create backup of plugin before update"""
        try:
            backup_dir = self.storage_path / "backups" / plugin_id
            backup_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"backup_{timestamp}"

            shutil.copytree(plugin_path, backup_path)

            if plugin_id not in self._backups:
                self._backups[plugin_id] = []
            self._backups[plugin_id].append(backup_path)

            logger.info(f"Backup created: {backup_path}")
            return backup_path

        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return None

    def rollback_update(
        self,
        plugin_id: str,
        plugin_path: Path,
        backup_path: Path
    ) -> bool:
        """Rollback plugin to previous version"""
        try:
            # Remove current version
            if plugin_path.exists():
                shutil.rmtree(plugin_path)

            # Restore from backup
            shutil.copytree(backup_path, plugin_path)

            logger.info(f"Rollback completed: {plugin_id}")
            return True

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False

    def cleanup_old_backups(self, plugin_id: str, keep_count: int = 3) -> None:
        """Clean up old backups"""
        backups = self._backups.get(plugin_id, [])
        if len(backups) > keep_count:
            # Sort by modification time
            backups.sort(key=lambda p: p.stat().st_mtime)

            # Remove oldest
            for backup in backups[:-keep_count]:
                try:
                    shutil.rmtree(backup)
                    logger.info(f"Backup removed: {backup}")
                except Exception as e:
                    logger.warning(f"Failed to remove backup: {e}")

            self._backups[plugin_id] = backups[-keep_count:]

    def get_update(self, update_id: str) -> Optional[UpdateRecord]:
        """Get update record"""
        return self._updates.get(update_id)

    def list_updates(
        self,
        plugin_id: Optional[str] = None,
        status: Optional[UpdateStatus] = None
    ) -> list[UpdateRecord]:
        """List updates"""
        updates = list(self._updates.values())

        if plugin_id:
            updates = [u for u in updates if u.plugin_id == plugin_id]

        if status:
            updates = [u for u in updates if u.status == status]

        return sorted(updates, key=lambda u: u.created_at, reverse=True)

    def verify_file_integrity(self, file_path: Path, expected_hash: str) -> bool:
        """Verify file integrity using hash"""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)

            file_hash = sha256_hash.hexdigest()
            return file_hash == expected_hash

        except Exception as e:
            logger.error(f"Failed to verify file integrity: {e}")
            return False


# Global instance
update_manager = PluginUpdateManager()
