"""Repair loop for handling tool execution failures and generating recovery suggestions.

This module provides the RepairLoop class which analyzes tool call failures and
generates repair suggestions using a strategy-based approach. It replaces nested
if-statements with a cleaner, more maintainable error handling strategy.

Usage:
    from backend.app.core.repair_loop import RepairLoop
    from backend.app.core.contracts import ToolCallRecord

    repair_loop = RepairLoop()
    result, suggestion = repair_loop.analyze(tool_call)
    if suggestion.should_retry:
        print(f"Retry with: {suggestion.tool_name}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.core.constants import (
    ERROR_RECOVERY_STRATEGIES,
    ErrorType,
    ToolName,
)
from backend.app.core.contracts import ToolCallRecord
from backend.app.core.verification import VerificationEngine, VerificationResult


@dataclass
class RepairSuggestion:
    """Suggestion for repairing a failed tool call.

    Attributes:
        should_retry: Whether the tool call should be retried
        tool_name: Name of the tool to retry with (may differ from original)
        arguments: Arguments for the retry tool
        reason: Human-readable reason for the suggestion
        error_type: Type of error that occurred
        confidence: Confidence level of the suggestion (0.0-1.0)
        follow_up: List of follow-up actions to consider
    """

    should_retry: bool
    tool_name: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    error_type: str | None = None
    confidence: float = 0.5
    follow_up: list[str] = field(default_factory=list)


class ErrorClassifier:
    """Classifies errors and determines recovery strategies.

    This class encapsulates error classification logic, making it easier
    to add new error types and recovery strategies.
    """

    @staticmethod
    def classify(error_type: str) -> ErrorType:
        """Classify error string to ErrorType enum.

        Args:
            error_type: Error type string

        Returns:
            Corresponding ErrorType enum value

        Raises:
            ValueError: If error type is not recognized
        """
        try:
            return ErrorType(error_type)
        except ValueError:
            return ErrorType.UNKNOWN

    @staticmethod
    def get_recovery_strategy(error_type: str) -> dict[str, Any]:
        """Get recovery strategy for error type.

        Args:
            error_type: Error type string

        Returns:
            Dictionary with recovery strategy configuration
        """
        classified = ErrorClassifier.classify(error_type)
        return ERROR_RECOVERY_STRATEGIES.get(
            classified,
            {
                "should_retry": True,
                "confidence": 0.58,
                "follow_up": ["re-read context", "retry carefully"],
            },
        )


class SuggestionGenerator:
    """Generates repair suggestions based on error type and context.

    This class encapsulates suggestion generation logic, making it easier
    to customize recovery behavior for different error types.
    """

    @staticmethod
    def generate(
        tool_call: ToolCallRecord,
        result: VerificationResult,
    ) -> RepairSuggestion:
        """Generate repair suggestion for failed tool call.

        Args:
            tool_call: The failed tool call record
            result: Verification result for the tool call

        Returns:
            RepairSuggestion with recovery strategy
        """
        error_type = result.error_type or ErrorType.UNKNOWN.value
        strategy = ErrorClassifier.get_recovery_strategy(error_type)

        # Get base suggestion from strategy
        should_retry = strategy.get("should_retry", True)
        confidence = strategy.get("confidence", 0.5)
        follow_up = strategy.get("follow_up", [])

        # Customize suggestion based on error type
        if error_type == ErrorType.VALIDATION_ERROR.value:
            return SuggestionGenerator._handle_validation_error(
                tool_call, should_retry, confidence, follow_up
            )
        elif error_type == ErrorType.MISSING_RESOURCE.value:
            return SuggestionGenerator._handle_missing_resource(
                tool_call, should_retry, confidence, follow_up
            )
        elif error_type == ErrorType.PATCH_MISMATCH.value:
            return SuggestionGenerator._handle_patch_mismatch(
                tool_call, should_retry, confidence, follow_up
            )
        elif error_type in {
            ErrorType.APPROVAL_REQUIRED.value,
            ErrorType.PERMISSION_DENIED.value,
        }:
            return SuggestionGenerator._handle_approval_or_permission(
                error_type, should_retry, confidence, follow_up
            )
        else:
            # Default suggestion for other error types
            return RepairSuggestion(
                should_retry=should_retry,
                tool_name=tool_call.tool_name,
                arguments=dict(tool_call.arguments_preview),
                reason=f"retry after {error_type}",
                error_type=error_type,
                confidence=confidence,
                follow_up=follow_up,
            )

    @staticmethod
    def _handle_validation_error(
        tool_call: ToolCallRecord,
        should_retry: bool,
        confidence: float,
        follow_up: list[str],
    ) -> RepairSuggestion:
        """Handle validation error suggestion."""
        return RepairSuggestion(
            should_retry=should_retry,
            tool_name=tool_call.tool_name,
            arguments=dict(tool_call.arguments_preview),
            reason="retry with corrected arguments",
            error_type=ErrorType.VALIDATION_ERROR.value,
            confidence=confidence,
            follow_up=follow_up,
        )

    @staticmethod
    def _handle_missing_resource(
        tool_call: ToolCallRecord,
        should_retry: bool,
        confidence: float,
        follow_up: list[str],
    ) -> RepairSuggestion:
        """Handle missing resource suggestion."""
        arguments = dict(tool_call.arguments_preview)
        retry_tool = (
            ToolName.READ_FILE.value
            if tool_call.tool_name != ToolName.READ_FILE.value
            else None
        )
        retry_arguments = {"path": arguments.get("path", ""), "limit": 8000}

        # Preserve content for patch/write operations
        if tool_call.tool_name in {
            ToolName.APPLY_PATCH.value,
            ToolName.WRITE_FILE.value,
        } and arguments.get("content"):
            retry_arguments["content"] = arguments.get("content", "")

        return RepairSuggestion(
            should_retry=should_retry,
            tool_name=retry_tool,
            arguments=retry_arguments,
            reason="re-read context before retrying",
            error_type=ErrorType.MISSING_RESOURCE.value,
            confidence=confidence,
            follow_up=follow_up,
        )

    @staticmethod
    def _handle_patch_mismatch(
        tool_call: ToolCallRecord,
        should_retry: bool,
        confidence: float,
        follow_up: list[str],
    ) -> RepairSuggestion:
        """Handle patch mismatch suggestion."""
        arguments = dict(tool_call.arguments_preview)
        retry_tool = (
            ToolName.READ_FILE.value
            if tool_call.tool_name != ToolName.READ_FILE.value
            else None
        )
        retry_arguments = {"path": arguments.get("path", ""), "limit": 8000}

        return RepairSuggestion(
            should_retry=should_retry,
            tool_name=retry_tool,
            arguments=retry_arguments,
            reason="refresh file context and rebuild the patch",
            error_type=ErrorType.PATCH_MISMATCH.value,
            confidence=confidence,
            follow_up=follow_up,
        )

    @staticmethod
    def _handle_approval_or_permission(
        error_type: str,
        should_retry: bool,
        confidence: float,
        follow_up: list[str],
    ) -> RepairSuggestion:
        """Handle approval required or permission denied suggestion."""
        reason = (
            "await approval or authorization before retrying"
            if error_type == ErrorType.APPROVAL_REQUIRED.value
            else "permission denied; manual intervention required"
        )

        return RepairSuggestion(
            should_retry=should_retry,
            reason=reason,
            error_type=error_type,
            confidence=confidence,
            follow_up=follow_up,
        )


class RepairLoop:
    """Generates repair suggestions from verification results.

    This class orchestrates error analysis and suggestion generation using
    a strategy-based approach. It replaces nested if-statements with cleaner,
    more maintainable error handling.

    Attributes:
        verifier: VerificationEngine for analyzing tool calls
    """

    def __init__(self, verifier: VerificationEngine | None = None) -> None:
        """Initialize RepairLoop.

        Args:
            verifier: Optional custom VerificationEngine. If None, uses default.
        """
        self.verifier = verifier or VerificationEngine()

    @staticmethod
    def _dump_model(value: Any) -> Any:
        """Convert model to dictionary representation.

        Handles various model types (Pydantic, dataclass, dict, etc.)
        and converts them to JSON-serializable dictionaries.

        Args:
            value: Value to convert

        Returns:
            Dictionary representation of the value
        """
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if hasattr(value, "dict"):
            return value.dict()
        if isinstance(value, dict):
            return value
        return getattr(value, "__dict__", value)

    def analyze(
        self, tool_call: ToolCallRecord
    ) -> tuple[VerificationResult, RepairSuggestion]:
        """Analyze tool call and generate repair suggestion.

        Verifies the tool call and generates a repair suggestion based on
        the verification result.

        Args:
            tool_call: The tool call record to analyze

        Returns:
            Tuple of (VerificationResult, RepairSuggestion)

        Example:
            >>> result, suggestion = repair_loop.analyze(tool_call)
            >>> if suggestion.should_retry:
            ...     print(f"Retry with: {suggestion.tool_name}")
        """
        result = self.verifier.verify_tool_call(tool_call)
        suggestion = SuggestionGenerator.generate(tool_call, result)
        return result, suggestion

    def summarize(self, tool_calls: list[ToolCallRecord]) -> dict[str, Any]:
        """Summarize repairs for multiple tool calls.

        Analyzes all failed tool calls and generates a summary of repairs
        and retry opportunities.

        Args:
            tool_calls: List of tool call records to analyze

        Returns:
            Dictionary with repair summary including:
                - repairs: List of repair suggestions
                - retry_count: Number of retryable failures
                - retryable_failures: Count of retryable failures

        Example:
            >>> summary = repair_loop.summarize(tool_calls)
            >>> print(f"Retryable failures: {summary['retry_count']}")
        """
        summary = self.verifier.summarize_run(tool_calls)
        summary["repairs"] = []
        summary["retry_count"] = 0
        summary["retryable_failures"] = 0

        for call in tool_calls:
            if call.success:
                continue

            result, suggestion = self.analyze(call)
            if suggestion.should_retry:
                summary["retryable_failures"] += 1

            summary["repairs"].append(
                {
                    "tool_name": call.tool_name,
                    "verification": self._dump_model(result),
                    "suggestion": {
                        "should_retry": suggestion.should_retry,
                        "tool_name": suggestion.tool_name,
                        "arguments": suggestion.arguments,
                        "reason": suggestion.reason,
                        "error_type": suggestion.error_type,
                        "confidence": suggestion.confidence,
                        "follow_up": suggestion.follow_up,
                    },
                }
            )

        summary["retry_count"] = summary["retryable_failures"]
        return summary
