"""Tests for forum functionality."""

import pytest
from datetime import datetime
from backend.app.models.forum import (
    ForumPost,
    ForumComment,
    UserReputation,
    PostStatus,
    ModerationStatus,
    forum_store,
)
from backend.app.services.forum_search import search_index


@pytest.fixture(autouse=True)
def reset_forum_state():
    """每个测试前重置模块级单例状态。

    forum_store 与 search_index 都是模块级单例(forum.py / forum_search.py),
    会在测试间累积 posts/likes/bookmarks/reputation 等状态,导致计数类断言
    互相污染(例如 test_get_user_bookmarks 期望 2 却拿到 3、
    test_reputation_points_increase 期望 10 却拿到累计值)。
    这里在每个测试前清空它们的内部容器,保证测试隔离。
    """
    forum_store.posts.clear()
    forum_store.comments.clear()
    forum_store.user_reputations.clear()
    forum_store.likes.clear()
    forum_store.bookmarks.clear()
    forum_store.follows.clear()
    forum_store.notifications.clear()
    forum_store.moderation_rules.clear()

    search_index.word_index.clear()
    search_index.tag_index.clear()
    search_index.author_index.clear()
    search_index.category_index.clear()

    yield


class TestForumPost:
    """Test forum post operations."""

    def test_create_post(self):
        """Test creating a post."""
        post = ForumPost(
            title="Test Post",
            content="This is a test post content",
            author_id="user1",
            author_name="User One",
            category="general",
            tags=["test", "demo"],
        )

        created = forum_store.create_post(post)
        assert created.id == post.id
        assert created.title == "Test Post"
        assert created.author_id == "user1"
        assert created.view_count == 0

    def test_get_post_increments_view_count(self):
        """Test that getting a post increments view count."""
        post = ForumPost(
            title="View Test",
            content="Test content",
            author_id="user1",
            author_name="User One",
        )
        forum_store.create_post(post)

        retrieved = forum_store.get_post(post.id)
        assert retrieved.view_count == 1

        retrieved = forum_store.get_post(post.id)
        assert retrieved.view_count == 2

    def test_update_post(self):
        """Test updating a post."""
        post = ForumPost(
            title="Original Title",
            content="Original content",
            author_id="user1",
            author_name="User One",
        )
        forum_store.create_post(post)

        post.title = "Updated Title"
        updated = forum_store.update_post(post.id, post)
        assert updated.title == "Updated Title"

    def test_delete_post(self):
        """Test deleting a post."""
        post = ForumPost(
            title="To Delete",
            content="This will be deleted",
            author_id="user1",
            author_name="User One",
        )
        forum_store.create_post(post)

        success = forum_store.delete_post(post.id)
        assert success
        assert forum_store.posts[post.id].status == PostStatus.DELETED

    def test_list_posts_with_filtering(self):
        """Test listing posts with filters."""
        # Create posts in different categories
        post1 = ForumPost(
            title="General Post",
            content="Content",
            author_id="user1",
            author_name="User One",
            category="general",
            tags=["tag1"],
        )
        post2 = ForumPost(
            title="Bug Report",
            content="Content",
            author_id="user2",
            author_name="User Two",
            category="bugs",
            tags=["tag1", "tag2"],
        )

        forum_store.create_post(post1)
        forum_store.create_post(post2)

        # Filter by category
        posts, total = forum_store.list_posts(category="general")
        assert len(posts) >= 1
        assert any(p.id == post1.id for p in posts)

        # Filter by tag
        posts, total = forum_store.list_posts(tag="tag2")
        assert any(p.id == post2.id for p in posts)


class TestForumComment:
    """Test forum comment operations."""

    def test_create_comment(self):
        """Test creating a comment."""
        post = ForumPost(
            title="Post for Comments",
            content="Content",
            author_id="user1",
            author_name="User One",
        )
        forum_store.create_post(post)

        comment = ForumComment(
            post_id=post.id,
            content="Great post!",
            author_id="user2",
            author_name="User Two",
        )

        created = forum_store.create_comment(comment)
        assert created.post_id == post.id
        assert created.content == "Great post!"

        # Check post comment count increased
        updated_post = forum_store.get_post(post.id)
        assert updated_post.comment_count == 1

    def test_get_post_comments(self):
        """Test getting comments for a post."""
        post = ForumPost(
            title="Post",
            content="Content",
            author_id="user1",
            author_name="User One",
        )
        forum_store.create_post(post)

        comment1 = ForumComment(
            post_id=post.id,
            content="Comment 1",
            author_id="user2",
            author_name="User Two",
        )
        comment2 = ForumComment(
            post_id=post.id,
            content="Comment 2",
            author_id="user3",
            author_name="User Three",
        )

        forum_store.create_comment(comment1)
        forum_store.create_comment(comment2)

        comments, total = forum_store.get_post_comments(post.id)
        assert total == 2
        assert len(comments) == 2

    def test_delete_comment(self):
        """Test deleting a comment."""
        post = ForumPost(
            title="Post",
            content="Content",
            author_id="user1",
            author_name="User One",
        )
        forum_store.create_post(post)

        comment = ForumComment(
            post_id=post.id,
            content="Comment",
            author_id="user2",
            author_name="User Two",
        )
        forum_store.create_comment(comment)

        success = forum_store.delete_comment(comment.id)
        assert success
        assert forum_store.comments[comment.id].is_deleted


class TestLikeSystem:
    """Test like/vote system."""

    def test_like_post(self):
        """Test liking a post."""
        post = ForumPost(
            title="Post",
            content="Content",
            author_id="user1",
            author_name="User One",
        )
        forum_store.create_post(post)

        success = forum_store.like_post("user2", post.id)
        assert success
        assert post.like_count == 1

        # Try to like again
        success = forum_store.like_post("user2", post.id)
        assert not success

    def test_unlike_post(self):
        """Test unliking a post."""
        post = ForumPost(
            title="Post",
            content="Content",
            author_id="user1",
            author_name="User One",
        )
        forum_store.create_post(post)

        forum_store.like_post("user2", post.id)
        assert post.like_count == 1

        success = forum_store.unlike_post("user2", post.id)
        assert success
        assert post.like_count == 0


class TestBookmarkSystem:
    """Test bookmark system."""

    def test_bookmark_post(self):
        """Test bookmarking a post."""
        post = ForumPost(
            title="Post",
            content="Content",
            author_id="user1",
            author_name="User One",
        )
        forum_store.create_post(post)

        success = forum_store.bookmark_post("user2", post.id)
        assert success

    def test_get_user_bookmarks(self):
        """Test getting user's bookmarks."""
        post1 = ForumPost(
            title="Post 1",
            content="Content",
            author_id="user1",
            author_name="User One",
        )
        post2 = ForumPost(
            title="Post 2",
            content="Content",
            author_id="user1",
            author_name="User One",
        )

        forum_store.create_post(post1)
        forum_store.create_post(post2)

        forum_store.bookmark_post("user2", post1.id)
        forum_store.bookmark_post("user2", post2.id)

        bookmarks, total = forum_store.get_user_bookmarks("user2")
        assert total == 2


class TestFollowSystem:
    """Test user follow system."""

    def test_follow_user(self):
        """Test following a user."""
        success = forum_store.follow_user("user1", "user2")
        assert success

        # Try to follow again
        success = forum_store.follow_user("user1", "user2")
        assert not success

    def test_cannot_follow_self(self):
        """Test that user cannot follow themselves."""
        success = forum_store.follow_user("user1", "user1")
        assert not success

    def test_get_followers(self):
        """Test getting user's followers."""
        forum_store.follow_user("user1", "user2")
        forum_store.follow_user("user3", "user2")

        followers = forum_store.get_user_followers("user2")
        assert len(followers) == 2
        assert "user1" in followers
        assert "user3" in followers


class TestReputationSystem:
    """Test user reputation system."""

    def test_reputation_points_increase(self):
        """Test that reputation points increase with actions."""
        post = ForumPost(
            title="Post",
            content="Content",
            author_id="user1",
            author_name="User One",
        )
        forum_store.create_post(post)

        rep = forum_store.get_user_reputation("user1")
        assert rep.reputation_points == 10  # +10 for posting

    def test_reputation_level_progression(self):
        """Test reputation level progression."""
        # Simulate earning points
        for _ in range(10):
            post = ForumPost(
                title="Post",
                content="Content",
                author_id="user1",
                author_name="User One",
            )
            forum_store.create_post(post)

        rep = forum_store.get_user_reputation("user1")
        assert rep.reputation_points >= 100
        assert rep.level in ["member", "contributor", "expert", "moderator"]


class TestSearchIndex:
    """Test search functionality."""

    def test_index_post(self):
        """Test indexing a post."""
        search_index.index_post(
            "post1",
            "Python Programming",
            "Learn Python basics",
            ["python", "programming"],
            "user1",
            "general",
        )

        results = search_index.search("python")
        assert len(results) > 0
        assert ("post1", None) in results

    def test_search_by_tag(self):
        """Test searching by tag."""
        search_index.index_post(
            "post1",
            "Title",
            "Content",
            ["python"],
            "user1",
            "general",
        )

        results = search_index.search_by_tag("python")
        assert "post1" in results

    def test_search_by_author(self):
        """Test searching by author."""
        search_index.index_post(
            "post1",
            "Title",
            "Content",
            [],
            "user1",
            "general",
        )

        results = search_index.search_by_author("user1")
        assert "post1" in results

    def test_search_by_category(self):
        """Test searching by category."""
        search_index.index_post(
            "post1",
            "Title",
            "Content",
            [],
            "user1",
            "bugs",
        )

        results = search_index.search_by_category("bugs")
        assert "post1" in results


class TestModerationSystem:
    """Test content moderation."""

    def test_check_content_moderation(self):
        """Test content moderation check."""
        from backend.app.models.forum import ModerationRule

        rule = ModerationRule(
            name="Spam Filter",
            rule_type="keyword",
            pattern="spam",
            action="reject",
        )
        forum_store.add_moderation_rule(rule)

        status, reason = forum_store.check_content_moderation("This is spam content")
        assert status == ModerationStatus.REJECTED

        status, reason = forum_store.check_content_moderation("This is clean content")
        assert status == ModerationStatus.APPROVED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
