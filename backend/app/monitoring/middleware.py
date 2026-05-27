"""Monitoring middleware for FastAPI application."""

from __future__ import annotations

import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.core.metrics import metrics_collector

logger = logging.getLogger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting HTTP metrics."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and collect metrics."""
        start_time = time.perf_counter()

        # Extract request information
        method = request.method
        path = request.url.path

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            logger.error(f"Request failed: {e}", exc_info=True)
            raise
        finally:
            # Calculate duration
            duration = time.perf_counter() - start_time

            # Record metrics
            metrics_collector.record_http_request(
                method=method,
                endpoint=path,
                status=status_code,
                duration_seconds=duration,
            )

            # Record errors
            if status_code >= 500:
                metrics_collector.record_error(
                    error_type="server_error",
                    endpoint=path,
                )
            elif status_code >= 400:
                metrics_collector.record_error(
                    error_type="client_error",
                    endpoint=path,
                )

        return response


class TracingMiddleware(BaseHTTPMiddleware):
    """Middleware for distributed tracing."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with tracing."""
        from backend.app.monitoring.tracing import get_tracer

        tracer = get_tracer(__name__)

        # Extract trace context from headers
        trace_id = request.headers.get("X-Trace-ID", "")
        span_id = request.headers.get("X-Span-ID", "")

        with tracer.start_as_current_span(f"{request.method} {request.url.path}") as span:
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.url", str(request.url))
            span.set_attribute("http.target", request.url.path)

            if trace_id:
                span.set_attribute("trace_id", trace_id)
            if span_id:
                span.set_attribute("span_id", span_id)

            try:
                response = await call_next(request)
                span.set_attribute("http.status_code", response.status_code)
                return response
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("error", True)
                raise


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured logging."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with logging."""
        from backend.app.monitoring.logging_config import log_request

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            logger.error(f"Request processing failed: {e}", exc_info=True)
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log request
            log_request(
                logger,
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                duration_ms=duration_ms,
                request_id=request.headers.get("X-Request-ID"),
            )

        return response
