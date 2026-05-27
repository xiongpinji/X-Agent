"""Comprehensive tests for memory system components.

Tests cover:
- MemoryItem creation and validation
- MemoryScope management
- MemoryRevision tracking
- SessionRecord lifecycle
- MemorySearchHit scoring
- MemoryConsolidationResult
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.app.core.memory import (
    MemoryConsolidationResult,
    MemoryItem,
    MemoryPollutionReport,
    MemoryRevision,
    MemoryRollbackResult,
    MemoryScope,
    MemorySearchHit,
    MemoryUpdateResult,
    SessionRecord,
)


class TestMemoryScope:
    """Test MemoryScope model."""

    def test_memory_scope_default_values(self) -> None:
        scope = MemoryScope()
        assert scope.owner_agent_id is None
        assert scope.share_scope == "private"
        assert scope.visibility == "private"
        assert scope.shared_with == []
        assert scope.project_id is None
        assert scope.room_id is None
        assert scope.task_id is None

    def test_memory_scope_with_custom_values(self) -> None:
        scope = MemoryScope(
            owner_agent_id="agent-123",
            share_scope="shared",
            visibility="public",
            shared_with=["user-1", "user-2"],
            project_id="proj-1",
            room_id="room-1",
            task_id="task-1",
        )
        assert scope.owner_agent_id == "agent-123"
        assert scope.share_scope == "shared"
        assert scope.visibility == "public"
        assert scope.shared_with == ["user-1", "user-2"]
        assert scope.project_id == "proj-1"
        assert scope.room_id == "room-1"
        assert scope.task_id == "task-1"

    def test_memory_scope_serialization(self) -> None:
        scope = MemoryScope(
            owner_agent_id="agent-123",
            shared_with=["user-1"],
        )
        data = scope.model_dump()
        assert data["owner_agent_id"] == "agent-123"
        assert data["shared_with"] == ["user-1"]


class TestMemoryRevision:
    """Test MemoryRevision model."""

    def test_memory_revision_default_values(self) -> None:
        revision = MemoryRevision(memory_id="mem-123")
        assert revision.memory_id == "mem-123"
        assert revision.revision_id is not None
        assert revision.actor_agent_id is None
        assert revision.summary == ""
        assert isinstance(revision.created_at, datetime)

    def test_memory_revision_with_custom_values(self) -> None:
        now = datetime.now(UTC)
        revision = MemoryRevision(
            memory_id="mem-123",
            revision_id="rev-456",
            actor_agent_id="agent-789",
            summary="Updated memory content",
            created_at=now,
        )
        assert revision.memory_id == "mem-123"
        assert revision.revision_id == "rev-456"
        assert revision.actor_agent_id == "agent-789"
        assert revision.summary == "Updated memory content"
        assert revision.created_at == now

    def test_memory_revision_unique_ids(self) -> None:
        rev1 = MemoryRevision(memory_id="mem-123")
        rev2 = MemoryRevision(memory_id="mem-123")
        assert rev1.revision_id != rev2.revision_id


class TestMemoryItem:
    """Test MemoryItem model."""

    def test_memory_item_creation(self) -> None:
        item = MemoryItem(
            tenant_id="tenant-1",
            content="Test memory content",
            layer=1,
        )
        assert item.tenant_id == "tenant-1"
        assert item.content == "Test memory content"
        assert item.layer == 1
        assert item.id is not None
        assert item.importance == 0.5
        assert item.tags == []
        assert item.metadata == {}
        assert item.embedding == []
        assert item.revisions == []

    def test_memory_item_with_all_fields(self) -> None:
        now = datetime.now(UTC)
        item = MemoryItem(
            id="mem-123",
            tenant_id="tenant-1",
            agent_id="agent-1",
            session_id="session-1",
            scope=MemoryScope(owner_agent_id="agent-1"),
            content="Test content",
            layer=5,
            importance=0.8,
            tags=["tag1", "tag2"],
            metadata={"key": "value"},
            embedding=[0.1, 0.2, 0.3],
            created_at=now,
        )
        assert item.id == "mem-123"
        assert item.agent_id == "agent-1"
        assert item.session_id == "session-1"
        assert item.importance == 0.8
        assert item.tags == ["tag1", "tag2"]
        assert item.metadata == {"key": "value"}
        assert item.embedding == [0.1, 0.2, 0.3]

    def test_memory_item_layer_validation(self) -> None:
        with pytest.raises(ValidationError):
            MemoryItem(tenant_id="tenant-1", content="Test", layer=0)

        with pytest.raises(ValidationError):
            MemoryItem(tenant_id="tenant-1", content="Test", layer=11)

    def test_memory_item_importance_validation(self) -> None:
        with pytest.raises(ValidationError):
            MemoryItem(tenant_id="tenant-1", content="Test", layer=1, importance=-0.1)

        with pytest.raises(ValidationError):
            MemoryItem(tenant_id="tenant-1", content="Test", layer=1, importance=1.1)

    def test_memory_item_with_revisions(self) -> None:
        revision = MemoryRevision(memory_id="mem-123", summary="First update")
        item = MemoryItem(
            tenant_id="tenant-1",
            content="Test content",
            layer=1,
            revisions=[revision],
        )
        assert len(item.revisions) == 1
        assert item.revisions[0].summary == "First update"


class TestSessionRecord:
    """Test SessionRecord model."""

    def test_session_record_creation(self) -> None:
        record = SessionRecord(
            tenant_id="tenant-1",
            user_id="user-1",
        )
        assert record.session_id is not None
        assert record.tenant_id == "tenant-1"
        assert record.user_id == "user-1"
        assert record.agent_id is None
        assert record.title == ""
        assert record.summary == ""
        assert record.tags == []
        assert record.metadata == {}
        assert record.shared is False
        assert record.room_id is None
        assert record.project_id is None

    def test_session_record_with_all_fields(self) -> None:
        now = datetime.now(UTC)
        record = SessionRecord(
            session_id="session-123",
            tenant_id="tenant-1",
            user_id="user-1",
            agent_id="agent-1",
            title="Test Session",
            summary="A test session",
            tags=["test", "demo"],
            metadata={"key": "value"},
            created_at=now,
            updated_at=now,
            last_memory_id="mem-123",
            shared=True,
            room_id="room-1",
            project_id="proj-1",
        )
        assert record.session_id == "session-123"
        assert record.agent_id == "agent-1"
        assert record.title == "Test Session"
        assert record.tags == ["test", "demo"]
        assert record.shared is True
        assert record.room_id == "room-1"

    def test_session_record_timestamps(self) -> None:
        record = SessionRecord(tenant_id="tenant-1", user_id="user-1")
        assert isinstance(record.created_at, datetime)
        assert isinstance(record.updated_at, datetime)


class TestMemorySearchHit:
    """Test MemorySearchHit model."""

    def test_memory_search_hit_creation(self) -> None:
        item = MemoryItem(tenant_id="tenant-1", content="Test", layer=1)
        hit = MemorySearchHit(item=item, score=0.95)
        assert hit.item == item
        assert hit.score == 0.95
        assert hit.keyword_score == 0.0
        assert hit.graph_score == 0.0
        assert hit.vector_score == 0.0
        assert hit.importance_score == 0.0
        assert hit.freshness_score == 0.0

    def test_memory_search_hit_with_all_scores(self) -> None:
        item = MemoryItem(tenant_id="tenant-1", content="Test", layer=1)
        hit = MemorySearchHit(
            item=item,
            score=0.95,
            keyword_score=0.8,
            graph_score=0.7,
            vector_score=0.9,
            importance_score=0.6,
            freshness_score=0.85,
        )
        assert hit.keyword_score == 0.8
        assert hit.graph_score == 0.7
        assert hit.vector_score == 0.9
        assert hit.importance_score == 0.6
        assert hit.freshness_score == 0.85


class TestMemoryConsolidationResult:
    """Test MemoryConsolidationResult model."""

    def test_consolidation_result_creation(self) -> None:
        result = MemoryConsolidationResult(source_count=5)
        assert result.source_count == 5
        assert result.target_memory_id is None
        assert result.summary == ""
        assert result.tags == []

    def test_consolidation_result_with_all_fields(self) -> None:
        result = MemoryConsolidationResult(
            source_count=5,
            target_memory_id="mem-123",
            summary="Consolidated memory",
            tags=["consolidated", "merged"],
        )
        assert result.source_count == 5
        assert result.target_memory_id == "mem-123"
        assert result.summary == "Consolidated memory"
        assert result.tags == ["consolidated", "merged"]


class TestMemoryUpdateResult:
    """Test MemoryUpdateResult model."""

    def test_update_result_creation(self) -> None:
        result = MemoryUpdateResult(memory_id="mem-123")
        assert result.memory_id == "mem-123"
        assert result.revision_id is None
        assert result.content == ""

    def test_update_result_with_all_fields(self) -> None:
        result = MemoryUpdateResult(
            memory_id="mem-123",
            revision_id="rev-456",
            content="Updated content",
        )
        assert result.memory_id == "mem-123"
        assert result.revision_id == "rev-456"
        assert result.content == "Updated content"


class TestMemoryRollbackResult:
    """Test MemoryRollbackResult model."""

    def test_rollback_result_creation(self) -> None:
        result = MemoryRollbackResult(memory_id="mem-123")
        assert result.memory_id == "mem-123"
        assert result.revision_id is None
        assert result.content == ""

    def test_rollback_result_with_all_fields(self) -> None:
        result = MemoryRollbackResult(
            memory_id="mem-123",
            revision_id="rev-456",
            content="Rolled back content",
        )
        assert result.memory_id == "mem-123"
        assert result.revision_id == "rev-456"
        assert result.content == "Rolled back content"


class TestMemoryPollutionReport:
    """Test MemoryPollutionReport model."""

    def test_pollution_report_creation(self) -> None:
        report = MemoryPollutionReport(
            memory_id="mem-123",
            risk_level="high",
        )
        assert report.memory_id == "mem-123"
        assert report.risk_level == "high"
        assert report.reasons == []

    def test_pollution_report_with_reasons(self) -> None:
        report = MemoryPollutionReport(
            memory_id="mem-123",
            risk_level="critical",
            reasons=["Outdated information", "Conflicting data"],
        )
        assert report.memory_id == "mem-123"
        assert report.risk_level == "critical"
        assert len(report.reasons) == 2
        assert "Outdated information" in report.reasons
