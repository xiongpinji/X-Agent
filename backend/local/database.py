"""
X-Agent Local Database Manager

Handles SQLite database operations, connection pooling, and schema management.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Generator, Optional
from uuid import uuid4

from backend.local.schema import (
    ALL_TABLES,
    SCHEMA_VERSION,
    ENTITY_TYPES,
    SYNC_OPERATIONS,
    SYNC_STATES,
    CONFLICT_TYPES,
    RESOLUTION_STRATEGIES,
)

logger = logging.getLogger(__name__)


class DatabaseConfig:
    """Database configuration."""

    def __init__(
        self,
        db_path: str | Path = "~/.xagent/local.db",
        timeout: float = 30.0,
        check_same_thread: bool = False,
        enable_wal: bool = True,
        enable_foreign_keys: bool = True,
    ):
        """Initialize database configuration.

        Args:
            db_path: Path to SQLite database file
            timeout: Connection timeout in seconds
            check_same_thread: SQLite thread safety check
            enable_wal: Enable Write-Ahead Logging
            enable_foreign_keys: Enable foreign key constraints
        """
        self.db_path = Path(db_path).expanduser()
        self.timeout = timeout
        self.check_same_thread = check_same_thread
        self.enable_wal = enable_wal
        self.enable_foreign_keys = enable_foreign_keys

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


class LocalDatabase:
    """SQLite database manager for X-Agent local data."""

    def __init__(self, config: DatabaseConfig):
        """Initialize database manager.

        Args:
            config: Database configuration
        """
        self.config = config
        self._local = threading.local()
        self._lock = threading.RLock()
        self._initialized = False

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection.

        Returns:
            SQLite connection
        """
        if not hasattr(self._local, "connection") or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                str(self.config.db_path),
                timeout=self.config.timeout,
                check_same_thread=self.config.check_same_thread,
            )
            self._local.connection.row_factory = sqlite3.Row
            self._configure_connection(self._local.connection)

        return self._local.connection

    def _configure_connection(self, conn: sqlite3.Connection) -> None:
        """Configure SQLite connection.

        Args:
            conn: SQLite connection
        """
        if self.config.enable_wal:
            conn.execute("PRAGMA journal_mode = WAL")

        if self.config.enable_foreign_keys:
            conn.execute("PRAGMA foreign_keys = ON")

        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = -64000")  # 64MB cache

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database transactions.

        Yields:
            SQLite connection
        """
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction failed: {e}")
            raise

    def initialize(self) -> None:
        """Initialize database schema."""
        with self._lock:
            if self._initialized:
                return

            try:
                with self.transaction() as conn:
                    cursor = conn.cursor()

                    # Create all tables
                    # 每个 *_TABLE 字符串含多条语句(CREATE TABLE + 多条 CREATE INDEX),
                    # sqlite3 的 execute() 一次只能跑一条,必须用 executescript()。
                    for table_sql in ALL_TABLES:
                        cursor.executescript(table_sql)

                    # Create views
                    cursor.execute("""
                        CREATE VIEW IF NOT EXISTS pending_sync AS
                        SELECT
                            sq.id,
                            sq.entity_type,
                            sq.entity_id,
                            sq.operation,
                            sq.priority,
                            sq.retry_count,
                            sq.created_at,
                            ss.state as sync_state
                        FROM sync_queue sq
                        LEFT JOIN sync_state ss ON sq.entity_type = ss.entity_type
                            AND sq.entity_id = ss.entity_id
                        WHERE sq.status = 'pending'
                        ORDER BY sq.priority DESC, sq.created_at ASC
                    """)

                    cursor.execute("""
                        CREATE VIEW IF NOT EXISTS conflicted_entities AS
                        SELECT
                            cl.entity_type,
                            cl.entity_id,
                            COUNT(*) as conflict_count,
                            MAX(cl.created_at) as latest_conflict,
                            GROUP_CONCAT(DISTINCT cl.conflict_type) as conflict_types
                        FROM conflict_log cl
                        WHERE cl.resolved_at IS NULL
                        GROUP BY cl.entity_type, cl.entity_id
                    """)

                    logger.info("Database schema initialized successfully")
                    self._initialized = True

            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
                raise

    def close(self) -> None:
        """Close database connection."""
        if hasattr(self._local, "connection") and self._local.connection:
            self._local.connection.close()
            self._local.connection = None

    # ========================================================================
    # METADATA OPERATIONS
    # ========================================================================

    def set_metadata(
        self,
        entity_type: str,
        entity_id: str,
        local_version: int = 1,
        cloud_version: int = 0,
        is_encrypted: bool = False,
        checksum: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """Set entity metadata.

        Args:
            entity_type: Type of entity
            entity_id: Entity ID
            local_version: Local version number
            cloud_version: Cloud version number
            is_encrypted: Whether data is encrypted
            checksum: Data checksum
            metadata: Additional metadata

        Returns:
            Metadata ID
        """
        metadata_id = str(uuid4())

        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO local_metadata
                (id, entity_type, entity_id, local_version, cloud_version,
                 is_encrypted, checksum, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metadata_id,
                entity_type,
                entity_id,
                local_version,
                cloud_version,
                is_encrypted,
                checksum,
                json.dumps(metadata or {}),
                datetime.now(UTC),
            ))

        return metadata_id

    def get_metadata(self, entity_type: str, entity_id: str) -> Optional[dict]:
        """Get entity metadata.

        Args:
            entity_type: Type of entity
            entity_id: Entity ID

        Returns:
            Metadata dictionary or None
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM local_metadata
            WHERE entity_type = ? AND entity_id = ?
        """, (entity_type, entity_id))

        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    # ========================================================================
    # SYNC STATE OPERATIONS
    # ========================================================================

    def update_sync_state(
        self,
        entity_type: str,
        entity_id: str,
        state: str,
        error_message: Optional[str] = None,
        retry_count: int = 0,
    ) -> None:
        """Update sync state for entity.

        Args:
            entity_type: Type of entity
            entity_id: Entity ID
            state: New sync state
            error_message: Error message if failed
            retry_count: Number of retries
        """
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO sync_state
                (id, entity_type, entity_id, state, last_sync_attempt_at,
                 last_error_message, retry_count, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid4()),
                entity_type,
                entity_id,
                state,
                datetime.now(UTC),
                error_message,
                retry_count,
                datetime.now(UTC),
            ))

    def get_sync_state(self, entity_type: str, entity_id: str) -> Optional[dict]:
        """Get sync state for entity.

        Args:
            entity_type: Type of entity
            entity_id: Entity ID

        Returns:
            Sync state dictionary or None
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM sync_state
            WHERE entity_type = ? AND entity_id = ?
        """, (entity_type, entity_id))

        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    # ========================================================================
    # CONFLICT OPERATIONS
    # ========================================================================

    def log_conflict(
        self,
        entity_type: str,
        entity_id: str,
        conflict_type: str,
        local_data: dict,
        cloud_data: dict,
        local_version: Optional[int] = None,
        cloud_version: Optional[int] = None,
    ) -> str:
        """Log a conflict.

        Args:
            entity_type: Type of entity
            entity_id: Entity ID
            conflict_type: Type of conflict
            local_data: Local data
            cloud_data: Cloud data
            local_version: Local version
            cloud_version: Cloud version

        Returns:
            Conflict log ID
        """
        conflict_id = str(uuid4())

        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO conflict_log
                (id, entity_type, entity_id, conflict_type, local_version,
                 cloud_version, local_data, cloud_data, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                conflict_id,
                entity_type,
                entity_id,
                conflict_type,
                local_version,
                cloud_version,
                json.dumps(local_data),
                json.dumps(cloud_data),
                datetime.now(UTC),
            ))

        return conflict_id

    def resolve_conflict(
        self,
        conflict_id: str,
        resolution_strategy: str,
        resolved_data: dict,
        resolved_by: Optional[str] = None,
    ) -> None:
        """Resolve a conflict.

        Args:
            conflict_id: Conflict ID
            resolution_strategy: Resolution strategy used
            resolved_data: Resolved data
            resolved_by: User/agent who resolved it
        """
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE conflict_log
                SET resolution_strategy = ?, resolved_data = ?,
                    resolved_at = ?, resolved_by = ?, updated_at = ?
                WHERE id = ?
            """, (
                resolution_strategy,
                json.dumps(resolved_data),
                datetime.now(UTC),
                resolved_by,
                datetime.now(UTC),
                conflict_id,
            ))

    def get_unresolved_conflicts(
        self, entity_type: Optional[str] = None
    ) -> list[dict]:
        """Get unresolved conflicts.

        Args:
            entity_type: Filter by entity type (optional)

        Returns:
            List of conflict records
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if entity_type:
            cursor.execute("""
                SELECT * FROM conflict_log
                WHERE resolved_at IS NULL AND entity_type = ?
                ORDER BY created_at DESC
            """, (entity_type,))
        else:
            cursor.execute("""
                SELECT * FROM conflict_log
                WHERE resolved_at IS NULL
                ORDER BY created_at DESC
            """)

        return [dict(row) for row in cursor.fetchall()]

    # ========================================================================
    # SYNC QUEUE OPERATIONS
    # ========================================================================

    def enqueue_sync(
        self,
        entity_type: str,
        entity_id: str,
        operation: str,
        data: dict,
        priority: int = 0,
    ) -> str:
        """Enqueue sync operation.

        Args:
            entity_type: Type of entity
            entity_id: Entity ID
            operation: Operation type (CREATE, UPDATE, DELETE)
            data: Operation data
            priority: Priority level

        Returns:
            Queue entry ID
        """
        queue_id = str(uuid4())

        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sync_queue
                (id, entity_type, entity_id, operation, data, priority, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                queue_id,
                entity_type,
                entity_id,
                operation,
                json.dumps(data),
                priority,
                "pending",
            ))

        return queue_id

    def get_pending_syncs(self, limit: int = 100) -> list[dict]:
        """Get pending sync operations.

        Args:
            limit: Maximum number of operations to return

        Returns:
            List of pending sync operations
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM sync_queue
            WHERE status = 'pending'
            ORDER BY priority DESC, created_at ASC
            LIMIT ?
        """, (limit,))

        return [dict(row) for row in cursor.fetchall()]

    def mark_sync_completed(self, queue_id: str, success: bool = True) -> None:
        """Mark sync operation as completed.

        Args:
            queue_id: Queue entry ID
            success: Whether operation succeeded
        """
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE sync_queue
                SET status = ?, completed_at = ?, updated_at = ?
                WHERE id = ?
            """, (
                "completed" if success else "failed",
                datetime.now(UTC),
                datetime.now(UTC),
                queue_id,
            ))

    # ========================================================================
    # OFFLINE QUEUE OPERATIONS
    # ========================================================================

    def enqueue_offline(
        self,
        entity_type: str,
        entity_id: str,
        operation: str,
        data: dict,
        priority: int = 0,
    ) -> str:
        """Enqueue offline operation.

        Args:
            entity_type: Type of entity
            entity_id: Entity ID
            operation: Operation type
            data: Operation data
            priority: Priority level

        Returns:
            Queue entry ID
        """
        queue_id = str(uuid4())

        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO offline_queue
                (id, entity_type, entity_id, operation, data, priority, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                queue_id,
                entity_type,
                entity_id,
                operation,
                json.dumps(data),
                priority,
                "pending",
            ))

        return queue_id

    def get_offline_operations(self) -> list[dict]:
        """Get all offline operations.

        Returns:
            List of offline operations
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM offline_queue
            WHERE status = 'pending'
            ORDER BY priority DESC, created_at ASC
        """)

        return [dict(row) for row in cursor.fetchall()]

    def mark_offline_synced(self, queue_id: str) -> None:
        """Mark offline operation as synced.

        Args:
            queue_id: Queue entry ID
        """
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE offline_queue
                SET status = 'synced', synced_at = ?, updated_at = ?
                WHERE id = ?
            """, (
                datetime.now(UTC),
                datetime.now(UTC),
                queue_id,
            ))

    # ========================================================================
    # SYNC HISTORY OPERATIONS
    # ========================================================================

    def record_sync_history(
        self,
        sync_batch_id: str,
        entity_type: str,
        entity_id: str,
        operation: str,
        direction: str,
        status: str,
        duration_ms: int = 0,
        error_message: Optional[str] = None,
        local_version: Optional[int] = None,
        cloud_version: Optional[int] = None,
    ) -> None:
        """Record sync operation in history.

        Args:
            sync_batch_id: Batch ID for this sync
            entity_type: Type of entity
            entity_id: Entity ID
            operation: Operation type
            direction: Sync direction (upload/download)
            status: Operation status
            duration_ms: Duration in milliseconds
            error_message: Error message if failed
            local_version: Local version
            cloud_version: Cloud version
        """
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sync_history
                (id, sync_batch_id, entity_type, entity_id, operation,
                 direction, status, duration_ms, error_message,
                 local_version, cloud_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid4()),
                sync_batch_id,
                entity_type,
                entity_id,
                operation,
                direction,
                status,
                duration_ms,
                error_message,
                local_version,
                cloud_version,
            ))

    def get_sync_history(
        self,
        entity_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get sync history.

        Args:
            entity_type: Filter by entity type (optional)
            limit: Maximum number of records

        Returns:
            List of sync history records
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if entity_type:
            cursor.execute("""
                SELECT * FROM sync_history
                WHERE entity_type = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (entity_type, limit))
        else:
            cursor.execute("""
                SELECT * FROM sync_history
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))

        return [dict(row) for row in cursor.fetchall()]

    # ========================================================================
    # CACHE OPERATIONS
    # ========================================================================

    def set_cache(
        self,
        entity_type: str,
        entity_id: str,
        cache_key: str,
        cache_value: Any,
        ttl_seconds: int = 3600,
    ) -> None:
        """Set cache entry.

        Args:
            entity_type: Type of entity
            entity_id: Entity ID
            cache_key: Cache key
            cache_value: Cache value
            ttl_seconds: Time to live in seconds
        """
        expires_at = datetime.now(UTC).timestamp() + ttl_seconds

        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO cache_index
                (id, entity_type, entity_id, cache_key, cache_value,
                 ttl_seconds, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid4()),
                entity_type,
                entity_id,
                cache_key,
                json.dumps(cache_value) if isinstance(cache_value, dict) else cache_value,
                ttl_seconds,
                expires_at,
            ))

    def get_cache(self, cache_key: str) -> Optional[Any]:
        """Get cache entry.

        Args:
            cache_key: Cache key

        Returns:
            Cache value or None
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cache_value FROM cache_index
            WHERE cache_key = ? AND expires_at > ?
        """, (cache_key, datetime.now(UTC).timestamp()))

        row = cursor.fetchone()
        if row:
            return row[0]
        return None

    def cleanup_expired_cache(self) -> int:
        """Clean up expired cache entries.

        Returns:
            Number of entries deleted
        """
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM cache_index
                WHERE expires_at <= ?
            """, (datetime.now(UTC).timestamp(),))

            return cursor.rowcount

    # ========================================================================
    # STATISTICS & MONITORING
    # ========================================================================

    def get_sync_stats(self) -> dict:
        """Get sync statistics.

        Returns:
            Dictionary with sync statistics
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Pending syncs
        cursor.execute("SELECT COUNT(*) FROM sync_queue WHERE status = 'pending'")
        pending = cursor.fetchone()[0]

        # Failed syncs
        cursor.execute("SELECT COUNT(*) FROM sync_queue WHERE status = 'failed'")
        failed = cursor.fetchone()[0]

        # Unresolved conflicts
        cursor.execute("SELECT COUNT(*) FROM conflict_log WHERE resolved_at IS NULL")
        conflicts = cursor.fetchone()[0]

        # Offline operations
        cursor.execute("SELECT COUNT(*) FROM offline_queue WHERE status = 'pending'")
        offline = cursor.fetchone()[0]

        return {
            "pending_syncs": pending,
            "failed_syncs": failed,
            "unresolved_conflicts": conflicts,
            "offline_operations": offline,
        }

    def get_database_size(self) -> dict:
        """Get database size information.

        Returns:
            Dictionary with size information
        """
        db_file = self.config.db_path
        if db_file.exists():
            size_bytes = db_file.stat().st_size
            return {
                "database_size_bytes": size_bytes,
                "database_size_mb": round(size_bytes / (1024 * 1024), 2),
            }
        return {"database_size_bytes": 0, "database_size_mb": 0}
