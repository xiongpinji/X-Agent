"""Archived with backend/app/core/task_dispatcher.py (P1-09 batch A, 2026-08-04).

Ghost-module test split out of tests/test_feature_enhancements.py.
Imports point at the archived module path; kept as record, not for collection.
"""

from backend.app.core.task_dispatcher import (
    TaskDispatcher,
    Task,
    TaskStatus,
    TaskPriority,
)


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
