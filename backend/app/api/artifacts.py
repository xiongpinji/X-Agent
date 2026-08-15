"""Tenant-scoped artifact, manifest, download, and archive APIs."""

from __future__ import annotations

import asyncio
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.core.artifacts import Artifact, ArtifactRenderer
from backend.app.core.contracts import ErrorCode
from backend.app.core.run_artifacts import (
    RunArtifactAuditError,
    RunArtifactManager,
    RunArtifactManifest,
    RunArtifactRollbackError,
    get_run_artifact_manager,
)
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_audit_store, get_current_principal

router = APIRouter(prefix="/api/v1/artifacts", tags=["artifacts"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
ManagerDependency = Annotated[RunArtifactManager, Depends(get_run_artifact_manager)]

artifact_renderer = ArtifactRenderer()


class CreateArtifactRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: str = Field(min_length=1, max_length=32)
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    description: str = ""


class UpdateArtifactRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = None
    metadata: dict[str, Any] | None = None
    tags: list[str] | None = None
    description: str | None = None


def _not_found(resource_id: str):
    return api_error(
        404,
        ErrorCode.RESOURCE_NOT_FOUND,
        "Artifact resource not found.",
        trace_id=resource_id,
    )


def _download_headers(name: str, fallback: str) -> dict[str, str]:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")[:120]
    filename = cleaned or fallback
    return {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Content-Type-Options": "nosniff",
    }


async def _audit(**kwargs: Any) -> str:
    record = await asyncio.to_thread(get_audit_store().record, **kwargs)
    audit_id = getattr(record, "id", None)
    if not audit_id:
        raise RunArtifactAuditError("Required audit id is missing")
    return str(audit_id)


async def _best_effort_failure_audit(**kwargs: Any) -> None:
    try:
        await _audit(**kwargs)
    except Exception:
        return


def _scope(principal: Principal) -> tuple[str, str]:
    return principal.tenant_id, principal.user_id


# Fixed paths must precede /{artifact_id}.
@router.get("/search")
async def search_artifacts(
    principal: PrincipalDependency,
    manager: ManagerDependency,
    query: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, Any]:
    enforce_scope(principal, "agent:read")
    tenant_id, user_id = _scope(principal)
    results = await manager.artifact_storage.search_artifacts(
        query,
        limit,
        tenant_id,
        user_id,
    )
    return {
        "query": query,
        "results": [item.model_dump(mode="json") for item in results],
        "count": len(results),
    }


@router.get("/stats")
async def get_artifact_stats(
    principal: PrincipalDependency,
    manager: ManagerDependency,
) -> dict[str, Any]:
    enforce_scope(principal, "agent:read")
    return await manager.artifact_storage.get_artifact_stats(*_scope(principal))


@router.get("/runs/{run_id}/manifest")
async def get_run_manifest(
    run_id: str,
    principal: PrincipalDependency,
    manager: ManagerDependency,
) -> dict[str, Any]:
    enforce_scope(principal, "agent:read")
    manifest = await manager.get_manifest(run_id, *_scope(principal))
    if manifest is None:
        raise _not_found(run_id)
    return manifest.model_dump(mode="json")


@router.post("/runs/{run_id}/archive")
async def archive_run(
    run_id: str,
    principal: PrincipalDependency,
    manager: ManagerDependency,
) -> dict[str, Any]:
    enforce_scope(principal, "agent:run")
    tenant_id, user_id = _scope(principal)

    async def _record_created(manifest: RunArtifactManifest) -> str:
        if manifest.archive is None:
            raise RunArtifactAuditError("Archive reference is missing")
        return await _audit(
            action="run.archive.created",
            resource_type="run_archive",
            resource_id=manifest.archive.archive_id,
            tenant_id=tenant_id,
            actor_id=user_id,
            trace_id=run_id,
            run_id=run_id,
            details={"status": "created", "size_bytes": manifest.archive.size_bytes},
        )

    async def _record_rollback(
        manifest: RunArtifactManifest,
        created_audit_id: str,
    ) -> str:
        if manifest.archive is None:
            raise RunArtifactAuditError("Archive reference is missing")
        return await _audit(
            action="run.archive.rollback",
            resource_type="run_archive",
            resource_id=manifest.archive.archive_id,
            tenant_id=tenant_id,
            actor_id=user_id,
            outcome="failure",
            trace_id=run_id,
            run_id=run_id,
            details={
                "status": "rolled_back",
                "created_audit_id": created_audit_id,
            },
        )

    try:
        archive_result = await manager.create_archive(
            run_id,
            tenant_id,
            user_id,
            audit_callback=_record_created,
            rollback_audit_callback=_record_rollback,
        )
    except RunArtifactRollbackError:
        raise api_error(
            503,
            ErrorCode.INTERNAL_ERROR,
            "Run archive rollback could not be completed.",
            trace_id=run_id,
        ) from None
    except RunArtifactAuditError:
        raise api_error(
            503,
            ErrorCode.INTERNAL_ERROR,
            "Run archive could not be audited.",
            trace_id=run_id,
        ) from None
    except (OSError, ValueError):
        raise api_error(
            409,
            ErrorCode.RESOURCE_CONFLICT,
            "Run archive integrity check failed.",
            trace_id=run_id,
        ) from None
    if archive_result is None:
        raise _not_found(run_id)
    manifest, _created = archive_result
    if manifest.archive is None:
        raise _not_found(run_id)
    return {"run_id": run_id, "archive": manifest.archive.model_dump(mode="json")}


@router.get("/archives/{archive_id}/download")
async def download_archive(
    archive_id: str,
    principal: PrincipalDependency,
    manager: ManagerDependency,
) -> Response:
    enforce_scope(principal, "agent:read")
    tenant_id, user_id = _scope(principal)
    stored = await manager.archive_bytes(archive_id, tenant_id, user_id)
    if stored is None:
        raise _not_found(archive_id)
    manifest, content = stored
    try:
        audit_id = await _audit(
            action="run.archive.download.requested",
            resource_type="run_archive",
            resource_id=archive_id,
            tenant_id=tenant_id,
            actor_id=user_id,
            trace_id=manifest.trace_id,
            run_id=manifest.run_id,
            details={"status": "requested", "size_bytes": len(content)},
        )
    except Exception:
        raise api_error(
            503,
            ErrorCode.INTERNAL_ERROR,
            "Run archive download could not be audited.",
            trace_id=manifest.trace_id,
        ) from None
    try:
        await manager.add_audit_id(manifest, audit_id)
    except Exception:
        await _best_effort_failure_audit(
            action="run.archive.download.manifest_failed",
            resource_type="run_archive",
            resource_id=archive_id,
            tenant_id=tenant_id,
            actor_id=user_id,
            outcome="failure",
            trace_id=manifest.trace_id,
            run_id=manifest.run_id,
            details={"status": "manifest_failed", "request_audit_id": audit_id},
        )
        raise api_error(
            503,
            ErrorCode.INTERNAL_ERROR,
            "Run archive download could not be audited.",
            trace_id=manifest.trace_id,
        ) from None
    return Response(
        content=content,
        media_type="application/zip",
        headers=_download_headers(f"run-{manifest.run_id}.zip", "archive.zip"),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_artifact(
    request: CreateArtifactRequest,
    principal: PrincipalDependency,
    manager: ManagerDependency,
) -> dict[str, str]:
    enforce_scope(principal, "agent:run")
    tenant_id, user_id = _scope(principal)
    artifact = Artifact(
        **request.model_dump(),
        tenant_id=tenant_id,
        user_id=user_id,
    )
    await manager.artifact_storage.save_artifact(artifact)
    try:
        await _audit(
            action="artifact.created",
            resource_type="artifact",
            resource_id=artifact.id,
            tenant_id=tenant_id,
            actor_id=user_id,
            trace_id=artifact.trace_id,
            run_id=artifact.run_id,
            details={"status": "created", "content_sha256": artifact.content_sha256},
        )
    except Exception:
        await manager.artifact_storage.delete_artifact(
            artifact.id,
            tenant_id,
            user_id,
        )
        raise api_error(
            503,
            ErrorCode.INTERNAL_ERROR,
            "Artifact creation could not be audited.",
        ) from None
    return {"id": artifact.id, "status": "created"}


@router.get("")
async def list_artifacts(
    principal: PrincipalDependency,
    manager: ManagerDependency,
    artifact_type: str | None = Query(None),
    tags: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    enforce_scope(principal, "agent:read")
    items = await manager.artifact_storage.list_artifacts(
        artifact_type,
        tags.split(",") if tags else None,
        limit,
        offset,
        *_scope(principal),
    )
    return {
        "artifacts": [item.model_dump(mode="json") for item in items],
        "count": len(items),
        "limit": limit,
        "offset": offset,
    }


@router.get("/{artifact_id}/download")
async def download_artifact(
    artifact_id: str,
    principal: PrincipalDependency,
    manager: ManagerDependency,
) -> Response:
    enforce_scope(principal, "agent:read")
    tenant_id, user_id = _scope(principal)
    stored = await manager.artifact_storage.content_bytes(
        artifact_id,
        tenant_id,
        user_id,
    )
    if stored is None:
        raise _not_found(artifact_id)
    artifact, content = stored
    try:
        audit_id = await _audit(
            action="artifact.download.requested",
            resource_type="artifact",
            resource_id=artifact.id,
            tenant_id=tenant_id,
            actor_id=user_id,
            trace_id=artifact.trace_id,
            run_id=artifact.run_id,
            details={"status": "requested", "size_bytes": len(content)},
        )
    except Exception:
        raise api_error(
            503,
            ErrorCode.INTERNAL_ERROR,
            "Artifact download could not be audited.",
            trace_id=artifact.trace_id,
        ) from None
    try:
        if artifact.run_id and artifact.trace_id == artifact.run_id:
            manifest = await manager.get_manifest(
                artifact.run_id,
                tenant_id,
                user_id,
            )
            if manifest is not None:
                await manager.add_audit_id(manifest, audit_id)
    except Exception:
        await _best_effort_failure_audit(
            action="artifact.download.manifest_failed",
            resource_type="artifact",
            resource_id=artifact.id,
            tenant_id=tenant_id,
            actor_id=user_id,
            outcome="failure",
            trace_id=artifact.trace_id,
            run_id=artifact.run_id,
            details={"status": "manifest_failed", "request_audit_id": audit_id},
        )
        raise api_error(
            503,
            ErrorCode.INTERNAL_ERROR,
            "Artifact download could not be audited.",
            trace_id=artifact.trace_id,
        ) from None
    return Response(
        content=content,
        media_type=artifact.mime_type,
        headers=_download_headers(artifact.name, f"artifact-{artifact.id}.txt"),
    )


@router.get("/{artifact_id}/render")
async def render_artifact(
    artifact_id: str,
    principal: PrincipalDependency,
    manager: ManagerDependency,
) -> dict[str, str]:
    enforce_scope(principal, "agent:read")
    artifact = await manager.artifact_storage.load_artifact(
        artifact_id,
        *_scope(principal),
    )
    if artifact is None:
        raise _not_found(artifact_id)
    try:
        html = await artifact_renderer.render(artifact)
    except Exception:
        raise api_error(
            400,
            ErrorCode.VALIDATION_ERROR,
            "Artifact could not be rendered.",
            trace_id=artifact.trace_id,
        ) from None
    return {"html": html, "artifact_id": artifact_id}


@router.get("/{artifact_id}")
async def get_artifact(
    artifact_id: str,
    principal: PrincipalDependency,
    manager: ManagerDependency,
) -> dict[str, Any]:
    enforce_scope(principal, "agent:read")
    artifact = await manager.artifact_storage.load_artifact(
        artifact_id,
        *_scope(principal),
    )
    if artifact is None:
        raise _not_found(artifact_id)
    return artifact.model_dump(mode="json")


@router.put("/{artifact_id}")
async def update_artifact(
    artifact_id: str,
    request: UpdateArtifactRequest,
    principal: PrincipalDependency,
    manager: ManagerDependency,
) -> dict[str, Any]:
    enforce_scope(principal, "agent:run")
    updates = request.model_dump(exclude_none=True)
    artifact = await manager.artifact_storage.update_artifact(
        artifact_id,
        updates,
        *_scope(principal),
    )
    if artifact is None:
        raise _not_found(artifact_id)
    return artifact.model_dump(mode="json")


@router.delete("/{artifact_id}")
async def delete_artifact(
    artifact_id: str,
    principal: PrincipalDependency,
    manager: ManagerDependency,
) -> dict[str, str]:
    enforce_scope(principal, "agent:run")
    deleted = await manager.artifact_storage.delete_artifact(
        artifact_id,
        *_scope(principal),
    )
    if not deleted:
        raise _not_found(artifact_id)
    return {"status": "deleted", "id": artifact_id}
