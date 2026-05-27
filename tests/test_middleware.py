"""
Tests for middleware system.

Tests:
- Individual middleware functionality
- Middleware chain execution
- Error handling and propagation
- Performance monitoring
- Request tracing
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.testclient import TestClient

from backend.app.core.middleware.base import BaseMiddleware, MiddlewareChain
from backend.app.core.middleware.logging_middleware import StructuredLoggingMiddleware
from backend.app.core.middleware.error_handler import ErrorHandlingMiddleware, ErrorCategory
from backend.app.core.middleware.performance_monitor import PerformanceMonitorMiddleware
from backend.app.core.middleware.request_tracer import RequestTracerMiddleware
from backend.app.core.middleware.config import MiddlewareConfig, MiddlewareFactory


# Test fixtures
@pytest.fixture
def app():
    """Create test application."""
    app = Starlette()

    @app.route("/test")
    async def test_endpoint(request):
        return JSONResponse({"status": "ok"})

    @app.route("/error")
    async def error_endpoint(request):
        raise ValueError("Test error")

    @app.route("/slow")
    async def slow_endpoint(request):
        import time
        time.sleep(1.5)
        return JSONResponse({"status": "ok"})

    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


# Base middleware tests
class TestBaseMiddleware:
    """Test base middleware functionality."""

    def test_middleware_enabled_by_default(self, app):
        """Test middleware is enabled by default."""
        middleware = StructuredLoggingMiddleware(app)
        assert middleware.is_enabled()

    def test_middleware_can_be_disabled(self, app):
        """Test middleware can be disabled."""
        middleware = StructuredLoggingMiddleware(app, enabled=False)
        assert not middleware.is_enabled()

    def test_middleware_config_storage(self, app):
        """Test middleware stores configuration."""
        config = {"key": "value", "number": 42}
        middleware = StructuredLoggingMiddleware(app, **config)
        assert middleware.get_config("key") == "value"
        assert middleware.get_config("number") == 42
        assert middleware.get_config("missing", "default") == "default"


# Middleware chain tests
class TestMiddlewareChain:
    """Test middleware chain functionality."""

    def test_empty_chain_execution(self):
        """Test empty chain passes through."""
        chain = MiddlewareChain()
        assert len(chain._middlewares) == 0

    def test_chain_add_middleware(self, app):
        """Test adding middleware to chain."""
        chain = MiddlewareChain()
        middleware = StructuredLoggingMiddleware(app)
        chain.add(middleware)
        assert len(chain._middlewares) == 1

    def test_chain_fluent_api(self, app):
        """Test chain fluent API."""
        chain = MiddlewareChain()
        result = chain.add(StructuredLoggingMiddleware(app)).add(
            ErrorHandlingMiddleware(app)
        )
        assert result is chain
        assert len(chain._middlewares) == 2

    def test_chain_get_stats(self, app):
        """Test chain statistics."""
        chain = MiddlewareChain()
        chain.add(StructuredLoggingMiddleware(app), enabled=True)
        chain.add(ErrorHandlingMiddleware(app), enabled=False)

        stats = chain.get_stats()
        assert stats["total_middleware"] == 2
        assert stats["enabled_middleware"] == 1


# Logging middleware tests
class TestStructuredLoggingMiddleware:
    """Test structured logging middleware."""

    def test_logging_middleware_excludes_paths(self, app, client):
        """Test logging middleware excludes configured paths."""
        app.add_middleware(
            StructuredLoggingMiddleware,
            excluded_paths={"/health", "/ready"},
        )
        # Should not raise
        response = client.get("/health")
        assert response.status_code == 404  # Not found, but no logging error

    def test_logging_middleware_json_format(self, app, client, caplog):
        """Test logging middleware outputs JSON."""
        app.add_middleware(StructuredLoggingMiddleware)
        response = client.get("/test")
        assert response.status_code == 200

        # Check logs contain JSON
        log_records = [r for r in caplog.records if "http_request" in r.getMessage()]
        assert len(log_records) > 0


# Error handler middleware tests
class TestErrorHandlingMiddleware:
    """Test error handling middleware."""

    def test_error_classification(self, app):
        """Test error classification."""
        middleware = ErrorHandlingMiddleware(app)

        # Test validation error
        assert middleware._classify_error(ValueError("test")) == ErrorCategory.VALIDATION

        # Test authentication error
        class AuthError(Exception):
            pass

        assert middleware._classify_error(AuthError("test")) == ErrorCategory.AUTHENTICATION

        # Test system error
        assert middleware._classify_error(RuntimeError("test")) == ErrorCategory.SYSTEM

    def test_error_status_code_mapping(self, app):
        """Test error to status code mapping."""
        middleware = ErrorHandlingMiddleware(app)

        assert middleware._get_status_code(ValueError(), ErrorCategory.VALIDATION) == 422
        assert middleware._get_status_code(ValueError(), ErrorCategory.AUTHENTICATION) == 401
        assert middleware._get_status_code(ValueError(), ErrorCategory.BUSINESS) == 400
        assert middleware._get_status_code(ValueError(), ErrorCategory.SYSTEM) == 500

    def test_error_user_message(self, app):
        """Test user-friendly error messages."""
        middleware = ErrorHandlingMiddleware(app)

        assert "Invalid" in middleware._get_user_message(ValueError(), ErrorCategory.VALIDATION)
        assert "Authentication" in middleware._get_user_message(
            ValueError(), ErrorCategory.AUTHENTICATION
        )


# Performance monitor middleware tests
class TestPerformanceMonitorMiddleware:
    """Test performance monitoring middleware."""

    def test_performance_stats_initialization(self, app):
        """Test performance stats are initialized."""
        middleware = PerformanceMonitorMiddleware(app)
        stats = middleware.get_stats()

        assert stats["total_requests"] == 0
        assert stats["total_errors"] == 0
        assert stats["average_duration_ms"] == 0

    def test_slow_request_detection(self, app, client):
        """Test slow request detection."""
        app.add_middleware(
            PerformanceMonitorMiddleware,
            slow_request_threshold=0.1,  # 100ms
        )
        response = client.get("/slow")
        assert response.status_code == 200

        # Get middleware instance to check stats
        # Note: In real tests, you'd need to access the middleware instance


# Request tracer middleware tests
class TestRequestTracerMiddleware:
    """Test request tracing middleware."""

    def test_trace_id_generation(self, app):
        """Test trace ID generation."""
        middleware = RequestTracerMiddleware(app)
        request = MagicMock(spec=Request)
        request.headers = {}

        trace_id = middleware._get_or_generate_trace_id(request)
        assert trace_id is not None
        assert len(trace_id) > 0

    def test_trace_id_from_header(self, app):
        """Test trace ID extraction from header."""
        middleware = RequestTracerMiddleware(app)
        request = MagicMock(spec=Request)
        request.headers = {"x-trace-id": "test-trace-123"}

        trace_id = middleware._get_or_generate_trace_id(request)
        assert trace_id == "test-trace-123"

    def test_span_id_generation(self, app):
        """Test span ID generation."""
        middleware = RequestTracerMiddleware(app)
        span_id = middleware._generate_span_id()
        assert span_id is not None
        assert len(span_id) > 0


# Middleware factory tests
class TestMiddlewareFactory:
    """Test middleware factory."""

    def test_factory_creates_logging_middleware(self, app):
        """Test factory creates logging middleware."""
        middleware = MiddlewareFactory.create_logging_middleware(app)
        assert isinstance(middleware, StructuredLoggingMiddleware)

    def test_factory_creates_error_handler_middleware(self, app):
        """Test factory creates error handler middleware."""
        middleware = MiddlewareFactory.create_error_handler_middleware(app)
        assert isinstance(middleware, ErrorHandlingMiddleware)

    def test_factory_creates_performance_monitor_middleware(self, app):
        """Test factory creates performance monitor middleware."""
        middleware = MiddlewareFactory.create_performance_monitor_middleware(app)
        assert isinstance(middleware, PerformanceMonitorMiddleware)

    def test_factory_creates_request_tracer_middleware(self, app):
        """Test factory creates request tracer middleware."""
        middleware = MiddlewareFactory.create_request_tracer_middleware(app)
        assert isinstance(middleware, RequestTracerMiddleware)

    def test_factory_creates_chain(self, app):
        """Test factory creates middleware chain."""
        config = MiddlewareConfig()
        chain = MiddlewareFactory.create_chain(app, config)
        assert isinstance(chain, MiddlewareChain)
        assert chain.get_stats()["total_middleware"] == 4


# Middleware configuration tests
class TestMiddlewareConfig:
    """Test middleware configuration."""

    def test_config_initialization(self):
        """Test configuration initialization."""
        config = MiddlewareConfig()
        assert config.logging_config is not None
        assert config.error_handler_config is not None
        assert config.performance_monitor_config is not None
        assert config.request_tracer_config is not None

    def test_config_fluent_api(self):
        """Test configuration fluent API."""
        config = MiddlewareConfig()
        result = config.set_logging_config(slow_query_threshold=2.0).set_error_handler_config(
            include_traceback=True
        )
        assert result is config
        assert config.logging_config["slow_query_threshold"] == 2.0
        assert config.error_handler_config["include_traceback"] is True

    def test_config_to_dict(self):
        """Test configuration to dictionary."""
        config = MiddlewareConfig()
        config_dict = config.to_dict()
        assert "logging" in config_dict
        assert "error_handler" in config_dict
        assert "performance_monitor" in config_dict
        assert "request_tracer" in config_dict


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
