"""Example: Integrating monitoring into X-Agent FastAPI application."""

from __future__ import annotations

from fastapi import FastAPI
from prometheus_client import generate_latest
from starlette.responses import Response

from backend.app.services.observability.monitoring_setup import setup_monitoring
from backend.app.services.observability.prometheus_middleware import metrics_endpoint

# Example usage in main.py or app initialization


def setup_app_monitoring(app: FastAPI, db_engine=None) -> None:
    """
    Setup complete monitoring for the FastAPI application.

    Usage:
        from fastapi import FastAPI
        from backend.app.services.observability.monitoring_setup import setup_monitoring

        app = FastAPI()
        setup_monitoring(app, db_engine)

        # Add metrics endpoint
        @app.get("/metrics")
        async def metrics():
            return Response(generate_latest(), media_type="text/plain; charset=utf-8")
    """
    # Setup all monitoring components
    monitoring = setup_monitoring(
        app=app,
        engine=db_engine,
    )

    # Add metrics endpoint
    @app.get("/metrics", tags=["monitoring"])
    async def metrics():
        """Prometheus metrics endpoint."""
        return await metrics_endpoint()

    # Add health check endpoint
    @app.get("/health", tags=["monitoring"])
    async def health():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "service": "x-agent",
            "version": "0.1.0",
        }

    # Add readiness check endpoint
    @app.get("/ready", tags=["monitoring"])
    async def ready():
        """Readiness check endpoint."""
        return {
            "status": "ready",
            "service": "x-agent",
        }


# Example: Recording custom metrics

from backend.app.services.observability.prometheus_metrics import (
    agent_runs_total,
    agent_run_duration_seconds,
    tool_executions_total,
    workflow_runs_total,
)


async def example_agent_execution():
    """Example of recording agent execution metrics."""
    import time

    agent_id = "agent-001"
    start_time = time.perf_counter()

    try:
        # Simulate agent work
        await asyncio.sleep(1)

        # Record successful run
        agent_runs_total.labels(agent_id=agent_id, status="success").inc()
        duration = time.perf_counter() - start_time
        agent_run_duration_seconds.labels(agent_id=agent_id).observe(duration)

    except Exception as e:
        # Record failed run
        agent_runs_total.labels(agent_id=agent_id, status="failed").inc()
        raise


async def example_tool_execution():
    """Example of recording tool execution metrics."""
    import time

    tool_name = "browser_automation"
    start_time = time.perf_counter()

    try:
        # Simulate tool execution
        await asyncio.sleep(0.5)

        # Record successful execution
        tool_executions_total.labels(tool_name=tool_name, status="success").inc()

    except Exception as e:
        # Record failed execution
        tool_executions_total.labels(tool_name=tool_name, status="failed").inc()
        raise


# Example: Using context managers for metrics

from backend.app.services.observability.prometheus_metrics import (
    async_metrics_context,
    db_query_duration_seconds,
)


async def example_database_query():
    """Example of recording database query metrics."""
    async with async_metrics_context(
        db_query_duration_seconds,
        labels={"query_type": "select", "table": "workflows"},
    ):
        # Simulate database query
        await asyncio.sleep(0.1)


# Example: Structured logging with context

import logging
from backend.app.services.observability.logging_config import get_logger

logger = get_logger(__name__)


def example_structured_logging():
    """Example of structured logging with context."""
    logger.info(
        "Workflow execution started",
        extra={
            "request_id": "req-123",
            "user_id": "user-456",
            "tenant_id": "tenant-789",
            "workflow_id": "wf-001",
            "trace_id": "trace-abc",
        },
    )


# Example: Distributed tracing with Jaeger

from opentelemetry import trace

tracer = trace.get_tracer(__name__)


async def example_distributed_tracing():
    """Example of distributed tracing with Jaeger."""
    with tracer.start_as_current_span("process_workflow") as span:
        span.set_attribute("workflow_id", "wf-001")
        span.set_attribute("user_id", "user-456")
        span.set_attribute("tenant_id", "tenant-789")

        # Simulate workflow processing
        await asyncio.sleep(0.5)

        span.set_attribute("status", "completed")


# Integration example in main application

"""
# In backend/app/main.py

from fastapi import FastAPI
from backend.app.services.observability.monitoring_setup import setup_monitoring

app = FastAPI(title="X-Agent", version="0.1.0")

# Setup monitoring before adding routes
setup_monitoring(app, db_engine)

# Add your routes here
@app.get("/api/v1/workflows")
async def list_workflows():
    return {"workflows": []}

# Run with: uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
"""
