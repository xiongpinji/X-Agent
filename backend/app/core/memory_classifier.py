"""Memory classifier for automatic categorization and importance scoring.

Features:
- Automatic category detection (user, feedback, project, reference)
- Importance scoring based on content characteristics
- Duplicate detection
- Expiration detection
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from backend.app.core.hybrid_memory_system import Memory


class MemoryClassifier:
    """Classify and score memories for optimal storage and retrieval."""

    # Category keywords
    CATEGORY_KEYWORDS = {
        "user": {
            "keywords": ["user", "profile", "preference", "setting", "account", "identity"],
            "weight": 1.0,
        },
        "feedback": {
            "keywords": ["feedback", "review", "comment", "suggestion", "issue", "bug", "error"],
            "weight": 0.9,
        },
        "project": {
            "keywords": ["project", "task", "goal", "milestone", "deadline", "sprint", "workflow"],
            "weight": 0.95,
        },
        "reference": {
            "keywords": ["reference", "documentation", "guide", "tutorial", "example", "note"],
            "weight": 0.8,
        },
    }

    # Importance factors
    IMPORTANCE_FACTORS = {
        "length": 0.1,  # Longer content = slightly more important
        "keywords": 0.3,  # Important keywords boost score
        "recency": 0.2,  # Recent memories are more important
        "frequency": 0.2,  # Frequently accessed memories are important
        "relationships": 0.2,  # Well-connected memories are important
    }

    def __init__(self) -> None:
        self.min_importance = 0.1
        self.max_importance = 1.0

    def classify(self, memory: Memory) -> str:
        """Classify memory into category.

        Args:
            memory: Memory to classify

        Returns:
            Category name: "user", "feedback", "project", or "reference"
        """
        content_lower = memory.content.lower()
        scores: dict[str, float] = {}

        for category, config in self.CATEGORY_KEYWORDS.items():
            score = 0.0
            for keyword in config["keywords"]:
                # Count keyword occurrences
                count = len(re.findall(rf"\b{keyword}\b", content_lower))
                score += count * config["weight"]

            scores[category] = score

        # Return category with highest score, default to reference
        if not scores or max(scores.values()) == 0:
            return "reference"

        return max(scores, key=scores.get)

    def score_importance(self, memory: Memory) -> float:
        """Score memory importance (0.0 to 1.0).

        Args:
            memory: Memory to score

        Returns:
            Importance score
        """
        score = 0.5  # Base score

        # Length factor: longer content is slightly more important
        length_score = min(len(memory.content) / 1000, 1.0)
        score += length_score * self.IMPORTANCE_FACTORS["length"]

        # Keyword factor: important keywords boost score
        keyword_score = self._keyword_importance_score(memory.content)
        score += keyword_score * self.IMPORTANCE_FACTORS["keywords"]

        # Recency factor: recent memories are more important
        age_days = (datetime.now(UTC) - memory.created_at).days
        recency_score = 1.0 / (1.0 + age_days * 0.1)
        score += recency_score * self.IMPORTANCE_FACTORS["recency"]

        # Frequency factor: frequently accessed memories are important
        frequency_score = min(memory.access_count / 10, 1.0)
        score += frequency_score * self.IMPORTANCE_FACTORS["frequency"]

        # Relationship factor: well-connected memories are important
        relationship_score = min(len(memory.related_ids) / 5, 1.0)
        score += relationship_score * self.IMPORTANCE_FACTORS["relationships"]

        # Normalize to 0.0-1.0 range
        score = max(self.min_importance, min(score, self.max_importance))

        return round(score, 2)

    def detect_duplicates(
        self,
        memory: Memory,
        existing: list[Memory],
    ) -> list[str]:
        """Detect potential duplicate memories.

        Args:
            memory: Memory to check
            existing: List of existing memories

        Returns:
            List of duplicate memory IDs
        """
        duplicates: list[str] = []

        for existing_mem in existing:
            similarity = self._content_similarity(memory.content, existing_mem.content)

            # High similarity = duplicate
            if similarity > 0.85:
                duplicates.append(existing_mem.id)
            # Medium similarity + same category = likely duplicate
            elif similarity > 0.7 and memory.category == existing_mem.category:
                duplicates.append(existing_mem.id)

        return duplicates

    def should_expire(self, memory: Memory) -> bool:
        """Check if memory should be expired/archived.

        Args:
            memory: Memory to check

        Returns:
            True if memory should expire
        """
        # Don't expire high-importance memories
        if memory.importance >= 0.8:
            return False

        # Expire very old, low-importance memories
        age_days = (datetime.now(UTC) - memory.created_at).days
        if age_days > 365 and memory.importance < 0.3:
            return True

        # Expire old, never-accessed memories
        if age_days > 90 and memory.access_count == 0 and memory.importance < 0.5:
            return True

        return False

    def get_expiration_date(self, memory: Memory) -> datetime | None:
        """Get expiration date for memory.

        Args:
            memory: Memory to check

        Returns:
            Expiration datetime or None if no expiration
        """
        # High-importance memories don't expire
        if memory.importance >= 0.8:
            return None

        # Calculate expiration based on importance
        if memory.importance >= 0.6:
            days = 365  # 1 year
        elif memory.importance >= 0.4:
            days = 180  # 6 months
        elif memory.importance >= 0.2:
            days = 90  # 3 months
        else:
            days = 30  # 1 month

        return memory.created_at + timedelta(days=days)

    def _keyword_importance_score(self, content: str) -> float:
        """Score importance based on keywords."""
        content_lower = content.lower()

        # High-importance keywords
        high_importance_keywords = [
            "critical", "urgent", "important", "must", "required",
            "error", "bug", "security", "vulnerability", "risk",
            "decision", "approved", "confirmed", "completed",
        ]

        # Low-importance keywords
        low_importance_keywords = [
            "maybe", "perhaps", "possibly", "might", "could",
            "draft", "wip", "todo", "temp", "test",
        ]

        score = 0.5  # Base score

        for keyword in high_importance_keywords:
            if keyword in content_lower:
                score += 0.1

        for keyword in low_importance_keywords:
            if keyword in content_lower:
                score -= 0.1

        return max(0.0, min(score, 1.0))

    @staticmethod
    def _content_similarity(content1: str, content2: str) -> float:
        """Calculate content similarity (0.0 to 1.0).

        Uses simple word overlap method.
        """
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def batch_classify(self, memories: list[Memory]) -> dict[str, list[Memory]]:
        """Classify multiple memories efficiently.

        Args:
            memories: List of memories to classify

        Returns:
            Dictionary mapping categories to memories
        """
        classified: dict[str, list[Memory]] = {
            "user": [],
            "feedback": [],
            "project": [],
            "reference": [],
        }

        for memory in memories:
            category = self.classify(memory)
            classified[category].append(memory)

        return classified

    def batch_score(self, memories: list[Memory]) -> dict[str, float]:
        """Score multiple memories efficiently.

        Args:
            memories: List of memories to score

        Returns:
            Dictionary mapping memory IDs to importance scores
        """
        scores: dict[str, float] = {}

        for memory in memories:
            scores[memory.id] = self.score_importance(memory)

        return scores
