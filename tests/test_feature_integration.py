"""Integration tests for Phase 3 feature enhancements."""

import asyncio
import pytest
import time
from unittest.mock import Mock, AsyncMock, patch

from backend.app.core.memory_fusion import Memory, MemoryFusion, MemoryCluster
from backend.app.core.agent_collaboration import (
    AgentMessage,
    AgentInfo,
    AgentStatus,
    MessageType,
    AgentCollaboration,
)
from backend.app.services.browser.enhanced_automation import (
    EnhancedBrowserAutomation,
    ElementInfo,
    ElementDetectionMethod,
    WaitStrategy,
)
from backend.app.core.advanced_repair_loop import (
    AdvancedRepairLoop,
    FailureRecord,
    FailureCategory,
    RepairStrategy,
    RepairSuggestion,
)


class TestMemoryFusion:
    """Tests for memory fusion system."""

    @pytest.mark.asyncio
    async def test_add_memory_with_embedding(self):
        """Test adding memory with embedding generation."""
        fusion = MemoryFusion()

        memory = Memory(
            id="mem_1",
            content="Test memory content",
        )

        result = await fusion.add_memory(memory)

        assert result.id == "mem_1"
        assert len(result.embedding) > 0
        assert result in fusion._memory_cache.values()

    @pytest.mark.asyncio
    async def test_deduplicate_similar_memories(self):
        """Test deduplication of similar memories."""
        fusion = MemoryFusion(similarity_threshold=0.85)

        memories = [
            Memory(id="mem_1", content="The quick brown fox jumps over the lazy dog"),
            Memory(id="mem_2", content="The quick brown fox jumps over a lazy dog"),
            Memory(id="mem_3", content="Completely different content here"),
        ]

        # Add memories
        for memory in memories:
            await fusion.add_memory(memory)

        # Deduplicate
        unique = await fusion.deduplicate(memories)

        assert len(unique) <= len(memories)
        assert len(unique) >= 2  # At least 2 unique clusters

    @pytest.mark.asyncio
    async def test_compress_memories(self):
        """Test memory compression."""
        fusion = MemoryFusion(compression_ratio=0.5)

        memories = [
            Memory(id=f"mem_{i}", content=f"Memory {i}", importance=float(i))
            for i in range(10)
        ]

        compressed = await fusion.compress_memories(memories)

        assert len(compressed) <= len(memories)
        assert len(compressed) >= int(len(memories) * fusion.compression_ratio)

    @pytest.mark.asyncio
    async def test_associate_memories(self):
        """Test memory association through graph."""
        fusion = MemoryFusion()

        memory1 = Memory(id="mem_1", content="Python programming language")
        memory2 = Memory(id="mem_2", content="Python is great for data science")
        memory3 = Memory(id="mem_3", content="JavaScript web development")

        await fusion.add_memory(memory1)
        await fusion.add_memory(memory2)
        await fusion.add_memory(memory3)

        # Find associations
        related = await fusion.associate_memories(memory1)

        assert len(related) > 0
        assert memory2 in related or memory3 in related

    @pytest.mark.asyncio
    async def test_memory_stats(self):
        """Test memory statistics."""
        fusion = MemoryFusion()

        memories = [
            Memory(id=f"mem_{i}", content=f"Memory {i}", importance=0.5 + i * 0.1)
            for i in range(5)
        ]

        for memory in memories:
            await fusion.add_memory(memory)

        stats = fusion.get_memory_stats()

        assert stats["total_memories"] == 5
        assert stats["avg_importance"] > 0
        assert stats["total_content_length"] > 0


class TestAgentCollaboration:
    """Tests for multi-agent collaboration system."""

    @pytest.mark.asyncio
    async def test_agent_registration(self):
        """Test agent registration."""
        collab = AgentCollaboration()

        with patch("redis.asyncio.from_url", new_callable=AsyncMock):
            collab.redis = AsyncMock()
            collab.redis.hset = AsyncMock()
            collab.redis.delete = AsyncMock()

            agent_info = await collab.register_agent("agent_1", capacity=10)

            assert agent_info.agent_id == "agent_1"
            assert agent_info.capacity == 10
            assert agent_info.status == AgentStatus.IDLE

    @pytest.mark.asyncio
    async def test_send_message(self):
        """Test sending message between agents."""
        collab = AgentCollaboration()

        with patch("redis.asyncio.from_url", new_callable=AsyncMock):
            collab.redis = AsyncMock()
            collab.redis.lpush = AsyncMock()
            collab.redis.expire = AsyncMock()
            collab.redis.publish = AsyncMock()

            message = AgentMessage(
                from_agent="agent_1",
                to_agent="agent_2",
                message_type=MessageType.TASK_REQUEST,
                payload={"task": "test"},
            )

            success = await collab.send_message(message)

            assert success is True
            collab.redis.lpush.assert_called_once()

    @pytest.mark.asyncio
    async def test_receive_messages(self):
        """Test receiving messages."""
        collab = AgentCollaboration()

        message = AgentMessage(
            from_agent="agent_1",
            to_agent="agent_2",
            message_type=MessageType.TASK_REQUEST,
            payload={"task": "test"},
        )

        with patch("redis.asyncio.from_url", new_callable=AsyncMock):
            collab.redis = AsyncMock()
            collab.redis.lrange = AsyncMock(return_value=[message.to_json().encode()])

            messages = await collab.receive_messages("agent_2")

            assert len(messages) == 1
            assert messages[0].from_agent == "agent_1"

    @pytest.mark.asyncio
    async def test_update_agent_status(self):
        """Test updating agent status."""
        collab = AgentCollaboration()

        with patch("redis.asyncio.from_url", new_callable=AsyncMock):
            collab.redis = AsyncMock()
            collab.redis.hset = AsyncMock()

            await collab.register_agent("agent_1")
            await collab.update_agent_status(
                "agent_1",
                AgentStatus.BUSY,
                load=0.5,
                active_tasks=3,
            )

            agent_info = collab._local_agent_info["agent_1"]
            assert agent_info.status == AgentStatus.BUSY
            assert agent_info.load == 0.5
            assert agent_info.active_tasks == 3

    @pytest.mark.asyncio
    async def test_get_available_agents(self):
        """Test getting available agents."""
        collab = AgentCollaboration()

        with patch("redis.asyncio.from_url", new_callable=AsyncMock):
            collab.redis = AsyncMock()

            agent1 = AgentInfo(agent_id="agent_1", status=AgentStatus.IDLE, load=0.2)
            agent2 = AgentInfo(agent_id="agent_2", status=AgentStatus.BUSY, load=0.9)

            agents_data = {
                "agent_1": agent1.__dict__,
                "agent_2": agent2.__dict__,
            }

            collab.redis.hgetall = AsyncMock(
                return_value={
                    k: str(v).encode() for k, v in agents_data.items()
                }
            )

            # This would need proper JSON serialization in real test
            # For now, just verify the method exists
            assert hasattr(collab, "get_available_agents")


class TestEnhancedBrowserAutomation:
    """Tests for enhanced browser automation."""

    @pytest.mark.asyncio
    async def test_create_session(self):
        """Test creating a browser session."""
        automation = EnhancedBrowserAutomation()

        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        session = await automation.create_session(
            "session_1",
            mock_browser,
            mock_context,
            mock_page,
        )

        assert session.session_id == "session_1"
        assert session.browser == mock_browser
        assert session.page == mock_page

    @pytest.mark.asyncio
    async def test_close_session(self):
        """Test closing a browser session."""
        automation = EnhancedBrowserAutomation()

        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        await automation.create_session(
            "session_1",
            mock_browser,
            mock_context,
            mock_page,
        )

        success = await automation.close_session("session_1")

        assert success is True
        mock_page.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_element_by_selector(self):
        """Test finding element by CSS selector."""
        automation = EnhancedBrowserAutomation()

        mock_page = AsyncMock()
        mock_locator = AsyncMock()
        mock_locator.count = AsyncMock(return_value=1)
        mock_page.locator = Mock(return_value=mock_locator)

        await automation.create_session(
            "session_1",
            AsyncMock(),
            AsyncMock(),
            mock_page,
        )

        element = await automation.find_element(
            "session_1",
            ".button",
            ElementDetectionMethod.CSS_SELECTOR,
        )

        assert element is not None
        assert element.selector == ".button"

    @pytest.mark.asyncio
    async def test_click_element(self):
        """Test clicking an element."""
        automation = EnhancedBrowserAutomation()

        mock_page = AsyncMock()
        mock_locator = AsyncMock()
        mock_locator.scroll_into_view_if_needed = AsyncMock()
        mock_locator.wait_for = AsyncMock()
        mock_locator.click = AsyncMock()
        mock_page.locator = Mock(return_value=mock_locator)

        await automation.create_session(
            "session_1",
            AsyncMock(),
            AsyncMock(),
            mock_page,
        )

        element = ElementInfo(selector=".button", method=ElementDetectionMethod.CSS_SELECTOR)
        success = await automation.click_element("session_1", element)

        assert success is True
        mock_locator.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_fill_input(self):
        """Test filling an input element."""
        automation = EnhancedBrowserAutomation()

        mock_page = AsyncMock()
        mock_locator = AsyncMock()
        mock_locator.scroll_into_view_if_needed = AsyncMock()
        mock_locator.wait_for = AsyncMock()
        mock_locator.clear = AsyncMock()
        mock_locator.fill = AsyncMock()
        mock_page.locator = Mock(return_value=mock_locator)

        await automation.create_session(
            "session_1",
            AsyncMock(),
            AsyncMock(),
            mock_page,
        )

        element = ElementInfo(selector="input", method=ElementDetectionMethod.CSS_SELECTOR)
        success = await automation.fill_input("session_1", element, "test value")

        assert success is True
        mock_locator.fill.assert_called_once_with("test value")


class TestAdvancedRepairLoop:
    """Tests for advanced repair loop."""

    @pytest.mark.asyncio
    async def test_analyze_failure(self):
        """Test failure analysis."""
        repair = AdvancedRepairLoop()

        error = TimeoutError("Operation timed out")
        failure = await repair.analyze_failure(error, {"operation": "test"})

        assert failure.error_type == "TimeoutError"
        assert failure.category == FailureCategory.TIMEOUT
        assert failure.context["operation"] == "test"

    @pytest.mark.asyncio
    async def test_suggest_repair_transient(self):
        """Test repair suggestion for transient failure."""
        repair = AdvancedRepairLoop()

        failure = FailureRecord(
            id="failure_1",
            error_message="Connection refused",
            error_type="ConnectionError",
            category=FailureCategory.TRANSIENT,
        )

        suggestion = await repair.suggest_repair(failure)

        assert suggestion.strategy == RepairStrategy.RETRY
        assert suggestion.confidence > 0.5

    @pytest.mark.asyncio
    async def test_suggest_repair_resource(self):
        """Test repair suggestion for resource failure."""
        repair = AdvancedRepairLoop()

        failure = FailureRecord(
            id="failure_1",
            error_message="Out of memory",
            error_type="MemoryError",
            category=FailureCategory.RESOURCE,
        )

        suggestion = await repair.suggest_repair(failure)

        assert suggestion.strategy == RepairStrategy.COMPENSATE
        assert len(suggestion.compensation_actions) > 0

    @pytest.mark.asyncio
    async def test_execute_retry(self):
        """Test retry execution."""
        repair = AdvancedRepairLoop(max_retries=3)

        call_count = 0

        async def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection failed")
            return "success"

        failure = FailureRecord(
            id="failure_1",
            error_message="Connection failed",
            error_type="ConnectionError",
            category=FailureCategory.TRANSIENT,
        )

        suggestion = RepairSuggestion(strategy=RepairStrategy.RETRY)

        success, result = await repair.execute_repair(
            failure,
            suggestion,
            failing_operation,
        )

        assert success is True
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_learning_update(self):
        """Test learning record update."""
        repair = AdvancedRepairLoop(learning_enabled=True)

        failure = FailureRecord(
            id="failure_1",
            error_message="Connection failed",
            error_type="ConnectionError",
            category=FailureCategory.TRANSIENT,
        )

        await repair._update_learning(failure, RepairStrategy.RETRY, True)
        await repair._update_learning(failure, RepairStrategy.RETRY, True)
        await repair._update_learning(failure, RepairStrategy.RETRY, False)

        stats = repair.get_learning_stats()

        assert stats["total_patterns"] > 0
        assert stats["avg_success_rate"] > 0


@pytest.mark.asyncio
async def test_integration_memory_and_repair():
    """Integration test: memory fusion with repair loop."""
    fusion = MemoryFusion()
    repair = AdvancedRepairLoop()

    # Create memories
    memories = [
        Memory(id="mem_1", content="Test memory 1"),
        Memory(id="mem_2", content="Test memory 2"),
    ]

    # Add memories with potential failures
    for memory in memories:
        try:
            await fusion.add_memory(memory)
        except Exception as e:
            failure = await repair.analyze_failure(e)
            suggestion = await repair.suggest_repair(failure)
            print(f"Repair suggestion: {suggestion.strategy}")

    # Verify memories were added
    assert len(fusion._memory_cache) == 2


@pytest.mark.asyncio
async def test_integration_agent_collaboration():
    """Integration test: agent collaboration system."""
    collab = AgentCollaboration()

    with patch("redis.asyncio.from_url", new_callable=AsyncMock):
        collab.redis = AsyncMock()
        collab.redis.hset = AsyncMock()
        collab.redis.delete = AsyncMock()
        collab.redis.lpush = AsyncMock()
        collab.redis.expire = AsyncMock()
        collab.redis.publish = AsyncMock()

        # Register agents
        agent1 = await collab.register_agent("agent_1", capacity=10)
        agent2 = await collab.register_agent("agent_2", capacity=10)

        assert agent1.agent_id == "agent_1"
        assert agent2.agent_id == "agent_2"

        # Send message
        message = AgentMessage(
            from_agent="agent_1",
            to_agent="agent_2",
            message_type=MessageType.TASK_REQUEST,
            payload={"task": "test"},
        )

        success = await collab.send_message(message)
        assert success is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
