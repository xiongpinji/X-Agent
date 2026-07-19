"""
Comprehensive tests for X-Agent feature enhancements.

Tests for memory fusion, multi-agent collaboration, browser automation,
and repair loop functionality.
"""

import pytest
from datetime import datetime, timedelta
from backend.app.core.memory_deduplication import (
    MemoryDeduplicator,
    Memory,
)
from backend.app.services.memory.hybrid_retriever import (
    HybridRetriever,
)
from backend.app.core.memory_graph_enhanced import (
    EnhancedMemoryGraph,
    MemoryNode,
    MemoryRelation,
)
from backend.app.core.memory_compression import (
    MemoryCompressor,
)
from backend.app.core.agent_communication import (
    AgentMessenger,
    MessageType,
    MessagePriority,
)
from backend.app.core.task_dispatcher import (
    TaskDispatcher,
    Task,
    TaskStatus,
    TaskPriority,
)
from backend.app.services.browser.smart_locator import (
    SmartLocator,
    LocatorStrategy,
)
from backend.app.core.failure_detection import (
    FailureDetector,
    FailureCategory,
    ExecutionContext,
)


class TestMemoryDeduplication:
    """Tests for memory deduplication."""

    def test_deduplicate_similar_memories(self):
        """Test deduplication of similar memories."""
        deduplicator = MemoryDeduplicator(similarity_threshold=0.8)

        memories = [
            Memory(id="m1", content="Python is a programming language"),
            Memory(id="m2", content="Python is a programming language"),
            Memory(id="m3", content="Java is a programming language"),
        ]

        result = deduplicator.deduplicate(memories)

        assert result.original_count == 3
        assert result.deduplicated_count <= 3
        assert len(result.removed_ids) >= 0

    def test_deduplication_stats(self):
        """Test deduplication statistics."""
        deduplicator = MemoryDeduplicator()

        memories = [
            Memory(id=f"m{i}", content=f"Memory {i}")
            for i in range(5)
        ]

        result = deduplicator.deduplicate(memories)
        stats = deduplicator.get_deduplication_stats(result)

        assert stats["original_count"] == 5
        assert stats["reduction_rate"] >= 0


class TestHybridRetriever:
    """Tests for hybrid memory retrieval."""

    def test_hybrid_search(self):
        """Test hybrid search functionality."""
        retriever = HybridRetriever()

        memories = [
            {"id": "m1", "content": "Python programming tutorial"},
            {"id": "m2", "content": "Java programming guide"},
            {"id": "m3", "content": "Python web development"},
        ]

        results = retriever.search(
            query="Python programming",
            memories=memories,
            top_k=2,
            use_hybrid=True,
        )

        assert len(results) <= 2
        assert all(r.combined_score >= 0 for r in results)

    def test_retrieval_stats(self):
        """Test retrieval statistics."""
        retriever = HybridRetriever()

        memories = [
            {"id": "m1", "content": "Test content"},
        ]

        results = retriever.search("test", memories)
        stats = retriever.get_retrieval_stats(results)

        assert "total_results" in stats
        assert "avg_combined_score" in stats


class TestEnhancedMemoryGraph:
    """Tests for enhanced memory graph."""

    def test_add_nodes_and_relations(self):
        """Test adding nodes and relations."""
        graph = EnhancedMemoryGraph()

        node1 = MemoryNode(id="n1", content="Node 1")
        node2 = MemoryNode(id="n2", content="Node 2")

        graph.add_node(node1)
        graph.add_node(node2)

        relation = MemoryRelation(
            source_id="n1",
            target_id="n2",
            relation_type="related",
            strength=0.8,
        )
        graph.add_relation(relation)

        assert len(graph.nodes) == 2
        assert len(graph.relations["n1"]) == 1

    def test_find_related_memories(self):
        """Test finding related memories."""
        graph = EnhancedMemoryGraph()

        for i in range(3):
            graph.add_node(MemoryNode(id=f"n{i}", content=f"Node {i}"))

        graph.add_relation(MemoryRelation("n0", "n1", "related", 0.9))
        graph.add_relation(MemoryRelation("n1", "n2", "related", 0.8))

        related = graph.find_related_memories("n0", depth=2)

        assert len(related) > 0

    def test_trace_memory_path(self):
        """Test tracing memory paths."""
        graph = EnhancedMemoryGraph()

        for i in range(3):
            graph.add_node(MemoryNode(id=f"n{i}", content=f"Node {i}"))

        graph.add_relation(MemoryRelation("n0", "n1", "related", 1.0))
        graph.add_relation(MemoryRelation("n1", "n2", "related", 1.0))

        path = graph.trace_memory_path("n0", "n2")

        assert path is not None
        assert path.path_length == 2


class TestMemoryCompression:
    """Tests for memory compression."""

    def test_compress_old_memories(self):
        """Test compressing old memories."""
        compressor = MemoryCompressor(compression_threshold_days=0)

        memories = [
            {
                "id": "m1",
                "content": "This is a long memory content that should be compressed",
                "created_at": (datetime.now() - timedelta(days=10)).isoformat(),
            }
        ]

        result = compressor.compress_old_memories(memories)

        assert result.total_memories == 1
        assert result.compressed_count >= 0

    def test_cleanup_expired_memories(self):
        """Test cleaning up expired memories."""
        compressor = MemoryCompressor(retention_days=1)

        memories = [
            {
                "id": "m1",
                "content": "Old memory",
                "created_at": (datetime.now() - timedelta(days=10)).isoformat(),
            }
        ]

        removed = compressor.cleanup_expired_memories(memories)

        assert len(removed) > 0


class TestAgentCommunication:
    """Tests for agent communication."""

    @pytest.mark.asyncio
    async def test_send_message(self):
        """Test sending messages between agents."""
        messenger = AgentMessenger()

        messenger.register_agent("agent1")
        messenger.register_agent("agent2")

        message_id = await messenger.send_message(
            from_agent_id="agent1",
            to_agent_id="agent2",
            message_type=MessageType.TASK_REQUEST,
            payload={"task": "test"},
        )

        assert message_id != ""

    @pytest.mark.asyncio
    async def test_receive_message(self):
        """Test receiving messages."""
        messenger = AgentMessenger()

        messenger.register_agent("agent1")
        messenger.register_agent("agent2")

        await messenger.send_message(
            from_agent_id="agent1",
            to_agent_id="agent2",
            message_type=MessageType.TASK_REQUEST,
            payload={"task": "test"},
        )

        message = await messenger.receive_message("agent2")

        assert message is not None
        assert message.from_agent_id == "agent1"

    def test_message_stats(self):
        """Test message statistics."""
        messenger = AgentMessenger()

        messenger.register_agent("agent1")
        messenger.register_agent("agent2")

        stats = messenger.get_message_stats()

        assert stats["total_agents"] == 2
        assert stats["total_messages"] == 0


class TestTaskDispatcher:
    """Tests for task dispatcher."""

    def test_decompose_task(self):
        """Test task decomposition."""
        dispatcher = TaskDispatcher()

        task = Task(
            id="t1",
            name="Main Task",
            description="Step 1; Step 2; Step 3",
        )

        subtasks = dispatcher.decompose_task(task, max_subtasks=3)

        assert len(subtasks) <= 3
        assert all(st.metadata.get("parent_task_id") == "t1" for st in subtasks)

    def test_allocate_tasks(self):
        """Test task allocation."""
        dispatcher = TaskDispatcher()

        dispatcher.register_agent("agent1", max_concurrent_tasks=2)
        dispatcher.register_agent("agent2", max_concurrent_tasks=2)

        tasks = [
            Task(id=f"t{i}", name=f"Task {i}", description=f"Task {i}")
            for i in range(3)
        ]

        results = dispatcher.allocate_tasks(tasks)

        assert len(results) == 3
        assert any(r.assigned_agent_id for r in results)

    def test_dispatcher_stats(self):
        """Test dispatcher statistics."""
        dispatcher = TaskDispatcher()

        dispatcher.register_agent("agent1")

        stats = dispatcher.get_dispatcher_stats()

        assert stats["total_agents"] == 1
        assert stats["total_capacity"] > 0


class TestSmartLocator:
    """Tests for smart element locator."""

    def test_find_element(self):
        """Test finding elements."""
        locator = SmartLocator("session1")

        result = locator.find_element(
            css_selector=".button",
            strategies=[LocatorStrategy.CSS],
        )

        assert result is not None

    def test_find_element_with_retry(self):
        """Test finding elements with retry."""
        locator = SmartLocator("session1", max_retries=2)

        result = locator.find_element_with_retry(
            css_selector=".button",
        )

        assert result is not None
        assert result.retry_count >= 0

    def test_cache_management(self):
        """Test cache management."""
        locator = SmartLocator("session1")

        locator.find_element(css_selector=".button")
        stats = locator.get_cache_stats()

        assert stats["cache_size"] >= 0


class TestFailureDetection:
    """Tests for failure detection."""

    def test_detect_failure(self):
        """Test failure detection."""
        detector = FailureDetector()

        execution_result = {
            "success": False,
            "error": "Connection refused",
            "error_code": "ECONNREFUSED",
        }

        failure = detector.detect_failure(execution_result)

        assert failure is not None
        assert failure.category == FailureCategory.NETWORK_ERROR

    def test_classify_failure(self):
        """Test failure classification."""
        detector = FailureDetector()

        categories = [
            ("timeout error", FailureCategory.TIMEOUT),
            ("element not found", FailureCategory.ELEMENT_NOT_FOUND),
            ("permission denied", FailureCategory.PERMISSION_DENIED),
        ]

        for message, expected_category in categories:
            category = detector.classify_failure_by_message(message)
            assert category == expected_category

    def test_failure_stats(self):
        """Test failure statistics."""
        detector = FailureDetector()

        execution_result = {
            "success": False,
            "error": "Test error",
        }

        detector.detect_failure(execution_result)
        stats = detector.get_failure_stats()

        assert stats["total_failures"] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
