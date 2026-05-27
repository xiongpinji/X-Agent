"""Skill Registry - Central registry for skill discovery and management"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any, Callable
import asyncio

from .skills_core import SkillMetadata, SkillCapability, SkillStatus

logger = logging.getLogger(__name__)


@dataclass
class SkillRating:
    """Rating information for a skill"""
    skill_id: str
    average_rating: float = 0.0
    total_ratings: int = 0
    download_count: int = 0
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class SkillSearchResult:
    """Result of skill search"""
    skill_id: str
    name: str
    version: str
    description: str
    capabilities: list[str]
    rating: float
    download_count: int
    relevance_score: float = 0.0


class SkillRegistry:
    """Central registry for skill discovery and management"""

    def __init__(self):
        self.skills: dict[str, SkillMetadata] = {}
        self.ratings: dict[str, SkillRating] = {}
        self.status: dict[str, SkillStatus] = {}
        self.tags_index: dict[str, set[str]] = {}  # tag -> skill_ids
        self.capability_index: dict[str, set[str]] = {}  # capability -> skill_ids
        self._lock = asyncio.Lock()

    async def register_skill(self, metadata: SkillMetadata) -> tuple[bool, str | None]:
        """Register a skill in the registry"""
        async with self._lock:
            try:
                skill_id = metadata.skill_id

                # Check if already registered
                if skill_id in self.skills:
                    return False, f"Skill already registered: {skill_id}"

                # Store metadata
                self.skills[skill_id] = metadata
                self.status[skill_id] = SkillStatus.REGISTERED

                # Initialize rating
                self.ratings[skill_id] = SkillRating(skill_id=skill_id)

                # Update indices
                self._update_indices(skill_id, metadata)

                logger.info(f"Registered skill: {metadata.name} ({skill_id})")
                return True, None

            except Exception as e:
                error = f"Error registering skill: {str(e)}"
                logger.error(error, exc_info=True)
                return False, error

    async def unregister_skill(self, skill_id: str) -> tuple[bool, str | None]:
        """Unregister a skill from the registry"""
        async with self._lock:
            try:
                if skill_id not in self.skills:
                    return False, f"Skill not found: {skill_id}"

                metadata = self.skills[skill_id]

                # Remove from indices
                self._remove_from_indices(skill_id, metadata)

                # Remove from registry
                del self.skills[skill_id]
                if skill_id in self.status:
                    del self.status[skill_id]
                if skill_id in self.ratings:
                    del self.ratings[skill_id]

                logger.info(f"Unregistered skill: {skill_id}")
                return True, None

            except Exception as e:
                error = f"Error unregistering skill: {str(e)}"
                logger.error(error, exc_info=True)
                return False, error

    async def update_skill_status(self, skill_id: str, status: SkillStatus) -> tuple[bool, str | None]:
        """Update skill status"""
        async with self._lock:
            if skill_id not in self.skills:
                return False, f"Skill not found: {skill_id}"

            self.status[skill_id] = status
            logger.info(f"Updated skill status: {skill_id} -> {status.value}")
            return True, None

    def get_skill(self, skill_id: str) -> SkillMetadata | None:
        """Get skill metadata by ID"""
        return self.skills.get(skill_id)

    def get_skill_status(self, skill_id: str) -> SkillStatus | None:
        """Get skill status"""
        return self.status.get(skill_id)

    def get_skill_rating(self, skill_id: str) -> SkillRating | None:
        """Get skill rating information"""
        return self.ratings.get(skill_id)

    def list_skills(self, status: SkillStatus | None = None) -> list[SkillMetadata]:
        """List all skills, optionally filtered by status"""
        skills = list(self.skills.values())

        if status:
            skills = [s for s in skills if self.status.get(s.skill_id) == status]

        return sorted(skills, key=lambda s: s.updated_at, reverse=True)

    def search_skills(self, query: str, limit: int = 20) -> list[SkillSearchResult]:
        """Search skills by name or description"""
        query_lower = query.lower()
        results = []

        for skill_id, metadata in self.skills.items():
            relevance_score = 0.0

            # Check name match
            if query_lower in metadata.name.lower():
                relevance_score += 10.0

            # Check description match
            if query_lower in metadata.description.lower():
                relevance_score += 5.0

            # Check tags match
            for tag in metadata.tags:
                if query_lower in tag.lower():
                    relevance_score += 3.0

            if relevance_score > 0:
                rating = self.ratings.get(skill_id)
                result = SkillSearchResult(
                    skill_id=skill_id,
                    name=metadata.name,
                    version=metadata.version,
                    description=metadata.description,
                    capabilities=[c.value for c in metadata.capabilities],
                    rating=rating.average_rating if rating else 0.0,
                    download_count=rating.download_count if rating else 0,
                    relevance_score=relevance_score,
                )
                results.append(result)

        # Sort by relevance score
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results[:limit]

    def find_by_capability(self, capability: SkillCapability) -> list[SkillMetadata]:
        """Find skills by capability"""
        skill_ids = self.capability_index.get(capability.value, set())
        return [self.skills[sid] for sid in skill_ids if sid in self.skills]

    def find_by_tag(self, tag: str) -> list[SkillMetadata]:
        """Find skills by tag"""
        skill_ids = self.tags_index.get(tag.lower(), set())
        return [self.skills[sid] for sid in skill_ids if sid in self.skills]

    async def rate_skill(self, skill_id: str, rating: float) -> tuple[bool, str | None]:
        """Rate a skill (1-5 stars)"""
        if not 1.0 <= rating <= 5.0:
            return False, "Rating must be between 1 and 5"

        async with self._lock:
            if skill_id not in self.ratings:
                return False, f"Skill not found: {skill_id}"

            skill_rating = self.ratings[skill_id]
            total = skill_rating.total_ratings
            current_avg = skill_rating.average_rating

            # Calculate new average
            new_avg = (current_avg * total + rating) / (total + 1)
            skill_rating.average_rating = new_avg
            skill_rating.total_ratings = total + 1
            skill_rating.last_updated = datetime.now(UTC)

            return True, None

    async def increment_download_count(self, skill_id: str) -> tuple[bool, str | None]:
        """Increment download count for a skill"""
        async with self._lock:
            if skill_id not in self.ratings:
                return False, f"Skill not found: {skill_id}"

            self.ratings[skill_id].download_count += 1
            return True, None

    def get_top_skills(self, limit: int = 10) -> list[tuple[SkillMetadata, SkillRating]]:
        """Get top-rated skills"""
        skills_with_ratings = [
            (self.skills[sid], self.ratings[sid])
            for sid in self.skills
            if sid in self.ratings
        ]

        # Sort by rating, then by download count
        skills_with_ratings.sort(
            key=lambda x: (x[1].average_rating, x[1].download_count),
            reverse=True,
        )

        return skills_with_ratings[:limit]

    def get_trending_skills(self, limit: int = 10) -> list[tuple[SkillMetadata, SkillRating]]:
        """Get trending skills (by recent downloads)"""
        skills_with_ratings = [
            (self.skills[sid], self.ratings[sid])
            for sid in self.skills
            if sid in self.ratings
        ]

        # Sort by download count
        skills_with_ratings.sort(
            key=lambda x: x[1].download_count,
            reverse=True,
        )

        return skills_with_ratings[:limit]

    def _update_indices(self, skill_id: str, metadata: SkillMetadata) -> None:
        """Update search indices for a skill"""
        # Update capability index
        for capability in metadata.capabilities:
            cap_key = capability.value
            if cap_key not in self.capability_index:
                self.capability_index[cap_key] = set()
            self.capability_index[cap_key].add(skill_id)

        # Update tags index
        for tag in metadata.tags:
            tag_key = tag.lower()
            if tag_key not in self.tags_index:
                self.tags_index[tag_key] = set()
            self.tags_index[tag_key].add(skill_id)

    def _remove_from_indices(self, skill_id: str, metadata: SkillMetadata) -> None:
        """Remove skill from search indices"""
        # Remove from capability index
        for capability in metadata.capabilities:
            cap_key = capability.value
            if cap_key in self.capability_index:
                self.capability_index[cap_key].discard(skill_id)

        # Remove from tags index
        for tag in metadata.tags:
            tag_key = tag.lower()
            if tag_key in self.tags_index:
                self.tags_index[tag_key].discard(skill_id)

    def get_statistics(self) -> dict[str, Any]:
        """Get registry statistics"""
        total_skills = len(self.skills)
        total_downloads = sum(r.download_count for r in self.ratings.values())
        avg_rating = (
            sum(r.average_rating for r in self.ratings.values()) / len(self.ratings)
            if self.ratings
            else 0.0
        )

        status_counts = {}
        for status in SkillStatus:
            count = sum(1 for s in self.status.values() if s == status)
            if count > 0:
                status_counts[status.value] = count

        return {
            "total_skills": total_skills,
            "total_downloads": total_downloads,
            "average_rating": round(avg_rating, 2),
            "status_distribution": status_counts,
            "capabilities_count": len(self.capability_index),
            "tags_count": len(self.tags_index),
        }


# Global registry instance
_skill_registry: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    """Get or create the global skill registry"""
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = SkillRegistry()
    return _skill_registry


__all__ = [
    "SkillRegistry",
    "SkillRating",
    "SkillSearchResult",
    "get_skill_registry",
]
