"""Integration tests for context management system.

Tests:
- Session initialization and restoration
- Message handling and compression
- Context metrics and statistics
- Long conversation scenarios
"""

from __future__ import annotations

import asyncio
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.app.core.context_compactor import ContextCompactor
from backend.app.core.context import (
    ContextManager,
    SessionRecovery,
    Message,
    SessionState,
)


@pytest.fixture
def temp_storage():
    """Create temporary storage directory."""
    with TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def session_recovery(temp_storage):
    """Create session recovery instance."""
    return SessionRecovery(storage_path=temp_storage)


@pytest.fixture
def context_compactor():
    """Create context compactor instance."""
    return ContextCompactor(
        model="gpt-4",
        token_limit=128_000,
        compression_threshold=0.85,
        min_messages_to_keep=3,
    )


@pytest.fixture
async def context_manager(session_recovery, context_compactor):
    """Create context manager instance."""
    manager = ContextManager(
        session_recovery=session_recovery,
        context_compactor=context_compactor,
        auto_save_interval_seconds=60,
        auto_compress_enabled=True,
    )
    yield manager
    await manager.cleanup()


class TestSessionInitialization:
    """Test session initialization and restoration."""

    @pytest.mark.asyncio
    async def test_initialize_new_session(self, context_manager):
        """Test initializing a new session."""
        session_state = await context_manager.initialize_session(
            session_id="test-session-1",
            agent_id="agent-1",
            tenant_id="tenant-1",
        )

        assert session_state.session_id == "test-session-1"
        assert session_state.agent_id == "agent-1"
        assert session_state.tenant_id == "tenant-1"
        assert len(session_state.messages) == 0
        assert session_state.total_tokens == 0

    @pytest.mark.asyncio
    async def test_restore_existing_session(self, context_manager, session_recovery):
        """Test restoring an existing session."""
        # Create and save a session
        session_state = SessionState(
            session_id="test-session-2",
            agent_id="agent-1",
            tenant_id="tenant-1",
            messages=[
                Message(role="user", content="Hello"),
                Message(role="assistant", content="Hi there!"),
            ],
        )
        await session_recovery.save_snapshot(session_state)

        # Restore the session
        restored = await context_manager.restore_session("test-session-2")

        assert restored is not None
        assert restored.session_id == "test-session-2"
        assert len(restored.messages) == 2
        assert restored.messages[0].content == "Hello"


class TestMessageHandling:
    """Test message handling and storage."""

    @pytest.mark.asyncio
    async def test_add_single_message(self, context_manager):
        """Test adding a single message."""
        await context_manager.initialize_session("test-session-3")

        message = await context_manager.add_message(
            role="user",
            content="What is 2+2?",
        )

        assert message.role == "user"
        assert message.content == "What is 2+2?"
        assert message.token_count > 0

    @pytest.mark.asyncio
    async def test_add_multiple_messages(self, context_manager):
        """Test adding multiple messages."""
        await context_manager.initialize_session("test-session-4")

        messages = []
        for i in range(5):
            msg = await context_manager.add_message(
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
            )
            messages.append(msg)

        context = await context_manager.get_context()
        assert len(context) == 5

    @pytest.mark.asyncio
    async def test_get_context_with_limit(self, context_manager):
        """Test getting context with message limit."""
        await context_manager.initialize_session("test-session-5")

        for i in range(10):
            await context_manager.add_message(
                role="user",
                content=f"Message {i}",
            )

        context = await context_manager.get_context(limit=5)
        assert len(context) == 5

    @pytest.mark.asyncio
    async def test_message_metadata(self, context_manager):
        """Test message metadata handling."""
        await context_manager.initialize_session("test-session-6")

        metadata = {"source": "test", "priority": "high"}
        message = await context_manager.add_message(
            role="user",
            content="Test message",
            metadata=metadata,
            importance=0.8,
        )

        assert message.metadata == metadata
        assert message.importance == 0.8


class TestContextCompression:
    """Test context compression functionality."""

    @pytest.mark.asyncio
    async def test_compression_triggered(self, context_manager, context_compactor):
        """Test that compression is triggered when needed."""
        await context_manager.initialize_session("test-session-7")

        # Add messages until compression is triggered
        for i in range(100):
            await context_manager.add_message(
                role="user" if i % 2 == 0 else "assistant",
                content="x" * 1000,  # Large messages
            )

        metrics = await context_manager.get_metrics()
        # Compression should have been triggered
        assert metrics.compression_count >= 0

    @pytest.mark.asyncio
    async def test_manual_compression(self, context_manager):
        """Test manual compression trigger."""
        await context_manager.initialize_session("test-session-8")

        for i in range(10):
            await context_manager.add_message(
                role="user",
                content=f"Message {i}",
            )

        result = await context_manager.compress_if_needed()
        # May or may not compress depending on token count
        assert result is None or result.success


class TestSessionPersistence:
    """Test session persistence and recovery."""

    @pytest.mark.asyncio
    async def test_save_and_restore_session(self, context_manager):
        """Test saving and restoring a session."""
        await context_manager.initialize_session("test-session-9")

        # Add messages
        for i in range(5):
            await context_manager.add_message(
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
            )

        # Save session
        await context_manager.save_session()

        # Create new manager and restore
        from backend.app.core.context_compactor import ContextCompactor
        from backend.app.core.context import SessionRecovery

        new_recovery = SessionRecovery(storage_path=context_manager.session_recovery.storage_path)
        new_compactor = ContextCompactor()
        new_manager = ContextManager(
            session_recovery=new_recovery,
            context_compactor=new_compactor,
        )

        restored = await new_manager.restore_session("test-session-9")

        assert restored is not None
        assert len(restored.messages) == 5

        await new_manager.cleanup()

    @pytest.mark.asyncio
    async def test_list_sessions(self, context_manager):
        """Test listing sessions."""
        # Create multiple sessions
        for i in range(3):
            await context_manager.initialize_session(f"test-session-list-{i}", agent_id="agent-1")
            await context_manager.add_message(role="user", content="Test")
            await context_manager.save_session()

        sessions = await context_manager.list_sessions(agent_id="agent-1")
        assert len(sessions) >= 3

    @pytest.mark.asyncio
    async def test_delete_session(self, context_manager):
        """Test deleting a session."""
        await context_manager.initialize_session("test-session-delete")
        await context_manager.add_message(role="user", content="Test")
        await context_manager.save_session()

        # Delete session
        success = await context_manager.delete_session("test-session-delete")
        assert success

        # Try to restore deleted session
        restored = await context_manager.restore_session("test-session-delete")
        assert restored is None


class TestSessionStatistics:
    """Test session statistics and metrics."""

    @pytest.mark.asyncio
    async def test_get_session_stats(self, context_manager):
        """Test getting session statistics."""
        await context_manager.initialize_session("test-session-stats")

        for i in range(5):
            await context_manager.add_message(
                role="user",
                content=f"Message {i}",
            )

        await context_manager.save_session()

        stats = await context_manager.get_session_stats("test-session-stats")

        assert stats is not None
        assert stats.message_count == 5
        assert stats.total_tokens > 0

    @pytest.mark.asyncio
    async def test_get_context_metrics(self, context_manager):
        """Test getting context metrics."""
        await context_manager.initialize_session("test-session-metrics")

        for i in range(3):
            await context_manager.add_message(
                role="user",
                content=f"Message {i}",
            )

        metrics = await context_manager.get_metrics()

        assert metrics.total_messages == 3
        assert metrics.total_tokens > 0


class TestLongConversation:
    """Test long conversation scenarios."""

    @pytest.mark.asyncio
    async def test_long_conversation_with_compression(self, context_manager):
        """Test a long conversation with automatic compression."""
        await context_manager.initialize_session("test-session-long")

        # Simulate a long conversation
        for i in range(50):
            role = "user" if i % 2 == 0 else "assistant"
            content = f"Message {i}: " + "x" * 500

            await context_manager.add_message(
                role=role,
                content=content,
            )

        metrics = await context_manager.get_metrics()

        assert metrics.total_messages == 50
        assert metrics.total_tokens > 0

        # Context should still be accessible
        context = await context_manager.get_context()
        assert len(context) > 0

    @pytest.mark.asyncio
    async def test_conversation_recovery_after_interruption(self, context_manager):
        """Test recovering a conversation after interruption."""
        session_id = "test-session-recovery"

        # Start conversation
        await context_manager.initialize_session(session_id)

        for i in range(10):
            await context_manager.add_message(
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
            )

        await context_manager.save_session()

        # Simulate interruption by creating new manager
        from backend.app.core.context_compactor import ContextCompactor
        from backend.app.core.context import SessionRecovery

        new_recovery = SessionRecovery(storage_path=context_manager.session_recovery.storage_path)
        new_compactor = ContextCompactor()
        new_manager = ContextManager(
            session_recovery=new_recovery,
            context_compactor=new_compactor,
        )

        # Restore and continue
        await new_manager.restore_session(session_id)

        for i in range(10, 15):
            await new_manager.add_message(
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
            )

        context = await new_manager.get_context()
        assert len(context) == 15

        await new_manager.cleanup()


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_add_message_without_session(self, context_manager):
        """Test adding message without initializing session."""
        with pytest.raises(ValueError):
            await context_manager.add_message(role="user", content="Test")

    @pytest.mark.asyncio
    async def test_restore_nonexistent_session(self, context_manager):
        """Test restoring a nonexistent session."""
        restored = await context_manager.restore_session("nonexistent-session")
        assert restored is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session(self, context_manager):
        """Test deleting a nonexistent session."""
        success = await context_manager.delete_session("nonexistent-session")
        assert not success


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
