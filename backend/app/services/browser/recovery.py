"""
Error recovery and resilience mechanisms for browser automation.

Implements automatic retry, captcha detection, login state detection,
page crash recovery, and network error handling.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Any, Callable, List

logger = logging.getLogger(__name__)


class ErrorType(str, Enum):
    """Types of errors that can occur."""
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    ELEMENT_NOT_FOUND = "element_not_found"
    NAVIGATION_ERROR = "navigation_error"
    CAPTCHA_DETECTED = "captcha_detected"
    LOGIN_REQUIRED = "login_required"
    PAGE_CRASH = "page_crash"
    PERMISSION_DENIED = "permission_denied"
    UNKNOWN = "unknown"


class RecoveryStrategy(str, Enum):
    """Recovery strategies for errors."""
    RETRY = "retry"
    RELOAD = "reload"
    NAVIGATE_HOME = "navigate_home"
    CLEAR_COOKIES = "clear_cookies"
    WAIT_AND_RETRY = "wait_and_retry"
    MANUAL_INTERVENTION = "manual_intervention"
    SKIP = "skip"


@dataclass
class ErrorContext:
    """Context information about an error."""
    error_type: ErrorType
    error_message: str
    timestamp: float
    page_url: Optional[str] = None
    page_title: Optional[str] = None
    screenshot_path: Optional[str] = None
    recovery_attempted: bool = False
    recovery_strategy: Optional[RecoveryStrategy] = None
    recovery_successful: bool = False


class ErrorRecovery:
    """
    Handles error recovery and resilience.
    """

    def __init__(self, session_id: str):
        """
        Initialize error recovery.

        Args:
            session_id: Browser session ID
        """
        self.session_id = session_id
        self.logger = logger
        self.error_history: List[ErrorContext] = []
        self.recovery_handlers: dict[ErrorType, Callable] = {}
        self.max_retries = 3
        self.retry_delay = 2.0

    async def handle_error(
        self,
        page: Any,
        error: Exception,
        context: Optional[dict] = None,
    ) -> bool:
        """
        Handle an error with automatic recovery.

        Args:
            page: Playwright page object
            error: Exception that occurred
            context: Additional context

        Returns:
            True if recovery was successful
        """
        error_type = self._classify_error(error)
        error_context = ErrorContext(
            error_type=error_type,
            error_message=str(error),
            timestamp=time.time(),
            page_url=page.url if page else None,
            page_title=await page.title() if page else None,
        )

        self.logger.warning(f"Error detected: {error_type.value} - {error}")
        self.error_history.append(error_context)

        # Try to recover
        recovery_strategy = self._select_recovery_strategy(error_type)
        error_context.recovery_strategy = recovery_strategy

        try:
            success = await self._execute_recovery(page, error_type, recovery_strategy)
            error_context.recovery_successful = success
            error_context.recovery_attempted = True
            return success
        except Exception as e:
            self.logger.error(f"Recovery failed: {e}")
            error_context.recovery_attempted = True
            error_context.recovery_successful = False
            return False

    async def retry_operation(
        self,
        operation: Callable,
        max_retries: Optional[int] = None,
        delay: Optional[float] = None,
        backoff: bool = True,
    ) -> Any:
        """
        Retry an operation with exponential backoff.

        Args:
            operation: Async callable to retry
            max_retries: Maximum retry attempts
            delay: Initial delay between retries
            backoff: Use exponential backoff

        Returns:
            Result of operation
        """
        max_retries = max_retries or self.max_retries
        delay = delay or self.retry_delay

        for attempt in range(max_retries + 1):
            try:
                result = await operation()
                if attempt > 0:
                    self.logger.info(f"Operation succeeded on attempt {attempt + 1}")
                return result
            except Exception as e:
                if attempt < max_retries:
                    wait_time = delay * (2 ** attempt) if backoff else delay
                    self.logger.warning(
                        f"Operation failed (attempt {attempt + 1}/{max_retries + 1}), "
                        f"retrying in {wait_time:.1f}s: {e}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(f"Operation failed after {max_retries + 1} attempts")
                    raise

    async def detect_captcha(self, page: Any) -> bool:
        """
        Detect if page has CAPTCHA.

        Args:
            page: Playwright page object

        Returns:
            True if CAPTCHA detected
        """
        try:
            # Check for common CAPTCHA indicators
            captcha_selectors = [
                "iframe[src*='recaptcha']",
                "[data-sitekey]",
                ".g-recaptcha",
                ".h-captcha",
                "iframe[src*='hcaptcha']",
                ".captcha",
                "#captcha",
            ]

            for selector in captcha_selectors:
                try:
                    count = await page.locator(selector).count()
                    if count > 0:
                        self.logger.warning(f"CAPTCHA detected: {selector}")
                        return True
                except Exception:
                    pass

            return False
        except Exception as e:
            self.logger.error(f"CAPTCHA detection failed: {e}")
            return False

    async def detect_login_required(self, page: Any) -> bool:
        """
        Detect if login is required.

        Args:
            page: Playwright page object

        Returns:
            True if login required
        """
        try:
            # Check for common login indicators
            login_selectors = [
                "button:has-text('Login')",
                "button:has-text('Sign In')",
                "a:has-text('Login')",
                "a:has-text('Sign In')",
                "input[type='password']",
                ".login-form",
                "#login",
            ]

            for selector in login_selectors:
                try:
                    count = await page.locator(selector).count()
                    if count > 0:
                        self.logger.warning(f"Login required detected: {selector}")
                        return True
                except Exception:
                    pass

            return False
        except Exception as e:
            self.logger.error(f"Login detection failed: {e}")
            return False

    async def detect_page_crash(self, page: Any) -> bool:
        """
        Detect if page has crashed.

        Args:
            page: Playwright page object

        Returns:
            True if page crashed
        """
        try:
            # Check for crash indicators
            crash_indicators = [
                "This page isn't available",
                "Error 500",
                "Internal Server Error",
                "Service Unavailable",
                "Bad Gateway",
            ]

            page_text = await page.content()

            for indicator in crash_indicators:
                if indicator.lower() in page_text.lower():
                    self.logger.warning(f"Page crash detected: {indicator}")
                    return True

            return False
        except Exception as e:
            self.logger.error(f"Crash detection failed: {e}")
            return False

    async def handle_network_error(
        self,
        page: Any,
        retry_count: int = 3,
    ) -> bool:
        """
        Handle network errors with retry.

        Args:
            page: Playwright page object
            retry_count: Number of retries

        Returns:
            True if recovered
        """
        try:
            for attempt in range(retry_count):
                try:
                    # Try to reload page
                    await page.reload()
                    self.logger.info("Page reloaded successfully")
                    return True
                except Exception as e:
                    if attempt < retry_count - 1:
                        wait_time = 2 ** attempt
                        self.logger.warning(
                            f"Reload failed (attempt {attempt + 1}), "
                            f"retrying in {wait_time}s: {e}"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        self.logger.error(f"Reload failed after {retry_count} attempts")
                        return False

            return False
        except Exception as e:
            self.logger.error(f"Network error handling failed: {e}")
            return False

    def _classify_error(self, error: Exception) -> ErrorType:
        """Classify error type."""
        error_str = str(error).lower()

        if "timeout" in error_str or "timed out" in error_str:
            return ErrorType.TIMEOUT
        elif "network" in error_str or "connection" in error_str:
            return ErrorType.NETWORK_ERROR
        elif "not found" in error_str or "no such element" in error_str:
            return ErrorType.ELEMENT_NOT_FOUND
        elif "navigation" in error_str:
            return ErrorType.NAVIGATION_ERROR
        elif "permission" in error_str or "denied" in error_str:
            return ErrorType.PERMISSION_DENIED
        else:
            return ErrorType.UNKNOWN

    def _select_recovery_strategy(self, error_type: ErrorType) -> RecoveryStrategy:
        """Select recovery strategy for error type."""
        strategies = {
            ErrorType.NETWORK_ERROR: RecoveryStrategy.WAIT_AND_RETRY,
            ErrorType.TIMEOUT: RecoveryStrategy.RELOAD,
            ErrorType.ELEMENT_NOT_FOUND: RecoveryStrategy.WAIT_AND_RETRY,
            ErrorType.NAVIGATION_ERROR: RecoveryStrategy.RELOAD,
            ErrorType.CAPTCHA_DETECTED: RecoveryStrategy.MANUAL_INTERVENTION,
            ErrorType.LOGIN_REQUIRED: RecoveryStrategy.MANUAL_INTERVENTION,
            ErrorType.PAGE_CRASH: RecoveryStrategy.NAVIGATE_HOME,
            ErrorType.PERMISSION_DENIED: RecoveryStrategy.SKIP,
            ErrorType.UNKNOWN: RecoveryStrategy.WAIT_AND_RETRY,
        }

        return strategies.get(error_type, RecoveryStrategy.WAIT_AND_RETRY)

    async def _execute_recovery(
        self,
        page: Any,
        error_type: ErrorType,
        strategy: RecoveryStrategy,
    ) -> bool:
        """Execute recovery strategy."""
        try:
            if strategy == RecoveryStrategy.RETRY:
                await asyncio.sleep(self.retry_delay)
                return True

            elif strategy == RecoveryStrategy.RELOAD:
                await page.reload()
                return True

            elif strategy == RecoveryStrategy.NAVIGATE_HOME:
                await page.goto("/")
                return True

            elif strategy == RecoveryStrategy.CLEAR_COOKIES:
                await page.context.clear_cookies()
                await page.reload()
                return True

            elif strategy == RecoveryStrategy.WAIT_AND_RETRY:
                await asyncio.sleep(self.retry_delay)
                return True

            elif strategy == RecoveryStrategy.MANUAL_INTERVENTION:
                self.logger.warning("Manual intervention required")
                return False

            elif strategy == RecoveryStrategy.SKIP:
                self.logger.warning("Skipping operation due to error")
                return False

            return False

        except Exception as e:
            self.logger.error(f"Recovery execution failed: {e}")
            return False

    def register_error_handler(
        self,
        error_type: ErrorType,
        handler: Callable,
    ) -> None:
        """
        Register custom error handler.

        Args:
            error_type: Type of error
            handler: Handler function
        """
        self.recovery_handlers[error_type] = handler
        self.logger.debug(f"Registered handler for {error_type.value}")

    def get_error_stats(self) -> dict:
        """Get error statistics."""
        by_type = {}
        for error in self.error_history:
            etype = error.error_type.value
            if etype not in by_type:
                by_type[etype] = {"count": 0, "recovered": 0}
            by_type[etype]["count"] += 1
            if error.recovery_successful:
                by_type[etype]["recovered"] += 1

        total_errors = len(self.error_history)
        recovered = sum(1 for e in self.error_history if e.recovery_successful)

        return {
            "total_errors": total_errors,
            "recovered": recovered,
            "recovery_rate": recovered / total_errors if total_errors > 0 else 0,
            "by_type": by_type,
        }

    def clear_history(self) -> None:
        """Clear error history."""
        self.error_history.clear()


def create_error_recovery(session_id: str) -> ErrorRecovery:
    """Create error recovery for a session."""
    return ErrorRecovery(session_id)
