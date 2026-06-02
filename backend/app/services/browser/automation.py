from __future__ import annotations

from typing import Any

from backend.app.services.browser.playwright_client import BrowserActionResult, browser_client
from backend.app.services.observability.langfuse_client import langfuse_client

try:  # Playwright is an optional dependency
    from playwright.async_api import async_playwright
except Exception:  # pragma: no cover - optional import
    async_playwright = None  # type: ignore[assignment]


class BrowserAutomationService:
    def create_session(self, **kwargs: Any) -> Any:
        session = browser_client.create_session(**kwargs)
        langfuse_client.log(
            "browser.session_created",
            trace_id=session.trace_id,
            run_id=session.run_id,
            tenant_id=session.tenant_id,
            user_id=session.user_id,
            session_id=session.session_id,
        )
        return session

    def get_session(self, session_id: str) -> Any:
        return browser_client.get_session(session_id)

    def goto(self, session_id: str, url: str) -> BrowserActionResult:
        result = browser_client.goto(session_id, url)
        self._log_action(session_id, result)
        return result

    def click(self, session_id: str, selector: str) -> BrowserActionResult:
        result = browser_client.click(session_id, selector)
        self._log_action(session_id, result)
        return result

    def fill(self, session_id: str, selector: str, value: str) -> BrowserActionResult:
        result = browser_client.fill(session_id, selector, value)
        self._log_action(session_id, result)
        return result

    def screenshot(self, session_id: str, path: str) -> BrowserActionResult:
        result = browser_client.screenshot(session_id, path)
        self._log_action(session_id, result)
        return result

    def extract_text(self, session_id: str, selector: str) -> BrowserActionResult:
        result = browser_client.extract_text(session_id, selector)
        self._log_action(session_id, result)
        return result

    def wait_for(self, session_id: str, selector: str) -> BrowserActionResult:
        result = browser_client.wait_for(session_id, selector)
        self._log_action(session_id, result)
        return result

    def close(self, session_id: str) -> bool:
        closed = browser_client.close_session(session_id)
        if closed:
            langfuse_client.log("browser.session_closed", session_id=session_id)
        return closed

    def _log_action(self, session_id: str, result: BrowserActionResult) -> None:
        session = browser_client.get_session(session_id)
        langfuse_client.log(
            f"browser.{result.action}",
            session_id=session_id,
            trace_id=session.trace_id if session else None,
            run_id=session.run_id if session else None,
            tenant_id=session.tenant_id if session else None,
            user_id=session.user_id if session else None,
            ok=result.ok,
            detail=result.detail,
            **result.data,
        )


browser_automation = BrowserAutomationService()


class BrowserAutomation:
    """Async Playwright-based browser automation.

    Thin wrapper exposing an async lifecycle (initialize/navigate/...).
    Designed so individual methods can be patched in tests.
    """

    def __init__(self) -> None:
        self._playwright: Any = None
        self._browser: Any = None
        self._page: Any = None
        self._alive = False

    async def initialize(self) -> None:
        """Launch the underlying Playwright browser."""
        if async_playwright is None:
            raise RuntimeError("Playwright is not installed")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch()
        self._page = await self._browser.new_page()
        self._alive = True

    async def navigate(self, url: str) -> Any:
        """Navigate to a URL."""
        if not isinstance(url, str) or "://" not in url or " " in url.strip():
            raise ValueError(f"Invalid URL: {url!r}")
        if self._page is None:
            raise RuntimeError("Browser not initialized")
        return await self._page.goto(url)

    async def execute_script(self, script: str) -> Any:
        """Execute JavaScript in the current page."""
        if self._page is None:
            raise RuntimeError("Browser not initialized")
        return await self._page.evaluate(script)

    async def find_element(self, selector: str) -> Any:
        """Find an element by selector."""
        if self._page is None:
            raise RuntimeError("Browser not initialized")
        return await self._page.query_selector(selector)

    async def click(self, selector: str) -> Any:
        """Click an element by selector."""
        if self._page is None:
            raise RuntimeError("Browser not initialized")
        return await self._page.click(selector)

    async def type_text(self, selector: str, text: str) -> Any:
        """Type text into an element by selector."""
        if self._page is None:
            raise RuntimeError("Browser not initialized")
        return await self._page.fill(selector, text)

    async def get_content(self) -> str:
        """Return the current page's HTML content."""
        if self._page is None:
            raise RuntimeError("Browser not initialized")
        return await self._page.content()

    async def screenshot(self, path: str | None = None) -> Any:
        """Capture a screenshot of the current page."""
        if self._page is None:
            raise RuntimeError("Browser not initialized")
        if path is not None:
            return await self._page.screenshot(path=path)
        return await self._page.screenshot()

    async def get_memory_usage(self) -> int:
        """Return current browser memory usage in MB (stub)."""
        return 0

    async def is_alive(self) -> bool:
        """Return whether the browser is still running."""
        return self._alive

    async def close(self) -> None:
        """Tear down the browser and Playwright."""
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()
        self._alive = False
