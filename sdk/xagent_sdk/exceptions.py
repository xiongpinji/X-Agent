"""X-Agent SDK exception classes."""


class XAgentError(Exception):
    """Base exception for X-Agent SDK.

    All X-Agent SDK exceptions inherit from this class.
    """

    def __init__(self, message: str, code: str = "UNKNOWN", status_code: int = 500):
        """Initialize XAgentError.

        Args:
            message: Human-readable error message.
            code: Error code for programmatic handling.
            status_code: HTTP status code (if applicable).
        """
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class AuthenticationError(XAgentError):
    """Raised when authentication fails or is missing.

    Typically indicates invalid or missing API key, or expired credentials.
    """

    def __init__(self, message: str = "Authentication failed", code: str = "AUTH_ERROR"):
        super().__init__(message, code, status_code=401)


class AuthorizationError(XAgentError):
    """Raised when user lacks permission for requested operation.

    Indicates valid authentication but insufficient privileges.
    """

    def __init__(self, message: str = "Insufficient permissions", code: str = "AUTHZ_ERROR"):
        super().__init__(message, code, status_code=403)


class ValidationError(XAgentError):
    """Raised when request validation fails.

    Indicates malformed request data, invalid parameters, or schema violations.
    """

    def __init__(self, message: str = "Validation failed", code: str = "VALIDATION_ERROR"):
        super().__init__(message, code, status_code=400)


class TaskTimeoutError(XAgentError):
    """Raised when a task execution times out.

    Indicates task did not complete within specified time limit.
    """

    def __init__(
        self, message: str = "Task execution timed out", code: str = "TASK_TIMEOUT"
    ):
        super().__init__(message, code, status_code=408)


class TaskNotFoundError(XAgentError):
    """Raised when a task cannot be found.

    Indicates the task_id does not correspond to a known task.
    """

    def __init__(self, task_id: str, code: str = "TASK_NOT_FOUND"):
        message = f"Task not found: {task_id}"
        super().__init__(message, code, status_code=404)


class TaskCancelledError(XAgentError):
    """Raised when attempting to access a cancelled task."""

    def __init__(
        self, task_id: str, code: str = "TASK_CANCELLED"
    ):
        message = f"Task was cancelled: {task_id}"
        super().__init__(message, code, status_code=410)


class ServerError(XAgentError):
    """Raised when server returns a 5xx error.

    Indicates an internal server error or service failure.
    """

    def __init__(
        self, message: str = "Internal server error", code: str = "SERVER_ERROR", status_code: int = 500
    ):
        super().__init__(message, code, status_code)


class ServiceUnavailableError(ServerError):
    """Raised when the service is temporarily unavailable."""

    def __init__(
        self, message: str = "Service temporarily unavailable", code: str = "SERVICE_UNAVAILABLE"
    ):
        super().__init__(message, code, status_code=503)


class RateLimitError(XAgentError):
    """Raised when rate limit is exceeded.

    Indicates too many requests; client should retry with exponential backoff.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        code: str = "RATE_LIMIT",
        retry_after: int = 60,
    ):
        super().__init__(message, code, status_code=429)
        self.retry_after = retry_after


class ConnectionError(XAgentError):
    """Raised when connection to server cannot be established."""

    def __init__(self, message: str = "Connection failed", code: str = "CONNECTION_ERROR"):
        super().__init__(message, code, status_code=0)


class TimeoutError(XAgentError):
    """Raised when an operation times out at the transport level."""

    def __init__(self, message: str = "Operation timed out", code: str = "TIMEOUT"):
        super().__init__(message, code, status_code=0)
