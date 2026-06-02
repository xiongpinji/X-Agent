"""Git-like version control for artifacts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ArtifactVersion(BaseModel):
    """Single artifact version."""
    version_id: str = Field(..., description="Unique version ID")
    artifact_id: str = Field(..., description="Parent artifact ID")
    content: str = Field(..., description="Version content")
    content_hash: str = Field(..., description="SHA256 hash of content")
    author: str = Field(..., description="Author user ID")
    message: str = Field(default="", description="Commit message")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    parent_version_id: Optional[str] = Field(default=None, description="Parent version ID")
    metadata: dict = Field(default_factory=dict, description="Version metadata")


class VersionControl:
    """Git-like version control system for artifacts."""

    def __init__(self, storage_backend):
        """Initialize version control.

        Args:
            storage_backend: Backend for storing versions
        """
        self.storage = storage_backend

    @staticmethod
    def _compute_hash(content: str) -> str:
        """Compute SHA256 hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()

    async def create_version(
        self,
        artifact_id: str,
        content: str,
        message: str,
        author: str,
        metadata: dict = None,
    ) -> ArtifactVersion:
        """Create new version.

        Args:
            artifact_id: Parent artifact ID
            content: Version content
            message: Commit message
            author: Author user ID
            metadata: Additional metadata

        Returns:
            Created ArtifactVersion
        """
        content_hash = self._compute_hash(content)

        # Get parent version
        parent = await self.get_latest(artifact_id)
        parent_version_id = parent.version_id if parent else None

        version = ArtifactVersion(
            version_id=self._generate_version_id(),
            artifact_id=artifact_id,
            content=content,
            content_hash=content_hash,
            author=author,
            message=message,
            parent_version_id=parent_version_id,
            metadata=metadata or {},
        )

        await self.storage.save_version(version)
        return version

    async def get_version(self, version_id: str) -> Optional[ArtifactVersion]:
        """Get specific version.

        Args:
            version_id: Version ID

        Returns:
            ArtifactVersion or None
        """
        return await self.storage.get_version(version_id)

    async def get_latest(self, artifact_id: str) -> Optional[ArtifactVersion]:
        """Get latest version of artifact.

        Args:
            artifact_id: Artifact ID

        Returns:
            Latest ArtifactVersion or None
        """
        return await self.storage.get_latest_version(artifact_id)

    async def list_versions(
        self,
        artifact_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ArtifactVersion], int]:
        """List all versions of artifact.

        Args:
            artifact_id: Artifact ID
            limit: Result limit
            offset: Result offset

        Returns:
            Tuple of (versions, total_count)
        """
        return await self.storage.list_versions(artifact_id, limit=limit, offset=offset)

    async def get_diff(
        self,
        version_id_1: str,
        version_id_2: str,
    ) -> dict:
        """Get diff between two versions.

        Args:
            version_id_1: First version ID
            version_id_2: Second version ID

        Returns:
            Diff information
        """
        v1 = await self.get_version(version_id_1)
        v2 = await self.get_version(version_id_2)

        if not v1 or not v2:
            raise ValueError("One or both versions not found")

        # Simple line-based diff
        lines1 = v1.content.split("\n")
        lines2 = v2.content.split("\n")

        added = []
        removed = []
        modified = []

        for i, (line1, line2) in enumerate(zip(lines1, lines2)):
            if line1 != line2:
                modified.append({
                    "line": i + 1,
                    "before": line1,
                    "after": line2,
                })

        # Handle length differences
        if len(lines1) < len(lines2):
            for i in range(len(lines1), len(lines2)):
                added.append({
                    "line": i + 1,
                    "content": lines2[i],
                })
        elif len(lines1) > len(lines2):
            for i in range(len(lines2), len(lines1)):
                removed.append({
                    "line": i + 1,
                    "content": lines1[i],
                })

        return {
            "from_version": version_id_1,
            "to_version": version_id_2,
            "added_lines": len(added),
            "removed_lines": len(removed),
            "modified_lines": len(modified),
            "changes": {
                "added": added,
                "removed": removed,
                "modified": modified,
            },
        }

    async def revert(
        self,
        artifact_id: str,
        target_version_id: str,
        author: str,
    ) -> ArtifactVersion:
        """Revert to previous version.

        Args:
            artifact_id: Artifact ID
            target_version_id: Version to revert to
            author: User performing revert

        Returns:
            New version with reverted content
        """
        target = await self.get_version(target_version_id)
        if not target:
            raise ValueError(f"Version {target_version_id} not found")

        # Create new version with old content
        return await self.create_version(
            artifact_id,
            target.content,
            f"Revert to {target_version_id}",
            author,
            metadata={"reverted_from": target_version_id},
        )

    async def get_history(
        self,
        artifact_id: str,
        limit: int = 20,
    ) -> list[dict]:
        """Get version history summary.

        Args:
            artifact_id: Artifact ID
            limit: Number of versions to return

        Returns:
            List of version summaries
        """
        versions, _ = await self.list_versions(artifact_id, limit=limit)

        return [
            {
                "version_id": v.version_id,
                "author": v.author,
                "message": v.message,
                "created_at": v.created_at.isoformat(),
                "content_hash": v.content_hash[:8],  # Short hash
                "size_bytes": len(v.content),
            }
            for v in versions
        ]

    async def get_stats(self, artifact_id: str) -> dict:
        """Get version statistics.

        Args:
            artifact_id: Artifact ID

        Returns:
            Statistics dictionary
        """
        versions, total = await self.list_versions(artifact_id, limit=1000)

        if not versions:
            return {
                "total_versions": 0,
                "total_size_bytes": 0,
                "authors": [],
            }

        authors = set()
        total_size = 0

        for v in versions:
            authors.add(v.author)
            total_size += len(v.content)

        return {
            "total_versions": total,
            "total_size_bytes": total_size,
            "average_size_bytes": total_size // len(versions) if versions else 0,
            "authors": list(authors),
            "oldest_version": versions[-1].created_at.isoformat() if versions else None,
            "newest_version": versions[0].created_at.isoformat() if versions else None,
        }

    @staticmethod
    def _generate_version_id() -> str:
        """Generate unique version ID."""
        import uuid
        return str(uuid.uuid4())
