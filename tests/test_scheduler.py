"""
Tests for scheduler functionality.

Tests cron scheduling, task dependencies, priority queue, and monitoring.
"""

import pytest
import asyncio
from datetime import datetime, UTC, timedelta

from backend.app.core.scheduler import cron_scheduler, ScheduleType, ScheduleStatus
from backend.app.core.task_dependencies import task_dependency_manager
from backend.app.core.task_queue import task_queue, TaskPriority
from backend.app.core.task_monitor import task_monitor


@pytest.mark.asyncio
async def test_schedule_interval():
    """Test interval-based scheduling."""
    async def dummy_task():
        return "executed"

    task_id = cron_scheduler.schedule_interval(
        name="test task",
        coroutine=dummy_task,
        interval_seconds=60,
    )

    assert task_id.startswith("task_")
    assert task_id in cron_scheduler.scheduled_tasks

    status = cron_scheduler.get_task_status(task_id)
    assert status is not None
    assert status["schedule_type"] == "interval"
    assert status["interval_seconds"] == 60


@pytest.mark.asyncio
async def test_schedule_cron():
    """Test cron-based scheduling."""
    async def dummy_task():
        return "executed"

    task_id = cron_scheduler.schedule_cron(
        name="daily task",
        coroutine=dummy_task,
        cron_expression="0 9 * * *",
    )

    assert task_id in cron_scheduler.scheduled_tasks

    status = cron_scheduler.get_task_status(task_id)
    assert status["schedule_type"] == "cron"
    assert status["cron_expression"] == "0 9 * * *"


@pytest.mark.asyncio
async def test_schedule_once():
    """Test one-time scheduling."""
    async def dummy_task():
        return "executed"

    run_at = datetime.now(UTC) + timedelta(hours=1)

    task_id = cron_scheduler.schedule_once(
        name="one-time task",
        coroutine=dummy_task,
        run_at=run_at,
    )

    assert task_id in cron_scheduler.scheduled_tasks

    status = cron_scheduler.get_task_status(task_id)
    assert status["schedule_type"] == "once"
    assert status["max_runs"] == 1


@pytest.mark.asyncio
async def test_pause_resume_task():
    """Test pausing and resuming a task."""
    async def dummy_task():
        return "executed"

    task_id = cron_scheduler.schedule_interval(
        name="test task",
        coroutine=dummy_task,
        interval_seconds=60,
    )

    # Pause
    success = cron_scheduler.pause_task(task_id)
    assert success

    status = cron_scheduler.get_task_status(task_id)
    assert status["status"] == "paused"

    # Resume
    success = cron_scheduler.resume_task(task_id)
    assert success

    status = cron_scheduler.get_task_status(task_id)
    assert status["status"] == "active"


@pytest.mark.asyncio
async def test_cancel_task():
    """Test canceling a task."""
    async def dummy_task():
        return "executed"

    task_id = cron_scheduler.schedule_interval(
        name="test task",
        coroutine=dummy_task,
        interval_seconds=60,
    )

    success = cron_scheduler.cancel_task(task_id)
    assert success

    status = cron_scheduler.get_task_status(task_id)
    assert status["status"] == "disabled"


@pytest.mark.asyncio
async def test_list_tasks():
    """Test listing scheduled tasks."""
    async def dummy_task():
        return "executed"

    task_id_1 = cron_scheduler.schedule_interval(
        name="task 1",
        coroutine=dummy_task,
        interval_seconds=60,
    )

    task_id_2 = cron_scheduler.schedule_interval(
        name="task 2",
        coroutine=dummy_task,
        interval_seconds=120,
    )

    tasks = cron_scheduler.list_tasks()

    assert len(tasks) >= 2
    assert any(t["task_id"] == task_id_1 for t in tasks)
    assert any(t["task_id"] == task_id_2 for t in tasks)


def test_add_task_dependency():
    """Test adding task dependencies."""
    task_dependency_manager.add_task("task_a")
    task_dependency_manager.add_task("task_b")
    task_dependency_manager.add_task("task_c")

    # Add dependencies
    success = task_dependency_manager.add_dependency("task_b", "task_a")
    assert success

    success = task_dependency_manager.add_dependency("task_c", "task_b")
    assert success

    # Check dependencies
    deps_b = task_dependency_manager.get_dependencies("task_b")
    assert "task_a" in deps_b

    deps_c = task_dependency_manager.get_dependencies("task_c")
    assert "task_b" in deps_c


def test_resolve_dependencies():
    """Test resolving transitive dependencies."""
    task_dependency_manager.add_task("task_1")
    task_dependency_manager.add_task("task_2")
    task_dependency_manager.add_task("task_3")

    task_dependency_manager.add_dependency("task_2", "task_1")
    task_dependency_manager.add_dependency("task_3", "task_2")

    # Resolve all dependencies for task_3
    all_deps = task_dependency_manager.resolve_dependencies("task_3")

    assert "task_2" in all_deps
    assert "task_1" in all_deps


def test_execution_order():
    """Test topological sort for execution order."""
    task_dependency_manager.add_task("a")
    task_dependency_manager.add_task("b")
    task_dependency_manager.add_task("c")
    task_dependency_manager.add_task("d")

    task_dependency_manager.add_dependency("b", "a")
    task_dependency_manager.add_dependency("c", "a")
    task_dependency_manager.add_dependency("d", "b")
    task_dependency_manager.add_dependency("d", "c")

    order = task_dependency_manager.get_execution_order(["a", "b", "c", "d"])

    # A should come first
    assert order[0] == "a"
    # D should come last
    assert order[-1] == "d"


def test_cycle_detection():
    """Test cycle detection in dependencies."""
    task_dependency_manager.add_task("x")
    task_dependency_manager.add_task("y")
    task_dependency_manager.add_task("z")

    task_dependency_manager.add_dependency("y", "x")
    task_dependency_manager.add_dependency("z", "y")

    # This should create a cycle
    success = task_dependency_manager.add_dependency("x", "z")

    assert not success  # Should fail due to cycle


@pytest.mark.asyncio
async def test_enqueue_task():
    """Test enqueueing a task."""
    task_id = await task_queue.enqueue(
        name="test task",
        payload={"key": "value"},
        priority=TaskPriority.NORMAL,
    )

    assert task_id.startswith("task_")

    size = await task_queue.size()
    assert size >= 1


@pytest.mark.asyncio
async def test_dequeue_task():
    """Test dequeueing a task."""
    task_id = await task_queue.enqueue(
        name="test task",
        payload={"key": "value"},
        priority=TaskPriority.NORMAL,
    )

    task = await task_queue.dequeue(timeout_seconds=1)

    assert task is not None
    assert task.task_id == task_id


@pytest.mark.asyncio
async def test_priority_queue():
    """Test priority-based task queue."""
    # Enqueue tasks with different priorities
    low_id = await task_queue.enqueue(
        name="low priority",
        payload={},
        priority=TaskPriority.LOW,
    )

    high_id = await task_queue.enqueue(
        name="high priority",
        payload={},
        priority=TaskPriority.HIGH,
    )

    # Dequeue should get high priority first
    task = await task_queue.dequeue(timeout_seconds=1)
    assert task.task_id == high_id

    task = await task_queue.dequeue(timeout_seconds=1)
    assert task.task_id == low_id


@pytest.mark.asyncio
async def test_task_retry():
    """Test task retry in queue."""
    task_id = await task_queue.enqueue(
        name="retry task",
        payload={},
        priority=TaskPriority.NORMAL,
        max_retries=2,
    )

    # Dequeue
    task = await task_queue.dequeue(timeout_seconds=1)
    assert task.retry_count == 0

    # Re-queue for retry
    success = await task_queue.requeue_task(task_id)
    assert success

    # Dequeue again
    task = await task_queue.dequeue(timeout_seconds=1)
    assert task.retry_count == 1


@pytest.mark.asyncio
async def test_queue_pause_resume():
    """Test pausing and resuming queue."""
    await task_queue.pause()

    status = task_queue.status.value
    assert status == "paused"

    await task_queue.resume()

    status = task_queue.status.value
    assert status == "running"


@pytest.mark.asyncio
async def test_queue_stats():
    """Test queue statistics."""
    await task_queue.enqueue(
        name="task 1",
        payload={},
        priority=TaskPriority.NORMAL,
    )

    stats = await task_queue.get_stats()

    assert "queue_size" in stats
    assert "max_size" in stats
    assert "status" in stats
    assert "priority_breakdown" in stats


def test_record_task_execution():
    """Test recording task execution metrics."""
    task_monitor.record_task_execution(
        task_id="task_1",
        name="test task",
        duration_seconds=1.5,
        success=True,
    )

    metrics = task_monitor.get_task_metrics("task_1")

    assert metrics is not None
    assert metrics.total_executions == 1
    assert metrics.successful_executions == 1
    assert metrics.avg_duration_seconds == 1.5


def test_task_failure_metrics():
    """Test recording task failures."""
    task_monitor.record_task_execution(
        task_id="task_2",
        name="failing task",
        duration_seconds=0.5,
        success=False,
        error="Test error",
    )

    metrics = task_monitor.get_task_metrics("task_2")

    assert metrics.failed_executions == 1
    assert metrics.last_error == "Test error"
    assert metrics.success_rate == 0.0


def test_health_status():
    """Test health status calculation."""
    # Record some successful executions
    for i in range(10):
        task_monitor.record_task_execution(
            task_id="healthy_task",
            name="healthy task",
            duration_seconds=0.1,
            success=True,
        )

    health = task_monitor.get_health_status()

    assert health["status"] in ["healthy", "degraded", "unhealthy"]
    assert "overall_success_rate" in health


def test_performance_summary():
    """Test performance summary."""
    task_monitor.record_task_execution(
        task_id="perf_task",
        name="performance task",
        duration_seconds=2.0,
        success=True,
    )

    summary = task_monitor.get_performance_summary()

    assert "total_tasks" in summary
    assert "total_executions" in summary
    assert "total_duration_seconds" in summary


def test_top_tasks_by_duration():
    """Test getting top tasks by duration."""
    task_monitor.record_task_execution(
        task_id="slow_task",
        name="slow task",
        duration_seconds=5.0,
        success=True,
    )

    task_monitor.record_task_execution(
        task_id="fast_task",
        name="fast task",
        duration_seconds=0.1,
        success=True,
    )

    top_tasks = task_monitor.get_top_tasks_by_duration(limit=2)

    assert len(top_tasks) >= 1
    assert top_tasks[0].task_id == "slow_task"


def test_scheduler_stats():
    """Test scheduler statistics."""
    stats = cron_scheduler.get_scheduler_stats()

    assert "total_tasks" in stats
    assert "status_breakdown" in stats
    assert "total_executions" in stats
