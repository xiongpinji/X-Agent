"""Authenticated session model and in-memory session store."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Session:
    """Represents an authenticated user session.

    Parameters
    ----------
    session_id:
        Unique identifier for the session.
    user_id:
        Identifier of the authenticated user.
    issued_at:
        Unix timestamp when the session was created.
    expires_at:
        Unix timestamp when the session expires.
    data:
        Arbitrary session-scoped metadata.
    """

    session_id: str
    user_id: str
    issued_at: int
    expires_at: int
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        """Whether the session has not yet expired."""
        return self.expires_at > int(time.time())


class SessionStore:
    """Thread-safe in-memory session store.

    Intended for development/testing or single-process deployments. For
    distributed setups, replace with a persistent store (e.g. Redis) that
    implements the same interface.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.RLock()

    def create(
        self, session_id: str, user_id: str, *, ttl: int = 86_400, **data: Any
    ) -> Session:
        """Create and store a new session."""
        now = int(time.time())
        session = Session(
            session_id=session_id,
            user_id=user_id,
            issued_at=now,
            expires_at=now + ttl,
            data=data,
        )
        with self._lock:
            self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        """Retrieve a session by id, or ``None`` if missing/expired."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or not session.is_active:
                return None
            return session

    def revoke(self, session_id: str) -> bool:
        """Revoke (remove) a session. Returns ``True`` if it existed."""
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def revoke_all_for_user(self, user_id: str) -> int:
        """Revoke every session belonging to ``user_id``.

        Returns the number of sessions revoked.
        """
        revoked = 0
        with self._lock:
            for session_id in list(self._sessions):
                if self._sessions[session_id].user_id == user_id:
                    del self._sessions[session_id]
                    revoked += 1
        return revoked

    def cleanup_expired(self) -> int:
        """Remove all expired sessions. Returns the number removed."""
        now = int(time.time())
        removed = 0
        with self._lock:
            for session_id in list(self._sessions):
                if self._sessions[session_id].expires_at <= now:
                    del self._sessions[session_id]
                    removed += 1
        return removed
