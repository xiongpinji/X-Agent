"""Automated Backup Scheduler — periodic backups of all data stores.

Supports:
- PostgreSQL: pg_dump (if available) or SQL export
- File stores: copy data/*.json, data/*.jsonl to timestamped backup dir
- Qdrant: trigger snapshot (if enabled)
- Audit logs: rotate and archive

Environment variables (prefix XAGENT_):
    XAGENT_BACKUP_ENABLED       – master switch (default: false)
    XAGENT_BACKUP_DIR           – backup target directory (default: data/backups)
    XAGENT_BACKUP_SCHEDULE      – cron expression (default: "0 2 * * *")
    XAGENT_BACKUP_RETENTION_DAYS – days to keep backups (default: 30)
"""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import logging
import shutil
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Project root (two levels up from backend/app/core/)
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


# ─── Data Models ────────────────────────────────────────────────────────────────


@dataclass
class BackupConfig:
    """Configuration for the automated backup scheduler."""

    backup_dir: str = "data/backups"
    schedule_cron: str = "0 2 * * *"  # 2 AM daily
    retention_days: int = 30
    keep_latest: int = 7
    compress: bool = True
    # PostgreSQL
    pg_enabled: bool = True
    pg_dsn: str = ""  # empty → skip pg backup
    # Qdrant
    qdrant_enabled: bool = False
    qdrant_url: str = "http://localhost:6333"
    # File stores
    file_store_dirs: list[str] = field(default_factory=lambda: ["data"])
    file_patterns: list[str] = field(
        default_factory=lambda: ["*.json", "*.jsonl"]
    )


@dataclass
class ComponentResult:
    """Result of backing up a single component."""

    component: str
    success: bool
    files: list[str] = field(default_factory=list)
    size_bytes: int = 0
    duration_seconds: float = 0.0
    error: str | None = None


@dataclass
class BackupResult:
    """Result of a full backup run."""

    backup_id: str
    success: bool
    started_at: str
    completed_at: str | None = None
    components: list[ComponentResult] = field(default_factory=list)
    total_size_bytes: int = 0
    manifest_path: str | None = None


@dataclass
class BackupInfo:
    """Summary info about an existing backup."""

    backup_id: str
    created_at: str
    success: bool
    total_size_bytes: int
    components: list[str]
    path: str


# ─── Scheduler ──────────────────────────────────────────────────────────────────


class BackupScheduler:
    """Automated backup scheduler for all X-Agent data stores."""

    def __init__(self, config: BackupConfig | None = None) -> None:
        self.config = config or BackupConfig()
        self._backup_dir = Path(self.config.backup_dir)
        if not self._backup_dir.is_absolute():
            self._backup_dir = _PROJECT_ROOT / self._backup_dir
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._last_run: datetime | None = None
        self._last_result: BackupResult | None = None

    # ─── Public API ─────────────────────────────────────────────────────────

    async def run_backup(self) -> BackupResult:
        """Execute a full backup of all stores."""
        backup_id = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        started_at = datetime.now(UTC).isoformat()
        target_dir = self._backup_dir / backup_id
        target_dir.mkdir(parents=True, exist_ok=True)

        results: list[ComponentResult] = []

        # 1. PostgreSQL backup
        if self.config.pg_enabled and self.config.pg_dsn:
            results.append(await self._backup_postgres(backup_id, target_dir))

        # 2. File stores backup
        results.append(await self._backup_file_stores(target_dir))

        # 3. Qdrant snapshot (if enabled)
        if self.config.qdrant_enabled:
            results.append(await self._backup_qdrant(target_dir))

        # 4. Audit log rotation
        results.append(await self._rotate_audit_logs(target_dir))

        all_ok = all(r.success for r in results)
        total_size = sum(r.size_bytes for r in results)

        # Write manifest
        manifest_path = self._write_manifest(backup_id, target_dir, results)

        result = BackupResult(
            backup_id=backup_id,
            success=all_ok,
            started_at=started_at,
            completed_at=datetime.now(UTC).isoformat(),
            components=results,
            total_size_bytes=total_size,
            manifest_path=str(manifest_path) if manifest_path else None,
        )

        self._last_run = datetime.now(UTC)
        self._last_result = result

        # Cleanup old backups
        self.cleanup_old(keep=self.config.keep_latest)

        logger.info(
            "Backup %s completed: success=%s, size=%d bytes",
            backup_id, all_ok, total_size,
        )
        return result

    async def verify_backup(self, backup_id: str) -> bool:
        """Verify a backup is restorable (integrity check via checksums)."""
        backup_dir = self._backup_dir / backup_id
        manifest_file = backup_dir / "manifest.json"
        if not manifest_file.exists():
            logger.warning("Manifest not found for backup %s", backup_id)
            return False

        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            checksums: dict[str, str] = manifest.get("checksums", {})

            for filename, expected_hash in checksums.items():
                filepath = backup_dir / filename
                if not filepath.exists():
                    logger.error("Missing file in backup %s: %s", backup_id, filename)
                    return False
                actual_hash = self._sha256_file(filepath)
                if actual_hash != expected_hash:
                    logger.error(
                        "Checksum mismatch for %s in backup %s", filename, backup_id
                    )
                    return False
            return True
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to verify backup %s: %s", backup_id, exc)
            return False

    def list_backups(self) -> list[BackupInfo]:
        """List available backups, newest first."""
        backups: list[BackupInfo] = []
        if not self._backup_dir.exists():
            return backups

        for entry in sorted(self._backup_dir.iterdir(), reverse=True):
            manifest_file = entry / "manifest.json"
            if not entry.is_dir() or not manifest_file.exists():
                continue
            try:
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                backups.append(
                    BackupInfo(
                        backup_id=manifest.get("backup_id", entry.name),
                        created_at=manifest.get("created_at", ""),
                        success=manifest.get("success", False),
                        total_size_bytes=manifest.get("total_size_bytes", 0),
                        components=manifest.get("components", []),
                        path=str(entry),
                    )
                )
            except (json.JSONDecodeError, OSError):
                continue
        return backups

    async def restore(self, backup_id: str) -> bool:
        """Restore file-based stores from a backup.

        Copies backed-up files back to their original locations.
        """
        backup_dir = self._backup_dir / backup_id
        manifest_file = backup_dir / "manifest.json"
        if not manifest_file.exists():
            logger.error("Cannot restore: manifest not found for %s", backup_id)
            return False

        # Verify integrity first
        if not await self.verify_backup(backup_id):
            logger.error("Cannot restore: integrity check failed for %s", backup_id)
            return False

        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            file_map: dict[str, str] = manifest.get("file_map", {})

            for backup_filename, original_path_str in file_map.items():
                src = backup_dir / backup_filename
                if not src.exists():
                    continue
                dest = Path(original_path_str)
                if not dest.is_absolute():
                    dest = _PROJECT_ROOT / dest

                # Decompress if gzipped
                if backup_filename.endswith(".gz"):
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with gzip.open(src, "rb") as f_in:
                        dest.write_bytes(f_in.read())
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)

            logger.info("Restore from backup %s completed", backup_id)
            return True
        except OSError as exc:
            logger.error("Restore failed for %s: %s", backup_id, exc)
            return False

    def cleanup_old(self, keep: int = 7) -> int:
        """Remove old backups, keeping N most recent. Returns count removed."""
        if not self._backup_dir.exists():
            return 0

        dirs = sorted(
            [d for d in self._backup_dir.iterdir() if d.is_dir() and (d / "manifest.json").exists()],
            reverse=True,
        )
        removed = 0
        for old_dir in dirs[keep:]:
            try:
                shutil.rmtree(old_dir)
                removed += 1
                logger.info("Removed old backup: %s", old_dir.name)
            except OSError as exc:
                logger.warning("Failed to remove old backup %s: %s", old_dir.name, exc)
        return removed

    # ─── Scheduler Loop ─────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background scheduler loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.ensure_future(self._scheduler_loop())
        logger.info("Backup scheduler started (cron: %s)", self.config.schedule_cron)

    def stop(self) -> None:
        """Stop the background scheduler loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("Backup scheduler stopped")

    @property
    def status(self) -> dict[str, Any]:
        """Current scheduler status."""
        return {
            "running": self._running,
            "schedule_cron": self.config.schedule_cron,
            "backup_dir": str(self._backup_dir),
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "last_success": self._last_result.success if self._last_result else None,
            "last_backup_id": self._last_result.backup_id if self._last_result else None,
            "retention_days": self.config.retention_days,
            "keep_latest": self.config.keep_latest,
        }

    async def _scheduler_loop(self) -> None:
        """Simple interval-based scheduler (checks every 60s)."""
        interval_seconds = self._cron_to_interval(self.config.schedule_cron)
        while self._running:
            try:
                await asyncio.sleep(interval_seconds)
                if self._running:
                    await self.run_backup()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Backup scheduler loop error")
                await asyncio.sleep(60)

    # ─── Private: Component Backups ─────────────────────────────────────────

    async def _backup_postgres(self, backup_id: str, target_dir: Path) -> ComponentResult:
        """Backup PostgreSQL via pg_dump."""
        start = time.monotonic()
        dump_file = target_dir / f"postgres_{backup_id}.sql.gz"
        try:
            # Check if pg_dump is available
            pg_dump = shutil.which("pg_dump")
            if not pg_dump:
                return ComponentResult(
                    component="postgresql",
                    success=False,
                    error="pg_dump not found in PATH",
                    duration_seconds=time.monotonic() - start,
                )

            proc = await asyncio.create_subprocess_exec(
                pg_dump,
                "--dbname", self.config.pg_dsn,
                "--format", "plain",
                "--no-owner",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                return ComponentResult(
                    component="postgresql",
                    success=False,
                    error=stderr.decode(errors="replace")[:500],
                    duration_seconds=time.monotonic() - start,
                )

            # Compress
            with gzip.open(dump_file, "wb", compresslevel=6) as f:
                f.write(stdout)

            return ComponentResult(
                component="postgresql",
                success=True,
                files=[dump_file.name],
                size_bytes=dump_file.stat().st_size,
                duration_seconds=time.monotonic() - start,
            )
        except Exception as exc:
            return ComponentResult(
                component="postgresql",
                success=False,
                error=str(exc),
                duration_seconds=time.monotonic() - start,
            )

    async def _backup_file_stores(self, target_dir: Path) -> ComponentResult:
        """Backup file-based stores (data/*.json, data/*.jsonl)."""
        start = time.monotonic()
        backed_up: list[str] = []
        total_size = 0
        errors: list[str] = []

        for dir_pattern in self.config.file_store_dirs:
            source_dir = Path(dir_pattern)
            if not source_dir.is_absolute():
                source_dir = _PROJECT_ROOT / dir_pattern

            if not source_dir.exists():
                continue

            for pattern in self.config.file_patterns:
                for filepath in source_dir.glob(pattern):
                    if not filepath.is_file():
                        continue
                    try:
                        if self.config.compress:
                            dest_name = filepath.name + ".gz"
                            dest = target_dir / dest_name
                            with (
                                open(filepath, "rb") as f_in,
                                gzip.open(dest, "wb", compresslevel=6) as f_out,
                            ):
                                shutil.copyfileobj(f_in, f_out)
                        else:
                            dest = target_dir / filepath.name
                            shutil.copy2(filepath, dest)

                        backed_up.append(dest.name)
                        total_size += dest.stat().st_size
                    except OSError as exc:
                        errors.append(f"{filepath.name}: {exc}")

        success = len(errors) == 0
        return ComponentResult(
            component="file_stores",
            success=success,
            files=backed_up,
            size_bytes=total_size,
            duration_seconds=time.monotonic() - start,
            error="; ".join(errors) if errors else None,
        )

    async def _backup_qdrant(self, target_dir: Path) -> ComponentResult:
        """Trigger Qdrant snapshot (best-effort)."""
        start = time.monotonic()
        try:
            import httpx

            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.get(
                    f"{self.config.qdrant_url}/collections"
                )
                if resp.status_code != 200:
                    return ComponentResult(
                        component="qdrant",
                        success=False,
                        error=f"Qdrant unreachable: HTTP {resp.status_code}",
                        duration_seconds=time.monotonic() - start,
                    )

                collections = resp.json().get("result", {}).get("collections", [])
                snapshots: list[str] = []
                for coll in collections:
                    name = coll.get("name", "")
                    if not name:
                        continue
                    snap_resp = await client.post(
                        f"{self.config.qdrant_url}/collections/{name}/snapshots"
                    )
                    if snap_resp.status_code == 200:
                        snapshots.append(name)

                return ComponentResult(
                    component="qdrant",
                    success=True,
                    files=snapshots,
                    duration_seconds=time.monotonic() - start,
                )
        except Exception as exc:
            return ComponentResult(
                component="qdrant",
                success=False,
                error=str(exc),
                duration_seconds=time.monotonic() - start,
            )

    async def _rotate_audit_logs(self, target_dir: Path) -> ComponentResult:
        """Archive audit logs into the backup directory."""
        start = time.monotonic()
        audit_file = _PROJECT_ROOT / "data" / "audit.jsonl"
        if not audit_file.exists():
            return ComponentResult(
                component="audit_logs",
                success=True,
                files=[],
                duration_seconds=time.monotonic() - start,
            )

        try:
            dest = target_dir / "audit.jsonl.gz"
            with (
                open(audit_file, "rb") as f_in,
                gzip.open(dest, "wb", compresslevel=6) as f_out,
            ):
                shutil.copyfileobj(f_in, f_out)

            return ComponentResult(
                component="audit_logs",
                success=True,
                files=[dest.name],
                size_bytes=dest.stat().st_size,
                duration_seconds=time.monotonic() - start,
            )
        except OSError as exc:
            return ComponentResult(
                component="audit_logs",
                success=False,
                error=str(exc),
                duration_seconds=time.monotonic() - start,
            )

    # ─── Private: Helpers ───────────────────────────────────────────────────

    def _write_manifest(
        self,
        backup_id: str,
        target_dir: Path,
        results: list[ComponentResult],
    ) -> Path | None:
        """Write manifest.json with checksums for all backed-up files."""
        try:
            checksums: dict[str, str] = {}
            file_map: dict[str, str] = {}

            for f in target_dir.iterdir():
                if f.is_file() and f.name != "manifest.json":
                    checksums[f.name] = self._sha256_file(f)

            # Build file_map for restore: backup_filename → original relative path
            for r in results:
                if r.component == "file_stores":
                    for fname in r.files:
                        # Strip .gz suffix to get original name
                        orig_name = fname.removesuffix(".gz")
                        for dir_pattern in self.config.file_store_dirs:
                            candidate = Path(dir_pattern) / orig_name
                            if not candidate.is_absolute():
                                candidate = _PROJECT_ROOT / candidate
                            if candidate.exists():
                                rel = candidate.relative_to(_PROJECT_ROOT)
                                file_map[fname] = str(rel)
                                break

            manifest = {
                "backup_id": backup_id,
                "created_at": datetime.now(UTC).isoformat(),
                "success": all(r.success for r in results),
                "total_size_bytes": sum(r.size_bytes for r in results),
                "components": [r.component for r in results],
                "component_details": [
                    {
                        "component": r.component,
                        "success": r.success,
                        "files": r.files,
                        "size_bytes": r.size_bytes,
                        "duration_seconds": round(r.duration_seconds, 3),
                        "error": r.error,
                    }
                    for r in results
                ],
                "checksums": checksums,
                "file_map": file_map,
            }

            manifest_path = target_dir / "manifest.json"
            manifest_path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            return manifest_path
        except OSError as exc:
            logger.error("Failed to write manifest: %s", exc)
            return None

    @staticmethod
    def _sha256_file(filepath: Path) -> str:
        """Compute SHA-256 hash of a file."""
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _cron_to_interval(cron: str) -> int:
        """Convert simple cron to seconds interval (fallback: 24h).

        Supports basic patterns:
            "0 2 * * *"  → 86400 (daily)
            "0 */6 * * *" → 21600 (every 6h)
            "0 * * * *"  → 3600 (hourly)
        """
        parts = cron.strip().split()
        if len(parts) != 5:
            return 86400
        minute, hour, *_ = parts
        if hour.startswith("*/"):
            try:
                return int(hour[2:]) * 3600
            except ValueError:
                return 86400
        if hour == "*" and minute != "*":
            return 3600
        return 86400  # default daily


# ─── Factory ────────────────────────────────────────────────────────────────────

_scheduler_instance: BackupScheduler | None = None


def get_backup_scheduler(config: BackupConfig | None = None) -> BackupScheduler:
    """Get or create the global backup scheduler instance."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = BackupScheduler(config)
    return _scheduler_instance
