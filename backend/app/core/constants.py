"""Constants and enumerations for X-Agent core.

This module defines all constants, enumerations, and magic strings used
throughout the X-Agent core system. Centralizing these definitions improves
maintainability and reduces the risk of inconsistencies.

Usage:
    from backend.app.core.constants import ErrorType, ToolName, ExecutionState

    if error.type == ErrorType.VALIDATION_ERROR:
        handle_validation_error(error)
"""

from __future__ import annotations

from enum import StrEnum


class ErrorType(StrEnum):
    """Error types for tool execution and verification.

    Attributes:
        VALIDATION_ERROR: Input validation failed
        MISSING_RESOURCE: Required resource not found
        PATCH_MISMATCH: Patch application failed due to mismatch
        APPROVAL_REQUIRED: Action requires user approval
        PERMISSION_DENIED: User lacks required permissions
        TIMEOUT: Operation timed out
        RATE_LIMIT: Rate limit exceeded
        UNKNOWN: Unknown error type
    """

    VALIDATION_ERROR = "validation_error"
    MISSING_RESOURCE = "missing_resource"
    PATCH_MISMATCH = "patch_mismatch"
    APPROVAL_REQUIRED = "approval_required"
    PERMISSION_DENIED = "permission_denied"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    UNKNOWN = "unknown"


class ToolName(StrEnum):
    """Standard tool names used in the system.

    Attributes:
        READ_FILE: Read file contents
        WRITE_FILE: Write file contents
        APPLY_PATCH: Apply text patch to file
        SEARCH_TEXT: Search for text in files
        RUN_TESTS: Run test suite
        OBSERVE: Observe system state
        SUMMARIZE: Summarize information
    """

    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    APPLY_PATCH = "apply_text_patch"
    SEARCH_TEXT = "search_text"
    RUN_TESTS = "run_tests"
    OBSERVE = "observe"
    SUMMARIZE = "summarize_text"


class ExecutionState(StrEnum):
    """Agent execution states.

    Attributes:
        INITIALIZING: Initializing execution
        PLANNING: Planning phase
        EXECUTING: Executing plan
        RECOVERING: Recovery phase
        COMPLETING: Completing execution
        COMPLETED: Execution completed
        FAILED: Execution failed
    """

    INITIALIZING = "initializing"
    PLANNING = "planning"
    EXECUTING = "executing"
    RECOVERING = "recovering"
    COMPLETING = "completing"
    COMPLETED = "completed"
    FAILED = "failed"


class CapabilityName(StrEnum):
    """Capability names for routing.

    Attributes:
        APPROVAL: Approval capability
        BROWSER: Browser automation capability
        WORKFLOW: Workflow execution capability
        DESKTOP: Desktop automation capability
        CODE: Code execution capability
    """

    APPROVAL = "approval"
    BROWSER = "browser"
    WORKFLOW = "workflow"
    DESKTOP = "desktop"
    CODE = "code"


class TaskKeyword(StrEnum):
    """Keywords for task classification.

    Attributes:
        MODIFY: Task involves code modification
        SEARCH: Task involves searching
        TEST: Task involves testing
        SUMMARIZE: Task involves summarization
    """

    MODIFY = "modify"
    SEARCH = "search"
    TEST = "test"
    SUMMARIZE = "summarize"


# Confidence thresholds
CONFIDENCE_HIGH = 0.9
CONFIDENCE_MEDIUM = 0.7
CONFIDENCE_LOW = 0.5

# Retry limits
MAX_RETRIES = 3
BACKOFF_FACTOR = 2.0

# Timeout values (in seconds)
DEFAULT_TIMEOUT = 30
LONG_TIMEOUT = 300

# Default values
DEFAULT_CONFIDENCE = 0.5
DEFAULT_FOLLOW_UP_STEPS = ["continue planning", "execute selected tool"]
DEFAULT_RECOVERY_BRANCH = "continue"

# Task keywords for classification
MODIFY_KEYWORDS = {"fix", "patch", "edit", "write", "implement", "refactor", "update", "change"}
SEARCH_KEYWORDS = {"search", "find", "locate", "discover", "where"}
TEST_KEYWORDS = {"test", "verify", "validate", "check"}
SUMMARIZE_KEYWORDS = {"summarize", "report", "explain", "overview"}

# Error recovery strategies
ERROR_RECOVERY_STRATEGIES = {
    ErrorType.VALIDATION_ERROR: {
        "should_retry": True,
        "confidence": 0.92,
        "follow_up": ["rebuild arguments", "re-run validation"],
    },
    ErrorType.MISSING_RESOURCE: {
        "should_retry": True,
        "confidence": 0.88,
        "follow_up": ["refresh file context", "retry with discovered path"],
    },
    ErrorType.PATCH_MISMATCH: {
        "should_retry": True,
        "confidence": 0.86,
        "follow_up": ["re-read file", "reconstruct patch"],
    },
    ErrorType.APPROVAL_REQUIRED: {
        "should_retry": False,
        "confidence": 0.1,
        "follow_up": ["request approval", "pause execution"],
    },
    ErrorType.PERMISSION_DENIED: {
        "should_retry": False,
        "confidence": 0.1,
        "follow_up": ["request permission", "pause execution"],
    },
    ErrorType.TIMEOUT: {
        "should_retry": True,
        "confidence": 0.7,
        "follow_up": ["backoff and retry", "reduce scope if needed"],
    },
    ErrorType.RATE_LIMIT: {
        "should_retry": True,
        "confidence": 0.68,
        "follow_up": ["backoff", "retry later"],
    },
}
