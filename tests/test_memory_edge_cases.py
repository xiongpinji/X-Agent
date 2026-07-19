"""Edge case and error scenario tests for Memory module."""

import pytest
from datetime import datetime, UTC
from pathlib import Path
from backend.app.core.memory import (
    MemoryItem,
    MemoryScope,
    MemoryRevision,
    SessionRecord,
    MemorySearchHit,
    MemoryConsolidationResult,
    MemoryUpdateResult,
    MemoryRollbackResult,
    MemoryPollutionReport,
    MemoryExportBundle,
    MemorySystem,
)
from backend.app.core.contracts import RunContext


class TestMemoryItem:
    """Test MemoryItem model edge cases."""

    def test_memory_item_default_values(self):
        """Test MemoryItem with default values."""
        item = MemoryItem(
            tenant_id="tenant-1",
            content="test content",
            layer=5,
        )
        assert item.id is not None
        assert item.tenant_id == "tenant-1"
        assert item.content == "test content"
        assert item.layer == 5
        assert item.importance == 0.5
        assert item.tags == []
        assert item.metadata == {}
        assert item.embedding == []
        assert item.created_at is not None

    def test_memory_item_with_all_fields(self):
        """Test MemoryItem with all fields populated."""
        now = datetime.now(UTC)
        item = MemoryItem(
            id="item-1",
            tenant_id="tenant-1",
            agent_id="agent-1",
            session_id="session-1",
            scope=MemoryScope(owner_agent_id="agent-1"),
            content="test content",
            layer=7,
            importance=0.8,
            tags=["tag1", "tag2"],
            metadata={"key": "value"},
            embedding=[0.1, 0.2, 0.3],
            created_at=now,
        )
        assert item.id == "item-1"
        assert item.agent_id == "agent-1"
        assert item.session_id == "session-1"
        assert item.importance == 0.8
        assert len(item.tags) == 2
        assert item.metadata["key"] == "value"

    def test_memory_item_layer_validation(self):
        """Test MemoryItem layer validation."""
        # Valid layers
        for layer in range(1, 11):
            item = MemoryItem(
                tenant_id="tenant-1",
                content="test",
                layer=layer,
            )
            assert item.layer == layer

    def test_memory_item_importance_validation(self):
        """Test MemoryItem importance validation."""
        # Valid importance values
        for importance in [0.0, 0.5, 1.0]:
            item = MemoryItem(
                tenant_id="tenant-1",
                content="test",
                layer=5,
                importance=importance,
            )
            assert item.importance == importance

    def test_memory_item_with_revisions(self):
        """Test MemoryItem with revision history."""
        revision = MemoryRevision(
            memory_id="item-1",
            actor_agent_id="agent-1",
            summary="Updated content",
        )
        item = MemoryItem(
            id="item-1",
            tenant_id="tenant-1",
            content="test content",
            layer=5,
            revisions=[revision],
        )
        assert len(item.revisions) == 1
        assert item.revisions[0].memory_id == "item-1"


class TestMemoryScope:
    """Test MemoryScope model edge cases."""

    def test_memory_scope_default_values(self):
        """Test MemoryScope with default values."""
        scope = MemoryScope()
        assert scope.owner_agent_id is None
        assert scope.share_scope == "private"
        assert scope.visibility == "private"
        assert scope.shared_with == []
        assert scope.project_id is None
        assert scope.room_id is None
        assert scope.task_id is None

    def test_memory_scope_with_sharing(self):
        """Test MemoryScope with sharing configuration."""
        scope = MemoryScope(
            owner_agent_id="agent-1",
            share_scope="team",
            visibility="shared",
            shared_with=["agent-2", "agent-3"],
            project_id="project-1",
        )
        assert scope.owner_agent_id == "agent-1"
        assert scope.share_scope == "team"
        assert scope.visibility == "shared"
        assert len(scope.shared_with) == 2

    def test_memory_scope_with_room_and_task(self):
        """Test MemoryScope with room and task context."""
        scope = MemoryScope(
            room_id="room-1",
            task_id="task-1",
        )
        assert scope.room_id == "room-1"
        assert scope.task_id == "task-1"


class TestSessionRecord:
    """Test SessionRecord model edge cases."""

    def test_session_record_default_values(self):
        """Test SessionRecord with default values."""
        record = SessionRecord(
            tenant_id="tenant-1",
            user_id="user-1",
        )
        assert record.session_id is not None
        assert record.tenant_id == "tenant-1"
        assert record.user_id == "user-1"
        assert record.title == ""
        assert record.summary == ""
        assert record.tags == []
        assert record.metadata == {}
        assert record.shared is False

    def test_session_record_with_agent(self):
        """Test SessionRecord with agent context."""
        record = SessionRecord(
            tenant_id="tenant-1",
            user_id="user-1",
            agent_id="agent-1",
            title="Agent Session",
            summary="Session with agent",
        )
        assert record.agent_id == "agent-1"
        assert record.title == "Agent Session"

    def test_session_record_with_sharing(self):
        """Test SessionRecord with sharing configuration."""
        record = SessionRecord(
            tenant_id="tenant-1",
            user_id="user-1",
            shared=True,
            room_id="room-1",
            project_id="project-1",
        )
        assert record.shared is True
        assert record.room_id == "room-1"
        assert record.project_id == "project-1"


class TestMemorySearchHit:
    """Test MemorySearchHit model edge cases."""

    def test_memory_search_hit_basic(self):
        """Test MemorySearchHit with basic fields."""
        item = MemoryItem(
            tenant_id="tenant-1",
            content="test",
            layer=5,
        )
        hit = MemorySearchHit(
            item=item,
            score=0.95,
        )
        assert hit.item == item
        assert hit.score == 0.95
        assert hit.keyword_score == 0.0
        assert hit.graph_score == 0.0
        assert hit.vector_score == 0.0

    def test_memory_search_hit_with_all_scores(self):
        """Test MemorySearchHit with all score types."""
        item = MemoryItem(
            tenant_id="tenant-1",
            content="test",
            layer=5,
        )
        hit = MemorySearchHit(
            item=item,
            score=0.95,
            keyword_score=0.8,
            graph_score=0.7,
            vector_score=0.9,
            importance_score=0.6,
            freshness_score=0.5,
        )
        assert hit.keyword_score == 0.8
        assert hit.graph_score == 0.7
        assert hit.vector_score == 0.9
        assert hit.importance_score == 0.6
        assert hit.freshness_score == 0.5


class TestMemoryConsolidationResult:
    """Test MemoryConsolidationResult model edge cases."""

    def test_consolidation_result_basic(self):
        """Test MemoryConsolidationResult basic fields."""
        result = MemoryConsolidationResult(
            source_count=5,
        )
        assert result.source_count == 5
        assert result.target_memory_id is None
        assert result.summary == ""
        assert result.tags == []

    def test_consolidation_result_with_target(self):
        """Test MemoryConsolidationResult with target memory."""
        result = MemoryConsolidationResult(
            source_count=5,
            target_memory_id="target-1",
            summary="Consolidated memory",
            tags=["consolidated", "merged"],
        )
        assert result.target_memory_id == "target-1"
        assert result.summary == "Consolidated memory"
        assert len(result.tags) == 2


class TestMemoryUpdateResult:
    """Test MemoryUpdateResult model edge cases."""

    def test_update_result_basic(self):
        """Test MemoryUpdateResult basic fields."""
        result = MemoryUpdateResult(
            memory_id="item-1",
        )
        assert result.memory_id == "item-1"
        assert result.revision_id is None
        assert result.content == ""

    def test_update_result_with_revision(self):
        """Test MemoryUpdateResult with revision."""
        result = MemoryUpdateResult(
            memory_id="item-1",
            revision_id="rev-1",
            content="Updated content",
        )
        assert result.revision_id == "rev-1"
        assert result.content == "Updated content"


class TestMemoryPollutionReport:
    """Test MemoryPollutionReport model edge cases."""

    def test_pollution_report_basic(self):
        """Test MemoryPollutionReport basic fields."""
        report = MemoryPollutionReport(
            memory_id="item-1",
            risk_level="low",
        )
        assert report.memory_id == "item-1"
        assert report.risk_level == "low"
        assert report.reasons == []
        assert report.blocked is False

    def test_pollution_report_with_reasons(self):
        """Test MemoryPollutionReport with risk reasons."""
        report = MemoryPollutionReport(
            memory_id="item-1",
            risk_level="high",
            reasons=["Contains sensitive data", "Outdated information"],
            blocked=True,
        )
        assert report.risk_level == "high"
        assert len(report.reasons) == 2
        assert report.blocked is True


class TestMemoryExportBundle:
    """Test MemoryExportBundle model edge cases."""

    def test_export_bundle_empty(self):
        """Test MemoryExportBundle with no data."""
        bundle = MemoryExportBundle()
        assert bundle.memories == []
        assert bundle.sessions == []

    def test_export_bundle_with_data(self):
        """Test MemoryExportBundle with memories and sessions."""
        item = MemoryItem(
            tenant_id="tenant-1",
            content="test",
            layer=5,
        )
        session = SessionRecord(
            tenant_id="tenant-1",
            user_id="user-1",
        )
        bundle = MemoryExportBundle(
            memories=[item],
            sessions=[session],
        )
        assert len(bundle.memories) == 1
        assert len(bundle.sessions) == 1


class TestMemorySystem:
    """Test MemorySystem edge cases."""

    def test_memory_system_initialization(self):
        """Test MemorySystem initialization."""
        system = MemorySystem()
        assert system._items == []
        assert system._sessions == {}
        assert system._storage_path is None

    def test_memory_system_with_storage_path(self):
        """Test MemorySystem with storage path."""
        path = Path("/tmp/memory_test")
        system = MemorySystem(storage_path=path)
        assert system._storage_path == path

    def test_memory_system_add_without_tenant_id(self):
        """Test MemorySystem.add raises error without tenant_id."""
        system = MemorySystem()
        with pytest.raises(ValueError, match="tenant_id is required"):
            system.add("test content")

    def test_memory_system_add_with_tenant_id(self):
        """Test MemorySystem.add with tenant_id."""
        system = MemorySystem()
        memory_id = system.add("test content", tenant_id="tenant-1")
        assert memory_id is not None
        assert len(system._items) == 1

    def test_memory_system_add_with_summary(self):
        """Test MemorySystem.add with summary."""
        system = MemorySystem()
        memory_id = system.add(
            "test content",
            summary="Test summary",
            tenant_id="tenant-1",
        )
        assert memory_id is not None
        item = system._items[0]
        assert item.metadata["summary"] == "Test summary"

    def test_memory_system_layer_profiles(self):
        """Test MemorySystem layer profiles."""
        system = MemorySystem()
        assert len(system._LAYER_PROFILES) == 10
        for layer in range(1, 11):
            profile = system._LAYER_PROFILES[layer]
            assert "name" in profile
            assert "role" in profile
            assert "scope" in profile
            assert "lifetime" in profile
            assert "access" in profile

    def test_memory_system_layer_profile_names(self):
        """Test MemorySystem layer profile names."""
        system = MemorySystem()
        expected_names = [
            "instant_context",
            "session_working",
            "task_memory",
            "collaboration_memory",
            "tool_memory",
            "behavior_memory",
            "project_memory",
            "organization_memory",
            "platform_memory",
            "long_term_evolution",
        ]
        for layer in range(1, 11):
            assert system._LAYER_PROFILES[layer]["name"] == expected_names[layer - 1]

    def test_memory_system_layer_profile_roles(self):
        """Test MemorySystem layer profile roles."""
        system = MemorySystem()
        expected_roles = [
            "perception",
            "working",
            "episodic",
            "collaboration",
            "procedural",
            "meta",
            "session",
            "reflection",
            "strategy",
            "identity",
        ]
        for layer in range(1, 11):
            assert system._LAYER_PROFILES[layer]["role"] == expected_roles[layer - 1]

    def test_memory_system_layer_profile_lifetimes(self):
        """Test MemorySystem layer profile lifetimes."""
        system = MemorySystem()
        expected_lifetimes = [
            "seconds",
            "minutes",
            "task",
            "collaboration",
            "tool_session",
            "long_session",
            "project",
            "organization",
            "platform",
            "persistent",
        ]
        for layer in range(1, 11):
            assert system._LAYER_PROFILES[layer]["lifetime"] == expected_lifetimes[layer - 1]

    def test_memory_system_concurrent_access(self):
        """Test MemorySystem thread safety."""
        import threading
        system = MemorySystem()
        results = []

        def add_memory():
            memory_id = system.add("test content", tenant_id="tenant-1")
            results.append(memory_id)

        threads = [threading.Thread(target=add_memory) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(results) == 10
        assert len(system._items) == 10
        assert len(set(results)) == 10  # All IDs are unique
