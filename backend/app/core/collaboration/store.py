from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
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


class CollaborationStore:
    def __init__(self) -> None:
        self._rooms: dict[str, CollaborationRoom] = {}
        self._lock = RLock()

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
        return message

    def add_member(self, room_id: str, member_id: str) -> CollaborationRoom:
        with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                raise ValueError(f"Room not found: {room_id}")
            if member_id not in room.members:
                room.members.append(member_id)
                room.updated_at = datetime.now(UTC)
            return room

    def remove_member(self, room_id: str, member_id: str) -> CollaborationRoom:
        with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                raise ValueError(f"Room not found: {room_id}")
            if member_id in room.members:
                room.members.remove(member_id)
                room.updated_at = datetime.now(UTC)
            return room

    def add_memory_ref(self, room_id: str, ref: str) -> CollaborationRoom:
        with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                raise ValueError(f"Room not found: {room_id}")
            if ref not in room.memory_refs:
                room.memory_refs.append(ref)
                room.updated_at = datetime.now(UTC)
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
            return room

    def close_room(self, room_id: str) -> CollaborationRoom:
        with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                raise ValueError(f"Room not found: {room_id}")
            room.status = "closed"
            room.updated_at = datetime.now(UTC)
            return room


collaboration_store = CollaborationStore()
