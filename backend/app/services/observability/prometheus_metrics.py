"""Prometheus metrics integration for X-Agent.

NOTE: This module is legacy. Canonical metrics now live in
backend.app.monitoring.metrics. All registrations here are wrapped in
try/except to avoid "Duplicated timeseries" crashes when both modules
are imported in the same process (e.g. during tests).
"""

from prometheus_client import Counter, Gauge, Histogram, generate_latest


def _safe_counter(name, doc, labelnames=None, **kw):
    try:
        if labelnames:
            return Counter(name, doc, labelnames, **kw)
        return Counter(name, doc, **kw)
    except ValueError:
        return None


def _safe_histogram(name, doc, labelnames=None, **kw):
    try:
        if labelnames:
            return Histogram(name, doc, labelnames, **kw)
        return Histogram(name, doc, **kw)
    except ValueError:
        return None


def _safe_gauge(name, doc, labelnames=None, **kw):
    try:
        if labelnames:
            return Gauge(name, doc, labelnames, **kw)
        return Gauge(name, doc, **kw)
    except ValueError:
        return None


# API metrics
api_requests_total = _safe_counter(
    "xagent_api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status"],
)

api_request_duration_seconds = _safe_histogram(
    "xagent_api_request_duration_seconds",
    "API request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
)

api_request_size_bytes = _safe_histogram(
    "xagent_api_request_size_bytes",
    "API request size in bytes",
    ["method", "endpoint"],
)

api_response_size_bytes = _safe_histogram(
    "xagent_api_response_size_bytes",
    "API response size in bytes",
    ["method", "endpoint"],
)

# Agent metrics
agent_runs_total = _safe_counter(
    "xagent_agent_runs_total",
    "Total agent runs",
    ["status"],
)

agent_run_duration_seconds = _safe_histogram(
    "xagent_agent_run_duration_seconds",
    "Agent run duration in seconds",
    buckets=(1, 5, 10, 30, 60, 300, 600),
)

agent_tasks_completed = _safe_counter(
    "xagent_agent_tasks_completed",
    "Total tasks completed by agents",
)

agent_errors_total = _safe_counter(
    "xagent_agent_errors_total",
    "Total agent errors",
    ["error_type"],
)

# Workflow metrics
workflow_runs_total = _safe_counter(
    "xagent_workflow_runs_total",
    "Total workflow runs",
    ["status"],
)

workflow_run_duration_seconds = _safe_histogram(
    "xagent_workflow_run_duration_seconds",
    "Workflow run duration in seconds",
    buckets=(1, 5, 10, 30, 60, 300, 600),
)

# Memory metrics
memory_operations_total = _safe_counter(
    "xagent_memory_operations_total",
    "Total memory operations",
    ["operation"],
)

memory_search_duration_seconds = _safe_histogram(
    "xagent_memory_search_duration_seconds",
    "Memory search duration in seconds",
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0),
)

memory_size_bytes = _safe_gauge(
    "xagent_memory_size_bytes",
    "Total memory size in bytes",
)

# Database metrics
db_query_duration_seconds = _safe_histogram(
    "xagent_db_query_duration_seconds",
    "Database query duration in seconds",
    ["query_type"],
    buckets=(0.001, 0.01, 0.05, 0.1, 0.5, 1.0),
)

db_connections_active = _safe_gauge(
    "xagent_db_connections_active",
    "Active database connections",
)

db_connection_pool_size = _safe_gauge(
    "xagent_db_connection_pool_size",
    "Database connection pool size",
)

# Cache metrics
cache_hits_total = _safe_counter(
    "xagent_cache_hits_total",
    "Total cache hits",
    ["cache_type"],
)

cache_misses_total = _safe_counter(
    "xagent_cache_misses_total",
    "Total cache misses",
    ["cache_type"],
)

cache_size_bytes = _safe_gauge(
    "xagent_cache_size_bytes",
    "Cache size in bytes",
    ["cache_type"],
)

# Tool execution metrics
tool_executions_total = _safe_counter(
    "xagent_tool_executions_total",
    "Total tool executions",
    ["tool_name", "status"],
)

tool_execution_duration_seconds = _safe_histogram(
    "xagent_tool_execution_duration_seconds",
    "Tool execution duration in seconds",
    ["tool_name"],
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0),
)

# System metrics
system_memory_usage_bytes = _safe_gauge(
    "xagent_system_memory_usage_bytes",
    "System memory usage in bytes",
)

system_cpu_usage_percent = _safe_gauge(
    "xagent_system_cpu_usage_percent",
    "System CPU usage percentage",
)

# Error metrics
errors_total = _safe_counter(
    "xagent_errors_total",
    "Total errors",
    ["error_type", "severity"],
)

# Audit metrics
audit_events_total = _safe_counter(
    "xagent_audit_events_total",
    "Total audit events",
    ["event_type"],
)

# Health check metrics
health_check_status = _safe_gauge(
    "xagent_health_check_status",
    "Health check status (1=healthy, 0=unhealthy)",
    ["component"],
)


def get_metrics() -> bytes:
    """Get all metrics in Prometheus format."""
    return generate_latest()
