"""In-memory collaboration chat-room store with optional snapshot persistence.

Default mode is **in-memory only** (rooms are lost on restart) and is intended
for development. For durable rooms, configure a storage path — either via the
``XAGENT_COLLABORATION_STORE_PATH`` environment variable (picked up by the
module-level ``collaboration_store`` singleton) or by constructing
``CollaborationStore(storage_path=...)`` directly. When configured, every
mutation writes a full JSON snapshot atomically (tmp file + ``os.replace``)
and the snapshot is loaded back on startup.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from uuid import uuid4

from backend.app.core.memory import MemoryScope


@dataclass
class CollaborationMessage:
    message_id: str
    room_id: str
    sender_id: str
    sender_type: str
    content: str
    created_at: datetime
    metadata: dict[str, object] = field(default_factory=dict)

    def model_dump(self, mode: str = "json") -> dict[str, object]:
        return {
            "message_id": self.message_id,
            "room_id": self.room_id,
            "sender_id": self.sender_id,
            "sender_type": self.sender_type,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "CollaborationMessage":
        return cls(
            message_id=str(data["message_id"]),
            room_id=str(data["room_id"]),
            sender_id=str(data["sender_id"]),
            sender_type=str(data["sender_type"]),
            content=str(data["content"]),
            created_at=datetime.fromisoformat(str(data["created_at"])),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class CollaborationRoom:
    room_id: str
    topic: str
    tenant_id: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    members: list[str] = field(default_factory=list)
    messages: list[CollaborationMessage] = field(default_factory=list)
    status: str = "active"
    memory_scope: dict[str, object] = field(default_factory=dict)
    memory_refs: list[str] = field(default_factory=list)
    agent_memory_refs: dict[str, list[str]] = field(default_factory=dict)
    department_memory_refs: dict[str, list[str]] = field(default_factory=dict)

    def model_dump(self, mode: str = "json") -> dict[str, object]:
        return {
            "room_id": self.room_id,
            "topic": self.topic,
            "tenant_id": self.tenant_id,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "members": list(self.members),
            "messages": [message.model_dump(mode=mode) for message in self.messages],
            "status": self.status,
            "message_count": len(self.messages),
            "memory_scope": dict(self.memory_scope),
            "memory_refs": list(self.memory_refs),
            "agent_memory_refs": {agent_id: list(refs) for agent_id, refs in self.agent_memory_refs.items()},
        }

    def snapshot_dict(self) -> dict[str, object]:
        """Full-fidelity dict for persistence (superset of ``model_dump``).

        Unlike ``model_dump`` (the API response shape), this includes
        ``department_memory_refs`` so a reload restores the complete state.
        """
        data = self.model_dump(mode="json")
        data["department_memory_refs"] = {
            department_id: list(refs) for department_id, refs in self.department_memory_refs.items()
        }
        return data

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "CollaborationRoom":
        return cls(
            room_id=str(data["room_id"]),
            topic=str(data["topic"]),
            tenant_id=str(data["tenant_id"]),
            created_by=str(data["created_by"]),
            created_at=datetime.fromisoformat(str(data["created_at"])),
            updated_at=datetime.fromisoformat(str(data["updated_at"])),
            members=[str(member) for member in data.get("members") or []],
            messages=[CollaborationMessage.from_dict(item) for item in data.get("messages") or []],
            status=str(data.get("status") or "active"),
            memory_scope=dict(data.get("memory_scope") or {}),
            memory_refs=[str(ref) for ref in data.get("memory_refs") or []],
            agent_memory_refs={
                str(agent_id): [str(ref) for ref in refs]
                for agent_id, refs in (data.get("agent_memory_refs") or {}).items()
            },
            department_memory_refs={
                str(department_id): [str(ref) for ref in refs]
                for department_id, refs in (data.get("department_memory_refs") or {}).items()
            },
        )


class CollaborationStore:
    """Chat-room store.

    Args:
        storage_path: Optional JSON snapshot path. ``None`` (default) keeps the
            store memory-only — explicitly a dev mode: rooms do not survive a
            restart. When set, the snapshot is loaded at construction and
            re-written atomically after every mutation.
    """

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._rooms: dict[str, CollaborationRoom] = {}
        self._lock = RLock()
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path is not None:
            self._load_from_disk()

    @property
    def persistent(self) -> bool:
        """Whether this store survives restarts (snapshot path configured)."""
        return self._storage_path is not None

    def create_room(self, *, topic: str, tenant_id: str, created_by: str, members: list[str] | None = None, memory_scope: dict[str, object] | None = None) -> CollaborationRoom:
        now = datetime.now(UTC)
        room = CollaborationRoom(
            room_id=str(uuid4()),
            topic=topic,
            tenant_id=tenant_id,
            created_by=created_by,
            created_at=now,
            updated_at=now,
            members=members or [],
            memory_scope=memory_scope or {},
        )
        with self._lock:
            self._rooms[room.room_id] = room
            self._save_to_disk()
        return room

    def list_rooms(self, *, tenant_id: str | None = None) -> list[CollaborationRoom]:
        rooms = list(self._rooms.values())
        if tenant_id is not None:
            rooms = [room for room in rooms if room.tenant_id == tenant_id]
        rooms.sort(key=lambda room: room.updated_at, reverse=True)
        return rooms

    def get_room(self, room_id: str) -> CollaborationRoom | None:
        return self._rooms.get(room_id)

    def post_message(
        self,
        room_id: str,
        *,
        sender_id: str,
        sender_type: str,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> CollaborationMessage:
        now = datetime.now(UTC)
        metadata = dict(metadata or {})
        memory_refs = [str(ref) for ref in metadata.get("memory_refs", []) if str(ref)] if isinstance(metadata.get("memory_refs", []), list) else []
        agent_id = str(metadata.get("agent_id") or sender_id)
        department_id = str(metadata.get("department_id") or "")
        message = CollaborationMessage(
            message_id=str(uuid4()),
            room_id=room_id,
            sender_id=sender_id,
            sender_type=sender_type,
            content=content,
            created_at=now,
            metadata=metadata,
        )
        with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                raise ValueError(f"Room not found: {room_id}")
            room.messages.append(message)
            room.updated_at = now
            if sender_type == "agent":
                room.agent_memory_refs.setdefault(agent_id, []).append(f"message:{message.message_id}")
                room.memory_refs.append(f"message:{message.message_id}")
            for ref in memory_refs:
                if ref not in room.memory_refs:
                    room.memory_refs.append(ref)
                if agent_id:
                    agent_refs = room.agent_memory_refs.setdefault(agent_id, [])
                    if ref not in agent_refs:
                        agent_refs.append(ref)
                if department_id:
                    dept_refs = room.department_memory_refs.setdefault(department_id, [])
                    if ref not in dept_refs:
                        dept_refs.append(ref)
            self._save_to_disk()
        return message

    def add_member(self, room_id: str, member_id: str) -> CollaborationRoom:
        with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                raise ValueError(f"Room not found: {room_id}")
            if member_id not in room.members:
                room.members.append(member_id)
                room.updated_at = datetime.now(UTC)
                self._save_to_disk()
            return room

    def remove_member(self, room_id: str, member_id: str) -> CollaborationRoom:
        with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                raise ValueError(f"Room not found: {room_id}")
            if member_id in room.members:
                room.members.remove(member_id)
                room.updated_at = datetime.now(UTC)
                self._save_to_disk()
            return room

    def add_memory_ref(self, room_id: str, ref: str) -> CollaborationRoom:
        with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                raise ValueError(f"Room not found: {room_id}")
            if ref not in room.memory_refs:
                room.memory_refs.append(ref)
                room.updated_at = datetime.now(UTC)
                self._save_to_disk()
            return room

    def add_agent_memory_ref(self, room_id: str, agent_id: str, ref: str) -> CollaborationRoom:
        with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                raise ValueError(f"Room not found: {room_id}")
            agent_refs = room.agent_memory_refs.setdefault(agent_id, [])
            if ref not in agent_refs:
                agent_refs.append(ref)
                room.updated_at = datetime.now(UTC)
                self._save_to_disk()
            return room

    def add_department_memory_ref(self, room_id: str, department_id: str, ref: str) -> CollaborationRoom:
        with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                raise ValueError(f"Room not found: {room_id}")
            dept_refs = room.department_memory_refs.setdefault(department_id, [])
            if ref not in dept_refs:
                dept_refs.append(ref)
                room.updated_at = datetime.now(UTC)
                self._save_to_disk()
            return room

    def close_room(self, room_id: str) -> CollaborationRoom:
        with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                raise ValueError(f"Room not found: {room_id}")
            room.status = "closed"
            room.updated_at = datetime.now(UTC)
            self._save_to_disk()
            return room

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load_from_disk(self) -> None:
        if self._storage_path is None or not self._storage_path.exists():
            return
        with self._storage_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        rooms = payload.get("rooms", []) if isinstance(payload, dict) else []
        for item in rooms:
            room = CollaborationRoom.from_dict(item)
            self._rooms[room.room_id] = room

    def _save_to_disk(self) -> None:
        """Atomically snapshot all rooms (caller must hold ``self._lock``)."""
        if self._storage_path is None:
            return
        payload = {
            "version": 1,
            "saved_at": datetime.now(UTC).isoformat(),
            "rooms": [room.snapshot_dict() for room in self._rooms.values()],
        }
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._storage_path.with_name(self._storage_path.name + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
        os.replace(tmp_path, self._storage_path)


def _build_default_store() -> CollaborationStore:
    """Build the module-level singleton.

    ``XAGENT_COLLABORATION_STORE_PATH`` opts into durable snapshot persistence;
    unset/empty means the explicitly dev-only in-memory mode.
    """
    path = os.environ.get("XAGENT_COLLABORATION_STORE_PATH", "").strip()
    return CollaborationStore(storage_path=path or None)


collaboration_store = _build_default_store()
