"""Structured logging configuration for X-Agent with JSON formatting."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.thread,
            "thread_name": record.threadName,
            "process": record.process,
        }

        # Add exception information if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            log_data["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None

        # Add extra fields if present
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        # Add context information
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "tenant_id"):
            log_data["tenant_id"] = record.tenant_id

        return json.dumps(log_data, default=str)


class StructuredLogger(logging.LoggerAdapter):
    """Logger adapter for adding structured context to logs."""

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Process log message and add context."""
        return msg, kwargs

    def log_with_context(
        self,
        level: int,
        msg: str,
        extra_fields: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Log with additional context fields."""
        extra = kwargs.pop("extra", {})
        if extra_fields:
            extra["extra_fields"] = extra_fields
        self.log(level, msg, extra=extra, **kwargs)


def setup_logging(
    log_level: str = "INFO",
    log_dir: str | None = None,
    enable_console: bool = True,
    enable_file: bool = True,
) -> None:
    """Configure structured logging for X-Agent.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files (default: /var/log/xagent)
        enable_console: Enable console output
        enable_file: Enable file output
    """
    # Create logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create formatters
    json_formatter = JSONFormatter()

    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_handler.setFormatter(json_formatter)
        root_logger.addHandler(console_handler)

    # File handler
    if enable_file:
        if log_dir is None:
            log_dir = "/var/log/xagent"

        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        # Main log file
        main_log_file = log_path / "xagent.log"
        file_handler = logging.FileHandler(main_log_file)
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_handler.setFormatter(json_formatter)
        root_logger.addHandler(file_handler)

        # Error log file
        error_log_file = log_path / "xagent-error.log"
        error_handler = logging.FileHandler(error_log_file)
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(json_formatter)
        root_logger.addHandler(error_handler)

    # Configure specific loggers
    logging.getLogger("xagent").setLevel(getattr(logging, log_level.upper()))
    logging.getLogger("xagent.api").setLevel(getattr(logging, log_level.upper()))
    logging.getLogger("xagent.core").setLevel(getattr(logging, log_level.upper()))
    logging.getLogger("xagent.services").setLevel(getattr(logging, log_level.upper()))

    # Suppress verbose third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    logging.getLogger("uvicorn").setLevel(logging.INFO)


def get_structured_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name

    Returns:
        StructuredLogger instance
    """
    logger = logging.getLogger(name)
    return StructuredLogger(logger, {})


# Convenience functions for common logging patterns
def log_request(
    logger: logging.Logger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    request_id: str | None = None,
) -> None:
    """Log HTTP request."""
    extra_fields = {
        "http_method": method,
        "http_path": path,
        "http_status": status_code,
        "duration_ms": duration_ms,
    }
    if request_id:
        extra_fields["request_id"] = request_id

    if status_code >= 500:
        logger.error("HTTP request failed", extra={"extra_fields": extra_fields})
    elif status_code >= 400:
        logger.warning("HTTP request error", extra={"extra_fields": extra_fields})
    else:
        logger.info("HTTP request completed", extra={"extra_fields": extra_fields})


def log_agent_execution(
    logger: logging.Logger,
    agent_id: str,
    status: str,
    duration_ms: float,
    error: str | None = None,
) -> None:
    """Log agent execution."""
    extra_fields = {
        "agent_id": agent_id,
        "execution_status": status,
        "duration_ms": duration_ms,
    }
    if error:
        extra_fields["error"] = error

    if status == "failed":
        logger.error("Agent execution failed", extra={"extra_fields": extra_fields})
    elif status == "completed":
        logger.info("Agent execution completed", extra={"extra_fields": extra_fields})
    else:
        logger.debug("Agent execution status", extra={"extra_fields": extra_fields})


def log_tool_call(
    logger: logging.Logger,
    tool_name: str,
    status: str,
    duration_ms: float,
    error: str | None = None,
) -> None:
    """Log tool call."""
    extra_fields = {
        "tool_name": tool_name,
        "call_status": status,
        "duration_ms": duration_ms,
    }
    if error:
        extra_fields["error"] = error

    if status == "failed":
        logger.error("Tool call failed", extra={"extra_fields": extra_fields})
    else:
        logger.info("Tool call completed", extra={"extra_fields": extra_fields})


def log_database_query(
    logger: logging.Logger,
    query_type: str,
    status: str,
    duration_ms: float,
    error: str | None = None,
) -> None:
    """Log database query."""
    extra_fields = {
        "query_type": query_type,
        "query_status": status,
        "duration_ms": duration_ms,
    }
    if error:
        extra_fields["error"] = error

    if status == "failed":
        logger.error("Database query failed", extra={"extra_fields": extra_fields})
    else:
        logger.debug("Database query completed", extra={"extra_fields": extra_fields})
