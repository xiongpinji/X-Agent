"""Artifacts API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from backend.app.api.errors import api_error
from backend.app.core.artifacts import Artifact, ArtifactRenderer, ArtifactStorage
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/artifacts", tags=["artifacts"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# Initialize storage and renderer
artifact_storage = ArtifactStorage("./data/artifacts")
artifact_renderer = ArtifactRenderer()


@router.post("")
async def create_artifact(
    artifact: Artifact,
    principal: PrincipalDependency,
) -> dict:
    """Create a new artifact.

    Args:
        artifact: Artifact to create
        principal: Current principal

    Returns:
        Created artifact
    """
    enforce_scope(principal, "artifacts:write")

    artifact_id = await artifact_storage.save_artifact(artifact)
    return {"id": artifact_id, "status": "created"}


@router.get("")
async def list_artifacts(
    artifact_type: str | None = Query(None),
    tags: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    *,
    principal: PrincipalDependency,
) -> dict:
    """List artifacts with optional filtering.

    Args:
        artifact_type: Filter by artifact type
        tags: Filter by tags (comma-separated)
        limit: Maximum number of results
        offset: Number of results to skip
        principal: Current principal

    Returns:
        List of artifacts
    """
    enforce_scope(principal, "artifacts:read")

    tag_list = tags.split(",") if tags else None
    artifacts = await artifact_storage.list_artifacts(
        artifact_type=artifact_type,
        tags=tag_list,
        limit=limit,
        offset=offset,
    )

    return {
        "artifacts": [a.model_dump(mode="json") for a in artifacts],
        "count": len(artifacts),
        "limit": limit,
        "offset": offset,
    }


@router.get("/{artifact_id}")
async def get_artifact(
    artifact_id: str,
    principal: PrincipalDependency,
) -> dict:
    """Get artifact by ID.

    Args:
        artifact_id: Artifact ID
        principal: Current principal

    Returns:
        Artifact details
    """
    enforce_scope(principal, "artifacts:read")

    artifact = await artifact_storage.load_artifact(artifact_id)
    if not artifact:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Artifact not found.", trace_id=artifact_id)

    return artifact.model_dump(mode="json")


@router.put("/{artifact_id}")
async def update_artifact(
    artifact_id: str,
    updates: dict,
    principal: PrincipalDependency,
) -> dict:
    """Update artifact.

    Args:
        artifact_id: Artifact ID
        updates: Fields to update
        principal: Current principal

    Returns:
        Updated artifact
    """
    enforce_scope(principal, "artifacts:write")

    artifact = await artifact_storage.update_artifact(artifact_id, updates)
    if not artifact:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Artifact not found.", trace_id=artifact_id)

    return artifact.model_dump(mode="json")


@router.delete("/{artifact_id}")
async def delete_artifact(
    artifact_id: str,
    principal: PrincipalDependency,
) -> dict:
    """Delete artifact.

    Args:
        artifact_id: Artifact ID
        principal: Current principal

    Returns:
        Deletion result
    """
    enforce_scope(principal, "artifacts:write")

    deleted = await artifact_storage.delete_artifact(artifact_id)
    if not deleted:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Artifact not found.", trace_id=artifact_id)

    return {"status": "deleted", "id": artifact_id}


@router.get("/{artifact_id}/render")
async def render_artifact(
    artifact_id: str,
    principal: PrincipalDependency,
) -> dict:
    """Render artifact to HTML.

    Args:
        artifact_id: Artifact ID
        principal: Current principal

    Returns:
        Rendered HTML
    """
    enforce_scope(principal, "artifacts:read")

    artifact = await artifact_storage.load_artifact(artifact_id)
    if not artifact:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, "Artifact not found.", trace_id=artifact_id)

    try:
        html = await artifact_renderer.render(artifact)
        return {"html": html, "artifact_id": artifact_id}
    except Exception as e:
        raise api_error(400, ErrorCode.INVALID_REQUEST, f"Render failed: {e!s}")


@router.get("/search")
async def search_artifacts(
    query: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=500),
    *,
    principal: PrincipalDependency,
) -> dict:
    """Search artifacts.

    Args:
        query: Search query
        limit: Maximum number of results
        principal: Current principal

    Returns:
        Search results
    """
    enforce_scope(principal, "artifacts:read")

    results = await artifact_storage.search_artifacts(query, limit)
    return {
        "query": query,
        "results": [a.model_dump(mode="json") for a in results],
        "count": len(results),
    }


@router.get("/stats")
async def get_artifact_stats(
    principal: PrincipalDependency,
) -> dict:
    """Get artifact storage statistics.

    Args:
        principal: Current principal

    Returns:
        Storage statistics
    """
    enforce_scope(principal, "artifacts:read")

    stats = await artifact_storage.get_artifact_stats()
    return stats
