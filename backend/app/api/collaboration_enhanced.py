"""Enhanced collaboration API endpoints."""

from __future__ import annotations

from typing import Annotated, Optional
from datetime import datetime, timedelta, UTC

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.core.collaboration_enhanced import (
    CollaborativeDocument,
    CollaborationStore,
    ConflictResolutionStrategy,
    Operation,
    PermissionLevel,
    collaboration_store,
)
from backend.app.core.notification_system import (
    NotificationChannel,
    NotificationPriority,
    NotificationType,
    notification_service,
    notification_store,
)
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/collaborate", tags=["collaboration"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# Request/Response Models
class DocumentCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(default="", max_length=1000000)
    conflict_strategy: str = Field(default="auto_merge")


class DocumentUpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


class OperationRequest(BaseModel):
    op_type: str = Field(..., regex="^(insert|delete|replace)$")
    position: int = Field(..., ge=0)
    content: str = Field(default="")


class CommentRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    position: int = Field(..., ge=0)
    parent_comment_id: Optional[str] = None


class PermissionGrantRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    level: str = Field(..., regex="^(view|comment|edit|manage)$")
    expires_in_days: Optional[int] = None


class ShareLinkCreateRequest(BaseModel):
    permission_level: str = Field(default="view", regex="^(view|comment|edit)$")
    expires_in_days: Optional[int] = None
    password: Optional[str] = None


class InvitationRequest(BaseModel):
    invitee_email: str = Field(..., regex="^[^@]+@[^@]+\\.[^@]+$")
    permission_level: str = Field(default="edit", regex="^(view|comment|edit)$")
    message: Optional[str] = None


class ConflictResolutionRequest(BaseModel):
    conflict_id: str
    resolution: str = Field(..., regex="^(keep_op1|keep_op2|merge)$")


class CursorUpdateRequest(BaseModel):
    position: int = Field(..., ge=0)
    selection_start: int = Field(..., ge=0)
    selection_end: int = Field(..., ge=0)
    color: Optional[str] = None
    name: Optional[str] = None


# Document Endpoints
@router.post("/documents")
async def create_document(
    request: DocumentCreateRequest,
    principal: PrincipalDependency,
) -> dict:
    """Create a new collaborative document."""
    enforce_scope(principal, "collaboration:write")

    strategy = ConflictResolutionStrategy(request.conflict_strategy)
    doc = collaboration_store.create_document(
        title=request.title,
        owner_id=principal.user_id,
        content=request.content,
        conflict_strategy=strategy,
    )

    await notification_service.send_notification(
        user_id=principal.user_id,
        notification_type=NotificationType.DOCUMENT_UPDATED,
        title="Document Created",
        content=f"Document '{doc.title}' has been created",
        related_resource_id=doc.doc_id,
        related_resource_type="document",
    )

    return doc.to_dict()


@router.get("/documents/{doc_id}")
async def get_document(
    doc_id: str,
    principal: PrincipalDependency,
) -> dict:
    """Get a document."""
    enforce_scope(principal, "collaboration:read")

    if not collaboration_store.has_permission(principal.user_id, doc_id, PermissionLevel.VIEW):
        raise api_error(403, ErrorCode.PERMISSION_DENIED, "Access denied to this document")

    doc = collaboration_store.get_document(doc_id)
    if not doc:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Document not found")

    return doc.to_dict()


@router.get("/documents")
async def list_documents(
    principal: PrincipalDependency,
) -> list[dict]:
    """List documents accessible to the user."""
    enforce_scope(principal, "collaboration:read")

    docs = collaboration_store.list_documents(principal.user_id)
    return [doc.to_dict() for doc in docs]


@router.put("/documents/{doc_id}")
async def update_document(
    doc_id: str,
    request: DocumentUpdateRequest,
    principal: PrincipalDependency,
) -> dict:
    """Update a document."""
    enforce_scope(principal, "collaboration:write")

    if not collaboration_store.has_permission(principal.user_id, doc_id, PermissionLevel.EDIT):
        raise api_error(403, ErrorCode.PERMISSION_DENIED, "Permission denied")

    doc = collaboration_store.get_document(doc_id)
    if not doc:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Document not found")

    if request.title:
        doc.title = request.title
    if request.content is not None:
        doc.content = request.content

    doc.updated_at = datetime.now(UTC)

    return doc.to_dict()


# Operation Endpoints
@router.post("/documents/{doc_id}/operations")
async def apply_operation(
    doc_id: str,
    request: OperationRequest,
    principal: PrincipalDependency,
) -> dict:
    """Apply an operation to a document."""
    enforce_scope(principal, "collaboration:write")

    if not collaboration_store.has_permission(principal.user_id, doc_id, PermissionLevel.EDIT):
        raise api_error(403, ErrorCode.PERMISSION_DENIED, "Permission denied")

    doc = collaboration_store.get_document(doc_id)
    if not doc:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Document not found")

    operation = Operation(
        op_id=str(__import__("uuid").uuid4()),
        user_id=principal.user_id,
        timestamp=datetime.now(UTC),
        op_type=request.op_type,
        position=request.position,
        content=request.content,
        version=doc.version_number,
    )

    conflicts = doc.detect_conflicts(operation)
    if conflicts and doc.conflict_strategy == ConflictResolutionStrategy.MANUAL:
        return {
            "status": "conflict_detected",
            "conflicts": [c.to_dict() for c in conflicts],
            "operation": operation.to_dict(),
        }

    if doc.apply_operation(operation):
        return {
            "status": "applied",
            "operation": operation.to_dict(),
            "document": doc.to_dict(),
        }
    else:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "Failed to apply operation")


@router.get("/documents/{doc_id}/operations")
async def get_operations(
    doc_id: str,
    principal: PrincipalDependency,
    limit: int = Query(50, ge=1, le=1000),
) -> list[dict]:
    """Get operations for a document."""
    enforce_scope(principal, "collaboration:read")

    if not collaboration_store.has_permission(principal.user_id, doc_id, PermissionLevel.VIEW):
        raise api_error(403, ErrorCode.PERMISSION_DENIED, "Permission denied")

    doc = collaboration_store.get_document(doc_id)
    if not doc:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Document not found")

    return [op.to_dict() for op in doc.operations[-limit:]]


# Comment Endpoints
@router.post("/documents/{doc_id}/comments")
async def add_comment(
    doc_id: str,
    request: CommentRequest,
    principal: PrincipalDependency,
) -> dict:
    """Add a comment to a document."""
    enforce_scope(principal, "collaboration:write")

    if not collaboration_store.has_permission(principal.user_id, doc_id, PermissionLevel.COMMENT):
        raise api_error(403, ErrorCode.PERMISSION_DENIED, "Permission denied")

    doc = collaboration_store.get_document(doc_id)
    if not doc:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Document not found")

    comment = doc.add_comment(
        user_id=principal.user_id,
        content=request.content,
        position=request.position,
        parent_comment_id=request.parent_comment_id,
    )

    await notification_service.send_notification(
        user_id=doc.owner_id,
        notification_type=NotificationType.COMMENT_ADDED,
        title="New Comment",
        content=f"{principal.user_id} commented on your document",
        related_resource_id=doc_id,
        related_resource_type="document",
        action_url=f"/documents/{doc_id}#comment-{comment.comment_id}",
    )

    return comment.to_dict()


@router.get("/documents/{doc_id}/comments")
async def get_comments(
    doc_id: str,
    principal: PrincipalDependency,
) -> list[dict]:
    """Get comments for a document."""
    enforce_scope(principal, "collaboration:read")

    if not collaboration_store.has_permission(principal.user_id, doc_id, PermissionLevel.VIEW):
        raise api_error(403, ErrorCode.PERMISSION_DENIED, "Permission denied")

    doc = collaboration_store.get_document(doc_id)
    if not doc:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Document not found")

    return [c.to_dict() for c in doc.comments.values()]


@router.post("/documents/{doc_id}/comments/{comment_id}/resolve")
async def resolve_comment(
    doc_id: str,
    comment_id: str,
    principal: PrincipalDependency,
) -> dict:
    """Resolve a comment."""
    enforce_scope(principal, "collaboration:write")

    if not collaboration_store.has_permission(principal.user_id, doc_id, PermissionLevel.EDIT):
        raise api_error(403, ErrorCode.PERMISSION_DENIED, "Permission denied")

    doc = collaboration_store.get_document(doc_id)
    if not doc:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Document not found")

    if doc.resolve_comment(comment_id):
        return {"status": "resolved"}
    else:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Comment not found")


# Permission Endpoints
@router.post("/documents/{doc_id}/permissions")
async def grant_permission(
    doc_id: str,
    request: PermissionGrantRequest,
    principal: PrincipalDependency,
) -> dict:
    """Grant permission to a user."""
    enforce_scope(principal, "collaboration:manage")

    if not collaboration_store.has_permission(principal.user_id, doc_id, PermissionLevel.MANAGE):
        raise api_error(403, ErrorCode.PERMISSION_DENIED, "Permission denied")

    doc = collaboration_store.get_document(doc_id)
    if not doc:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Document not found")

    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.now(UTC) + timedelta(days=request.expires_in_days)

    level = PermissionLevel(request.level)
    permission = collaboration_store.grant_permission(
        user_id=request.user_id,
        resource_id=doc_id,
        level=level,
        granted_by=principal.user_id,
        expires_at=expires_at,
    )

    await notification_service.send_notification(
        user_id=request.user_id,
        notification_type=NotificationType.PERMISSION_GRANTED,
        title="Permission Granted",
        content=f"You have been granted {level.value} access to '{doc.title}'",
        related_resource_id=doc_id,
        related_resource_type="document",
    )

    return permission.to_dict()


@router.get("/documents/{doc_id}/permissions")
async def get_permissions(
    doc_id: str,
    principal: PrincipalDependency,
) -> list[dict]:
    """Get permissions for a document."""
    enforce_scope(principal, "collaboration:read")

    if not collaboration_store.has_permission(principal.user_id, doc_id, PermissionLevel.MANAGE):
        raise api_error(403, ErrorCode.PERMISSION_DENIED, "Permission denied")

    permissions = collaboration_store.get_document_permissions(doc_id)
    return [p.to_dict() for p in permissions]


@router.delete("/documents/{doc_id}/permissions/{user_id}")
async def revoke_permission(
    doc_id: str,
    user_id: str,
    principal: PrincipalDependency,
) -> dict:
    """Revoke permission from a user."""
    enforce_scope(principal, "collaboration:manage")

    if not collaboration_store.has_permission(principal.user_id, doc_id, PermissionLevel.MANAGE):
        raise api_error(403, ErrorCode.PERMISSION_DENIED, "Permission denied")

    if collaboration_store.revoke_permission(user_id, doc_id):
        return {"status": "revoked"}
    else:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Permission not found")


# Share Link Endpoints
@router.post("/documents/{doc_id}/share-links")
async def create_share_link(
    doc_id: str,
    request: ShareLinkCreateRequest,
    principal: PrincipalDependency,
) -> dict:
    """Create a shareable link."""
    enforce_scope(principal, "collaboration:manage")

    if not collaboration_store.has_permission(principal.user_id, doc_id, PermissionLevel.MANAGE):
        raise api_error(403, ErrorCode.PERMISSION_DENIED, "Permission denied")

    doc = collaboration_store.get_document(doc_id)
    if not doc:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Document not found")

    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.now(UTC) + timedelta(days=request.expires_in_days)

    level = PermissionLevel(request.permission_level)
    link = collaboration_store.create_share_link(
        doc_id=doc_id,
        created_by=principal.user_id,
        permission_level=level,
        expires_at=expires_at,
        password=request.password,
    )

    return link.to_dict()


@router.get("/share-links/{link_id}")
async def access_share_link(
    link_id: str,
    password: Optional[str] = None,
) -> dict:
    """Access a document via share link."""
    link = collaboration_store.get_share_link(link_id)
    if not link:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Share link not found")

    doc = collaboration_store.access_share_link(link_id, password)
    if not doc:
        raise api_error(403, ErrorCode.PERMISSION_DENIED, "Invalid password or link expired")

    return {
        "document": doc.to_dict(),
        "link": link.to_dict(),
    }


# Invitation Endpoints
@router.post("/documents/{doc_id}/invitations")
async def send_invitation(
    doc_id: str,
    request: InvitationRequest,
    principal: PrincipalDependency,
) -> dict:
    """Send an invitation to collaborate."""
    enforce_scope(principal, "collaboration:manage")

    if not collaboration_store.has_permission(principal.user_id, doc_id, PermissionLevel.MANAGE):
        raise api_error(403, ErrorCode.PERMISSION_DENIED, "Permission denied")

    doc = collaboration_store.get_document(doc_id)
    if not doc:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Document not found")

    level = PermissionLevel(request.permission_level)
    invitation = collaboration_store.send_invitation(
        doc_id=doc_id,
        inviter_id=principal.user_id,
        invitee_email=request.invitee_email,
        permission_level=level,
        message=request.message or "",
    )

    return invitation


@router.post("/invitations/{invitation_id}/accept")
async def accept_invitation(
    invitation_id: str,
    principal: PrincipalDependency,
) -> dict:
    """Accept an invitation."""
    enforce_scope(principal, "collaboration:write")

    if collaboration_store.accept_invitation(invitation_id, principal.user_id):
        return {"status": "accepted"}
    else:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "Invalid or expired invitation")


# Conflict Resolution Endpoints
@router.post("/documents/{doc_id}/conflicts/{conflict_id}/resolve")
async def resolve_conflict(
    doc_id: str,
    conflict_id: str,
    request: ConflictResolutionRequest,
    principal: PrincipalDependency,
) -> dict:
    """Resolve a conflict."""
    enforce_scope(principal, "collaboration:write")

    if not collaboration_store.has_permission(principal.user_id, doc_id, PermissionLevel.EDIT):
        raise api_error(403, ErrorCode.PERMISSION_DENIED, "Permission denied")

    doc = collaboration_store.get_document(doc_id)
    if not doc:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Document not found")

    if doc.resolve_conflict(conflict_id, request.resolution, principal.user_id):
        await notification_service.send_notification(
            user_id=doc.owner_id,
            notification_type=NotificationType.CONFLICT_RESOLVED,
            title="Conflict Resolved",
            content=f"A conflict in '{doc.title}' has been resolved",
            related_resource_id=doc_id,
            related_resource_type="document",
        )
        return {"status": "resolved"}
    else:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Conflict not found")


# Cursor Tracking Endpoints
@router.post("/documents/{doc_id}/cursors")
async def update_cursor(
    doc_id: str,
    request: CursorUpdateRequest,
    principal: PrincipalDependency,
) -> dict:
    """Update cursor position."""
    enforce_scope(principal, "collaboration:read")

    if not collaboration_store.has_permission(principal.user_id, doc_id, PermissionLevel.VIEW):
        raise api_error(403, ErrorCode.PERMISSION_DENIED, "Permission denied")

    doc = collaboration_store.get_document(doc_id)
    if not doc:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Document not found")

    cursor = doc.update_cursor(
        user_id=principal.user_id,
        position=request.position,
        selection_start=request.selection_start,
        selection_end=request.selection_end,
        color=request.color or "",
        name=request.name or principal.user_id,
    )

    return {
        "cursor": {
            "user_id": cursor.user_id,
            "position": cursor.position,
            "selection_start": cursor.selection_start,
            "selection_end": cursor.selection_end,
            "color": cursor.color,
            "name": cursor.name,
            "updated_at": cursor.updated_at.isoformat(),
        },
        "active_cursors": [
            {
                "user_id": c.user_id,
                "position": c.position,
                "color": c.color,
                "name": c.name,
            }
            for c in doc.get_active_cursors(exclude_user_id=principal.user_id)
        ],
    }


@router.get("/documents/{doc_id}/cursors")
async def get_active_cursors(
    doc_id: str,
    principal: PrincipalDependency,
) -> list[dict]:
    """Get active cursors for a document."""
    enforce_scope(principal, "collaboration:read")

    if not collaboration_store.has_permission(principal.user_id, doc_id, PermissionLevel.VIEW):
        raise api_error(403, ErrorCode.PERMISSION_DENIED, "Permission denied")

    doc = collaboration_store.get_document(doc_id)
    if not doc:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Document not found")

    cursors = doc.get_active_cursors(exclude_user_id=principal.user_id)
    return [
        {
            "user_id": c.user_id,
            "position": c.position,
            "selection_start": c.selection_start,
            "selection_end": c.selection_end,
            "color": c.color,
            "name": c.name,
            "updated_at": c.updated_at.isoformat(),
        }
        for c in cursors
    ]


# Activity Log Endpoints
@router.get("/documents/{doc_id}/activity")
async def get_activity_history(
    doc_id: str,
    principal: PrincipalDependency,
    limit: int = Query(50, ge=1, le=500),
) -> list[dict]:
    """Get activity history for a document."""
    enforce_scope(principal, "collaboration:read")

    if not collaboration_store.has_permission(principal.user_id, doc_id, PermissionLevel.VIEW):
        raise api_error(403, ErrorCode.PERMISSION_DENIED, "Permission denied")

    doc = collaboration_store.get_document(doc_id)
    if not doc:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Document not found")

    logs = doc.get_activity_history(limit=limit)
    return [log.to_dict() for log in logs]


# Notification Endpoints
@router.get("/notifications")
async def get_notifications(
    principal: PrincipalDependency,
    unread_only: bool = False,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    """Get notifications for the user."""
    enforce_scope(principal, "collaboration:read")

    notifications = notification_store.get_user_notifications(
        user_id=principal.user_id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )

    unread_count = notification_store.get_unread_count(principal.user_id)

    return {
        "notifications": [n.to_dict() for n in notifications],
        "unread_count": unread_count,
        "total_count": len(notification_store._user_notifications.get(principal.user_id, [])),
    }


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    principal: PrincipalDependency,
) -> dict:
    """Mark a notification as read."""
    enforce_scope(principal, "collaboration:write")

    if notification_store.mark_as_read(notification_id):
        return {"status": "marked_as_read"}
    else:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Notification not found")


@router.post("/notifications/read-all")
async def mark_all_notifications_read(
    principal: PrincipalDependency,
) -> dict:
    """Mark all notifications as read."""
    enforce_scope(principal, "collaboration:write")

    count = notification_store.mark_all_as_read(principal.user_id)
    return {"marked_as_read": count}


@router.get("/notification-preferences")
async def get_notification_preferences(
    principal: PrincipalDependency,
) -> dict:
    """Get notification preferences."""
    enforce_scope(principal, "collaboration:read")

    preference = notification_store.get_preference(principal.user_id)
    return preference.to_dict()


@router.put("/notification-preferences")
async def update_notification_preferences(
    request: dict,
    principal: PrincipalDependency,
) -> dict:
    """Update notification preferences."""
    enforce_scope(principal, "collaboration:write")

    preference = notification_store.get_preference(principal.user_id)

    if "enabled" in request:
        preference.enabled = request["enabled"]
    if "frequency" in request:
        preference.frequency = request["frequency"]
    if "quiet_hours_start" in request:
        preference.quiet_hours_start = request["quiet_hours_start"]
    if "quiet_hours_end" in request:
        preference.quiet_hours_end = request["quiet_hours_end"]
    if "aggregate_similar" in request:
        preference.aggregate_similar = request["aggregate_similar"]

    notification_store.set_preference(preference)
    return preference.to_dict()
