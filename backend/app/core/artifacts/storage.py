"""Tenant-scoped, file-backed artifact storage."""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_MIME_TYPES = {
    "html": "text/html; charset=utf-8",
    "chart": "application/json; charset=utf-8",
    "dashboard": "application/json; charset=utf-8",
    "table": "application/json; charset=utf-8",
}


def _validated_component(value: str) -> str:
    if not _SAFE_COMPONENT.fullmatch(value) or value in {".", ".."}:
        raise ValueError("Invalid storage identifier")
    return value


class Artifact(BaseModel):
    """Authoritative stored artifact metadata and UTF-8 content."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    type: str
    content: str
    tenant_id: str = "default"
    user_id: str = "anonymous"
    run_id: str | None = None
    trace_id: str | None = None
    content_sha256: str = ""
    mime_type: str = "text/plain; charset=utf-8"
    size_bytes: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tags: list[str] = Field(default_factory=list)
    description: str = ""


class ArtifactStorage:
    """Store each artifact below an owning tenant/user partition."""

    def __init__(self, storage_path: str | Path):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def _scope_path(self, tenant_id: str, user_id: str) -> Path:
        _validated_component(tenant_id)
        _validated_component(user_id)
        tenant = sha256(f"tenant:{tenant_id}".encode()).hexdigest()[:24]
        user = sha256(f"user:{user_id}".encode()).hexdigest()[:24]
        path = self.storage_path / tenant / user
        resolved_root = self.storage_path.resolve()
        resolved_path = path.resolve()
        if resolved_root not in resolved_path.parents:
            raise ValueError("Invalid artifact scope")
        return path

    def _artifact_path(self, artifact_id: str, tenant_id: str, user_id: str) -> Path:
        identifier = _validated_component(artifact_id)
        return self._scope_path(tenant_id, user_id) / f"{identifier}.json"

    @staticmethod
    def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()

    async def save_artifact(self, artifact: Artifact) -> str:
        _validated_component(artifact.id)
        _validated_component(artifact.tenant_id)
        _validated_component(artifact.user_id)
        content_bytes = artifact.content.encode("utf-8")
        artifact.content_sha256 = sha256(content_bytes).hexdigest()
        artifact.size_bytes = len(content_bytes)
        artifact.mime_type = _MIME_TYPES.get(artifact.type, artifact.mime_type)
        artifact.updated_at = datetime.now(UTC)
        path = self._artifact_path(artifact.id, artifact.tenant_id, artifact.user_id)
        await asyncio.to_thread(
            self._write_json_atomic,
            path,
            artifact.model_dump(mode="json"),
        )
        return artifact.id

    @staticmethod
    def _read_artifact(
        path: Path,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> Artifact | None:
        if not path.is_file():
            return None
        try:
            artifact = Artifact.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        content = artifact.content.encode("utf-8")
        if (
            artifact.id != path.stem
            or artifact.content_sha256 != sha256(content).hexdigest()
            or artifact.size_bytes != len(content)
        ):
            return None
        if tenant_id is not None and (
            user_id is None
            or artifact.tenant_id != tenant_id
            or artifact.user_id != user_id
        ):
            return None
        return artifact

    async def load_artifact(
        self,
        artifact_id: str,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> Artifact | None:
        try:
            _validated_component(artifact_id)
            if tenant_id is not None or user_id is not None:
                if tenant_id is None or user_id is None:
                    return None
                path = self._artifact_path(artifact_id, tenant_id, user_id)
                return await asyncio.to_thread(
                    self._read_artifact,
                    path,
                    tenant_id,
                    user_id,
                )
        except ValueError:
            return None

        matches = await asyncio.to_thread(
            lambda: list(self.storage_path.glob(f"*/*/{artifact_id}.json"))
        )
        if len(matches) != 1:
            return None
        return await asyncio.to_thread(self._read_artifact, matches[0])

    async def delete_artifact(
        self,
        artifact_id: str,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> bool:
        artifact = await self.load_artifact(artifact_id, tenant_id, user_id)
        if artifact is None:
            return False
        path = self._artifact_path(artifact.id, artifact.tenant_id, artifact.user_id)

        def _delete() -> bool:
            try:
                path.unlink()
                return True
            except FileNotFoundError:
                return False

        return await asyncio.to_thread(_delete)

    async def list_artifacts(
        self,
        artifact_type: str | None = None,
        tags: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> list[Artifact]:
        try:
            if tenant_id is None and user_id is None:
                files = await asyncio.to_thread(lambda: list(self.storage_path.glob("*/*/*.json")))
            elif tenant_id is not None and user_id is not None:
                scope = self._scope_path(tenant_id, user_id)
                files = await asyncio.to_thread(lambda: list(scope.glob("*.json")))
            else:
                return []
        except ValueError:
            return []
        artifacts = []
        for path in files:
            artifact = await asyncio.to_thread(
                self._read_artifact,
                path,
                tenant_id,
                user_id,
            )
            if artifact is None:
                continue
            if artifact_type and artifact.type != artifact_type:
                continue
            if tags and not any(tag in artifact.tags for tag in tags):
                continue
            artifacts.append(artifact)
        artifacts.sort(key=lambda item: item.created_at, reverse=True)
        return artifacts[offset : offset + limit]

    async def search_artifacts(
        self,
        query: str,
        limit: int = 50,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> list[Artifact]:
        artifacts = await self.list_artifacts(
            limit=10_000,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        query_lower = query.lower()
        matches = [
            artifact
            for artifact in artifacts
            if query_lower in artifact.name.lower()
            or query_lower in artifact.description.lower()
        ]
        return matches[:limit]

    async def update_artifact(
        self,
        artifact_id: str,
        updates: dict[str, Any],
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> Artifact | None:
        artifact = await self.load_artifact(artifact_id, tenant_id, user_id)
        if artifact is None:
            return None
        for key, value in updates.items():
            if key in {"name", "content", "metadata", "tags", "description"}:
                setattr(artifact, key, value)
        await self.save_artifact(artifact)
        return artifact

    async def get_artifact_stats(
        self,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        artifacts = await self.list_artifacts(
            limit=10_000,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        type_counts: dict[str, int] = {}
        for artifact in artifacts:
            type_counts[artifact.type] = type_counts.get(artifact.type, 0) + 1
        return {
            "total_artifacts": len(artifacts),
            "by_type": type_counts,
        }

    async def content_bytes(
        self,
        artifact_id: str,
        tenant_id: str,
        user_id: str,
    ) -> tuple[Artifact, bytes] | None:
        artifact = await self.load_artifact(artifact_id, tenant_id, user_id)
        if artifact is None:
            return None
        content = artifact.content.encode("utf-8")
        if (
            sha256(content).hexdigest() != artifact.content_sha256
            or len(content) != artifact.size_bytes
        ):
            return None
        return artifact, content
