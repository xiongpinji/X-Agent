"""
Middleware configuration and factory.

Provides:
- Centralized middleware configuration
- Factory for creating middleware instances
- Environment-based configuration
"""

from __future__ import annotations

import logging
from typing import Any

from .base import MiddlewareChain
from .error_handler import ErrorHandlingMiddleware
from .logging_middleware import StructuredLoggingMiddleware
from .performance_monitor import PerformanceMonitorMiddleware
from .request_tracer import RequestTracerMiddleware

logger = logging.getLogger(__name__)


class MiddlewareConfig:
    """Middleware configuration."""

    def __init__(self) -> None:
        """Initialize configuration."""
        self.logging_config: dict[str, Any] = {
            "excluded_paths": {"/health", "/ready", "/metrics", "/docs", "/openapi.json"},
            "slow_query_threshold": 1.0,
            "log_request_body": False,
            "log_response_body": False,
            "max_body_size": 1000,
        }

        self.error_handler_config: dict[str, Any] = {
            "include_traceback": False,
            "include_details": False,
            "report_errors": False,
            "error_reporter": None,
        }

        self.performance_monitor_config: dict[str, Any] = {
            "slow_request_threshold": 1.0,
            "max_slow_requests_history": 100,
            "enable_metrics": False,
        }

        self.request_tracer_config: dict[str, Any] = {
            "trace_id_header": "x-trace-id",
            "span_id_header": "x-span-id",
            "correlation_id_header": "x-correlation-id",
            "langfuse_enabled": False,
            "langfuse_client": None,
        }

    def set_logging_config(self, **config: Any) -> MiddlewareConfig:
        """Set logging middleware configuration."""
        self.logging_config.update(config)
        return self

    def set_error_handler_config(self, **config: Any) -> MiddlewareConfig:
        """Set error handler middleware configuration."""
        self.error_handler_config.update(config)
        return self

    def set_performance_monitor_config(self, **config: Any) -> MiddlewareConfig:
        """Set performance monitor middleware configuration."""
        self.performance_monitor_config.update(config)
        return self

    def set_request_tracer_config(self, **config: Any) -> MiddlewareConfig:
        """Set request tracer middleware configuration."""
        self.request_tracer_config.update(config)
        return self

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "logging": self.logging_config,
            "error_handler": self.error_handler_config,
            "performance_monitor": self.performance_monitor_config,
            "request_tracer": self.request_tracer_config,
        }


class MiddlewareFactory:
    """Factory for creating middleware instances."""

    @staticmethod
    def create_logging_middleware(app: Any, **config: Any) -> StructuredLoggingMiddleware:
        """Create logging middleware."""
        return StructuredLoggingMiddleware(app, **config)

    @staticmethod
    def create_error_handler_middleware(app: Any, **config: Any) -> ErrorHandlingMiddleware:
        """Create error handler middleware."""
        return ErrorHandlingMiddleware(app, **config)

    @staticmethod
    def create_performance_monitor_middleware(
        app: Any, **config: Any
    ) -> PerformanceMonitorMiddleware:
        """Create performance monitor middleware."""
        return PerformanceMonitorMiddleware(app, **config)

    @staticmethod
    def create_request_tracer_middleware(app: Any, **config: Any) -> RequestTracerMiddleware:
        """Create request tracer middleware."""
        return RequestTracerMiddleware(app, **config)

    @staticmethod
    def create_chain(app: Any, config: MiddlewareConfig) -> MiddlewareChain:
        """Create middleware chain from configuration."""
        chain = MiddlewareChain()

        # Add middleware in order
        # 1. Request tracing (first to capture all requests)
        tracer = MiddlewareFactory.create_request_tracer_middleware(
            app, **config.request_tracer_config
        )
        chain.add(tracer, enabled=True)

        # 2. Error handling (before logging to catch all errors)
        error_handler = MiddlewareFactory.create_error_handler_middleware(
            app, **config.error_handler_config
        )
        chain.add(error_handler, enabled=True)

        # 3. Performance monitoring
        perf_monitor = MiddlewareFactory.create_performance_monitor_middleware(
            app, **config.performance_monitor_config
        )
        chain.add(perf_monitor, enabled=True)

        # 4. Structured logging (last to log all requests)
        logger_mw = MiddlewareFactory.create_logging_middleware(
            app, **config.logging_config
        )
        chain.add(logger_mw, enabled=True)

        return chain


def create_default_middleware_chain(app: Any) -> MiddlewareChain:
    """Create default middleware chain."""
    config = MiddlewareConfig()
    return MiddlewareFactory.create_chain(app, config)
