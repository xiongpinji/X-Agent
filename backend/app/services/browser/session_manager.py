from __future__ import annotations

from backend.app.services.browser.playwright_client import BrowserSession, browser_client


class BrowserSessionManager:
    def create(self, **kwargs) -> BrowserSession:
        return browser_client.create_session(**kwargs)

    def get(self, session_id: str) -> BrowserSession | None:
        return browser_client.get_session(session_id)

    def close(self, session_id: str) -> bool:
        return browser_client.close_session(session_id)


browser_sessions = BrowserSessionManager()
