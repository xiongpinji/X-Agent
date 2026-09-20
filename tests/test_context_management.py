"""Tests for context management system.

Tests cover token counting, compression, memory persistence, and session recovery.
"""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.app.core.context_compactor import ContextCompactor, CompactionResult
from backend.app.core.session_recovery import SessionRecovery, SessionSnapshot


class TestContextCompactor:
    """Tests for ContextCompactor."""

    @pytest.fixture
    def compactor(self) -> ContextCompactor:
        """Create a compactor instance."""
        return ContextCompactor(model="gpt-4", token_limit=1000, compression_threshold=0.8)

    def test_token_counting(self, compactor: ContextCompactor) -> None:
        """Test token counting accuracy."""
        text = "Hello world"
        tokens = compactor.count_tokens(text)
        assert tokens > 0

    def test_message_token_counting(self, compactor: ContextCompactor) -> None:
        """Test counting tokens in message list."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        tokens = compactor.count_messages_tokens(messages)
        assert tokens > 0

    def test_should_compress_below_threshold(self, compactor: ContextCompactor) -> None:
        """Test that compression is not triggered below threshold."""
        messages = [
            {"role": "user", "content": "Short message"},
        ]
        assert not compactor.should_compress(messages)

    def test_should_compress_above_threshold(self, compactor: ContextCompactor) -> None:
        """Test that compression is triggered above threshold."""
        # Create messages that exceed threshold
        long_content = "x" * 5000
        messages = [
            {"role": "user", "content": long_content},
            {"role": "assistant", "content": long_content},
            {"role": "user", "content": long_content},
        ]
        assert compactor.should_compress(messages)

    def test_message_importance_scoring(self, compactor: ContextCompactor) -> None:
        """Test message importance scoring."""
        # Tool messages should score high
        tool_msg = {"role": "tool", "content": "Tool result"}
        score = compactor._score_message_importance(tool_msg, 0, 1)
        assert score > 0.3

        # User messages should score reasonably
        user_msg = {"role": "user", "content": "User instruction"}
        score = compactor._score_message_importance(user_msg, 0, 1)
        assert score > 0.2

    def test_compression_preserves_critical_messages(self, compactor: ContextCompactor) -> None:
        """Test that compression preserves critical messages."""
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "x" * 1000},
            {"role": "assistant", "content": "y" * 1000},
            {"role": "tool", "content": "Tool result"},
            {"role": "user", "content": "z" * 1000},
        ]

        result = compactor.compress(messages)
        assert result.success
        # Tool message should be preserved
        tool_messages = [m for m in result.messages if m.get("role") == "tool"]
        assert len(tool_messages) > 0

    def test_compression_reduces_message_count(self, compactor: ContextCompactor) -> None:
        """Test that compression reduces message count."""
        messages = [
            {"role": "user", "content": f"Message {i}"}
            for i in range(20)
        ]
        result = compactor.compress(messages)
        assert result.success
        assert result.metrics.messages_after < result.metrics.messages_before

    def test_compression_maintains_minimum_messages(self, compactor: ContextCompactor) -> None:
        """Test that compression maintains minimum message count."""
        messages = [
            {"role": "user", "content": "Message 1"},
            {"role": "user", "content": "Message 2"},
        ]
        result = compactor.compress(messages)
        assert result.success
        # When the input is already at/below the keep-floor, compress() correctly
        # returns everything (it cannot fabricate messages). The faithful invariant
        # is therefore min(input_count, keep-floor), not the raw keep-floor.
        assert result.metrics.messages_after >= min(
            len(messages), compactor.min_messages_to_keep
        )

    def test_incremental_compression(self, compactor: ContextCompactor) -> None:
        """Test incremental compression."""
        existing = [
            {"role": "user", "content": "Existing message"},
        ]
        new = [
            {"role": "assistant", "content": "New response"},
        ]
        result = compactor.incremental_compress(existing, new)
        assert result.success
        assert len(result.messages) >= 2

    def test_compression_creates_summary(self, compactor: ContextCompactor) -> None:
        """Test that compression creates summary message."""
        messages = [
            {"role": "user", "content": f"x" * 500}
            for _ in range(10)
        ]
        result = compactor.compress(messages)
        assert result.success
        # Should have summary message
        summary_msgs = [m for m in result.messages if m.get("role") == "system" and "compressed" in m.get("content", "").lower()]
        assert len(summary_msgs) > 0


class TestSessionRecovery:
    """Tests for SessionRecovery."""

    @pytest.fixture
    def sessions_dir(self) -> Path:
        """Create temporary sessions directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def recovery(self, sessions_dir: Path) -> SessionRecovery:
        """Create recovery instance."""
        return SessionRecovery(sessions_dir)

    def test_create_session(self, recovery: SessionRecovery) -> None:
        """Test creating a session."""
        session_id = recovery.create_session()
        assert session_id is not None
        metadata = recovery.get_session_metadata(session_id)
        assert metadata is not None
        assert metadata.status == "active"

    def test_save_snapshot(self, recovery: SessionRecovery) -> None:
        """Test saving a snapshot."""
        session_id = recovery.create_session()
        snapshot = SessionSnapshot(
            session_id=session_id,
            iteration=0,
            messages=[{"role": "user", "content": "Test"}],
            context={"key": "value"},
        )
        path = recovery.save_snapshot(snapshot)
        assert Path(path).exists()

    def test_load_latest_snapshot(self, recovery: SessionRecovery) -> None:
        """Test loading latest snapshot."""
        session_id = recovery.create_session()
        snapshot = SessionSnapshot(
            session_id=session_id,
            iteration=0,
            messages=[{"role": "user", "content": "Test"}],
        )
        recovery.save_snapshot(snapshot)
        loaded = recovery.load_latest_snapshot(session_id)
        assert loaded is not None
        assert loaded.iteration == 0

    def test_load_snapshot_at_iteration(self, recovery: SessionRecovery) -> None:
        """Test loading snapshot at specific iteration."""
        session_id = recovery.create_session()
        for i in range(3):
            snapshot = SessionSnapshot(
                session_id=session_id,
                iteration=i,
                messages=[{"role": "user", "content": f"Message {i}"}],
            )
            recovery.save_snapshot(snapshot)

        loaded = recovery.load_snapshot_at_iteration(session_id, 1)
        assert loaded is not None
        assert loaded.iteration == 1

    def test_list_snapshots(self, recovery: SessionRecovery) -> None:
        """Test listing snapshots."""
        session_id = recovery.create_session()
        for i in range(3):
            snapshot = SessionSnapshot(
                session_id=session_id,
                iteration=i,
            )
            recovery.save_snapshot(snapshot)

        snapshots = recovery.list_snapshots(session_id)
        assert len(snapshots) == 3

    def test_delete_session(self, recovery: SessionRecovery) -> None:
        """Test deleting a session."""
        session_id = recovery.create_session()
        snapshot = SessionSnapshot(session_id=session_id, iteration=0)
        recovery.save_snapshot(snapshot)

        assert recovery.delete_session(session_id)
        assert recovery.get_session_metadata(session_id) is None

    def test_update_session_status(self, recovery: SessionRecovery) -> None:
        """Test updating session status."""
        session_id = recovery.create_session()
        assert recovery.update_session_status(session_id, "paused")
        metadata = recovery.get_session_metadata(session_id)
        assert metadata.status == "paused"

    def test_list_sessions(self, recovery: SessionRecovery) -> None:
        """Test listing sessions."""
        for _ in range(3):
            recovery.create_session()

        sessions = recovery.list_sessions()
        assert len(sessions) >= 3

    def test_list_sessions_by_status(self, recovery: SessionRecovery) -> None:
        """Test listing sessions by status."""
        session_id1 = recovery.create_session()
        session_id2 = recovery.create_session()

        recovery.update_session_status(session_id1, "completed")
        recovery.update_session_status(session_id2, "active")

        completed = recovery.list_sessions(status="completed")
        assert any(s.session_id == session_id1 for s in completed)

    def test_snapshot_preserves_state(self, recovery: SessionRecovery) -> None:
        """Test that snapshots preserve full state."""
        session_id = recovery.create_session()
        state = {
            "iteration": 5,
            "tool_calls": ["tool1", "tool2"],
            "results": {"key": "value"},
        }
        snapshot = SessionSnapshot(
            session_id=session_id,
            iteration=5,
            state=state,
            context={"task": "test"},
        )
        recovery.save_snapshot(snapshot)

        loaded = recovery.load_latest_snapshot(session_id)
        assert loaded.state == state
        assert loaded.context == {"task": "test"}
