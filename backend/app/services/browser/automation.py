from __future__ import annotations

import contextlib
from typing import Any
from uuid import uuid4

from backend.app.services.browser.playwright_client import (
    BrowserActionResult,
    BrowserSession,
    browser_client,
    resolve_screenshot_path,
)
from backend.app.services.observability.langfuse_client import langfuse_client

try:  # Playwright is an optional dependency
    from playwright.async_api import async_playwright
except Exception:  # pragma: no cover - optional import
    async_playwright = None  # type: ignore[assignment]


class BrowserUnavailableError(RuntimeError):
    """Raised when the real browser backend cannot be started.

    The browser automation API has no silent fallback mode: when Playwright
    (or its browser binaries) is unavailable, the service raises this error
    and the API layer answers HTTP 503 instead of returning fake success.
    """


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

    async def initialize(self, headless: bool = True) -> None:
        """Launch the underlying Playwright browser."""
        if async_playwright is None:
            raise RuntimeError("Playwright is not installed")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=headless)
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

    async def extract_text(self, selector: str) -> str:
        """Return the inner text of the element matching selector."""
        if self._page is None:
            raise RuntimeError("Browser not initialized")
        return await self._page.inner_text(selector, timeout=5000)

    async def wait_for(self, selector: str) -> Any:
        """Wait for an element matching selector to appear."""
        if self._page is None:
            raise RuntimeError("Browser not initialized")
        return await self._page.wait_for_selector(selector, timeout=10000)

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


class BrowserAutomationService:
    """Session-scoped browser automation backed by async Playwright.

    Each session owns a real browser via ``BrowserAutomation``. There is
    intentionally no in-memory fallback: the previous sync-Playwright client
    could never start a browser inside the FastAPI event loop and silently
    returned success for no-op actions. When the browser backend is
    unavailable, ``create_session`` raises ``BrowserUnavailableError`` and the
    API layer answers HTTP 503.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, BrowserSession] = {}
        self._automation: dict[str, BrowserAutomation] = {}

    async def create_session(self, **kwargs: Any) -> BrowserSession:
        if async_playwright is None:
            raise BrowserUnavailableError(
                "Playwright is not installed; browser automation backend is unavailable."
            )
        headless = bool(kwargs.pop("headless", True))
        automation = BrowserAutomation()
        try:
            await automation.initialize(headless=headless)
        except Exception as exc:
            with contextlib.suppress(Exception):
                await automation.close()
            raise BrowserUnavailableError(f"Failed to launch browser backend: {exc}") from exc
        session = BrowserSession(
            session_id=str(uuid4()),
            trace_id=kwargs.get("trace_id"),
            run_id=kwargs.get("run_id"),
            tenant_id=kwargs.get("tenant_id", "default"),
            user_id=kwargs.get("user_id", "anonymous"),
            managed=True,
        )
        self._sessions[session.session_id] = session
        self._automation[session.session_id] = automation
        langfuse_client.log(
            "browser.session_created",
            trace_id=session.trace_id,
            run_id=session.run_id,
            tenant_id=session.tenant_id,
            user_id=session.user_id,
            session_id=session.session_id,
        )
        return session

    def get_session(self, session_id: str) -> BrowserSession | None:
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[BrowserSession]:
        return list(self._sessions.values())

    async def goto(self, session_id: str, url: str) -> BrowserActionResult:
        session, automation = self._require(session_id)
        try:
            await automation.navigate(url)
            result = session.record("goto", True, url=url, navigation_kind="real")
        except Exception as exc:
            result = session.record("goto", False, detail=f"goto failed: {exc}", url=url, navigation_kind="real")
        self._log_action(session_id, result)
        return result

    async def click(self, session_id: str, selector: str) -> BrowserActionResult:
        session, automation = self._require(session_id)
        try:
            browser_client._validate_selector(selector)
            await automation.click(selector)
            result = session.record("click", True, selector=selector, execution_mode="real")
        except Exception as exc:
            result = session.record("click", False, detail=f"Click failed: {exc}", selector=selector)
        self._log_action(session_id, result)
        return result

    async def fill(self, session_id: str, selector: str, value: str) -> BrowserActionResult:
        session, automation = self._require(session_id)
        try:
            browser_client._validate_selector(selector)
            await automation.type_text(selector, value)
            result = session.record("fill", True, selector=selector, value=value, execution_mode="real")
        except Exception as exc:
            result = session.record("fill", False, detail=f"Fill failed: {exc}", selector=selector, value=value)
        self._log_action(session_id, result)
        return result

    async def screenshot(self, session_id: str, path: str) -> BrowserActionResult:
        import os

        session, automation = self._require(session_id)
        try:
            real_path = resolve_screenshot_path(path)
            os.makedirs(os.path.dirname(real_path), exist_ok=True)
            await automation.screenshot(path=real_path)
            result = session.record("screenshot", True, path=real_path, execution_mode="real")
        except Exception as exc:
            result = session.record("screenshot", False, detail=f"Screenshot failed: {exc}", path=path)
        self._log_action(session_id, result)
        return result

    async def extract_text(self, session_id: str, selector: str) -> BrowserActionResult:
        session, automation = self._require(session_id)
        try:
            browser_client._validate_selector(selector)
            text = await automation.extract_text(selector)
            result = session.record("extract_text", True, selector=selector, text=text, execution_mode="real")
        except Exception as exc:
            result = session.record("extract_text", False, detail=f"Extract text failed: {exc}", selector=selector)
        self._log_action(session_id, result)
        return result

    async def wait_for(self, session_id: str, selector: str) -> BrowserActionResult:
        session, automation = self._require(session_id)
        try:
            browser_client._validate_selector(selector)
            await automation.wait_for(selector)
            result = session.record("wait_for", True, selector=selector, execution_mode="real")
        except Exception as exc:
            result = session.record("wait_for", False, detail=f"Wait for failed: {exc}", selector=selector)
        self._log_action(session_id, result)
        return result

    async def close(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session is None:
            return False
        automation = self._automation.pop(session_id, None)
        if automation is not None:
            with contextlib.suppress(Exception):
                await automation.close()
        session.active = False
        langfuse_client.log("browser.session_closed", session_id=session_id)
        return True

    def _require(self, session_id: str) -> tuple[BrowserSession, BrowserAutomation]:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Browser session not found: {session_id}")
        if not session.active:
            raise RuntimeError(f"Browser session is closed: {session_id}")
        automation = self._automation.get(session_id)
        if automation is None:
            raise BrowserUnavailableError(
                f"Browser backend missing for session: {session_id}"
            )
        return session, automation

    def _log_action(self, session_id: str, result: BrowserActionResult) -> None:
        session = self._sessions.get(session_id)
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
