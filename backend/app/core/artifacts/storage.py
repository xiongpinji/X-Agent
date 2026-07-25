"""Artifact storage module."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Artifact(BaseModel):
    """Artifact model."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    type: str  # html, chart, dashboard, table
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tags: list[str] = Field(default_factory=list)
    description: str = ""


class ArtifactStorage:
    """Artifact storage manager."""

    def __init__(self, storage_path: str):
        """Initialize artifact storage.

        Args:
            storage_path: Path to store artifacts
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    async def save_artifact(self, artifact: Artifact) -> str:
        """Save artifact to storage.

        Args:
            artifact: Artifact to save

        Returns:
            Artifact ID
        """
        artifact.updated_at = datetime.now(UTC)
        artifact_path = self.storage_path / f"{artifact.id}.json"

        with open(artifact_path, "w", encoding="utf-8") as f:
            json.dump(artifact.model_dump(mode="json"), f, indent=2, default=str)

        return artifact.id

    async def load_artifact(self, artifact_id: str) -> Artifact | None:
        """Load artifact from storage.

        Args:
            artifact_id: Artifact ID

        Returns:
            Artifact or None if not found
        """
        artifact_path = self.storage_path / f"{artifact_id}.json"
        if not artifact_path.exists():
            return None

        with open(artifact_path, encoding="utf-8") as f:
            data = json.load(f)

        return Artifact(**data)

    async def delete_artifact(self, artifact_id: str) -> bool:
        """Delete artifact from storage.

        Args:
            artifact_id: Artifact ID

        Returns:
            True if deleted, False if not found
        """
        artifact_path = self.storage_path / f"{artifact_id}.json"
        if not artifact_path.exists():
            return False

        artifact_path.unlink()
        return True

    async def list_artifacts(
        self,
        artifact_type: str | None = None,
        tags: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Artifact]:
        """List artifacts with optional filtering.

        Args:
            artifact_type: Filter by artifact type
            tags: Filter by tags (any match)
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of artifacts
        """
        artifacts = []

        for artifact_file in sorted(self.storage_path.glob("*.json")):
            artifact = await self.load_artifact(artifact_file.stem)
            if not artifact:
                continue

            # Apply filters
            if artifact_type and artifact.type != artifact_type:
                continue

            if tags and not any(tag in artifact.tags for tag in tags):
                continue

            artifacts.append(artifact)

        # Sort by creation time (newest first)
        artifacts.sort(key=lambda a: a.created_at, reverse=True)

        # Apply pagination
        return artifacts[offset : offset + limit]

    async def search_artifacts(self, query: str, limit: int = 50) -> list[Artifact]:
        """Search artifacts by name or description.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of matching artifacts
        """
        query_lower = query.lower()
        results = []

        for artifact_file in self.storage_path.glob("*.json"):
            artifact = await self.load_artifact(artifact_file.stem)
            if not artifact:
                continue

            if query_lower in artifact.name.lower() or query_lower in artifact.description.lower():
                results.append(artifact)

        results.sort(key=lambda a: a.created_at, reverse=True)
        return results[:limit]

    async def update_artifact(self, artifact_id: str, updates: dict[str, Any]) -> Artifact | None:
        """Update artifact.

        Args:
            artifact_id: Artifact ID
            updates: Fields to update

        Returns:
            Updated artifact or None if not found
        """
        artifact = await self.load_artifact(artifact_id)
        if not artifact:
            return None

        # Update allowed fields
        for key, value in updates.items():
            if key in ["name", "content", "metadata", "tags", "description"]:
                setattr(artifact, key, value)

        await self.save_artifact(artifact)
        return artifact

    async def get_artifact_stats(self) -> dict[str, Any]:
        """Get storage statistics.

        Returns:
            Storage statistics
        """
        artifacts = []
        for artifact_file in self.storage_path.glob("*.json"):
            artifact = await self.load_artifact(artifact_file.stem)
            if artifact:
                artifacts.append(artifact)

        type_counts = {}
        for artifact in artifacts:
            type_counts[artifact.type] = type_counts.get(artifact.type, 0) + 1

        return {
            "total_artifacts": len(artifacts),
            "by_type": type_counts,
            "storage_path": str(self.storage_path),
        }
