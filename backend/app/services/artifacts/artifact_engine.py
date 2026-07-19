"""Artifact engine for creating, managing, and rendering artifacts."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ArtifactType(str, Enum):
    """Supported artifact types."""
    HTML = "html"
    REACT = "react"
    MARKDOWN = "markdown"
    SVG = "svg"
    CHART = "chart"
    TABLE = "table"
    CODE = "code"
    DOCUMENT = "document"
    DASHBOARD = "dashboard"
    VISUALIZATION = "visualization"


class ArtifactStatus(str, Enum):
    """Artifact lifecycle status."""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ArtifactMetadata(BaseModel):
    """Artifact metadata."""
    title: str = Field(..., description="Artifact title")
    description: str = Field(default="", description="Artifact description")
    tags: list[str] = Field(default_factory=list, description="Artifact tags")
    author: str = Field(..., description="Creator user ID")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    version: int = Field(default=1, description="Current version number")
    is_public: bool = Field(default=False, description="Public visibility")
    is_template: bool = Field(default=False, description="Can be used as template")


class Artifact(BaseModel):
    """Artifact representation."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique artifact ID")
    type: ArtifactType = Field(..., description="Artifact type")
    status: ArtifactStatus = Field(default=ArtifactStatus.DRAFT, description="Artifact status")
    content: str = Field(..., description="Artifact content")
    metadata: ArtifactMetadata = Field(..., description="Artifact metadata")
    dependencies: list[str] = Field(default_factory=list, description="External dependencies")
    sandbox_config: dict = Field(default_factory=dict, description="Sandbox execution config")
    render_config: dict = Field(default_factory=dict, description="Rendering configuration")


class ArtifactEngine:
    """Main artifact management engine."""

    def __init__(self, storage_backend, version_control):
        """Initialize artifact engine.

        Args:
            storage_backend: Backend for artifact storage (e.g., database)
            version_control: Version control system for artifacts
        """
        self.storage = storage_backend
        self.version_control = version_control

    async def create(
        self,
        artifact_type: ArtifactType,
        content: str,
        title: str,
        author: str,
        description: str = "",
        tags: list[str] = None,
        is_public: bool = False,
        dependencies: list[str] = None,
        sandbox_config: dict = None,
        render_config: dict = None,
    ) -> Artifact:
        """Create new artifact.

        Args:
            artifact_type: Type of artifact
            content: Artifact content
            title: Artifact title
            author: Creator user ID
            description: Artifact description
            tags: Artifact tags
            is_public: Public visibility
            dependencies: External dependencies
            sandbox_config: Sandbox configuration
            render_config: Rendering configuration

        Returns:
            Created Artifact
        """
        metadata = ArtifactMetadata(
            title=title,
            description=description,
            tags=tags or [],
            author=author,
            is_public=is_public,
        )

        artifact = Artifact(
            type=artifact_type,
            content=content,
            metadata=metadata,
            dependencies=dependencies or [],
            sandbox_config=sandbox_config or {},
            render_config=render_config or {},
        )

        # Store artifact
        await self.storage.save(artifact)

        # Create initial version
        await self.version_control.create_version(
            artifact.id,
            content,
            f"Initial version: {title}",
            author,
        )

        return artifact

    async def get(self, artifact_id: str) -> Optional[Artifact]:
        """Get artifact by ID.

        Args:
            artifact_id: Artifact ID

        Returns:
            Artifact or None if not found
        """
        return await self.storage.get(artifact_id)

    async def update(
        self,
        artifact_id: str,
        content: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        author: Optional[str] = None,
        commit_message: str = "",
    ) -> Artifact:
        """Update artifact content and metadata.

        Args:
            artifact_id: Artifact ID
            content: New content
            title: New title (optional)
            description: New description (optional)
            tags: New tags (optional)
            author: User making the update
            commit_message: Version control commit message

        Returns:
            Updated Artifact
        """
        artifact = await self.get(artifact_id)
        if not artifact:
            raise ValueError(f"Artifact {artifact_id} not found")

        # Update metadata
        if title:
            artifact.metadata.title = title
        if description is not None:
            artifact.metadata.description = description
        if tags is not None:
            artifact.metadata.tags = tags

        artifact.content = content
        artifact.metadata.updated_at = datetime.utcnow()
        artifact.metadata.version += 1

        # Save updated artifact
        await self.storage.save(artifact)

        # Create version
        if author:
            await self.version_control.create_version(
                artifact_id,
                content,
                commit_message or f"Update v{artifact.metadata.version}",
                author,
            )

        return artifact

    async def publish(self, artifact_id: str) -> Artifact:
        """Publish artifact.

        Args:
            artifact_id: Artifact ID

        Returns:
            Published Artifact
        """
        artifact = await self.get(artifact_id)
        if not artifact:
            raise ValueError(f"Artifact {artifact_id} not found")

        artifact.status = ArtifactStatus.PUBLISHED
        artifact.metadata.updated_at = datetime.utcnow()

        await self.storage.save(artifact)
        return artifact

    async def archive(self, artifact_id: str) -> Artifact:
        """Archive artifact.

        Args:
            artifact_id: Artifact ID

        Returns:
            Archived Artifact
        """
        artifact = await self.get(artifact_id)
        if not artifact:
            raise ValueError(f"Artifact {artifact_id} not found")

        artifact.status = ArtifactStatus.ARCHIVED
        artifact.metadata.updated_at = datetime.utcnow()

        await self.storage.save(artifact)
        return artifact

    async def delete(self, artifact_id: str) -> bool:
        """Delete artifact.

        Args:
            artifact_id: Artifact ID

        Returns:
            True if deleted successfully
        """
        artifact = await self.get(artifact_id)
        if not artifact:
            raise ValueError(f"Artifact {artifact_id} not found")

        artifact.status = ArtifactStatus.DELETED
        artifact.metadata.updated_at = datetime.utcnow()

        await self.storage.save(artifact)
        return True

    async def list_by_author(
        self,
        author: str,
        status: Optional[ArtifactStatus] = None,
        artifact_type: Optional[ArtifactType] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Artifact], int]:
        """List artifacts by author.

        Args:
            author: Author user ID
            status: Filter by status (optional)
            artifact_type: Filter by type (optional)
            limit: Result limit
            offset: Result offset

        Returns:
            Tuple of (artifacts, total_count)
        """
        return await self.storage.list_by_author(
            author,
            status=status,
            artifact_type=artifact_type,
            limit=limit,
            offset=offset,
        )

    async def search(
        self,
        query: str,
        artifact_type: Optional[ArtifactType] = None,
        tags: Optional[list[str]] = None,
        limit: int = 50,
    ) -> list[Artifact]:
        """Search artifacts.

        Args:
            query: Search query
            artifact_type: Filter by type (optional)
            tags: Filter by tags (optional)
            limit: Result limit

        Returns:
            List of matching artifacts
        """
        return await self.storage.search(
            query,
            artifact_type=artifact_type,
            tags=tags,
            limit=limit,
        )

    async def get_stats(self, author: str) -> dict:
        """Get artifact statistics for author.

        Args:
            author: Author user ID

        Returns:
            Statistics dictionary
        """
        artifacts, total = await self.list_by_author(author, limit=1000)

        type_counts = {}
        status_counts = {}

        for artifact in artifacts:
            type_counts[artifact.type.value] = type_counts.get(artifact.type.value, 0) + 1
            status_counts[artifact.status.value] = status_counts.get(artifact.status.value, 0) + 1

        return {
            "total_artifacts": total,
            "by_type": type_counts,
            "by_status": status_counts,
            "published": status_counts.get("published", 0),
            "drafts": status_counts.get("draft", 0),
        }
