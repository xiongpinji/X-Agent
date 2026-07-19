"""Distributed tracing configuration using Jaeger and OpenTelemetry."""

from __future__ import annotations

import logging
from typing import Any

try:
    from opentelemetry import trace
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
except ImportError:
    trace = None  # type: ignore
    JaegerExporter = None  # type: ignore
    FastAPIInstrumentor = None  # type: ignore
    HTTPXClientInstrumentor = None  # type: ignore
    SQLAlchemyInstrumentor = None  # type: ignore
    Resource = None  # type: ignore
    TracerProvider = None  # type: ignore
    BatchSpanProcessor = None  # type: ignore

logger = logging.getLogger(__name__)


class TracingConfig:
    """Configuration for distributed tracing."""

    def __init__(
        self,
        enabled: bool = True,
        jaeger_host: str = "localhost",
        jaeger_port: int = 6831,
        service_name: str = "xagent",
        environment: str = "development",
        sample_rate: float = 1.0,
    ) -> None:
        """Initialize tracing configuration.

        Args:
            enabled: Enable tracing
            jaeger_host: Jaeger agent host
            jaeger_port: Jaeger agent port
            service_name: Service name for traces
            environment: Environment name
            sample_rate: Sampling rate (0.0 to 1.0)
        """
        self.enabled = enabled and trace is not None
        self.jaeger_host = jaeger_host
        self.jaeger_port = jaeger_port
        self.service_name = service_name
        self.environment = environment
        self.sample_rate = sample_rate
        self.tracer_provider: TracerProvider | None = None

    def setup(self) -> None:
        """Setup tracing with Jaeger."""
        if not self.enabled:
            logger.warning("Tracing is disabled")
            return

        try:
            # Create resource
            resource = Resource.create(
                {
                    SERVICE_NAME: self.service_name,
                    "environment": self.environment,
                }
            )

            # Create Jaeger exporter
            jaeger_exporter = JaegerExporter(
                agent_host_name=self.jaeger_host,
                agent_port=self.jaeger_port,
            )

            # Create tracer provider
            self.tracer_provider = TracerProvider(resource=resource)
            self.tracer_provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))

            # Set global tracer provider
            trace.set_tracer_provider(self.tracer_provider)

            logger.info(
                f"Tracing configured with Jaeger at {self.jaeger_host}:{self.jaeger_port}"
            )
        except Exception as e:
            logger.error(f"Failed to setup tracing: {e}")
            self.enabled = False

    def instrument_fastapi(self, app: Any) -> None:
        """Instrument FastAPI application.

        Args:
            app: FastAPI application instance
        """
        if not self.enabled:
            return

        try:
            FastAPIInstrumentor.instrument_app(app)
            logger.info("FastAPI instrumented for tracing")
        except Exception as e:
            logger.error(f"Failed to instrument FastAPI: {e}")

    def instrument_httpx(self) -> None:
        """Instrument HTTPX client."""
        if not self.enabled:
            return

        try:
            HTTPXClientInstrumentor().instrument()
            logger.info("HTTPX instrumented for tracing")
        except Exception as e:
            logger.error(f"Failed to instrument HTTPX: {e}")

    def instrument_sqlalchemy(self, engine: Any) -> None:
        """Instrument SQLAlchemy engine.

        Args:
            engine: SQLAlchemy engine instance
        """
        if not self.enabled:
            return

        try:
            SQLAlchemyInstrumentor().instrument(engine=engine)
            logger.info("SQLAlchemy instrumented for tracing")
        except Exception as e:
            logger.error(f"Failed to instrument SQLAlchemy: {e}")

    def get_tracer(self, name: str) -> Any:
        """Get tracer instance.

        Args:
            name: Tracer name

        Returns:
            Tracer instance
        """
        if not self.enabled or self.tracer_provider is None:
            return NoOpTracer()

        return self.tracer_provider.get_tracer(name)

    def shutdown(self) -> None:
        """Shutdown tracing."""
        if self.tracer_provider is not None:
            self.tracer_provider.force_flush()


class NoOpTracer:
    """No-op tracer for when tracing is disabled."""

    def start_as_current_span(self, name: str, **kwargs: Any) -> NoOpSpan:
        """Start a no-op span."""
        return NoOpSpan()

    def start_span(self, name: str, **kwargs: Any) -> NoOpSpan:
        """Start a no-op span."""
        return NoOpSpan()


class NoOpSpan:
    """No-op span for when tracing is disabled."""

    def __enter__(self) -> NoOpSpan:
        """Enter context manager."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Exit context manager."""
        pass

    def set_attribute(self, key: str, value: Any) -> None:
        """Set span attribute (no-op)."""
        pass

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Add span event (no-op)."""
        pass

    def record_exception(self, exception: Exception) -> None:
        """Record exception (no-op)."""
        pass


# Global tracing configuration
_tracing_config: TracingConfig | None = None


def get_tracing_config() -> TracingConfig:
    """Get global tracing configuration."""
    global _tracing_config
    if _tracing_config is None:
        _tracing_config = TracingConfig()
    return _tracing_config


def setup_tracing(
    jaeger_host: str = "localhost",
    jaeger_port: int = 6831,
    service_name: str = "xagent",
    environment: str = "development",
) -> TracingConfig:
    """Setup global tracing configuration.

    Args:
        jaeger_host: Jaeger agent host
        jaeger_port: Jaeger agent port
        service_name: Service name for traces
        environment: Environment name

    Returns:
        TracingConfig instance
    """
    global _tracing_config
    _tracing_config = TracingConfig(
        jaeger_host=jaeger_host,
        jaeger_port=jaeger_port,
        service_name=service_name,
        environment=environment,
    )
    _tracing_config.setup()
    return _tracing_config


def get_tracer(name: str) -> Any:
    """Get tracer instance.

    Args:
        name: Tracer name

    Returns:
        Tracer instance
    """
    config = get_tracing_config()
    return config.get_tracer(name)
