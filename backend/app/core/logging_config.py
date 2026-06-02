import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict
from pythonjsonlogger import jsonlogger
import structlog
from pythonjsonlogger.jsonlogger import JsonFormatter


class StructuredFormatter(JsonFormatter):
    """Custom JSON formatter for structured logging."""

    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
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

    def _mask_sensitive_fields(self, log_record: Dict[str, Any]) -> None:
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


def setup_logging(app_name: str, log_level: str = 'INFO', log_file: str = None) -> None:
    """Configure structured logging for the application."""

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt='iso'),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Console handler with JSON formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = StructuredFormatter(
        fmt='%(timestamp)s %(level)s %(logger)s %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler with rotation
    if log_file:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,  # 100MB
            backupCount=10
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(console_formatter)
        root_logger.addHandler(file_handler)

    # Suppress noisy loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)


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
