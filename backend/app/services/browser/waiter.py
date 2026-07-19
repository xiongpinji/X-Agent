# 未接线（P0-11 审计标注）：本模块为宣传的企业级浏览器增强能力，但当前没有任何 API 消费方，未暴露到任何接口。按要求保留代码，待后续接线或归档。
"""
Smart waiting mechanisms for browser automation.

Implements dynamic timeout adjustment, condition waiting, network idle detection,
and page stability detection.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, Any

logger = logging.getLogger(__name__)


class WaitStrategy(str, Enum):
    """Strategies for waiting in browser automation."""
    NETWORK_IDLE = "network_idle"
    DOM_CONTENT = "domcontentloaded"
    LOAD = "load"
    ADAPTIVE = "adaptive"
    CUSTOM = "custom"
    STABLE = "stable"


@dataclass
class WaitResult:
    """Result of a wait operation."""
    success: bool
    strategy_used: WaitStrategy
    time_taken_ms: float
    reason: Optional[str] = None
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class SmartWaiter:
    """
    Intelligent waiting with multiple strategies and dynamic timeout adjustment.
    """

    def __init__(
        self,
        session_id: str,
        default_timeout: float = 30.0,
        adaptive_timeout: bool = True,
        network_idle_timeout: float = 2.0,
    ):
        """
        Initialize smart waiter.

        Args:
            session_id: Browser session ID
            default_timeout: Default timeout in seconds
            adaptive_timeout: Enable adaptive timeout adjustment
            network_idle_timeout: Network idle detection timeout in seconds
        """
        self.session_id = session_id
        self.default_timeout = default_timeout
        self.adaptive_timeout = adaptive_timeout
        self.network_idle_timeout = network_idle_timeout
        self.logger = logger
        self.wait_history: list[WaitResult] = []
        self.average_wait_time = 0.0

    async def wait_for_selector(
        self,
        page: Any,
        selector: str,
        timeout: Optional[float] = None,
        strategy: WaitStrategy = WaitStrategy.ADAPTIVE,
    ) -> WaitResult:
        """
        Wait for element selector to appear.

        Args:
            page: Playwright page object
            selector: CSS selector
            timeout: Timeout in seconds
            strategy: Waiting strategy

        Returns:
            WaitResult
        """
        timeout = timeout or self.default_timeout
        start_time = time.time()

        try:
            if strategy == WaitStrategy.ADAPTIVE:
                await self._adaptive_wait_for_selector(page, selector, timeout)
            else:
                await page.wait_for_selector(selector, timeout=timeout * 1000)

            elapsed = (time.time() - start_time) * 1000
            result = WaitResult(
                success=True,
                strategy_used=strategy,
                time_taken_ms=elapsed,
                metadata={"selector": selector}
            )
            self._record_wait(result)
            return result

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            self.logger.warning(f"Wait for selector failed: {e}")
            result = WaitResult(
                success=False,
                strategy_used=strategy,
                time_taken_ms=elapsed,
                reason=str(e),
                metadata={"selector": selector}
            )
            self._record_wait(result)
            return result

    async def wait_for_navigation(
        self,
        page: Any,
        timeout: Optional[float] = None,
        strategy: WaitStrategy = WaitStrategy.LOAD,
    ) -> WaitResult:
        """
        Wait for page navigation to complete.

        Args:
            page: Playwright page object
            timeout: Timeout in seconds
            strategy: Waiting strategy

        Returns:
            WaitResult
        """
        timeout = timeout or self.default_timeout
        start_time = time.time()

        try:
            if strategy == WaitStrategy.NETWORK_IDLE:
                await page.wait_for_load_state("networkidle", timeout=timeout * 1000)
            elif strategy == WaitStrategy.DOM_CONTENT:
                await page.wait_for_load_state("domcontentloaded", timeout=timeout * 1000)
            elif strategy == WaitStrategy.LOAD:
                await page.wait_for_load_state("load", timeout=timeout * 1000)
            elif strategy == WaitStrategy.ADAPTIVE:
                await self._adaptive_wait_for_navigation(page, timeout)
            else:
                await page.wait_for_load_state("load", timeout=timeout * 1000)

            elapsed = (time.time() - start_time) * 1000
            result = WaitResult(
                success=True,
                strategy_used=strategy,
                time_taken_ms=elapsed,
                metadata={"url": page.url}
            )
            self._record_wait(result)
            return result

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            self.logger.warning(f"Wait for navigation failed: {e}")
            result = WaitResult(
                success=False,
                strategy_used=strategy,
                time_taken_ms=elapsed,
                reason=str(e),
                metadata={"url": page.url}
            )
            self._record_wait(result)
            return result

    async def wait_for_condition(
        self,
        page: Any,
        condition: Callable,
        timeout: Optional[float] = None,
        check_interval: float = 0.5,
    ) -> WaitResult:
        """
        Wait for custom condition to be true.

        Args:
            page: Playwright page object
            condition: Async callable that returns bool
            timeout: Timeout in seconds
            check_interval: Interval between checks in seconds

        Returns:
            WaitResult
        """
        timeout = timeout or self.default_timeout
        start_time = time.time()

        try:
            while time.time() - start_time < timeout:
                try:
                    result = condition(page)
                    if asyncio.iscoroutine(result):
                        result = await result

                    if result:
                        elapsed = (time.time() - start_time) * 1000
                        wait_result = WaitResult(
                            success=True,
                            strategy_used=WaitStrategy.CUSTOM,
                            time_taken_ms=elapsed,
                        )
                        self._record_wait(wait_result)
                        return wait_result
                except Exception as e:
                    self.logger.debug(f"Condition check failed: {e}")

                await asyncio.sleep(check_interval)

            elapsed = (time.time() - start_time) * 1000
            result = WaitResult(
                success=False,
                strategy_used=WaitStrategy.CUSTOM,
                time_taken_ms=elapsed,
                reason="Condition timeout",
            )
            self._record_wait(result)
            return result

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            self.logger.warning(f"Wait for condition failed: {e}")
            result = WaitResult(
                success=False,
                strategy_used=WaitStrategy.CUSTOM,
                time_taken_ms=elapsed,
                reason=str(e),
            )
            self._record_wait(result)
            return result

    async def wait_for_page_stable(
        self,
        page: Any,
        timeout: Optional[float] = None,
        stability_threshold: float = 1.0,
    ) -> WaitResult:
        """
        Wait for page to become stable (no DOM changes).

        Args:
            page: Playwright page object
            timeout: Timeout in seconds
            stability_threshold: Time without changes to consider stable (seconds)

        Returns:
            WaitResult
        """
        timeout = timeout or self.default_timeout
        start_time = time.time()

        try:
            last_change_time = time.time()

            while time.time() - start_time < timeout:
                # Check if DOM has changed
                try:
                    current_hash = await page.evaluate(
                        "document.documentElement.innerHTML.length"
                    )
                    await asyncio.sleep(0.2)
                    new_hash = await page.evaluate(
                        "document.documentElement.innerHTML.length"
                    )

                    if current_hash != new_hash:
                        last_change_time = time.time()
                    elif time.time() - last_change_time >= stability_threshold:
                        elapsed = (time.time() - start_time) * 1000
                        result = WaitResult(
                            success=True,
                            strategy_used=WaitStrategy.STABLE,
                            time_taken_ms=elapsed,
                        )
                        self._record_wait(result)
                        return result
                except Exception as e:
                    self.logger.debug(f"Stability check failed: {e}")

                await asyncio.sleep(0.1)

            elapsed = (time.time() - start_time) * 1000
            result = WaitResult(
                success=False,
                strategy_used=WaitStrategy.STABLE,
                time_taken_ms=elapsed,
                reason="Stability timeout",
            )
            self._record_wait(result)
            return result

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            self.logger.warning(f"Wait for page stable failed: {e}")
            result = WaitResult(
                success=False,
                strategy_used=WaitStrategy.STABLE,
                time_taken_ms=elapsed,
                reason=str(e),
            )
            self._record_wait(result)
            return result

    async def wait_for_network_idle(
        self,
        page: Any,
        timeout: Optional[float] = None,
    ) -> WaitResult:
        """
        Wait for network to become idle.

        Args:
            page: Playwright page object
            timeout: Timeout in seconds

        Returns:
            WaitResult
        """
        timeout = timeout or self.default_timeout
        start_time = time.time()

        try:
            await page.wait_for_load_state("networkidle", timeout=timeout * 1000)

            elapsed = (time.time() - start_time) * 1000
            result = WaitResult(
                success=True,
                strategy_used=WaitStrategy.NETWORK_IDLE,
                time_taken_ms=elapsed,
            )
            self._record_wait(result)
            return result

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            self.logger.warning(f"Wait for network idle failed: {e}")
            result = WaitResult(
                success=False,
                strategy_used=WaitStrategy.NETWORK_IDLE,
                time_taken_ms=elapsed,
                reason=str(e),
            )
            self._record_wait(result)
            return result

    async def _adaptive_wait_for_selector(
        self,
        page: Any,
        selector: str,
        timeout: float,
    ) -> None:
        """Adaptive wait for selector using multiple strategies."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # Try to find element
                locator = page.locator(selector)
                count = await locator.count()
                if count > 0:
                    return
            except Exception:
                pass

            await asyncio.sleep(0.2)

        raise TimeoutError(f"Selector not found: {selector}")

    async def _adaptive_wait_for_navigation(
        self,
        page: Any,
        timeout: float,
    ) -> None:
        """Adaptive wait for navigation using multiple strategies."""
        start_time = time.time()

        try:
            # Try network idle first
            await page.wait_for_load_state("networkidle", timeout=2000)
            return
        except Exception:
            pass

        # Fall back to load state
        while time.time() - start_time < timeout:
            try:
                ready_state = await page.evaluate("document.readyState")
                if ready_state == "complete":
                    return
            except Exception:
                pass

            await asyncio.sleep(0.5)

        raise TimeoutError("Navigation timeout")

    def _record_wait(self, result: WaitResult) -> None:
        """Record wait result for analytics."""
        self.wait_history.append(result)

        # Update average wait time
        if self.wait_history:
            total_time = sum(w.time_taken_ms for w in self.wait_history)
            self.average_wait_time = total_time / len(self.wait_history)

        self.logger.debug(
            f"Wait recorded: {result.strategy_used.value}, "
            f"time: {result.time_taken_ms:.2f}ms, "
            f"success: {result.success}"
        )

    def get_wait_stats(self) -> dict:
        """Get wait statistics."""
        successful = sum(1 for w in self.wait_history if w.success)
        failed = len(self.wait_history) - successful

        return {
            "total_waits": len(self.wait_history),
            "successful": successful,
            "failed": failed,
            "success_rate": successful / len(self.wait_history) if self.wait_history else 0,
            "average_wait_ms": self.average_wait_time,
            "max_wait_ms": max((w.time_taken_ms for w in self.wait_history), default=0),
            "min_wait_ms": min((w.time_taken_ms for w in self.wait_history), default=0),
        }

    def clear_history(self) -> None:
        """Clear wait history."""
        self.wait_history.clear()
        self.average_wait_time = 0.0


def create_smart_waiter(session_id: str) -> SmartWaiter:
    """Create a smart waiter for a session."""
    return SmartWaiter(session_id)
