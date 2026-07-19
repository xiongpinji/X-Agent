"""Artifact sharing and access control."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Optional

from pydantic import BaseModel, Field


class ArtifactShare(BaseModel):
    """Artifact share link."""
    share_id: str = Field(..., description="Unique share ID")
    artifact_id: str = Field(..., description="Artifact ID")
    owner: str = Field(..., description="Share owner user ID")
    share_token: str = Field(..., description="Share access token")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = Field(default=None, description="Expiration time")
    is_public: bool = Field(default=False, description="Public share")
    allow_download: bool = Field(default=False, description="Allow downloading")
    allow_edit: bool = Field(default=False, description="Allow editing")
    view_count: int = Field(default=0, description="Number of views")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")


class SharingManager:
    """Manage artifact sharing and access."""

    def __init__(self, storage_backend):
        """Initialize sharing manager.

        Args:
            storage_backend: Backend for storing shares
        """
        self.storage = storage_backend

    @staticmethod
    def _generate_share_token(length: int = 32) -> str:
        """Generate secure share token."""
        return secrets.token_urlsafe(length)

    @staticmethod
    def _generate_share_id() -> str:
        """Generate unique share ID."""
        import uuid
        return str(uuid.uuid4())

    async def create_share(
        self,
        artifact_id: str,
        owner: str,
        is_public: bool = False,
        allow_download: bool = False,
        allow_edit: bool = False,
        expires_in_days: Optional[int] = None,
    ) -> ArtifactShare:
        """Create share link for artifact.

        Args:
            artifact_id: Artifact ID
            owner: Share owner user ID
            is_public: Public share
            allow_download: Allow downloading
            allow_edit: Allow editing
            expires_in_days: Days until expiration (None = no expiration)

        Returns:
            Created ArtifactShare
        """
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        share = ArtifactShare(
            share_id=self._generate_share_id(),
            artifact_id=artifact_id,
            owner=owner,
            share_token=self._generate_share_token(),
            is_public=is_public,
            allow_download=allow_download,
            allow_edit=allow_edit,
            expires_at=expires_at,
        )

        await self.storage.save_share(share)
        return share

    async def get_share(self, share_id: str) -> Optional[ArtifactShare]:
        """Get share by ID.

        Args:
            share_id: Share ID

        Returns:
            ArtifactShare or None
        """
        share = await self.storage.get_share(share_id)

        if share and share.expires_at and share.expires_at < datetime.utcnow():
            # Share expired
            return None

        return share

    async def get_share_by_token(self, share_token: str) -> Optional[ArtifactShare]:
        """Get share by token.

        Args:
            share_token: Share token

        Returns:
            ArtifactShare or None
        """
        share = await self.storage.get_share_by_token(share_token)

        if share and share.expires_at and share.expires_at < datetime.utcnow():
            # Share expired
            return None

        return share

    async def list_shares(
        self,
        artifact_id: str,
        owner: Optional[str] = None,
    ) -> list[ArtifactShare]:
        """List shares for artifact.

        Args:
            artifact_id: Artifact ID
            owner: Filter by owner (optional)

        Returns:
            List of ArtifactShare
        """
        return await self.storage.list_shares(artifact_id, owner=owner)

    async def update_share(
        self,
        share_id: str,
        allow_download: Optional[bool] = None,
        allow_edit: Optional[bool] = None,
        expires_in_days: Optional[int] = None,
    ) -> Optional[ArtifactShare]:
        """Update share settings.

        Args:
            share_id: Share ID
            allow_download: Update download permission
            allow_edit: Update edit permission
            expires_in_days: Update expiration

        Returns:
            Updated ArtifactShare or None
        """
        share = await self.get_share(share_id)
        if not share:
            return None

        if allow_download is not None:
            share.allow_download = allow_download
        if allow_edit is not None:
            share.allow_edit = allow_edit
        if expires_in_days is not None:
            share.expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        await self.storage.save_share(share)
        return share

    async def revoke_share(self, share_id: str) -> bool:
        """Revoke share link.

        Args:
            share_id: Share ID

        Returns:
            True if revoked successfully
        """
        return await self.storage.delete_share(share_id)

    async def record_view(self, share_id: str) -> bool:
        """Record share view.

        Args:
            share_id: Share ID

        Returns:
            True if recorded successfully
        """
        share = await self.get_share(share_id)
        if not share:
            return False

        share.view_count += 1
        await self.storage.save_share(share)
        return True

    async def get_share_stats(self, artifact_id: str) -> dict:
        """Get sharing statistics for artifact.

        Args:
            artifact_id: Artifact ID

        Returns:
            Statistics dictionary
        """
        shares = await self.list_shares(artifact_id)

        total_views = sum(s.view_count for s in shares)
        active_shares = sum(1 for s in shares if not s.expires_at or s.expires_at > datetime.utcnow())
        public_shares = sum(1 for s in shares if s.is_public)

        return {
            "total_shares": len(shares),
            "active_shares": active_shares,
            "public_shares": public_shares,
            "total_views": total_views,
            "average_views_per_share": total_views // len(shares) if shares else 0,
        }

    async def generate_share_url(
        self,
        share_id: str,
        base_url: str = "https://xagent.ai",
    ) -> str:
        """Generate shareable URL.

        Args:
            share_id: Share ID
            base_url: Base URL for share links

        Returns:
            Full share URL
        """
        return f"{base_url}/artifacts/share/{share_id}"

    async def check_access(
        self,
        share_id: str,
        user_id: Optional[str] = None,
        action: str = "view",
    ) -> bool:
        """Check if user has access to shared artifact.

        Args:
            share_id: Share ID
            user_id: User ID (None for anonymous)
            action: Action to check ("view", "download", "edit")

        Returns:
            True if access allowed
        """
        share = await self.get_share(share_id)
        if not share:
            return False

        # Check expiration
        if share.expires_at and share.expires_at < datetime.utcnow():
            return False

        # Check permissions
        if action == "view":
            return True  # Always allow view for valid shares
        elif action == "download":
            return share.allow_download
        elif action == "edit":
            return share.allow_edit and (user_id == share.owner)

        return False
