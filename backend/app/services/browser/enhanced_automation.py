"""Enhanced browser automation with AI element detection and smart waiting."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from playwright.async_api import Page, Browser, BrowserContext


class WaitStrategy(str, Enum):
    """Strategies for waiting in browser automation."""
    NETWORK_IDLE = "network_idle"
    DOM_CONTENT = "domcontentloaded"
    LOAD = "load"
    ADAPTIVE = "adaptive"
    CUSTOM = "custom"


class ElementDetectionMethod(str, Enum):
    """Methods for detecting elements."""
    CSS_SELECTOR = "css_selector"
    XPATH = "xpath"
    TEXT = "text"
    AI_VISION = "ai_vision"


@dataclass
class ElementInfo:
    """Information about a detected element."""
    selector: str
    method: ElementDetectionMethod
    confidence: float = 1.0
    description: str = ""
    bounding_box: dict[str, float] | None = None
    visible: bool = True


@dataclass
class BrowserSession:
    """Represents a browser session."""
    session_id: str
    browser: Browser | None = None
    context: BrowserContext | None = None
    page: Page | None = None
    created_at: float = 0.0
    last_activity: float = 0.0
    active_operations: int = 0


class EnhancedBrowserAutomation:
    """Enhanced browser automation with AI capabilities."""

    def __init__(
        self,
        ai_detector: Any | None = None,
        default_wait_strategy: WaitStrategy = WaitStrategy.ADAPTIVE,
        operation_timeout: float = 30.0,
    ):
        """Initialize enhanced browser automation.

        Args:
            ai_detector: AI model for element detection
            default_wait_strategy: Default waiting strategy
            operation_timeout: Timeout for operations (seconds)
        """
        self.ai_detector = ai_detector
        self.default_wait_strategy = default_wait_strategy
        self.operation_timeout = operation_timeout
        self._sessions: dict[str, BrowserSession] = {}
        self._error_handlers: dict[str, Callable] = {}

    async def create_session(
        self,
        session_id: str,
        browser: Browser,
        context: BrowserContext,
        page: Page,
    ) -> BrowserSession:
        """Create a new browser session.

        Args:
            session_id: Unique session identifier
            browser: Playwright browser instance
            context: Browser context
            page: Browser page

        Returns:
            Browser session
        """
        session = BrowserSession(
            session_id=session_id,
            browser=browser,
            context=context,
            page=page,
            created_at=time.time(),
            last_activity=time.time(),
        )

        self._sessions[session_id] = session
        return session

    async def close_session(self, session_id: str) -> bool:
        """Close a browser session.

        Args:
            session_id: Session identifier

        Returns:
            True if session was closed successfully
        """
        session = self._sessions.pop(session_id, None)
        if not session:
            return False

        try:
            if session.page:
                await session.page.close()
            if session.context:
                await session.context.close()
            if session.browser:
                await session.browser.close()
            return True
        except Exception as e:
            print(f"Error closing session: {e}")
            return False

    async def smart_wait(
        self,
        session_id: str,
        strategy: WaitStrategy | None = None,
        timeout: float | None = None,
        condition: Callable | None = None,
    ) -> bool:
        """Smart wait with multiple strategies.

        Args:
            session_id: Session identifier
            strategy: Waiting strategy
            timeout: Timeout in seconds
            condition: Custom condition function

        Returns:
            True if wait succeeded
        """
        session = self._sessions.get(session_id)
        if not session or not session.page:
            return False

        strategy = strategy or self.default_wait_strategy
        timeout = timeout or self.operation_timeout

        try:
            if strategy == WaitStrategy.NETWORK_IDLE:
                await session.page.wait_for_load_state("networkidle", timeout=timeout * 1000)
            elif strategy == WaitStrategy.DOM_CONTENT:
                await session.page.wait_for_load_state("domcontentloaded", timeout=timeout * 1000)
            elif strategy == WaitStrategy.LOAD:
                await session.page.wait_for_load_state("load", timeout=timeout * 1000)
            elif strategy == WaitStrategy.ADAPTIVE:
                await self._adaptive_wait(session, timeout)
            elif strategy == WaitStrategy.CUSTOM and condition:
                await self._custom_wait(session, condition, timeout)

            session.last_activity = time.time()
            return True
        except Exception as e:
            print(f"Wait failed: {e}")
            return False

    async def find_element(
        self,
        session_id: str,
        description: str,
        method: ElementDetectionMethod = ElementDetectionMethod.AI_VISION,
    ) -> ElementInfo | None:
        """Find an element using AI vision or other methods.

        Args:
            session_id: Session identifier
            description: Description of element to find
            method: Detection method

        Returns:
            Element information if found
        """
        session = self._sessions.get(session_id)
        if not session or not session.page:
            return None

        try:
            if method == ElementDetectionMethod.AI_VISION and self.ai_detector:
                return await self._find_element_with_ai(session, description)
            elif method == ElementDetectionMethod.CSS_SELECTOR:
                return await self._find_element_by_selector(session, description)
            elif method == ElementDetectionMethod.XPATH:
                return await self._find_element_by_xpath(session, description)
            elif method == ElementDetectionMethod.TEXT:
                return await self._find_element_by_text(session, description)

            session.last_activity = time.time()
            return None
        except Exception as e:
            print(f"Element detection failed: {e}")
            return None

    async def click_element(
        self,
        session_id: str,
        element: ElementInfo,
        retry_count: int = 3,
    ) -> bool:
        """Click an element with error recovery.

        Args:
            session_id: Session identifier
            element: Element to click
            retry_count: Number of retries

        Returns:
            True if click succeeded
        """
        session = self._sessions.get(session_id)
        if not session or not session.page:
            return False

        for attempt in range(retry_count):
            try:
                session.active_operations += 1

                # Scroll element into view
                await session.page.locator(element.selector).scroll_into_view_if_needed()

                # Wait for element to be visible
                await session.page.locator(element.selector).wait_for(state="visible", timeout=5000)

                # Click element
                await session.page.locator(element.selector).click()

                session.last_activity = time.time()
                return True
            except Exception as e:
                if attempt < retry_count - 1:
                    await asyncio.sleep(1)
                else:
                    print(f"Click failed after {retry_count} attempts: {e}")
                    await self._handle_error(session_id, "click_failed", e)
            finally:
                session.active_operations -= 1

        return False

    async def fill_input(
        self,
        session_id: str,
        element: ElementInfo,
        value: str,
        clear_first: bool = True,
    ) -> bool:
        """Fill an input element.

        Args:
            session_id: Session identifier
            element: Input element
            value: Value to fill
            clear_first: Clear input before filling

        Returns:
            True if fill succeeded
        """
        session = self._sessions.get(session_id)
        if not session or not session.page:
            return False

        try:
            session.active_operations += 1

            locator = session.page.locator(element.selector)
            await locator.scroll_into_view_if_needed()
            await locator.wait_for(state="visible", timeout=5000)

            if clear_first:
                await locator.clear()

            await locator.fill(value)

            session.last_activity = time.time()
            return True
        except Exception as e:
            print(f"Fill input failed: {e}")
            await self._handle_error(session_id, "fill_failed", e)
            return False
        finally:
            session.active_operations -= 1

    async def extract_text(
        self,
        session_id: str,
        selector: str,
    ) -> str | None:
        """Extract text from an element.

        Args:
            session_id: Session identifier
            selector: CSS selector

        Returns:
            Extracted text or None
        """
        session = self._sessions.get(session_id)
        if not session or not session.page:
            return None

        try:
            session.active_operations += 1

            text = await session.page.locator(selector).text_content()
            session.last_activity = time.time()
            return text
        except Exception as e:
            print(f"Text extraction failed: {e}")
            return None
        finally:
            session.active_operations -= 1

    async def take_screenshot(
        self,
        session_id: str,
        path: str | None = None,
    ) -> bytes | None:
        """Take a screenshot of the page.

        Args:
            session_id: Session identifier
            path: Optional path to save screenshot

        Returns:
            Screenshot bytes or None
        """
        session = self._sessions.get(session_id)
        if not session or not session.page:
            return None

        try:
            session.active_operations += 1

            screenshot = await session.page.screenshot(path=path)
            session.last_activity = time.time()
            return screenshot
        except Exception as e:
            print(f"Screenshot failed: {e}")
            return None
        finally:
            session.active_operations -= 1

    async def _adaptive_wait(self, session: BrowserSession, timeout: float) -> None:
        """Adaptive wait strategy that combines multiple approaches.

        Args:
            session: Browser session
            timeout: Timeout in seconds
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # Try network idle first
                await session.page.wait_for_load_state("networkidle", timeout=2000)
                return
            except Exception:
                pass

            # Check if page is still loading
            is_loading = await session.page.evaluate("document.readyState !== 'complete'")
            if not is_loading:
                return

            await asyncio.sleep(0.5)

    async def _custom_wait(
        self,
        session: BrowserSession,
        condition: Callable,
        timeout: float,
    ) -> None:
        """Wait for a custom condition.

        Args:
            session: Browser session
            condition: Condition function
            timeout: Timeout in seconds
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                result = condition(session.page)
                if isinstance(result, bool):
                    if result:
                        return
                else:
                    await result
                    return
            except Exception:
                pass

            await asyncio.sleep(0.5)

    async def _find_element_with_ai(
        self,
        session: BrowserSession,
        description: str,
    ) -> ElementInfo | None:
        """Find element using AI vision.

        Args:
            session: Browser session
            description: Element description

        Returns:
            Element information or None
        """
        if not self.ai_detector:
            return None

        try:
            screenshot = await session.page.screenshot()
            elements = await self.ai_detector.detect(screenshot, description)

            if elements:
                element = elements[0]
                return ElementInfo(
                    selector=element.get("selector", ""),
                    method=ElementDetectionMethod.AI_VISION,
                    confidence=element.get("confidence", 0.9),
                    description=description,
                    bounding_box=element.get("bounding_box"),
                )
        except Exception as e:
            print(f"AI detection failed: {e}")

        return None

    async def _find_element_by_selector(
        self,
        session: BrowserSession,
        selector: str,
    ) -> ElementInfo | None:
        """Find element by CSS selector.

        Args:
            session: Browser session
            selector: CSS selector

        Returns:
            Element information or None
        """
        try:
            locator = session.page.locator(selector)
            count = await locator.count()

            if count > 0:
                return ElementInfo(
                    selector=selector,
                    method=ElementDetectionMethod.CSS_SELECTOR,
                    confidence=1.0,
                )
        except Exception:
            pass

        return None

    async def _find_element_by_xpath(
        self,
        session: BrowserSession,
        xpath: str,
    ) -> ElementInfo | None:
        """Find element by XPath.

        Args:
            session: Browser session
            xpath: XPath expression

        Returns:
            Element information or None
        """
        try:
            locator = session.page.locator(f"xpath={xpath}")
            count = await locator.count()

            if count > 0:
                return ElementInfo(
                    selector=xpath,
                    method=ElementDetectionMethod.XPATH,
                    confidence=1.0,
                )
        except Exception:
            pass

        return None

    async def _find_element_by_text(
        self,
        session: BrowserSession,
        text: str,
    ) -> ElementInfo | None:
        """Find element by text content.

        Args:
            session: Browser session
            text: Text to search for

        Returns:
            Element information or None
        """
        try:
            locator = session.page.get_by_text(text)
            count = await locator.count()

            if count > 0:
                return ElementInfo(
                    selector=text,
                    method=ElementDetectionMethod.TEXT,
                    confidence=0.8,
                )
        except Exception:
            pass

        return None

    async def _handle_error(
        self,
        session_id: str,
        error_type: str,
        error: Exception,
    ) -> None:
        """Handle errors with registered handlers.

        Args:
            session_id: Session identifier
            error_type: Type of error
            error: Exception object
        """
        handler = self._error_handlers.get(error_type)
        if handler:
            try:
                await handler(session_id, error)
            except Exception as e:
                print(f"Error handler failed: {e}")

    def register_error_handler(
        self,
        error_type: str,
        handler: Callable,
    ) -> None:
        """Register an error handler.

        Args:
            error_type: Type of error
            handler: Handler function
        """
        self._error_handlers[error_type] = handler

    def get_session_stats(self, session_id: str) -> dict[str, Any] | None:
        """Get statistics for a session.

        Args:
            session_id: Session identifier

        Returns:
            Session statistics or None
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        return {
            "session_id": session_id,
            "created_at": session.created_at,
            "last_activity": session.last_activity,
            "active_operations": session.active_operations,
            "uptime": time.time() - session.created_at,
        }


# Global instance
enhanced_browser_automation = EnhancedBrowserAutomation()
