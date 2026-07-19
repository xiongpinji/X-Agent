from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from uuid import uuid4

from pydantic import BaseModel, Field


class DesktopActionResult(BaseModel):
    action: str
    target: str | None = None
    value: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    ok: bool = True
    detail: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DesktopSessionRecord(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str | None = None
    run_id: str | None = None
    tenant_id: str = "default"
    user_id: str = "anonymous"
    provider: str = "ui-tars"
    metadata: dict[str, object] = Field(default_factory=dict)
    active: bool = True
    actions: list[DesktopActionResult] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


@dataclass
class DesktopAutomationStore:
    _sessions: dict[str, DesktopSessionRecord] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    def create_session(
        self,
        *,
        trace_id: str | None = None,
        run_id: str | None = None,
        tenant_id: str = "default",
        user_id: str = "anonymous",
        provider: str = "ui-tars",
        metadata: dict[str, object] | None = None,
    ) -> DesktopSessionRecord:
        session = DesktopSessionRecord(
            trace_id=trace_id,
            run_id=run_id,
            tenant_id=tenant_id,
            user_id=user_id,
            provider=provider,
            metadata=metadata or {},
        )
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def list_sessions(self) -> list[DesktopSessionRecord]:
        sessions = list(self._sessions.values())
        sessions.sort(key=lambda item: item.updated_at, reverse=True)
        return sessions

    def get_session(self, session_id: str) -> DesktopSessionRecord | None:
        return self._sessions.get(session_id)

    def send_action(self, session_id: str, action: str, target: str | None = None, value: str | None = None, metadata: dict[str, object] | None = None) -> DesktopActionResult:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return DesktopActionResult(action=action, target=target, value=value, metadata=metadata or {}, ok=False, detail=f"Desktop session not found: {session_id}")
            result = DesktopActionResult(action=action, target=target, value=value, metadata=metadata or {}, ok=True, detail=f"Action accepted: {action}")
            session.actions.append(result)
            session.updated_at = datetime.now(UTC)
            return result

    def close(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return False
            session.active = False
            session.updated_at = datetime.now(UTC)
            return True


desktop_automation_store = DesktopAutomationStore()
