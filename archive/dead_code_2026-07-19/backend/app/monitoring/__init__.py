"""Monitoring system initialization for X-Agent."""

from __future__ import annotations

import logging
import os
from typing import Any

from backend.app.monitoring.logging_config import setup_logging
from backend.app.monitoring.tracing import setup_tracing

logger = logging.getLogger(__name__)


def initialize_monitoring(app: Any) -> None:
    """Initialize all monitoring systems.

    Args:
        app: FastAPI application instance
    """
    # Setup logging
    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_dir = os.getenv("LOG_DIR", "/var/log/xagent")
    setup_logging(
        log_level=log_level,
        log_dir=log_dir,
        enable_console=True,
        enable_file=True,
    )
    logger.info(f"Logging configured with level {log_level}")

    # Setup tracing
    jaeger_host = os.getenv("JAEGER_HOST", "localhost")
    jaeger_port = int(os.getenv("JAEGER_PORT", "6831"))
    environment = os.getenv("ENVIRONMENT", "development")

    tracing_config = setup_tracing(
        jaeger_host=jaeger_host,
        jaeger_port=jaeger_port,
        service_name="xagent",
        environment=environment,
    )
    logger.info(f"Tracing configured with Jaeger at {jaeger_host}:{jaeger_port}")

    # Instrument FastAPI
    tracing_config.instrument_fastapi(app)
    tracing_config.instrument_httpx()

    # Add monitoring middleware
    from backend.app.monitoring.middleware import (
        LoggingMiddleware,
        MetricsMiddleware,
        TracingMiddleware,
    )

    app.add_middleware(LoggingMiddleware)
    app.add_middleware(TracingMiddleware)
    app.add_middleware(MetricsMiddleware)

    logger.info("Monitoring middleware added to FastAPI application")

    # Setup metrics endpoint
    try:
        from prometheus_client import make_asgi_app

        metrics_app = make_asgi_app()
        app.mount("/metrics", metrics_app)
        logger.info("Prometheus metrics endpoint mounted at /metrics")
    except ImportError:
        logger.warning("prometheus_client not installed, metrics endpoint not available")

    logger.info("Monitoring system initialized successfully")


def setup_resource_monitoring() -> None:
    """Setup resource monitoring (CPU, memory, disk)."""
    import threading

    from backend.app.monitoring.resource_monitor import ResourceMonitor

    monitor = ResourceMonitor()
    thread = threading.Thread(target=monitor.start, daemon=True)
    thread.start()
    logger.info("Resource monitoring started")


def setup_health_checks(app: Any) -> None:
    """Setup health check endpoints.

    Args:
        app: FastAPI application instance
    """
    from backend.app.api.health import router as health_router

    app.include_router(health_router)
    logger.info("Health check endpoints registered")
