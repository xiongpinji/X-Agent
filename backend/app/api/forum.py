"""Forum API endpoints."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query

from backend.app.api.errors import api_error
from backend.app.api.pagination import PaginationParams, apply_pagination
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal
from backend.app.models.forum import (
    ForumPost,
    ForumComment,
    ForumNotification,
    ModerationRule,
    PostStatus,
    ModerationStatus,
    forum_store,
)

router = APIRouter(prefix="/api/v1/forum", tags=["forum"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# ============================================================================
# Post Endpoints
# ============================================================================


@router.post("/posts")
async def create_post(
    request: dict,
    principal: PrincipalDependency,
) -> dict:
    """Create a new forum post.

    Args:
        request: Post creation request with title, content, category, tags
        principal: Current user principal

    Returns:
        Created post object
    """
    title = request.get("title", "").strip()
    content = request.get("content", "").strip()
    category = request.get("category", "general")
    tags = request.get("tags", [])

    if not title or len(title) < 5:
        raise api_error(400, ErrorCode.INVALID_REQUEST, "Title must be at least 5 characters")
    if not content or len(content) < 20:
        raise api_error(400, ErrorCode.INVALID_REQUEST, "Content must be at least 20 characters")

    # Check moderation
    mod_status, mod_reason = forum_store.check_content_moderation(content)
    if mod_status == ModerationStatus.REJECTED:
        raise api_error(400, ErrorCode.INVALID_REQUEST, mod_reason)

    post = ForumPost(
        title=title,
        content=content,
        author_id=principal.user_id,
        author_name=principal.user_id,
        category=category,
        tags=tags,
        moderation_status=mod_status,
        moderation_reason=mod_reason,
    )

    created = forum_store.create_post(post)
    return created.model_dump()


@router.get("/posts")
async def list_posts(
    category: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    sort_by: str = Query("created_at", regex="^(created_at|views|likes|comments)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    principal: PrincipalDependency = None,
) -> dict:
    """List forum posts with filtering and pagination.

    Args:
        category: Filter by category
        tag: Filter by tag
        sort_by: Sort order (created_at, views, likes, comments)
        limit: Number of posts per page
        offset: Number of posts to skip
        principal: Current user principal

    Returns:
        Paginated list of posts
    """
    posts, total = forum_store.list_posts(
        category=category,
        tag=tag,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
    )

    return {
        "data": [p.model_dump() for p in posts],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/posts/{post_id}")
async def get_post(
    post_id: str,
    principal: PrincipalDependency = None,
) -> dict:
    """Get a specific post by ID.

    Args:
        post_id: Post ID
        principal: Current user principal

    Returns:
        Post object with details
    """
    post = forum_store.get_post(post_id)
    if not post:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Post not found")

    return post.model_dump()


@router.put("/posts/{post_id}")
async def update_post(
    post_id: str,
    request: dict,
    principal: PrincipalDependency,
) -> dict:
    """Update a forum post.

    Args:
        post_id: Post ID
        request: Update request with title, content, etc.
        principal: Current user principal

    Returns:
        Updated post object
    """
    post = forum_store.get_post(post_id)
    if not post:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Post not found")

    if post.author_id != principal.user_id:
        raise api_error(403, ErrorCode.FORBIDDEN, "You can only edit your own posts")

    # Update fields
    if "title" in request:
        post.title = request["title"].strip()
    if "content" in request:
        post.content = request["content"].strip()
    if "tags" in request:
        post.tags = request["tags"]

    # Re-check moderation
    mod_status, mod_reason = forum_store.check_content_moderation(post.content)
    post.moderation_status = mod_status
    post.moderation_reason = mod_reason

    updated = forum_store.update_post(post_id, post)
    return updated.model_dump()


@router.delete("/posts/{post_id}")
async def delete_post(
    post_id: str,
    principal: PrincipalDependency,
) -> dict:
    """Delete a forum post.

    Args:
        post_id: Post ID
        principal: Current user principal

    Returns:
        Success message
    """
    post = forum_store.get_post(post_id)
    if not post:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Post not found")

    if post.author_id != principal.user_id:
        raise api_error(403, ErrorCode.FORBIDDEN, "You can only delete your own posts")

    forum_store.delete_post(post_id)
    return {"message": "Post deleted successfully"}


# ============================================================================
# Comment Endpoints
# ============================================================================


@router.post("/posts/{post_id}/comments")
async def create_comment(
    post_id: str,
    request: dict,
    principal: PrincipalDependency,
) -> dict:
    """Create a comment on a post.

    Args:
        post_id: Post ID
        request: Comment creation request with content
        principal: Current user principal

    Returns:
        Created comment object
    """
    post = forum_store.get_post(post_id)
    if not post:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Post not found")

    content = request.get("content", "").strip()
    if not content or len(content) < 3:
        raise api_error(400, ErrorCode.INVALID_REQUEST, "Comment must be at least 3 characters")

    # Check moderation
    mod_status, mod_reason = forum_store.check_content_moderation(content)
    if mod_status == ModerationStatus.REJECTED:
        raise api_error(400, ErrorCode.INVALID_REQUEST, mod_reason)

    comment = ForumComment(
        post_id=post_id,
        content=content,
        author_id=principal.user_id,
        author_name=principal.user_id,
        parent_comment_id=request.get("parent_comment_id"),
        moderation_status=mod_status,
    )

    created = forum_store.create_comment(comment)

    # Create notification for post author
    if post.author_id != principal.user_id:
        notification = ForumNotification(
            user_id=post.author_id,
            type="comment_reply",
            related_user_id=principal.user_id,
            related_post_id=post_id,
            related_comment_id=created.id,
            message=f"{principal.user_id} commented on your post",
        )
        forum_store.create_notification(notification)

    return created.model_dump()


@router.get("/posts/{post_id}/comments")
async def list_comments(
    post_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: PrincipalDependency = None,
) -> dict:
    """List comments on a post.

    Args:
        post_id: Post ID
        limit: Number of comments per page
        offset: Number of comments to skip
        principal: Current user principal

    Returns:
        Paginated list of comments
    """
    post = forum_store.get_post(post_id)
    if not post:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Post not found")

    comments, total = forum_store.get_post_comments(post_id, limit=limit, offset=offset)

    return {
        "data": [c.model_dump() for c in comments],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.put("/comments/{comment_id}")
async def update_comment(
    comment_id: str,
    request: dict,
    principal: PrincipalDependency,
) -> dict:
    """Update a comment.

    Args:
        comment_id: Comment ID
        request: Update request with content
        principal: Current user principal

    Returns:
        Updated comment object
    """
    comment = forum_store.get_comment(comment_id)
    if not comment:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Comment not found")

    if comment.author_id != principal.user_id:
        raise api_error(403, ErrorCode.FORBIDDEN, "You can only edit your own comments")

    content = request.get("content", "").strip()
    if not content:
        raise api_error(400, ErrorCode.INVALID_REQUEST, "Comment content cannot be empty")

    comment.content = content
    updated = forum_store.update_comment(comment_id, comment)
    return updated.model_dump()


@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: str,
    principal: PrincipalDependency,
) -> dict:
    """Delete a comment.

    Args:
        comment_id: Comment ID
        principal: Current user principal

    Returns:
        Success message
    """
    comment = forum_store.get_comment(comment_id)
    if not comment:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Comment not found")

    if comment.author_id != principal.user_id:
        raise api_error(403, ErrorCode.FORBIDDEN, "You can only delete your own comments")

    forum_store.delete_comment(comment_id)
    return {"message": "Comment deleted successfully"}


# ============================================================================
# Like/Vote Endpoints
# ============================================================================


@router.post("/posts/{post_id}/like")
async def like_post(
    post_id: str,
    principal: PrincipalDependency,
) -> dict:
    """Like a post.

    Args:
        post_id: Post ID
        principal: Current user principal

    Returns:
        Success message with updated like count
    """
    post = forum_store.get_post(post_id)
    if not post:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Post not found")

    success = forum_store.like_post(principal.user_id, post_id)
    if not success:
        raise api_error(400, ErrorCode.INVALID_REQUEST, "You already liked this post")

    return {"message": "Post liked", "like_count": post.like_count}


@router.post("/posts/{post_id}/unlike")
async def unlike_post(
    post_id: str,
    principal: PrincipalDependency,
) -> dict:
    """Unlike a post.

    Args:
        post_id: Post ID
        principal: Current user principal

    Returns:
        Success message with updated like count
    """
    post = forum_store.get_post(post_id)
    if not post:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Post not found")

    success = forum_store.unlike_post(principal.user_id, post_id)
    if not success:
        raise api_error(400, ErrorCode.INVALID_REQUEST, "You haven't liked this post")

    return {"message": "Post unliked", "like_count": post.like_count}


@router.post("/comments/{comment_id}/like")
async def like_comment(
    comment_id: str,
    principal: PrincipalDependency,
) -> dict:
    """Like a comment.

    Args:
        comment_id: Comment ID
        principal: Current user principal

    Returns:
        Success message with updated like count
    """
    comment = forum_store.get_comment(comment_id)
    if not comment:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Comment not found")

    success = forum_store.like_comment(principal.user_id, comment_id)
    if not success:
        raise api_error(400, ErrorCode.INVALID_REQUEST, "You already liked this comment")

    return {"message": "Comment liked", "like_count": comment.like_count}


@router.post("/comments/{comment_id}/unlike")
async def unlike_comment(
    comment_id: str,
    principal: PrincipalDependency,
) -> dict:
    """Unlike a comment.

    Args:
        comment_id: Comment ID
        principal: Current user principal

    Returns:
        Success message with updated like count
    """
    comment = forum_store.get_comment(comment_id)
    if not comment:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Comment not found")

    success = forum_store.unlike_comment(principal.user_id, comment_id)
    if not success:
        raise api_error(400, ErrorCode.INVALID_REQUEST, "You haven't liked this comment")

    return {"message": "Comment unliked", "like_count": comment.like_count}


# ============================================================================
# Bookmark Endpoints
# ============================================================================


@router.post("/posts/{post_id}/bookmark")
async def bookmark_post(
    post_id: str,
    principal: PrincipalDependency,
) -> dict:
    """Bookmark a post.

    Args:
        post_id: Post ID
        principal: Current user principal

    Returns:
        Success message
    """
    post = forum_store.get_post(post_id)
    if not post:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Post not found")

    success = forum_store.bookmark_post(principal.user_id, post_id)
    if not success:
        raise api_error(400, ErrorCode.INVALID_REQUEST, "Post already bookmarked")

    return {"message": "Post bookmarked"}


@router.post("/posts/{post_id}/unbookmark")
async def unbookmark_post(
    post_id: str,
    principal: PrincipalDependency,
) -> dict:
    """Remove bookmark from a post.

    Args:
        post_id: Post ID
        principal: Current user principal

    Returns:
        Success message
    """
    success = forum_store.unbookmark_post(principal.user_id, post_id)
    if not success:
        raise api_error(400, ErrorCode.INVALID_REQUEST, "Post not bookmarked")

    return {"message": "Bookmark removed"}


@router.get("/bookmarks")
async def get_bookmarks(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    principal: PrincipalDependency = None,
) -> dict:
    """Get user's bookmarked posts.

    Args:
        limit: Number of posts per page
        offset: Number of posts to skip
        principal: Current user principal

    Returns:
        Paginated list of bookmarked posts
    """
    posts, total = forum_store.get_user_bookmarks(principal.user_id, limit=limit, offset=offset)

    return {
        "data": [p.model_dump() for p in posts],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ============================================================================
# User Follow Endpoints
# ============================================================================


@router.post("/users/{user_id}/follow")
async def follow_user(
    user_id: str,
    principal: PrincipalDependency,
) -> dict:
    """Follow a user.

    Args:
        user_id: User ID to follow
        principal: Current user principal

    Returns:
        Success message
    """
    success = forum_store.follow_user(principal.user_id, user_id)
    if not success:
        raise api_error(400, ErrorCode.INVALID_REQUEST, "Cannot follow this user")

    # Create notification
    notification = ForumNotification(
        user_id=user_id,
        type="user_follow",
        related_user_id=principal.user_id,
        message=f"{principal.user_id} started following you",
    )
    forum_store.create_notification(notification)

    return {"message": "User followed"}


@router.post("/users/{user_id}/unfollow")
async def unfollow_user(
    user_id: str,
    principal: PrincipalDependency,
) -> dict:
    """Unfollow a user.

    Args:
        user_id: User ID to unfollow
        principal: Current user principal

    Returns:
        Success message
    """
    success = forum_store.unfollow_user(principal.user_id, user_id)
    if not success:
        raise api_error(400, ErrorCode.INVALID_REQUEST, "User not followed")

    return {"message": "User unfollowed"}


@router.get("/users/{user_id}/followers")
async def get_followers(
    user_id: str,
    principal: PrincipalDependency = None,
) -> dict:
    """Get user's followers.

    Args:
        user_id: User ID
        principal: Current user principal

    Returns:
        List of follower user IDs
    """
    followers = forum_store.get_user_followers(user_id)
    return {"followers": followers, "count": len(followers)}


@router.get("/users/{user_id}/following")
async def get_following(
    user_id: str,
    principal: PrincipalDependency = None,
) -> dict:
    """Get users that a user is following.

    Args:
        user_id: User ID
        principal: Current user principal

    Returns:
        List of following user IDs
    """
    following = forum_store.get_user_following(user_id)
    return {"following": following, "count": len(following)}


# ============================================================================
# User Reputation Endpoints
# ============================================================================


@router.get("/users/{user_id}/reputation")
async def get_user_reputation(
    user_id: str,
    principal: PrincipalDependency = None,
) -> dict:
    """Get user's reputation.

    Args:
        user_id: User ID
        principal: Current user principal

    Returns:
        User reputation object
    """
    reputation = forum_store.get_user_reputation(user_id)
    if not reputation:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "User reputation not found")

    return reputation.model_dump()


# ============================================================================
# Notification Endpoints
# ============================================================================


@router.get("/notifications")
async def get_notifications(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    principal: PrincipalDependency = None,
) -> dict:
    """Get user's notifications.

    Args:
        limit: Number of notifications per page
        offset: Number of notifications to skip
        principal: Current user principal

    Returns:
        Paginated list of notifications
    """
    notifications, total = forum_store.get_user_notifications(
        principal.user_id,
        limit=limit,
        offset=offset,
    )

    return {
        "data": [n.model_dump() for n in notifications],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.put("/notifications/{notification_id}/read")
async def mark_notification_as_read(
    notification_id: str,
    principal: PrincipalDependency,
) -> dict:
    """Mark notification as read.

    Args:
        notification_id: Notification ID
        principal: Current user principal

    Returns:
        Success message
    """
    success = forum_store.mark_notification_as_read(notification_id)
    if not success:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Notification not found")

    return {"message": "Notification marked as read"}


# ============================================================================
# Moderation Endpoints
# ============================================================================


@router.post("/moderation/rules")
async def create_moderation_rule(
    request: dict,
    principal: PrincipalDependency,
) -> dict:
    """Create a moderation rule (admin only).

    Args:
        request: Rule creation request
        principal: Current user principal

    Returns:
        Created rule object
    """
    enforce_scope(principal, "forum:moderate")

    rule = ModerationRule(
        name=request.get("name", ""),
        description=request.get("description", ""),
        rule_type=request.get("rule_type", "keyword"),
        pattern=request.get("pattern", ""),
        action=request.get("action", "flag"),
        severity=request.get("severity", "low"),
    )

    created = forum_store.add_moderation_rule(rule)
    return created.model_dump()


@router.get("/moderation/rules")
async def list_moderation_rules(
    principal: PrincipalDependency,
) -> dict:
    """List moderation rules (admin only).

    Args:
        principal: Current user principal

    Returns:
        List of moderation rules
    """
    enforce_scope(principal, "forum:moderate")

    rules = forum_store.get_moderation_rules()
    return {"data": [r.model_dump() for r in rules]}


@router.post("/moderation/check")
async def check_content_moderation(
    request: dict,
    principal: PrincipalDependency,
) -> dict:
    """Check content against moderation rules.

    Args:
        request: Request with content to check
        principal: Current user principal

    Returns:
        Moderation status and reason
    """
    content = request.get("content", "")
    status, reason = forum_store.check_content_moderation(content)

    return {
        "status": status.value,
        "reason": reason,
    }
