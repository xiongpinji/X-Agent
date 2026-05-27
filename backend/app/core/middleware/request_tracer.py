"""
Request tracing middleware.

Provides:
- Trace ID and span ID generation
- Cross-service tracing support
- Langfuse integration
- Request context propagation
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Callable

from starlette.requests import Request
from starlette.responses import Response

from .base import BaseMiddleware

logger = logging.getLogger(__name__)


class RequestTracerMiddleware(BaseMiddleware):
    """
    Request tracing middleware for distributed tracing.

    Configuration:
        trace_id_header: Header name for trace ID (default: x-trace-id)
        span_id_header: Header name for span ID (default: x-span-id)
        correlation_id_header: Header name for correlation ID (default: x-correlation-id)
        langfuse_enabled: Enable Langfuse integration (default: False)
        langfuse_client: Langfuse client instance
    """

    DEFAULT_TRACE_ID_HEADER = "x-trace-id"
    DEFAULT_SPAN_ID_HEADER = "x-span-id"
    DEFAULT_CORRELATION_ID_HEADER = "x-correlation-id"

    def __init__(self, app: Any, **config: Any) -> None:
        """Initialize request tracing middleware."""
        super().__init__(app, **config)
        self.trace_id_header = config.get("trace_id_header", self.DEFAULT_TRACE_ID_HEADER)
        self.span_id_header = config.get("span_id_header", self.DEFAULT_SPAN_ID_HEADER)
        self.correlation_id_header = config.get(
            "correlation_id_header", self.DEFAULT_CORRELATION_ID_HEADER
        )
        self.langfuse_enabled = config.get("langfuse_enabled", False)
        self.langfuse_client = config.get("langfuse_client", None)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Trace request."""
        if not self.is_enabled():
            return await call_next(request)

        # Generate or extract trace IDs
        trace_id = self._get_or_generate_trace_id(request)
        span_id = self._generate_span_id()
        correlation_id = self._get_or_generate_correlation_id(request)

        # Store in request state
        request.state.trace_id = trace_id
        request.state.span_id = span_id
        request.state.correlation_id = correlation_id

        # Record trace start
        start_time = time.time()
        trace_data = {
            "trace_id": trace_id,
            "span_id": span_id,
            "correlation_id": correlation_id,
            "method": request.method,
            "path": request.url.path,
            "query": request.url.query or None,
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent"),
        }

        # Extract user context if available
        if hasattr(request.state, "user_id"):
            trace_data["user_id"] = request.state.user_id
        if hasattr(request.state, "tenant_id"):
            trace_data["tenant_id"] = request.state.tenant_id

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Record trace end
            trace_data["status_code"] = response.status_code
            trace_data["duration_ms"] = round(duration * 1000, 2)
            trace_data["event"] = "trace_end"

            # Add trace headers to response
            response.headers[self.trace_id_header] = trace_id
            response.headers[self.span_id_header] = span_id
            response.headers[self.correlation_id_header] = correlation_id

            # Log trace
            self.logger.info(json.dumps(trace_data, ensure_ascii=False))

            # Report to Langfuse if enabled
            if self.langfuse_enabled and self.langfuse_client:
                await self._report_to_langfuse(trace_data)

            return response

        except Exception as e:
            duration = time.time() - start_time
            trace_data["error"] = str(e)
            trace_data["error_type"] = type(e).__name__
            trace_data["duration_ms"] = round(duration * 1000, 2)
            trace_data["event"] = "trace_error"

            self.logger.error(json.dumps(trace_data, ensure_ascii=False), exc_info=True)

            # Report error to Langfuse if enabled
            if self.langfuse_enabled and self.langfuse_client:
                await self._report_to_langfuse(trace_data)

            raise

    def _get_or_generate_trace_id(self, request: Request) -> str:
        """Get trace ID from header or generate new one."""
        trace_id = request.headers.get(self.trace_id_header)
        if not trace_id:
            trace_id = str(uuid.uuid4())
        return trace_id

    def _get_or_generate_correlation_id(self, request: Request) -> str:
        """Get correlation ID from header or generate new one."""
        correlation_id = request.headers.get(self.correlation_id_header)
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        return correlation_id

    def _generate_span_id(self) -> str:
        """Generate new span ID."""
        return str(uuid.uuid4())

    async def _report_to_langfuse(self, trace_data: dict[str, Any]) -> None:
        """Report trace to Langfuse."""
        if not self.langfuse_client:
            return

        try:
            # Map trace data to Langfuse format
            langfuse_event = {
                "traceId": trace_data.get("trace_id"),
                "spanId": trace_data.get("span_id"),
                "name": f"{trace_data.get('method')} {trace_data.get('path')}",
                "startTime": time.time(),
                "endTime": time.time(),
                "metadata": {
                    "method": trace_data.get("method"),
                    "path": trace_data.get("path"),
                    "status_code": trace_data.get("status_code"),
                    "duration_ms": trace_data.get("duration_ms"),
                    "user_id": trace_data.get("user_id"),
                    "tenant_id": trace_data.get("tenant_id"),
                },
            }

            # Report to Langfuse
            if hasattr(self.langfuse_client, "trace"):
                self.langfuse_client.trace(langfuse_event)
            elif hasattr(self.langfuse_client, "capture_event"):
                self.langfuse_client.capture_event(langfuse_event)

        except Exception as e:
            self.logger.error(f"Failed to report to Langfuse: {e}")
