"""
Comprehensive tests for X-Agent feature enhancements.

Tests for memory fusion, multi-agent collaboration, browser automation,
and repair loop functionality.
"""

import pytest
from datetime import datetime, timedelta
from backend.app.services.memory.hybrid_retriever import (
    HybridRetriever,
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
