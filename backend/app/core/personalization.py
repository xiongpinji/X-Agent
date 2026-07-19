"""
Personalization and Recommendation System for X-Agent

This module provides:
1. User preference storage and management
2. Recommendation engine with multiple strategies
3. Personalized UI configuration
4. Machine learning models for recommendations
5. A/B testing framework
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from enum import Enum
from threading import RLock
from typing import Any
from uuid import uuid4

import numpy as np
from pydantic import BaseModel, Field


class PreferenceType(str, Enum):
    """Types of user preferences."""
    THEME = "theme"
    LAYOUT = "layout"
    SHORTCUTS = "shortcuts"
    WIDGETS = "widgets"
    WORKSPACE = "workspace"
    NOTIFICATIONS = "notifications"
    LANGUAGE = "language"
    ACCESSIBILITY = "accessibility"


class FeedbackType(str, Enum):
    """Types of user feedback."""
    IMPLICIT = "implicit"  # Click, view, dwell time
    EXPLICIT = "explicit"  # Like, dislike, rating
    CONVERSION = "conversion"  # Completed action


class RecommendationType(str, Enum):
    """Types of recommendations."""
    WORKFLOW = "workflow"
    TOOL = "tool"
    TEMPLATE = "template"
    PLUGIN = "plugin"
    SKILL = "skill"


class UserPreference(BaseModel):
    """User preference record."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    preference_type: PreferenceType
    key: str
    value: dict[str, Any]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class UserProfile(BaseModel):
    """User profile for personalization."""
    user_id: str
    role: str = "developer"
    skill_level: str = "intermediate"  # beginner, intermediate, advanced
    preferences: dict[str, Any] = Field(default_factory=dict)
    usage_patterns: dict[str, Any] = Field(default_factory=dict)
    interests: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class UserFeedback(BaseModel):
    """User feedback for recommendations."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    item_id: str
    item_type: RecommendationType
    feedback_type: FeedbackType
    rating: float | None = None  # 0-5 for explicit feedback
    dwell_time: int | None = None  # seconds for implicit feedback
    action_taken: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RecommendationItem(BaseModel):
    """Item to be recommended."""
    id: str
    name: str
    description: str
    item_type: RecommendationType
    category: str
    tags: list[str] = Field(default_factory=list)
    popularity_score: float = 0.0
    quality_score: float = 0.0
    features: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Recommendation(BaseModel):
    """Recommendation result."""
    item_id: str
    item_name: str
    item_type: RecommendationType
    score: float
    reason: str
    algorithm: str
    confidence: float


class ThemePreference(BaseModel):
    """Theme customization."""
    name: str
    primary_color: str = "#007AFF"
    secondary_color: str = "#5AC8FA"
    background_color: str = "#FFFFFF"
    text_color: str = "#000000"
    font_family: str = "system-ui"
    font_size: int = 14
    dark_mode: bool = False


class LayoutPreference(BaseModel):
    """Layout customization."""
    sidebar_position: str = "left"  # left, right, hidden
    sidebar_width: int = 250
    compact_mode: bool = False
    show_minimap: bool = True
    show_breadcrumb: bool = True
    default_view: str = "grid"  # grid, list, kanban


class ShortcutPreference(BaseModel):
    """Keyboard shortcuts customization."""
    shortcuts: dict[str, str] = Field(default_factory=dict)
    vim_mode: bool = False
    emacs_mode: bool = False


class WidgetPreference(BaseModel):
    """Dashboard widget customization."""
    widgets: list[dict[str, Any]] = Field(default_factory=list)
    widget_order: list[str] = Field(default_factory=list)
    widget_sizes: dict[str, dict[str, int]] = Field(default_factory=dict)


class WorkspacePreference(BaseModel):
    """Workspace state persistence."""
    workspace_id: str
    layout: dict[str, Any] = Field(default_factory=dict)
    open_tabs: list[str] = Field(default_factory=list)
    active_tab: str | None = None
    scroll_positions: dict[str, int] = Field(default_factory=dict)
    last_accessed: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PreferenceStore:
    """Store for user preferences."""

    def __init__(self) -> None:
        self._preferences: dict[str, UserPreference] = {}
        self._profiles: dict[str, UserProfile] = {}
        self._lock = RLock()

    def save_preference(self, user_id: str, preference_type: PreferenceType, key: str, value: dict[str, Any]) -> UserPreference:
        """Save user preference."""
        with self._lock:
            pref_id = f"{user_id}:{preference_type}:{key}"
            pref = UserPreference(
                id=pref_id,
                user_id=user_id,
                preference_type=preference_type,
                key=key,
                value=value,
            )
            self._preferences[pref_id] = pref
            return pref

    def get_preference(self, user_id: str, preference_type: PreferenceType, key: str) -> UserPreference | None:
        """Get user preference."""
        with self._lock:
            pref_id = f"{user_id}:{preference_type}:{key}"
            return self._preferences.get(pref_id)

    def get_all_preferences(self, user_id: str, preference_type: PreferenceType | None = None) -> list[UserPreference]:
        """Get all preferences for a user."""
        with self._lock:
            prefs = [p for p in self._preferences.values() if p.user_id == user_id]
            if preference_type:
                prefs = [p for p in prefs if p.preference_type == preference_type]
            return prefs

    def delete_preference(self, user_id: str, preference_type: PreferenceType, key: str) -> bool:
        """Delete user preference."""
        with self._lock:
            pref_id = f"{user_id}:{preference_type}:{key}"
            if pref_id in self._preferences:
                del self._preferences[pref_id]
                return True
            return False

    def get_or_create_profile(self, user_id: str, role: str = "developer") -> UserProfile:
        """Get or create user profile."""
        with self._lock:
            if user_id not in self._profiles:
                self._profiles[user_id] = UserProfile(user_id=user_id, role=role)
            return self._profiles[user_id]

    def update_profile(self, user_id: str, **kwargs: Any) -> UserProfile:
        """Update user profile."""
        with self._lock:
            profile = self.get_or_create_profile(user_id)
            for key, value in kwargs.items():
                if hasattr(profile, key):
                    setattr(profile, key, value)
            profile.updated_at = datetime.now(UTC)
            self._profiles[user_id] = profile
            return profile


class FeedbackStore:
    """Store for user feedback."""

    def __init__(self) -> None:
        self._feedback: dict[str, UserFeedback] = {}
        self._lock = RLock()

    def record_feedback(
        self,
        user_id: str,
        item_id: str,
        item_type: RecommendationType,
        feedback_type: FeedbackType,
        rating: float | None = None,
        dwell_time: int | None = None,
        action_taken: bool = False,
    ) -> UserFeedback:
        """Record user feedback."""
        with self._lock:
            feedback = UserFeedback(
                user_id=user_id,
                item_id=item_id,
                item_type=item_type,
                feedback_type=feedback_type,
                rating=rating,
                dwell_time=dwell_time,
                action_taken=action_taken,
            )
            self._feedback[feedback.id] = feedback
            return feedback

    def get_user_feedback(self, user_id: str, item_type: RecommendationType | None = None) -> list[UserFeedback]:
        """Get feedback for a user."""
        with self._lock:
            feedback = [f for f in self._feedback.values() if f.user_id == user_id]
            if item_type:
                feedback = [f for f in feedback if f.item_type == item_type]
            return feedback

    def get_item_feedback(self, item_id: str) -> list[UserFeedback]:
        """Get feedback for an item."""
        with self._lock:
            return [f for f in self._feedback.values() if f.item_id == item_id]

    def get_recent_feedback(self, user_id: str, days: int = 30) -> list[UserFeedback]:
        """Get recent feedback for a user."""
        with self._lock:
            cutoff = datetime.now(UTC) - timedelta(days=days)
            return [f for f in self._feedback.values() if f.user_id == user_id and f.created_at >= cutoff]


class ItemCatalog:
    """Catalog of items for recommendation."""

    def __init__(self) -> None:
        self._items: dict[str, RecommendationItem] = {}
        self._lock = RLock()

    def add_item(self, item: RecommendationItem) -> None:
        """Add item to catalog."""
        with self._lock:
            self._items[item.id] = item

    def get_item(self, item_id: str) -> RecommendationItem | None:
        """Get item from catalog."""
        with self._lock:
            return self._items.get(item_id)

    def get_items_by_type(self, item_type: RecommendationType) -> list[RecommendationItem]:
        """Get items by type."""
        with self._lock:
            return [item for item in self._items.values() if item.item_type == item_type]

    def get_items_by_category(self, category: str) -> list[RecommendationItem]:
        """Get items by category."""
        with self._lock:
            return [item for item in self._items.values() if item.category == category]

    def get_items_by_tags(self, tags: list[str]) -> list[RecommendationItem]:
        """Get items by tags."""
        with self._lock:
            return [item for item in self._items.values() if any(tag in item.tags for tag in tags)]

    def update_item_scores(self, item_id: str, popularity_score: float | None = None, quality_score: float | None = None) -> None:
        """Update item scores."""
        with self._lock:
            if item_id in self._items:
                item = self._items[item_id]
                if popularity_score is not None:
                    item.popularity_score = popularity_score
                if quality_score is not None:
                    item.quality_score = quality_score


class RecommendationEngine:
    """Recommendation engine with multiple strategies."""

    def __init__(self, preference_store: PreferenceStore, feedback_store: FeedbackStore, catalog: ItemCatalog) -> None:
        self.preference_store = preference_store
        self.feedback_store = feedback_store
        self.catalog = catalog
        self._lock = RLock()

    def recommend_collaborative_filtering(
        self, user_id: str, item_type: RecommendationType, top_k: int = 5
    ) -> list[Recommendation]:
        """Collaborative filtering: recommend based on similar users."""
        user_feedback = self.feedback_store.get_user_feedback(user_id, item_type)
        if not user_feedback:
            return self._recommend_popular(item_type, top_k)

        # Get items user has interacted with
        user_items = {f.item_id for f in user_feedback}

        # Find similar users (users who liked similar items)
        similar_users = self._find_similar_users(user_id, user_items)

        # Get items liked by similar users but not by current user
        recommendations: dict[str, float] = {}
        for similar_user in similar_users:
            similar_feedback = self.feedback_store.get_user_feedback(similar_user, item_type)
            for feedback in similar_feedback:
                if feedback.item_id not in user_items and feedback.rating and feedback.rating >= 4:
                    if feedback.item_id not in recommendations:
                        recommendations[feedback.item_id] = 0
                    recommendations[feedback.item_id] += feedback.rating

        # Sort and return top recommendations
        sorted_items = sorted(recommendations.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [
            Recommendation(
                item_id=item_id,
                item_name=self.catalog.get_item(item_id).name if self.catalog.get_item(item_id) else item_id,
                item_type=item_type,
                score=score / 5.0,
                reason="Recommended by users with similar interests",
                algorithm="collaborative_filtering",
                confidence=min(score / 20.0, 1.0),
            )
            for item_id, score in sorted_items
        ]

    def recommend_content_based(self, user_id: str, item_type: RecommendationType, top_k: int = 5) -> list[Recommendation]:
        """Content-based filtering: recommend based on item similarity."""
        user_feedback = self.feedback_store.get_user_feedback(user_id, item_type)
        if not user_feedback:
            return self._recommend_popular(item_type, top_k)

        # Get items user has rated highly
        liked_items = [f.item_id for f in user_feedback if f.rating and f.rating >= 4]
        if not liked_items:
            return self._recommend_popular(item_type, top_k)

        # Get features of liked items
        liked_features = []
        for item_id in liked_items:
            item = self.catalog.get_item(item_id)
            if item:
                liked_features.append(item.features)

        # Find similar items
        all_items = self.catalog.get_items_by_type(item_type)
        recommendations: dict[str, float] = {}

        for item in all_items:
            if item.id not in liked_items:
                similarity = self._calculate_similarity(item.features, liked_features)
                if similarity > 0.5:
                    recommendations[item.id] = similarity

        # Sort and return top recommendations
        sorted_items = sorted(recommendations.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [
            Recommendation(
                item_id=item_id,
                item_name=self.catalog.get_item(item_id).name if self.catalog.get_item(item_id) else item_id,
                item_type=item_type,
                score=score,
                reason="Similar to items you liked",
                algorithm="content_based",
                confidence=score,
            )
            for item_id, score in sorted_items
        ]

    def recommend_personalized(self, user_id: str, item_type: RecommendationType, top_k: int = 5) -> list[Recommendation]:
        """Personalized recommendation combining multiple strategies."""
        profile = self.preference_store.get_or_create_profile(user_id)

        # Get recommendations from different strategies
        collab_recs = self.recommend_collaborative_filtering(user_id, item_type, top_k * 2)
        content_recs = self.recommend_content_based(user_id, item_type, top_k * 2)

        # Combine and rank recommendations
        combined: dict[str, dict[str, Any]] = {}
        for rec in collab_recs:
            combined[rec.item_id] = {
                "score": rec.score * 0.6,
                "item_name": rec.item_name,
                "item_type": rec.item_type,
                "reason": rec.reason,
                "algorithm": "hybrid",
            }

        for rec in content_recs:
            if rec.item_id in combined:
                combined[rec.item_id]["score"] += rec.score * 0.4
            else:
                combined[rec.item_id] = {
                    "score": rec.score * 0.4,
                    "item_name": rec.item_name,
                    "item_type": rec.item_type,
                    "reason": rec.reason,
                    "algorithm": "hybrid",
                }

        # Apply user profile boost
        for item_id, data in combined.items():
            item = self.catalog.get_item(item_id)
            if item:
                # Boost based on user interests
                if any(tag in profile.interests for tag in item.tags):
                    data["score"] *= 1.2

                # Boost based on popularity
                data["score"] += item.popularity_score * 0.1

        # Sort and return top recommendations
        sorted_items = sorted(combined.items(), key=lambda x: x[1]["score"], reverse=True)[:top_k]
        return [
            Recommendation(
                item_id=item_id,
                item_name=data["item_name"],
                item_type=data["item_type"],
                score=min(data["score"], 1.0),
                reason=data["reason"],
                algorithm=data["algorithm"],
                confidence=min(data["score"], 1.0),
            )
            for item_id, data in sorted_items
        ]

    def _recommend_popular(self, item_type: RecommendationType, top_k: int = 5) -> list[Recommendation]:
        """Recommend popular items (cold start)."""
        items = self.catalog.get_items_by_type(item_type)
        sorted_items = sorted(items, key=lambda x: x.popularity_score, reverse=True)[:top_k]
        return [
            Recommendation(
                item_id=item.id,
                item_name=item.name,
                item_type=item.item_type,
                score=item.popularity_score,
                reason="Popular with other users",
                algorithm="popularity",
                confidence=0.5,
            )
            for item in sorted_items
        ]

    def _find_similar_users(self, user_id: str, user_items: set[str], top_k: int = 5) -> list[str]:
        """Find users with similar interests."""
        all_feedback = self.feedback_store._feedback.values()
        user_similarities: dict[str, float] = {}

        for feedback in all_feedback:
            if feedback.user_id != user_id:
                # Calculate Jaccard similarity
                other_items = {f.item_id for f in self.feedback_store.get_user_feedback(feedback.user_id)}
                intersection = len(user_items & other_items)
                union = len(user_items | other_items)
                if union > 0:
                    similarity = intersection / union
                    if similarity > 0:
                        user_similarities[feedback.user_id] = similarity

        sorted_users = sorted(user_similarities.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [user for user, _ in sorted_users]

    def _calculate_similarity(self, features1: dict[str, Any], features_list: list[dict[str, Any]]) -> float:
        """Calculate cosine similarity between features."""
        if not features_list:
            return 0.0

        similarities = []
        for features2 in features_list:
            # 取两边特征 key 的并集构建向量,缺失维度填 0。
            # 旧实现用 features1[key] == features2[key] 精确相等计数,
            # 对连续数值特征(如 complexity=0.5/0.6/…)几乎永不相等 → 相似度恒 0,
            # 与 docstring 声称的 cosine similarity 不符。这里改为真正的余弦相似度。
            keys = sorted(set(features1.keys()) | set(features2.keys()))
            v1: list[float] = []
            v2: list[float] = []
            for key in keys:
                a = features1.get(key, 0)
                b = features2.get(key, 0)
                try:
                    v1.append(float(a))
                    v2.append(float(b))
                except (TypeError, ValueError):
                    # 非数值特征退化为相等性匹配
                    v1.append(1.0 if a == b else 0.0)
                    v2.append(1.0)

            if not v1:
                similarities.append(0.0)
                continue

            arr1 = np.array(v1)
            arr2 = np.array(v2)
            denom = float(np.linalg.norm(arr1) * np.linalg.norm(arr2))
            similarities.append(float(np.dot(arr1, arr2) / denom) if denom else 0.0)

        return sum(similarities) / len(similarities) if similarities else 0.0


class ABTestManager:
    """A/B testing for recommendations."""

    def __init__(self) -> None:
        self._tests: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    def create_test(self, test_id: str, variants: dict[str, list[Recommendation]], user_id: str) -> str:
        """Create A/B test."""
        with self._lock:
            variant = "A" if hash(user_id) % 2 == 0 else "B"
            self._tests[f"{test_id}:{user_id}"] = {
                "test_id": test_id,
                "user_id": user_id,
                "variant": variant,
                "recommendations": variants[variant],
                "created_at": datetime.now(UTC),
                "conversions": 0,
            }
            return variant

    def record_conversion(self, test_id: str, user_id: str) -> None:
        """Record conversion for A/B test."""
        with self._lock:
            key = f"{test_id}:{user_id}"
            if key in self._tests:
                self._tests[key]["conversions"] += 1

    def get_test_results(self, test_id: str) -> dict[str, Any]:
        """Get A/B test results."""
        with self._lock:
            tests = [t for t in self._tests.values() if t["test_id"] == test_id]
            if not tests:
                return {}

            variant_a = [t for t in tests if t["variant"] == "A"]
            variant_b = [t for t in tests if t["variant"] == "B"]

            return {
                "test_id": test_id,
                "variant_a": {
                    "count": len(variant_a),
                    "conversions": sum(t["conversions"] for t in variant_a),
                    "conversion_rate": sum(t["conversions"] for t in variant_a) / len(variant_a) if variant_a else 0,
                },
                "variant_b": {
                    "count": len(variant_b),
                    "conversions": sum(t["conversions"] for t in variant_b),
                    "conversion_rate": sum(t["conversions"] for t in variant_b) / len(variant_b) if variant_b else 0,
                },
            }


# Global instances
preference_store = PreferenceStore()
feedback_store = FeedbackStore()
item_catalog = ItemCatalog()
recommendation_engine = RecommendationEngine(preference_store, feedback_store, item_catalog)
ab_test_manager = ABTestManager()
