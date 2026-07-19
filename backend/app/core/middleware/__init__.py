"""
Middleware system for cross-cutting concerns.

Provides:
- Base middleware interface
- Middleware chain pattern
- Pluggable middleware architecture
- Async-first design
"""

from __future__ import annotations

from .base import BaseMiddleware, MiddlewareChain
from .logging_middleware import StructuredLoggingMiddleware
from .error_handler import ErrorHandlingMiddleware
from .performance_monitor import PerformanceMonitorMiddleware
from .request_tracer import RequestTracerMiddleware

__all__ = [
    "BaseMiddleware",
    "MiddlewareChain",
    "StructuredLoggingMiddleware",
    "ErrorHandlingMiddleware",
    "PerformanceMonitorMiddleware",
    "RequestTracerMiddleware",
]
