"""
Test suite for personalization and recommendation system.

Tests:
- Preference storage and retrieval
- Recommendation algorithms
- User profiling
- A/B testing
- Model evaluation
"""

from __future__ import annotations

import pytest
from datetime import UTC, datetime

from backend.app.core.personalization import (
    FeedbackType,
    ItemCatalog,
    PreferenceStore,
    PreferenceType,
    RecommendationEngine,
    RecommendationItem,
    RecommendationType,
    FeedbackStore,
    ABTestManager,
)
from backend.app.core.ml_models import (
    UserProfileBuilder,
    ItemProfileBuilder,
    SimilarityCalculator,
    RecommendationScorer,
    ModelEvaluator,
    RecommendationModel,
)


class TestPreferenceStore:
    """Test preference storage."""

    def test_save_and_get_preference(self) -> None:
        """Test saving and retrieving preferences."""
        store = PreferenceStore()
        user_id = "user1"
        pref_type = PreferenceType.THEME
        key = "default"
        value = {"dark_mode": True}

        # Save preference
        pref = store.save_preference(user_id, pref_type, key, value)
        assert pref.user_id == user_id
        assert pref.preference_type == pref_type
        assert pref.key == key
        assert pref.value == value

        # Get preference
        retrieved = store.get_preference(user_id, pref_type, key)
        assert retrieved is not None
        assert retrieved.value == value

    def test_get_all_preferences(self) -> None:
        """Test getting all preferences for a user."""
        store = PreferenceStore()
        user_id = "user1"

        # Save multiple preferences
        store.save_preference(user_id, PreferenceType.THEME, "default", {"dark_mode": True})
        store.save_preference(user_id, PreferenceType.LAYOUT, "default", {"sidebar_position": "left"})

        # Get all preferences
        all_prefs = store.get_all_preferences(user_id)
        assert len(all_prefs) == 2

        # Get preferences by type
        theme_prefs = store.get_all_preferences(user_id, PreferenceType.THEME)
        assert len(theme_prefs) == 1
        assert theme_prefs[0].preference_type == PreferenceType.THEME

    def test_delete_preference(self) -> None:
        """Test deleting preferences."""
        store = PreferenceStore()
        user_id = "user1"
        pref_type = PreferenceType.THEME
        key = "default"

        # Save and delete
        store.save_preference(user_id, pref_type, key, {"dark_mode": True})
        success = store.delete_preference(user_id, pref_type, key)
        assert success

        # Verify deletion
        retrieved = store.get_preference(user_id, pref_type, key)
        assert retrieved is None

    def test_user_profile_management(self) -> None:
        """Test user profile creation and updates."""
        store = PreferenceStore()
        user_id = "user1"

        # Get or create profile
        profile = store.get_or_create_profile(user_id, "developer")
        assert profile.user_id == user_id
        assert profile.role == "developer"

        # Update profile
        updated = store.update_profile(user_id, skill_level="advanced", interests=["AI", "ML"])
        assert updated.skill_level == "advanced"
        assert updated.interests == ["AI", "ML"]


class TestFeedbackStore:
    """Test feedback storage."""

    def test_record_feedback(self) -> None:
        """Test recording user feedback."""
        store = FeedbackStore()
        user_id = "user1"
        item_id = "item1"

        feedback = store.record_feedback(
            user_id=user_id,
            item_id=item_id,
            item_type=RecommendationType.WORKFLOW,
            feedback_type=FeedbackType.EXPLICIT,
            rating=4.5,
        )

        assert feedback.user_id == user_id
        assert feedback.item_id == item_id
        assert feedback.rating == 4.5

    def test_get_user_feedback(self) -> None:
        """Test retrieving user feedback."""
        store = FeedbackStore()
        user_id = "user1"

        # Record multiple feedback
        store.record_feedback(user_id, "item1", RecommendationType.WORKFLOW, FeedbackType.EXPLICIT, rating=4.0)
        store.record_feedback(user_id, "item2", RecommendationType.TOOL, FeedbackType.EXPLICIT, rating=3.5)

        # Get all feedback
        all_feedback = store.get_user_feedback(user_id)
        assert len(all_feedback) == 2

        # Get feedback by type
        workflow_feedback = store.get_user_feedback(user_id, RecommendationType.WORKFLOW)
        assert len(workflow_feedback) == 1

    def test_get_item_feedback(self) -> None:
        """Test retrieving feedback for an item."""
        store = FeedbackStore()
        item_id = "item1"

        # Record feedback from multiple users
        store.record_feedback("user1", item_id, RecommendationType.WORKFLOW, FeedbackType.EXPLICIT, rating=4.0)
        store.record_feedback("user2", item_id, RecommendationType.WORKFLOW, FeedbackType.EXPLICIT, rating=3.5)

        # Get item feedback
        item_feedback = store.get_item_feedback(item_id)
        assert len(item_feedback) == 2


class TestItemCatalog:
    """Test item catalog."""

    def test_add_and_get_item(self) -> None:
        """Test adding and retrieving items."""
        catalog = ItemCatalog()
        item = RecommendationItem(
            id="item1",
            name="Test Workflow",
            description="A test workflow",
            item_type=RecommendationType.WORKFLOW,
            category="automation",
            tags=["test", "automation"],
        )

        catalog.add_item(item)
        retrieved = catalog.get_item("item1")
        assert retrieved is not None
        assert retrieved.name == "Test Workflow"

    def test_get_items_by_type(self) -> None:
        """Test getting items by type."""
        catalog = ItemCatalog()

        # Add items of different types
        catalog.add_item(
            RecommendationItem(
                id="item1",
                name="Workflow 1",
                description="",
                item_type=RecommendationType.WORKFLOW,
                category="automation",
            )
        )
        catalog.add_item(
            RecommendationItem(
                id="item2",
                name="Tool 1",
                description="",
                item_type=RecommendationType.TOOL,
                category="utility",
            )
        )

        # Get by type
        workflows = catalog.get_items_by_type(RecommendationType.WORKFLOW)
        assert len(workflows) == 1
        assert workflows[0].item_type == RecommendationType.WORKFLOW


class TestRecommendationEngine:
    """Test recommendation engine."""

    def test_collaborative_filtering(self) -> None:
        """Test collaborative filtering recommendations."""
        preference_store = PreferenceStore()
        feedback_store = FeedbackStore()
        catalog = ItemCatalog()
        engine = RecommendationEngine(preference_store, feedback_store, catalog)

        # Add items to catalog
        for i in range(5):
            catalog.add_item(
                RecommendationItem(
                    id=f"item{i}",
                    name=f"Item {i}",
                    description="",
                    item_type=RecommendationType.WORKFLOW,
                    category="test",
                    popularity_score=0.5 + i * 0.1,
                )
            )

        # Record feedback from user1
        feedback_store.record_feedback("user1", "item0", RecommendationType.WORKFLOW, FeedbackType.EXPLICIT, rating=5.0)
        feedback_store.record_feedback("user1", "item1", RecommendationType.WORKFLOW, FeedbackType.EXPLICIT, rating=4.0)

        # Record feedback from user2 (similar to user1)
        feedback_store.record_feedback("user2", "item0", RecommendationType.WORKFLOW, FeedbackType.EXPLICIT, rating=5.0)
        feedback_store.record_feedback("user2", "item1", RecommendationType.WORKFLOW, FeedbackType.EXPLICIT, rating=4.0)
        feedback_store.record_feedback("user2", "item2", RecommendationType.WORKFLOW, FeedbackType.EXPLICIT, rating=4.5)

        # Get recommendations for user1
        recommendations = engine.recommend_collaborative_filtering("user1", RecommendationType.WORKFLOW, top_k=3)
        assert len(recommendations) > 0
        assert recommendations[0].algorithm == "collaborative_filtering"

    def test_content_based_filtering(self) -> None:
        """Test content-based filtering recommendations."""
        preference_store = PreferenceStore()
        feedback_store = FeedbackStore()
        catalog = ItemCatalog()
        engine = RecommendationEngine(preference_store, feedback_store, catalog)

        # Add items with features
        for i in range(5):
            catalog.add_item(
                RecommendationItem(
                    id=f"item{i}",
                    name=f"Item {i}",
                    description="",
                    item_type=RecommendationType.WORKFLOW,
                    category="test",
                    tags=["automation", "workflow"] if i < 3 else ["manual", "task"],
                    features={"complexity": 0.5 + i * 0.1},
                )
            )

        # Record feedback
        feedback_store.record_feedback("user1", "item0", RecommendationType.WORKFLOW, FeedbackType.EXPLICIT, rating=5.0)
        feedback_store.record_feedback("user1", "item1", RecommendationType.WORKFLOW, FeedbackType.EXPLICIT, rating=4.5)

        # Get recommendations
        recommendations = engine.recommend_content_based("user1", RecommendationType.WORKFLOW, top_k=3)
        assert len(recommendations) > 0
        assert recommendations[0].algorithm == "content_based"

    def test_personalized_recommendations(self) -> None:
        """Test personalized recommendations."""
        preference_store = PreferenceStore()
        feedback_store = FeedbackStore()
        catalog = ItemCatalog()
        engine = RecommendationEngine(preference_store, feedback_store, catalog)

        # Setup
        preference_store.get_or_create_profile("user1", "developer")
        preference_store.update_profile("user1", interests=["AI", "ML"])

        for i in range(5):
            catalog.add_item(
                RecommendationItem(
                    id=f"item{i}",
                    name=f"Item {i}",
                    description="",
                    item_type=RecommendationType.WORKFLOW,
                    category="test",
                    tags=["AI", "ML"] if i < 3 else ["other"],
                    popularity_score=0.5,
                )
            )

        # Get recommendations
        recommendations = engine.recommend_personalized("user1", RecommendationType.WORKFLOW, top_k=3)
        assert len(recommendations) > 0
        assert recommendations[0].algorithm == "hybrid"


class TestABTestManager:
    """Test A/B testing."""

    def test_create_and_record_test(self) -> None:
        """Test creating and recording A/B tests."""
        manager = ABTestManager()

        variants = {
            "A": [],
            "B": [],
        }

        # Create test
        variant = manager.create_test("test1", variants, "user1")
        assert variant in ["A", "B"]

        # Record conversion
        manager.record_conversion("test1", "user1")

        # Get results
        results = manager.get_test_results("test1")
        assert results["test_id"] == "test1"


class TestUserProfileBuilder:
    """Test user profile building."""

    def test_build_profile(self) -> None:
        """Test building user profile."""
        builder = UserProfileBuilder()

        interactions = [
            {"timestamp": datetime.now(UTC), "feedback_type": "explicit", "rating": 5.0, "category": "workflow", "tags": ["AI"]},
            {"timestamp": datetime.now(UTC), "feedback_type": "explicit", "rating": 4.0, "category": "tool", "tags": ["ML"]},
        ]

        profile = builder.build_profile("user1", "developer", "intermediate", interactions)
        assert profile.user_id == "user1"
        assert profile.role == "developer"
        assert profile.skill_level == "intermediate"
        assert len(profile.feature_vector) == 6


class TestItemProfileBuilder:
    """Test item profile building."""

    def test_build_profile(self) -> None:
        """Test building item profile."""
        builder = ItemProfileBuilder()

        feedback = [
            {"rating": 5.0},
            {"rating": 4.0},
        ]

        profile = builder.build_profile(
            "item1",
            "Test Item",
            "workflow",
            ["AI", "ML"],
            feedback,
            datetime.now(UTC),
        )
        assert profile.item_id == "item1"
        assert profile.name == "Test Item"
        assert len(profile.feature_vector) == 6


class TestSimilarityCalculator:
    """Test similarity calculations."""

    def test_cosine_similarity(self) -> None:
        """Test cosine similarity."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]
        similarity = SimilarityCalculator.cosine_similarity(vec1, vec2)
        assert similarity == pytest.approx(1.0)

    def test_euclidean_distance(self) -> None:
        """Test Euclidean distance."""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 1.0, 1.0]
        distance = SimilarityCalculator.euclidean_distance(vec1, vec2)
        assert distance == pytest.approx(1.732, rel=0.01)

    def test_jaccard_similarity(self) -> None:
        """Test Jaccard similarity."""
        set1 = {"a", "b", "c"}
        set2 = {"b", "c", "d"}
        similarity = SimilarityCalculator.jaccard_similarity(set1, set2)
        assert similarity == pytest.approx(0.5)


class TestModelEvaluator:
    """Test model evaluation metrics."""

    def test_precision(self) -> None:
        """Test precision calculation."""
        recommendations = ["item1", "item2", "item3", "item4", "item5"]
        relevant = {"item1", "item3"}
        precision = ModelEvaluator.calculate_precision(recommendations, relevant, top_k=5)
        assert precision == pytest.approx(0.4)

    def test_recall(self) -> None:
        """Test recall calculation."""
        recommendations = ["item1", "item2", "item3", "item4", "item5"]
        relevant = {"item1", "item3", "item6"}
        recall = ModelEvaluator.calculate_recall(recommendations, relevant, top_k=5)
        assert recall == pytest.approx(2.0 / 3.0, rel=0.01)

    def test_ndcg(self) -> None:
        """Test NDCG calculation."""
        recommendations = ["item1", "item2", "item3"]
        relevant = {"item1", "item3"}
        ndcg = ModelEvaluator.calculate_ndcg(recommendations, relevant, top_k=3)
        assert ndcg > 0.0

    def test_mrr(self) -> None:
        """Test MRR calculation."""
        recommendations = ["item1", "item2", "item3"]
        relevant = {"item2"}
        mrr = ModelEvaluator.calculate_mrr(recommendations, relevant)
        assert mrr == pytest.approx(0.5)


class TestRecommendationModel:
    """Test complete recommendation model."""

    def test_train_and_evaluate(self) -> None:
        """Test training and evaluating model."""
        model = RecommendationModel()

        users = [
            {"id": "user1", "role": "developer", "skill_level": "intermediate"},
            {"id": "user2", "role": "analyst", "skill_level": "advanced"},
        ]

        items = [
            {"id": "item1", "name": "Workflow 1", "category": "automation", "tags": ["AI"], "complexity": 0.5},
            {"id": "item2", "name": "Tool 1", "category": "utility", "tags": ["ML"], "complexity": 0.7},
        ]

        interactions = [
            {"user_id": "user1", "item_id": "item1", "rating": 5.0},
            {"user_id": "user1", "item_id": "item2", "rating": 3.0},
            {"user_id": "user2", "item_id": "item1", "rating": 4.0},
        ]

        # Train model
        model.train(users, items, interactions)

        # Verify profiles were built
        user_profile = model.user_profile_builder.get_profile("user1")
        assert user_profile is not None
        assert user_profile.user_id == "user1"

        item_profile = model.item_profile_builder.get_profile("item1")
        assert item_profile is not None
        assert item_profile.item_id == "item1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
