"""Structured logging configuration for X-Agent.

Provides JSON-formatted structured logging with request context propagation.
Uses structlog for structured logging with fallback to standard logging.

Usage:
    from backend.app.core.logging_config import setup_logging, get_logger
    
    # During app startup
    setup_logging(json_output=True, level="INFO")
    
    # In modules
    logger = get_logger(__name__)
    logger.info("event_name", user_id="123", action="login")
"""

from __future__ import annotations

import logging
import sys
from typing import Any

# Try to import structlog, fall back to standard logging
try:
    import structlog
    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False


def setup_logging(
    json_output: bool = False,
    level: str = "INFO",
    service_name: str = "xagent-api",
) -> None:
    """Configure structured logging for the application.
    
    Args:
        json_output: If True, output logs as JSON (for production).
                     If False, use console-friendly format (for development).
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        service_name: Service name to include in all log entries.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )
    
    if STRUCTLOG_AVAILABLE:
        # Shared processors for all log entries
        shared_processors: list[Any] = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),
            # Add service name to all logs
            lambda logger, method_name, event_dict: {
                **event_dict,
                "service": service_name,
            },
        ]
        
        if json_output:
            # Production: JSON output for log aggregation
            renderer = structlog.processors.JSONRenderer()
        else:
            # Development: Console-friendly colored output
            renderer = structlog.dev.ConsoleRenderer()
        
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        # Configure the formatter for standard library handlers
        formatter = structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                renderer,
            ],
        )
        
        # Apply formatter to root logger
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        # Attach RequestIdFilter so stdlib log records also carry request_id
        handler.addFilter(RequestIdFilter())
        
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.addHandler(handler)
        root_logger.setLevel(log_level)
        
        # Reduce noise from third-party libraries
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        
    else:
        # Fallback: standard logging with basic format
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.addHandler(handler)
        root_logger.setLevel(log_level)


def get_logger(name: str | None = None) -> Any:
    """Get a structured logger instance.
    
    Args:
        name: Logger name (usually __name__).
        
    Returns:
        A structlog BoundLogger if structlog is available,
        otherwise a standard logging.Logger.
    """
    if STRUCTLOG_AVAILABLE:
        return structlog.get_logger(name)
    return logging.getLogger(name)


def bind_request_context(
    request_id: str,
    user_id: str | None = None,
    tenant_id: str | None = None,
    **extra: Any,
) -> None:
    """Bind request context to the current context for log correlation.
    
    Call this at the start of request handling to include request_id,
    user_id, and tenant_id in all subsequent log entries.
    
    Args:
        request_id: Unique request identifier.
        user_id: Authenticated user ID (if available).
        tenant_id: Tenant ID (if available).
        **extra: Additional context fields.
    """
    if STRUCTLOG_AVAILABLE:
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            user_id=user_id,
            tenant_id=tenant_id,
            **extra,
        )


def clear_request_context() -> None:
    """Clear the current request context."""
    if STRUCTLOG_AVAILABLE:
        structlog.contextvars.clear_contextvars()


class RequestIdFilter(logging.Filter):
    """Logging filter that adds request_id from contextvars to log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        if STRUCTLOG_AVAILABLE:
            ctx = structlog.contextvars.get_contextvars()
            record.request_id = ctx.get("request_id", "-")
        else:
            record.request_id = "-"
        return True


def create_request_id_middleware():
    """Create a middleware that sets up request context for logging.
    
    Returns:
        A Starlette middleware class.
    """
    from uuid import uuid4

    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    
    class RequestIdMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            # Get or generate request ID
            request_id = request.headers.get("x-request-id") or str(uuid4())
            
            # Bind to logging context
            bind_request_context(
                request_id=request_id,
                path=request.url.path,
                method=request.method,
            )
            
            try:
                response = await call_next(request)
                response.headers["x-request-id"] = request_id
                return response
            finally:
                clear_request_context()
    
    return RequestIdMiddleware
import logging
from datetime import datetime

import structlog
from pythonjsonlogger.jsonlogger import JsonFormatter


class StructuredFormatter(JsonFormatter):
    """Custom JSON formatter for structured logging."""

    def add_fields(self, log_record: dict[str, Any], record: logging.LogRecord, message_dict: dict[str, Any]) -> None:
        super().add_fields(log_record, record, message_dict)

        # Add standard fields
        log_record['timestamp'] = datetime.utcnow().isoformat()
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['module'] = record.module
        log_record['function'] = record.funcName
        log_record['line'] = record.lineno

        # Add request context if available
        if hasattr(record, 'request_id'):
            log_record['request_id'] = record.request_id
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id
        if hasattr(record, 'tenant_id'):
            log_record['tenant_id'] = record.tenant_id

        # Add exception info if present
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)

        # Mask sensitive information
        self._mask_sensitive_fields(log_record)

    def _mask_sensitive_fields(self, log_record: dict[str, Any]) -> None:
        """Mask sensitive information in logs."""
        sensitive_keys = [
            'password', 'token', 'secret', 'api_key', 'authorization',
            'credit_card', 'ssn', 'private_key', 'access_token', 'refresh_token'
        ]

        for key in list(log_record.keys()):
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                log_record[key] = '***MASKED***'
            elif isinstance(log_record[key], dict):
                self._mask_sensitive_fields(log_record[key])


class RequestContextFilter(logging.Filter):
    """Add request context to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        # This will be populated by middleware
        return True


class SensitiveDataFilter(logging.Filter):
    """Filter to mask sensitive data in logs."""

    SENSITIVE_PATTERNS = [
        r'password["\']?\s*[:=]\s*["\']?([^"\'}\s]+)',
        r'token["\']?\s*[:=]\s*["\']?([^"\'}\s]+)',
        r'api[_-]?key["\']?\s*[:=]\s*["\']?([^"\'}\s]+)',
        r'secret["\']?\s*[:=]\s*["\']?([^"\'}\s]+)',
        r'authorization["\']?\s*[:=]\s*["\']?([^"\'}\s]+)',
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        import re
        message = record.getMessage()
        for pattern in self.SENSITIVE_PATTERNS:
            message = re.sub(pattern, r'\1***MASKED***', message, flags=re.IGNORECASE)
        record.msg = message
        return True
