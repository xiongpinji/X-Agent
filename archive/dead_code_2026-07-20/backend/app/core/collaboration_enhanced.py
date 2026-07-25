"""Enhanced collaboration system with real-time editing, permissions, and notifications."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from threading import RLock
from typing import Any, Callable, Optional
from uuid import uuid4

from backend.app.core.memory import MemoryScope


class PermissionLevel(str, Enum):
    """Permission levels for collaboration."""
    VIEW = "view"
    COMMENT = "comment"
    EDIT = "edit"
    MANAGE = "manage"


class UserRole(str, Enum):
    """User roles in collaboration."""
    OWNER = "owner"
    EDITOR = "editor"
    COMMENTER = "commenter"
    VIEWER = "viewer"


class ConflictResolutionStrategy(str, Enum):
    """Strategies for resolving conflicts."""
    LAST_WRITE_WINS = "last_write_wins"
    FIRST_WRITE_WINS = "first_write_wins"
    MANUAL = "manual"
    AUTO_MERGE = "auto_merge"


@dataclass
class Operation:
    """Represents a single operation in collaborative editing."""
    op_id: str
    user_id: str
    timestamp: datetime
    op_type: str  # "insert", "delete", "replace"
    position: int
    content: str
    version: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op_id": self.op_id,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "op_type": self.op_type,
            "position": self.position,
            "content": self.content,
            "version": self.version,
            "metadata": self.metadata,
        }


@dataclass
class Conflict:
    """Represents a conflict between operations."""
    conflict_id: str
    op1: Operation
    op2: Operation
    created_at: datetime
    status: str = "unresolved"  # "unresolved", "resolved", "manual_review"
    resolution: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "op1": self.op1.to_dict(),
            "op2": self.op2.to_dict(),
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "resolution": self.resolution,
            "resolved_by": self.resolved_by,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


@dataclass
class DocumentVersion:
    """Represents a version of a document."""
    version_id: str
    version_number: int
    content: str
    created_by: str
    created_at: datetime
    operations: list[Operation] = field(default_factory=list)
    parent_version: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version_id": self.version_id,
            "version_number": self.version_number,
            "content": self.content,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "operations": [op.to_dict() for op in self.operations],
            "parent_version": self.parent_version,
            "metadata": self.metadata,
        }


@dataclass
class Comment:
    """Represents a comment on a document."""
    comment_id: str
    document_id: str
    user_id: str
    content: str
    position: int
    created_at: datetime
    updated_at: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    replies: list[Comment] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "comment_id": self.comment_id,
            "document_id": self.document_id,
            "user_id": self.user_id,
            "content": self.content,
            "position": self.position,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "replies": [reply.to_dict() for reply in self.replies],
            "metadata": self.metadata,
        }


@dataclass
class UserCursor:
    """Represents a user's cursor position."""
    user_id: str
    position: int
    selection_start: int
    selection_end: int
    updated_at: datetime
    color: str = ""
    name: str = ""


@dataclass
class Permission:
    """Represents a permission grant."""
    permission_id: str
    user_id: str
    resource_id: str
    level: PermissionLevel
    granted_by: str
    granted_at: datetime
    expires_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "permission_id": self.permission_id,
            "user_id": self.user_id,
            "resource_id": self.resource_id,
            "level": self.level.value,
            "granted_by": self.granted_by,
            "granted_at": self.granted_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata,
        }


@dataclass
class ShareLink:
    """Represents a shareable link."""
    link_id: str
    document_id: str
    created_by: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    password: Optional[str] = None
    permission_level: PermissionLevel = PermissionLevel.VIEW
    access_count: int = 0
    last_accessed_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "link_id": self.link_id,
            "document_id": self.document_id,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "permission_level": self.permission_level.value,
            "access_count": self.access_count,
            "last_accessed_at": self.last_accessed_at.isoformat() if self.last_accessed_at else None,
            "metadata": self.metadata,
        }


@dataclass
class ActivityLog:
    """Represents an activity log entry."""
    log_id: str
    document_id: str
    user_id: str
    action: str
    details: dict[str, Any]
    created_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "log_id": self.log_id,
            "document_id": self.document_id,
            "user_id": self.user_id,
            "action": self.action,
            "details": self.details,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


class OperationalTransform:
    """Implements Operational Transformation for conflict-free collaborative editing."""

    @staticmethod
    def transform(op1: Operation, op2: Operation) -> tuple[Operation, Operation]:
        """Transform two concurrent operations to maintain consistency."""
        if op1.timestamp > op2.timestamp:
            op1, op2 = op2, op1

        if op1.op_type == "insert" and op2.op_type == "insert":
            if op1.position < op2.position:
                return op1, Operation(
                    op_id=op2.op_id,
                    user_id=op2.user_id,
                    timestamp=op2.timestamp,
                    op_type=op2.op_type,
                    position=op2.position + len(op1.content),
                    content=op2.content,
                    version=op2.version,
                    metadata=op2.metadata,
                )
            elif op1.position > op2.position:
                return Operation(
                    op_id=op1.op_id,
                    user_id=op1.user_id,
                    timestamp=op1.timestamp,
                    op_type=op1.op_type,
                    position=op1.position + len(op2.content),
                    content=op1.content,
                    version=op1.version,
                    metadata=op1.metadata,
                ), op2
            else:
                if op1.user_id < op2.user_id:
                    return op1, Operation(
                        op_id=op2.op_id,
                        user_id=op2.user_id,
                        timestamp=op2.timestamp,
                        op_type=op2.op_type,
                        position=op2.position + len(op1.content),
                        content=op2.content,
                        version=op2.version,
                        metadata=op2.metadata,
                    )
                else:
                    return Operation(
                        op_id=op1.op_id,
                        user_id=op1.user_id,
                        timestamp=op1.timestamp,
                        op_type=op1.op_type,
                        position=op1.position + len(op2.content),
                        content=op1.content,
                        version=op1.version,
                        metadata=op1.metadata,
                    ), op2

        elif op1.op_type == "delete" and op2.op_type == "delete":
            if op1.position < op2.position:
                return op1, Operation(
                    op_id=op2.op_id,
                    user_id=op2.user_id,
                    timestamp=op2.timestamp,
                    op_type=op2.op_type,
                    position=max(op1.position, op2.position - len(op1.content)),
                    content=op2.content,
                    version=op2.version,
                    metadata=op2.metadata,
                )
            else:
                return Operation(
                    op_id=op1.op_id,
                    user_id=op1.user_id,
                    timestamp=op1.timestamp,
                    op_type=op1.op_type,
                    position=max(op1.position - len(op2.content), op2.position),
                    content=op1.content,
                    version=op1.version,
                    metadata=op1.metadata,
                ), op2

        elif op1.op_type == "insert" and op2.op_type == "delete":
            if op1.position <= op2.position:
                return op1, Operation(
                    op_id=op2.op_id,
                    user_id=op2.user_id,
                    timestamp=op2.timestamp,
                    op_type=op2.op_type,
                    position=op2.position + len(op1.content),
                    content=op2.content,
                    version=op2.version,
                    metadata=op2.metadata,
                )
            else:
                return Operation(
                    op_id=op1.op_id,
                    user_id=op1.user_id,
                    timestamp=op1.timestamp,
                    op_type=op1.op_type,
                    position=op1.position - len(op2.content),
                    content=op1.content,
                    version=op1.version,
                    metadata=op1.metadata,
                ), op2

        else:  # delete then insert
            if op2.position <= op1.position:
                return Operation(
                    op_id=op1.op_id,
                    user_id=op1.user_id,
                    timestamp=op1.timestamp,
                    op_type=op1.op_type,
                    position=op1.position + len(op2.content),
                    content=op1.content,
                    version=op1.version,
                    metadata=op1.metadata,
                ), op2
            else:
                return op1, Operation(
                    op_id=op2.op_id,
                    user_id=op2.user_id,
                    timestamp=op2.timestamp,
                    op_type=op2.op_type,
                    position=op2.position - len(op1.content),
                    content=op2.content,
                    version=op2.version,
                    metadata=op2.metadata,
                )

    @staticmethod
    def apply_operation(content: str, operation: Operation) -> str:
        """Apply an operation to content."""
        if operation.op_type == "insert":
            return content[:operation.position] + operation.content + content[operation.position:]
        elif operation.op_type == "delete":
            return content[:operation.position] + content[operation.position + len(operation.content):]
        elif operation.op_type == "replace":
            return content[:operation.position] + operation.content + content[operation.position + len(operation.content):]
        return content


class CollaborativeDocument:
    """Represents a collaborative document with version control and conflict resolution."""

    def __init__(
        self,
        doc_id: str,
        title: str,
        owner_id: str,
        content: str = "",
        conflict_strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.AUTO_MERGE,
    ):
        self.doc_id = doc_id
        self.title = title
        self.owner_id = owner_id
        self.content = content
        self.conflict_strategy = conflict_strategy
        self.created_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

        self.version_number = 0
        self.versions: dict[str, DocumentVersion] = {}
        self.operations: list[Operation] = []
        self.conflicts: dict[str, Conflict] = {}
        self.comments: dict[str, Comment] = {}
        self.user_cursors: dict[str, UserCursor] = {}
        self.activity_logs: list[ActivityLog] = []

        self._create_version(owner_id, content)
        self._lock = RLock()

    def _create_version(self, user_id: str, content: str) -> DocumentVersion:
        """Create a new version of the document."""
        version = DocumentVersion(
            version_id=str(uuid4()),
            version_number=self.version_number,
            content=content,
            created_by=user_id,
            created_at=datetime.now(UTC),
            parent_version=list(self.versions.values())[-1].version_id if self.versions else None,
        )
        self.versions[version.version_id] = version
        self.version_number += 1
        return version

    def apply_operation(self, operation: Operation) -> bool:
        """Apply an operation to the document."""
        with self._lock:
            try:
                self.content = OperationalTransform.apply_operation(self.content, operation)
                self.operations.append(operation)
                self.updated_at = datetime.now(UTC)

                self._log_activity(
                    operation.user_id,
                    "operation_applied",
                    {
                        "op_id": operation.op_id,
                        "op_type": operation.op_type,
                        "position": operation.position,
                    },
                )
                return True
            except Exception:
                return False

    def detect_conflicts(self, new_operation: Operation) -> list[Conflict]:
        """Detect conflicts with existing operations."""
        detected_conflicts = []
        with self._lock:
            for existing_op in self.operations[-10:]:
                if existing_op.user_id != new_operation.user_id and existing_op.version == new_operation.version:
                    if self._operations_conflict(existing_op, new_operation):
                        conflict = Conflict(
                            conflict_id=str(uuid4()),
                            op1=existing_op,
                            op2=new_operation,
                            created_at=datetime.now(UTC),
                        )
                        self.conflicts[conflict.conflict_id] = conflict
                        detected_conflicts.append(conflict)

        return detected_conflicts

    def _operations_conflict(self, op1: Operation, op2: Operation) -> bool:
        """Check if two operations conflict."""
        if op1.op_type == "delete" and op2.op_type == "delete":
            return op1.position == op2.position
        elif op1.op_type == "insert" and op2.op_type == "delete":
            return op1.position <= op2.position < op1.position + len(op1.content)
        elif op1.op_type == "delete" and op2.op_type == "insert":
            return op2.position <= op1.position < op2.position + len(op2.content)
        return False

    def resolve_conflict(
        self,
        conflict_id: str,
        resolution: str,
        resolved_by: str,
    ) -> bool:
        """Resolve a conflict."""
        with self._lock:
            conflict = self.conflicts.get(conflict_id)
            if conflict is None:
                return False

            conflict.status = "resolved"
            conflict.resolution = resolution
            conflict.resolved_by = resolved_by
            conflict.resolved_at = datetime.now(UTC)

            self._log_activity(
                resolved_by,
                "conflict_resolved",
                {
                    "conflict_id": conflict_id,
                    "resolution": resolution,
                },
            )
            return True

    def add_comment(
        self,
        user_id: str,
        content: str,
        position: int,
        parent_comment_id: Optional[str] = None,
    ) -> Comment:
        """Add a comment to the document."""
        with self._lock:
            comment = Comment(
                comment_id=str(uuid4()),
                document_id=self.doc_id,
                user_id=user_id,
                content=content,
                position=position,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

            if parent_comment_id:
                parent = self.comments.get(parent_comment_id)
                if parent:
                    parent.replies.append(comment)
            else:
                self.comments[comment.comment_id] = comment

            self._log_activity(
                user_id,
                "comment_added",
                {
                    "comment_id": comment.comment_id,
                    "position": position,
                },
            )
            return comment

    def resolve_comment(self, comment_id: str) -> bool:
        """Mark a comment as resolved."""
        with self._lock:
            comment = self.comments.get(comment_id)
            if comment:
                comment.resolved = True
                comment.resolved_at = datetime.now(UTC)
                self._log_activity(
                    comment.user_id,
                    "comment_resolved",
                    {"comment_id": comment_id},
                )
                return True
            return False

    def update_cursor(self, user_id: str, position: int, selection_start: int, selection_end: int, color: str = "", name: str = "") -> UserCursor:
        """Update a user's cursor position."""
        with self._lock:
            cursor = UserCursor(
                user_id=user_id,
                position=position,
                selection_start=selection_start,
                selection_end=selection_end,
                updated_at=datetime.now(UTC),
                color=color,
                name=name,
            )
            self.user_cursors[user_id] = cursor
            return cursor

    def get_active_cursors(self, exclude_user_id: Optional[str] = None) -> list[UserCursor]:
        """Get active cursors (updated in last 30 seconds)."""
        with self._lock:
            now = datetime.now(UTC)
            active = []
            for cursor in self.user_cursors.values():
                if (now - cursor.updated_at).total_seconds() < 30:
                    if exclude_user_id is None or cursor.user_id != exclude_user_id:
                        active.append(cursor)
            return active

    def _log_activity(self, user_id: str, action: str, details: dict[str, Any]) -> None:
        """Log an activity."""
        log = ActivityLog(
            log_id=str(uuid4()),
            document_id=self.doc_id,
            user_id=user_id,
            action=action,
            details=details,
            created_at=datetime.now(UTC),
        )
        self.activity_logs.append(log)

    def get_activity_history(self, limit: int = 50) -> list[ActivityLog]:
        """Get activity history."""
        with self._lock:
            return self.activity_logs[-limit:]

    def rollback_to_version(self, version_id: str) -> bool:
        """Rollback to a previous version."""
        with self._lock:
            version = self.versions.get(version_id)
            if version is None:
                return False

            self.content = version.content
            self.updated_at = datetime.now(UTC)
            self._log_activity(
                version.created_by,
                "version_rollback",
                {"version_id": version_id, "version_number": version.version_number},
            )
            return True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        with self._lock:
            return {
                "doc_id": self.doc_id,
                "title": self.title,
                "owner_id": self.owner_id,
                "content": self.content,
                "version_number": self.version_number,
                "created_at": self.created_at.isoformat(),
                "updated_at": self.updated_at.isoformat(),
                "conflict_strategy": self.conflict_strategy.value,
                "operation_count": len(self.operations),
                "conflict_count": len(self.conflicts),
                "comment_count": len(self.comments),
                "active_users": len(self.user_cursors),
            }


class CollaborationStore:
    """Store for managing collaborative documents and permissions."""

    def __init__(self):
        self._documents: dict[str, CollaborativeDocument] = {}
        self._permissions: dict[str, list[Permission]] = {}
        self._share_links: dict[str, ShareLink] = {}
        self._invitations: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    def create_document(
        self,
        title: str,
        owner_id: str,
        content: str = "",
        conflict_strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.AUTO_MERGE,
    ) -> CollaborativeDocument:
        """Create a new collaborative document."""
        with self._lock:
            doc = CollaborativeDocument(
                doc_id=str(uuid4()),
                title=title,
                owner_id=owner_id,
                content=content,
                conflict_strategy=conflict_strategy,
            )
            self._documents[doc.doc_id] = doc
            self._grant_permission(owner_id, doc.doc_id, PermissionLevel.MANAGE, owner_id)
            return doc

    def get_document(self, doc_id: str) -> Optional[CollaborativeDocument]:
        """Get a document by ID."""
        return self._documents.get(doc_id)

    def list_documents(self, user_id: str) -> list[CollaborativeDocument]:
        """List documents accessible to a user."""
        with self._lock:
            docs = []
            for doc in self._documents.values():
                if self._has_permission(user_id, doc.doc_id, PermissionLevel.VIEW):
                    docs.append(doc)
            return sorted(docs, key=lambda d: d.updated_at, reverse=True)

    def _grant_permission(
        self,
        user_id: str,
        resource_id: str,
        level: PermissionLevel,
        granted_by: str,
        expires_at: Optional[datetime] = None,
    ) -> Permission:
        """Grant a permission."""
        permission = Permission(
            permission_id=str(uuid4()),
            user_id=user_id,
            resource_id=resource_id,
            level=level,
            granted_by=granted_by,
            granted_at=datetime.now(UTC),
            expires_at=expires_at,
        )
        key = f"{user_id}:{resource_id}"
        if key not in self._permissions:
            self._permissions[key] = []
        self._permissions[key].append(permission)
        return permission

    def grant_permission(
        self,
        user_id: str,
        resource_id: str,
        level: PermissionLevel,
        granted_by: str,
        expires_at: Optional[datetime] = None,
    ) -> Permission:
        """Grant a permission to a user."""
        with self._lock:
            return self._grant_permission(user_id, resource_id, level, granted_by, expires_at)

    def _has_permission(self, user_id: str, resource_id: str, required_level: PermissionLevel) -> bool:
        """Check if a user has a permission."""
        key = f"{user_id}:{resource_id}"
        permissions = self._permissions.get(key, [])

        level_order = [PermissionLevel.VIEW, PermissionLevel.COMMENT, PermissionLevel.EDIT, PermissionLevel.MANAGE]
        required_index = level_order.index(required_level)

        for perm in permissions:
            if not perm.is_expired():
                perm_index = level_order.index(perm.level)
                if perm_index >= required_index:
                    return True
        return False

    def has_permission(self, user_id: str, resource_id: str, required_level: PermissionLevel) -> bool:
        """Check if a user has a permission."""
        with self._lock:
            return self._has_permission(user_id, resource_id, required_level)

    def revoke_permission(self, user_id: str, resource_id: str) -> bool:
        """Revoke all permissions for a user on a resource."""
        with self._lock:
            key = f"{user_id}:{resource_id}"
            if key in self._permissions:
                del self._permissions[key]
                return True
            return False

    def create_share_link(
        self,
        doc_id: str,
        created_by: str,
        permission_level: PermissionLevel = PermissionLevel.VIEW,
        expires_at: Optional[datetime] = None,
        password: Optional[str] = None,
    ) -> ShareLink:
        """Create a shareable link."""
        with self._lock:
            link = ShareLink(
                link_id=str(uuid4()),
                document_id=doc_id,
                created_by=created_by,
                created_at=datetime.now(UTC),
                expires_at=expires_at,
                password=password,
                permission_level=permission_level,
            )
            self._share_links[link.link_id] = link
            return link

    def get_share_link(self, link_id: str) -> Optional[ShareLink]:
        """Get a share link."""
        return self._share_links.get(link_id)

    def access_share_link(self, link_id: str, password: Optional[str] = None) -> Optional[CollaborativeDocument]:
        """Access a document via share link."""
        with self._lock:
            link = self._share_links.get(link_id)
            if link is None or link.is_expired():
                return None

            if link.password and link.password != password:
                return None

            link.access_count += 1
            link.last_accessed_at = datetime.now(UTC)

            doc = self._documents.get(link.document_id)
            return doc

    def send_invitation(
        self,
        doc_id: str,
        inviter_id: str,
        invitee_email: str,
        permission_level: PermissionLevel,
        message: str = "",
    ) -> dict[str, Any]:
        """Send an invitation to collaborate."""
        with self._lock:
            invitation = {
                "invitation_id": str(uuid4()),
                "doc_id": doc_id,
                "inviter_id": inviter_id,
                "invitee_email": invitee_email,
                "permission_level": permission_level.value,
                "message": message,
                "created_at": datetime.now(UTC).isoformat(),
                "status": "pending",
            }
            self._invitations[invitation["invitation_id"]] = invitation
            return invitation

    def accept_invitation(self, invitation_id: str, user_id: str) -> bool:
        """Accept an invitation."""
        with self._lock:
            invitation = self._invitations.get(invitation_id)
            if invitation is None or invitation["status"] != "pending":
                return False

            doc_id = invitation["doc_id"]
            level = PermissionLevel(invitation["permission_level"])
            self._grant_permission(user_id, doc_id, level, invitation["inviter_id"])

            invitation["status"] = "accepted"
            invitation["accepted_at"] = datetime.now(UTC).isoformat()
            return True

    def get_document_permissions(self, doc_id: str) -> list[Permission]:
        """Get all permissions for a document."""
        with self._lock:
            perms = []
            for key, perm_list in self._permissions.items():
                if key.endswith(f":{doc_id}"):
                    perms.extend([p for p in perm_list if not p.is_expired()])
            return perms


collaboration_store = CollaborationStore()
