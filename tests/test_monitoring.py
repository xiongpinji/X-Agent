"""Tests for X-Agent monitoring and health check systems."""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from backend.app.core.metrics import MetricsCollector, metrics_collector
from backend.app.api.health import (
    HealthStatus,
    HealthCheckResult,
    check_database,
    check_memory_store,
    check_audit_store,
    check_approval_store,
)


class TestMetricsCollector:
    """Test MetricsCollector functionality."""

    def test_metrics_collector_initialization(self):
        """Test metrics collector initialization."""
        collector = MetricsCollector(enabled=True)
        assert collector.enabled is True
        assert collector.http_requests_total is not None

    def test_metrics_collector_disabled(self):
        """Test metrics collector when disabled."""
        collector = MetricsCollector(enabled=False)
        assert collector.enabled is False

    def test_record_http_request(self):
        """Test recording HTTP request metrics."""
        collector = MetricsCollector(enabled=True)
        collector.record_http_request("GET", "/api/test", 200, 0.5)
        # Metrics recorded successfully

    def test_record_error(self):
        """Test recording error metrics."""
        collector = MetricsCollector(enabled=True)
        collector.record_error("ValueError", "/api/test")
        # Error recorded successfully

    def test_record_agent_execution(self):
        """Test recording agent execution metrics."""
        collector = MetricsCollector(enabled=True)
        collector.record_agent_execution("agent-1", "success", 1.5)
        # Agent execution recorded successfully

    def test_set_active_agent_executions(self):
        """Test setting active agent executions."""
        collector = MetricsCollector(enabled=True)
        collector.set_active_agent_executions("agent-1", 5)
        # Active executions set successfully

    def test_record_tool_call(self):
        """Test recording tool call metrics."""
        collector = MetricsCollector(enabled=True)
        collector.record_tool_call("browser_tool", "success", 2.0)
        # Tool call recorded successfully

    def test_record_llm_call(self):
        """Test recording LLM call metrics."""
        collector = MetricsCollector(enabled=True)
        collector.record_llm_call("gpt-4", "success", 1.0, 100, 50)
        # LLM call recorded successfully

    def test_record_memory_operation(self):
        """Test recording memory operation metrics."""
        collector = MetricsCollector(enabled=True)
        collector.record_memory_operation("retrieval", "success", 0.1)
        # Memory operation recorded successfully

    def test_set_memory_size(self):
        """Test setting memory size metric."""
        collector = MetricsCollector(enabled=True)
        collector.set_memory_size("vector_store", 1024000)
        # Memory size set successfully

    def test_record_workflow_execution(self):
        """Test recording workflow execution metrics."""
        collector = MetricsCollector(enabled=True)
        collector.record_workflow_execution("workflow-1", "success", 5.0)
        # Workflow execution recorded successfully

    def test_record_db_query(self):
        """Test recording database query metrics."""
        collector = MetricsCollector(enabled=True)
        collector.record_db_query("select", "success", 0.05)
        # Database query recorded successfully

    def test_set_db_connection_pool_size(self):
        """Test setting database connection pool size."""
        collector = MetricsCollector(enabled=True)
        collector.set_db_connection_pool_size(20)
        # Connection pool size set successfully

    def test_set_db_active_connections(self):
        """Test setting active database connections."""
        collector = MetricsCollector(enabled=True)
        collector.set_db_active_connections(15)
        # Active connections set successfully

    def test_record_cache_hit(self):
        """Test recording cache hit."""
        collector = MetricsCollector(enabled=True)
        collector.record_cache_hit("redis")
        # Cache hit recorded successfully

    def test_record_cache_miss(self):
        """Test recording cache miss."""
        collector = MetricsCollector(enabled=True)
        collector.record_cache_miss("redis")
        # Cache miss recorded successfully

    def test_set_cache_size(self):
        """Test setting cache size."""
        collector = MetricsCollector(enabled=True)
        collector.set_cache_size("redis", 5000000)
        # Cache size set successfully

    def test_set_approvals_pending(self):
        """Test setting pending approvals count."""
        collector = MetricsCollector(enabled=True)
        collector.set_approvals_pending(10)
        # Pending approvals set successfully

    def test_set_runs_total(self):
        """Test setting total runs count."""
        collector = MetricsCollector(enabled=True)
        collector.set_runs_total(100)
        # Total runs set successfully

    def test_set_traces_total(self):
        """Test setting total traces count."""
        collector = MetricsCollector(enabled=True)
        collector.set_traces_total(500)
        # Total traces set successfully

    def test_set_memories_total(self):
        """Test setting total memories count."""
        collector = MetricsCollector(enabled=True)
        collector.set_memories_total(1000)
        # Total memories set successfully

    def test_set_resource_metrics(self):
        """Test setting resource metrics."""
        collector = MetricsCollector(enabled=True)
        collector.set_resource_metrics(
            cpu_percent=45.5,
            memory_bytes=2147483648,
            disk_bytes={"/": 10737418240},
        )
        # Resource metrics set successfully

    def test_record_langfuse_event(self):
        """Test recording Langfuse event."""
        collector = MetricsCollector(enabled=True)
        collector.record_langfuse_event("agent_execution")
        # Langfuse event recorded successfully

    def test_record_langfuse_api_call(self):
        """Test recording Langfuse API call."""
        collector = MetricsCollector(enabled=True)
        collector.record_langfuse_api_call("/traces", "success")
        # Langfuse API call recorded successfully


class TestHealthCheckResult:
    """Test HealthCheckResult class."""

    def test_health_check_result_creation(self):
        """Test creating a health check result."""
        result = HealthCheckResult("database", HealthStatus.HEALTHY, "Database OK", 10.5)
        assert result.name == "database"
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "Database OK"
        assert result.latency_ms == 10.5

    def test_health_check_result_to_dict(self):
        """Test converting health check result to dict."""
        result = HealthCheckResult("database", HealthStatus.HEALTHY, "Database OK", 10.5)
        result_dict = result.to_dict()
        assert result_dict["name"] == "database"
        assert result_dict["status"] == HealthStatus.HEALTHY
        assert result_dict["message"] == "Database OK"
        assert result_dict["latency_ms"] == 10.5


class TestHealthChecks:
    """Test health check functions."""

    @pytest.mark.asyncio
    async def test_check_database_success(self):
        """Test successful database health check."""
        with patch("backend.app.api.health.get_trace_store") as mock_store:
            mock_store.return_value.list_trace_ids.return_value = ["trace-1", "trace-2"]
            result = await check_database()
            assert result.status == HealthStatus.HEALTHY
            assert "Database accessible" in result.message

    @pytest.mark.asyncio
    async def test_check_database_failure(self):
        """Test failed database health check."""
        with patch("backend.app.api.health.get_trace_store") as mock_store:
            mock_store.side_effect = Exception("Connection failed")
            result = await check_database()
            assert result.status == HealthStatus.UNHEALTHY
            assert "Connection failed" in result.message

    @pytest.mark.asyncio
    async def test_check_memory_store_success(self):
        """Test successful memory store health check."""
        with patch("backend.app.api.health.get_memory") as mock_memory:
            mock_memory.return_value.count.return_value = 100
            result = await check_memory_store()
            assert result.status == HealthStatus.HEALTHY
            assert "Memory store accessible" in result.message

    @pytest.mark.asyncio
    async def test_check_memory_store_failure(self):
        """Test failed memory store health check."""
        with patch("backend.app.api.health.get_memory") as mock_memory:
            mock_memory.side_effect = Exception("Connection failed")
            result = await check_memory_store()
            assert result.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_check_audit_store_success(self):
        """Test successful audit store health check."""
        with patch("backend.app.api.health.get_audit_store") as mock_store:
            mock_store.return_value.count.return_value = 50
            result = await check_audit_store()
            assert result.status == HealthStatus.HEALTHY
            assert "Audit store accessible" in result.message

    @pytest.mark.asyncio
    async def test_check_approval_store_success(self):
        """Test successful approval store health check."""
        with patch("backend.app.api.health.get_approval_store") as mock_store:
            mock_store.return_value.pending_count.return_value = 5
            result = await check_approval_store()
            assert result.status == HealthStatus.HEALTHY
            assert "Approval store accessible" in result.message


class TestMetricsIntegration:
    """Test metrics integration."""

    def test_global_metrics_instance(self):
        """Test global metrics instance."""
        assert metrics_collector is not None
        assert isinstance(metrics_collector, MetricsCollector)

    def test_metrics_disabled_gracefully(self):
        """Test that metrics handle disabled state gracefully."""
        collector = MetricsCollector(enabled=False)
        # Should not raise any exceptions
        collector.record_http_request("GET", "/test", 200, 0.5)
        collector.record_error("TestError", "/test")
        collector.record_agent_execution("agent-1", "success", 1.0)


class TestMetricsPerformance:
    """Test metrics performance."""

    def test_metrics_recording_performance(self):
        """Test that metrics recording is fast."""
        import time

        collector = MetricsCollector(enabled=True)
        start = time.perf_counter()

        for i in range(1000):
            collector.record_http_request("GET", f"/api/test/{i}", 200, 0.1)

        duration = time.perf_counter() - start
        # Should complete 1000 recordings in less than 1 second
        assert duration < 1.0

    def test_metrics_timer_context_manager(self):
        """Test metrics timer context manager."""
        import time

        collector = MetricsCollector(enabled=True)

        with collector.timer("test_operation"):
            time.sleep(0.01)

        # Timer should work without errors


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
