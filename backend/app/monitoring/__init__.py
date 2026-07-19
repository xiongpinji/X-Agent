"""Monitoring package for X-Agent.

Live modules: middleware (HTTP metrics/logging/tracing middleware),
resource_monitor, tracing, logging_config.

The former dead initialization helpers (initialize_monitoring,
setup_resource_monitoring, setup_health_checks) had zero callers after
main.py wired MetricsMiddleware and /metrics manually; they were archived
to archive/dead_code_2026-07-19/backend/app/monitoring/__init__.py.
"""
