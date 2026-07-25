"""Comprehensive tests for collaboration system."""

import pytest

# P1-09: collaboration_enhanced 已归档至 archive/dead_code_2026-07-20/
pytest.importorskip(
    "backend.app.core.collaboration_enhanced",
    reason="collaboration_enhanced archived (P1-09)",
)

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from backend.app.core.collaboration_enhanced import (
    CollaborativeDocument,
    CollaborationStore,
    ConflictResolutionStrategy,
    Operation,
    OperationalTransform,
    PermissionLevel,
    Comment,
    Conflict,
)
from backend.app.core.notification_system import (
    NotificationChannel,
    NotificationPriority,
    NotificationType,
    NotificationStore,
    NotificationService,
    NotificationPreference,
)


class TestOperationalTransform:
    """Test Operational Transformation algorithm."""

    def test_insert_insert_same_position(self):
        """Test two inserts at the same position."""
        op1 = Operation(
            op_id="op1",
            user_id="user1",
            timestamp=datetime.now(UTC),
            op_type="insert",
            position=5,
            content="hello",
            version=1,
        )

        op2 = Operation(
            op_id="op2",
            user_id="user2",
            timestamp=datetime.now(UTC) + timedelta(seconds=1),
            op_type="insert",
            position=5,
            content="world",
            version=1,
        )

        t_op1, t_op2 = OperationalTransform.transform(op1, op2)

        assert t_op1.position == 5
        assert t_op2.position == 10

    def test_insert_delete_no_conflict(self):
        """Test insert and delete at different positions."""
        op1 = Operation(
            op_id="op1",
            user_id="user1",
            timestamp=datetime.now(UTC),
            op_type="insert",
            position=0,
            content="hello",
            version=1,
        )

        op2 = Operation(
            op_id="op2",
            user_id="user2",
            timestamp=datetime.now(UTC) + timedelta(seconds=1),
            op_type="delete",
            position=10,
            content="x",
            version=1,
        )

        t_op1, t_op2 = OperationalTransform.transform(op1, op2)

        assert t_op1.position == 0
        assert t_op2.position == 15

    def test_apply_insert_operation(self):
        """Test applying insert operation."""
        content = "hello world"
        op = Operation(
            op_id="op1",
            user_id="user1",
            timestamp=datetime.now(UTC),
            op_type="insert",
            position=5,
            content=" beautiful",
            version=1,
        )

        result = OperationalTransform.apply_operation(content, op)
        assert result == "hello beautiful world"

    def test_apply_delete_operation(self):
        """Test applying delete operation."""
        content = "hello world"
        op = Operation(
            op_id="op1",
            user_id="user1",
            timestamp=datetime.now(UTC),
            op_type="delete",
            position=5,
            content=" ",
            version=1,
        )

        result = OperationalTransform.apply_operation(content, op)
        assert result == "helloworld"


class TestCollaborativeDocument:
    """Test CollaborativeDocument class."""

    def test_create_document(self):
        """Test creating a document."""
        doc = CollaborativeDocument(
            doc_id="doc1",
            title="Test Document",
            owner_id="user1",
            content="Initial content",
        )

        assert doc.doc_id == "doc1"
        assert doc.title == "Test Document"
        assert doc.owner_id == "user1"
        assert doc.content == "Initial content"
        assert doc.version_number == 1

    def test_apply_operation(self):
        """Test applying an operation."""
        doc = CollaborativeDocument(
            doc_id="doc1",
            title="Test",
            owner_id="user1",
            content="hello",
        )

        op = Operation(
            op_id="op1",
            user_id="user1",
            timestamp=datetime.now(UTC),
            op_type="insert",
            position=5,
            content=" world",
            version=1,
        )

        assert doc.apply_operation(op)
        assert doc.content == "hello world"
        assert len(doc.operations) == 1

    def test_detect_conflicts(self):
        """Test conflict detection."""
        doc = CollaborativeDocument(
            doc_id="doc1",
            title="Test",
            owner_id="user1",
            content="hello world",
        )

        op1 = Operation(
            op_id="op1",
            user_id="user1",
            timestamp=datetime.now(UTC),
            op_type="delete",
            position=5,
            content=" ",
            version=1,
        )
        doc.apply_operation(op1)

        op2 = Operation(
            op_id="op2",
            user_id="user2",
            timestamp=datetime.now(UTC) + timedelta(seconds=1),
            op_type="delete",
            position=5,
            content=" ",
            version=1,
        )

        conflicts = doc.detect_conflicts(op2)
        assert len(conflicts) > 0

    def test_add_comment(self):
        """Test adding a comment."""
        doc = CollaborativeDocument(
            doc_id="doc1",
            title="Test",
            owner_id="user1",
        )

        comment = doc.add_comment(
            user_id="user2",
            content="This is a comment",
            position=0,
        )

        assert comment.user_id == "user2"
        assert comment.content == "This is a comment"
        assert comment.position == 0
        assert not comment.resolved

    def test_resolve_comment(self):
        """Test resolving a comment."""
        doc = CollaborativeDocument(
            doc_id="doc1",
            title="Test",
            owner_id="user1",
        )

        comment = doc.add_comment(
            user_id="user2",
            content="This is a comment",
            position=0,
        )

        assert doc.resolve_comment(comment.comment_id)
        assert comment.resolved

    def test_update_cursor(self):
        """Test updating cursor position."""
        doc = CollaborativeDocument(
            doc_id="doc1",
            title="Test",
            owner_id="user1",
        )

        cursor = doc.update_cursor(
            user_id="user1",
            position=10,
            selection_start=5,
            selection_end=15,
            color="#FF0000",
            name="User 1",
        )

        assert cursor.user_id == "user1"
        assert cursor.position == 10
        assert cursor.color == "#FF0000"

    def test_get_active_cursors(self):
        """Test getting active cursors."""
        doc = CollaborativeDocument(
            doc_id="doc1",
            title="Test",
            owner_id="user1",
        )

        doc.update_cursor("user1", 10, 5, 15)
        doc.update_cursor("user2", 20, 15, 25)

        cursors = doc.get_active_cursors()
        assert len(cursors) == 2

    def test_rollback_to_version(self):
        """Test rolling back to a previous version."""
        doc = CollaborativeDocument(
            doc_id="doc1",
            title="Test",
            owner_id="user1",
            content="version 0",
        )

        version_id = list(doc.versions.keys())[0]

        op = Operation(
            op_id="op1",
            user_id="user1",
            timestamp=datetime.now(UTC),
            op_type="insert",
            position=9,
            content=" modified",
            version=1,
        )
        doc.apply_operation(op)

        assert doc.content == "version 0 modified"

        assert doc.rollback_to_version(version_id)
        assert doc.content == "version 0"


class TestCollaborationStore:
    """Test CollaborationStore class."""

    def test_create_document(self):
        """Test creating a document."""
        store = CollaborationStore()
        doc = store.create_document(
            title="Test",
            owner_id="user1",
            content="Initial",
        )

        assert doc.title == "Test"
        assert doc.owner_id == "user1"

    def test_get_document(self):
        """Test getting a document."""
        store = CollaborationStore()
        doc = store.create_document(
            title="Test",
            owner_id="user1",
        )

        retrieved = store.get_document(doc.doc_id)
        assert retrieved is not None
        assert retrieved.doc_id == doc.doc_id

    def test_list_documents(self):
        """Test listing documents."""
        store = CollaborationStore()
        doc1 = store.create_document(title="Doc1", owner_id="user1")
        doc2 = store.create_document(title="Doc2", owner_id="user1")

        docs = store.list_documents("user1")
        assert len(docs) >= 2

    def test_grant_permission(self):
        """Test granting permission."""
        store = CollaborationStore()
        doc = store.create_document(title="Test", owner_id="user1")

        perm = store.grant_permission(
            user_id="user2",
            resource_id=doc.doc_id,
            level=PermissionLevel.EDIT,
            granted_by="user1",
        )

        assert perm.user_id == "user2"
        assert perm.level == PermissionLevel.EDIT

    def test_has_permission(self):
        """Test checking permission."""
        store = CollaborationStore()
        doc = store.create_document(title="Test", owner_id="user1")

        store.grant_permission(
            user_id="user2",
            resource_id=doc.doc_id,
            level=PermissionLevel.EDIT,
            granted_by="user1",
        )

        assert store.has_permission(
            user_id="user2",
            resource_id=doc.doc_id,
            required_level=PermissionLevel.EDIT,
        )

    def test_revoke_permission(self):
        """Test revoking permission."""
        store = CollaborationStore()
        doc = store.create_document(title="Test", owner_id="user1")

        store.grant_permission(
            user_id="user2",
            resource_id=doc.doc_id,
            level=PermissionLevel.EDIT,
            granted_by="user1",
        )

        assert store.revoke_permission("user2", doc.doc_id)
        assert not store.has_permission(
            user_id="user2",
            resource_id=doc.doc_id,
            required_level=PermissionLevel.VIEW,
        )

    def test_create_share_link(self):
        """Test creating a share link."""
        store = CollaborationStore()
        doc = store.create_document(title="Test", owner_id="user1")

        link = store.create_share_link(
            doc_id=doc.doc_id,
            created_by="user1",
            permission_level=PermissionLevel.VIEW,
        )

        assert link.document_id == doc.doc_id
        assert link.permission_level == PermissionLevel.VIEW

    def test_access_share_link(self):
        """Test accessing a share link."""
        store = CollaborationStore()
        doc = store.create_document(title="Test", owner_id="user1")

        link = store.create_share_link(
            doc_id=doc.doc_id,
            created_by="user1",
            permission_level=PermissionLevel.VIEW,
        )

        accessed_doc = store.access_share_link(link.link_id)
        assert accessed_doc is not None
        assert accessed_doc.doc_id == doc.doc_id

    def test_send_invitation(self):
        """Test sending an invitation."""
        store = CollaborationStore()
        doc = store.create_document(title="Test", owner_id="user1")

        invitation = store.send_invitation(
            doc_id=doc.doc_id,
            inviter_id="user1",
            invitee_email="user2@example.com",
            permission_level=PermissionLevel.EDIT,
        )

        assert invitation["doc_id"] == doc.doc_id
        assert invitation["status"] == "pending"

    def test_accept_invitation(self):
        """Test accepting an invitation."""
        store = CollaborationStore()
        doc = store.create_document(title="Test", owner_id="user1")

        invitation = store.send_invitation(
            doc_id=doc.doc_id,
            inviter_id="user1",
            invitee_email="user2@example.com",
            permission_level=PermissionLevel.EDIT,
        )

        assert store.accept_invitation(invitation["invitation_id"], "user2")
        assert store.has_permission(
            user_id="user2",
            resource_id=doc.doc_id,
            required_level=PermissionLevel.EDIT,
        )


class TestNotificationStore:
    """Test NotificationStore class."""

    def test_create_notification(self):
        """Test creating a notification."""
        store = NotificationStore()
        notif = store.create_notification(
            user_id="user1",
            notification_type=NotificationType.DOCUMENT_SHARED,
            title="Document Shared",
            content="A document has been shared with you",
        )

        assert notif.user_id == "user1"
        assert notif.notification_type == NotificationType.DOCUMENT_SHARED

    def test_get_user_notifications(self):
        """Test getting user notifications."""
        store = NotificationStore()
        store.create_notification(
            user_id="user1",
            notification_type=NotificationType.DOCUMENT_SHARED,
            title="Test",
            content="Test",
        )

        notifs = store.get_user_notifications("user1")
        assert len(notifs) == 1

    def test_mark_as_read(self):
        """Test marking notification as read."""
        store = NotificationStore()
        notif = store.create_notification(
            user_id="user1",
            notification_type=NotificationType.DOCUMENT_SHARED,
            title="Test",
            content="Test",
        )

        assert store.mark_as_read(notif.notification_id)
        assert notif.is_read()

    def test_get_unread_count(self):
        """Test getting unread count."""
        store = NotificationStore()
        store.create_notification(
            user_id="user1",
            notification_type=NotificationType.DOCUMENT_SHARED,
            title="Test1",
            content="Test",
        )
        store.create_notification(
            user_id="user1",
            notification_type=NotificationType.COMMENT_ADDED,
            title="Test2",
            content="Test",
        )

        assert store.get_unread_count("user1") == 2

    def test_notification_preference(self):
        """Test notification preferences."""
        store = NotificationStore()
        pref = store.get_preference("user1")

        assert pref.user_id == "user1"
        assert pref.enabled

        pref.enabled = False
        store.set_preference(pref)

        retrieved = store.get_preference("user1")
        assert not retrieved.enabled


class TestPerformance:
    """Performance tests for collaboration system."""

    def test_concurrent_operations(self):
        """Test handling concurrent operations."""
        doc = CollaborativeDocument(
            doc_id="doc1",
            title="Test",
            owner_id="user1",
            content="",
        )

        for i in range(100):
            op = Operation(
                op_id=f"op{i}",
                user_id=f"user{i % 10}",
                timestamp=datetime.now(UTC),
                op_type="insert",
                position=i,
                content=f"text{i}",
                version=1,
            )
            doc.apply_operation(op)

        assert len(doc.operations) == 100

    def test_large_document(self):
        """Test handling large documents."""
        large_content = "x" * 1000000

        doc = CollaborativeDocument(
            doc_id="doc1",
            title="Large",
            owner_id="user1",
            content=large_content,
        )

        assert len(doc.content) == 1000000

    def test_many_comments(self):
        """Test handling many comments."""
        doc = CollaborativeDocument(
            doc_id="doc1",
            title="Test",
            owner_id="user1",
        )

        for i in range(100):
            doc.add_comment(
                user_id=f"user{i % 10}",
                content=f"Comment {i}",
                position=i,
            )

        assert len(doc.comments) == 100

    def test_many_cursors(self):
        """Test handling many active cursors."""
        doc = CollaborativeDocument(
            doc_id="doc1",
            title="Test",
            owner_id="user1",
        )

        for i in range(50):
            doc.update_cursor(
                user_id=f"user{i}",
                position=i * 10,
                selection_start=i * 10,
                selection_end=i * 10 + 5,
            )

        cursors = doc.get_active_cursors()
        assert len(cursors) == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
