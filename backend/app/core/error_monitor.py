"""
Error monitoring and metrics collection.

Tracks:
- Error rates and frequencies
- Error categorization
- Retry success rates
- Degradation triggers
- Performance metrics
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from backend.app.core.exceptions import ErrorCode, ErrorSeverity, XAgentException

logger = logging.getLogger(__name__)


@dataclass
class ErrorMetric:
    """Error metric."""

    error_code: ErrorCode
    severity: ErrorSeverity
    count: int = 0
    first_occurrence: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_occurrence: datetime = field(default_factory=lambda: datetime.now(UTC))
    total_duration: float = 0.0
    avg_duration: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "error_code": self.error_code.value,
            "severity": self.severity.value,
            "count": self.count,
            "first_occurrence": self.first_occurrence.isoformat(),
            "last_occurrence": self.last_occurrence.isoformat(),
            "avg_duration": self.avg_duration,
        }


@dataclass
class RetryMetric:
    """Retry metric."""

    total_attempts: int = 0
    successful_retries: int = 0
    failed_retries: int = 0
    avg_retry_count: float = 0.0
    success_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_attempts": self.total_attempts,
            "successful_retries": self.successful_retries,
            "failed_retries": self.failed_retries,
            "avg_retry_count": self.avg_retry_count,
            "success_rate": self.success_rate,
        }


@dataclass
class DegradationMetric:
    """Degradation metric."""

    trigger_count: int = 0
    total_duration: float = 0.0
    last_trigger: datetime | None = None
    degradation_level: str = "full_service"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "trigger_count": self.trigger_count,
            "total_duration": self.total_duration,
            "last_trigger": self.last_trigger.isoformat() if self.last_trigger else None,
            "degradation_level": self.degradation_level,
        }


class ErrorMonitor:
    """Monitor and track errors."""

    def __init__(self, max_history: int = 10000) -> None:
        self.max_history = max_history
        self._errors: list[XAgentException] = []
        self._error_metrics: dict[str, ErrorMetric] = {}
        self._retry_metrics = RetryMetric()
        self._degradation_metrics = DegradationMetric()
        self._lock = asyncio.Lock()

    async def record_error(
        self,
        error: XAgentException | Exception,
        duration: float = 0.0,
    ) -> None:
        """Record an error."""
        async with self._lock:
            # Store error
            if isinstance(error, XAgentException):
                self._errors.append(error)
            else:
                # Convert to XAgentException
                xagent_error = XAgentException(
                    str(error),
                    error_code=ErrorCode.INTERNAL_ERROR,
                )
                self._errors.append(xagent_error)

            # Trim history
            if len(self._errors) > self.max_history:
                self._errors = self._errors[-self.max_history :]

            # Update metrics
            if isinstance(error, XAgentException):
                key = f"{error.error_code.value}:{error.severity.value}"
                if key not in self._error_metrics:
                    self._error_metrics[key] = ErrorMetric(
                        error_code=error.error_code,
                        severity=error.severity,
                    )

                metric = self._error_metrics[key]
                metric.count += 1
                metric.last_occurrence = datetime.now(UTC)
                metric.total_duration += duration
                metric.avg_duration = metric.total_duration / metric.count

    async def record_retry(
        self,
        success: bool,
        retry_count: int = 1,
    ) -> None:
        """Record a retry attempt."""
        async with self._lock:
            self._retry_metrics.total_attempts += 1

            if success:
                self._retry_metrics.successful_retries += 1
            else:
                self._retry_metrics.failed_retries += 1

            total = (
                self._retry_metrics.successful_retries
                + self._retry_metrics.failed_retries
            )
            if total > 0:
                self._retry_metrics.success_rate = (
                    self._retry_metrics.successful_retries / total
                )

    async def record_degradation(
        self,
        level: str,
        duration: float = 0.0,
    ) -> None:
        """Record degradation event."""
        async with self._lock:
            self._degradation_metrics.trigger_count += 1
            self._degradation_metrics.total_duration += duration
            self._degradation_metrics.last_trigger = datetime.now(UTC)
            self._degradation_metrics.degradation_level = level

    async def get_error_stats(self) -> dict[str, Any]:
        """Get error statistics."""
        async with self._lock:
            return {
                "total_errors": len(self._errors),
                "error_metrics": {
                    key: metric.to_dict()
                    for key, metric in self._error_metrics.items()
                },
                "recent_errors": [
                    {
                        "error_code": e.error_code.value,
                        "message": e.message,
                        "severity": e.severity.value,
                        "timestamp": e.timestamp,
                    }
                    for e in self._errors[-10:]
                ],
            }

    async def get_retry_stats(self) -> dict[str, Any]:
        """Get retry statistics."""
        async with self._lock:
            return self._retry_metrics.to_dict()

    async def get_degradation_stats(self) -> dict[str, Any]:
        """Get degradation statistics."""
        async with self._lock:
            return self._degradation_metrics.to_dict()

    async def get_all_stats(self) -> dict[str, Any]:
        """Get all statistics."""
        return {
            "errors": await self.get_error_stats(),
            "retries": await self.get_retry_stats(),
            "degradation": await self.get_degradation_stats(),
        }

    async def get_errors_by_severity(
        self,
        severity: ErrorSeverity,
    ) -> list[XAgentException]:
        """Get errors by severity."""
        async with self._lock:
            return [
                e for e in self._errors
                if isinstance(e, XAgentException) and e.severity == severity
            ]

    async def get_errors_by_code(
        self,
        error_code: ErrorCode,
    ) -> list[XAgentException]:
        """Get errors by code."""
        async with self._lock:
            return [
                e for e in self._errors
                if isinstance(e, XAgentException) and e.error_code == error_code
            ]

    async def get_error_rate(self, window_seconds: int = 60) -> float:
        """Get error rate in the last N seconds."""
        async with self._lock:
            now = datetime.now(UTC)
            cutoff = now - timedelta(seconds=window_seconds)

            recent_errors = [
                e for e in self._errors
                if isinstance(e, XAgentException)
                and datetime.fromtimestamp(e.timestamp, UTC) > cutoff
            ]

            return len(recent_errors) / window_seconds if window_seconds > 0 else 0.0

    async def clear_history(self) -> None:
        """Clear error history."""
        async with self._lock:
            self._errors.clear()
            self._error_metrics.clear()
            self._retry_metrics = RetryMetric()
            self._degradation_metrics = DegradationMetric()


# Global error monitor
_error_monitor: ErrorMonitor | None = None


def get_error_monitor() -> ErrorMonitor:
    """Get or create the global error monitor."""
    global _error_monitor
    if _error_monitor is None:
        _error_monitor = ErrorMonitor()
    return _error_monitor
