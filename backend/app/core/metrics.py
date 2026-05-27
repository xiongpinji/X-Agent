"""Prometheus metrics collection for X-Agent."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Generator

try:
    from prometheus_client import Counter, Gauge, Histogram, Summary
except ImportError:
    Counter = Gauge = Histogram = Summary = None  # type: ignore


class MetricsCollector:
    """Centralized metrics collection using Prometheus."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled and Counter is not None
        self._init_metrics()

    def _init_metrics(self) -> None:
        """Initialize all Prometheus metrics."""
        if not self.enabled:
            return

        # HTTP Request Metrics
        self.http_requests_total = Counter(
            "xagent_http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"],
        )
        self.http_request_duration_seconds = Histogram(
            "xagent_http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"],
            buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
        )

        # Error Metrics
        self.errors_total = Counter(
            "xagent_errors_total",
            "Total errors",
            ["error_type", "endpoint"],
        )
        self.error_rate = Gauge(
            "xagent_error_rate",
            "Current error rate",
            ["error_type"],
        )

        # Agent Execution Metrics
        self.agent_executions_total = Counter(
            "xagent_agent_executions_total",
            "Total agent executions",
            ["agent_id", "status"],
        )
        self.agent_execution_duration_seconds = Histogram(
            "xagent_agent_execution_duration_seconds",
            "Agent execution duration in seconds",
            ["agent_id"],
            buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0),
        )
        self.agent_active_executions = Gauge(
            "xagent_agent_active_executions",
            "Number of active agent executions",
            ["agent_id"],
        )

        # Tool Execution Metrics
        self.tool_calls_total = Counter(
            "xagent_tool_calls_total",
            "Total tool calls",
            ["tool_name", "status"],
        )
        self.tool_call_duration_seconds = Histogram(
            "xagent_tool_call_duration_seconds",
            "Tool call duration in seconds",
            ["tool_name"],
            buckets=(0.01, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0),
        )

        # LLM Metrics
        self.llm_calls_total = Counter(
            "xagent_llm_calls_total",
            "Total LLM calls",
            ["model", "status"],
        )
        self.llm_tokens_total = Counter(
            "xagent_llm_tokens_total",
            "Total LLM tokens used",
            ["model", "token_type"],
        )
        self.llm_call_duration_seconds = Histogram(
            "xagent_llm_call_duration_seconds",
            "LLM call duration in seconds",
            ["model"],
            buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0),
        )

        # Memory Metrics
        self.memory_operations_total = Counter(
            "xagent_memory_operations_total",
            "Total memory operations",
            ["operation", "status"],
        )
        self.memory_size_bytes = Gauge(
            "xagent_memory_size_bytes",
            "Memory size in bytes",
            ["memory_type"],
        )
        self.memory_retrieval_duration_seconds = Histogram(
            "xagent_memory_retrieval_duration_seconds",
            "Memory retrieval duration in seconds",
            ["memory_type"],
            buckets=(0.001, 0.01, 0.05, 0.1, 0.5, 1.0),
        )

        # Workflow Metrics
        self.workflow_executions_total = Counter(
            "xagent_workflow_executions_total",
            "Total workflow executions",
            ["workflow_id", "status"],
        )
        self.workflow_execution_duration_seconds = Histogram(
            "xagent_workflow_execution_duration_seconds",
            "Workflow execution duration in seconds",
            ["workflow_id"],
            buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0),
        )

        # Database Metrics
        self.db_queries_total = Counter(
            "xagent_db_queries_total",
            "Total database queries",
            ["query_type", "status"],
        )
        self.db_query_duration_seconds = Histogram(
            "xagent_db_query_duration_seconds",
            "Database query duration in seconds",
            ["query_type"],
            buckets=(0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
        )
        self.db_connection_pool_size = Gauge(
            "xagent_db_connection_pool_size",
            "Database connection pool size",
        )
        self.db_active_connections = Gauge(
            "xagent_db_active_connections",
            "Number of active database connections",
        )

        # Cache Metrics
        self.cache_hits_total = Counter(
            "xagent_cache_hits_total",
            "Total cache hits",
            ["cache_name"],
        )
        self.cache_misses_total = Counter(
            "xagent_cache_misses_total",
            "Total cache misses",
            ["cache_name"],
        )
        self.cache_size_bytes = Gauge(
            "xagent_cache_size_bytes",
            "Cache size in bytes",
            ["cache_name"],
        )

        # Business Metrics
        self.approvals_pending = Gauge(
            "xagent_approvals_pending",
            "Number of pending approvals",
        )
        self.runs_total = Gauge(
            "xagent_runs_total",
            "Total number of runs",
        )
        self.traces_total = Gauge(
            "xagent_traces_total",
            "Total number of traces",
        )
        self.memories_total = Gauge(
            "xagent_memories_total",
            "Total number of memories",
        )

        # Resource Metrics
        self.cpu_usage_percent = Gauge(
            "xagent_cpu_usage_percent",
            "CPU usage percentage",
        )
        self.memory_usage_bytes = Gauge(
            "xagent_memory_usage_bytes",
            "Memory usage in bytes",
        )
        self.disk_usage_bytes = Gauge(
            "xagent_disk_usage_bytes",
            "Disk usage in bytes",
            ["mount_point"],
        )

        # Langfuse Metrics
        self.langfuse_events_total = Counter(
            "xagent_langfuse_events_total",
            "Total Langfuse events sent",
            ["event_type"],
        )
        self.langfuse_api_calls_total = Counter(
            "xagent_langfuse_api_calls_total",
            "Total Langfuse API calls",
            ["endpoint", "status"],
        )

    def record_http_request(
        self,
        method: str,
        endpoint: str,
        status: int,
        duration_seconds: float,
    ) -> None:
        """Record HTTP request metrics."""
        if not self.enabled:
            return
        self.http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
        self.http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(
            duration_seconds
        )

    def record_error(self, error_type: str, endpoint: str = "unknown") -> None:
        """Record error metrics."""
        if not self.enabled:
            return
        self.errors_total.labels(error_type=error_type, endpoint=endpoint).inc()

    def record_agent_execution(
        self,
        agent_id: str,
        status: str,
        duration_seconds: float,
    ) -> None:
        """Record agent execution metrics."""
        if not self.enabled:
            return
        self.agent_executions_total.labels(agent_id=agent_id, status=status).inc()
        self.agent_execution_duration_seconds.labels(agent_id=agent_id).observe(duration_seconds)

    def set_active_agent_executions(self, agent_id: str, count: int) -> None:
        """Set active agent executions count."""
        if not self.enabled:
            return
        self.agent_active_executions.labels(agent_id=agent_id).set(count)

    def record_tool_call(
        self,
        tool_name: str,
        status: str,
        duration_seconds: float,
    ) -> None:
        """Record tool call metrics."""
        if not self.enabled:
            return
        self.tool_calls_total.labels(tool_name=tool_name, status=status).inc()
        self.tool_call_duration_seconds.labels(tool_name=tool_name).observe(duration_seconds)

    def record_llm_call(
        self,
        model: str,
        status: str,
        duration_seconds: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        """Record LLM call metrics."""
        if not self.enabled:
            return
        self.llm_calls_total.labels(model=model, status=status).inc()
        self.llm_call_duration_seconds.labels(model=model).observe(duration_seconds)
        if input_tokens > 0:
            self.llm_tokens_total.labels(model=model, token_type="input").inc(input_tokens)
        if output_tokens > 0:
            self.llm_tokens_total.labels(model=model, token_type="output").inc(output_tokens)

    def record_memory_operation(
        self,
        operation: str,
        status: str,
        duration_seconds: float = 0,
    ) -> None:
        """Record memory operation metrics."""
        if not self.enabled:
            return
        self.memory_operations_total.labels(operation=operation, status=status).inc()
        if duration_seconds > 0:
            self.memory_retrieval_duration_seconds.labels(memory_type=operation).observe(
                duration_seconds
            )

    def set_memory_size(self, memory_type: str, size_bytes: int) -> None:
        """Set memory size metric."""
        if not self.enabled:
            return
        self.memory_size_bytes.labels(memory_type=memory_type).set(size_bytes)

    def record_workflow_execution(
        self,
        workflow_id: str,
        status: str,
        duration_seconds: float,
    ) -> None:
        """Record workflow execution metrics."""
        if not self.enabled:
            return
        self.workflow_executions_total.labels(workflow_id=workflow_id, status=status).inc()
        self.workflow_execution_duration_seconds.labels(workflow_id=workflow_id).observe(
            duration_seconds
        )

    def record_db_query(
        self,
        query_type: str,
        status: str,
        duration_seconds: float,
    ) -> None:
        """Record database query metrics."""
        if not self.enabled:
            return
        self.db_queries_total.labels(query_type=query_type, status=status).inc()
        self.db_query_duration_seconds.labels(query_type=query_type).observe(duration_seconds)

    def set_db_connection_pool_size(self, size: int) -> None:
        """Set database connection pool size."""
        if not self.enabled:
            return
        self.db_connection_pool_size.set(size)

    def set_db_active_connections(self, count: int) -> None:
        """Set active database connections count."""
        if not self.enabled:
            return
        self.db_active_connections.set(count)

    def record_cache_hit(self, cache_name: str) -> None:
        """Record cache hit."""
        if not self.enabled:
            return
        self.cache_hits_total.labels(cache_name=cache_name).inc()

    def record_cache_miss(self, cache_name: str) -> None:
        """Record cache miss."""
        if not self.enabled:
            return
        self.cache_misses_total.labels(cache_name=cache_name).inc()

    def set_cache_size(self, cache_name: str, size_bytes: int) -> None:
        """Set cache size."""
        if not self.enabled:
            return
        self.cache_size_bytes.labels(cache_name=cache_name).set(size_bytes)

    def set_approvals_pending(self, count: int) -> None:
        """Set pending approvals count."""
        if not self.enabled:
            return
        self.approvals_pending.set(count)

    def set_runs_total(self, count: int) -> None:
        """Set total runs count."""
        if not self.enabled:
            return
        self.runs_total.set(count)

    def set_traces_total(self, count: int) -> None:
        """Set total traces count."""
        if not self.enabled:
            return
        self.traces_total.set(count)

    def set_memories_total(self, count: int) -> None:
        """Set total memories count."""
        if not self.enabled:
            return
        self.memories_total.set(count)

    def set_resource_metrics(
        self,
        cpu_percent: float = 0,
        memory_bytes: int = 0,
        disk_bytes: dict[str, int] | None = None,
    ) -> None:
        """Set resource usage metrics."""
        if not self.enabled:
            return
        if cpu_percent > 0:
            self.cpu_usage_percent.set(cpu_percent)
        if memory_bytes > 0:
            self.memory_usage_bytes.set(memory_bytes)
        if disk_bytes:
            for mount_point, size in disk_bytes.items():
                self.disk_usage_bytes.labels(mount_point=mount_point).set(size)

    def record_langfuse_event(self, event_type: str) -> None:
        """Record Langfuse event."""
        if not self.enabled:
            return
        self.langfuse_events_total.labels(event_type=event_type).inc()

    def record_langfuse_api_call(self, endpoint: str, status: str) -> None:
        """Record Langfuse API call."""
        if not self.enabled:
            return
        self.langfuse_api_calls_total.labels(endpoint=endpoint, status=status).inc()

    @contextmanager
    def timer(self, metric_name: str, labels: dict[str, str] | None = None) -> Generator[None, None, None]:
        """Context manager for timing operations."""
        if not self.enabled:
            yield
            return

        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            # This is a helper for custom timing; specific metrics use their own methods


# Global metrics instance
metrics_collector = MetricsCollector(enabled=True)
