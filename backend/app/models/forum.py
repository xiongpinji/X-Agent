"""Forum data models and storage layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import uuid4


class PostStatus(StrEnum):
    """Post status enumeration."""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ModerationStatus(StrEnum):
    """Content moderation status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FLAGGED = "flagged"


class UserReputation(StrEnum):
    """User reputation levels."""
    NEWBIE = "newbie"  # 0-50 points
    MEMBER = "member"  # 50-200 points
    CONTRIBUTOR = "contributor"  # 200-500 points
    EXPERT = "expert"  # 500-1000 points
    MODERATOR = "moderator"  # 1000+ points


@dataclass
class ForumPost:
    """Forum post model."""
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    content: str = ""
    author_id: str = ""
    author_name: str = ""
    category: str = ""  # e.g., "general", "bugs", "features", "showcase"
    tags: list[str] = field(default_factory=list)
    status: PostStatus = PostStatus.PUBLISHED
    moderation_status: ModerationStatus = ModerationStatus.APPROVED
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    is_pinned: bool = False
    is_locked: bool = False
    moderation_notes: str = ""
    moderation_reason: str = ""

    def model_dump(self, mode: str = "python") -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "author_id": self.author_id,
            "author_name": self.author_name,
            "category": self.category,
            "tags": self.tags,
            "status": self.status.value,
            "moderation_status": self.moderation_status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "view_count": self.view_count,
            "like_count": self.like_count,
            "comment_count": self.comment_count,
            "is_pinned": self.is_pinned,
            "is_locked": self.is_locked,
            "moderation_notes": self.moderation_notes,
            "moderation_reason": self.moderation_reason,
        }


@dataclass
class ForumComment:
    """Forum comment model."""
    id: str = field(default_factory=lambda: str(uuid4()))
    post_id: str = ""
    content: str = ""
    author_id: str = ""
    author_name: str = ""
    parent_comment_id: str | None = None  # For nested replies
    status: PostStatus = PostStatus.PUBLISHED
    moderation_status: ModerationStatus = ModerationStatus.APPROVED
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    like_count: int = 0
    is_deleted: bool = False
    moderation_notes: str = ""

    def model_dump(self, mode: str = "python") -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "post_id": self.post_id,
            "content": self.content,
            "author_id": self.author_id,
            "author_name": self.author_name,
            "parent_comment_id": self.parent_comment_id,
            "status": self.status.value,
            "moderation_status": self.moderation_status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "like_count": self.like_count,
            "is_deleted": self.is_deleted,
            "moderation_notes": self.moderation_notes,
        }


@dataclass
class UserReputationProfile:
    """User reputation model."""
    user_id: str = ""
    username: str = ""
    reputation_points: int = 0
    level: str = "newbie"
    badges: list[str] = field(default_factory=list)
    post_count: int = 0
    comment_count: int = 0
    helpful_votes: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def model_dump(self, mode: str = "python") -> dict:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "reputation_points": self.reputation_points,
            "level": self.level,
            "badges": self.badges,
            "post_count": self.post_count,
            "comment_count": self.comment_count,
            "helpful_votes": self.helpful_votes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class UserLike:
    """User like/vote model."""
    id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = ""
    post_id: str | None = None
    comment_id: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def model_dump(self, mode: str = "python") -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "post_id": self.post_id,
            "comment_id": self.comment_id,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class UserBookmark:
    """User bookmark/favorite model."""
    id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = ""
    post_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    def model_dump(self, mode: str = "python") -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "post_id": self.post_id,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class UserFollow:
    """User follow model."""
    id: str = field(default_factory=lambda: str(uuid4()))
    follower_id: str = ""
    following_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    def model_dump(self, mode: str = "python") -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "follower_id": self.follower_id,
            "following_id": self.following_id,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ForumNotification:
    """Forum notification model."""
    id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = ""
    type: str = ""  # "comment_reply", "post_like", "user_follow", etc.
    related_user_id: str = ""
    related_post_id: str = ""
    related_comment_id: str = ""
    message: str = ""
    is_read: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)

    def model_dump(self, mode: str = "python") -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "type": self.type,
            "related_user_id": self.related_user_id,
            "related_post_id": self.related_post_id,
            "related_comment_id": self.related_comment_id,
            "message": self.message,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ModerationRule:
    """Content moderation rule."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    rule_type: str = ""  # "keyword", "pattern", "length", "spam"
    pattern: str = ""
    action: str = "flag"  # "flag", "reject", "approve"
    severity: str = "low"  # "low", "medium", "high"
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)

    def model_dump(self, mode: str = "python") -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "rule_type": self.rule_type,
            "pattern": self.pattern,
            "action": self.action,
            "severity": self.severity,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
        }


class ForumStore:
    """In-memory forum data store."""

    def __init__(self):
        """Initialize forum store."""
        self.posts: dict[str, ForumPost] = {}
        self.comments: dict[str, ForumComment] = {}
        self.user_reputations: dict[str, UserReputationProfile] = {}
        self.likes: dict[str, UserLike] = {}
        self.bookmarks: dict[str, UserBookmark] = {}
        self.follows: dict[str, UserFollow] = {}
        self.notifications: dict[str, ForumNotification] = {}
        self.moderation_rules: dict[str, ModerationRule] = {}

    # Post operations
    def create_post(self, post: ForumPost) -> ForumPost:
        """Create a new post."""
        self.posts[post.id] = post
        self._update_user_reputation(post.author_id, 10)  # +10 points for posting
        return post

    def get_post(self, post_id: str) -> ForumPost | None:
        """Get a post by ID."""
        post = self.posts.get(post_id)
        if post:
            post.view_count += 1
        return post

    def update_post(self, post_id: str, post: ForumPost) -> ForumPost | None:
        """Update a post."""
        if post_id in self.posts:
            post.updated_at = datetime.utcnow()
            self.posts[post_id] = post
            return post
        return None

    def delete_post(self, post_id: str) -> bool:
        """Delete a post."""
        if post_id in self.posts:
            self.posts[post_id].status = PostStatus.DELETED
            return True
        return False

    def list_posts(
        self,
        category: str | None = None,
        tag: str | None = None,
        status: PostStatus = PostStatus.PUBLISHED,
        limit: int = 20,
        offset: int = 0,
        sort_by: str = "created_at",
    ) -> tuple[list[ForumPost], int]:
        """List posts with filtering and pagination."""
        posts = list(self.posts.values())

        # Filter by status
        posts = [p for p in posts if p.status == status]

        # Filter by category
        if category:
            posts = [p for p in posts if p.category == category]

        # Filter by tag
        if tag:
            posts = [p for p in posts if tag in p.tags]

        # Sort
        if sort_by == "created_at":
            posts.sort(key=lambda p: p.created_at, reverse=True)
        elif sort_by == "views":
            posts.sort(key=lambda p: p.view_count, reverse=True)
        elif sort_by == "likes":
            posts.sort(key=lambda p: p.like_count, reverse=True)
        elif sort_by == "comments":
            posts.sort(key=lambda p: p.comment_count, reverse=True)

        total = len(posts)
        return posts[offset : offset + limit], total

    # Comment operations
    def create_comment(self, comment: ForumComment) -> ForumComment:
        """Create a new comment."""
        self.comments[comment.id] = comment
        if comment.post_id in self.posts:
            self.posts[comment.post_id].comment_count += 1
        self._update_user_reputation(comment.author_id, 5)  # +5 points for commenting
        return comment

    def get_comment(self, comment_id: str) -> ForumComment | None:
        """Get a comment by ID."""
        return self.comments.get(comment_id)

    def get_post_comments(
        self,
        post_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ForumComment], int]:
        """Get comments for a post."""
        comments = [c for c in self.comments.values() if c.post_id == post_id and not c.is_deleted]
        comments.sort(key=lambda c: c.created_at)
        total = len(comments)
        return comments[offset : offset + limit], total

    def update_comment(self, comment_id: str, comment: ForumComment) -> ForumComment | None:
        """Update a comment."""
        if comment_id in self.comments:
            comment.updated_at = datetime.utcnow()
            self.comments[comment_id] = comment
            return comment
        return None

    def delete_comment(self, comment_id: str) -> bool:
        """Delete a comment."""
        if comment_id in self.comments:
            comment = self.comments[comment_id]
            comment.is_deleted = True
            if comment.post_id in self.posts:
                self.posts[comment.post_id].comment_count -= 1
            return True
        return False

    # Like operations
    def like_post(self, user_id: str, post_id: str) -> bool:
        """Like a post."""
        like_key = f"{user_id}:{post_id}"
        if like_key not in self.likes:
            like = UserLike(user_id=user_id, post_id=post_id)
            self.likes[like_key] = like
            if post_id in self.posts:
                self.posts[post_id].like_count += 1
                self._update_user_reputation(self.posts[post_id].author_id, 2)
            return True
        return False

    def unlike_post(self, user_id: str, post_id: str) -> bool:
        """Unlike a post."""
        like_key = f"{user_id}:{post_id}"
        if like_key in self.likes:
            del self.likes[like_key]
            if post_id in self.posts:
                self.posts[post_id].like_count = max(0, self.posts[post_id].like_count - 1)
            return True
        return False

    def like_comment(self, user_id: str, comment_id: str) -> bool:
        """Like a comment."""
        like_key = f"{user_id}:c:{comment_id}"
        if like_key not in self.likes:
            like = UserLike(user_id=user_id, comment_id=comment_id)
            self.likes[like_key] = like
            if comment_id in self.comments:
                self.comments[comment_id].like_count += 1
                self._update_user_reputation(self.comments[comment_id].author_id, 1)
            return True
        return False

    def unlike_comment(self, user_id: str, comment_id: str) -> bool:
        """Unlike a comment."""
        like_key = f"{user_id}:c:{comment_id}"
        if like_key in self.likes:
            del self.likes[like_key]
            if comment_id in self.comments:
                self.comments[comment_id].like_count = max(0, self.comments[comment_id].like_count - 1)
            return True
        return False

    # Bookmark operations
    def bookmark_post(self, user_id: str, post_id: str) -> bool:
        """Bookmark a post."""
        bookmark_key = f"{user_id}:{post_id}"
        if bookmark_key not in self.bookmarks:
            bookmark = UserBookmark(user_id=user_id, post_id=post_id)
            self.bookmarks[bookmark_key] = bookmark
            return True
        return False

    def unbookmark_post(self, user_id: str, post_id: str) -> bool:
        """Remove bookmark from a post."""
        bookmark_key = f"{user_id}:{post_id}"
        if bookmark_key in self.bookmarks:
            del self.bookmarks[bookmark_key]
            return True
        return False

    def get_user_bookmarks(self, user_id: str, limit: int = 20, offset: int = 0) -> tuple[list[ForumPost], int]:
        """Get user's bookmarked posts."""
        bookmarks = [b for b in self.bookmarks.values() if b.user_id == user_id]
        posts = [self.posts[b.post_id] for b in bookmarks if b.post_id in self.posts]
        posts.sort(key=lambda p: p.created_at, reverse=True)
        total = len(posts)
        return posts[offset : offset + limit], total

    # Follow operations
    def follow_user(self, follower_id: str, following_id: str) -> bool:
        """Follow a user."""
        if follower_id == following_id:
            return False
        follow_key = f"{follower_id}:{following_id}"
        if follow_key not in self.follows:
            follow = UserFollow(follower_id=follower_id, following_id=following_id)
            self.follows[follow_key] = follow
            return True
        return False

    def unfollow_user(self, follower_id: str, following_id: str) -> bool:
        """Unfollow a user."""
        follow_key = f"{follower_id}:{following_id}"
        if follow_key in self.follows:
            del self.follows[follow_key]
            return True
        return False

    def get_user_followers(self, user_id: str) -> list[str]:
        """Get user's followers."""
        return [f.follower_id for f in self.follows.values() if f.following_id == user_id]

    def get_user_following(self, user_id: str) -> list[str]:
        """Get users that a user is following."""
        return [f.following_id for f in self.follows.values() if f.follower_id == user_id]

    # Reputation operations
    def get_user_reputation(self, user_id: str) -> UserReputationProfile | None:
        """Get user reputation."""
        return self.user_reputations.get(user_id)

    def _update_user_reputation(self, user_id: str, points: int) -> None:
        """Update user reputation points."""
        if user_id not in self.user_reputations:
            self.user_reputations[user_id] = UserReputationProfile(user_id=user_id)

        rep = self.user_reputations[user_id]
        rep.reputation_points += points
        rep.updated_at = datetime.utcnow()

        # Update level based on points
        if rep.reputation_points >= 1000:
            rep.level = "moderator"
        elif rep.reputation_points >= 500:
            rep.level = "expert"
        elif rep.reputation_points >= 200:
            rep.level = "contributor"
        elif rep.reputation_points >= 50:
            rep.level = "member"
        else:
            rep.level = "newbie"

    # Notification operations
    def create_notification(self, notification: ForumNotification) -> ForumNotification:
        """Create a notification."""
        self.notifications[notification.id] = notification
        return notification

    def get_user_notifications(self, user_id: str, limit: int = 20, offset: int = 0) -> tuple[list[ForumNotification], int]:
        """Get user notifications."""
        notifications = [n for n in self.notifications.values() if n.user_id == user_id]
        notifications.sort(key=lambda n: n.created_at, reverse=True)
        total = len(notifications)
        return notifications[offset : offset + limit], total

    def mark_notification_as_read(self, notification_id: str) -> bool:
        """Mark notification as read."""
        if notification_id in self.notifications:
            self.notifications[notification_id].is_read = True
            return True
        return False

    # Moderation operations
    def add_moderation_rule(self, rule: ModerationRule) -> ModerationRule:
        """Add a moderation rule."""
        self.moderation_rules[rule.id] = rule
        return rule

    def get_moderation_rules(self) -> list[ModerationRule]:
        """Get all moderation rules."""
        return list(self.moderation_rules.values())

    def check_content_moderation(self, content: str) -> tuple[ModerationStatus, str]:
        """Check content against moderation rules."""
        for rule in self.moderation_rules.values():
            if not rule.enabled:
                continue

            if rule.rule_type == "keyword":
                if rule.pattern.lower() in content.lower():
                    if rule.action == "reject":
                        return ModerationStatus.REJECTED, f"Content violates rule: {rule.name}"
                    elif rule.action == "flag":
                        return ModerationStatus.FLAGGED, f"Content flagged by rule: {rule.name}"

            elif rule.rule_type == "length":
                max_length = int(rule.pattern)
                if len(content) > max_length and rule.action == "reject":
                    return ModerationStatus.REJECTED, f"Content exceeds maximum length: {rule.name}"

        return ModerationStatus.APPROVED, ""


# Global forum store instance
forum_store = ForumStore()
