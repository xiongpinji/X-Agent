"""
X-Agent Sync Client

Handles incremental synchronization between local and cloud.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, UTC, timedelta
from enum import Enum
from typing import Any, Callable, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class SyncDirection(str, Enum):
    """Sync direction."""
    UPLOAD = "upload"
    DOWNLOAD = "download"
    BIDIRECTIONAL = "bidirectional"


class ConflictResolutionStrategy(str, Enum):
    """Conflict resolution strategies."""
    LAST_WRITE_WINS = "last_write_wins"
    LOCAL_WINS = "local_wins"
    CLOUD_WINS = "cloud_wins"
    MANUAL = "manual"
    MERGE = "merge"


@dataclass
class SyncOperation:
    """Represents a sync operation."""
    id: str = field(default_factory=lambda: str(uuid4()))
    entity_type: str = ""
    entity_id: str = ""
    operation: str = ""  # CREATE, UPDATE, DELETE
    direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    data: dict = field(default_factory=dict)
    local_version: int = 0
    cloud_version: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: str = "pending"  # pending, syncing, completed, failed
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class SyncConflict:
    """Represents a sync conflict."""
    id: str = field(default_factory=lambda: str(uuid4()))
    entity_type: str = ""
    entity_id: str = ""
    conflict_type: str = ""  # UPDATE_CONFLICT, DELETE_CONFLICT, CREATE_CONFLICT
    local_data: dict = field(default_factory=dict)
    cloud_data: dict = field(default_factory=dict)
    local_version: int = 0
    cloud_version: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    resolution_strategy: Optional[ConflictResolutionStrategy] = None
    resolved_data: Optional[dict] = None


@dataclass
class SyncBatch:
    """Represents a batch of sync operations."""
    id: str = field(default_factory=lambda: str(uuid4()))
    operations: list[SyncOperation] = field(default_factory=list)
    conflicts: list[SyncConflict] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: Optional[datetime] = None
    status: str = "pending"  # pending, syncing, completed, failed
    error: Optional[str] = None


class SyncClient:
    """Synchronization client for local-cloud sync."""

    def __init__(
        self,
        db,
        cloud_api_client,
        conflict_resolver: Optional[ConflictResolver] = None,
        default_strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.LAST_WRITE_WINS,
    ):
        """Initialize sync client.

        Args:
            db: Local database instance
            cloud_api_client: Cloud API client
            conflict_resolver: Conflict resolver instance
            default_strategy: Default conflict resolution strategy
        """
        self.db = db
        self.cloud_api_client = cloud_api_client
        self.conflict_resolver = conflict_resolver or ConflictResolver()
        self.default_strategy = default_strategy

        self._is_syncing = False
        self._sync_lock = asyncio.Lock()
        self._pending_operations: list[SyncOperation] = []
        self._offline_mode = False
        self._last_sync_time: Optional[datetime] = None
        self._sync_callbacks: list[Callable] = []

    def register_sync_callback(self, callback: Callable) -> None:
        """Register callback for sync events.

        Args:
            callback: Callback function
        """
        self._sync_callbacks.append(callback)

    async def _notify_callbacks(self, event: str, data: dict) -> None:
        """Notify registered callbacks.

        Args:
            event: Event type
            data: Event data
        """
        for callback in self._sync_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event, data)
                else:
                    callback(event, data)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    def set_offline_mode(self, offline: bool) -> None:
        """Set offline mode.

        Args:
            offline: Whether in offline mode
        """
        self._offline_mode = offline
        if offline:
            logger.info("Entering offline mode")
        else:
            logger.info("Exiting offline mode")

    async def enqueue_operation(
        self,
        entity_type: str,
        entity_id: str,
        operation: str,
        data: dict,
        priority: int = 0,
    ) -> str:
        """Enqueue a sync operation.

        Args:
            entity_type: Type of entity
            entity_id: Entity ID
            operation: Operation type (CREATE, UPDATE, DELETE)
            data: Operation data
            priority: Priority level

        Returns:
            Operation ID
        """
        if self._offline_mode:
            # Enqueue to offline queue
            queue_id = self.db.enqueue_offline(
                entity_type, entity_id, operation, data, priority
            )
            await self._notify_callbacks("offline_operation_queued", {
                "queue_id": queue_id,
                "entity_type": entity_type,
                "entity_id": entity_id,
            })
        else:
            # Enqueue to sync queue
            queue_id = self.db.enqueue_sync(
                entity_type, entity_id, operation, data, priority
            )
            await self._notify_callbacks("sync_operation_queued", {
                "queue_id": queue_id,
                "entity_type": entity_type,
                "entity_id": entity_id,
            })

        return queue_id

    async def sync(self) -> SyncBatch:
        """Perform synchronization.

        Returns:
            Sync batch result
        """
        async with self._sync_lock:
            if self._is_syncing:
                logger.warning("Sync already in progress")
                return SyncBatch(status="skipped")

            self._is_syncing = True
            batch = SyncBatch()

            try:
                await self._notify_callbacks("sync_started", {
                    "batch_id": batch.id,
                })

                # Get pending operations
                pending_ops = self.db.get_pending_syncs()
                batch.operations = [
                    SyncOperation(
                        id=op["id"],
                        entity_type=op["entity_type"],
                        entity_id=op["entity_id"],
                        operation=op["operation"],
                        data=json.loads(op["data"]),
                    )
                    for op in pending_ops
                ]

                # Upload local changes
                await self._upload_changes(batch)

                # Download cloud changes
                await self._download_changes(batch)

                # Detect and resolve conflicts
                await self._handle_conflicts(batch)

                batch.status = "completed"
                batch.completed_at = datetime.now(UTC)
                self._last_sync_time = datetime.now(UTC)

                await self._notify_callbacks("sync_completed", {
                    "batch_id": batch.id,
                    "operations_count": len(batch.operations),
                    "conflicts_count": len(batch.conflicts),
                })

            except Exception as e:
                logger.error(f"Sync failed: {e}")
                batch.status = "failed"
                batch.error = str(e)
                batch.completed_at = datetime.now(UTC)

                await self._notify_callbacks("sync_failed", {
                    "batch_id": batch.id,
                    "error": str(e),
                })

            finally:
                self._is_syncing = False

            return batch

    async def _upload_changes(self, batch: SyncBatch) -> None:
        """Upload local changes to cloud.

        Args:
            batch: Sync batch
        """
        logger.info(f"Uploading {len(batch.operations)} changes")

        for op in batch.operations:
            try:
                # Get metadata
                metadata = self.db.get_metadata(op.entity_type, op.entity_id)
                if metadata:
                    op.local_version = metadata.get("local_version", 0)
                    op.cloud_version = metadata.get("cloud_version", 0)

                # Upload to cloud
                result = await self.cloud_api_client.sync_entity(
                    entity_type=op.entity_type,
                    entity_id=op.entity_id,
                    operation=op.operation,
                    data=op.data,
                    local_version=op.local_version,
                    cloud_version=op.cloud_version,
                )

                # Update sync state
                self.db.update_sync_state(
                    op.entity_type,
                    op.entity_id,
                    "synced",
                )

                # Mark as completed
                self.db.mark_sync_completed(op.id, success=True)

                # Record history
                self.db.record_sync_history(
                    batch.id,
                    op.entity_type,
                    op.entity_id,
                    op.operation,
                    "upload",
                    "success",
                    duration_ms=0,
                    local_version=op.local_version,
                    cloud_version=result.get("cloud_version"),
                )

                op.status = "completed"

            except Exception as e:
                logger.error(f"Upload failed for {op.entity_id}: {e}")
                op.status = "failed"
                op.error = str(e)
                op.retry_count += 1

                # Record history
                self.db.record_sync_history(
                    batch.id,
                    op.entity_type,
                    op.entity_id,
                    op.operation,
                    "upload",
                    "failed",
                    error_message=str(e),
                )

    async def _download_changes(self, batch: SyncBatch) -> None:
        """Download cloud changes.

        Args:
            batch: Sync batch
        """
        logger.info("Downloading cloud changes")

        try:
            # Get changes since last sync
            since = self._last_sync_time or (datetime.now(UTC) - timedelta(days=30))

            changes = await self.cloud_api_client.get_changes(since=since)

            for change in changes:
                op = SyncOperation(
                    entity_type=change["entity_type"],
                    entity_id=change["entity_id"],
                    operation=change["operation"],
                    data=change.get("data", {}),
                    cloud_version=change.get("version", 0),
                    direction=SyncDirection.DOWNLOAD,
                )

                # Check for conflicts
                local_metadata = self.db.get_metadata(op.entity_type, op.entity_id)
                if local_metadata and local_metadata.get("local_version", 0) > 0:
                    # Potential conflict
                    if local_metadata.get("local_version") != local_metadata.get("cloud_version"):
                        conflict = SyncConflict(
                            entity_type=op.entity_type,
                            entity_id=op.entity_id,
                            conflict_type="UPDATE_CONFLICT",
                            local_version=local_metadata.get("local_version"),
                            cloud_version=op.cloud_version,
                        )
                        batch.conflicts.append(conflict)
                        continue

                # Apply change
                await self._apply_change(op)
                batch.operations.append(op)

                # Record history
                self.db.record_sync_history(
                    batch.id,
                    op.entity_type,
                    op.entity_id,
                    op.operation,
                    "download",
                    "success",
                    cloud_version=op.cloud_version,
                )

        except Exception as e:
            logger.error(f"Download failed: {e}")

    async def _apply_change(self, op: SyncOperation) -> None:
        """Apply a downloaded change.

        Args:
            op: Sync operation
        """
        # Update metadata
        self.db.set_metadata(
            op.entity_type,
            op.entity_id,
            cloud_version=op.cloud_version,
        )

        # Update sync state
        self.db.update_sync_state(
            op.entity_type,
            op.entity_id,
            "synced",
        )

    async def _handle_conflicts(self, batch: SyncBatch) -> None:
        """Handle conflicts.

        Args:
            batch: Sync batch
        """
        logger.info(f"Handling {len(batch.conflicts)} conflicts")

        for conflict in batch.conflicts:
            try:
                # Resolve conflict
                resolution = await self.conflict_resolver.resolve(
                    conflict,
                    self.default_strategy,
                )

                # Apply resolution
                if resolution:
                    conflict.resolution_strategy = resolution.strategy
                    conflict.resolved_data = resolution.resolved_data

                    # Update database
                    self.db.resolve_conflict(
                        conflict.id,
                        resolution.strategy.value,
                        resolution.resolved_data,
                    )

            except Exception as e:
                logger.error(f"Conflict resolution failed: {e}")

    async def sync_offline_operations(self) -> None:
        """Sync offline operations when back online.

        Returns:
            None
        """
        logger.info("Syncing offline operations")

        offline_ops = self.db.get_offline_operations()

        for op in offline_ops:
            try:
                # Re-enqueue to sync queue
                self.db.enqueue_sync(
                    op["entity_type"],
                    op["entity_id"],
                    op["operation"],
                    json.loads(op["data"]),
                )

                # Mark as synced
                self.db.mark_offline_synced(op["id"])

            except Exception as e:
                logger.error(f"Failed to sync offline operation: {e}")

    def get_sync_status(self) -> dict:
        """Get current sync status.

        Returns:
            Sync status dictionary
        """
        stats = self.db.get_sync_stats()
        return {
            "is_syncing": self._is_syncing,
            "offline_mode": self._offline_mode,
            "last_sync_time": self._last_sync_time.isoformat() if self._last_sync_time else None,
            **stats,
        }


class ConflictResolver:
    """Resolves sync conflicts."""

    @dataclass
    class Resolution:
        """Conflict resolution result."""
        strategy: ConflictResolutionStrategy
        resolved_data: dict

    async def resolve(
        self,
        conflict: SyncConflict,
        default_strategy: ConflictResolutionStrategy,
    ) -> Optional[Resolution]:
        """Resolve a conflict.

        Args:
            conflict: Conflict to resolve
            default_strategy: Default resolution strategy

        Returns:
            Resolution result or None
        """
        strategy = default_strategy

        if strategy == ConflictResolutionStrategy.LAST_WRITE_WINS:
            return await self._resolve_last_write_wins(conflict)
        elif strategy == ConflictResolutionStrategy.LOCAL_WINS:
            return self.Resolution(
                strategy=strategy,
                resolved_data=conflict.local_data,
            )
        elif strategy == ConflictResolutionStrategy.CLOUD_WINS:
            return self.Resolution(
                strategy=strategy,
                resolved_data=conflict.cloud_data,
            )
        elif strategy == ConflictResolutionStrategy.MERGE:
            return await self._resolve_merge(conflict)
        else:
            logger.warning(f"Unknown resolution strategy: {strategy}")
            return None

    async def _resolve_last_write_wins(
        self,
        conflict: SyncConflict,
    ) -> Resolution:
        """Resolve using last-write-wins strategy.

        Args:
            conflict: Conflict to resolve

        Returns:
            Resolution result
        """
        # Use local data if it's newer
        local_timestamp = conflict.local_data.get("updated_at", 0)
        cloud_timestamp = conflict.cloud_data.get("updated_at", 0)

        if local_timestamp >= cloud_timestamp:
            resolved_data = conflict.local_data
        else:
            resolved_data = conflict.cloud_data

        return self.Resolution(
            strategy=ConflictResolutionStrategy.LAST_WRITE_WINS,
            resolved_data=resolved_data,
        )

    async def _resolve_merge(
        self,
        conflict: SyncConflict,
    ) -> Resolution:
        """Resolve using merge strategy.

        Args:
            conflict: Conflict to resolve

        Returns:
            Resolution result
        """
        # Simple merge: combine non-conflicting fields
        merged = {**conflict.cloud_data, **conflict.local_data}

        return self.Resolution(
            strategy=ConflictResolutionStrategy.MERGE,
            resolved_data=merged,
        )
