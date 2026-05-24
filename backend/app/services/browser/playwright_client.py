from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import asyncio

try:
    from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
except ImportError:  # pragma: no cover - optional runtime dependency
    Browser = BrowserContext = Page = object  # type: ignore[assignment]
    sync_playwright = None  # type: ignore[assignment]


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
            try:
                enriched.setdefault("page_url", self.page.url)
            except Exception:
                pass
            try:
                enriched.setdefault("page_title", self.page.title())
            except Exception:
                pass
        result = BrowserActionResult(action=action, ok=ok, detail=detail, data=enriched)
        self.actions.append(result)
        if "url" in data:
            self.current_url = str(data["url"])
        elif "page_url" in enriched:
            self.current_url = str(enriched["page_url"])
        return result


class PlaywrightBrowserClient:
    """Playwright-backed browser client with in-memory fallback."""

    def __init__(self) -> None:
        self._sessions: dict[str, BrowserSession] = {}

    @property
    def has_real_client(self) -> bool:
        try:
            return sync_playwright is not None and not asyncio.get_running_loop().is_running()
        except RuntimeError:
            return sync_playwright is not None

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
        if session.page is not None:
            session.page.goto(url, wait_until="domcontentloaded")
        return session.record("goto", True, url=url, navigation_kind="real" if session.page is not None else "fallback")

    def click(self, session_id: str, selector: str) -> BrowserActionResult:
        session = self._require_session(session_id)
        if session.page is not None:
            session.page.click(selector)
        return session.record("click", True, selector=selector, execution_mode="real" if session.page is not None else "fallback")

    def fill(self, session_id: str, selector: str, value: str) -> BrowserActionResult:
        session = self._require_session(session_id)
        if session.page is not None:
            session.page.fill(selector, value)
        return session.record("fill", True, selector=selector, value=value, execution_mode="real" if session.page is not None else "fallback")

    def screenshot(self, session_id: str, path: str) -> BrowserActionResult:
        session = self._require_session(session_id)
        if session.page is not None:
            session.page.screenshot(path=path, full_page=True)
        return session.record("screenshot", True, path=path, execution_mode="real" if session.page is not None else "fallback")

    def extract_text(self, session_id: str, selector: str) -> BrowserActionResult:
        session = self._require_session(session_id)
        text = ""
        if session.page is not None:
            text = session.page.locator(selector).inner_text()
        return session.record("extract_text", True, selector=selector, text=text, execution_mode="real" if session.page is not None else "fallback")

    def wait_for(self, session_id: str, selector: str) -> BrowserActionResult:
        session = self._require_session(session_id)
        if session.page is not None:
            session.page.wait_for_selector(selector)
        return session.record("wait_for", True, selector=selector, execution_mode="real" if session.page is not None else "fallback")

    def _require_session(self, session_id: str) -> BrowserSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Browser session not found: {session_id}")
        if not session.active:
            raise RuntimeError(f"Browser session is closed: {session_id}")
        return session


browser_client = PlaywrightBrowserClient()
