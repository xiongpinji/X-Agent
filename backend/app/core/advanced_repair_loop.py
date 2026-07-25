"""Advanced repair loop with learning and compensation mechanisms."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from backend.app.core.verification import VerificationEngine


class RepairStrategy(StrEnum):
    """Strategies for repairing failures."""
    RETRY = "retry"
    FALLBACK = "fallback"
    COMPENSATE = "compensate"
    ESCALATE = "escalate"


class FailureCategory(StrEnum):
    """Categories of failures."""
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    RESOURCE = "resource"
    TIMEOUT = "timeout"
    VALIDATION = "validation"


@dataclass
class FailureRecord:
    """Record of a failure."""
    id: str
    error_message: str
    error_type: str
    category: FailureCategory
    timestamp: float = 0.0
    context: dict[str, Any] = field(default_factory=dict)
    recovery_attempted: bool = False
    recovery_successful: bool = False


@dataclass
class RepairSuggestion:
    """Suggestion for repairing a failure."""
    strategy: RepairStrategy
    confidence: float = 0.5
    reason: str = ""
    follow_up: list[str] = field(default_factory=list)
    estimated_success_rate: float = 0.5
    compensation_actions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class LearningRecord:
    """Record of learned repair patterns."""
    error_pattern: str
    successful_strategies: list[RepairStrategy] = field(default_factory=list)
    success_rate: float = 0.0
    failure_count: int = 0
    success_count: int = 0
    last_updated: float = 0.0


class AdvancedRepairLoop:
    """Advanced repair loop with learning and compensation."""

    def __init__(
        self,
        verification_engine: VerificationEngine | None = None,
        max_retries: int = 3,
        learning_enabled: bool = True,
    ):
        """Initialize advanced repair loop.

        Args:
            verification_engine: Engine for verification
            max_retries: Maximum retry attempts
            learning_enabled: Enable learning from repairs
        """
        self.verification_engine = verification_engine or VerificationEngine()
        self.max_retries = max_retries
        self.learning_enabled = learning_enabled
        self._failure_history: dict[str, FailureRecord] = {}
        self._learning_records: dict[str, LearningRecord] = {}
        self._repair_handlers: dict[FailureCategory, Callable] = {}
        self._compensation_handlers: dict[str, Callable] = {}

    async def analyze_failure(
        self,
        error: Exception,
        context: dict[str, Any] | None = None,
    ) -> FailureRecord:
        """Analyze a failure and categorize it.

        Args:
            error: Exception that occurred
            context: Context information

        Returns:
            Failure record
        """
        error_message = str(error)
        error_type = type(error).__name__

        # Categorize failure
        category = self._categorize_failure(error_type, error_message)

        failure = FailureRecord(
            id=f"failure_{len(self._failure_history)}",
            error_message=error_message,
            error_type=error_type,
            category=category,
            context=context or {},
        )

        self._failure_history[failure.id] = failure
        return failure

    async def suggest_repair(
        self,
        failure: FailureRecord,
    ) -> RepairSuggestion:
        """Suggest a repair strategy for a failure.

        Args:
            failure: Failure record

        Returns:
            Repair suggestion
        """
        # Check learning records
        if self.learning_enabled:
            error_pattern = f"{failure.error_type}:{failure.category.value}"
            learning = self._learning_records.get(error_pattern)
            if learning and learning.successful_strategies:
                best_strategy = max(
                    learning.successful_strategies,
                    key=lambda s: self._get_strategy_success_rate(learning, s),
                )
                return RepairSuggestion(
                    strategy=best_strategy,
                    confidence=learning.success_rate,
                    reason=f"Based on {learning.success_count} successful repairs",
                    follow_up=self._get_follow_up_actions(best_strategy),
                    estimated_success_rate=learning.success_rate,
                )

        # Default suggestions based on category
        if failure.category == FailureCategory.TRANSIENT:
            return RepairSuggestion(
                strategy=RepairStrategy.RETRY,
                confidence=0.8,
                reason="Transient failures often succeed on retry",
                follow_up=["retry with exponential backoff", "check system resources"],
                estimated_success_rate=0.8,
            )
        elif failure.category == FailureCategory.TIMEOUT:
            return RepairSuggestion(
                strategy=RepairStrategy.RETRY,
                confidence=0.6,
                reason="Timeout may be resolved with increased timeout",
                follow_up=["increase timeout", "check network connectivity"],
                estimated_success_rate=0.6,
            )
        elif failure.category == FailureCategory.RESOURCE:
            return RepairSuggestion(
                strategy=RepairStrategy.COMPENSATE,
                confidence=0.7,
                reason="Resource exhaustion requires compensation",
                follow_up=["free resources", "use fallback resources"],
                estimated_success_rate=0.7,
                compensation_actions=[
                    {"action": "cleanup", "target": "temporary_files"},
                    {"action": "reduce_load", "target": "concurrent_operations"},
                ],
            )
        elif failure.category == FailureCategory.VALIDATION:
            return RepairSuggestion(
                strategy=RepairStrategy.FALLBACK,
                confidence=0.5,
                reason="Validation failures may need alternative approach",
                follow_up=["use alternative method", "adjust parameters"],
                estimated_success_rate=0.5,
            )
        else:
            return RepairSuggestion(
                strategy=RepairStrategy.ESCALATE,
                confidence=0.3,
                reason="Permanent failures require escalation",
                follow_up=["log error", "notify administrator"],
                estimated_success_rate=0.3,
            )

    async def execute_repair(
        self,
        failure: FailureRecord,
        suggestion: RepairSuggestion,
        operation: Callable,
        *args,
        **kwargs,
    ) -> tuple[bool, Any]:
        """Execute a repair strategy.

        Args:
            failure: Failure record
            suggestion: Repair suggestion
            operation: Operation to retry
            *args: Operation arguments
            **kwargs: Operation keyword arguments

        Returns:
            Tuple of (success, result)
        """
        if suggestion.strategy == RepairStrategy.RETRY:
            return await self._execute_retry(failure, operation, *args, **kwargs)
        elif suggestion.strategy == RepairStrategy.FALLBACK:
            return await self._execute_fallback(failure, operation, *args, **kwargs)
        elif suggestion.strategy == RepairStrategy.COMPENSATE:
            return await self._execute_compensation(
                failure,
                suggestion,
                operation,
                *args,
                **kwargs,
            )
        elif suggestion.strategy == RepairStrategy.ESCALATE:
            return await self._execute_escalation(failure, suggestion)

        return False, None

    async def _execute_retry(
        self,
        failure: FailureRecord,
        operation: Callable,
        *args,
        **kwargs,
    ) -> tuple[bool, Any]:
        """Execute retry strategy.

        Args:
            failure: Failure record
            operation: Operation to retry
            *args: Operation arguments
            **kwargs: Operation keyword arguments

        Returns:
            Tuple of (success, result)
        """
        for attempt in range(self.max_retries):
            try:
                # Exponential backoff
                if attempt > 0:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)

                result = operation(*args, **kwargs)
                if inspect.iscoroutine(result):
                    result = await result

                failure.recovery_attempted = True
                failure.recovery_successful = True

                # Update learning
                if self.learning_enabled:
                    await self._update_learning(
                        failure,
                        RepairStrategy.RETRY,
                        True,
                    )

                return True, result
            except Exception:
                if attempt == self.max_retries - 1:
                    failure.recovery_attempted = True
                    failure.recovery_successful = False
                    return False, None

        return False, None

    async def _execute_fallback(
        self,
        failure: FailureRecord,
        operation: Callable,
        *args,
        **kwargs,
    ) -> tuple[bool, Any]:
        """Execute fallback strategy.

        Args:
            failure: Failure record
            operation: Operation to retry
            *args: Operation arguments
            **kwargs: Operation keyword arguments

        Returns:
            Tuple of (success, result)
        """
        # Try alternative approaches
        fallback_operations = kwargs.pop("fallback_operations", [])

        for fallback_op in fallback_operations:
            try:
                result = fallback_op(*args, **kwargs)
                if inspect.iscoroutine(result):
                    result = await result

                failure.recovery_attempted = True
                failure.recovery_successful = True

                if self.learning_enabled:
                    await self._update_learning(
                        failure,
                        RepairStrategy.FALLBACK,
                        True,
                    )

                return True, result
            except Exception:
                continue

        failure.recovery_attempted = True
        failure.recovery_successful = False
        return False, None

    async def _execute_compensation(
        self,
        failure: FailureRecord,
        suggestion: RepairSuggestion,
        operation: Callable,
        *args,
        **kwargs,
    ) -> tuple[bool, Any]:
        """Execute compensation strategy.

        Args:
            failure: Failure record
            suggestion: Repair suggestion
            operation: Operation to retry
            *args: Operation arguments
            **kwargs: Operation keyword arguments

        Returns:
            Tuple of (success, result)
        """
        # Execute compensation actions
        for action in suggestion.compensation_actions:
            handler = self._compensation_handlers.get(action.get("action"))
            if handler:
                try:
                    await handler(action)
                except Exception as e:
                    print(f"Compensation action failed: {e}")

        # Retry operation
        try:
            result = operation(*args, **kwargs)
            if inspect.iscoroutine(result):
                result = await result

            failure.recovery_attempted = True
            failure.recovery_successful = True

            if self.learning_enabled:
                await self._update_learning(
                    failure,
                    RepairStrategy.COMPENSATE,
                    True,
                )

            return True, result
        except Exception:
            failure.recovery_attempted = True
            failure.recovery_successful = False
            return False, None

    async def _execute_escalation(
        self,
        failure: FailureRecord,
        suggestion: RepairSuggestion,
    ) -> tuple[bool, Any]:
        """Execute escalation strategy.

        Args:
            failure: Failure record
            suggestion: Repair suggestion

        Returns:
            Tuple of (success, result)
        """
        failure.recovery_attempted = True
        failure.recovery_successful = False

        # Log escalation
        print(f"Escalating failure: {failure.error_message}")
        print(f"Reason: {suggestion.reason}")
        print(f"Follow-up actions: {suggestion.follow_up}")

        return False, None

    def _categorize_failure(
        self,
        error_type: str,
        error_message: str,
    ) -> FailureCategory:
        """Categorize a failure.

        Args:
            error_type: Type of error
            error_message: Error message

        Returns:
            Failure category
        """
        if "timeout" in error_message.lower() or error_type == "TimeoutError":
            return FailureCategory.TIMEOUT
        elif "resource" in error_message.lower() or "memory" in error_message.lower():
            return FailureCategory.RESOURCE
        elif "validation" in error_message.lower():
            return FailureCategory.VALIDATION
        elif error_type in ("ConnectionError", "IOError"):
            return FailureCategory.TRANSIENT
        else:
            return FailureCategory.PERMANENT

    def _get_follow_up_actions(self, strategy: RepairStrategy) -> list[str]:
        """Get follow-up actions for a strategy.

        Args:
            strategy: Repair strategy

        Returns:
            List of follow-up actions
        """
        if strategy == RepairStrategy.RETRY:
            return ["monitor retry progress", "check system health"]
        elif strategy == RepairStrategy.FALLBACK:
            return ["verify fallback result", "log fallback usage"]
        elif strategy == RepairStrategy.COMPENSATE:
            return ["verify compensation", "monitor resources"]
        else:
            return ["log error", "notify administrator"]

    def _get_strategy_success_rate(
        self,
        learning: LearningRecord,
        strategy: RepairStrategy,
    ) -> float:
        """Get success rate for a strategy.

        Args:
            learning: Learning record
            strategy: Repair strategy

        Returns:
            Success rate (0-1)
        """
        if strategy in learning.successful_strategies:
            return learning.success_rate
        return 0.0

    async def _update_learning(
        self,
        failure: FailureRecord,
        strategy: RepairStrategy,
        success: bool,
    ) -> None:
        """Update learning records.

        Args:
            failure: Failure record
            strategy: Repair strategy
            success: Whether repair was successful
        """
        error_pattern = f"{failure.error_type}:{failure.category.value}"

        if error_pattern not in self._learning_records:
            self._learning_records[error_pattern] = LearningRecord(
                error_pattern=error_pattern,
            )

        learning = self._learning_records[error_pattern]

        if success:
            learning.success_count += 1
            if strategy not in learning.successful_strategies:
                learning.successful_strategies.append(strategy)
        else:
            learning.failure_count += 1

        # Update success rate
        total = learning.success_count + learning.failure_count
        learning.success_rate = learning.success_count / total if total > 0 else 0.0

    def register_compensation_handler(
        self,
        action: str,
        handler: Callable,
    ) -> None:
        """Register a compensation handler.

        Args:
            action: Action type
            handler: Handler function
        """
        self._compensation_handlers[action] = handler

    def get_learning_stats(self) -> dict[str, Any]:
        """Get learning statistics.

        Returns:
            Dictionary with learning statistics
        """
        if not self._learning_records:
            return {
                "total_patterns": 0,
                "avg_success_rate": 0.0,
            }

        success_rates = [r.success_rate for r in self._learning_records.values()]
        return {
            "total_patterns": len(self._learning_records),
            "avg_success_rate": sum(success_rates) / len(success_rates),
            "total_repairs": sum(r.success_count + r.failure_count for r in self._learning_records.values()),
        }


# Global instance
advanced_repair_loop = AdvancedRepairLoop()
