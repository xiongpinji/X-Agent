"""Extended test coverage for core modules - boundary conditions, exceptions, and concurrency."""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import UTC, datetime, timedelta

from backend.app.core.execution_planner import ExecutionPlanner, ExecutionPlan
from backend.app.core.repair_loop import RepairLoop, RepairSuggestion
from backend.app.core.verification import VerificationEngine, VerificationResult
from backend.app.core.contracts import ToolCallRecord
from backend.app.core.memory import MemoryItem, MemoryScope, MemoryRevision
from backend.app.core.agent_runtime_adapter import AgentRuntimeAdapter
from backend.app.core.agent_state_manager import AgentRunState
from backend.app.core.run_view import RunView


class TestExecutionPlannerBoundaryConditions:
    """Test ExecutionPlanner with boundary conditions."""

    def test_build_plan_with_empty_task(self):
        """Test building plan with empty task string."""
        planner = ExecutionPlanner()
        plan = planner.build("")
        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) > 0
        assert len(plan.verification_steps) > 0

    def test_build_plan_with_very_long_task(self):
        """Test building plan with very long task description."""
        planner = ExecutionPlanner()
        long_task = "x" * 10000
        plan = planner.build(long_task)
        assert isinstance(plan, ExecutionPlan)
        assert plan.metadata["task"] == long_task

    def test_build_plan_with_special_characters(self):
        """Test building plan with special characters in task."""
        planner = ExecutionPlanner()
        special_task = "Task with special chars: !@#$%^&*()_+-=[]{}|;:',.<>?/~`"
        plan = planner.build(special_task)
        assert isinstance(plan, ExecutionPlan)
        assert plan.metadata["task"] == special_task

    def test_build_plan_with_unicode_characters(self):
        """Test building plan with unicode characters."""
        planner = ExecutionPlanner()
        unicode_task = "任务描述 with 中文 and émojis 🚀"
        plan = planner.build(unicode_task)
        assert isinstance(plan, ExecutionPlan)
        assert plan.metadata["task"] == unicode_task

    def test_commands_from_mapping_with_empty_test_files(self):
        """Test command generation with empty test files."""
        from backend.app.core.test_mapper import TestMappingResult

        mapping = TestMappingResult(
            query="test",
            test_files=[],
            related_files=[],
            dependency_hints=[],
            impact_hints=[],
            recommended_commands=[]
        )
        commands = ExecutionPlanner._commands_from_mapping(mapping)
        assert isinstance(commands, list)
        assert len(commands) == 0

    def test_commands_from_mapping_with_mixed_file_types(self):
        """Test command generation with mixed file types."""
        from backend.app.core.test_mapper import TestMappingResult

        mapping = TestMappingResult(
            query="test",
            test_files=[
                {"path": "test_file.py"},
                {"path": "test_file.ts"},
                {"path": "test_file.jsx"},
                {"path": "test_file.unknown"},
                {"path": ""},
            ],
            related_files=[],
            dependency_hints=[],
            impact_hints=[],
            recommended_commands=["npm test"]
        )
        commands = ExecutionPlanner._commands_from_mapping(mapping)
        assert "pytest test_file.py" in commands
        assert "npm test -- test_file.ts" in commands
        assert "npm test -- test_file.jsx" in commands
        assert "npm test" in commands

    def test_commands_from_mapping_deduplication(self):
        """Test that duplicate commands are removed."""
        from backend.app.core.test_mapper import TestMappingResult

        mapping = TestMappingResult(
            query="test",
            test_files=[
                {"path": "test_file.py"},
                {"path": "test_file.py"},
                {"path": "test_file.py"},
            ],
            related_files=[],
            dependency_hints=[],
            impact_hints=[],
            recommended_commands=["pytest test_file.py", "pytest test_file.py"]
        )
        commands = ExecutionPlanner._commands_from_mapping(mapping)
        assert commands.count("pytest test_file.py") == 1


class TestRepairLoopExceptionHandling:
    """Test RepairLoop exception handling and edge cases."""

    def test_analyze_with_validation_error(self):
        """Test repair suggestion for validation errors."""
        repair_loop = RepairLoop()
        tool_call = ToolCallRecord(
            tool_name="test_tool",
            arguments_preview={"arg1": "value1"},
            success=False,
            error_message="Validation failed"
        )

        with patch.object(repair_loop.verifier, 'verify_tool_call') as mock_verify:
            mock_verify.return_value = VerificationResult(
                is_valid=False,
                error_type="validation_error",
                error_message="Invalid arguments"
            )
            result, suggestion = repair_loop.analyze(tool_call)
            assert suggestion.should_retry is True
            assert suggestion.error_type == "validation_error"
            assert suggestion.confidence > 0.9

    def test_analyze_with_missing_resource(self):
        """Test repair suggestion for missing resources."""
        repair_loop = RepairLoop()
        tool_call = ToolCallRecord(
            tool_name="read_file",
            arguments_preview={"path": "/nonexistent/file.txt"},
            success=False,
            error_message="File not found"
        )

        with patch.object(repair_loop.verifier, 'verify_tool_call') as mock_verify:
            mock_verify.return_value = VerificationResult(
                is_valid=False,
                error_type="missing_resource",
                error_message="Resource not found"
            )
            result, suggestion = repair_loop.analyze(tool_call)
            assert suggestion.should_retry is True
            assert suggestion.error_type == "missing_resource"

    def test_analyze_with_permission_denied(self):
        """Test repair suggestion for permission denied."""
        repair_loop = RepairLoop()
        tool_call = ToolCallRecord(
            tool_name="write_file",
            arguments_preview={"path": "/protected/file.txt"},
            success=False,
            error_message="Permission denied"
        )

        with patch.object(repair_loop.verifier, 'verify_tool_call') as mock_verify:
            mock_verify.return_value = VerificationResult(
                is_valid=False,
                error_type="permission_denied",
                error_message="Permission denied"
            )
            result, suggestion = repair_loop.analyze(tool_call)
            assert suggestion.should_retry is False
            assert suggestion.error_type == "permission_denied"
            assert suggestion.confidence < 0.5

    def test_analyze_with_timeout(self):
        """Test repair suggestion for timeout errors."""
        repair_loop = RepairLoop()
        tool_call = ToolCallRecord(
            tool_name="long_running_tool",
            arguments_preview={"timeout": 1},
            success=False,
            error_message="Operation timed out"
        )

        with patch.object(repair_loop.verifier, 'verify_tool_call') as mock_verify:
            mock_verify.return_value = VerificationResult(
                is_valid=False,
                error_type="timeout",
                error_message="Timeout"
            )
            result, suggestion = repair_loop.analyze(tool_call)
            assert suggestion.should_retry is True
            assert suggestion.error_type == "timeout"
            assert suggestion.confidence < 0.8

    def test_analyze_with_rate_limit(self):
        """Test repair suggestion for rate limit errors."""
        repair_loop = RepairLoop()
        tool_call = ToolCallRecord(
            tool_name="api_call",
            arguments_preview={"endpoint": "/api/test"},
            success=False,
            error_message="Rate limit exceeded"
        )

        with patch.object(repair_loop.verifier, 'verify_tool_call') as mock_verify:
            mock_verify.return_value = VerificationResult(
                is_valid=False,
                error_type="rate_limit",
                error_message="Rate limit"
            )
            result, suggestion = repair_loop.analyze(tool_call)
            assert suggestion.should_retry is True
            assert suggestion.error_type == "rate_limit"

    def test_summarize_with_mixed_results(self):
        """Test summarize with mix of successful and failed tool calls."""
        repair_loop = RepairLoop()
        tool_calls = [
            ToolCallRecord(
                tool_name="tool1",
                arguments_preview={"arg": "val1"},
                success=True,
                error_message=None
            ),
            ToolCallRecord(
                tool_name="tool2",
                arguments_preview={"arg": "val2"},
                success=False,
                error_message="Failed"
            ),
            ToolCallRecord(
                tool_name="tool3",
                arguments_preview={"arg": "val3"},
                success=False,
                error_message="Failed"
            ),
        ]

        with patch.object(repair_loop.verifier, 'summarize_run') as mock_summarize:
            mock_summarize.return_value = {"total_calls": 3}
            with patch.object(repair_loop, 'analyze') as mock_analyze:
                mock_analyze.side_effect = [
                    (VerificationResult(is_valid=False, error_type="validation_error"),
                     RepairSuggestion(should_retry=True, error_type="validation_error")),
                    (VerificationResult(is_valid=False, error_type="timeout"),
                     RepairSuggestion(should_retry=True, error_type="timeout")),
                ]
                summary = repair_loop.summarize(tool_calls)
                assert summary["total_calls"] == 3
                assert summary["retryable_failures"] == 2
                assert len(summary["repairs"]) == 2

    def test_dump_model_with_pydantic_model(self):
        """Test _dump_model with Pydantic model."""
        model = MemoryScope()
        dumped = RepairLoop._dump_model(model)
        assert isinstance(dumped, dict)
        assert "owner_agent_id" in dumped

    def test_dump_model_with_dict(self):
        """Test _dump_model with dict."""
        data = {"key": "value"}
        dumped = RepairLoop._dump_model(data)
        assert dumped == data

    def test_dump_model_with_object(self):
        """Test _dump_model with generic object."""
        class CustomObject:
            def __init__(self):
                self.attr = "value"

        obj = CustomObject()
        dumped = RepairLoop._dump_model(obj)
        assert isinstance(dumped, dict)
        assert dumped.get("attr") == "value"


class TestMemoryItemBoundaryConditions:
    """Test MemoryItem with boundary conditions."""

    def test_memory_item_with_max_importance(self):
        """Test MemoryItem with maximum importance."""
        item = MemoryItem(
            tenant_id="tenant1",
            content="Important memory",
            layer=10,
            importance=1.0
        )
        assert item.importance == 1.0
        assert item.layer == 10

    def test_memory_item_with_min_importance(self):
        """Test MemoryItem with minimum importance."""
        item = MemoryItem(
            tenant_id="tenant1",
            content="Unimportant memory",
            layer=1,
            importance=0.0
        )
        assert item.importance == 0.0
        assert item.layer == 1

    def test_memory_item_with_invalid_importance(self):
        """Test MemoryItem with invalid importance values."""
        with pytest.raises(ValueError):
            MemoryItem(
                tenant_id="tenant1",
                content="Memory",
                layer=5,
                importance=1.5  # Out of range
            )

    def test_memory_item_with_invalid_layer(self):
        """Test MemoryItem with invalid layer values."""
        with pytest.raises(ValueError):
            MemoryItem(
                tenant_id="tenant1",
                content="Memory",
                layer=11,  # Out of range
                importance=0.5
            )

    def test_memory_item_with_empty_content(self):
        """Test MemoryItem with empty content."""
        item = MemoryItem(
            tenant_id="tenant1",
            content="",
            layer=5,
            importance=0.5
        )
        assert item.content == ""

    def test_memory_item_with_very_long_content(self):
        """Test MemoryItem with very long content."""
        long_content = "x" * 100000
        item = MemoryItem(
            tenant_id="tenant1",
            content=long_content,
            layer=5,
            importance=0.5
        )
        assert len(item.content) == 100000

    def test_memory_item_with_many_tags(self):
        """Test MemoryItem with many tags."""
        tags = [f"tag_{i}" for i in range(1000)]
        item = MemoryItem(
            tenant_id="tenant1",
            content="Memory with many tags",
            layer=5,
            importance=0.5,
            tags=tags
        )
        assert len(item.tags) == 1000

    def test_memory_item_with_large_metadata(self):
        """Test MemoryItem with large metadata."""
        metadata = {f"key_{i}": f"value_{i}" for i in range(1000)}
        item = MemoryItem(
            tenant_id="tenant1",
            content="Memory with large metadata",
            layer=5,
            importance=0.5,
            metadata=metadata
        )
        assert len(item.metadata) == 1000

    def test_memory_revision_creation(self):
        """Test MemoryRevision creation."""
        revision = MemoryRevision(memory_id="mem1")
        assert revision.memory_id == "mem1"
        assert revision.revision_id is not None
        assert revision.created_at is not None

    def test_memory_scope_defaults(self):
        """Test MemoryScope default values."""
        scope = MemoryScope()
        assert scope.owner_agent_id is None
        assert scope.share_scope == "private"
        assert scope.visibility == "private"
        assert scope.shared_with == []


class TestAgentRuntimeAdapterEdgeCases:
    """Test AgentRuntimeAdapter with edge cases."""

    def test_build_recovery_view_with_none_recovery_frame(self):
        """Test build_recovery_view when recovery_frame is None."""
        adapter = AgentRuntimeAdapter(Mock())
        state = Mock(spec=AgentRunState)
        state.recovery_frame = None

        result = adapter.build_recovery_view(state)
        assert result == {}

    def test_build_recovery_view_with_pydantic_model(self):
        """Test build_recovery_view with Pydantic model."""
        adapter = AgentRuntimeAdapter(Mock())
        state = Mock(spec=AgentRunState)
        state.recovery_frame = MemoryScope()

        result = adapter.build_recovery_view(state)
        assert isinstance(result, dict)
        assert "owner_agent_id" in result

    def test_build_snapshot_with_missing_frames(self):
        """Test build_snapshot when frames are missing."""
        adapter = AgentRuntimeAdapter(Mock())
        state = Mock(spec=AgentRunState)
        state.task_frame = None
        state.execution_frame = None
        state.plan_frame = None

        result = adapter.build_snapshot(state)
        assert result["task"] == {}
        assert result["execution_frame"] == {}
        assert result["plan"] == {}

    def test_build_summary_with_missing_execution_frame(self):
        """Test build_summary when execution_frame is missing."""
        adapter = AgentRuntimeAdapter(Mock())
        state = Mock(spec=AgentRunState)
        state.context = Mock(trace_id="trace1", agent_id="agent1")
        state.metadata = {"key": "value"}
        state.execution_frame = None

        result = adapter.build_summary(state)
        assert result["trace_id"] == "trace1"
        assert result["agent_id"] == "agent1"
        assert result["metadata"] == {"key": "value"}
        assert result["execution_summary"] == {}

    def test_build_run_view_complete(self):
        """Test build_run_view with complete state."""
        adapter = AgentRuntimeAdapter(Mock())
        state = Mock(spec=AgentRunState)
        state.context = Mock(trace_id="trace1", agent_id="agent1")
        state.metadata = {"key": "value"}
        state.recovery_frame = None
        state.task_frame = None
        state.execution_frame = None
        state.plan_frame = None

        result = adapter.build_run_view(state, status="completed", answer="test answer")
        assert isinstance(result, RunView)
        assert result.trace_id == "trace1"
        assert result.status == "completed"
        assert result.answer == "test answer"


class TestConcurrentOperations:
    """Test concurrent operations and thread safety."""

    @pytest.mark.asyncio
    async def test_concurrent_memory_item_creation(self):
        """Test concurrent creation of MemoryItem instances."""
        async def create_item(i):
            return MemoryItem(
                tenant_id=f"tenant_{i}",
                content=f"Memory {i}",
                layer=5,
                importance=0.5
            )

        tasks = [create_item(i) for i in range(100)]
        items = await asyncio.gather(*tasks)
        assert len(items) == 100
        assert all(isinstance(item, MemoryItem) for item in items)

    @pytest.mark.asyncio
    async def test_concurrent_repair_loop_analysis(self):
        """Test concurrent repair loop analysis."""
        repair_loop = RepairLoop()

        async def analyze_call(i):
            tool_call = ToolCallRecord(
                tool_name=f"tool_{i}",
                arguments_preview={"arg": f"val_{i}"},
                success=False,
                error_message="Failed"
            )
            with patch.object(repair_loop.verifier, 'verify_tool_call') as mock_verify:
                mock_verify.return_value = VerificationResult(
                    is_valid=False,
                    error_type="validation_error",
                    error_message="Invalid"
                )
                return repair_loop.analyze(tool_call)

        tasks = [analyze_call(i) for i in range(50)]
        results = await asyncio.gather(*tasks)
        assert len(results) == 50
        assert all(len(r) == 2 for r in results)

    def test_execution_planner_thread_safety(self):
        """Test ExecutionPlanner thread safety."""
        import threading

        planner = ExecutionPlanner()
        results = []

        def build_plan(task_id):
            plan = planner.build(f"Task {task_id}")
            results.append(plan)

        threads = [threading.Thread(target=build_plan, args=(i,)) for i in range(50)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(results) == 50
        assert all(isinstance(plan, ExecutionPlan) for plan in results)


class TestErrorRecoveryScenarios:
    """Test error recovery scenarios."""

    def test_repair_loop_with_unknown_error_type(self):
        """Test repair suggestion for unknown error types."""
        repair_loop = RepairLoop()
        tool_call = ToolCallRecord(
            tool_name="unknown_tool",
            arguments_preview={"arg": "value"},
            success=False,
            error_message="Unknown error"
        )

        with patch.object(repair_loop.verifier, 'verify_tool_call') as mock_verify:
            mock_verify.return_value = VerificationResult(
                is_valid=False,
                error_type="unknown_error_type",
                error_message="Unknown"
            )
            result, suggestion = repair_loop.analyze(tool_call)
            assert suggestion.should_retry is True
            assert suggestion.error_type == "unknown_error_type"
            assert suggestion.confidence < 0.7

    def test_execution_planner_with_none_test_mapping(self):
        """Test ExecutionPlanner with None test mapping."""
        planner = ExecutionPlanner()
        plan = planner.build("Test task", test_mapping=None)
        assert plan.metadata["test_mapping"] is None
        assert plan.metadata["related_file_count"] == 0
        assert plan.metadata["dependency_hint_count"] == 0

    def test_memory_item_revision_tracking(self):
        """Test MemoryItem revision tracking."""
        item = MemoryItem(
            tenant_id="tenant1",
            content="Original content",
            layer=5,
            importance=0.5
        )

        revision1 = MemoryRevision(memory_id=item.id, summary="First revision")
        revision2 = MemoryRevision(memory_id=item.id, summary="Second revision")

        item.revisions.append(revision1)
        item.revisions.append(revision2)

        assert len(item.revisions) == 2
        assert item.revisions[0].summary == "First revision"
        assert item.revisions[1].summary == "Second revision"
