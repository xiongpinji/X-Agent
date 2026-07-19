"""Structured logging configuration for X-Agent."""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Any

from backend.app.settings import get_settings


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id

        if hasattr(record, "tenant_id"):
            log_data["tenant_id"] = record.tenant_id

        if hasattr(record, "trace_id"):
            log_data["trace_id"] = record.trace_id

        if hasattr(record, "span_id"):
            log_data["span_id"] = record.span_id

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "stack_info",
                "getMessage",
                "request_id",
                "user_id",
                "tenant_id",
                "trace_id",
                "span_id",
            }:
                log_data[key] = str(value)

        return json.dumps(log_data, default=str)


def setup_logging(log_level: str = "INFO", log_dir: str | None = None) -> None:
    """Configure structured logging for X-Agent."""
    settings = get_settings()

    # Create log directory if specified
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
    else:
        log_path = Path("/var/log/xagent")
        log_path.mkdir(parents=True, exist_ok=True)

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # JSON formatter
    json_formatter = JSONFormatter()

    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(json_formatter)
    root_logger.addHandler(console_handler)

    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_path / "xagent.log",
        maxBytes=100 * 1024 * 1024,  # 100MB
        backupCount=10,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(json_formatter)
    root_logger.addHandler(file_handler)

    # Error file handler with rotation
    error_handler = logging.handlers.RotatingFileHandler(
        log_path / "xagent-errors.log",
        maxBytes=50 * 1024 * 1024,  # 50MB
        backupCount=5,
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(json_formatter)
    root_logger.addHandler(error_handler)

    # Syslog handler (if available)
    try:
        syslog_handler = logging.handlers.SysLogHandler(address="/dev/log")
        syslog_handler.setLevel(logging.WARNING)
        syslog_handler.setFormatter(json_formatter)
        root_logger.addHandler(syslog_handler)
    except (FileNotFoundError, OSError):
        # Syslog not available on this system
        pass

    # HTTP handler for remote logging (optional)
    if settings.log_remote_url:
        try:
            http_handler = logging.handlers.HTTPHandler(
                settings.log_remote_url,
                "/logs",
                method="POST",
            )
            http_handler.setLevel(logging.WARNING)
            http_handler.setFormatter(json_formatter)
            root_logger.addHandler(http_handler)
        except Exception as e:
            root_logger.warning(f"Failed to setup HTTP logging: {e}")

    # Configure specific loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)


class ContextFilter(logging.Filter):
    """Add context information to log records."""

    def __init__(self, context_provider: callable):
        super().__init__()
        self.context_provider = context_provider

    def filter(self, record: logging.LogRecord) -> bool:
        context = self.context_provider()
        if context:
            for key, value in context.items():
                setattr(record, key, value)
        return True


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)
