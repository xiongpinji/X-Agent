"""
Failure detection module for X-Agent repair loop.

Implements automatic failure detection, classification, and context recording
for intelligent error recovery.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class FailureCategory(str, Enum):
    """Categories of failures."""

    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    ELEMENT_NOT_FOUND = "element_not_found"
    INVALID_INPUT = "invalid_input"
    PERMISSION_DENIED = "permission_denied"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    LOGIC_ERROR = "logic_error"
    EXTERNAL_SERVICE_ERROR = "external_service_error"
    UNKNOWN = "unknown"


class FailureSeverity(int, Enum):
    """Failure severity levels."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class ExecutionContext:
    """Context of execution when failure occurred."""

    task_id: str
    agent_id: str
    step_index: int
    action_type: str
    parameters: dict = field(default_factory=dict)
    environment: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class FailureRecord:
    """Record of a detected failure."""

    id: str
    category: FailureCategory
    severity: FailureSeverity
    message: str
    error_code: Optional[str] = None
    stack_trace: Optional[str] = None
    context: Optional[ExecutionContext] = None
    root_cause: Optional[str] = None
    suggestions: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    detected_at: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    resolution_time: Optional[float] = None


class FailureDetector:
    """
    Detects and classifies execution failures.

    Automatically identifies failures, categorizes them, and records
    context for intelligent recovery.
    """

    def __init__(self):
        """Initialize the failure detector."""
        self.logger = logger
        self.failure_patterns: dict[str, FailureCategory] = {
            "connection refused": FailureCategory.NETWORK_ERROR,
            "timeout": FailureCategory.TIMEOUT,
            "not found": FailureCategory.ELEMENT_NOT_FOUND,
            "permission denied": FailureCategory.PERMISSION_DENIED,
            "out of memory": FailureCategory.RESOURCE_EXHAUSTED,
            "invalid": FailureCategory.INVALID_INPUT,
        }
        self.failure_history: list[FailureRecord] = []

    def detect_failure(
        self,
        execution_result: dict,
        context: Optional[ExecutionContext] = None,
    ) -> Optional[FailureRecord]:
        """
        Detect if execution resulted in failure.

        Args:
            execution_result: Result of execution
            context: Execution context

        Returns:
            FailureRecord if failure detected, None otherwise
        """
        # Check for failure indicators
        if not self._is_failure(execution_result):
            return None

        # Extract failure information
        error_message = execution_result.get("error", "Unknown error")
        error_code = execution_result.get("error_code")
        stack_trace = execution_result.get("stack_trace")

        # Classify failure
        category = self.classify_failure_by_message(error_message)
        severity = self._determine_severity(category, error_message)

        # Create failure record
        failure_id = f"failure_{len(self.failure_history)}"
        failure = FailureRecord(
            id=failure_id,
            category=category,
            severity=severity,
            message=error_message,
            error_code=error_code,
            stack_trace=stack_trace,
            context=context,
        )

        # Analyze root cause
        failure.root_cause = self._analyze_root_cause(failure)

        # Generate suggestions
        failure.suggestions = self._generate_suggestions(failure)

        # Record failure
        self.failure_history.append(failure)

        self.logger.warning(
            f"Failure detected: {failure.category.value} - {failure.message}"
        )

        return failure

    def _is_failure(self, execution_result: dict) -> bool:
        """Check if execution result indicates failure."""
        if not isinstance(execution_result, dict):
            return False

        # Check for explicit failure indicators
        if execution_result.get("success") is False:
            return True

        if execution_result.get("error"):
            return True

        if execution_result.get("status") == "failed":
            return True

        return False

    def classify_failure_by_message(self, message: str) -> FailureCategory:
        """Classify failure based on error message."""
        message_lower = message.lower()

        # Check against known patterns
        for pattern, category in self.failure_patterns.items():
            if pattern in message_lower:
                return category

        # Default to unknown
        return FailureCategory.UNKNOWN

    def classify_failure(
        self,
        failure: FailureRecord,
    ) -> FailureCategory:
        """Classify a failure record."""
        # Try message-based classification first
        category = self.classify_failure_by_message(failure.message)

        if category != FailureCategory.UNKNOWN:
            return category

        # Try error code-based classification
        if failure.error_code:
            category = self._classify_by_error_code(failure.error_code)

        return category

    def _classify_by_error_code(self, error_code: str) -> FailureCategory:
        """Classify failure by error code."""
        error_code_lower = error_code.lower()

        if "timeout" in error_code_lower:
            return FailureCategory.TIMEOUT
        elif "404" in error_code_lower or "not_found" in error_code_lower:
            return FailureCategory.ELEMENT_NOT_FOUND
        elif "403" in error_code_lower or "401" in error_code_lower:
            return FailureCategory.PERMISSION_DENIED
        elif "503" in error_code_lower or "502" in error_code_lower:
            return FailureCategory.EXTERNAL_SERVICE_ERROR

        return FailureCategory.UNKNOWN

    def _determine_severity(
        self,
        category: FailureCategory,
        message: str,
    ) -> FailureSeverity:
        """Determine failure severity."""
        # Critical failures
        if category in (
            FailureCategory.PERMISSION_DENIED,
            FailureCategory.RESOURCE_EXHAUSTED,
        ):
            return FailureSeverity.CRITICAL

        # High severity failures
        if category in (
            FailureCategory.EXTERNAL_SERVICE_ERROR,
            FailureCategory.LOGIC_ERROR,
        ):
            return FailureSeverity.HIGH

        # Medium severity failures
        if category in (
            FailureCategory.TIMEOUT,
            FailureCategory.NETWORK_ERROR,
        ):
            return FailureSeverity.MEDIUM

        # Low severity failures
        if category in (
            FailureCategory.ELEMENT_NOT_FOUND,
            FailureCategory.INVALID_INPUT,
        ):
            return FailureSeverity.LOW

        return FailureSeverity.MEDIUM

    def _analyze_root_cause(self, failure: FailureRecord) -> str:
        """Analyze root cause of failure."""
        category = failure.category

        if category == FailureCategory.NETWORK_ERROR:
            return "Network connectivity issue or service unavailable"
        elif category == FailureCategory.TIMEOUT:
            return "Operation exceeded timeout threshold"
        elif category == FailureCategory.ELEMENT_NOT_FOUND:
            return "Target element not found in current state"
        elif category == FailureCategory.INVALID_INPUT:
            return "Invalid input parameters provided"
        elif category == FailureCategory.PERMISSION_DENIED:
            return "Insufficient permissions for operation"
        elif category == FailureCategory.RESOURCE_EXHAUSTED:
            return "System resources exhausted"
        elif category == FailureCategory.LOGIC_ERROR:
            return "Logic error in execution flow"
        elif category == FailureCategory.EXTERNAL_SERVICE_ERROR:
            return "External service error or unavailable"
        else:
            return "Unknown root cause"

    def _generate_suggestions(self, failure: FailureRecord) -> list[str]:
        """Generate recovery suggestions."""
        suggestions = []
        category = failure.category

        if category == FailureCategory.NETWORK_ERROR:
            suggestions = [
                "Retry operation with exponential backoff",
                "Check network connectivity",
                "Verify service availability",
            ]
        elif category == FailureCategory.TIMEOUT:
            suggestions = [
                "Increase timeout threshold",
                "Optimize operation performance",
                "Break operation into smaller steps",
            ]
        elif category == FailureCategory.ELEMENT_NOT_FOUND:
            suggestions = [
                "Wait for element to appear",
                "Try alternative locator strategies",
                "Refresh page and retry",
            ]
        elif category == FailureCategory.INVALID_INPUT:
            suggestions = [
                "Validate input parameters",
                "Check input format and constraints",
                "Use default values if available",
            ]
        elif category == FailureCategory.PERMISSION_DENIED:
            suggestions = [
                "Verify user permissions",
                "Authenticate with correct credentials",
                "Request elevated privileges if needed",
            ]
        elif category == FailureCategory.RESOURCE_EXHAUSTED:
            suggestions = [
                "Free up system resources",
                "Reduce operation scope",
                "Implement resource pooling",
            ]

        return suggestions

    def get_failure_stats(self) -> dict:
        """Get failure statistics."""
        if not self.failure_history:
            return {
                "total_failures": 0,
                "by_category": {},
                "by_severity": {},
            }

        by_category = {}
        by_severity = {}

        for failure in self.failure_history:
            # Count by category
            cat = failure.category.value
            by_category[cat] = by_category.get(cat, 0) + 1

            # Count by severity
            sev = failure.severity.name
            by_severity[sev] = by_severity.get(sev, 0) + 1

        return {
            "total_failures": len(self.failure_history),
            "resolved_failures": sum(1 for f in self.failure_history if f.resolved),
            "by_category": by_category,
            "by_severity": by_severity,
        }

    def get_recent_failures(self, limit: int = 10) -> list[FailureRecord]:
        """Get recent failures."""
        return self.failure_history[-limit:]

    def mark_resolved(self, failure_id: str, resolution_time: float) -> bool:
        """Mark a failure as resolved."""
        for failure in self.failure_history:
            if failure.id == failure_id:
                failure.resolved = True
                failure.resolution_time = resolution_time
                self.logger.debug(f"Marked failure {failure_id} as resolved")
                return True

        return False

    def export_failures(self) -> dict:
        """Export failure history."""
        return {
            "total_failures": len(self.failure_history),
            "failures": [
                {
                    "id": f.id,
                    "category": f.category.value,
                    "severity": f.severity.name,
                    "message": f.message,
                    "error_code": f.error_code,
                    "root_cause": f.root_cause,
                    "suggestions": f.suggestions,
                    "resolved": f.resolved,
                    "resolution_time": f.resolution_time,
                    "detected_at": f.detected_at.isoformat(),
                }
                for f in self.failure_history
            ],
        }


# Global instance
failure_detector = FailureDetector()
