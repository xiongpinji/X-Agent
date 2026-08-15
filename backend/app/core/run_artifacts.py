"""Persistent manifests joining an agent run to its artifacts and archive."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
import zipfile
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from functools import lru_cache
from hashlib import sha256
from html import escape
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.app.core.artifacts import Artifact, ArtifactStorage

_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_LOCK_TIMEOUT_SECONDS = 5.0
_LOCK_STALE_SECONDS = 300.0
_LOCK_POLL_SECONDS = 0.02


def _safe_component(value: str) -> str:
    if not _SAFE_COMPONENT.fullmatch(value) or value in {".", ".."}:
        raise ValueError("Invalid run artifact identifier")
    return value


class ArtifactReference(BaseModel):
    artifact_id: str
    name: str
    type: str
    content_sha256: str
    mime_type: str
    size_bytes: int
    download_url: str


class ArchiveReference(BaseModel):
    archive_id: str
    archive_sha256: str
    size_bytes: int
    download_url: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RunArtifactManifest(BaseModel):
    run_id: str
    trace_id: str
    tenant_id: str
    user_id: str
    status: str
    artifacts: list[ArtifactReference] = Field(default_factory=list)
    audit_ids: list[str] = Field(default_factory=list)
    archive: ArchiveReference | None = None
    error_code: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RunArtifactAuditError(RuntimeError):
    """A required lifecycle audit could not be committed."""


ArchiveAuditCallback = Callable[[RunArtifactManifest], Awaitable[str]]
ArchiveRollbackAuditCallback = Callable[[RunArtifactManifest, str], Awaitable[str]]


class RunArtifactManager:
    """Own manifests/archives while sharing the authoritative artifact store."""

    def __init__(
        self,
        root_path: str | Path,
        *,
        artifact_storage: ArtifactStorage | None = None,
    ) -> None:
        self.root_path = Path(root_path)
        self.manifest_path = self.root_path / "manifests"
        self.archive_path = self.root_path / "archives"
        self.lock_path = self.root_path / "locks"
        self.artifact_storage = artifact_storage or ArtifactStorage(
            self.root_path / "artifacts"
        )
        self.manifest_path.mkdir(parents=True, exist_ok=True)
        self.archive_path.mkdir(parents=True, exist_ok=True)
        self.lock_path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _atomic_write(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_bytes(content)
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def _scope_path(self, root: Path, tenant_id: str, user_id: str) -> Path:
        _safe_component(tenant_id)
        _safe_component(user_id)
        tenant = sha256(f"tenant:{tenant_id}".encode()).hexdigest()[:24]
        user = sha256(f"user:{user_id}".encode()).hexdigest()[:24]
        path = root / tenant / user
        if root.resolve() not in path.resolve().parents:
            raise ValueError("Invalid run artifact scope")
        return path

    def _manifest_file(self, run_id: str, tenant_id: str, user_id: str) -> Path:
        run = _safe_component(run_id)
        return self._scope_path(self.manifest_path, tenant_id, user_id) / f"{run}.json"

    def _archive_file(self, archive_id: str, tenant_id: str, user_id: str) -> Path:
        archive = _safe_component(archive_id)
        return self._scope_path(self.archive_path, tenant_id, user_id) / f"{archive}.zip"

    def _lock_file(self, run_id: str, tenant_id: str, user_id: str) -> Path:
        run = _safe_component(run_id)
        return self._scope_path(self.lock_path, tenant_id, user_id) / f"{run}.lock"

    @staticmethod
    def _try_acquire_lock(path: Path, token: str) -> bool:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(
                path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError:
            return False
        try:
            payload = json.dumps(
                {
                    "token": token,
                    "pid": os.getpid(),
                    "created_at": time.time(),
                }
            ).encode("utf-8")
            os.write(descriptor, payload)
        except Exception:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            raise
        finally:
            os.close(descriptor)
        return True

    @staticmethod
    def _pid_is_running(pid: int) -> bool:
        if pid <= 0:
            return True
        if pid == os.getpid():
            return True
        if os.name == "nt":
            import ctypes

            synchronize = 0x00100000
            handle = ctypes.windll.kernel32.OpenProcess(synchronize, False, pid)
            if not handle:
                return False
            try:
                wait_timeout = 0x00000102
                return ctypes.windll.kernel32.WaitForSingleObject(handle, 0) == wait_timeout
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    @classmethod
    def _remove_stale_lock(cls, path: Path) -> bool:
        try:
            stat = path.stat()
            if time.time() - stat.st_mtime <= _LOCK_STALE_SECONDS:
                return False
            observed = path.read_text(encoding="utf-8")
            payload = json.loads(observed)
            pid = int(payload["pid"])
            token = str(payload["token"])
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return False
        if not token or cls._pid_is_running(pid):
            return False
        try:
            if path.read_text(encoding="utf-8") != observed:
                return False
            path.unlink()
        except (FileNotFoundError, OSError):
            return False
        return True

    @staticmethod
    def _release_lock(path: Path, token: str) -> None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("token") != token:
                return
            path.unlink()
        except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError):
            return

    @asynccontextmanager
    async def _run_lock(
        self,
        run_id: str,
        tenant_id: str,
        user_id: str,
    ) -> AsyncIterator[None]:
        path = self._lock_file(run_id, tenant_id, user_id)
        token = uuid4().hex
        deadline = time.monotonic() + _LOCK_TIMEOUT_SECONDS
        while True:
            acquired = await asyncio.to_thread(self._try_acquire_lock, path, token)
            if acquired:
                break
            await asyncio.to_thread(self._remove_stale_lock, path)
            if time.monotonic() >= deadline:
                raise TimeoutError("Run artifact lock acquisition timed out")
            await asyncio.sleep(_LOCK_POLL_SECONDS)
        try:
            yield
        finally:
            release = asyncio.create_task(
                asyncio.to_thread(self._release_lock, path, token)
            )
            try:
                await asyncio.shield(release)
            except asyncio.CancelledError:
                await release
                raise

    async def save_manifest(self, manifest: RunArtifactManifest) -> RunArtifactManifest:
        async with self._run_lock(
            manifest.run_id,
            manifest.tenant_id,
            manifest.user_id,
        ):
            authoritative = await self._get_manifest_unlocked(
                manifest.run_id,
                manifest.tenant_id,
                manifest.user_id,
            )
            if authoritative is not None:
                if authoritative.status != manifest.status:
                    raise ValueError("Manifest status is immutable")
                manifest.created_at = authoritative.created_at
                manifest.audit_ids = list(
                    dict.fromkeys([*authoritative.audit_ids, *manifest.audit_ids])
                )
                if authoritative.archive is not None:
                    manifest.archive = authoritative.archive
            return await self._save_manifest_unlocked(manifest)

    async def _save_manifest_unlocked(
        self,
        manifest: RunArtifactManifest,
    ) -> RunArtifactManifest:
        if manifest.status not in {"completed", "failed"}:
            raise ValueError("Invalid manifest status")
        if manifest.run_id != manifest.trace_id:
            raise ValueError("run_id and trace_id must match")
        manifest.updated_at = datetime.now(UTC)
        payload = json.dumps(
            manifest.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        path = self._manifest_file(
            manifest.run_id,
            manifest.tenant_id,
            manifest.user_id,
        )
        await asyncio.to_thread(self._atomic_write, path, payload)
        return manifest

    async def _get_manifest_unlocked(
        self,
        run_id: str,
        tenant_id: str,
        user_id: str,
    ) -> RunArtifactManifest | None:
        try:
            path = self._manifest_file(run_id, tenant_id, user_id)
        except ValueError:
            return None
        return await asyncio.to_thread(
            self._read_manifest,
            path,
            run_id,
            tenant_id,
            user_id,
        )

    async def get_manifest(
        self,
        run_id: str,
        tenant_id: str,
        user_id: str,
    ) -> RunArtifactManifest | None:
        return await self._get_manifest_unlocked(run_id, tenant_id, user_id)

    @staticmethod
    def _read_manifest(
        path: Path,
        run_id: str,
        tenant_id: str,
        user_id: str,
    ) -> RunArtifactManifest | None:
        if not path.is_file():
            return None
        try:
            _safe_component(path.stem)
            manifest = RunArtifactManifest.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            return None
        if (
            path.stem != run_id
            or manifest.run_id != run_id
            or manifest.trace_id != run_id
            or manifest.status not in {"completed", "failed"}
            or manifest.tenant_id != tenant_id
            or manifest.user_id != user_id
        ):
            return None
        return manifest

    async def create_answer_artifact(
        self,
        *,
        run_id: str,
        tenant_id: str,
        user_id: str,
        answer: str,
    ) -> Artifact:
        safe_answer = escape(answer)
        artifact = Artifact(
            name=f"run-{run_id}-answer.html",
            type="html",
            content=(
                "<!doctype html><html><head><meta charset=\"utf-8\">"
                "<title>Agent result</title></head><body><main><pre>"
                f"{safe_answer}</pre></main></body></html>"
            ),
            tenant_id=tenant_id,
            user_id=user_id,
            run_id=run_id,
            trace_id=run_id,
            description="Final answer generated by the agent run.",
            tags=["agent-run", "final-answer"],
        )
        await self.artifact_storage.save_artifact(artifact)
        return artifact

    @staticmethod
    def _reference(artifact: Artifact) -> ArtifactReference:
        return ArtifactReference(
            artifact_id=artifact.id,
            name=artifact.name,
            type=artifact.type,
            content_sha256=artifact.content_sha256,
            mime_type=artifact.mime_type,
            size_bytes=artifact.size_bytes,
            download_url=f"/api/v1/artifacts/{artifact.id}/download",
        )

    def completed_manifest(
        self,
        *,
        run_id: str,
        tenant_id: str,
        user_id: str,
        artifacts: list[Artifact],
        audit_ids: list[str],
    ) -> RunArtifactManifest:
        return RunArtifactManifest(
            run_id=run_id,
            trace_id=run_id,
            tenant_id=tenant_id,
            user_id=user_id,
            status="completed",
            artifacts=[self._reference(artifact) for artifact in artifacts],
            audit_ids=audit_ids,
        )

    @staticmethod
    def failed_manifest(
        *,
        run_id: str,
        tenant_id: str,
        user_id: str,
        error_code: str,
        audit_ids: list[str],
    ) -> RunArtifactManifest:
        return RunArtifactManifest(
            run_id=run_id,
            trace_id=run_id,
            tenant_id=tenant_id,
            user_id=user_id,
            status="failed",
            artifacts=[],
            audit_ids=audit_ids,
            error_code=error_code,
        )

    async def create_archive(
        self,
        run_id: str,
        tenant_id: str,
        user_id: str,
        *,
        audit_callback: ArchiveAuditCallback | None = None,
        rollback_audit_callback: ArchiveRollbackAuditCallback | None = None,
    ) -> tuple[RunArtifactManifest, bool] | None:
        if (audit_callback is None) != (rollback_audit_callback is None):
            raise ValueError("Archive audit callbacks must be provided together")
        async with self._run_lock(run_id, tenant_id, user_id):
            manifest = await self._get_manifest_unlocked(run_id, tenant_id, user_id)
            if manifest is None or manifest.status != "completed":
                return None
            if manifest.archive is not None:
                archive_file = self._archive_file(
                    manifest.archive.archive_id,
                    tenant_id,
                    user_id,
                )
                if not await asyncio.to_thread(archive_file.is_file):
                    raise ValueError("Declared archive is missing")
                existing = await asyncio.to_thread(archive_file.read_bytes)
                if (
                    sha256(existing).hexdigest()
                    != manifest.archive.archive_sha256
                    or len(existing) != manifest.archive.size_bytes
                ):
                    raise ValueError("Declared archive integrity check failed")
                return manifest, False
            verified: list[tuple[Artifact, bytes]] = []
            for reference in manifest.artifacts:
                stored = await self.artifact_storage.content_bytes(
                    reference.artifact_id,
                    tenant_id,
                    user_id,
                )
                if stored is None:
                    raise ValueError("Artifact integrity check failed")
                artifact, content = stored
                if (
                    artifact.run_id != run_id
                    or artifact.trace_id != run_id
                    or artifact.content_sha256 != reference.content_sha256
                    or len(content) != reference.size_bytes
                ):
                    raise ValueError("Artifact manifest integrity check failed")
                verified.append((artifact, content))

            def _build_zip() -> bytes:
                buffer = BytesIO()
                with zipfile.ZipFile(
                    buffer,
                    "w",
                    compression=zipfile.ZIP_DEFLATED,
                ) as archive:
                    archive.writestr(
                        "manifest.json",
                        json.dumps(
                            manifest.model_dump(mode="json"),
                            ensure_ascii=False,
                            indent=2,
                        ),
                    )
                    for artifact, content in verified:
                        suffix = ".html" if artifact.type == "html" else ".txt"
                        archive.writestr(f"artifacts/{artifact.id}{suffix}", content)
                return buffer.getvalue()

            archive_bytes = await asyncio.to_thread(_build_zip)
            archive_id = str(uuid4())
            archive_file = self._archive_file(archive_id, tenant_id, user_id)
            await asyncio.to_thread(self._atomic_write, archive_file, archive_bytes)
            manifest.archive = ArchiveReference(
                archive_id=archive_id,
                archive_sha256=sha256(archive_bytes).hexdigest(),
                size_bytes=len(archive_bytes),
                download_url=f"/api/v1/artifacts/archives/{archive_id}/download",
            )
            audit_id: str | None = None
            audit_started = False
            try:
                await self._save_manifest_unlocked(manifest)
                if audit_callback is not None:
                    audit_started = True
                    audit_id = await audit_callback(manifest)
                    if not audit_id:
                        raise RunArtifactAuditError("Required audit id is missing")
                    if audit_id not in manifest.audit_ids:
                        manifest.audit_ids.append(audit_id)
                    await self._save_manifest_unlocked(manifest)
            except BaseException as failure:
                cleanup = asyncio.create_task(
                    self._rollback_archive_commit(
                        run_id,
                        tenant_id,
                        user_id,
                        archive_id,
                        manifest,
                        audit_id,
                        rollback_audit_callback,
                    )
                )
                while not cleanup.done():
                    try:
                        await asyncio.shield(cleanup)
                    except asyncio.CancelledError:
                        continue
                cleanup.result()
                if isinstance(failure, Exception) and audit_started:
                    raise RunArtifactAuditError(
                        "Required archive audit could not be committed"
                    ) from None
                raise
            return manifest, True

    @staticmethod
    def _remove_file(path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    async def _rollback_archive_commit(
        self,
        run_id: str,
        tenant_id: str,
        user_id: str,
        archive_id: str,
        manifest: RunArtifactManifest,
        audit_id: str | None,
        rollback_audit_callback: ArchiveRollbackAuditCallback | None,
    ) -> None:
        rolled_back: RunArtifactManifest | None = None
        try:
            rolled_back = await self._remove_archive_unlocked(
                run_id,
                tenant_id,
                user_id,
                archive_id,
            )
        except Exception:
            pass
        if not audit_id or rollback_audit_callback is None:
            return
        try:
            rollback_audit_id = await rollback_audit_callback(manifest, audit_id)
            if not rollback_audit_id:
                raise RunArtifactAuditError("Required rollback audit id is missing")
            if rolled_back is not None:
                rolled_back.audit_ids = list(
                    dict.fromkeys(
                        [*rolled_back.audit_ids, audit_id, rollback_audit_id]
                    )
                )
                await self._save_manifest_unlocked(rolled_back)
        except Exception:
            pass

    async def _remove_archive_unlocked(
        self,
        run_id: str,
        tenant_id: str,
        user_id: str,
        archive_id: str,
    ) -> RunArtifactManifest | None:
        archive_file = self._archive_file(archive_id, tenant_id, user_id)
        await asyncio.to_thread(self._remove_file, archive_file)
        authoritative = await self._get_manifest_unlocked(
            run_id,
            tenant_id,
            user_id,
        )
        if (
            authoritative is not None
            and authoritative.archive is not None
            and authoritative.archive.archive_id == archive_id
        ):
            authoritative.archive = None
            await self._save_manifest_unlocked(authoritative)
        return authoritative

    async def remove_archive(self, manifest: RunArtifactManifest) -> None:
        """Make an archive unreachable and remove its bytes after audit failure."""
        archive = manifest.archive
        if archive is None:
            return
        async with self._run_lock(
            manifest.run_id,
            manifest.tenant_id,
            manifest.user_id,
        ):
            await self._remove_archive_unlocked(
                manifest.run_id,
                manifest.tenant_id,
                manifest.user_id,
                archive.archive_id,
            )

    async def add_audit_id(
        self,
        manifest: RunArtifactManifest,
        audit_id: str,
    ) -> RunArtifactManifest:
        if not audit_id:
            raise RunArtifactAuditError("Required audit id is missing")
        async with self._run_lock(
            manifest.run_id,
            manifest.tenant_id,
            manifest.user_id,
        ):
            authoritative = await self._get_manifest_unlocked(
                manifest.run_id,
                manifest.tenant_id,
                manifest.user_id,
            )
            if authoritative is None:
                raise ValueError("Run artifact manifest is missing")
            if audit_id not in authoritative.audit_ids:
                authoritative.audit_ids.append(audit_id)
                await self._save_manifest_unlocked(authoritative)
            return authoritative

    async def archive_bytes(
        self,
        archive_id: str,
        tenant_id: str,
        user_id: str,
    ) -> tuple[RunArtifactManifest, bytes] | None:
        try:
            scope = self._scope_path(self.manifest_path, tenant_id, user_id)
            _safe_component(archive_id)
        except ValueError:
            return None

        def _manifest_files() -> list[Path]:
            return list(scope.glob("*.json"))

        for path in await asyncio.to_thread(_manifest_files):
            manifest = await asyncio.to_thread(
                self._read_manifest,
                path,
                path.stem,
                tenant_id,
                user_id,
            )
            if manifest is None:
                continue
            if manifest.archive is None or manifest.archive.archive_id != archive_id:
                continue
            archive_file = self._archive_file(archive_id, tenant_id, user_id)
            if not await asyncio.to_thread(archive_file.is_file):
                return None
            content = await asyncio.to_thread(archive_file.read_bytes)
            if (
                sha256(content).hexdigest() != manifest.archive.archive_sha256
                or len(content) != manifest.archive.size_bytes
            ):
                return None
            return manifest, content
        return None


@lru_cache
def get_run_artifact_manager() -> RunArtifactManager:
    return RunArtifactManager(Path("data") / "run_artifacts")
