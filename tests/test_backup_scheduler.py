"""Unit tests for the automated backup scheduler (file-based backup/restore)."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from backend.app.core.backup_scheduler import (
    BackupConfig,
    BackupScheduler,
)


@pytest.fixture()
def tmp_data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory with sample files."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # Sample JSON files
    (data_dir / "workflows.json").write_text(
        json.dumps({"workflows": [{"id": "w1", "name": "test"}]}), encoding="utf-8"
    )
    (data_dir / "approvals.json").write_text(
        json.dumps({"approvals": []}), encoding="utf-8"
    )
    # Sample JSONL file
    (data_dir / "audit.jsonl").write_text(
        '{"event": "login", "ts": 1}\n{"event": "logout", "ts": 2}\n',
        encoding="utf-8",
    )
    return data_dir


@pytest.fixture()
def backup_dir(tmp_path: Path) -> Path:
    """Create a temporary backup directory."""
    bdir = tmp_path / "backups"
    bdir.mkdir()
    return bdir


@pytest.fixture()
def scheduler(tmp_data_dir: Path, backup_dir: Path, monkeypatch: pytest.MonkeyPatch) -> BackupScheduler:
    """Create a BackupScheduler configured for the temp directories."""
    # Patch _PROJECT_ROOT so file_store_dirs resolves to tmp_data_dir
    import backend.app.core.backup_scheduler as mod

    monkeypatch.setattr(mod, "_PROJECT_ROOT", tmp_data_dir.parent)

    config = BackupConfig(
        backup_dir=str(backup_dir),
        compress=True,
        pg_enabled=False,  # No pg in tests
        qdrant_enabled=False,
        file_store_dirs=["data"],
        file_patterns=["*.json", "*.jsonl"],
    )
    return BackupScheduler(config)


class TestFileBackup:
    """Tests for file-based backup."""

    @pytest.mark.asyncio()
    async def test_run_backup_creates_files(self, scheduler: BackupScheduler, backup_dir: Path) -> None:
        """Backup should create a timestamped directory with compressed files."""
        result = await scheduler.run_backup()

        assert result.success is True
        assert result.backup_id != ""
        assert result.total_size_bytes > 0

        # Check backup directory was created
        backup_subdir = backup_dir / result.backup_id
        assert backup_subdir.exists()

        # Check manifest exists
        manifest_file = backup_subdir / "manifest.json"
        assert manifest_file.exists()

        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        assert manifest["backup_id"] == result.backup_id
        assert manifest["success"] is True
        assert "checksums" in manifest
        assert len(manifest["checksums"]) > 0

    @pytest.mark.asyncio()
    async def test_backup_compresses_files(self, scheduler: BackupScheduler, backup_dir: Path) -> None:
        """Backup should gzip-compress files when compress=True."""
        result = await scheduler.run_backup()
        backup_subdir = backup_dir / result.backup_id

        # All data files should be .gz
        gz_files = list(backup_subdir.glob("*.gz"))
        assert len(gz_files) >= 3  # workflows.json.gz, approvals.json.gz, audit.jsonl.gz

        # Verify a compressed file is valid gzip
        for gz_file in gz_files:
            with gzip.open(gz_file, "rb") as f:
                content = f.read()
                assert len(content) > 0

    @pytest.mark.asyncio()
    async def test_backup_manifest_checksums(self, scheduler: BackupScheduler, backup_dir: Path) -> None:
        """Manifest should contain valid SHA-256 checksums."""
        result = await scheduler.run_backup()
        backup_subdir = backup_dir / result.backup_id
        manifest = json.loads((backup_subdir / "manifest.json").read_text(encoding="utf-8"))

        checksums = manifest["checksums"]
        assert len(checksums) > 0

        # Verify each checksum
        import hashlib

        for filename, expected_hash in checksums.items():
            filepath = backup_subdir / filename
            assert filepath.exists(), f"Missing file: {filename}"
            h = hashlib.sha256()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            assert h.hexdigest() == expected_hash


class TestVerifyBackup:
    """Tests for backup verification."""

    @pytest.mark.asyncio()
    async def test_verify_valid_backup(self, scheduler: BackupScheduler) -> None:
        """Verification should pass for a valid backup."""
        result = await scheduler.run_backup()
        assert await scheduler.verify_backup(result.backup_id) is True

    @pytest.mark.asyncio()
    async def test_verify_missing_backup(self, scheduler: BackupScheduler) -> None:
        """Verification should fail for non-existent backup."""
        assert await scheduler.verify_backup("nonexistent") is False

    @pytest.mark.asyncio()
    async def test_verify_corrupted_backup(
        self, scheduler: BackupScheduler, backup_dir: Path
    ) -> None:
        """Verification should fail if a file is corrupted."""
        result = await scheduler.run_backup()
        backup_subdir = backup_dir / result.backup_id

        # Corrupt a file
        gz_files = list(backup_subdir.glob("*.gz"))
        if gz_files:
            gz_files[0].write_bytes(b"corrupted data")

        assert await scheduler.verify_backup(result.backup_id) is False


class TestRestore:
    """Tests for backup restore."""

    @pytest.mark.asyncio()
    async def test_restore_files(
        self, scheduler: BackupScheduler, tmp_data_dir: Path, backup_dir: Path
    ) -> None:
        """Restore should copy files back to original locations."""
        # Run backup
        result = await scheduler.run_backup()

        # Modify original files
        (tmp_data_dir / "workflows.json").write_text('{"modified": true}', encoding="utf-8")

        # Restore
        success = await scheduler.restore(result.backup_id)
        assert success is True

        # Verify restored content
        restored = json.loads((tmp_data_dir / "workflows.json").read_text(encoding="utf-8"))
        assert "workflows" in restored

    @pytest.mark.asyncio()
    async def test_restore_nonexistent_backup(self, scheduler: BackupScheduler) -> None:
        """Restore should fail for non-existent backup."""
        assert await scheduler.restore("nonexistent") is False


class TestListAndCleanup:
    """Tests for listing and cleanup."""

    @pytest.mark.asyncio()
    async def test_list_backups(self, scheduler: BackupScheduler) -> None:
        """list_backups should return created backups."""
        await scheduler.run_backup()
        backups = scheduler.list_backups()
        assert len(backups) >= 1
        assert backups[0].backup_id != ""
        assert backups[0].success is True

    @pytest.mark.asyncio()
    async def test_cleanup_old(self, scheduler: BackupScheduler, backup_dir: Path) -> None:
        """cleanup_old should remove excess backups."""
        # Create multiple fake backup dirs
        for i in range(10):
            d = backup_dir / f"2026010{i}_000000"
            d.mkdir()
            (d / "manifest.json").write_text(
                json.dumps({"backup_id": f"2026010{i}_000000", "success": True}),
                encoding="utf-8",
            )

        removed = scheduler.cleanup_old(keep=3)
        assert removed == 7

        remaining = [d for d in backup_dir.iterdir() if d.is_dir()]
        assert len(remaining) == 3


class TestSchedulerStatus:
    """Tests for scheduler status reporting."""

    def test_status_initial(self, scheduler: BackupScheduler) -> None:
        """Status should reflect initial state."""
        st = scheduler.status
        assert st["running"] is False
        assert st["last_run"] is None
        assert st["last_success"] is None

    @pytest.mark.asyncio()
    async def test_status_after_backup(self, scheduler: BackupScheduler) -> None:
        """Status should update after a backup run."""
        await scheduler.run_backup()
        st = scheduler.status
        assert st["last_run"] is not None
        assert st["last_success"] is True
        assert st["last_backup_id"] != ""
