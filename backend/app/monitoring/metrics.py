"""X-Agent Prometheus metrics definitions.

Canonical metric registry for the X-Agent platform. All metrics use the
``xagent_`` prefix and are registered on the default prometheus_client
CollectorRegistry (the same registry served by the /metrics endpoint in
main.py).

Usage::

    from backend.app.monitoring.metrics import REQUESTS_TOTAL, REQUEST_DURATION
    REQUESTS_TOTAL.labels(method="GET", path="/health", status=200).inc()
"""
from __future__ import annotations

import logging

try:
    from prometheus_client import Counter, Gauge, Histogram, Info
except ImportError:  # pragma: no cover – graceful degradation
    Counter = Gauge = Histogram = Info = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Safe metric creation helpers – avoid "Duplicated timeseries" crashes when
# the module is imported multiple times (tests, hot-reload) or when a metric
# name was already registered by legacy code (backend.app.core.metrics).
# ---------------------------------------------------------------------------
_METRIC_CACHE: dict[str, object] = {}


def _get_or_create(metric_cls, name: str, documentation: str, labelnames=None, **kwargs):
    """Get-or-create a Prometheus metric, avoiding duplicate registration."""
    if metric_cls is None:
        return None
    cached = _METRIC_CACHE.get(name)
    if cached is not None:
        return cached
    try:
        if labelnames:
            metric = metric_cls(name, documentation, labelnames, **kwargs)
        else:
            metric = metric_cls(name, documentation, **kwargs)
    except ValueError:
        # Metric already registered (e.g. by core.metrics legacy module).
        # Return None; callers should guard with ``if metric is not None``.
        logger.debug("Metric %s already registered elsewhere; skipping.", name)
        return None
    _METRIC_CACHE[name] = metric
    return metric


# ---------------------------------------------------------------------------
# HTTP request metrics
# ---------------------------------------------------------------------------
REQUESTS_TOTAL = _get_or_create(
    Counter,
    "xagent_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

REQUEST_DURATION = _get_or_create(
    Histogram,
    "xagent_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# ---------------------------------------------------------------------------
# Agent metrics
# ---------------------------------------------------------------------------
AGENT_RUNS_TOTAL = _get_or_create(
    Counter,
    "xagent_agent_runs_total",
    "Total agent execution runs",
    ["status"],  # success, failure, timeout
)

AGENT_RUN_DURATION = _get_or_create(
    Histogram,
    "xagent_agent_run_duration_seconds",
    "Agent run duration",
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
)

# ---------------------------------------------------------------------------
# LLM metrics
# ---------------------------------------------------------------------------
LLM_CALLS_TOTAL = _get_or_create(
    Counter,
    "xagent_llm_calls_total",
    "Total LLM API calls",
    ["backend", "model", "status"],
)

LLM_TOKENS_TOTAL = _get_or_create(
    Counter,
    "xagent_llm_tokens_total",
    "Total LLM tokens consumed",
    ["backend", "model", "type"],  # type: prompt, completion
)

# ---------------------------------------------------------------------------
# Memory metrics
# ---------------------------------------------------------------------------
MEMORY_OPERATIONS_TOTAL = _get_or_create(
    Counter,
    "xagent_memory_operations_total",
    "Total memory operations",
    ["operation", "backend"],  # operation: store, search, delete
)

# ---------------------------------------------------------------------------
# Active sessions gauge
# ---------------------------------------------------------------------------
ACTIVE_SESSIONS = _get_or_create(
    Gauge,
    "xagent_active_sessions",
    "Number of active agent sessions",
)

# ---------------------------------------------------------------------------
# App info
# ---------------------------------------------------------------------------
APP_INFO = _get_or_create(
    Info,
    "xagent",
    "X-Agent application info",
)
