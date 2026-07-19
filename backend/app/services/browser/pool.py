# 未接线（P0-11 审计标注）：本模块为宣传的企业级浏览器增强能力，但当前没有任何 API 消费方，未暴露到任何接口。按要求保留代码，待后续接线或归档。
"""
Browser instance pool for resource management and session reuse.

Implements browser pooling, session management, resource limits,
and automatic cleanup.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any, List
from uuid import uuid4

logger = logging.getLogger(__name__)


class PoolStatus(str, Enum):
    """Status of browser pool."""
    IDLE = "idle"
    ACTIVE = "active"
    BUSY = "busy"
    CLOSED = "closed"


@dataclass
class PooledBrowser:
    """A browser instance in the pool."""
    browser_id: str
    browser: Any
    context: Any
    page: Any
    created_at: float
    last_used: float
    in_use: bool = False
    use_count: int = 0
    error_count: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class PoolStats:
    """Statistics about the browser pool."""
    total_browsers: int
    active_browsers: int
    idle_browsers: int
    total_sessions: int
    average_session_duration: float
    total_errors: int
    uptime: float


class BrowserPool:
    """
    Manages a pool of browser instances for efficient resource usage.
    """

    def __init__(
        self,
        max_browsers: int = 5,
        max_sessions_per_browser: int = 10,
        browser_timeout: float = 300.0,
        idle_timeout: float = 60.0,
    ):
        """
        Initialize browser pool.

        Args:
            max_browsers: Maximum number of browser instances
            max_sessions_per_browser: Maximum sessions per browser
            browser_timeout: Browser instance timeout in seconds
            idle_timeout: Idle browser timeout in seconds
        """
        self.max_browsers = max_browsers
        self.max_sessions_per_browser = max_sessions_per_browser
        self.browser_timeout = browser_timeout
        self.idle_timeout = idle_timeout
        self.logger = logger

        self.browsers: List[PooledBrowser] = []
        self.sessions: dict[str, Any] = {}
        self.status = PoolStatus.IDLE
        self.created_at = time.time()
        self.total_errors = 0

    async def acquire_browser(self) -> Optional[PooledBrowser]:
        """
        Acquire a browser from the pool.

        Returns:
            PooledBrowser or None if pool is full
        """
        try:
            # Try to reuse idle browser
            for browser in self.browsers:
                if not browser.in_use and browser.use_count < self.max_sessions_per_browser:
                    browser.in_use = True
                    browser.last_used = time.time()
                    browser.use_count += 1
                    self.logger.debug(f"Reused browser {browser.browser_id}")
                    return browser

            # Create new browser if under limit
            if len(self.browsers) < self.max_browsers:
                browser = await self._create_browser()
                if browser:
                    self.browsers.append(browser)
                    self.logger.info(f"Created new browser {browser.browser_id}")
                    return browser

            self.logger.warning("Browser pool exhausted")
            return None

        except Exception as e:
            self.logger.error(f"Failed to acquire browser: {e}")
            self.total_errors += 1
            return None

    async def release_browser(self, browser_id: str) -> bool:
        """
        Release a browser back to the pool.

        Args:
            browser_id: Browser ID

        Returns:
            True if released successfully
        """
        try:
            for browser in self.browsers:
                if browser.browser_id == browser_id:
                    browser.in_use = False
                    browser.last_used = time.time()
                    self.logger.debug(f"Released browser {browser_id}")
                    return True

            return False
        except Exception as e:
            self.logger.error(f"Failed to release browser: {e}")
            return False

    async def close_browser(self, browser_id: str) -> bool:
        """
        Close and remove a browser from the pool.

        Args:
            browser_id: Browser ID

        Returns:
            True if closed successfully
        """
        try:
            for i, browser in enumerate(self.browsers):
                if browser.browser_id == browser_id:
                    try:
                        if browser.page:
                            await browser.page.close()
                        if browser.context:
                            await browser.context.close()
                        if browser.browser:
                            await browser.browser.close()
                    except Exception as e:
                        self.logger.warning(f"Error closing browser: {e}")

                    self.browsers.pop(i)
                    self.logger.info(f"Closed browser {browser_id}")
                    return True

            return False
        except Exception as e:
            self.logger.error(f"Failed to close browser: {e}")
            return False

    async def cleanup_idle_browsers(self) -> int:
        """
        Close idle browsers that exceed timeout.

        Returns:
            Number of browsers closed
        """
        try:
            current_time = time.time()
            closed_count = 0

            browsers_to_close = []
            for browser in self.browsers:
                if not browser.in_use:
                    idle_time = current_time - browser.last_used
                    if idle_time > self.idle_timeout:
                        browsers_to_close.append(browser.browser_id)

            for browser_id in browsers_to_close:
                if await self.close_browser(browser_id):
                    closed_count += 1

            if closed_count > 0:
                self.logger.info(f"Cleaned up {closed_count} idle browsers")

            return closed_count

        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")
            return 0

    async def close_all(self) -> bool:
        """
        Close all browsers in the pool.

        Returns:
            True if all closed successfully
        """
        try:
            browser_ids = [b.browser_id for b in self.browsers]

            for browser_id in browser_ids:
                await self.close_browser(browser_id)

            self.status = PoolStatus.CLOSED
            self.logger.info("Closed all browsers in pool")
            return True

        except Exception as e:
            self.logger.error(f"Failed to close all browsers: {e}")
            return False

    async def _create_browser(self) -> Optional[PooledBrowser]:
        """Create a new browser instance."""
        try:
            from playwright.async_api import async_playwright

            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            pooled_browser = PooledBrowser(
                browser_id=str(uuid4()),
                browser=browser,
                context=context,
                page=page,
                created_at=time.time(),
                last_used=time.time(),
                in_use=True,
                use_count=1,
            )

            return pooled_browser

        except Exception as e:
            self.logger.error(f"Failed to create browser: {e}")
            self.total_errors += 1
            return None

    def get_stats(self) -> PoolStats:
        """Get pool statistics."""
        active = sum(1 for b in self.browsers if b.in_use)
        idle = len(self.browsers) - active

        total_sessions = sum(b.use_count for b in self.browsers)
        avg_duration = 0.0
        if total_sessions > 0:
            total_time = sum(b.last_used - b.created_at for b in self.browsers)
            avg_duration = total_time / total_sessions

        uptime = time.time() - self.created_at

        return PoolStats(
            total_browsers=len(self.browsers),
            active_browsers=active,
            idle_browsers=idle,
            total_sessions=total_sessions,
            average_session_duration=avg_duration,
            total_errors=self.total_errors,
            uptime=uptime,
        )

    def get_browser_info(self, browser_id: str) -> Optional[dict]:
        """Get information about a specific browser."""
        for browser in self.browsers:
            if browser.browser_id == browser_id:
                return {
                    "browser_id": browser.browser_id,
                    "in_use": browser.in_use,
                    "use_count": browser.use_count,
                    "error_count": browser.error_count,
                    "created_at": browser.created_at,
                    "last_used": browser.last_used,
                    "uptime": time.time() - browser.created_at,
                }

        return None

    async def health_check(self) -> bool:
        """Check pool health."""
        try:
            # Check if any browsers are dead
            dead_browsers = []
            for browser in self.browsers:
                try:
                    if browser.page:
                        await browser.page.evaluate("1 + 1")
                except Exception:
                    dead_browsers.append(browser.browser_id)

            # Remove dead browsers
            for browser_id in dead_browsers:
                await self.close_browser(browser_id)
                self.logger.warning(f"Removed dead browser {browser_id}")

            # Cleanup idle browsers
            await self.cleanup_idle_browsers()

            return len(dead_browsers) == 0

        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False


class BrowserPoolManager:
    """Manages multiple browser pools."""

    def __init__(self):
        """Initialize pool manager."""
        self.pools: dict[str, BrowserPool] = {}
        self.logger = logger

    def create_pool(
        self,
        pool_id: str,
        max_browsers: int = 5,
        **kwargs,
    ) -> BrowserPool:
        """Create a new browser pool."""
        pool = BrowserPool(max_browsers=max_browsers, **kwargs)
        self.pools[pool_id] = pool
        self.logger.info(f"Created pool {pool_id}")
        return pool

    def get_pool(self, pool_id: str) -> Optional[BrowserPool]:
        """Get a browser pool."""
        return self.pools.get(pool_id)

    async def close_pool(self, pool_id: str) -> bool:
        """Close a browser pool."""
        pool = self.pools.pop(pool_id, None)
        if pool:
            await pool.close_all()
            self.logger.info(f"Closed pool {pool_id}")
            return True
        return False

    async def close_all_pools(self) -> bool:
        """Close all pools."""
        for pool_id in list(self.pools.keys()):
            await self.close_pool(pool_id)
        return True

    def get_all_stats(self) -> dict[str, PoolStats]:
        """Get statistics for all pools."""
        return {
            pool_id: pool.get_stats()
            for pool_id, pool in self.pools.items()
        }


# Global pool manager instance
pool_manager = BrowserPoolManager()


def create_browser_pool(
    pool_id: str,
    max_browsers: int = 5,
    **kwargs,
) -> BrowserPool:
    """Create a browser pool."""
    return pool_manager.create_pool(pool_id, max_browsers, **kwargs)


def get_browser_pool(pool_id: str) -> Optional[BrowserPool]:
    """Get a browser pool."""
    return pool_manager.get_pool(pool_id)
