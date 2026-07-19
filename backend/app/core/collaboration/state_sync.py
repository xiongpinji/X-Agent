"""Distributed state synchronization for collaborative agents."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class StateSnapshot:
    """Snapshot of distributed state at a point in time."""

    snapshot_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    state_data: dict[str, Any] = field(default_factory=dict)
    agent_id: str = ""
    version: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class ConflictResolutionStrategy:
    """Base class for conflict resolution strategies."""

    async def resolve(
        self,
        local_state: dict[str, Any],
        remote_state: dict[str, Any],
        key: str,
    ) -> Any:
        """Resolve conflict between local and remote state.

        Args:
            local_state: Local state dictionary
            remote_state: Remote state dictionary
            key: Key being conflicted

        Returns:
            Resolved value
        """
        raise NotImplementedError


class LastWriteWinsStrategy(ConflictResolutionStrategy):
    """Last write wins conflict resolution."""

    async def resolve(
        self,
        local_state: dict[str, Any],
        remote_state: dict[str, Any],
        key: str,
    ) -> Any:
        """Use the most recently written value."""
        local_value = local_state.get(key)
        remote_value = remote_state.get(key)

        if isinstance(local_value, dict) and "timestamp" in local_value:
            local_ts = local_value.get("timestamp", 0)
        else:
            local_ts = 0

        if isinstance(remote_value, dict) and "timestamp" in remote_value:
            remote_ts = remote_value.get("timestamp", 0)
        else:
            remote_ts = 0

        return remote_value if remote_ts >= local_ts else local_value


class MergeStrategy(ConflictResolutionStrategy):
    """Merge conflict resolution for collections."""

    async def resolve(
        self,
        local_state: dict[str, Any],
        remote_state: dict[str, Any],
        key: str,
    ) -> Any:
        """Merge local and remote values."""
        local_value = local_state.get(key, {})
        remote_value = remote_state.get(key, {})

        if isinstance(local_value, dict) and isinstance(remote_value, dict):
            merged = dict(local_value)
            merged.update(remote_value)
            return merged
        elif isinstance(local_value, list) and isinstance(remote_value, list):
            return list(set(local_value + remote_value))
        else:
            return remote_value


class StateManager:
    """Manages distributed state synchronization across agents."""

    def __init__(
        self,
        conflict_strategy: Optional[ConflictResolutionStrategy] = None,
    ) -> None:
        self._local_state: dict[str, Any] = {}
        self._remote_states: dict[str, dict[str, Any]] = {}
        self._snapshots: list[StateSnapshot] = []
        self._version = 0
        self._lock = asyncio.Lock()
        self._conflict_strategy = conflict_strategy or LastWriteWinsStrategy()
        self._state_listeners: list[Callable] = []
        self._sync_history: list[dict[str, Any]] = []

    async def set_state(self, key: str, value: Any) -> None:
        """Set local state value.

        Args:
            key: State key
            value: State value
        """
        async with self._lock:
            self._local_state[key] = value
            self._version += 1
            await self._notify_listeners("state_changed", {"key": key, "value": value})

    async def get_state(self, key: str, default: Any = None) -> Any:
        """Get local state value.

        Args:
            key: State key
            default: Default value if key not found

        Returns:
            State value or default
        """
        return self._local_state.get(key, default)

    async def update_state(self, updates: dict[str, Any]) -> None:
        """Update multiple state values.

        Args:
            updates: Dictionary of updates
        """
        async with self._lock:
            self._local_state.update(updates)
            self._version += 1
            await self._notify_listeners("state_updated", {"updates": updates})

    async def sync_state(self, agent_id: str, remote_state: dict[str, Any]) -> None:
        """Synchronize state with remote agent.

        Args:
            agent_id: ID of remote agent
            remote_state: Remote state dictionary
        """
        async with self._lock:
            self._remote_states[agent_id] = remote_state

            for key in set(list(self._local_state.keys()) + list(remote_state.keys())):
                if key in self._local_state and key in remote_state:
                    if self._local_state[key] != remote_state[key]:
                        resolved = await self._conflict_strategy.resolve(
                            self._local_state,
                            remote_state,
                            key,
                        )
                        self._local_state[key] = resolved
                        self._sync_history.append({
                            "timestamp": datetime.now(UTC).isoformat(),
                            "agent_id": agent_id,
                            "key": key,
                            "action": "resolved_conflict",
                        })
                elif key in remote_state:
                    self._local_state[key] = remote_state[key]

            self._version += 1
            await self._notify_listeners("state_synced", {"agent_id": agent_id})

    async def create_snapshot(self, agent_id: str = "") -> StateSnapshot:
        """Create a snapshot of current state.

        Args:
            agent_id: ID of agent creating snapshot

        Returns:
            StateSnapshot object
        """
        async with self._lock:
            snapshot = StateSnapshot(
                state_data=dict(self._local_state),
                agent_id=agent_id,
                version=self._version,
            )
            self._snapshots.append(snapshot)
            return snapshot

    async def restore_snapshot(self, snapshot_id: str) -> bool:
        """Restore state from a snapshot.

        Args:
            snapshot_id: ID of snapshot to restore

        Returns:
            True if restored, False if snapshot not found
        """
        snapshot = next(
            (s for s in self._snapshots if s.snapshot_id == snapshot_id),
            None,
        )

        if not snapshot:
            return False

        async with self._lock:
            self._local_state = dict(snapshot.state_data)
            self._version = snapshot.version + 1
            await self._notify_listeners("snapshot_restored", {"snapshot_id": snapshot_id})

        return True

    async def register_listener(self, listener: Callable) -> None:
        """Register a state change listener.

        Args:
            listener: Async callable that receives (event_type, data)
        """
        self._state_listeners.append(listener)

    async def _notify_listeners(self, event_type: str, data: dict[str, Any]) -> None:
        """Notify all listeners of state change."""
        for listener in self._state_listeners:
            if asyncio.iscoroutinefunction(listener):
                await listener(event_type, data)
            else:
                listener(event_type, data)

    async def get_state_diff(self, other_state: dict[str, Any]) -> dict[str, Any]:
        """Get differences between local and other state.

        Args:
            other_state: Other state dictionary

        Returns:
            Dictionary of differences
        """
        diff = {
            "added": {},
            "removed": {},
            "modified": {},
        }

        for key, value in other_state.items():
            if key not in self._local_state:
                diff["added"][key] = value
            elif self._local_state[key] != value:
                diff["modified"][key] = {
                    "local": self._local_state[key],
                    "remote": value,
                }

        for key in self._local_state:
            if key not in other_state:
                diff["removed"][key] = self._local_state[key]

        return diff

    async def get_state_manager_stats(self) -> dict[str, Any]:
        """Get state manager statistics."""
        return {
            "version": self._version,
            "local_state_size": len(self._local_state),
            "remote_agents": len(self._remote_states),
            "snapshots": len(self._snapshots),
            "sync_history_size": len(self._sync_history),
            "listeners": len(self._state_listeners),
        }

    async def get_full_state(self) -> dict[str, Any]:
        """Get full local state."""
        return dict(self._local_state)

    async def clear_state(self) -> None:
        """Clear all state."""
        async with self._lock:
            self._local_state.clear()
            self._version += 1
            await self._notify_listeners("state_cleared", {})
