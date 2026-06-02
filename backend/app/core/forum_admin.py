"""Forum administration tools and utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from backend.app.models.forum import (
    forum_store,
    PostStatus,
    ModerationStatus,
    ForumPost,
    ModerationRule,
)


@dataclass
class ForumStats:
    """Forum statistics."""
    total_posts: int = 0
    total_comments: int = 0
    total_users: int = 0
    posts_today: int = 0
    comments_today: int = 0
    avg_post_length: float = 0.0
    avg_comments_per_post: float = 0.0
    moderation_queue_size: int = 0
    flagged_content_count: int = 0


class ForumAdmin:
    """Forum administration utilities."""

    @staticmethod
    def get_forum_stats() -> ForumStats:
        """Get forum statistics."""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        total_posts = len(forum_store.posts)
        total_comments = len(forum_store.comments)
        total_users = len(forum_store.user_reputations)

        posts_today = sum(
            1 for p in forum_store.posts.values()
            if p.created_at >= today_start
        )

        comments_today = sum(
            1 for c in forum_store.comments.values()
            if c.created_at >= today_start
        )

        # Calculate averages
        avg_post_length = (
            sum(len(p.content) for p in forum_store.posts.values()) / total_posts
            if total_posts > 0 else 0
        )

        avg_comments_per_post = (
            total_comments / total_posts if total_posts > 0 else 0
        )

        # Count moderation queue
        moderation_queue_size = sum(
            1 for p in forum_store.posts.values()
            if p.moderation_status == ModerationStatus.PENDING
        )

        flagged_content_count = sum(
            1 for p in forum_store.posts.values()
            if p.moderation_status == ModerationStatus.FLAGGED
        )

        return ForumStats(
            total_posts=total_posts,
            total_comments=total_comments,
            total_users=total_users,
            posts_today=posts_today,
            comments_today=comments_today,
            avg_post_length=avg_post_length,
            avg_comments_per_post=avg_comments_per_post,
            moderation_queue_size=moderation_queue_size,
            flagged_content_count=flagged_content_count,
        )

    @staticmethod
    def get_moderation_queue(limit: int = 50) -> list[ForumPost]:
        """Get posts pending moderation."""
        pending = [
            p for p in forum_store.posts.values()
            if p.moderation_status in [ModerationStatus.PENDING, ModerationStatus.FLAGGED]
        ]
        pending.sort(key=lambda p: p.created_at)
        return pending[:limit]

    @staticmethod
    def approve_post(post_id: str, moderator_id: str) -> bool:
        """Approve a post."""
        post = forum_store.posts.get(post_id)
        if not post:
            return False

        post.moderation_status = ModerationStatus.APPROVED
        post.moderation_notes = f"Approved by {moderator_id}"
        return True

    @staticmethod
    def reject_post(post_id: str, reason: str, moderator_id: str) -> bool:
        """Reject a post."""
        post = forum_store.posts.get(post_id)
        if not post:
            return False

        post.moderation_status = ModerationStatus.REJECTED
        post.moderation_reason = reason
        post.moderation_notes = f"Rejected by {moderator_id}: {reason}"
        return True

    @staticmethod
    def flag_post(post_id: str, reason: str) -> bool:
        """Flag a post for review."""
        post = forum_store.posts.get(post_id)
        if not post:
            return False

        post.moderation_status = ModerationStatus.FLAGGED
        post.moderation_reason = reason
        return True

    @staticmethod
    def pin_post(post_id: str) -> bool:
        """Pin a post to the top."""
        post = forum_store.posts.get(post_id)
        if not post:
            return False

        post.is_pinned = True
        return True

    @staticmethod
    def unpin_post(post_id: str) -> bool:
        """Unpin a post."""
        post = forum_store.posts.get(post_id)
        if not post:
            return False

        post.is_pinned = False
        return True

    @staticmethod
    def lock_post(post_id: str) -> bool:
        """Lock a post (prevent new comments)."""
        post = forum_store.posts.get(post_id)
        if not post:
            return False

        post.is_locked = True
        return True

    @staticmethod
    def unlock_post(post_id: str) -> bool:
        """Unlock a post."""
        post = forum_store.posts.get(post_id)
        if not post:
            return False

        post.is_locked = False
        return True

    @staticmethod
    def get_user_activity(user_id: str, days: int = 30) -> dict:
        """Get user activity statistics."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        user_posts = [
            p for p in forum_store.posts.values()
            if p.author_id == user_id and p.created_at >= cutoff_date
        ]

        user_comments = [
            c for c in forum_store.comments.values()
            if c.author_id == user_id and c.created_at >= cutoff_date
        ]

        user_likes = [
            l for l in forum_store.likes.values()
            if l.user_id == user_id
        ]

        return {
            "user_id": user_id,
            "posts_count": len(user_posts),
            "comments_count": len(user_comments),
            "likes_count": len(user_likes),
            "total_engagement": len(user_posts) + len(user_comments) + len(user_likes),
            "last_activity": max(
                [p.created_at for p in user_posts] +
                [c.created_at for c in user_comments] +
                [datetime.utcnow()]
            ),
        }

    @staticmethod
    def get_top_contributors(limit: int = 10) -> list[dict]:
        """Get top contributors by reputation."""
        contributors = sorted(
            forum_store.user_reputations.values(),
            key=lambda r: r.reputation_points,
            reverse=True,
        )

        return [
            {
                "user_id": c.user_id,
                "username": c.username,
                "reputation_points": c.reputation_points,
                "level": c.level,
                "post_count": c.post_count,
                "comment_count": c.comment_count,
            }
            for c in contributors[:limit]
        ]

    @staticmethod
    def get_trending_topics(days: int = 7, limit: int = 10) -> list[dict]:
        """Get trending topics."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        recent_posts = [
            p for p in forum_store.posts.values()
            if p.created_at >= cutoff_date
        ]

        # Count tag occurrences
        tag_counts = {}
        for post in recent_posts:
            for tag in post.tags:
                tag_lower = tag.lower()
                tag_counts[tag_lower] = tag_counts.get(tag_lower, 0) + 1

        # Sort by count
        trending = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)

        return [
            {"tag": tag, "count": count, "posts": [
                p.id for p in recent_posts if tag in [t.lower() for t in p.tags]
            ][:5]}
            for tag, count in trending[:limit]
        ]

    @staticmethod
    def get_moderation_report(days: int = 30) -> dict:
        """Get moderation report."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        posts_in_period = [
            p for p in forum_store.posts.values()
            if p.created_at >= cutoff_date
        ]

        approved = sum(
            1 for p in posts_in_period
            if p.moderation_status == ModerationStatus.APPROVED
        )

        rejected = sum(
            1 for p in posts_in_period
            if p.moderation_status == ModerationStatus.REJECTED
        )

        flagged = sum(
            1 for p in posts_in_period
            if p.moderation_status == ModerationStatus.FLAGGED
        )

        pending = sum(
            1 for p in posts_in_period
            if p.moderation_status == ModerationStatus.PENDING
        )

        approval_rate = (
            approved / len(posts_in_period) * 100
            if posts_in_period else 0
        )

        return {
            "period_days": days,
            "total_posts": len(posts_in_period),
            "approved": approved,
            "rejected": rejected,
            "flagged": flagged,
            "pending": pending,
            "approval_rate": approval_rate,
            "rejection_rate": (rejected / len(posts_in_period) * 100) if posts_in_period else 0,
        }

    @staticmethod
    def export_forum_data(format: str = "json") -> str:
        """Export forum data."""
        import json

        data = {
            "posts": [p.model_dump() for p in forum_store.posts.values()],
            "comments": [c.model_dump() for c in forum_store.comments.values()],
            "users": [r.model_dump() for r in forum_store.user_reputations.values()],
            "stats": ForumAdmin.get_forum_stats().__dict__,
        }

        if format == "json":
            return json.dumps(data, indent=2, default=str)
        else:
            raise ValueError(f"Unsupported format: {format}")

    @staticmethod
    def cleanup_old_content(days: int = 365) -> int:
        """Clean up old deleted content."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        deleted_count = 0

        # Remove old deleted posts
        posts_to_remove = [
            post_id for post_id, post in forum_store.posts.items()
            if post.status == PostStatus.DELETED and post.updated_at < cutoff_date
        ]

        for post_id in posts_to_remove:
            del forum_store.posts[post_id]
            deleted_count += 1

        # Remove old deleted comments
        comments_to_remove = [
            comment_id for comment_id, comment in forum_store.comments.items()
            if comment.is_deleted and comment.updated_at < cutoff_date
        ]

        for comment_id in comments_to_remove:
            del forum_store.comments[comment_id]
            deleted_count += 1

        return deleted_count


# Example usage
if __name__ == "__main__":
    # Get forum statistics
    stats = ForumAdmin.get_forum_stats()
    print(f"Total posts: {stats.total_posts}")
    print(f"Total comments: {stats.total_comments}")
    print(f"Moderation queue: {stats.moderation_queue_size}")

    # Get moderation queue
    queue = ForumAdmin.get_moderation_queue()
    print(f"Posts pending review: {len(queue)}")

    # Get top contributors
    contributors = ForumAdmin.get_top_contributors()
    for contributor in contributors:
        print(f"{contributor['username']}: {contributor['reputation_points']} points")

    # Get trending topics
    trending = ForumAdmin.get_trending_topics()
    for topic in trending:
        print(f"{topic['tag']}: {topic['count']} posts")

    # Get moderation report
    report = ForumAdmin.get_moderation_report()
    print(f"Approval rate: {report['approval_rate']:.1f}%")
