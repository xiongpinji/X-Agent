"""
Comprehensive enhanced browser automation service.

Integrates all advanced capabilities: smart locator, waiter, interactions,
analyzer, recovery, pool, and stealth.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional, Any, Callable, List

from backend.app.services.browser.smart_locator import SmartLocator, LocatorStrategy
from backend.app.services.browser.waiter import SmartWaiter, WaitStrategy
from backend.app.services.browser.interactions import AdvancedInteractions, InteractionType
from backend.app.services.browser.analyzer import PageAnalyzer, PageStructure
from backend.app.services.browser.recovery import ErrorRecovery, ErrorType
from backend.app.services.browser.pool import BrowserPool, BrowserPoolManager
from backend.app.services.browser.stealth import StealthBrowser

logger = logging.getLogger(__name__)


@dataclass
class AutomationSession:
    """Enhanced automation session."""
    session_id: str
    page: Any
    locator: SmartLocator
    waiter: SmartWaiter
    interactions: AdvancedInteractions
    analyzer: PageAnalyzer
    recovery: ErrorRecovery
    stealth: StealthBrowser
    created_at: float
    last_activity: float
    action_count: int = 0
    error_count: int = 0


class EnhancedBrowserAutomationService:
    """
    Comprehensive browser automation service with all advanced capabilities.
    """

    def __init__(
        self,
        pool_size: int = 5,
        default_timeout: float = 30.0,
        enable_stealth: bool = True,
    ):
        """
        Initialize enhanced automation service.

        Args:
            pool_size: Browser pool size
            default_timeout: Default timeout for operations
            enable_stealth: Enable stealth mode
        """
        self.pool_size = pool_size
        self.default_timeout = default_timeout
        self.enable_stealth = enable_stealth
        self.logger = logger

        self.sessions: dict[str, AutomationSession] = {}
        self.pool_manager = BrowserPoolManager()
        self.default_pool = self.pool_manager.create_pool(
            "default",
            max_browsers=pool_size,
        )

    async def create_session(
        self,
        session_id: str,
        page: Any,
        enable_stealth: Optional[bool] = None,
    ) -> AutomationSession:
        """
        Create an enhanced automation session.

        Args:
            session_id: Session ID
            page: Playwright page object
            enable_stealth: Enable stealth mode for this session

        Returns:
            AutomationSession
        """
        try:
            enable_stealth = enable_stealth if enable_stealth is not None else self.enable_stealth

            # Create component instances
            locator = SmartLocator(session_id)
            waiter = SmartWaiter(session_id, default_timeout=self.default_timeout)
            interactions = AdvancedInteractions(session_id)
            analyzer = PageAnalyzer(session_id)
            recovery = ErrorRecovery(session_id)
            stealth = StealthBrowser(session_id)

            # Apply stealth measures if enabled
            if enable_stealth:
                await stealth.apply_stealth_measures(page)

            # Create session
            session = AutomationSession(
                session_id=session_id,
                page=page,
                locator=locator,
                waiter=waiter,
                interactions=interactions,
                analyzer=analyzer,
                recovery=recovery,
                stealth=stealth,
                created_at=time.time(),
                last_activity=time.time(),
            )

            self.sessions[session_id] = session
            self.logger.info(f"Created enhanced session {session_id}")
            return session

        except Exception as e:
            self.logger.error(f"Failed to create session: {e}")
            raise

    async def close_session(self, session_id: str) -> bool:
        """
        Close an automation session.

        Args:
            session_id: Session ID

        Returns:
            True if closed successfully
        """
        try:
            session = self.sessions.pop(session_id, None)
            if session:
                try:
                    await session.page.close()
                except Exception:
                    pass
                self.logger.info(f"Closed session {session_id}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to close session: {e}")
            return False

    async def navigate(
        self,
        session_id: str,
        url: str,
        wait_strategy: WaitStrategy = WaitStrategy.ADAPTIVE,
    ) -> bool:
        """
        Navigate to URL with smart waiting.

        Args:
            session_id: Session ID
            url: URL to navigate to
            wait_strategy: Waiting strategy

        Returns:
            True if successful
        """
        try:
            session = self._get_session(session_id)

            async def navigate_op():
                await session.page.goto(url, wait_until="domcontentloaded")

            # Retry navigation if needed
            await session.recovery.retry_operation(navigate_op, max_retries=2)

            # Wait for page to be ready
            await session.waiter.wait_for_navigation(
                session.page,
                strategy=wait_strategy,
            )

            session.last_activity = time.time()
            session.action_count += 1
            self.logger.info(f"Navigated to {url}")
            return True

        except Exception as e:
            self.logger.error(f"Navigation failed: {e}")
            session.error_count += 1
            return False

    async def find_and_click(
        self,
        session_id: str,
        selector: str,
        wait_before_click: bool = True,
    ) -> bool:
        """
        Find element and click it with smart locating and waiting.

        Args:
            session_id: Session ID
            selector: Element selector
            wait_before_click: Wait for element before clicking

        Returns:
            True if successful
        """
        try:
            session = self._get_session(session_id)

            # Wait for element if requested
            if wait_before_click:
                wait_result = await session.waiter.wait_for_selector(
                    session.page,
                    selector,
                )
                if not wait_result.success:
                    self.logger.warning(f"Element not found: {selector}")
                    return False

            # Click element
            await session.page.click(selector)

            session.last_activity = time.time()
            session.action_count += 1
            self.logger.info(f"Clicked element: {selector}")
            return True

        except Exception as e:
            self.logger.error(f"Click failed: {e}")
            session.error_count += 1
            await session.recovery.handle_error(session.page, e)
            return False

    async def find_and_fill(
        self,
        session_id: str,
        selector: str,
        value: str,
        clear_first: bool = True,
        wait_before_fill: bool = True,
    ) -> bool:
        """
        Find element and fill it with value.

        Args:
            session_id: Session ID
            selector: Element selector
            value: Value to fill
            clear_first: Clear element before filling
            wait_before_fill: Wait for element before filling

        Returns:
            True if successful
        """
        try:
            session = self._get_session(session_id)

            # Wait for element if requested
            if wait_before_fill:
                wait_result = await session.waiter.wait_for_selector(
                    session.page,
                    selector,
                )
                if not wait_result.success:
                    self.logger.warning(f"Element not found: {selector}")
                    return False

            # Fill element
            if clear_first:
                await session.page.fill(selector, "")

            await session.interactions.type_text(
                session.page,
                selector,
                value,
                clear_first=False,
            )

            session.last_activity = time.time()
            session.action_count += 1
            self.logger.info(f"Filled element: {selector}")
            return True

        except Exception as e:
            self.logger.error(f"Fill failed: {e}")
            session.error_count += 1
            await session.recovery.handle_error(session.page, e)
            return False

    async def analyze_page(self, session_id: str) -> Optional[PageStructure]:
        """
        Analyze page structure.

        Args:
            session_id: Session ID

        Returns:
            PageStructure or None
        """
        try:
            session = self._get_session(session_id)
            structure = await session.analyzer.analyze_page(session.page)
            session.last_activity = time.time()
            return structure
        except Exception as e:
            self.logger.error(f"Page analysis failed: {e}")
            return None

    async def extract_text(
        self,
        session_id: str,
        selector: str,
    ) -> Optional[str]:
        """
        Extract text from element.

        Args:
            session_id: Session ID
            selector: Element selector

        Returns:
            Extracted text or None
        """
        try:
            session = self._get_session(session_id)
            text = await session.analyzer.extract_text_content(
                session.page,
                selector,
            )
            session.last_activity = time.time()
            return text
        except Exception as e:
            self.logger.error(f"Text extraction failed: {e}")
            return None

    async def take_screenshot(
        self,
        session_id: str,
        path: Optional[str] = None,
    ) -> Optional[bytes]:
        """
        Take screenshot.

        Args:
            session_id: Session ID
            path: Optional path to save screenshot

        Returns:
            Screenshot bytes or None
        """
        try:
            session = self._get_session(session_id)
            screenshot = await session.page.screenshot(path=path)
            session.last_activity = time.time()
            return screenshot
        except Exception as e:
            self.logger.error(f"Screenshot failed: {e}")
            return None

    async def drag_and_drop(
        self,
        session_id: str,
        source_selector: str,
        target_selector: str,
    ) -> bool:
        """
        Drag and drop element.

        Args:
            session_id: Session ID
            source_selector: Source element selector
            target_selector: Target element selector

        Returns:
            True if successful
        """
        try:
            session = self._get_session(session_id)
            result = await session.interactions.drag_and_drop(
                session.page,
                source_selector,
                target_selector,
            )
            session.last_activity = time.time()
            session.action_count += 1
            return result.success
        except Exception as e:
            self.logger.error(f"Drag and drop failed: {e}")
            session.error_count += 1
            return False

    async def upload_file(
        self,
        session_id: str,
        file_input_selector: str,
        file_path: str,
    ) -> bool:
        """
        Upload file.

        Args:
            session_id: Session ID
            file_input_selector: File input selector
            file_path: Path to file

        Returns:
            True if successful
        """
        try:
            session = self._get_session(session_id)
            result = await session.interactions.upload_file(
                session.page,
                file_input_selector,
                file_path,
            )
            session.last_activity = time.time()
            session.action_count += 1
            return result.success
        except Exception as e:
            self.logger.error(f"File upload failed: {e}")
            session.error_count += 1
            return False

    def get_session_stats(self, session_id: str) -> Optional[dict]:
        """Get session statistics."""
        try:
            session = self._get_session(session_id)

            return {
                "session_id": session_id,
                "created_at": session.created_at,
                "last_activity": session.last_activity,
                "uptime": time.time() - session.created_at,
                "action_count": session.action_count,
                "error_count": session.error_count,
                "locator_stats": session.locator.get_cache_stats(),
                "waiter_stats": session.waiter.get_wait_stats(),
                "interaction_stats": session.interactions.get_interaction_stats(),
                "error_stats": session.recovery.get_error_stats(),
            }
        except Exception as e:
            self.logger.error(f"Failed to get session stats: {e}")
            return None

    def get_pool_stats(self) -> dict:
        """Get pool statistics."""
        return {
            pool_id: {
                "total_browsers": stats.total_browsers,
                "active_browsers": stats.active_browsers,
                "idle_browsers": stats.idle_browsers,
                "total_sessions": stats.total_sessions,
                "uptime": stats.uptime,
            }
            for pool_id, stats in self.pool_manager.get_all_stats().items()
        }

    def _get_session(self, session_id: str) -> AutomationSession:
        """Get session or raise error."""
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        return session

    async def cleanup(self) -> bool:
        """Clean up all resources."""
        try:
            # Close all sessions
            for session_id in list(self.sessions.keys()):
                await self.close_session(session_id)

            # Close all pools
            await self.pool_manager.close_all_pools()

            self.logger.info("Cleanup complete")
            return True
        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")
            return False


# Global instance
enhanced_automation_service = EnhancedBrowserAutomationService()


def get_enhanced_automation_service() -> EnhancedBrowserAutomationService:
    """Get the enhanced automation service."""
    return enhanced_automation_service
