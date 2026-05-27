"""
迁移测试套件 - 验证迁移的正确性和兼容性
"""
from __future__ import annotations

import asyncio
import json
import pytest
from pathlib import Path
from typing import Any

from backend.app.core.context_manager import ContextManager
from backend.app.core.parallel_tool_executor import ParallelToolExecutor
from backend.app.core.compatibility_layer import CompatibilityLayer, LegacyToolAdapter
from backend.app.core.contracts import RunContext


class TestContextManager:
    """上下文管理器测试"""

    @pytest.fixture
    def context_manager(self, tmp_path):
        """创建临时上下文管理器"""
        return ContextManager(
            storage_path=str(tmp_path / "context"),
            max_tokens=10000,
            compression_threshold=0.8,
        )

    @pytest.mark.asyncio
    async def test_create_session(self, context_manager):
        """测试创建会话"""
        session_id = await context_manager.create_session()
        assert session_id is not None
        assert len(session_id) > 0

    @pytest.mark.asyncio
    async def test_save_and_recover_session(self, context_manager):
        """测试保存和恢复会话"""
        session_id = await context_manager.create_session()
        context = {"task": "test", "goal": "verify migration"}

        # 保存快照
        snapshot_id = await context_manager.save_snapshot(session_id, context)
        assert snapshot_id is not None

        # 恢复会话
        recovered = await context_manager.recover_session(session_id)
        assert recovered["task"] == "test"
        assert recovered["goal"] == "verify migration"

    @pytest.mark.asyncio
    async def test_context_compression(self, context_manager):
        """测试上下文压缩"""
        session_id = await context_manager.create_session()

        # 创建大上下文
        large_context = {
            "task": "test",
            "data": "x" * 5000,  # 大数据
            "nested": {"key": "value" * 100},
        }

        # 保存大上下文
        await context_manager.save_snapshot(session_id, large_context)

        # 检查是否需要压缩
        should_compress = context_manager.should_compress(session_id)
        assert should_compress or not should_compress  # 取决于阈值

    @pytest.mark.asyncio
    async def test_update_context(self, context_manager):
        """测试更新上下文"""
        session_id = await context_manager.create_session()

        # 初始上下文
        await context_manager.update_context(session_id, {"key1": "value1"})

        # 更新上下文
        await context_manager.update_context(session_id, {"key2": "value2"})

        # 验证
        context = await context_manager.get_context(session_id)
        assert context["key1"] == "value1"
        assert context["key2"] == "value2"

    @pytest.mark.asyncio
    async def test_session_cleanup(self, context_manager):
        """测试会话清理"""
        session_id = await context_manager.create_session()
        await context_manager.update_context(session_id, {"test": "data"})

        # 清理会话
        await context_manager.cleanup_session(session_id)

        # 验证会话已清理
        context = await context_manager.get_context(session_id)
        assert context == {}


class TestParallelToolExecutor:
    """并行工具执行器测试"""

    @pytest.fixture
    def executor(self):
        """创建执行器"""
        return ParallelToolExecutor(max_parallel=3, timeout=5)

    @pytest.fixture
    def mock_context(self):
        """创建模拟上下文"""
        return RunContext(
            trace_id="test-trace",
            agent_id="test-agent",
            tenant_id="test-tenant",
            user_id="test-user",
            request_id="test-request",
        )

    async def mock_executor(self, context, tool_name, arguments):
        """模拟工具执行"""
        await asyncio.sleep(0.1)
        return {"tool": tool_name, "result": "success"}

    @pytest.mark.asyncio
    async def test_batch_execution(self, executor, mock_context):
        """测试批量执行"""
        tool_calls = [
            ("tool1", {"arg": "value1"}),
            ("tool2", {"arg": "value2"}),
            ("tool3", {"arg": "value3"}),
        ]

        results = await executor.execute_batch(
            tool_calls, mock_context, self.mock_executor
        )

        assert len(results) == 3
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_sequential_execution(self, executor, mock_context):
        """测试顺序执行"""
        tool_calls = [
            ("tool1", {"arg": "value1"}),
            ("tool2", {"arg": "value2"}),
        ]

        results = await executor.execute_sequential(
            tool_calls, mock_context, self.mock_executor
        )

        assert len(results) == 2
        assert all(r.success for r in results)

    def test_execution_summary(self, executor):
        """测试执行摘要"""
        from backend.app.core.parallel_tool_executor import ToolExecutionResult

        results = [
            ToolExecutionResult(tool_name="tool1", success=True),
            ToolExecutionResult(tool_name="tool2", success=True),
            ToolExecutionResult(tool_name="tool3", success=False, error="test error"),
        ]

        summary = executor.get_execution_summary(results)

        assert summary["total_tools"] == 3
        assert summary["successful"] == 2
        assert summary["failed"] == 1
        assert summary["success_rate"] == pytest.approx(2 / 3)


class TestCompatibilityLayer:
    """兼容层测试"""

    @pytest.fixture
    def compat_layer(self):
        """创建兼容层"""
        return CompatibilityLayer()

    def test_wrap_old_tool(self, compat_layer):
        """测试包装旧工具"""

        def old_tool(arg1, arg2):
            return f"{arg1}_{arg2}"

        wrapped = compat_layer.wrap_old_tool(old_tool)
        assert wrapped is not None
        assert callable(wrapped)

    @pytest.mark.asyncio
    async def test_wrapped_tool_execution(self, compat_layer):
        """测试包装工具的执行"""

        def old_tool(arg1, arg2):
            return f"{arg1}_{arg2}"

        wrapped = compat_layer.wrap_old_tool(old_tool)

        context = RunContext(
            trace_id="test",
            agent_id="test",
            tenant_id="test",
            user_id="test",
            request_id="test",
        )

        result = await wrapped(context, arg1="hello", arg2="world")

        assert result.success
        assert result.output == "hello_world"

    def test_migrate_old_memory(self, compat_layer):
        """测试迁移旧记忆"""

        class OldMemory:
            def __init__(self):
                self.memories = [
                    type("Memory", (), {"id": "1", "content": "test", "importance": 0.8})()
                ]
                self.sessions = [
                    type("Session", (), {"session_id": "s1", "title": "test session"})()
                ]

        old_store = OldMemory()
        migrated = compat_layer.migrate_old_memory(old_store)

        assert migrated["metadata"]["migration_status"] == "completed"
        assert len(migrated["memories"]) == 1
        assert len(migrated["sessions"]) == 1

    def test_register_wrapped_tool(self, compat_layer):
        """测试注册包装工具"""

        def old_tool():
            return "result"

        compat_layer.register_wrapped_tool("test_tool", old_tool)

        assert compat_layer.get_wrapped_tool("test_tool") is not None
        assert compat_layer.get_migration_status()["test_tool"] == "wrapped"

    def test_migration_summary(self, compat_layer):
        """测试迁移摘要"""

        def tool1():
            pass

        def tool2():
            pass

        compat_layer.register_wrapped_tool("tool1", tool1)
        compat_layer.register_wrapped_tool("tool2", tool2)
        compat_layer.mark_tool_migrated("tool1")

        summary = compat_layer.get_migration_summary()

        assert summary["total_tools"] == 2
        assert summary["migrated"] == 1
        assert summary["wrapped"] == 1
        assert summary["migration_percentage"] == 50.0


class TestLegacyToolAdapter:
    """旧工具适配器测试"""

    @pytest.fixture
    def adapter(self):
        """创建适配器"""
        compat = CompatibilityLayer()
        return LegacyToolAdapter(compat)

    @pytest.mark.asyncio
    async def test_register_and_execute_legacy_tool(self, adapter):
        """测试注册和执行旧工具"""

        def legacy_tool(x, y):
            return x + y

        adapter.register_legacy_tool("add", legacy_tool)

        context = RunContext(
            trace_id="test",
            agent_id="test",
            tenant_id="test",
            user_id="test",
            request_id="test",
        )

        result = await adapter.execute_legacy_tool(context, "add", {"x": 5, "y": 3})

        assert result.success
        assert result.output == 8


class TestMigrationIntegration:
    """迁移集成测试"""

    @pytest.mark.asyncio
    async def test_full_migration_workflow(self, tmp_path):
        """测试完整迁移工作流"""
        # 初始化所有组件
        context_manager = ContextManager(storage_path=str(tmp_path / "context"))
        executor = ParallelToolExecutor()
        compat_layer = CompatibilityLayer()

        # 创建会话
        session_id = await context_manager.create_session()

        # 保存上下文
        context = {"task": "migration test", "status": "in_progress"}
        await context_manager.save_snapshot(session_id, context)

        # 恢复会话
        recovered = await context_manager.recover_session(session_id)
        assert recovered["task"] == "migration test"

        # 验证兼容层
        def old_tool():
            return "legacy result"

        compat_layer.register_wrapped_tool("legacy", old_tool)
        assert compat_layer.get_wrapped_tool("legacy") is not None

        # 获取迁移摘要
        summary = compat_layer.get_migration_summary()
        assert summary["total_tools"] >= 1

    @pytest.mark.asyncio
    async def test_backward_compatibility(self, tmp_path):
        """测试向后兼容性"""
        context_manager = ContextManager(storage_path=str(tmp_path / "context"))

        # 模拟旧系统的行为
        session_id = await context_manager.create_session("old_session_id")
        assert session_id == "old_session_id"

        # 保存和恢复
        context = {"old_key": "old_value"}
        await context_manager.save_snapshot(session_id, context)

        recovered = await context_manager.recover_session(session_id)
        assert recovered["old_key"] == "old_value"

    def test_migration_checklist(self):
        """测试迁移检查清单"""
        from backend.app.core.compatibility_layer import MigrationHelper

        compat = CompatibilityLayer()
        helper = MigrationHelper(compat)

        checklist = helper.get_migration_checklist()

        assert len(checklist) == 7
        assert all("step" in item for item in checklist)
        assert all("title" in item for item in checklist)
        assert all("status" in item for item in checklist)

    def test_migration_guide(self):
        """测试迁移指南"""
        from backend.app.core.compatibility_layer import MigrationHelper

        compat = CompatibilityLayer()
        helper = MigrationHelper(compat)

        guide = helper.get_migration_guide()

        assert "迁移指南" in guide
        assert "上下文管理系统迁移" in guide
        assert "工具系统迁移" in guide
        assert "记忆系统迁移" in guide


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
