"""Monitoring configuration for Agent V2 deployment.

This module defines monitoring metrics, alerts, and dashboards for
tracking Agent V2 deployment health and performance.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MetricType(StrEnum):
    """Metric types."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class AlertSeverity(StrEnum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class MetricDefinition:
    """Definition of a metric."""

    name: str
    type: MetricType
    description: str
    unit: str = ""
    labels: list[str] | None = None


@dataclass
class AlertRule:
    """Definition of an alert rule."""

    name: str
    condition: str
    severity: AlertSeverity
    duration: str = "5m"
    description: str = ""
    runbook_url: str = ""


class MonitoringConfig:
    """Monitoring configuration for Agent V2."""

    # Execution metrics
    EXECUTION_METRICS = [
        MetricDefinition(
            name="agent_v1_executions_total",
            type=MetricType.COUNTER,
            description="Total number of Agent V1 executions",
            labels=["tenant_id", "user_id", "status"],
        ),
        MetricDefinition(
            name="agent_v2_executions_total",
            type=MetricType.COUNTER,
            description="Total number of Agent V2 executions",
            labels=["tenant_id", "user_id", "status"],
        ),
        MetricDefinition(
            name="agent_v1_errors_total",
            type=MetricType.COUNTER,
            description="Total number of Agent V1 errors",
            labels=["tenant_id", "error_type"],
        ),
        MetricDefinition(
            name="agent_v2_errors_total",
            type=MetricType.COUNTER,
            description="Total number of Agent V2 errors",
            labels=["tenant_id", "error_type"],
        ),
        MetricDefinition(
            name="agent_execution_duration_seconds",
            type=MetricType.HISTOGRAM,
            description="Agent execution duration",
            unit="seconds",
            labels=["agent_version", "tenant_id"],
        ),
    ]

    # Performance metrics
    PERFORMANCE_METRICS = [
        MetricDefinition(
            name="http_request_duration_seconds",
            type=MetricType.HISTOGRAM,
            description="HTTP request duration",
            unit="seconds",
            labels=["method", "endpoint", "status"],
        ),
        MetricDefinition(
            name="http_requests_total",
            type=MetricType.COUNTER,
            description="Total HTTP requests",
            labels=["method", "endpoint", "status"],
        ),
        MetricDefinition(
            name="process_resident_memory_bytes",
            type=MetricType.GAUGE,
            description="Resident memory usage",
            unit="bytes",
        ),
        MetricDefinition(
            name="process_cpu_seconds_total",
            type=MetricType.COUNTER,
            description="CPU time used",
            unit="seconds",
        ),
    ]

    # Database metrics
    DATABASE_METRICS = [
        MetricDefinition(
            name="db_connection_pool_size",
            type=MetricType.GAUGE,
            description="Database connection pool size",
            labels=["pool_name"],
        ),
        MetricDefinition(
            name="db_connection_pool_checked_out",
            type=MetricType.GAUGE,
            description="Database connections checked out",
            labels=["pool_name"],
        ),
        MetricDefinition(
            name="db_query_duration_seconds",
            type=MetricType.HISTOGRAM,
            description="Database query duration",
            unit="seconds",
            labels=["query_type"],
        ),
        MetricDefinition(
            name="db_query_errors_total",
            type=MetricType.COUNTER,
            description="Total database query errors",
            labels=["query_type", "error_type"],
        ),
    ]

    # Cache metrics
    CACHE_METRICS = [
        MetricDefinition(
            name="cache_hits_total",
            type=MetricType.COUNTER,
            description="Total cache hits",
            labels=["cache_name"],
        ),
        MetricDefinition(
            name="cache_misses_total",
            type=MetricType.COUNTER,
            description="Total cache misses",
            labels=["cache_name"],
        ),
        MetricDefinition(
            name="cache_size_bytes",
            type=MetricType.GAUGE,
            description="Cache size",
            unit="bytes",
            labels=["cache_name"],
        ),
    ]

    # Feature flag metrics
    FEATURE_FLAG_METRICS = [
        MetricDefinition(
            name="feature_flag_enabled",
            type=MetricType.GAUGE,
            description="Feature flag enabled status",
            labels=["flag_name"],
        ),
        MetricDefinition(
            name="feature_flag_rollout_percentage",
            type=MetricType.GAUGE,
            description="Feature flag rollout percentage",
            labels=["flag_name"],
        ),
    ]

    # Alert rules
    ALERT_RULES = [
        AlertRule(
            name="AgentV2ErrorRateHigh",
            condition='(rate(agent_v2_errors_total[5m]) / rate(agent_v2_executions_total[5m])) > 0.05',
            severity=AlertSeverity.CRITICAL,
            duration="5m",
            description="Agent V2 error rate exceeds 5%",
            runbook_url="https://wiki.example.com/runbooks/agent-v2-error-rate",
        ),
        AlertRule(
            name="APIResponseTimeHigh",
            condition='histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1',
            severity=AlertSeverity.WARNING,
            duration="5m",
            description="API response time P95 exceeds 1 second",
            runbook_url="https://wiki.example.com/runbooks/api-response-time",
        ),
        AlertRule(
            name="DatabaseConnectionPoolExhausted",
            condition='db_connection_pool_checked_out / db_connection_pool_size > 0.9',
            severity=AlertSeverity.CRITICAL,
            duration="5m",
            description="Database connection pool usage exceeds 90%",
            runbook_url="https://wiki.example.com/runbooks/db-connection-pool",
        ),
        AlertRule(
            name="MemoryUsageHigh",
            condition='process_resident_memory_bytes > 1073741824',  # 1GB
            severity=AlertSeverity.WARNING,
            duration="10m",
            description="Memory usage exceeds 1GB",
            runbook_url="https://wiki.example.com/runbooks/memory-usage",
        ),
        AlertRule(
            name="CacheHitRateLow",
            condition='rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m])) < 0.7',
            severity=AlertSeverity.INFO,
            duration="10m",
            description="Cache hit rate below 70%",
            runbook_url="https://wiki.example.com/runbooks/cache-hit-rate",
        ),
        AlertRule(
            name="ServiceDown",
            condition='up{job="agent-backend"} == 0',
            severity=AlertSeverity.CRITICAL,
            duration="1m",
            description="Agent backend service is down",
            runbook_url="https://wiki.example.com/runbooks/service-down",
        ),
    ]

    # Dashboard configuration
    DASHBOARD_CONFIG = {
        "title": "Agent V2 Deployment Dashboard",
        "panels": [
            {
                "title": "Execution Statistics",
                "type": "stat",
                "metrics": [
                    "agent_v1_executions_total",
                    "agent_v2_executions_total",
                    "agent_v1_errors_total",
                    "agent_v2_errors_total",
                ],
            },
            {
                "title": "Error Rate Comparison",
                "type": "graph",
                "metrics": [
                    "rate(agent_v1_errors_total[5m]) / rate(agent_v1_executions_total[5m])",
                    "rate(agent_v2_errors_total[5m]) / rate(agent_v2_executions_total[5m])",
                ],
            },
            {
                "title": "Execution Duration",
                "type": "graph",
                "metrics": [
                    "histogram_quantile(0.50, rate(agent_execution_duration_seconds_bucket[5m]))",
                    "histogram_quantile(0.95, rate(agent_execution_duration_seconds_bucket[5m]))",
                    "histogram_quantile(0.99, rate(agent_execution_duration_seconds_bucket[5m]))",
                ],
            },
            {
                "title": "HTTP Request Duration",
                "type": "graph",
                "metrics": [
                    "histogram_quantile(0.50, rate(http_request_duration_seconds_bucket[5m]))",
                    "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
                ],
            },
            {
                "title": "Resource Usage",
                "type": "graph",
                "metrics": [
                    "process_resident_memory_bytes",
                    "process_cpu_seconds_total",
                ],
            },
            {
                "title": "Database Connection Pool",
                "type": "graph",
                "metrics": [
                    "db_connection_pool_checked_out",
                    "db_connection_pool_size",
                ],
            },
            {
                "title": "Cache Performance",
                "type": "graph",
                "metrics": [
                    "rate(cache_hits_total[5m])",
                    "rate(cache_misses_total[5m])",
                ],
            },
            {
                "title": "Feature Flag Status",
                "type": "stat",
                "metrics": [
                    "feature_flag_enabled{flag_name='use_agent_v2'}",
                    "feature_flag_rollout_percentage{flag_name='use_agent_v2'}",
                ],
            },
        ],
    }

    # SLO (Service Level Objectives)
    SLO_CONFIG = {
        "availability": {
            "target": 0.999,  # 99.9%
            "window": "30d",
            "description": "Service availability target",
        },
        "latency": {
            "p95": 500,  # milliseconds
            "p99": 1000,  # milliseconds
            "description": "API response time targets",
        },
        "error_rate": {
            "target": 0.001,  # 0.1%
            "window": "30d",
            "description": "Error rate target",
        },
    }


# Prometheus configuration template
PROMETHEUS_CONFIG_TEMPLATE = """
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - localhost:9093

rule_files:
  - 'alert_rules.yml'

scrape_configs:
  - job_name: 'agent-backend'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'

  - job_name: 'postgres'
    static_configs:
      - targets: ['localhost:5432']

  - job_name: 'redis'
    static_configs:
      - targets: ['localhost:6379']
"""

# Alert rules configuration template
ALERT_RULES_TEMPLATE = """
groups:
  - name: agent_v2_deployment
    interval: 30s
    rules:
      - alert: AgentV2ErrorRateHigh
        expr: |
          (rate(agent_v2_errors_total[5m]) / rate(agent_v2_executions_total[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Agent V2 error rate is high"
          description: "Error rate: {{ $value | humanizePercentage }}"

      - alert: APIResponseTimeHigh
        expr: |
          histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "API response time is high"
          description: "P95 response time: {{ $value }}s"

      - alert: DatabaseConnectionPoolExhausted
        expr: |
          db_connection_pool_checked_out / db_connection_pool_size > 0.9
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Database connection pool is nearly exhausted"
          description: "Pool usage: {{ $value | humanizePercentage }}"

      - alert: MemoryUsageHigh
        expr: |
          process_resident_memory_bytes > 1073741824
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Memory usage is high"
          description: "Memory: {{ $value | humanize }}B"

      - alert: ServiceDown
        expr: |
          up{job="agent-backend"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Agent backend service is down"
          description: "Service has been down for more than 1 minute"
"""

# Grafana dashboard JSON template
GRAFANA_DASHBOARD_TEMPLATE = {
    "dashboard": {
        "title": "Agent V2 Deployment",
        "tags": ["agent", "v2", "deployment"],
        "timezone": "browser",
        "panels": [
            {
                "title": "Execution Statistics",
                "targets": [
                    {
                        "expr": "agent_v1_executions_total",
                        "legendFormat": "Agent V1 Executions",
                    },
                    {
                        "expr": "agent_v2_executions_total",
                        "legendFormat": "Agent V2 Executions",
                    },
                ],
            },
            {
                "title": "Error Rate",
                "targets": [
                    {
                        "expr": "rate(agent_v1_errors_total[5m]) / rate(agent_v1_executions_total[5m])",
                        "legendFormat": "Agent V1 Error Rate",
                    },
                    {
                        "expr": "rate(agent_v2_errors_total[5m]) / rate(agent_v2_executions_total[5m])",
                        "legendFormat": "Agent V2 Error Rate",
                    },
                ],
            },
        ],
    }
}
