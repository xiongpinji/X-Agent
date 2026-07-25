"""Structured logging factory for X-Agent.

This module provides a centralized logging factory that ensures consistent
logging across the application with structured logging support.

Usage:
    from backend.app.core.logger_factory import LoggerFactory

    logger = LoggerFactory.get_logger(__name__)
    logger.info("Operation started", extra={"user_id": "123"})
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


class StructuredFormatter(logging.Formatter):
    """Formatter that outputs structured JSON logs.

    Converts log records to JSON format with all relevant context information.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: The log record to format

        Returns:
            JSON-formatted log string
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_data.update(record.extra)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


class PlainFormatter(logging.Formatter):
    """Formatter that outputs plain text logs.

    Provides human-readable log output for development and debugging.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as plain text.

        Args:
            record: The log record to format

        Returns:
            Formatted log string
        """
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        extra_str = ""

        if hasattr(record, "extra") and isinstance(record.extra, dict):
            extra_str = " | " + " | ".join(
                f"{k}={v}" for k, v in record.extra.items()
            )

        return (
            f"[{timestamp}] {record.levelname:8} {record.name:30} "
            f"{record.funcName}:{record.lineno} - {record.getMessage()}{extra_str}"
        )


class LoggerFactory:
    """Factory for creating configured loggers.

    Provides centralized logger creation with consistent configuration
    across the application.
    """

    _configured = False
    _log_level = logging.INFO
    _log_format = "plain"  # "plain" or "json"
    _log_dir: Path | None = None

    @classmethod
    def configure(
        cls,
        level: int = logging.INFO,
        format_type: str = "plain",
        log_dir: str | None = None,
    ) -> None:
        """Configure the logger factory.

        Args:
            level: Logging level (default: INFO)
            format_type: Log format type - "plain" or "json" (default: "plain")
            log_dir: Optional directory for log files
        """
        cls._log_level = level
        cls._log_format = format_type
        if log_dir:
            cls._log_dir = Path(log_dir)
            cls._log_dir.mkdir(parents=True, exist_ok=True)
        cls._configured = True

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """Get a configured logger.

        Args:
            name: Logger name (typically __name__)

        Returns:
            Configured logger instance
        """
        logger = logging.getLogger(name)

        # Only configure once
        if logger.handlers:
            return logger

        logger.setLevel(cls._log_level)

        # Create formatter
        formatter = StructuredFormatter() if cls._log_format == "json" else PlainFormatter()

        # Add console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(cls._log_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # Add file handler if log_dir is configured
        if cls._log_dir:
            log_file = cls._log_dir / f"{name.replace('.', '_')}.log"
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
            )
            file_handler.setLevel(cls._log_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    @classmethod
    def get_child_logger(cls, parent_name: str, child_name: str) -> logging.Logger:
        """Get a child logger.

        Args:
            parent_name: Parent logger name
            child_name: Child logger name

        Returns:
            Configured child logger instance
        """
        full_name = f"{parent_name}.{child_name}"
        return cls.get_logger(full_name)


class LogContext:
    """Context manager for adding context to logs.

    Allows adding context information that will be included in all logs
    within the context.

    Usage:
        with LogContext(user_id="123", request_id="abc"):
            logger.info("Processing request")  # Will include user_id and request_id
    """

    _context_stack: list[dict[str, Any]] = []

    def __init__(self, **context: Any) -> None:
        """Initialize log context.

        Args:
            **context: Context key-value pairs
        """
        self.context = context

    def __enter__(self) -> LogContext:
        """Enter context."""
        LogContext._context_stack.append(self.context)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context."""
        if LogContext._context_stack:
            LogContext._context_stack.pop()

    @classmethod
    def get_current_context(cls) -> dict[str, Any]:
        """Get current context.

        Returns:
            Merged context from all active contexts
        """
        merged = {}
        for context in cls._context_stack:
            merged.update(context)
        return merged


def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    **kwargs: Any,
) -> None:
    """Log message with current context.

    Args:
        logger: Logger instance
        level: Log level
        message: Log message
        **kwargs: Additional context
    """
    context = LogContext.get_current_context()
    context.update(kwargs)

    # Create a custom log record with extra context
    record = logger.makeRecord(
        logger.name,
        level,
        "(unknown file)",
        0,
        message,
        (),
        None,
    )
    record.extra = context
    logger.handle(record)


# Convenience functions
def get_logger(name: str) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return LoggerFactory.get_logger(name)


def configure_logging(
    level: int = logging.INFO,
    format_type: str = "plain",
    log_dir: str | None = None,
) -> None:
    """Configure logging globally.

    Args:
        level: Logging level
        format_type: Log format type
        log_dir: Optional log directory
    """
    LoggerFactory.configure(level=level, format_type=format_type, log_dir=log_dir)
