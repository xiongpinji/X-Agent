"""
Structured logging middleware.

Provides:
- JSON-formatted request/response logging
- Performance metrics (slow query detection)
- Request context propagation
- Configurable log levels and exclusions
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable

from starlette.requests import Request
from starlette.responses import Response

from .base import BaseMiddleware

logger = logging.getLogger(__name__)


class StructuredLoggingMiddleware(BaseMiddleware):
    """
    Structured logging middleware with JSON output.

    Configuration:
        excluded_paths: Set of paths to exclude from logging
        slow_query_threshold: Duration threshold for slow query detection (seconds)
        log_request_body: Whether to log request body (default: False)
        log_response_body: Whether to log response body (default: False)
        max_body_size: Maximum body size to log (bytes, default: 1000)
    """

    DEFAULT_EXCLUDED_PATHS = {"/health", "/ready", "/metrics", "/docs", "/openapi.json"}
    DEFAULT_SLOW_QUERY_THRESHOLD = 1.0  # seconds
    DEFAULT_MAX_BODY_SIZE = 1000  # bytes

    def __init__(self, app: Any, **config: Any) -> None:
        """Initialize logging middleware."""
        super().__init__(app, **config)
        self.excluded_paths = config.get("excluded_paths", self.DEFAULT_EXCLUDED_PATHS)
        self.slow_query_threshold = config.get(
            "slow_query_threshold", self.DEFAULT_SLOW_QUERY_THRESHOLD
        )
        self.log_request_body = config.get("log_request_body", False)
        self.log_response_body = config.get("log_response_body", False)
        self.max_body_size = config.get("max_body_size", self.DEFAULT_MAX_BODY_SIZE)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response."""
        if not self.is_enabled():
            return await call_next(request)

        # Skip excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)

        start_time = time.time()

        # Extract request info
        method = request.method
        path = request.url.path
        query_string = request.url.query
        client_ip = request.client.host if request.client else "unknown"

        # Get context info
        correlation_id = getattr(request.state, "correlation_id", None)
        user_id = getattr(request.state, "user_id", None)
        tenant_id = getattr(request.state, "tenant_id", None)

        # Extract request body if configured
        request_body = None
        if self.log_request_body and method in {"POST", "PUT", "PATCH"}:
            try:
                body = await request.body()
                if len(body) <= self.max_body_size:
                    request_body = body.decode("utf-8", errors="ignore")
            except Exception as e:
                self.logger.debug(f"Failed to read request body: {e}")

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Extract response body if configured
            response_body = None
            if self.log_response_body and response.status_code < 400:
                try:
                    # Note: This is a simplified approach; in production,
                    # you might need to use response.body_iterator
                    if hasattr(response, "body"):
                        body = response.body
                        if len(body) <= self.max_body_size:
                            response_body = body.decode("utf-8", errors="ignore")
                except Exception as e:
                    self.logger.debug(f"Failed to read response body: {e}")

            # Build log data
            log_data = {
                "event": "http_request",
                "timestamp": time.time(),
                "method": method,
                "path": path,
                "query": query_string or None,
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2),
                "client_ip": client_ip,
                "correlation_id": correlation_id,
                "user_id": user_id,
                "tenant_id": tenant_id,
            }

            # Add optional fields
            if request_body:
                log_data["request_body"] = request_body
            if response_body:
                log_data["response_body"] = response_body

            # Detect slow queries
            if duration > self.slow_query_threshold:
                log_data["slow_query"] = True
                self.logger.warning(json.dumps(log_data, ensure_ascii=False))
            elif response.status_code >= 400:
                self.logger.warning(json.dumps(log_data, ensure_ascii=False))
            else:
                self.logger.info(json.dumps(log_data, ensure_ascii=False))

            return response

        except Exception as e:
            duration = time.time() - start_time
            log_data = {
                "event": "http_error",
                "timestamp": time.time(),
                "method": method,
                "path": path,
                "query": query_string or None,
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_ms": round(duration * 1000, 2),
                "client_ip": client_ip,
                "correlation_id": correlation_id,
                "user_id": user_id,
                "tenant_id": tenant_id,
            }

            self.logger.error(json.dumps(log_data, ensure_ascii=False), exc_info=True)
            raise
