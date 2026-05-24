from __future__ import annotations

from backend.app.services.browser.playwright_client import BrowserActionResult, browser_client
from backend.app.services.observability.langfuse_client import langfuse_client


class BrowserAutomationService:
    def create_session(self, **kwargs):
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

    def get_session(self, session_id: str):
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
