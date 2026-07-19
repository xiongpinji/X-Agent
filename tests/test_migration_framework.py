"""
迁移测试套件 - 验证Agent引擎和工具系统迁移
"""
import asyncio
import pytest
from pathlib import Path
from datetime import UTC, datetime

from backend.app.core.migration_framework import (
    MigrationFramework,
    MigrationPhase,
    MigrationStatus,
    MigrationVersionManager,
    MigrationVersion,
)
from backend.app.core.agent_context import (
    AgentContextManager,
    AgentSessionRecovery,
    AgentSnapshot,
    AgentCompatibilityAdapter,
)
from backend.app.core.tool_migration import (
    ToolParallelExecutor,
    ToolDependencyGraph,
    ToolResultAggregator,
    ExecutionStrategy,
    ToolExecutionResult,
)


class TestMigrationFramework:
    """迁移框架测试"""

    def test_create_migration_framework(self):
        """测试创建迁移框架"""
        framework = MigrationFramework("1.0.0")
        assert framework.version == "1.0.0"
        assert framework.state.status == MigrationStatus.PENDING
        assert framework.state.phase == MigrationPhase.PREPARATION

    def test_add_checkpoint(self):
        """测试添加检查点"""
        framework = MigrationFramework("1.0.0")
        checkpoint = framework.add_checkpoint(
            "test_checkpoint",
            MigrationPhase.PREPARATION,
            {"test": "data"},
        )
        assert checkpoint.name == "test_checkpoint"
        assert checkpoint.status == MigrationStatus.IN_PROGRESS

    def test_complete_checkpoint(self):
        """测试完成检查点"""
        framework = MigrationFramework("1.0.0")
        checkpoint = framework.add_checkpoint(
            "test_checkpoint",
            MigrationPhase.PREPARATION,
        )
        framework.complete_checkpoint(checkpoint.id)
        assert checkpoint.status == MigrationStatus.COMPLETED

    def test_fail_checkpoint(self):
        """测试检查点失败"""
        framework = MigrationFramework("1.0.0")
        checkpoint = framework.add_checkpoint(
            "test_checkpoint",
            MigrationPhase.PREPARATION,
        )
        framework.fail_checkpoint(checkpoint.id, "Test error")
        assert checkpoint.status == MigrationStatus.FAILED
        assert framework.state.status == MigrationStatus.FAILED

    def test_transition_phase(self):
        """测试阶段转换"""
        framework = MigrationFramework("1.0.0")
        framework.transition_phase(MigrationPhase.EXECUTION)
        assert framework.state.phase == MigrationPhase.EXECUTION

    def test_update_progress(self):
        """测试更新进度"""
        framework = MigrationFramework("1.0.0")
        framework.update_progress(0.5)
        assert framework.state.progress == 0.5

    def test_rollback(self):
        """测试回滚"""
        framework = MigrationFramework("1.0.0")
        checkpoint1 = framework.add_checkpoint(
            "checkpoint1",
            MigrationPhase.PREPARATION,
        )
        checkpoint2 = framework.add_checkpoint(
            "checkpoint2",
            MigrationPhase.EXECUTION,
        )

        # 注册回滚处理器
        rollback_called = []
        framework.register_rollback_handler(
            "checkpoint2",
            lambda: rollback_called.append("checkpoint2"),
        )

        # 执行回滚
        result = framework.rollback(checkpoint1.id)
        assert result is True
        assert framework.state.status == MigrationStatus.ROLLED_BACK

    def test_get_summary(self):
        """测试获取摘要"""
        framework = MigrationFramework("1.0.0")
        framework.add_checkpoint("cp1", MigrationPhase.PREPARATION)
        framework.complete_migration()

        summary = framework.get_summary()
        assert summary["version"] == "1.0.0"
        assert summary["status"] == "completed"
        assert summary["progress"] == 1.0


class TestAgentContextManager:
    """Agent上下文管理器测试"""

    def test_create_session(self):
        """测试创建会话"""
        manager = AgentContextManager()
        session = manager.create_session("test_task", "test_goal")
        assert session.session_id is not None
        assert session.status == "active"

    def test_create_snapshot(self):
        """测试创建快照"""
        manager = AgentContextManager()
        session = manager.create_session("test_task", "test_goal")
        snapshot = manager.create_snapshot(
            session.session_id,
            "test_task",
            "test_goal",
            "planning",
            subtasks=["subtask1"],
        )
        assert snapshot.id is not None
        assert snapshot.stage == "planning"

    def test_get_latest_snapshot(self):
        """测试获取最新快照"""
        manager = AgentContextManager()
        session = manager.create_session("test_task", "test_goal")
        snapshot1 = manager.create_snapshot(
            session.session_id,
            "test_task",
            "test_goal",
            "planning",
        )
        snapshot2 = manager.create_snapshot(
            session.session_id,
            "test_task",
            "test_goal",
            "execution",
        )

        latest = manager.get_latest_snapshot(session.session_id)
        assert latest.id == snapshot2.id

    def test_recover_session(self):
        """测试恢复会话"""
        manager = AgentContextManager()
        session = manager.create_session("test_task", "test_goal")
        manager.update_session_status(session.session_id, "paused")

        recovered = manager.recover_session(session.session_id)
        assert recovered.status == "active"

    def test_compress_context(self):
        """测试压缩上下文"""
        manager = AgentContextManager()
        session = manager.create_session("test_task", "test_goal")
        snapshot = manager.create_snapshot(
            session.session_id,
            "test_task",
            "test_goal",
            "planning",
            context_tokens=1000,
        )

        result = manager.compress_context(snapshot.id, 0.5)
        assert result is True
        assert snapshot.compressed is True


class TestAgentSessionRecovery:
    """Agent会话恢复测试"""

    def test_create_recovery_point(self):
        """测试创建恢复点"""
        manager = AgentContextManager()
        recovery = AgentSessionRecovery(manager)
        session = manager.create_session("test_task", "test_goal")

        recovery_id = recovery.create_recovery_point(
            session.session_id,
            "checkpoint1",
            {"data": "test"},
        )
        assert recovery_id is not None

    def test_recover_from_point(self):
        """测试从恢复点恢复"""
        manager = AgentContextManager()
        recovery = AgentSessionRecovery(manager)
        session = manager.create_session("test_task", "test_goal")

        recovery_id = recovery.create_recovery_point(
            session.session_id,
            "checkpoint1",
            {"data": "test"},
        )

        data = recovery.recover_from_point(recovery_id)
        assert data["data"] == "test"


class TestAgentSnapshot:
    """Agent快照测试"""

    def test_take_snapshot(self):
        """测试拍摄快照"""
        manager = AgentContextManager()
        snapshot_mgr = AgentSnapshot(manager)
        session = manager.create_session("test_task", "test_goal")

        snapshot_id = snapshot_mgr.take_snapshot(
            session.session_id,
            {"state": "test"},
        )
        assert snapshot_id is not None

    def test_restore_snapshot(self):
        """测试恢复快照"""
        manager = AgentContextManager()
        snapshot_mgr = AgentSnapshot(manager)
        session = manager.create_session("test_task", "test_goal")

        snapshot_id = snapshot_mgr.take_snapshot(
            session.session_id,
            {"state": "test"},
        )

        state = snapshot_mgr.restore_snapshot(snapshot_id)
        assert state["state"] == "test"


class TestToolParallelExecutor:
    """工具并行执行器测试"""

    @pytest.mark.asyncio
    async def test_execute_sequential(self):
        """测试顺序执行"""
        executor = ToolParallelExecutor()

        async def tool1():
            return "result1"

        async def tool2():
            return "result2"

        tools = {"tool1": tool1, "tool2": tool2}
        results = await executor.execute_tools(
            tools,
            strategy=ExecutionStrategy.SEQUENTIAL,
        )

        assert len(results) == 2
        assert all(r.status == "success" for r in results)

    @pytest.mark.asyncio
    async def test_execute_parallel(self):
        """测试并行执行"""
        executor = ToolParallelExecutor()

        async def tool1():
            await asyncio.sleep(0.1)
            return "result1"

        async def tool2():
            await asyncio.sleep(0.1)
            return "result2"

        tools = {"tool1": tool1, "tool2": tool2}
        results = await executor.execute_tools(
            tools,
            strategy=ExecutionStrategy.PARALLEL,
        )

        assert len(results) == 2
        assert all(r.status == "success" for r in results)

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self):
        """测试超时执行"""
        executor = ToolParallelExecutor()

        async def slow_tool():
            await asyncio.sleep(10)
            return "result"

        tools = {"slow_tool": slow_tool}
        results = await executor.execute_tools(
            tools,
            timeout_ms=100,
        )

        assert len(results) == 1
        assert results[0].status == "timeout"

    @pytest.mark.asyncio
    async def test_execute_with_dependencies(self):
        """测试带依赖的执行"""
        executor = ToolParallelExecutor()

        async def tool1():
            return "result1"

        async def tool2():
            return "result2"

        tools = {"tool1": tool1, "tool2": tool2}

        from backend.app.core.tool_migration import ToolDependency

        dependencies = {
            "tool1": ToolDependency(tool_id="tool1"),
            "tool2": ToolDependency(tool_id="tool2", depends_on=["tool1"]),
        }

        results = await executor.execute_with_dependencies(
            tools,
            dependencies,
        )

        assert len(results) == 2


class TestToolDependencyGraph:
    """工具依赖图测试"""

    def test_add_dependency(self):
        """测试添加依赖"""
        graph = ToolDependencyGraph()
        graph.add_dependency("tool1", ["tool2", "tool3"])
        assert "tool1" in graph.dependencies
        assert graph.dependencies["tool1"].depends_on == ["tool2", "tool3"]

    def test_get_execution_order(self):
        """测试获取执行顺序"""
        graph = ToolDependencyGraph()
        graph.add_dependency("tool1")
        graph.add_dependency("tool2", ["tool1"])
        graph.add_dependency("tool3", ["tool1"])

        order = graph.get_execution_order(["tool1", "tool2", "tool3"])
        assert order is not None
        assert order[0] == ["tool1"]
        assert set(order[1]) == {"tool2", "tool3"}

    def test_circular_dependency(self):
        """测试循环依赖检测"""
        graph = ToolDependencyGraph()
        graph.add_dependency("tool1", ["tool2"])
        graph.add_dependency("tool2", ["tool1"])

        assert graph.has_circular_dependency() is True


class TestToolResultAggregator:
    """工具结果聚合器测试"""

    def test_add_result(self):
        """测试添加结果"""
        aggregator = ToolResultAggregator()
        result = ToolExecutionResult(
            tool_id="tool1",
            tool_name="tool1",
            status="success",
            result="test_result",
        )
        aggregator.add_result(result)
        assert "tool1" in aggregator.results

    def test_merge_results(self):
        """测试合并结果"""
        aggregator = ToolResultAggregator()
        result1 = ToolExecutionResult(
            tool_id="tool1",
            tool_name="tool1",
            status="success",
            result="result1",
        )
        result2 = ToolExecutionResult(
            tool_id="tool2",
            tool_name="tool2",
            status="success",
            result="result2",
        )
        aggregator.add_result(result1)
        aggregator.add_result(result2)

        merged = aggregator.aggregate_results(["tool1", "tool2"], "merge")
        assert merged["tool1"] == "result1"
        assert merged["tool2"] == "result2"

    def test_summarize_results(self):
        """测试总结结果"""
        aggregator = ToolResultAggregator()
        result1 = ToolExecutionResult(
            tool_id="tool1",
            tool_name="tool1",
            status="success",
            result="result1",
            execution_time_ms=100,
        )
        result2 = ToolExecutionResult(
            tool_id="tool2",
            tool_name="tool2",
            status="failed",
            error="error",
            execution_time_ms=200,
        )
        aggregator.add_result(result1)
        aggregator.add_result(result2)

        summary = aggregator.aggregate_results(["tool1", "tool2"], "summary")
        assert summary["total"] == 2
        assert summary["successful"] == 1
        assert summary["failed"] == 1


class TestMigrationVersionManager:
    """迁移版本管理器测试"""

    def test_register_version(self):
        """测试注册版本"""
        manager = MigrationVersionManager()
        version = MigrationVersion(
            version="1.0.0",
            timestamp=datetime.now(UTC).isoformat(),
            description="Test version",
            components=["agent", "tools"],
        )
        manager.register_version(version)
        assert manager.get_version("1.0.0") is not None

    def test_get_all_versions(self):
        """测试获取所有版本"""
        manager = MigrationVersionManager()
        version1 = MigrationVersion(
            version="1.0.0",
            timestamp=datetime.now(UTC).isoformat(),
            description="Version 1",
            components=["agent"],
        )
        version2 = MigrationVersion(
            version="2.0.0",
            timestamp=datetime.now(UTC).isoformat(),
            description="Version 2",
            components=["agent", "tools"],
        )
        manager.register_version(version1)
        manager.register_version(version2)

        versions = manager.get_all_versions()
        assert len(versions) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
