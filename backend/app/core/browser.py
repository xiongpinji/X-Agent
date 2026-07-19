from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from uuid import uuid4

from pydantic import BaseModel, Field


class BrowserActionResult(BaseModel):
    action: str
    ok: bool = True
    detail: str = ""
    data: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BrowserSessionRecord(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str | None = None
    run_id: str | None = None
    tenant_id: str = "default"
    user_id: str = "anonymous"
    current_url: str | None = None
    active: bool = True
    actions: list[BrowserActionResult] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


@dataclass
class BrowserAutomationStore:
    _sessions: dict[str, BrowserSessionRecord] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    def create_session(self, *, trace_id: str | None = None, run_id: str | None = None, tenant_id: str = "default", user_id: str = "anonymous") -> BrowserSessionRecord:
        session = BrowserSessionRecord(
            trace_id=trace_id,
            run_id=run_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def list_sessions(self) -> list[BrowserSessionRecord]:
        sessions = list(self._sessions.values())
        sessions.sort(key=lambda item: item.updated_at, reverse=True)
        return sessions

    def get_session(self, session_id: str) -> BrowserSessionRecord | None:
        return self._sessions.get(session_id)

    def goto(self, session_id: str, url: str) -> BrowserActionResult:
        return self._append_action(session_id, "goto", data={"url": url}, detail=f"Navigated to {url}")

    def click(self, session_id: str, selector: str) -> BrowserActionResult:
        return self._append_action(session_id, "click", data={"selector": selector}, detail=f"Clicked {selector}")

    def fill(self, session_id: str, selector: str, value: str) -> BrowserActionResult:
        return self._append_action(session_id, "fill", data={"selector": selector, "value": value}, detail=f"Filled {selector}")

    def extract_text(self, session_id: str, selector: str) -> BrowserActionResult:
        return self._append_action(session_id, "extract_text", data={"selector": selector, "text": f"mock text from {selector}"}, detail="Text extracted")

    def wait_for(self, session_id: str, selector: str) -> BrowserActionResult:
        return self._append_action(session_id, "wait_for", data={"selector": selector}, detail=f"Waited for {selector}")

    def screenshot(self, session_id: str, path: str) -> BrowserActionResult:
        return self._append_action(session_id, "screenshot", data={"path": path}, detail=f"Screenshot saved to {path}")

    def close(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return False
            session.active = False
            session.updated_at = datetime.now(UTC)
            return True

    def _append_action(self, session_id: str, action: str, *, data: dict[str, object] | None = None, detail: str = "") -> BrowserActionResult:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return BrowserActionResult(action=action, ok=False, detail=f"Browser session not found: {session_id}")
            result = BrowserActionResult(action=action, ok=True, detail=detail, data=data or {})
            session.actions.append(result)
            if action == "goto":
                session.current_url = str((data or {}).get("url"))
            session.updated_at = datetime.now(UTC)
            return result


browser_automation_store = BrowserAutomationStore()
