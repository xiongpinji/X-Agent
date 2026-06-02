"""Monitoring integration module for X-Agent."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI

from backend.app.services.observability.prometheus_middleware import PrometheusMiddleware
from backend.app.services.observability.logging_config import setup_logging
from backend.app.services.observability.jaeger_tracing import setup_jaeger_tracing
from backend.app.settings import get_settings

logger = logging.getLogger(__name__)


class MonitoringSetup:
    """Complete monitoring setup for X-Agent."""

    def __init__(self):
        self.settings = get_settings()
        self.jaeger_config = None

    def setup_logging(self, log_level: str = "INFO", log_dir: Optional[str] = None) -> None:
        """Setup structured logging."""
        try:
            setup_logging(
                log_level=log_level or self.settings.log_level,
                log_dir=log_dir or self.settings.log_dir,
            )
            logger.info("Logging configured successfully")
        except Exception as e:
            logger.error(f"Failed to setup logging: {e}")
            raise

    def setup_prometheus(self, app: FastAPI) -> None:
        """Setup Prometheus metrics collection."""
        try:
            app.add_middleware(PrometheusMiddleware, group_paths=True)
            logger.info("Prometheus middleware added")
        except Exception as e:
            logger.error(f"Failed to setup Prometheus: {e}")
            raise

    def setup_jaeger(
        self,
        app: FastAPI,
        engine: Optional[object] = None,
    ) -> None:
        """Setup Jaeger distributed tracing."""
        try:
            self.jaeger_config = setup_jaeger_tracing(
                service_name=self.settings.app_name,
                jaeger_host=self.settings.jaeger_host,
                jaeger_port=self.settings.jaeger_port,
            )

            # Instrument FastAPI
            self.jaeger_config.instrument_fastapi(app)

            # Instrument database if provided
            if engine:
                self.jaeger_config.instrument_sqlalchemy(engine)

            # Instrument other components
            self.jaeger_config.instrument_redis()
            self.jaeger_config.instrument_http_clients()

            logger.info("Jaeger tracing configured successfully")
        except Exception as e:
            logger.error(f"Failed to setup Jaeger: {e}")
            # Don't raise - tracing is optional

    def setup_all(
        self,
        app: FastAPI,
        engine: Optional[object] = None,
        log_level: str = "INFO",
        log_dir: Optional[str] = None,
    ) -> None:
        """Setup all monitoring components."""
        logger.info("Starting monitoring setup...")

        # Setup logging first
        self.setup_logging(log_level, log_dir)

        # Setup Prometheus
        self.setup_prometheus(app)

        # Setup Jaeger
        self.setup_jaeger(app, engine)

        logger.info("Monitoring setup completed successfully")


def setup_monitoring(
    app: FastAPI,
    engine: Optional[object] = None,
) -> MonitoringSetup:
    """Setup monitoring for X-Agent application."""
    monitoring = MonitoringSetup()
    monitoring.setup_all(app, engine)
    return monitoring
