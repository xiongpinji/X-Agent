from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

try:
    from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
except ImportError:  # pragma: no cover - optional runtime dependency
    Browser = BrowserContext = Page = object  # type: ignore[assignment]
    sync_playwright = None  # type: ignore[assignment]


def resolve_screenshot_path(path: str) -> str:
    """Validate a screenshot output path and return its normalized absolute form.

    Restricts writes to temp-like directories to prevent directory traversal
    attacks. Shared by the sync client and the async automation service.
    """
    import os
    from pathlib import Path

    # Get the real absolute path
    real_path = os.path.realpath(os.path.expanduser(path))

    # Define allowed base directories
    allowed_bases = [
        os.path.realpath("/tmp"),
        os.path.realpath("/var/tmp"),
        os.path.realpath(os.path.expanduser("~/xagent_screenshots")),
    ]

    # On Windows, add temp directory
    if os.name == "nt":
        allowed_bases.append(os.path.realpath(os.environ.get("TEMP", "C:\\Temp")))

    # Verify the real path is within allowed directories
    is_allowed = False
    for base in allowed_bases:
        try:
            Path(real_path).relative_to(base)
            is_allowed = True
            break
        except ValueError:
            continue

    if not is_allowed:
        raise ValueError(f"Screenshot path must be within allowed directories: {allowed_bases}")

    return real_path


@dataclass(slots=True)
class BrowserActionResult:
    action: str
    ok: bool
    detail: str = ""
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BrowserSession:
    session_id: str
    trace_id: str | None = None
    run_id: str | None = None
    tenant_id: str = "default"
    user_id: str = "anonymous"
    current_url: str | None = None
    active: bool = True
    actions: list[BrowserActionResult] = field(default_factory=list)
    browser: Any = None
    context: Any = None
    page: Any = None
    managed: bool = False

    def record(self, action: str, ok: bool, detail: str = "", **data: Any) -> BrowserActionResult:
        enriched = dict(data)
        if self.page is not None:
            with contextlib.suppress(Exception):
                enriched.setdefault("page_url", self.page.url)
            with contextlib.suppress(Exception):
                enriched.setdefault("page_title", self.page.title())
        result = BrowserActionResult(action=action, ok=ok, detail=detail, data=enriched)
        self.actions.append(result)
        if "url" in data:
            self.current_url = str(data["url"])
        elif "page_url" in enriched:
            self.current_url = str(enriched["page_url"])
        return result


class PlaywrightBrowserClient:
    """Playwright-backed browser client with in-memory fallback."""

    # CSS selector complexity limits
    _MAX_SELECTOR_LENGTH = 500
    _MAX_SELECTOR_DEPTH = 10
    _DANGEROUS_PATTERNS = [
        r"\*:nth-child\(\d{4,}\)",  # nth-child with large numbers
        r":has\(",  # :has() can be expensive
        r":is\(",  # :is() with many selectors
        r":where\(",  # :where() with many selectors
    ]

    def __init__(self) -> None:
        self._sessions: dict[str, BrowserSession] = {}

    @property
    def has_real_client(self) -> bool:
        try:
            return sync_playwright is not None and not asyncio.get_running_loop().is_running()
        except RuntimeError:
            return sync_playwright is not None

    def _validate_selector(self, selector: str) -> None:
        """Validate CSS selector to prevent DoS attacks and injection.

        Raises ValueError if selector is invalid or dangerous.
        """
        import re

        # Check length
        if len(selector) > self._MAX_SELECTOR_LENGTH:
            raise ValueError(f"Selector too long (max {self._MAX_SELECTOR_LENGTH} chars)")

        # Check depth (count commas and combinators)
        depth = selector.count(",") + selector.count(">") + selector.count("+") + selector.count("~")
        if depth > self._MAX_SELECTOR_DEPTH:
            raise ValueError(f"Selector too complex (max depth {self._MAX_SELECTOR_DEPTH})")

        # Check for dangerous patterns
        for pattern in self._DANGEROUS_PATTERNS:
            if re.search(pattern, selector):
                raise ValueError(f"Selector contains dangerous pattern: {pattern}")

        # Basic syntax validation - ensure balanced parentheses and brackets
        if selector.count("(") != selector.count(")"):
            raise ValueError("Selector has unbalanced parentheses")
        if selector.count("[") != selector.count("]"):
            raise ValueError("Selector has unbalanced brackets")

    def create_session(
        self,
        *,
        trace_id: str | None = None,
        run_id: str | None = None,
        tenant_id: str = "default",
        user_id: str = "anonymous",
        headless: bool = True,
    ) -> BrowserSession:
        session = BrowserSession(
            session_id=str(uuid4()),
            trace_id=trace_id,
            run_id=run_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        if sync_playwright is not None:
            try:
                loop_running = asyncio.get_running_loop().is_running()
            except RuntimeError:
                loop_running = False
            if not loop_running:
                playwright = sync_playwright().start()
                browser = playwright.chromium.launch(headless=headless)
                context = browser.new_context()
                page = context.new_page()
                session.browser = browser
                session.context = context
                session.page = page
                session.managed = True
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> BrowserSession | None:
        return self._sessions.get(session_id)

    def close_session(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session is None:
            return False
        if session.managed:
            try:
                if session.page is not None:
                    session.page.close()
                if session.context is not None:
                    session.context.close()
                if session.browser is not None:
                    session.browser.close()
            finally:
                session.active = False
        else:
            session.active = False
        return True

    def goto(self, session_id: str, url: str) -> BrowserActionResult:
        session = self._require_session(session_id)
        if session.page is None:
            # No silent fake success: fallback sessions cannot execute actions.
            return session.record("goto", False, detail="Real browser unavailable; fallback navigation is not executed.", url=url, navigation_kind="fallback")
        session.page.goto(url, wait_until="domcontentloaded")
        return session.record("goto", True, url=url, navigation_kind="real")

    def click(self, session_id: str, selector: str) -> BrowserActionResult:
        """Click element with selector validation and timeout protection."""
        session = self._require_session(session_id)
        try:
            self._validate_selector(selector)
            if session.page is None:
                # No silent fake success: fallback sessions cannot execute actions.
                raise RuntimeError("Real browser unavailable; fallback click is not executed.")
            # Set timeout to prevent hanging on complex selectors
            session.page.click(selector, timeout=5000)  # 5 second timeout
            return session.record("click", True, selector=selector, execution_mode="real")
        except Exception as e:
            return session.record("click", False, detail=f"Click failed: {e!s}", selector=selector)

    def fill(self, session_id: str, selector: str, value: str) -> BrowserActionResult:
        """Fill input field with selector validation and timeout protection."""
        session = self._require_session(session_id)
        try:
            self._validate_selector(selector)
            if session.page is None:
                # No silent fake success: fallback sessions cannot execute actions.
                raise RuntimeError("Real browser unavailable; fallback fill is not executed.")
            # Set timeout to prevent hanging on complex selectors
            session.page.fill(selector, value, timeout=5000)  # 5 second timeout
            return session.record("fill", True, selector=selector, value=value, execution_mode="real")
        except Exception as e:
            return session.record("fill", False, detail=f"Fill failed: {e!s}", selector=selector, value=value)

    def screenshot(self, session_id: str, path: str) -> BrowserActionResult:
        """Take a screenshot with strict path validation to prevent directory traversal attacks."""
        import os

        session = self._require_session(session_id)

        # Validate and normalize the path
        try:
            real_path = resolve_screenshot_path(path)

            # Ensure parent directory exists
            os.makedirs(os.path.dirname(real_path), exist_ok=True)

            if session.page is None:
                # No silent fake success: fallback sessions cannot execute actions.
                raise RuntimeError("Real browser unavailable; fallback screenshot is not executed.")
            session.page.screenshot(path=real_path, full_page=True)

            return session.record("screenshot", True, path=real_path, execution_mode="real")
        except Exception as e:
            return session.record("screenshot", False, detail=f"Screenshot failed: {e!s}", path=path)

    def extract_text(self, session_id: str, selector: str) -> BrowserActionResult:
        """Extract text with selector validation and timeout protection."""
        session = self._require_session(session_id)
        text = ""
        try:
            self._validate_selector(selector)
            if session.page is None:
                # No silent fake success: fallback sessions cannot execute actions.
                raise RuntimeError("Real browser unavailable; fallback extract_text is not executed.")
            # Set timeout to prevent hanging on complex selectors
            text = session.page.locator(selector).inner_text(timeout=5000)
            return session.record("extract_text", True, selector=selector, text=text, execution_mode="real")
        except Exception as e:
            return session.record("extract_text", False, detail=f"Extract text failed: {e!s}", selector=selector)

    def wait_for(self, session_id: str, selector: str) -> BrowserActionResult:
        """Wait for element with selector validation and timeout protection."""
        session = self._require_session(session_id)
        try:
            self._validate_selector(selector)
            if session.page is None:
                # No silent fake success: fallback sessions cannot execute actions.
                raise RuntimeError("Real browser unavailable; fallback wait_for is not executed.")
            # Set timeout to prevent hanging on complex selectors
            session.page.wait_for_selector(selector, timeout=10000)  # 10 second timeout
            return session.record("wait_for", True, selector=selector, execution_mode="real")
        except Exception as e:
            return session.record("wait_for", False, detail=f"Wait for failed: {e!s}", selector=selector)

    def _require_session(self, session_id: str) -> BrowserSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Browser session not found: {session_id}")
        if not session.active:
            raise RuntimeError(f"Browser session is closed: {session_id}")
        return session


browser_client = PlaywrightBrowserClient()
