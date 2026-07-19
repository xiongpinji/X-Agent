"""
X-Agent Monitoring Integration Module

This module provides comprehensive monitoring integration including:
- Prometheus metrics collection
- Jaeger distributed tracing
- Health check endpoints
- Performance metrics
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Callable, Optional

from prometheus_client import Counter, Gauge, Histogram, generate_latest
from jaeger_client import Config as JaegerConfig
from opentelemetry import trace, metrics
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

logger = logging.getLogger(__name__)


class PrometheusMetrics:
    """Prometheus metrics collection for X-Agent."""

    def __init__(self, app_name: str = "x-agent"):
        self.app_name = app_name

        # API metrics
        self.api_requests_total = Counter(
            "xagent_api_requests_total",
            "Total API requests",
            ["method", "endpoint", "status"],
        )

        self.api_request_duration_seconds = Histogram(
            "xagent_api_request_duration_seconds",
            "API request duration in seconds",
            ["method", "endpoint"],
            buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
        )

        self.api_errors_total = Counter(
            "xagent_errors_total",
            "Total API errors",
            ["error_type", "endpoint"],
        )

        # Agent execution metrics
        self.agent_runs_total = Counter(
            "xagent_agent_runs_total",
            "Total agent runs",
            ["status"],
        )

        self.agent_run_duration_seconds = Histogram(
            "xagent_agent_run_duration_seconds",
            "Agent run duration in seconds",
            buckets=(1, 5, 10, 30, 60, 300, 600, 1800),
        )

        # Database metrics
        self.db_query_duration_seconds = Histogram(
            "xagent_db_query_duration_seconds",
            "Database query duration in seconds",
            ["query_type"],
            buckets=(0.001, 0.01, 0.05, 0.1, 0.5, 1.0),
        )

        self.db_connections_active = Gauge(
            "xagent_db_connections_active",
            "Active database connections",
        )

        self.db_connection_pool_size = Gauge(
            "xagent_db_connection_pool_size",
            "Database connection pool size",
        )

        # Cache metrics
        self.cache_hits_total = Counter(
            "xagent_cache_hits_total",
            "Total cache hits",
            ["cache_type"],
        )

        self.cache_misses_total = Counter(
            "xagent_cache_misses_total",
            "Total cache misses",
            ["cache_type"],
        )

        # Tool execution metrics
        self.tool_executions_total = Counter(
            "xagent_tool_executions_total",
            "Total tool executions",
            ["tool_name", "status"],
        )

        self.tool_execution_duration_seconds = Histogram(
            "xagent_tool_execution_duration_seconds",
            "Tool execution duration in seconds",
            ["tool_name"],
            buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0),
        )

        # Workflow metrics
        self.workflow_runs_total = Counter(
            "xagent_workflow_runs_total",
            "Total workflow runs",
            ["status"],
        )

        self.workflow_run_duration_seconds = Histogram(
            "xagent_workflow_run_duration_seconds",
            "Workflow run duration in seconds",
            buckets=(1, 10, 30, 60, 300, 600, 1800, 3600),
        )

        # System metrics
        self.system_memory_usage_bytes = Gauge(
            "xagent_system_memory_usage_bytes",
            "System memory usage in bytes",
        )

        self.system_cpu_usage_percent = Gauge(
            "xagent_system_cpu_usage_percent",
            "System CPU usage percentage",
        )

        # Health check metrics
        self.health_check_status = Gauge(
            "xagent_health_check_status",
            "Health check status (1=healthy, 0=unhealthy)",
            ["component"],
        )

    def get_metrics(self) -> bytes:
        """Get Prometheus metrics in text format."""
        return generate_latest()


class JaegerTracing:
    """Jaeger distributed tracing integration."""

    def __init__(
        self,
        service_name: str = "x-agent",
        jaeger_host: str = "localhost",
        jaeger_port: int = 6831,
        sampler_type: str = "const",
        sampler_param: float = 1.0,
    ):
        self.service_name = service_name
        self.jaeger_host = jaeger_host
        self.jaeger_port = jaeger_port

        # Configure Jaeger exporter
        jaeger_exporter = JaegerExporter(
            agent_host_name=jaeger_host,
            agent_port=jaeger_port,
        )

        # Create tracer provider
        trace_provider = TracerProvider(
            resource=Resource.create({"service.name": service_name})
        )
        trace_provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
        trace.set_tracer_provider(trace_provider)

        self.tracer = trace.get_tracer(__name__)

    def get_tracer(self):
        """Get the tracer instance."""
        return self.tracer


class HealthChecker:
    """Health check system for monitoring."""

    def __init__(self):
        self.checks: dict[str, Callable[[], bool]] = {}

    def register_check(self, name: str, check_func: Callable[[], bool]) -> None:
        """Register a health check function."""
        self.checks[name] = check_func

    async def check_health(self) -> dict[str, Any]:
        """Run all health checks."""
        results = {}
        overall_healthy = True

        for name, check_func in self.checks.items():
            try:
                if hasattr(check_func, "__await__"):
                    is_healthy = await check_func()
                else:
                    is_healthy = check_func()
                results[name] = {
                    "status": "healthy" if is_healthy else "unhealthy",
                    "timestamp": time.time(),
                }
                if not is_healthy:
                    overall_healthy = False
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                results[name] = {
                    "status": "error",
                    "error": str(e),
                    "timestamp": time.time(),
                }
                overall_healthy = False

        return {
            "status": "healthy" if overall_healthy else "unhealthy",
            "checks": results,
            "timestamp": time.time(),
        }


class MonitoringMiddleware:
    """FastAPI middleware for monitoring."""

    def __init__(self, app, metrics: PrometheusMetrics):
        self.app = app
        self.metrics = metrics

    async def __call__(self, request, call_next):
        """Process request with monitoring."""
        start_time = time.time()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            self.metrics.api_errors_total.labels(
                error_type=type(e).__name__,
                endpoint=request.url.path,
            ).inc()
            raise
        finally:
            duration = time.time() - start_time

            # Record metrics
            self.metrics.api_requests_total.labels(
                method=request.method,
                endpoint=request.url.path,
                status=status_code,
            ).inc()

            self.metrics.api_request_duration_seconds.labels(
                method=request.method,
                endpoint=request.url.path,
            ).observe(duration)

        return response


def setup_monitoring(
    app,
    service_name: str = "x-agent",
    jaeger_enabled: bool = True,
    jaeger_host: str = "localhost",
    jaeger_port: int = 6831,
) -> tuple[PrometheusMetrics, Optional[JaegerTracing], HealthChecker]:
    """
    Setup complete monitoring for the application.

    Args:
        app: FastAPI application instance
        service_name: Name of the service
        jaeger_enabled: Enable Jaeger tracing
        jaeger_host: Jaeger agent host
        jaeger_port: Jaeger agent port

    Returns:
        Tuple of (metrics, tracing, health_checker)
    """

    # Initialize Prometheus metrics
    metrics = PrometheusMetrics(app_name=service_name)
    logger.info("Prometheus metrics initialized")

    # Initialize Jaeger tracing if enabled
    tracing = None
    if jaeger_enabled:
        try:
            tracing = JaegerTracing(
                service_name=service_name,
                jaeger_host=jaeger_host,
                jaeger_port=jaeger_port,
            )
            logger.info(f"Jaeger tracing initialized: {jaeger_host}:{jaeger_port}")
        except Exception as e:
            logger.warning(f"Failed to initialize Jaeger tracing: {e}")

    # Initialize health checker
    health_checker = HealthChecker()
    logger.info("Health checker initialized")

    # Add monitoring middleware
    app.add_middleware(MonitoringMiddleware, metrics=metrics)

    return metrics, tracing, health_checker


@asynccontextmanager
async def trace_operation(tracer, operation_name: str, attributes: Optional[dict] = None):
    """Context manager for tracing operations."""
    with tracer.start_as_current_span(operation_name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        yield span


def record_metric(
    metric: Counter | Gauge | Histogram,
    value: float = 1.0,
    labels: Optional[dict] = None,
) -> None:
    """Record a metric value."""
    if isinstance(metric, Counter):
        if labels:
            metric.labels(**labels).inc(value)
        else:
            metric.inc(value)
    elif isinstance(metric, Gauge):
        if labels:
            metric.labels(**labels).set(value)
        else:
            metric.set(value)
    elif isinstance(metric, Histogram):
        if labels:
            metric.labels(**labels).observe(value)
        else:
            metric.observe(value)
