"""Tests for parallel tool execution functionality."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.app.core.parallel_tool_executor import (
    ParallelToolExecutor,
    ToolCall,
    ToolResult,
    BatchExecutionStats,
)
from backend.app.core.tool_dependency_analyzer import (
    ToolDependencyAnalyzer,
    ExecutionLayer,
)
from backend.app.core.tool_result_cache import ToolResultCache, CacheStats
from backend.app.core.tool_call_batcher import ToolCallBatcher, Batch
from backend.app.core.contracts import RunContext, RiskLevel


class TestParallelToolExecutor:
    """Tests for ParallelToolExecutor."""

    @pytest.fixture
    def mock_registry(self):
        """Create a mock tool registry."""
        registry = AsyncMock()
        registry.execute = AsyncMock()
        return registry

    @pytest.fixture
    def executor(self, mock_registry):
        """Create a ParallelToolExecutor instance."""
        return ParallelToolExecutor(
            tool_registry=mock_registry,
            max_concurrent=5,
            default_timeout=30.0,
        )

    @pytest.fixture
    def context(self):
        """Create a RunContext."""
        return RunContext(
            trace_id="test_trace",
            tenant_id="test_tenant",
            user_id="test_user",
        )

    @pytest.mark.asyncio
    async def test_execute_batch_simple(self, executor, mock_registry, context):
        """Test simple batch execution without dependencies."""
        # Setup mock responses
        from backend.app.core.contracts import ToolCallRecord, ToolPolicyVerdict

        mock_registry.execute.side_effect = [
            ToolCallRecord(
                tool_name="read_file",
                success=True,
                output="content1",
                policy=ToolPolicyVerdict(allowed=True, reason="ok"),
                risk_level=RiskLevel.LOW,
            ),
            ToolCallRecord(
                tool_name="read_file",
                success=True,
                output="content2",
                policy=ToolPolicyVerdict(allowed=True, reason="ok"),
                risk_level=RiskLevel.LOW,
            ),
        ]

        # Create tool calls
        calls = [
            ToolCall(tool_name="read_file", arguments={"path": "file1.txt"}),
            ToolCall(tool_name="read_file", arguments={"path": "file2.txt"}),
        ]

        # Execute
        results = await executor.execute_batch(calls, context)

        # Verify
        assert len(results) == 2
        assert all(r.success for r in results)
        assert results[0].output == "content1"
        assert results[1].output == "content2"

    @pytest.mark.asyncio
    async def test_execute_batch_with_failure(self, executor, mock_registry, context):
        """Test batch execution with partial failure."""
        from backend.app.core.contracts import ToolCallRecord, ToolPolicyVerdict

        mock_registry.execute.side_effect = [
            ToolCallRecord(
                tool_name="read_file",
                success=True,
                output="content1",
                policy=ToolPolicyVerdict(allowed=True, reason="ok"),
                risk_level=RiskLevel.LOW,
            ),
            ToolCallRecord(
                tool_name="read_file",
                success=False,
                error="File not found",
                policy=ToolPolicyVerdict(allowed=True, reason="ok"),
                risk_level=RiskLevel.LOW,
            ),
        ]

        calls = [
            ToolCall(tool_name="read_file", arguments={"path": "file1.txt"}),
            ToolCall(tool_name="read_file", arguments={"path": "missing.txt"}),
        ]

        results = await executor.execute_batch(calls, context, allow_partial_failure=True)

        assert len(results) == 2
        assert results[0].success
        assert not results[1].success
        assert results[1].error == "File not found"

    @pytest.mark.asyncio
    async def test_execute_with_dependencies(self, executor, mock_registry, context):
        """Test execution with dependencies."""
        from backend.app.core.contracts import ToolCallRecord, ToolPolicyVerdict

        mock_registry.execute.side_effect = [
            ToolCallRecord(
                tool_name="read_file",
                success=True,
                output={"config": "value"},
                policy=ToolPolicyVerdict(allowed=True, reason="ok"),
                risk_level=RiskLevel.LOW,
            ),
            ToolCallRecord(
                tool_name="process_data",
                success=True,
                output="processed",
                policy=ToolPolicyVerdict(allowed=True, reason="ok"),
                risk_level=RiskLevel.LOW,
            ),
        ]

        calls = [
            ToolCall(
                tool_name="read_file",
                arguments={"path": "config.json"},
                call_id="read_config",
            ),
            ToolCall(
                tool_name="process_data",
                arguments={"config": "${read_config.output}"},
                call_id="process",
            ),
        ]

        results = await executor.execute_with_dependencies(calls, context)

        assert len(results) == 2
        assert "read_config" in results
        assert "process" in results
        assert results["read_config"].success
        assert results["process"].success

    @pytest.mark.asyncio
    async def test_caching(self, executor, context):
        """Test result caching."""
        from backend.app.core.contracts import ToolCallRecord, ToolPolicyVerdict

        executor._registry.execute = AsyncMock(
            return_value=ToolCallRecord(
                tool_name="read_file",
                success=True,
                output="cached_content",
                policy=ToolPolicyVerdict(allowed=True, reason="ok"),
                risk_level=RiskLevel.LOW,
            )
        )

        call = ToolCall(tool_name="read_file", arguments={"path": "file.txt"})

        # First execution
        result1 = await executor._execute_single(call, context)
        assert result1.success
        assert not result1.cached

        # Second execution (should be cached)
        result2 = await executor._execute_single(call, context)
        assert result2.success
        assert result2.cached

        # Registry should only be called once
        assert executor._registry.execute.call_count == 1

    def test_stats_tracking(self, executor):
        """Test statistics tracking."""
        stats = executor.get_stats()
        assert isinstance(stats, BatchExecutionStats)
        assert stats.total_calls == 0
        assert stats.successful_calls == 0


class TestToolDependencyAnalyzer:
    """Tests for ToolDependencyAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        """Create a ToolDependencyAnalyzer instance."""
        return ToolDependencyAnalyzer()

    def test_analyze_dependencies_no_deps(self, analyzer):
        """Test analyzing independent calls."""
        calls = [
            ToolCall(tool_name="read_file", arguments={"path": "a.txt"}, call_id="a"),
            ToolCall(tool_name="read_file", arguments={"path": "b.txt"}, call_id="b"),
        ]

        graph = analyzer.analyze_dependencies(calls)

        assert len(graph.nodes) == 2
        assert len(graph.reverse_edges["a"]) == 0
        assert len(graph.reverse_edges["b"]) == 0

    def test_analyze_dependencies_with_deps(self, analyzer):
        """Test analyzing dependent calls."""
        calls = [
            ToolCall(tool_name="read_file", arguments={"path": "a.txt"}, call_id="a"),
            ToolCall(
                tool_name="process",
                arguments={"data": "${a.output}"},
                call_id="b",
            ),
        ]

        graph = analyzer.analyze_dependencies(calls)

        assert len(graph.nodes) == 2
        assert "a" in graph.reverse_edges["b"]
        assert "b" in graph.edges["a"]

    def test_build_execution_plan(self, analyzer):
        """Test building execution plan."""
        calls = [
            ToolCall(tool_name="read_file", arguments={"path": "a.txt"}, call_id="a"),
            ToolCall(tool_name="read_file", arguments={"path": "b.txt"}, call_id="b"),
            ToolCall(
                tool_name="process",
                arguments={"a": "${a.output}", "b": "${b.output}"},
                call_id="c",
            ),
        ]

        graph = analyzer.analyze_dependencies(calls)
        plan = analyzer.build_execution_plan(graph)

        assert len(plan.layers) == 2
        assert len(plan.layers[0].call_ids) == 2  # a and b
        assert len(plan.layers[1].call_ids) == 1  # c
        assert plan.max_parallelism == 2

    def test_detect_cycles(self, analyzer):
        """Test cycle detection."""
        # Create a mock graph with a cycle
        from backend.app.core.tool_dependency_analyzer import DependencyGraph

        graph = DependencyGraph()
        graph.nodes = {"a": None, "b": None, "c": None}
        graph.edges = {"a": {"b"}, "b": {"c"}, "c": {"a"}}
        graph.reverse_edges = {"a": {"c"}, "b": {"a"}, "c": {"b"}}

        cycles = analyzer.detect_cycles(graph)
        assert len(cycles) > 0

    def test_calculate_parallelism(self, analyzer):
        """Test parallelism calculation."""
        from backend.app.core.tool_dependency_analyzer import ExecutionPlan

        plan = ExecutionPlan(
            layers=[
                ExecutionLayer(layer_id=0, call_ids={"a", "b", "c"}),
                ExecutionLayer(layer_id=1, call_ids={"d"}),
            ],
            total_calls=4,
        )

        parallelism = analyzer.calculate_parallelism(plan)
        assert parallelism == 2.0  # 4 calls / 2 layers


class TestToolResultCache:
    """Tests for ToolResultCache."""

    @pytest.fixture
    def cache(self):
        """Create a ToolResultCache instance."""
        return ToolResultCache(max_size=100, default_ttl=300)

    @pytest.mark.asyncio
    async def test_cache_hit(self, cache):
        """Test cache hit."""
        await cache.set("read_file", {"path": "file.txt"}, "content")
        result = await cache.get("read_file", {"path": "file.txt"})
        assert result == "content"

    @pytest.mark.asyncio
    async def test_cache_miss(self, cache):
        """Test cache miss."""
        result = await cache.get("read_file", {"path": "missing.txt"})
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_expiration(self, cache):
        """Test cache expiration."""
        await cache.set("read_file", {"path": "file.txt"}, "content", ttl=0)
        await asyncio.sleep(0.1)
        result = await cache.get("read_file", {"path": "file.txt"})
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_invalidation(self, cache):
        """Test cache invalidation."""
        await cache.set("read_file", {"path": "file.txt"}, "content")
        await cache.invalidate("read_file", {"path": "file.txt"})
        result = await cache.get("read_file", {"path": "file.txt"})
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_stats(self, cache):
        """Test cache statistics."""
        await cache.set("read_file", {"path": "file.txt"}, "content")
        await cache.get("read_file", {"path": "file.txt"})  # Hit
        await cache.get("read_file", {"path": "missing.txt"})  # Miss

        stats = cache.get_stats()
        assert stats.total_requests == 2
        assert stats.cache_hits == 1
        assert stats.cache_misses == 1
        assert stats.hit_rate == 0.5


class TestToolCallBatcher:
    """Tests for ToolCallBatcher."""

    @pytest.fixture
    def batcher(self):
        """Create a ToolCallBatcher instance."""
        return ToolCallBatcher(max_batch_size=10)

    def test_batch_tool_calls(self, batcher):
        """Test batching tool calls."""
        calls = [
            ToolCall(tool_name="read_file", arguments={"path": "a.txt"}),
            ToolCall(tool_name="read_file", arguments={"path": "b.txt"}),
            ToolCall(tool_name="write_file", arguments={"path": "c.txt", "content": "data"}),
        ]

        batches = batcher.batch_tool_calls(calls)

        assert len(batches) == 2
        assert batches[0].tool_name == "read_file"
        assert len(batches[0].calls) == 2
        assert batches[1].tool_name == "write_file"
        assert len(batches[1].calls) == 1

    def test_optimize_batches(self, batcher):
        """Test batch optimization."""
        calls = [
            ToolCall(tool_name="read_file", arguments={"path": "a.txt"}),
            ToolCall(tool_name="read_file", arguments={"path": "a.txt"}),  # Duplicate
            ToolCall(tool_name="write_file", arguments={"path": "c.txt", "content": "data"}),
        ]

        batches = batcher.batch_tool_calls(calls)
        optimized = batcher.optimize_batches(batches)

        # Read operations should have higher priority
        assert optimized[0].tool_name == "read_file"
        assert optimized[1].tool_name == "write_file"

    def test_merge_similar_calls(self, batcher):
        """Test merging similar calls."""
        calls = [
            ToolCall(tool_name="read_file", arguments={"path": "a.txt"}),
            ToolCall(tool_name="read_file", arguments={"path": "a.txt"}),
            ToolCall(tool_name="read_file", arguments={"path": "b.txt"}),
        ]

        merged = batcher.merge_similar_calls(calls)

        assert len(merged) == 2  # Duplicate removed


class TestPerformance:
    """Performance tests."""

    @pytest.mark.asyncio
    async def test_parallel_speedup(self):
        """Test that parallel execution is faster than sequential."""
        from backend.app.core.contracts import ToolCallRecord, ToolPolicyVerdict

        # Create mock registry
        registry = AsyncMock()

        async def slow_execute(*args, **kwargs):
            await asyncio.sleep(0.1)
            return ToolCallRecord(
                tool_name="slow_tool",
                success=True,
                output="result",
                policy=ToolPolicyVerdict(allowed=True, reason="ok"),
                risk_level=RiskLevel.LOW,
            )

        registry.execute = slow_execute

        executor = ParallelToolExecutor(tool_registry=registry, max_concurrent=5)
        context = RunContext()

        # Create 3 independent calls
        calls = [
            ToolCall(tool_name="slow_tool", arguments={"id": i})
            for i in range(3)
        ]

        # Measure parallel execution
        import time

        start = time.time()
        results = await executor.execute_batch(calls, context)
        parallel_time = time.time() - start

        # Parallel should be much faster than 0.3s (3 * 0.1s)
        assert parallel_time < 0.25
        assert len(results) == 3
        assert all(r.success for r in results)
