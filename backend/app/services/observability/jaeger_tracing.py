"""Jaeger distributed tracing integration for X-Agent."""

from __future__ import annotations

import logging
from typing import Optional

from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

from backend.app.settings import get_settings

logger = logging.getLogger(__name__)


class JaegerTracingConfig:
    """Jaeger tracing configuration and initialization."""

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
        self.sampler_type = sampler_type
        self.sampler_param = sampler_param
        self.tracer_provider: Optional[TracerProvider] = None

    def initialize(self) -> TracerProvider:
        """Initialize Jaeger tracing."""
        try:
            # Create Jaeger exporter
            jaeger_exporter = JaegerExporter(
                agent_host_name=self.jaeger_host,
                agent_port=self.jaeger_port,
            )

            # Create resource
            resource = Resource(
                attributes={
                    SERVICE_NAME: self.service_name,
                    "environment": get_settings().app_mode,
                    "version": "0.1.0",
                }
            )

            # Create tracer provider
            self.tracer_provider = TracerProvider(resource=resource)

            # Add batch span processor
            self.tracer_provider.add_span_processor(
                BatchSpanProcessor(jaeger_exporter)
            )

            # Set global tracer provider
            trace.set_tracer_provider(self.tracer_provider)

            logger.info(
                f"Jaeger tracing initialized: {self.jaeger_host}:{self.jaeger_port}"
            )

            return self.tracer_provider

        except Exception as e:
            logger.error(f"Failed to initialize Jaeger tracing: {e}")
            raise

    def instrument_fastapi(self, app) -> None:
        """Instrument FastAPI application."""
        try:
            FastAPIInstrumentor.instrument_app(app)
            logger.info("FastAPI instrumented for tracing")
        except Exception as e:
            logger.error(f"Failed to instrument FastAPI: {e}")

    def instrument_sqlalchemy(self, engine) -> None:
        """Instrument SQLAlchemy."""
        try:
            SQLAlchemyInstrumentor().instrument(engine=engine)
            logger.info("SQLAlchemy instrumented for tracing")
        except Exception as e:
            logger.error(f"Failed to instrument SQLAlchemy: {e}")

    def instrument_redis(self) -> None:
        """Instrument Redis."""
        try:
            RedisInstrumentor().instrument()
            logger.info("Redis instrumented for tracing")
        except Exception as e:
            logger.error(f"Failed to instrument Redis: {e}")

    def instrument_http_clients(self) -> None:
        """Instrument HTTP clients."""
        try:
            RequestsInstrumentor().instrument()
            HTTPXClientInstrumentor().instrument()
            logger.info("HTTP clients instrumented for tracing")
        except Exception as e:
            logger.error(f"Failed to instrument HTTP clients: {e}")

    def instrument_all(self, app, engine) -> None:
        """Instrument all components."""
        self.instrument_fastapi(app)
        self.instrument_sqlalchemy(engine)
        self.instrument_redis()
        self.instrument_http_clients()


def setup_jaeger_tracing(
    service_name: str = "x-agent",
    jaeger_host: Optional[str] = None,
    jaeger_port: Optional[int] = None,
) -> JaegerTracingConfig:
    """Setup Jaeger tracing with settings from environment."""
    settings = get_settings()

    config = JaegerTracingConfig(
        service_name=service_name,
        jaeger_host=jaeger_host or settings.jaeger_host,
        jaeger_port=jaeger_port or settings.jaeger_port,
    )

    config.initialize()
    return config


def get_tracer(name: str) -> trace.Tracer:
    """Get a tracer instance."""
    return trace.get_tracer(name)
