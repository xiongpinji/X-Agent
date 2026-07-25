"""Log sanitization utilities for removing sensitive information from logs.

SECURITY: Prevents accidental exposure of sensitive data in logs.
"""

import re


class LogSanitizer:
    """Sanitizes logs to remove sensitive information."""

    # Patterns for sensitive data
    SENSITIVE_PATTERNS = {
        "api_key": r"(xag_[a-zA-Z0-9_-]{32,})",
        "password": r"(password['\"]?\s*[:=]\s*['\"]?)([^'\"]+)(['\"]?)",
        "token": r"(token['\"]?\s*[:=]\s*['\"]?)([^'\"]+)(['\"]?)",
        "bearer": r"(Bearer\s+)([a-zA-Z0-9_-]+)",
        "email": r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
        "credit_card": r"(\d{4}[\s-]?){3}\d{4}",
        "ssn": r"\d{3}-\d{2}-\d{4}",
        "jwt": r"(eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+)",
    }

    # Fields that should be redacted
    SENSITIVE_FIELDS = {
        "password",
        "password_hash",
        "api_key",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "x-api-key",
        "private_key",
        "encryption_key",
        "jwt_secret",
    }

    @classmethod
    def sanitize_string(cls, text: str) -> str:
        """Sanitize a string by removing sensitive patterns.

        Args:
            text: Text to sanitize

        Returns:
            Sanitized text with sensitive data redacted
        """
        if not isinstance(text, str):
            return str(text)

        result = text

        # Apply pattern-based redaction
        for pattern_name, pattern in cls.SENSITIVE_PATTERNS.items():
            if pattern_name == "password":
                # Special handling for password pattern
                result = re.sub(
                    pattern,
                    r"\1***REDACTED***\3",
                    result,
                    flags=re.IGNORECASE,
                )
            elif pattern_name == "bearer":
                result = re.sub(
                    pattern,
                    r"\1***REDACTED***",
                    result,
                    flags=re.IGNORECASE,
                )
            else:
                result = re.sub(
                    pattern,
                    "***REDACTED***",
                    result,
                    flags=re.IGNORECASE,
                )

        return result

    @classmethod
    def sanitize_dict(cls, data: dict, depth: int = 0, max_depth: int = 10) -> dict:
        """Sanitize a dictionary by redacting sensitive fields.

        Args:
            data: Dictionary to sanitize
            depth: Current recursion depth
            max_depth: Maximum recursion depth

        Returns:
            Sanitized dictionary
        """
        if depth > max_depth:
            return data

        result = {}

        for key, value in data.items():
            # Check if field name is sensitive
            if key.lower() in cls.SENSITIVE_FIELDS:
                result[key] = "***REDACTED***"
            elif isinstance(value, dict):
                result[key] = cls.sanitize_dict(value, depth + 1, max_depth)
            elif isinstance(value, list):
                result[key] = [
                    cls.sanitize_dict(item, depth + 1, max_depth) if isinstance(item, dict)
                    else cls.sanitize_string(str(item)) if isinstance(item, str)
                    else item
                    for item in value
                ]
            elif isinstance(value, str):
                result[key] = cls.sanitize_string(value)
            else:
                result[key] = value

        return result

    @classmethod
    def sanitize_headers(cls, headers: dict) -> dict:
        """Sanitize HTTP headers.

        Args:
            headers: Headers dictionary

        Returns:
            Sanitized headers
        """
        result = {}

        for key, value in headers.items():
            if key.lower() in {"authorization", "x-api-key", "cookie"}:
                result[key] = "***REDACTED***"
            else:
                result[key] = value

        return result

    @classmethod
    def sanitize_url(cls, url: str) -> str:
        """Sanitize URL by removing sensitive query parameters.

        Args:
            url: URL to sanitize

        Returns:
            Sanitized URL
        """
        # Remove common sensitive query parameters
        sensitive_params = {"api_key", "token", "password", "secret", "key"}

        result = url
        for param in sensitive_params:
            # Match parameter and its value
            pattern = rf"([?&]){param}=[^&]*"
            result = re.sub(pattern, rf"\1{param}=***REDACTED***", result, flags=re.IGNORECASE)

        return result


class LogFilter:
    """Logging filter that sanitizes log records."""

    def __init__(self):
        """Initialize log filter."""
        self.sanitizer = LogSanitizer()

    def filter(self, record) -> bool:
        """Filter and sanitize log record.

        Args:
            record: Log record to filter

        Returns:
            True to allow record, False to reject
        """
        # Sanitize message
        if hasattr(record, "msg") and isinstance(record.msg, str):
            record.msg = self.sanitizer.sanitize_string(record.msg)

        # Sanitize args
        if hasattr(record, "args"):
            if isinstance(record.args, dict):
                record.args = self.sanitizer.sanitize_dict(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self.sanitizer.sanitize_string(str(arg)) if isinstance(arg, str) else arg
                    for arg in record.args
                )

        return True


def get_log_filter() -> LogFilter:
    """Get log filter instance.

    Returns:
        LogFilter instance
    """
    return LogFilter()
