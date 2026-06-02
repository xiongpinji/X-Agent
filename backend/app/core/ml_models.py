"""
Machine Learning Models for Personalization and Recommendations.

Provides:
- User profiling and feature extraction
- Item feature extraction
- Similarity calculations
- Model training and evaluation
- Recommendation scoring
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Any

import numpy as np
from pydantic import BaseModel, Field


class UserFeatures(BaseModel):
    """Extracted user features for ML models."""
    user_id: str
    role: str
    skill_level: str
    activity_level: float  # 0-1, based on usage frequency
    engagement_score: float  # 0-1, based on interaction depth
    preferred_categories: list[str] = Field(default_factory=list)
    preferred_tags: list[str] = Field(default_factory=list)
    avg_rating: float = 0.0
    total_interactions: int = 0
    last_active: datetime = Field(default_factory=lambda: datetime.now(UTC))
    feature_vector: list[float] = Field(default_factory=list)


class ItemFeatures(BaseModel):
    """Extracted item features for ML models."""
    item_id: str
    name: str
    category: str
    tags: list[str] = Field(default_factory=list)
    popularity: float = 0.0  # 0-1
    quality: float = 0.0  # 0-1
    recency: float = 0.0  # 0-1, based on creation date
    complexity: float = 0.5  # 0-1, beginner to advanced
    feature_vector: list[float] = Field(default_factory=list)


class UserProfileBuilder:
    """Build user profiles from interaction data."""

    def __init__(self) -> None:
        self._profiles: dict[str, UserFeatures] = {}
        self._lock = RLock()

    def build_profile(
        self,
        user_id: str,
        role: str,
        skill_level: str,
        interactions: list[dict[str, Any]],
    ) -> UserFeatures:
        """Build user profile from interactions."""
        with self._lock:
            # Calculate activity level
            if interactions:
                recent_interactions = [i for i in interactions if (datetime.now(UTC) - i.get("timestamp", datetime.now(UTC))).days < 30]
                activity_level = min(len(recent_interactions) / 100.0, 1.0)
            else:
                activity_level = 0.0

            # Calculate engagement score
            engagement_score = 0.0
            if interactions:
                explicit_feedback = [i for i in interactions if i.get("feedback_type") == "explicit"]
                conversions = [i for i in interactions if i.get("action_taken")]
                engagement_score = min((len(explicit_feedback) + len(conversions) * 2) / len(interactions), 1.0)

            # Extract preferred categories and tags
            categories: dict[str, int] = {}
            tags: dict[str, int] = {}
            ratings = []

            for interaction in interactions:
                if interaction.get("rating"):
                    ratings.append(interaction["rating"])
                if interaction.get("category"):
                    categories[interaction["category"]] = categories.get(interaction["category"], 0) + 1
                for tag in interaction.get("tags", []):
                    tags[tag] = tags.get(tag, 0) + 1

            preferred_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]
            preferred_tags = sorted(tags.items(), key=lambda x: x[1], reverse=True)[:10]

            avg_rating = sum(ratings) / len(ratings) if ratings else 0.0

            # Build feature vector
            feature_vector = self._build_feature_vector(
                role=role,
                skill_level=skill_level,
                activity_level=activity_level,
                engagement_score=engagement_score,
                avg_rating=avg_rating,
                num_interactions=len(interactions),
            )

            profile = UserFeatures(
                user_id=user_id,
                role=role,
                skill_level=skill_level,
                activity_level=activity_level,
                engagement_score=engagement_score,
                preferred_categories=[cat for cat, _ in preferred_categories],
                preferred_tags=[tag for tag, _ in preferred_tags],
                avg_rating=avg_rating,
                total_interactions=len(interactions),
                feature_vector=feature_vector,
            )

            self._profiles[user_id] = profile
            return profile

    def get_profile(self, user_id: str) -> UserFeatures | None:
        """Get user profile."""
        with self._lock:
            return self._profiles.get(user_id)

    def _build_feature_vector(
        self,
        role: str,
        skill_level: str,
        activity_level: float,
        engagement_score: float,
        avg_rating: float,
        num_interactions: int,
    ) -> list[float]:
        """Build feature vector for user."""
        # Role encoding
        role_encoding = {"developer": 0.0, "analyst": 0.33, "manager": 0.66, "admin": 1.0}
        role_feature = role_encoding.get(role, 0.5)

        # Skill level encoding
        skill_encoding = {"beginner": 0.0, "intermediate": 0.5, "advanced": 1.0}
        skill_feature = skill_encoding.get(skill_level, 0.5)

        # Normalize interaction count
        interaction_feature = min(num_interactions / 1000.0, 1.0)

        # Normalize rating
        rating_feature = avg_rating / 5.0

        return [role_feature, skill_feature, activity_level, engagement_score, interaction_feature, rating_feature]


class ItemProfileBuilder:
    """Build item profiles from metadata and feedback."""

    def __init__(self) -> None:
        self._profiles: dict[str, ItemFeatures] = {}
        self._lock = RLock()

    def build_profile(
        self,
        item_id: str,
        name: str,
        category: str,
        tags: list[str],
        feedback: list[dict[str, Any]],
        created_at: datetime,
        complexity: float = 0.5,
    ) -> ItemFeatures:
        """Build item profile from metadata and feedback."""
        with self._lock:
            # Calculate popularity
            if feedback:
                positive_feedback = [f for f in feedback if f.get("rating", 0) >= 4]
                popularity = min(len(positive_feedback) / max(len(feedback), 1), 1.0)
            else:
                popularity = 0.0

            # Calculate quality
            if feedback:
                ratings = [f.get("rating", 0) for f in feedback if f.get("rating")]
                quality = sum(ratings) / (len(ratings) * 5) if ratings else 0.0
            else:
                quality = 0.0

            # Calculate recency
            days_old = (datetime.now(UTC) - created_at).days
            recency = max(1.0 - (days_old / 365.0), 0.0)

            # Build feature vector
            feature_vector = self._build_feature_vector(
                category=category,
                tags=tags,
                popularity=popularity,
                quality=quality,
                recency=recency,
                complexity=complexity,
            )

            profile = ItemFeatures(
                item_id=item_id,
                name=name,
                category=category,
                tags=tags,
                popularity=popularity,
                quality=quality,
                recency=recency,
                complexity=complexity,
                feature_vector=feature_vector,
            )

            self._profiles[item_id] = profile
            return profile

    def get_profile(self, item_id: str) -> ItemFeatures | None:
        """Get item profile."""
        with self._lock:
            return self._profiles.get(item_id)

    def _build_feature_vector(
        self,
        category: str,
        tags: list[str],
        popularity: float,
        quality: float,
        recency: float,
        complexity: float,
    ) -> list[float]:
        """Build feature vector for item."""
        # Category encoding (simplified)
        category_encoding = {
            "workflow": 0.0,
            "tool": 0.25,
            "template": 0.5,
            "plugin": 0.75,
            "skill": 1.0,
        }
        category_feature = category_encoding.get(category, 0.5)

        # Tag count normalized
        tag_feature = min(len(tags) / 10.0, 1.0)

        return [category_feature, tag_feature, popularity, quality, recency, complexity]


class SimilarityCalculator:
    """Calculate similarity between users and items."""

    @staticmethod
    def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if not vec1 or not vec2:
            return 0.0

        vec1_array = np.array(vec1)
        vec2_array = np.array(vec2)

        dot_product = np.dot(vec1_array, vec2_array)
        norm1 = np.linalg.norm(vec1_array)
        norm2 = np.linalg.norm(vec2_array)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    @staticmethod
    def euclidean_distance(vec1: list[float], vec2: list[float]) -> float:
        """Calculate Euclidean distance between two vectors."""
        if not vec1 or not vec2:
            return float("inf")

        vec1_array = np.array(vec1)
        vec2_array = np.array(vec2)

        distance = np.linalg.norm(vec1_array - vec2_array)
        return float(distance)

    @staticmethod
    def jaccard_similarity(set1: set[str], set2: set[str]) -> float:
        """Calculate Jaccard similarity between two sets."""
        if not set1 and not set2:
            return 1.0

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        if union == 0:
            return 0.0

        return intersection / union


class RecommendationScorer:
    """Score recommendations based on multiple factors."""

    def __init__(self, user_profile_builder: UserProfileBuilder, item_profile_builder: ItemProfileBuilder) -> None:
        self.user_profile_builder = user_profile_builder
        self.item_profile_builder = item_profile_builder
        self.similarity_calculator = SimilarityCalculator()

    def score_item_for_user(
        self,
        user_id: str,
        item_id: str,
        user_profile: UserFeatures | None = None,
        item_profile: ItemFeatures | None = None,
        weights: dict[str, float] | None = None,
    ) -> float:
        """Score an item for a user."""
        if weights is None:
            weights = {
                "similarity": 0.4,
                "popularity": 0.2,
                "quality": 0.2,
                "recency": 0.1,
                "complexity_match": 0.1,
            }

        if not user_profile or not item_profile:
            return 0.0

        # Calculate similarity score
        similarity_score = self.similarity_calculator.cosine_similarity(
            user_profile.feature_vector,
            item_profile.feature_vector,
        )

        # Popularity score
        popularity_score = item_profile.popularity

        # Quality score
        quality_score = item_profile.quality

        # Recency score
        recency_score = item_profile.recency

        # Complexity match score
        skill_to_complexity = {"beginner": 0.3, "intermediate": 0.6, "advanced": 0.9}
        user_complexity = skill_to_complexity.get(user_profile.skill_level, 0.5)
        complexity_diff = abs(user_complexity - item_profile.complexity)
        complexity_match_score = 1.0 - min(complexity_diff, 1.0)

        # Weighted score
        total_score = (
            similarity_score * weights["similarity"]
            + popularity_score * weights["popularity"]
            + quality_score * weights["quality"]
            + recency_score * weights["recency"]
            + complexity_match_score * weights["complexity_match"]
        )

        return total_score


class ModelEvaluator:
    """Evaluate recommendation model performance."""

    @staticmethod
    def calculate_precision(recommendations: list[str], relevant_items: set[str], top_k: int = 5) -> float:
        """Calculate precision@k."""
        if not recommendations or not relevant_items:
            return 0.0

        top_recommendations = set(recommendations[:top_k])
        hits = len(top_recommendations & relevant_items)
        return hits / top_k if top_k > 0 else 0.0

    @staticmethod
    def calculate_recall(recommendations: list[str], relevant_items: set[str], top_k: int = 5) -> float:
        """Calculate recall@k."""
        if not relevant_items:
            return 0.0

        top_recommendations = set(recommendations[:top_k])
        hits = len(top_recommendations & relevant_items)
        return hits / len(relevant_items)

    @staticmethod
    def calculate_ndcg(recommendations: list[str], relevant_items: set[str], top_k: int = 5) -> float:
        """Calculate Normalized Discounted Cumulative Gain."""
        if not recommendations or not relevant_items:
            return 0.0

        # Calculate DCG
        dcg = 0.0
        for i, item in enumerate(recommendations[:top_k]):
            if item in relevant_items:
                dcg += 1.0 / np.log2(i + 2)

        # Calculate IDCG (ideal DCG)
        idcg = 0.0
        for i in range(min(len(relevant_items), top_k)):
            idcg += 1.0 / np.log2(i + 2)

        if idcg == 0:
            return 0.0

        return dcg / idcg

    @staticmethod
    def calculate_mrr(recommendations: list[str], relevant_items: set[str]) -> float:
        """Calculate Mean Reciprocal Rank."""
        for i, item in enumerate(recommendations):
            if item in relevant_items:
                return 1.0 / (i + 1)
        return 0.0

    @staticmethod
    def calculate_map(recommendations: list[list[str]], relevant_items_list: list[set[str]]) -> float:
        """Calculate Mean Average Precision."""
        if not recommendations or not relevant_items_list:
            return 0.0

        aps = []
        for recs, relevant in zip(recommendations, relevant_items_list):
            ap = 0.0
            hits = 0
            for i, item in enumerate(recs):
                if item in relevant:
                    hits += 1
                    ap += hits / (i + 1)
            if relevant:
                ap /= len(relevant)
            aps.append(ap)

        return sum(aps) / len(aps) if aps else 0.0


class ModelMetrics(BaseModel):
    """Model performance metrics."""
    precision_at_5: float = 0.0
    precision_at_10: float = 0.0
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    ndcg_at_5: float = 0.0
    ndcg_at_10: float = 0.0
    mrr: float = 0.0
    map_score: float = 0.0
    coverage: float = 0.0  # Percentage of items recommended
    diversity: float = 0.0  # Average dissimilarity between recommendations
    serendipity: float = 0.0  # Unexpectedness of recommendations


class RecommendationModel:
    """Complete recommendation model."""

    def __init__(self) -> None:
        self.user_profile_builder = UserProfileBuilder()
        self.item_profile_builder = ItemProfileBuilder()
        self.scorer = RecommendationScorer(self.user_profile_builder, self.item_profile_builder)
        self.evaluator = ModelEvaluator()
        self._lock = RLock()

    def train(
        self,
        users: list[dict[str, Any]],
        items: list[dict[str, Any]],
        interactions: list[dict[str, Any]],
    ) -> None:
        """Train recommendation model."""
        with self._lock:
            # Build user profiles
            for user in users:
                user_interactions = [i for i in interactions if i.get("user_id") == user["id"]]
                self.user_profile_builder.build_profile(
                    user_id=user["id"],
                    role=user.get("role", "developer"),
                    skill_level=user.get("skill_level", "intermediate"),
                    interactions=user_interactions,
                )

            # Build item profiles
            for item in items:
                item_feedback = [i for i in interactions if i.get("item_id") == item["id"]]
                self.item_profile_builder.build_profile(
                    item_id=item["id"],
                    name=item.get("name", ""),
                    category=item.get("category", ""),
                    tags=item.get("tags", []),
                    feedback=item_feedback,
                    created_at=item.get("created_at", datetime.now(UTC)),
                    complexity=item.get("complexity", 0.5),
                )

    def evaluate(
        self,
        recommendations: list[list[str]],
        relevant_items_list: list[set[str]],
    ) -> ModelMetrics:
        """Evaluate model performance."""
        with self._lock:
            metrics = ModelMetrics(
                precision_at_5=self.evaluator.calculate_precision(recommendations[0], relevant_items_list[0], 5)
                if recommendations and relevant_items_list
                else 0.0,
                precision_at_10=self.evaluator.calculate_precision(recommendations[0], relevant_items_list[0], 10)
                if recommendations and relevant_items_list
                else 0.0,
                recall_at_5=self.evaluator.calculate_recall(recommendations[0], relevant_items_list[0], 5)
                if recommendations and relevant_items_list
                else 0.0,
                recall_at_10=self.evaluator.calculate_recall(recommendations[0], relevant_items_list[0], 10)
                if recommendations and relevant_items_list
                else 0.0,
                ndcg_at_5=self.evaluator.calculate_ndcg(recommendations[0], relevant_items_list[0], 5)
                if recommendations and relevant_items_list
                else 0.0,
                ndcg_at_10=self.evaluator.calculate_ndcg(recommendations[0], relevant_items_list[0], 10)
                if recommendations and relevant_items_list
                else 0.0,
                mrr=self.evaluator.calculate_mrr(recommendations[0], relevant_items_list[0])
                if recommendations and relevant_items_list
                else 0.0,
                map_score=self.evaluator.calculate_map(recommendations, relevant_items_list),
            )
            return metrics


# Global model instance
recommendation_model = RecommendationModel()
