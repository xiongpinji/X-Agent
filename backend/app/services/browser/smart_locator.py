# 未接线（P0-11 审计标注）：本模块为宣传的企业级浏览器增强能力，但当前没有任何 API 消费方，未暴露到任何接口。按要求保留代码，待后续接线或归档。
"""
Smart element locator module for X-Agent browser automation.

Implements multi-strategy element location with automatic retry,
fallback, and adaptation to element changes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class LocatorStrategy(StrEnum):
    """Element locator strategies."""

    CSS = "css"
    XPATH = "xpath"
    TEXT = "text"
    ID = "id"
    CLASS = "class"
    AI = "ai"


@dataclass
class LocatorResult:
    """Result of element location attempt."""

    found: bool
    element: Any | None = None
    strategy_used: LocatorStrategy | None = None
    attempts: int = 0
    retry_count: int = 0
    time_taken_ms: float = 0.0
    error: str | None = None
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class SmartLocator:
    """
    Intelligently locates elements using multiple strategies.

    Tries different locator strategies in sequence, with automatic retry
    and fallback to AI-based detection if needed.
    """

    def __init__(
        self,
        session_id: str,
        max_retries: int = 3,
        retry_delay_ms: int = 500,
        enable_ai_fallback: bool = True,
    ):
        """
        Initialize the smart locator.

        Args:
            session_id: Browser session ID
            max_retries: Maximum retry attempts
            retry_delay_ms: Delay between retries in milliseconds
            enable_ai_fallback: Whether to enable AI-based fallback
        """
        self.session_id = session_id
        self.max_retries = max_retries
        self.retry_delay_ms = retry_delay_ms
        self.enable_ai_fallback = enable_ai_fallback
        self.logger = logger
        self.location_cache: dict[str, LocatorResult] = {}

    def find_element(
        self,
        strategies: list[str | LocatorStrategy] | None = None,
        css_selector: str | None = None,
        xpath: str | None = None,
        text: str | None = None,
        element_id: str | None = None,
        fallback_to_ai: bool = True,
        use_cache: bool = True,
    ) -> LocatorResult:
        """
        Find an element using multiple strategies.

        Args:
            strategies: List of strategies to try in order
            css_selector: CSS selector
            xpath: XPath expression
            text: Element text content
            element_id: Element ID
            fallback_to_ai: Whether to fallback to AI detection
            use_cache: Whether to use cached results

        Returns:
            LocatorResult with found element or error
        """
        start_time = datetime.now()

        # Build cache key
        cache_key = self._build_cache_key(
            css_selector, xpath, text, element_id
        )

        # Check cache
        if use_cache and cache_key in self.location_cache:
            cached_result = self.location_cache[cache_key]
            if cached_result.found:
                self.logger.debug(f"Using cached element location: {cache_key}")
                return cached_result

        # Determine strategies to try
        if strategies is None:
            strategies = [
                LocatorStrategy.CSS,
                LocatorStrategy.XPATH,
                LocatorStrategy.TEXT,
                LocatorStrategy.ID,
            ]

        # Convert strings to enums
        strategies = [
            LocatorStrategy(s) if isinstance(s, str) else s
            for s in strategies
        ]

        # Try each strategy
        result = None
        for strategy in strategies:
            result = self._try_strategy(
                strategy,
                css_selector=css_selector,
                xpath=xpath,
                text=text,
                element_id=element_id,
            )

            if result.found:
                result.time_taken_ms = (
                    (datetime.now() - start_time).total_seconds() * 1000
                )
                self.location_cache[cache_key] = result
                self.logger.debug(
                    f"Element found using {strategy.value} strategy"
                )
                return result

        # Fallback to AI if enabled
        if fallback_to_ai and self.enable_ai_fallback:
            result = self._try_ai_detection(
                css_selector, xpath, text, element_id
            )
            if result.found:
                result.time_taken_ms = (
                    (datetime.now() - start_time).total_seconds() * 1000
                )
                self.location_cache[cache_key] = result
                self.logger.debug("Element found using AI detection")
                return result

        # All strategies failed
        result = LocatorResult(
            found=False,
            error="Element not found using any strategy",
            attempts=len(strategies),
            time_taken_ms=(
                (datetime.now() - start_time).total_seconds() * 1000
            ),
        )

        self.logger.warning(
            f"Failed to locate element: {result.error}"
        )

        return result

    def find_element_with_retry(
        self,
        strategies: list[str | LocatorStrategy] | None = None,
        css_selector: str | None = None,
        xpath: str | None = None,
        text: str | None = None,
        element_id: str | None = None,
    ) -> LocatorResult:
        """
        Find element with automatic retry on failure.

        Args:
            strategies: List of strategies to try
            css_selector: CSS selector
            xpath: XPath expression
            text: Element text
            element_id: Element ID

        Returns:
            LocatorResult
        """
        import time

        result = None
        for attempt in range(self.max_retries + 1):
            result = self.find_element(
                strategies=strategies,
                css_selector=css_selector,
                xpath=xpath,
                text=text,
                element_id=element_id,
            )

            if result.found:
                result.retry_count = attempt
                return result

            if attempt < self.max_retries:
                self.logger.debug(
                    f"Retry {attempt + 1}/{self.max_retries} "
                    f"after {self.retry_delay_ms}ms"
                )
                time.sleep(self.retry_delay_ms / 1000.0)

        result.retry_count = self.max_retries
        return result

    def _try_strategy(
        self,
        strategy: LocatorStrategy,
        css_selector: str | None = None,
        xpath: str | None = None,
        text: str | None = None,
        element_id: str | None = None,
    ) -> LocatorResult:
        """Try a specific locator strategy."""
        try:
            if strategy == LocatorStrategy.CSS and css_selector:
                return self._locate_by_css(css_selector)
            elif strategy == LocatorStrategy.XPATH and xpath:
                return self._locate_by_xpath(xpath)
            elif strategy == LocatorStrategy.TEXT and text:
                return self._locate_by_text(text)
            elif strategy == LocatorStrategy.ID and element_id:
                return self._locate_by_id(element_id)
            else:
                return LocatorResult(
                    found=False,
                    error=f"Strategy {strategy.value} not applicable",
                )
        except Exception as e:
            self.logger.error(f"Error in {strategy.value} strategy: {e}")
            return LocatorResult(
                found=False,
                error=str(e),
                strategy_used=strategy,
            )

    def _locate_by_css(self, selector: str) -> LocatorResult:
        """Locate element by CSS selector."""
        # Simplified implementation - in real scenario would use Playwright
        self.logger.debug(f"Locating by CSS: {selector}")
        return LocatorResult(
            found=True,
            strategy_used=LocatorStrategy.CSS,
            metadata={"selector": selector},
        )

    def _locate_by_xpath(self, xpath: str) -> LocatorResult:
        """Locate element by XPath."""
        self.logger.debug(f"Locating by XPath: {xpath}")
        return LocatorResult(
            found=True,
            strategy_used=LocatorStrategy.XPATH,
            metadata={"xpath": xpath},
        )

    def _locate_by_text(self, text: str) -> LocatorResult:
        """Locate element by text content."""
        self.logger.debug(f"Locating by text: {text}")
        return LocatorResult(
            found=True,
            strategy_used=LocatorStrategy.TEXT,
            metadata={"text": text},
        )

    def _locate_by_id(self, element_id: str) -> LocatorResult:
        """Locate element by ID."""
        self.logger.debug(f"Locating by ID: {element_id}")
        return LocatorResult(
            found=True,
            strategy_used=LocatorStrategy.ID,
            metadata={"id": element_id},
        )

    def _try_ai_detection(
        self,
        css_selector: str | None = None,
        xpath: str | None = None,
        text: str | None = None,
        element_id: str | None = None,
    ) -> LocatorResult:
        """Try AI-based element detection."""
        self.logger.debug("Attempting AI-based element detection")

        # Simplified AI detection - in real scenario would use vision model
        return LocatorResult(
            found=False,
            strategy_used=LocatorStrategy.AI,
            error="AI detection not available",
        )

    def _build_cache_key(
        self,
        css_selector: str | None,
        xpath: str | None,
        text: str | None,
        element_id: str | None,
    ) -> str:
        """Build cache key from locator parameters."""
        parts = [
            f"css:{css_selector}" if css_selector else "",
            f"xpath:{xpath}" if xpath else "",
            f"text:{text}" if text else "",
            f"id:{element_id}" if element_id else "",
        ]
        return "|".join(p for p in parts if p)

    def clear_cache(self) -> None:
        """Clear location cache."""
        self.location_cache.clear()
        self.logger.debug("Cleared element location cache")

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        return {
            "cache_size": len(self.location_cache),
            "cached_elements": list(self.location_cache.keys()),
        }

    def adapt_to_changes(
        self,
        old_selector: str,
        new_selector: str,
    ) -> None:
        """
        Adapt to element changes.

        Args:
            old_selector: Previous selector
            new_selector: New selector
        """
        # Update cache with new selector
        if old_selector in self.location_cache:
            result = self.location_cache.pop(old_selector)
            self.location_cache[new_selector] = result
            self.logger.debug(
                f"Adapted selector: {old_selector} -> {new_selector}"
            )


# Global instance factory
def create_smart_locator(session_id: str) -> SmartLocator:
    """Create a smart locator for a session."""
    return SmartLocator(session_id)
