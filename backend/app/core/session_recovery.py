"""Session recovery and state management for long-running conversations.

This module handles session snapshots, breakpoint recovery, and context reconstruction
to enable resuming interrupted agent runs.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class SessionSnapshot:
    """A snapshot of session state at a point in time."""

    session_id: str
    snapshot_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    iteration: int = 0
    messages: list[dict[str, str]] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionMetadata:
    """Metadata about a session."""

    session_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_snapshot_id: str | None = None
    snapshot_count: int = 0
    total_iterations: int = 0
    status: str = "active"  # active, paused, completed, failed
    metadata: dict[str, Any] = field(default_factory=dict)


class SessionRecovery:
    """Manages session snapshots and recovery for long-running conversations."""

    def __init__(self, sessions_dir: str | Path) -> None:
        """Initialize session recovery.

        Args:
            sessions_dir: Directory to store session snapshots
        """
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, SessionMetadata] = {}
        self._load_sessions_index()

    def _load_sessions_index(self) -> None:
        """Load sessions index from disk."""
        index_file = self.sessions_dir / ".sessions_index.json"
        if index_file.exists():
            try:
                data = json.loads(index_file.read_text(encoding="utf-8"))
                for session_id, metadata_dict in data.items():
                    metadata = SessionMetadata(
                        session_id=session_id,
                        created_at=datetime.fromisoformat(metadata_dict.get("created_at", "")),
                        updated_at=datetime.fromisoformat(metadata_dict.get("updated_at", "")),
                        last_snapshot_id=metadata_dict.get("last_snapshot_id"),
                        snapshot_count=metadata_dict.get("snapshot_count", 0),
                        total_iterations=metadata_dict.get("total_iterations", 0),
                        status=metadata_dict.get("status", "active"),
                        metadata=metadata_dict.get("metadata", {}),
                    )
                    self._sessions[session_id] = metadata
            except Exception as e:
                logger.warning(f"Failed to load sessions index: {e}")

    def _save_sessions_index(self) -> None:
        """Save sessions index to disk."""
        index_file = self.sessions_dir / ".sessions_index.json"
        data = {}
        for session_id, metadata in self._sessions.items():
            data[session_id] = {
                "created_at": metadata.created_at.isoformat(),
                "updated_at": metadata.updated_at.isoformat(),
                "last_snapshot_id": metadata.last_snapshot_id,
                "snapshot_count": metadata.snapshot_count,
                "total_iterations": metadata.total_iterations,
                "status": metadata.status,
                "metadata": metadata.metadata,
            }
        index_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def create_session(self, session_id: str | None = None, metadata: dict[str, Any] | None = None) -> str:
        """Create a new session.

        Args:
            session_id: Optional session ID (generated if not provided)
            metadata: Optional metadata to attach to session

        Returns:
            Session ID
        """
        session_id = session_id or str(uuid4())
        session_metadata = SessionMetadata(
            session_id=session_id,
            metadata=metadata or {},
        )
        self._sessions[session_id] = session_metadata

        # Create session directory
        session_dir = self.sessions_dir / session_id
        session_dir.mkdir(exist_ok=True)

        self._save_sessions_index()
        logger.info(f"Created session: {session_id}")
        return session_id

    def save_snapshot(self, snapshot: SessionSnapshot) -> str:
        """Save a session snapshot.

        Args:
            snapshot: SessionSnapshot to save

        Returns:
            Path where snapshot was saved
        """
        session_id = snapshot.session_id
        if session_id not in self._sessions:
            self.create_session(session_id)

        session_dir = self.sessions_dir / session_id
        session_dir.mkdir(exist_ok=True)

        # Save snapshot as JSON
        snapshot_file = session_dir / f"snapshot_{snapshot.iteration:06d}.json"
        snapshot_data = {
            "session_id": snapshot.session_id,
            "snapshot_id": snapshot.snapshot_id,
            "timestamp": snapshot.timestamp.isoformat(),
            "iteration": snapshot.iteration,
            "messages": snapshot.messages,
            "context": snapshot.context,
            "state": snapshot.state,
            "metadata": snapshot.metadata,
        }
        snapshot_file.write_text(json.dumps(snapshot_data, indent=2), encoding="utf-8")

        # Update session metadata
        metadata = self._sessions[session_id]
        metadata.last_snapshot_id = snapshot.snapshot_id
        metadata.snapshot_count += 1
        metadata.total_iterations = max(metadata.total_iterations, snapshot.iteration)
        metadata.updated_at = datetime.now(UTC)
        self._save_sessions_index()

        logger.info(f"Saved snapshot for session {session_id}: {snapshot_file}")
        return str(snapshot_file)

    def load_latest_snapshot(self, session_id: str) -> SessionSnapshot | None:
        """Load the latest snapshot for a session.

        Args:
            session_id: Session ID

        Returns:
            Latest SessionSnapshot or None if not found
        """
        session_dir = self.sessions_dir / session_id
        if not session_dir.exists():
            return None

        # Find latest snapshot file
        snapshot_files = sorted(session_dir.glob("snapshot_*.json"), reverse=True)
        if not snapshot_files:
            return None

        try:
            data = json.loads(snapshot_files[0].read_text(encoding="utf-8"))
            return SessionSnapshot(
                session_id=data.get("session_id", session_id),
                snapshot_id=data.get("snapshot_id", ""),
                timestamp=datetime.fromisoformat(data.get("timestamp", "")),
                iteration=data.get("iteration", 0),
                messages=data.get("messages", []),
                context=data.get("context", {}),
                state=data.get("state", {}),
                metadata=data.get("metadata", {}),
            )
        except Exception as e:
            logger.error(f"Failed to load snapshot: {e}")
            return None

    def load_snapshot_at_iteration(self, session_id: str, iteration: int) -> SessionSnapshot | None:
        """Load a snapshot at a specific iteration.

        Args:
            session_id: Session ID
            iteration: Iteration number

        Returns:
            SessionSnapshot or None if not found
        """
        session_dir = self.sessions_dir / session_id
        if not session_dir.exists():
            return None

        snapshot_file = session_dir / f"snapshot_{iteration:06d}.json"
        if not snapshot_file.exists():
            return None

        try:
            data = json.loads(snapshot_file.read_text(encoding="utf-8"))
            return SessionSnapshot(
                session_id=data.get("session_id", session_id),
                snapshot_id=data.get("snapshot_id", ""),
                timestamp=datetime.fromisoformat(data.get("timestamp", "")),
                iteration=data.get("iteration", 0),
                messages=data.get("messages", []),
                context=data.get("context", {}),
                state=data.get("state", {}),
                metadata=data.get("metadata", {}),
            )
        except Exception as e:
            logger.error(f"Failed to load snapshot at iteration {iteration}: {e}")
            return None

    def list_snapshots(self, session_id: str) -> list[SessionSnapshot]:
        """List all snapshots for a session.

        Args:
            session_id: Session ID

        Returns:
            List of SessionSnapshot objects
        """
        session_dir = self.sessions_dir / session_id
        if not session_dir.exists():
            return []

        snapshots = []
        for snapshot_file in sorted(session_dir.glob("snapshot_*.json")):
            try:
                data = json.loads(snapshot_file.read_text(encoding="utf-8"))
                snapshot = SessionSnapshot(
                    session_id=data.get("session_id", session_id),
                    snapshot_id=data.get("snapshot_id", ""),
                    timestamp=datetime.fromisoformat(data.get("timestamp", "")),
                    iteration=data.get("iteration", 0),
                    messages=data.get("messages", []),
                    context=data.get("context", {}),
                    state=data.get("state", {}),
                    metadata=data.get("metadata", {}),
                )
                snapshots.append(snapshot)
            except Exception as e:
                logger.warning(f"Failed to load snapshot {snapshot_file}: {e}")

        return snapshots

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its snapshots.

        Args:
            session_id: Session ID

        Returns:
            True if deleted, False if not found
        """
        if session_id not in self._sessions:
            return False

        session_dir = self.sessions_dir / session_id
        try:
            # Delete all snapshot files
            for snapshot_file in session_dir.glob("snapshot_*.json"):
                snapshot_file.unlink()

            # Delete session directory
            session_dir.rmdir()

            # Remove from index
            del self._sessions[session_id]
            self._save_sessions_index()

            logger.info(f"Deleted session: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False

    def get_session_metadata(self, session_id: str) -> SessionMetadata | None:
        """Get metadata for a session.

        Args:
            session_id: Session ID

        Returns:
            SessionMetadata or None if not found
        """
        return self._sessions.get(session_id)

    def update_session_status(self, session_id: str, status: str) -> bool:
        """Update session status.

        Args:
            session_id: Session ID
            status: New status (active, paused, completed, failed)

        Returns:
            True if updated, False if not found
        """
        if session_id not in self._sessions:
            return False

        self._sessions[session_id].status = status
        self._sessions[session_id].updated_at = datetime.now(UTC)
        self._save_sessions_index()
        return True

    def list_sessions(self, status: str | None = None) -> list[SessionMetadata]:
        """List all sessions, optionally filtered by status.

        Args:
            status: Optional status filter

        Returns:
            List of SessionMetadata objects
        """
        sessions = list(self._sessions.values())
        if status:
            sessions = [s for s in sessions if s.status == status]
        return sorted(sessions, key=lambda s: s.updated_at, reverse=True)
