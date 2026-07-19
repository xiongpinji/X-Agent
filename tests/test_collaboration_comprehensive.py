"""Comprehensive tests for collaboration system components.

Tests cover:
- CollaborationMessage creation and serialization
- CollaborationRoom lifecycle
- CollaborationStore operations
- Room membership management
- Message posting and retrieval
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.app.core.collaboration import (
    CollaborationMessage,
    CollaborationRoom,
    CollaborationStore,
)


class TestCollaborationMessage:
    """Test CollaborationMessage model."""

    def test_message_creation(self) -> None:
        now = datetime.now(UTC)
        message = CollaborationMessage(
            message_id="msg-123",
            room_id="room-1",
            sender_id="user-1",
            sender_type="user",
            content="Hello, world!",
            created_at=now,
        )
        assert message.message_id == "msg-123"
        assert message.room_id == "room-1"
        assert message.sender_id == "user-1"
        assert message.sender_type == "user"
        assert message.content == "Hello, world!"
        assert message.created_at == now
        assert message.metadata == {}

    def test_message_with_metadata(self) -> None:
        now = datetime.now(UTC)
        metadata = {"priority": "high", "tags": ["urgent"]}
        message = CollaborationMessage(
            message_id="msg-123",
            room_id="room-1",
            sender_id="agent-1",
            sender_type="agent",
            content="Important update",
            created_at=now,
            metadata=metadata,
        )
        assert message.metadata == metadata
        assert message.sender_type == "agent"

    def test_message_model_dump(self) -> None:
        now = datetime.now(UTC)
        message = CollaborationMessage(
            message_id="msg-123",
            room_id="room-1",
            sender_id="user-1",
            sender_type="user",
            content="Test message",
            created_at=now,
            metadata={"key": "value"},
        )
        data = message.model_dump()
        assert data["message_id"] == "msg-123"
        assert data["room_id"] == "room-1"
        assert data["sender_id"] == "user-1"
        assert data["sender_type"] == "user"
        assert data["content"] == "Test message"
        assert data["created_at"] == now.isoformat()
        assert data["metadata"] == {"key": "value"}


class TestCollaborationRoom:
    """Test CollaborationRoom model."""

    def test_room_creation(self) -> None:
        now = datetime.now(UTC)
        room = CollaborationRoom(
            room_id="room-1",
            topic="Project Discussion",
            tenant_id="tenant-1",
            created_by="user-1",
            created_at=now,
            updated_at=now,
        )
        assert room.room_id == "room-1"
        assert room.topic == "Project Discussion"
        assert room.tenant_id == "tenant-1"
        assert room.created_by == "user-1"
        assert room.members == []
        assert room.messages == []
        assert room.status == "active"
        assert room.memory_scope == {}
        assert room.memory_refs == []

    def test_room_with_members(self) -> None:
        now = datetime.now(UTC)
        members = ["user-1", "user-2", "agent-1"]
        room = CollaborationRoom(
            room_id="room-1",
            topic="Team Meeting",
            tenant_id="tenant-1",
            created_by="user-1",
            created_at=now,
            updated_at=now,
            members=members,
        )
        assert room.members == members
        assert len(room.members) == 3

    def test_room_with_messages(self) -> None:
        now = datetime.now(UTC)
        msg1 = CollaborationMessage(
            message_id="msg-1",
            room_id="room-1",
            sender_id="user-1",
            sender_type="user",
            content="First message",
            created_at=now,
        )
        msg2 = CollaborationMessage(
            message_id="msg-2",
            room_id="room-1",
            sender_id="user-2",
            sender_type="user",
            content="Second message",
            created_at=now,
        )
        room = CollaborationRoom(
            room_id="room-1",
            topic="Discussion",
            tenant_id="tenant-1",
            created_by="user-1",
            created_at=now,
            updated_at=now,
            messages=[msg1, msg2],
        )
        assert len(room.messages) == 2
        assert room.messages[0].content == "First message"

    def test_room_with_memory_scope(self) -> None:
        now = datetime.now(UTC)
        memory_scope = {
            "visibility": "shared",
            "share_scope": "room",
        }
        room = CollaborationRoom(
            room_id="room-1",
            topic="Discussion",
            tenant_id="tenant-1",
            created_by="user-1",
            created_at=now,
            updated_at=now,
            memory_scope=memory_scope,
        )
        assert room.memory_scope == memory_scope

    def test_room_model_dump(self) -> None:
        now = datetime.now(UTC)
        msg = CollaborationMessage(
            message_id="msg-1",
            room_id="room-1",
            sender_id="user-1",
            sender_type="user",
            content="Test",
            created_at=now,
        )
        room = CollaborationRoom(
            room_id="room-1",
            topic="Discussion",
            tenant_id="tenant-1",
            created_by="user-1",
            created_at=now,
            updated_at=now,
            members=["user-1", "user-2"],
            messages=[msg],
        )
        data = room.model_dump()
        assert data["room_id"] == "room-1"
        assert data["topic"] == "Discussion"
        assert data["message_count"] == 1
        assert len(data["members"]) == 2
        assert len(data["messages"]) == 1

    def test_room_with_agent_memory_refs(self) -> None:
        now = datetime.now(UTC)
        agent_memory_refs = {
            "agent-1": ["mem-1", "mem-2"],
            "agent-2": ["mem-3"],
        }
        room = CollaborationRoom(
            room_id="room-1",
            topic="Discussion",
            tenant_id="tenant-1",
            created_by="user-1",
            created_at=now,
            updated_at=now,
            agent_memory_refs=agent_memory_refs,
        )
        assert room.agent_memory_refs == agent_memory_refs
        assert len(room.agent_memory_refs["agent-1"]) == 2


class TestCollaborationStore:
    """Test CollaborationStore operations."""

    def test_store_creation(self) -> None:
        store = CollaborationStore()
        assert store._rooms == {}

    def test_create_room(self) -> None:
        store = CollaborationStore()
        room = store.create_room(
            topic="Test Room",
            tenant_id="tenant-1",
            created_by="user-1",
        )
        assert room.room_id is not None
        assert room.topic == "Test Room"
        assert room.tenant_id == "tenant-1"
        assert room.created_by == "user-1"
        assert room.status == "active"

    def test_create_room_with_members(self) -> None:
        store = CollaborationStore()
        members = ["user-1", "user-2"]
        room = store.create_room(
            topic="Team Room",
            tenant_id="tenant-1",
            created_by="user-1",
            members=members,
        )
        assert room.members == members

    def test_create_room_with_memory_scope(self) -> None:
        store = CollaborationStore()
        memory_scope = {"visibility": "shared"}
        room = store.create_room(
            topic="Shared Room",
            tenant_id="tenant-1",
            created_by="user-1",
            memory_scope=memory_scope,
        )
        assert room.memory_scope == memory_scope

    def test_get_room(self) -> None:
        store = CollaborationStore()
        created_room = store.create_room(
            topic="Test Room",
            tenant_id="tenant-1",
            created_by="user-1",
        )
        retrieved_room = store.get_room(created_room.room_id)
        assert retrieved_room is not None
        assert retrieved_room.room_id == created_room.room_id
        assert retrieved_room.topic == "Test Room"

    def test_get_nonexistent_room(self) -> None:
        store = CollaborationStore()
        room = store.get_room("nonexistent-room-id")
        assert room is None

    def test_list_rooms(self) -> None:
        store = CollaborationStore()
        room1 = store.create_room(
            topic="Room 1",
            tenant_id="tenant-1",
            created_by="user-1",
        )
        room2 = store.create_room(
            topic="Room 2",
            tenant_id="tenant-1",
            created_by="user-1",
        )
        rooms = store.list_rooms()
        assert len(rooms) == 2
        assert room1.room_id in [r.room_id for r in rooms]
        assert room2.room_id in [r.room_id for r in rooms]

    def test_list_rooms_by_tenant(self) -> None:
        store = CollaborationStore()
        room1 = store.create_room(
            topic="Room 1",
            tenant_id="tenant-1",
            created_by="user-1",
        )
        room2 = store.create_room(
            topic="Room 2",
            tenant_id="tenant-2",
            created_by="user-1",
        )
        rooms_t1 = store.list_rooms(tenant_id="tenant-1")
        rooms_t2 = store.list_rooms(tenant_id="tenant-2")
        assert len(rooms_t1) == 1
        assert len(rooms_t2) == 1
        assert rooms_t1[0].room_id == room1.room_id
        assert rooms_t2[0].room_id == room2.room_id

    def test_list_rooms_empty(self) -> None:
        store = CollaborationStore()
        rooms = store.list_rooms()
        assert rooms == []

    def test_list_rooms_sorted_by_updated_at(self) -> None:
        store = CollaborationStore()
        room1 = store.create_room(
            topic="Room 1",
            tenant_id="tenant-1",
            created_by="user-1",
        )
        room2 = store.create_room(
            topic="Room 2",
            tenant_id="tenant-1",
            created_by="user-1",
        )
        # room2 should be more recent
        rooms = store.list_rooms()
        assert rooms[0].room_id == room2.room_id
        assert rooms[1].room_id == room1.room_id

    def test_post_message(self) -> None:
        store = CollaborationStore()
        room = store.create_room(
            topic="Test Room",
            tenant_id="tenant-1",
            created_by="user-1",
        )
        message = store.post_message(
            room_id=room.room_id,
            sender_id="user-1",
            sender_type="user",
            content="Hello!",
        )
        assert message.room_id == room.room_id
        assert message.sender_id == "user-1"
        assert message.content == "Hello!"
        # Verify message was added to room
        updated_room = store.get_room(room.room_id)
        assert len(updated_room.messages) == 1

    def test_post_message_to_nonexistent_room(self) -> None:
        store = CollaborationStore()
        with pytest.raises(ValueError):
            store.post_message(
                room_id="nonexistent-room",
                sender_id="user-1",
                sender_type="user",
                content="Hello!",
            )

    def test_add_member(self) -> None:
        store = CollaborationStore()
        room = store.create_room(
            topic="Test Room",
            tenant_id="tenant-1",
            created_by="user-1",
        )
        store.add_member(room.room_id, "user-2")
        updated_room = store.get_room(room.room_id)
        assert "user-2" in updated_room.members

    def test_add_member_duplicate(self) -> None:
        store = CollaborationStore()
        room = store.create_room(
            topic="Test Room",
            tenant_id="tenant-1",
            created_by="user-1",
            members=["user-1"],
        )
        store.add_member(room.room_id, "user-1")
        updated_room = store.get_room(room.room_id)
        # Should not add duplicate
        assert updated_room.members.count("user-1") == 1

    def test_remove_member(self) -> None:
        store = CollaborationStore()
        room = store.create_room(
            topic="Test Room",
            tenant_id="tenant-1",
            created_by="user-1",
            members=["user-1", "user-2"],
        )
        store.remove_member(room.room_id, "user-2")
        updated_room = store.get_room(room.room_id)
        assert "user-2" not in updated_room.members
        assert "user-1" in updated_room.members

    def test_close_room(self) -> None:
        store = CollaborationStore()
        room = store.create_room(
            topic="Test Room",
            tenant_id="tenant-1",
            created_by="user-1",
        )
        store.close_room(room.room_id)
        updated_room = store.get_room(room.room_id)
        assert updated_room.status == "closed"

    def test_close_nonexistent_room(self) -> None:
        store = CollaborationStore()
        with pytest.raises(ValueError):
            store.close_room("nonexistent-room")

    def test_add_memory_ref(self) -> None:
        store = CollaborationStore()
        room = store.create_room(
            topic="Test Room",
            tenant_id="tenant-1",
            created_by="user-1",
        )
        store.add_memory_ref(room.room_id, "mem-123")
        updated_room = store.get_room(room.room_id)
        assert "mem-123" in updated_room.memory_refs

    def test_add_agent_memory_ref(self) -> None:
        store = CollaborationStore()
        room = store.create_room(
            topic="Test Room",
            tenant_id="tenant-1",
            created_by="user-1",
        )
        store.add_agent_memory_ref(room.room_id, "agent-1", "mem-123")
        updated_room = store.get_room(room.room_id)
        assert "agent-1" in updated_room.agent_memory_refs
        assert "mem-123" in updated_room.agent_memory_refs["agent-1"]

    def test_thread_safety(self) -> None:
        """Test that store operations are thread-safe."""
        import threading

        store = CollaborationStore()
        room = store.create_room(
            topic="Test Room",
            tenant_id="tenant-1",
            created_by="user-1",
        )

        def add_messages():
            for i in range(10):
                store.post_message(
                    room_id=room.room_id,
                    sender_id=f"user-{i}",
                    sender_type="user",
                    content=f"Message {i}",
                )

        threads = [threading.Thread(target=add_messages) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        updated_room = store.get_room(room.room_id)
        assert len(updated_room.messages) == 30
