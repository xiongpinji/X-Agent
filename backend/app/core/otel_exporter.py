"""P2-06: OpenTelemetry integration — OTLP trace/metric export for enterprise observability.

Exports:
- Agent session spans (run lifecycle: start → plan → execute → finalize)
- Tool execution spans (per-tool with duration, success/failure)
- LLM call spans (model, tokens, latency)
- Custom metrics: token_usage_total, tool_calls_total, session_duration_seconds

Configuration (env vars):
- XAGENT_OTEL_ENABLED=true/false (default: false)
- XAGENT_OTEL_ENDPOINT=http://localhost:4317 (OTLP gRPC)
- XAGENT_OTEL_SERVICE_NAME=xagent-api
- XAGENT_OTEL_METRIC_INTERVAL=60 (seconds)
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Lazy OTel imports — graceful degradation when SDK not installed
_otel_available = False
try:
    from opentelemetry import metrics as otel_metrics
    from opentelemetry import trace as otel_trace
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.trace import StatusCode

    _otel_available = True
except ImportError:
    otel_metrics = None  # type: ignore
    otel_trace = None  # type: ignore
    StatusCode = None  # type: ignore


@dataclass
class OTelConfig:
    """OpenTelemetry configuration."""

    enabled: bool = False
    endpoint: str = "http://localhost:4317"
    service_name: str = "xagent-api"
    metric_interval_seconds: int = 60
    trace_sample_rate: float = 1.0
    environment: str = "development"


class OTelExporter:
    """OpenTelemetry exporter for X-Agent observability.

    Provides:
    - Distributed tracing (OTLP gRPC/HTTP)
    - Custom metrics (counters, histograms)
    - Graceful no-op when OTel SDK is not installed or disabled
    """

    def __init__(self, config: OTelConfig | None = None) -> None:
        self._config = config or OTelConfig()
        self._initialized = False
        self._tracer = None
        self._meter = None
        self._counters: dict[str, Any] = {}
        self._histograms: dict[str, Any] = {}

        if self._config.enabled and _otel_available:
            self._initialize()

    def _initialize(self) -> None:
        """Initialize OTel providers and exporters."""
        try:
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

            resource = Resource.create({
                SERVICE_NAME: self._config.service_name,
                "deployment.environment": self._config.environment,
            })

            # Trace provider
            span_exporter = OTLPSpanExporter(endpoint=self._config.endpoint)
            tracer_provider = TracerProvider(resource=resource)
            tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
            otel_trace.set_tracer_provider(tracer_provider)
            self._tracer = otel_trace.get_tracer(self._config.service_name)

            # Metric provider
            metric_exporter = OTLPMetricExporter(endpoint=self._config.endpoint)
            metric_reader = PeriodicExportingMetricReader(
                metric_exporter,
                export_interval_millis=self._config.metric_interval_seconds * 1000,
            )
            meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
            otel_metrics.set_meter_provider(meter_provider)
            self._meter = otel_metrics.get_meter(self._config.service_name)

            # Pre-create instruments
            self._counters["token_usage"] = self._meter.create_counter(
                "xagent.tokens.total",
                description="Total tokens consumed",
                unit="tokens",
            )
            self._counters["tool_calls"] = self._meter.create_counter(
                "xagent.tool_calls.total",
                description="Total tool executions",
                unit="calls",
            )
            self._counters["agent_runs"] = self._meter.create_counter(
                "xagent.agent_runs.total",
                description="Total agent runs",
                unit="runs",
            )
            self._histograms["session_duration"] = self._meter.create_histogram(
                "xagent.session.duration",
                description="Agent session duration",
                unit="s",
            )
            self._histograms["tool_latency"] = self._meter.create_histogram(
                "xagent.tool.latency",
                description="Tool execution latency",
                unit="ms",
            )
            self._histograms["llm_latency"] = self._meter.create_histogram(
                "xagent.llm.latency",
                description="LLM call latency",
                unit="ms",
            )

            self._initialized = True
            logger.info(
                "P2-06: OTel exporter initialized (endpoint=%s, service=%s)",
                self._config.endpoint,
                self._config.service_name,
            )
        except Exception as e:
            logger.warning("P2-06: OTel initialization failed (degraded to no-op): %s", e)
            self._initialized = False

    @property
    def is_active(self) -> bool:
        return self._initialized

    # --- Tracing ---

    @contextmanager
    def trace_span(
        self, name: str, *, attributes: dict[str, Any] | None = None
    ) -> Generator[Any, None, None]:
        """Create a trace span context manager."""
        if not self._initialized or self._tracer is None:
            yield None
            return

        with self._tracer.start_as_current_span(name) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, str(value))
            yield span

    def record_tool_execution(
        self,
        tool_name: str,
        success: bool,
        latency_ms: float,
        *,
        trace_id: str = "",
        risk_level: str = "low",
    ) -> None:
        """Record a tool execution metric."""
        if not self._initialized:
            return
        self._counters["tool_calls"].add(
            1,
            {"tool": tool_name, "success": str(success), "risk_level": risk_level},
        )
        self._histograms["tool_latency"].record(
            latency_ms, {"tool": tool_name, "success": str(success)}
        )

    def record_llm_call(
        self,
        model: str,
        tokens_used: int,
        latency_ms: float,
        *,
        tenant_id: str = "",
    ) -> None:
        """Record an LLM call metric."""
        if not self._initialized:
            return
        self._counters["token_usage"].add(
            tokens_used, {"model": model, "tenant_id": tenant_id}
        )
        self._histograms["llm_latency"].record(
            latency_ms, {"model": model}
        )

    def record_agent_run(
        self,
        status: str,
        duration_seconds: float,
        *,
        iterations: int = 0,
        tool_call_count: int = 0,
        tenant_id: str = "",
    ) -> None:
        """Record an agent run metric."""
        if not self._initialized:
            return
        self._counters["agent_runs"].add(
            1, {"status": status, "tenant_id": tenant_id}
        )
        self._histograms["session_duration"].record(
            duration_seconds, {"status": status}
        )


# --- Global singleton ---

_otel_exporter: OTelExporter | None = None


def get_otel_exporter() -> OTelExporter:
    """Get the global OTel exporter (lazy init from settings)."""
    global _otel_exporter
    if _otel_exporter is None:
        from backend.app.settings import get_settings

        settings = get_settings()
        config = OTelConfig(
            enabled=getattr(settings, "otel_enabled", False),
            endpoint=getattr(settings, "otel_endpoint", "http://localhost:4317"),
            service_name=getattr(settings, "otel_service_name", "xagent-api"),
            metric_interval_seconds=getattr(settings, "otel_metric_interval", 60),
            environment=getattr(settings, "app_mode", "development"),
        )
        _otel_exporter = OTelExporter(config)
    return _otel_exporter
