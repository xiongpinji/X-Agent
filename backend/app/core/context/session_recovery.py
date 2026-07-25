"""Session recovery and persistence system for X-Agent.

Handles saving and restoring conversation sessions with full state management.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Represents a single message in the conversation."""

    id: str = field(default_factory=lambda: str(uuid4()))
    role: str = "user"  # user, assistant, system, tool
    content: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict = field(default_factory=dict)
    importance: float = 0.5
    compressed: bool = False
    token_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "importance": self.importance,
            "compressed": self.compressed,
            "token_count": self.token_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        """Create from dictionary."""
        data = data.copy()
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


@dataclass
class SessionState:
    """Complete state of a conversation session."""

    session_id: str = field(default_factory=lambda: str(uuid4()))
    agent_id: str = ""
    tenant_id: str = ""
    messages: list[Message] = field(default_factory=list)
    context_window: int = 128_000
    compression_history: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_checkpoint: datetime = field(default_factory=lambda: datetime.now(UTC))
    total_tokens: int = 0
    compressed_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "tenant_id": self.tenant_id,
            "messages": [msg.to_dict() for msg in self.messages],
            "context_window": self.context_window,
            "compression_history": self.compression_history,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_checkpoint": self.last_checkpoint.isoformat(),
            "total_tokens": self.total_tokens,
            "compressed_tokens": self.compressed_tokens,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionState:
        """Create from dictionary."""
        data = data.copy()
        messages = [Message.from_dict(msg) for msg in data.pop("messages", [])]
        for key in ["created_at", "updated_at", "last_checkpoint"]:
            if isinstance(data.get(key), str):
                data[key] = datetime.fromisoformat(data[key])
        return cls(messages=messages, **data)


@dataclass
class SessionSnapshot:
    """Snapshot metadata for a saved session."""

    snapshot_id: str = field(default_factory=lambda: str(uuid4()))
    session_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    message_count: int = 0
    token_count: int = 0
    compressed_token_count: int = 0
    compression_ratio: float = 1.0
    storage_path: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "snapshot_id": self.snapshot_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "message_count": self.message_count,
            "token_count": self.token_count,
            "compressed_token_count": self.compressed_token_count,
            "compression_ratio": self.compression_ratio,
            "storage_path": self.storage_path,
            "metadata": self.metadata,
        }


@dataclass
class SessionMetadata:
    """Metadata for a session in the list."""

    session_id: str
    agent_id: str
    title: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    message_count: int = 0
    token_count: int = 0
    last_snapshot: datetime | None = None
    tenant_id: str = ""


@dataclass
class SessionStats:
    """Statistics for a session."""

    session_id: str
    message_count: int
    total_tokens: int
    compressed_tokens: int
    compression_ratio: float
    compression_count: int
    created_at: datetime
    updated_at: datetime
    last_checkpoint: datetime
    storage_size_mb: float


class SessionRecovery:
    """Manages session persistence and recovery.

    Features:
    - Session state snapshots to filesystem
    - Session restoration with full context
    - Session metadata management
    - Automatic cleanup of old sessions
    """

    def __init__(
        self,
        storage_path: str | Path = "~/.xagent/sessions",
        snapshot_interval_seconds: int = 300,
        retention_days: int = 30,
    ) -> None:
        """Initialize session recovery system.

        Args:
            storage_path: Base path for session storage
            snapshot_interval_seconds: Interval for automatic snapshots
            retention_days: Days to retain old sessions
        """
        self.storage_path = Path(storage_path).expanduser()
        self.snapshot_interval_seconds = snapshot_interval_seconds
        self.retention_days = retention_days

        # Create storage directory
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # In-memory cache of session metadata
        self._session_cache: dict[str, SessionMetadata] = {}
        self._lock = asyncio.Lock()

        logger.info(f"SessionRecovery initialized with storage path: {self.storage_path}")

    async def save_snapshot(
        self,
        session_state: SessionState,
    ) -> SessionSnapshot:
        """Save a session snapshot to disk.

        Args:
            session_state: Session state to save

        Returns:
            SessionSnapshot with metadata
        """
        async with self._lock:
            try:
                # Create session directory
                session_dir = self.storage_path / session_state.session_id
                session_dir.mkdir(parents=True, exist_ok=True)

                # Create snapshot
                snapshot = SessionSnapshot(
                    session_id=session_state.session_id,
                    timestamp=datetime.now(UTC),
                    message_count=len(session_state.messages),
                    token_count=session_state.total_tokens,
                    compressed_token_count=session_state.compressed_tokens,
                    compression_ratio=(
                        session_state.compressed_tokens / session_state.total_tokens
                        if session_state.total_tokens > 0
                        else 1.0
                    ),
                    storage_path=str(session_dir),
                    metadata=session_state.metadata,
                )

                # Save state to file
                state_file = session_dir / "state.json"
                state_data = session_state.to_dict()
                state_file.write_text(json.dumps(state_data, indent=2))

                # Save snapshot metadata
                snapshot_file = session_dir / f"snapshot_{snapshot.snapshot_id}.json"
                snapshot_file.write_text(json.dumps(snapshot.to_dict(), indent=2))

                # Update metadata index
                metadata_file = session_dir / "metadata.json"
                metadata = SessionMetadata(
                    session_id=session_state.session_id,
                    agent_id=session_state.agent_id,
                    title=session_state.metadata.get("title", ""),
                    created_at=session_state.created_at,
                    updated_at=datetime.now(UTC),
                    message_count=len(session_state.messages),
                    token_count=session_state.total_tokens,
                    last_snapshot=datetime.now(UTC),
                    tenant_id=session_state.tenant_id,
                )
                metadata_file.write_text(json.dumps(asdict(metadata), indent=2, default=str))

                # Update cache
                self._session_cache[session_state.session_id] = metadata

                logger.info(
                    f"Saved session snapshot: {session_state.session_id} "
                    f"({len(session_state.messages)} messages, "
                    f"{session_state.total_tokens} tokens)"
                )

                return snapshot

            except Exception as e:
                logger.error(f"Failed to save session snapshot: {e}")
                raise

    async def load_snapshot(
        self,
        session_id: str,
    ) -> SessionState | None:
        """Load a session snapshot from disk.

        Args:
            session_id: Session ID to load

        Returns:
            SessionState if found, None otherwise
        """
        async with self._lock:
            try:
                session_dir = self.storage_path / session_id
                state_file = session_dir / "state.json"

                if not state_file.exists():
                    logger.warning(f"Session not found: {session_id}")
                    return None

                # Load state from file
                state_data = json.loads(state_file.read_text())
                session_state = SessionState.from_dict(state_data)

                logger.info(
                    f"Loaded session snapshot: {session_id} "
                    f"({len(session_state.messages)} messages)"
                )

                return session_state

            except Exception as e:
                logger.error(f"Failed to load session snapshot: {e}")
                return None

    async def list_sessions(
        self,
        agent_id: str | None = None,
        limit: int = 100,
        tenant_id: str | None = None,
    ) -> list[SessionMetadata]:
        """List all sessions.

        Args:
            agent_id: Filter by agent ID (optional)
            limit: Maximum number of sessions to return
            tenant_id: Filter by tenant ID (optional); 传入时只返回该租户的会话，
                无 tenant_id 的旧元数据视为不属于任何指定租户。

        Returns:
            List of session metadata
        """
        async with self._lock:
            try:
                sessions = []

                for session_dir in self.storage_path.iterdir():
                    if not session_dir.is_dir():
                        continue

                    metadata_file = session_dir / "metadata.json"
                    if not metadata_file.exists():
                        continue

                    try:
                        metadata_data = json.loads(metadata_file.read_text())
                        metadata = SessionMetadata(
                            session_id=metadata_data["session_id"],
                            agent_id=metadata_data["agent_id"],
                            title=metadata_data.get("title", ""),
                            created_at=datetime.fromisoformat(metadata_data["created_at"]),
                            updated_at=datetime.fromisoformat(metadata_data["updated_at"]),
                            message_count=metadata_data["message_count"],
                            token_count=metadata_data["token_count"],
                            last_snapshot=(
                                datetime.fromisoformat(metadata_data["last_snapshot"])
                                if metadata_data.get("last_snapshot")
                                else None
                            ),
                            tenant_id=metadata_data.get("tenant_id", ""),
                        )

                        if agent_id is not None and metadata.agent_id != agent_id:
                            continue
                        if tenant_id is not None and metadata.tenant_id != tenant_id:
                            continue
                        sessions.append(metadata)

                    except Exception as e:
                        logger.warning(f"Failed to load metadata for {session_dir}: {e}")
                        continue

                # Sort by updated_at descending
                sessions.sort(key=lambda x: x.updated_at, reverse=True)

                return sessions[:limit]

            except Exception as e:
                logger.error(f"Failed to list sessions: {e}")
                return []

    async def delete_session(
        self,
        session_id: str,
    ) -> bool:
        """Delete a session.

        Args:
            session_id: Session ID to delete

        Returns:
            True if successful, False otherwise
        """
        async with self._lock:
            try:
                session_dir = self.storage_path / session_id

                if not session_dir.exists():
                    logger.warning(f"Session not found: {session_id}")
                    return False

                # Remove directory and all contents
                import shutil

                shutil.rmtree(session_dir)

                # Remove from cache
                self._session_cache.pop(session_id, None)

                logger.info(f"Deleted session: {session_id}")

                return True

            except Exception as e:
                logger.error(f"Failed to delete session: {e}")
                return False

    async def get_session_stats(
        self,
        session_id: str,
    ) -> SessionStats | None:
        """Get statistics for a session.

        Args:
            session_id: Session ID

        Returns:
            SessionStats if found, None otherwise
        """
        # NOTE: do NOT hold self._lock here. load_snapshot() acquires the same
        # non-reentrant asyncio.Lock internally; wrapping it in `async with
        # self._lock` deadlocks (asyncio.Lock is not reentrant). The remaining
        # work is read-only filesystem access that needs no extra serialization.
        try:
            session_state = await self.load_snapshot(session_id)
            if not session_state:
                return None

            session_dir = self.storage_path / session_id
            storage_size_mb = sum(
                f.stat().st_size for f in session_dir.rglob("*") if f.is_file()
            ) / (1024 * 1024)

            return SessionStats(
                session_id=session_id,
                message_count=len(session_state.messages),
                total_tokens=session_state.total_tokens,
                compressed_tokens=session_state.compressed_tokens,
                compression_ratio=(
                    session_state.compressed_tokens / session_state.total_tokens
                    if session_state.total_tokens > 0
                    else 1.0
                ),
                compression_count=len(session_state.compression_history),
                created_at=session_state.created_at,
                updated_at=session_state.updated_at,
                last_checkpoint=session_state.last_checkpoint,
                storage_size_mb=storage_size_mb,
            )

        except Exception as e:
            logger.error(f"Failed to get session stats: {e}")
            return None

    async def cleanup_old_sessions(self) -> int:
        """Clean up sessions older than retention period.

        Returns:
            Number of sessions deleted
        """
        async with self._lock:
            try:
                cutoff_date = datetime.now(UTC) - timedelta(days=self.retention_days)
                deleted_count = 0

                for session_dir in self.storage_path.iterdir():
                    if not session_dir.is_dir():
                        continue

                    metadata_file = session_dir / "metadata.json"
                    if not metadata_file.exists():
                        continue

                    try:
                        metadata_data = json.loads(metadata_file.read_text())
                        updated_at = datetime.fromisoformat(metadata_data["updated_at"])

                        if updated_at < cutoff_date:
                            import shutil

                            shutil.rmtree(session_dir)
                            deleted_count += 1

                    except Exception as e:
                        logger.warning(f"Failed to process {session_dir}: {e}")
                        continue

                logger.info(f"Cleaned up {deleted_count} old sessions")

                return deleted_count

            except Exception as e:
                logger.error(f"Failed to cleanup old sessions: {e}")
                return 0

    async def export_session(
        self,
        session_id: str,
        export_path: str | Path,
    ) -> bool:
        """Export a session to a file.

        Args:
            session_id: Session ID to export
            export_path: Path to export to

        Returns:
            True if successful, False otherwise
        """
        # NOTE: load_snapshot() acquires self._lock internally; do not wrap it
        # in `async with self._lock` (non-reentrant asyncio.Lock → deadlock).
        try:
            session_state = await self.load_snapshot(session_id)
            if not session_state:
                return False

            export_path = Path(export_path)
            export_path.parent.mkdir(parents=True, exist_ok=True)

            export_data = session_state.to_dict()
            export_path.write_text(json.dumps(export_data, indent=2))

            logger.info(f"Exported session {session_id} to {export_path}")

            return True

        except Exception as e:
            logger.error(f"Failed to export session: {e}")
            return False

    async def import_session(
        self,
        import_path: str | Path,
    ) -> SessionState | None:
        """Import a session from a file.

        Args:
            import_path: Path to import from

        Returns:
            SessionState if successful, None otherwise
        """
        # NOTE: save_snapshot() acquires self._lock internally; do not wrap it
        # in `async with self._lock` (non-reentrant asyncio.Lock → deadlock).
        try:
            import_path = Path(import_path)

            if not import_path.exists():
                logger.warning(f"Import file not found: {import_path}")
                return None

            import_data = json.loads(import_path.read_text())
            session_state = SessionState.from_dict(import_data)

            # Save the imported session
            await self.save_snapshot(session_state)

            logger.info(f"Imported session {session_state.session_id} from {import_path}")

            return session_state

        except Exception as e:
            logger.error(f"Failed to import session: {e}")
            return None
