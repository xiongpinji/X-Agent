"""
Unified exception hierarchy for X-Agent.

Provides a comprehensive exception system with:
- Hierarchical exception structure
- Business, system, network, and resource exceptions
- Error codes and context information
- Structured error details
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Standard error codes."""

    # Business errors
    BUSINESS_LOGIC_ERROR = "business_logic_error"
    INVALID_STATE = "invalid_state"
    OPERATION_NOT_ALLOWED = "operation_not_allowed"
    RESOURCE_EXHAUSTED = "resource_exhausted"

    # System errors
    INTERNAL_ERROR = "internal_error"
    NOT_IMPLEMENTED = "not_implemented"
    CONFIGURATION_ERROR = "configuration_error"
    INITIALIZATION_ERROR = "initialization_error"

    # Network errors
    CONNECTION_ERROR = "connection_error"
    TIMEOUT_ERROR = "timeout_error"
    SERVICE_UNAVAILABLE = "service_unavailable"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"

    # Resource errors
    RESOURCE_NOT_FOUND = "resource_not_found"
    RESOURCE_ALREADY_EXISTS = "resource_already_exists"
    RESOURCE_CONFLICT = "resource_conflict"
    INSUFFICIENT_RESOURCES = "insufficient_resources"

    # Validation errors
    VALIDATION_ERROR = "validation_error"
    INVALID_INPUT = "invalid_input"
    INVALID_FORMAT = "invalid_format"

    # Authentication/Authorization
    AUTHENTICATION_FAILED = "authentication_failed"
    AUTHORIZATION_FAILED = "authorization_failed"
    PERMISSION_DENIED = "permission_denied"


class ErrorSeverity(StrEnum):
    """Error severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class ErrorContext:
    """Context information for an error."""

    error_code: ErrorCode
    message: str
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    timestamp: float = field(default_factory=time.time)
    error_id: str = field(default_factory=lambda: f"err_{int(time.time() * 1000)}")
    details: dict[str, Any] = field(default_factory=dict)
    user_id: str | None = None
    tenant_id: str | None = None
    correlation_id: str | None = None
    trace_id: str | None = None
    stack_trace: str | None = None
    retry_count: int = 0
    is_retryable: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "severity": self.severity.value,
            "error_id": self.error_id,
            "timestamp": self.timestamp,
            "details": self.details,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "retry_count": self.retry_count,
            "is_retryable": self.is_retryable,
        }


class XAgentException(Exception):
    """Base exception for X-Agent."""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        details: dict[str, Any] | None = None,
        is_retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.severity = severity
        self.details = details or {}
        self.is_retryable = is_retryable
        self.timestamp = time.time()
        self.error_id = f"err_{int(self.timestamp * 1000)}"

    def to_context(
        self,
        user_id: str | None = None,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
        trace_id: str | None = None,
    ) -> ErrorContext:
        """Convert to error context."""
        return ErrorContext(
            error_code=self.error_code,
            message=self.message,
            severity=self.severity,
            error_id=self.error_id,
            timestamp=self.timestamp,
            details=self.details,
            user_id=user_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            trace_id=trace_id,
            is_retryable=self.is_retryable,
        )


# Business Exceptions
class BusinessError(XAgentException):
    """Business logic error."""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.BUSINESS_LOGIC_ERROR,
        **kwargs,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            severity=ErrorSeverity.MEDIUM,
            **kwargs,
        )


class InvalidStateError(BusinessError):
    """Invalid state error."""

    def __init__(self, message: str = "Invalid state", **kwargs) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.INVALID_STATE,
            **kwargs,
        )


class OperationNotAllowedError(BusinessError):
    """Operation not allowed."""

    def __init__(self, message: str = "Operation not allowed", **kwargs) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.OPERATION_NOT_ALLOWED,
            **kwargs,
        )


class ResourceExhaustedError(BusinessError):
    """Resource exhausted."""

    def __init__(self, message: str = "Resource exhausted", **kwargs) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.RESOURCE_EXHAUSTED,
            is_retryable=True,
            **kwargs,
        )


# System Exceptions
class SystemError(XAgentException):
    """System error."""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        **kwargs,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            severity=ErrorSeverity.HIGH,
            **kwargs,
        )


class NotImplementedError(SystemError):
    """Not implemented."""

    def __init__(self, message: str = "Not implemented", **kwargs) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.NOT_IMPLEMENTED,
            **kwargs,
        )


class ConfigurationError(SystemError):
    """Configuration error."""

    def __init__(self, message: str = "Configuration error", **kwargs) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.CONFIGURATION_ERROR,
            **kwargs,
        )


class InitializationError(SystemError):
    """Initialization error."""

    def __init__(self, message: str = "Initialization error", **kwargs) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.INITIALIZATION_ERROR,
            **kwargs,
        )


# Network Exceptions
class NetworkError(XAgentException):
    """Network error."""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.CONNECTION_ERROR,
        severity: ErrorSeverity = ErrorSeverity.HIGH,
        **kwargs,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            severity=severity,
            is_retryable=True,
            **kwargs,
        )


class ConnectionError(NetworkError):
    """Connection error."""

    def __init__(self, message: str = "Connection error", **kwargs) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.CONNECTION_ERROR,
            **kwargs,
        )


class TimeoutError(NetworkError):
    """Timeout error."""

    def __init__(self, message: str = "Operation timeout", **kwargs) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.TIMEOUT_ERROR,
            **kwargs,
        )


class ServiceUnavailableError(NetworkError):
    """Service unavailable."""

    def __init__(self, message: str = "Service unavailable", **kwargs) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.SERVICE_UNAVAILABLE,
            **kwargs,
        )


class RateLimitError(NetworkError):
    """Rate limit exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", **kwargs) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            severity=ErrorSeverity.MEDIUM,
            **kwargs,
        )


# Resource Exceptions
class ResourceError(XAgentException):
    """Resource error."""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.RESOURCE_NOT_FOUND,
        **kwargs,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            severity=ErrorSeverity.MEDIUM,
            **kwargs,
        )


class NotFoundError(ResourceError):
    """Resource not found."""

    def __init__(self, message: str = "Resource not found", **kwargs) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
            **kwargs,
        )


class AlreadyExistsError(ResourceError):
    """Resource already exists."""

    def __init__(self, message: str = "Resource already exists", **kwargs) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.RESOURCE_ALREADY_EXISTS,
            **kwargs,
        )


class ConflictError(ResourceError):
    """Resource conflict."""

    def __init__(self, message: str = "Resource conflict", **kwargs) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.RESOURCE_CONFLICT,
            **kwargs,
        )


class InsufficientResourcesError(ResourceError):
    """Insufficient resources."""

    def __init__(self, message: str = "Insufficient resources", **kwargs) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.INSUFFICIENT_RESOURCES,
            is_retryable=True,
            **kwargs,
        )


# Validation Exceptions
class ValidationError(XAgentException):
    """Validation error."""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.VALIDATION_ERROR,
        **kwargs,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            severity=ErrorSeverity.LOW,
            **kwargs,
        )


class InvalidInputError(ValidationError):
    """Invalid input."""

    def __init__(self, message: str = "Invalid input", **kwargs) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.INVALID_INPUT,
            **kwargs,
        )


class InvalidFormatError(ValidationError):
    """Invalid format."""

    def __init__(self, message: str = "Invalid format", **kwargs) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.INVALID_FORMAT,
            **kwargs,
        )


# Authentication/Authorization Exceptions
class AuthenticationError(XAgentException):
    """Authentication error."""

    def __init__(self, message: str = "Authentication failed", **kwargs) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.AUTHENTICATION_FAILED,
            severity=ErrorSeverity.HIGH,
            **kwargs,
        )


class AuthorizationError(XAgentException):
    """Authorization error."""

    def __init__(self, message: str = "Authorization failed", **kwargs) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.AUTHORIZATION_FAILED,
            severity=ErrorSeverity.HIGH,
            **kwargs,
        )


class PermissionDeniedError(XAgentException):
    """Permission denied."""

    def __init__(self, message: str = "Permission denied", **kwargs) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.PERMISSION_DENIED,
            severity=ErrorSeverity.HIGH,
            **kwargs,
        )
