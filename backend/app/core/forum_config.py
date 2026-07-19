"""Forum configuration and settings."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ForumConfig:
    """Forum configuration settings."""

    # Basic settings
    FORUM_ENABLED: bool = True
    FORUM_NAME: str = "X-Agent Community Forum"
    FORUM_DESCRIPTION: str = "A community forum for X-Agent users and developers"

    # Post settings
    MIN_POST_TITLE_LENGTH: int = 5
    MAX_POST_TITLE_LENGTH: int = 200
    MIN_POST_CONTENT_LENGTH: int = 20
    MAX_POST_CONTENT_LENGTH: int = 50000
    MAX_TAGS_PER_POST: int = 5
    MIN_TAG_LENGTH: int = 2
    MAX_TAG_LENGTH: int = 30

    # Comment settings
    MIN_COMMENT_LENGTH: int = 3
    MAX_COMMENT_LENGTH: int = 10000
    MAX_NESTED_REPLIES: int = 3

    # Moderation settings
    MODERATION_ENABLED: bool = True
    AUTO_MODERATION_ENABLED: bool = True
    REQUIRE_APPROVAL_FOR_NEW_USERS: bool = False
    NEW_USER_THRESHOLD_POSTS: int = 5
    SPAM_DETECTION_ENABLED: bool = True
    PROFANITY_FILTER_ENABLED: bool = True

    # Rate limiting
    RATE_LIMIT_POSTS_PER_HOUR: int = 10
    RATE_LIMIT_COMMENTS_PER_HOUR: int = 50
    RATE_LIMIT_LIKES_PER_HOUR: int = 100

    # Reputation settings
    REPUTATION_ENABLED: bool = True
    POINTS_FOR_POST: int = 10
    POINTS_FOR_COMMENT: int = 5
    POINTS_FOR_LIKE_RECEIVED: int = 2
    POINTS_FOR_COMMENT_LIKE_RECEIVED: int = 1
    POINTS_FOR_ACCEPTED_ANSWER: int = 25
    POINTS_FOR_HELPFUL_VOTE: int = 10

    # Badge settings
    BADGES_ENABLED: bool = True
    BADGE_FIRST_POST_THRESHOLD: int = 1
    BADGE_FIRST_ANSWER_THRESHOLD: int = 1
    BADGE_HELPFUL_HELPER_THRESHOLD: int = 10
    BADGE_KNOWLEDGE_SEEKER_THRESHOLD: int = 100
    BADGE_COMMUNITY_BUILDER_THRESHOLD: int = 50

    # Search settings
    SEARCH_ENABLED: bool = True
    SEARCH_INDEX_ENABLED: bool = True
    SEARCH_RESULT_LIMIT: int = 100
    SEARCH_MIN_QUERY_LENGTH: int = 2

    # Notification settings
    NOTIFICATIONS_ENABLED: bool = True
    NOTIFY_ON_COMMENT_REPLY: bool = True
    NOTIFY_ON_POST_LIKE: bool = True
    NOTIFY_ON_COMMENT_LIKE: bool = False
    NOTIFY_ON_USER_FOLLOW: bool = True
    NOTIFICATION_RETENTION_DAYS: int = 30

    # Category settings
    CATEGORIES: list[str] = None
    DEFAULT_CATEGORY: str = "general"

    # Pagination settings
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    MIN_PAGE_SIZE: int = 1

    # Archive settings
    ARCHIVE_ENABLED: bool = True
    ARCHIVE_AFTER_DAYS: int = 365
    ARCHIVE_RETENTION_DAYS: int = 1825  # 5 years

    # Feature flags
    ALLOW_ANONYMOUS_POSTS: bool = False
    ALLOW_EDIT_AFTER_MINUTES: int = 60
    ALLOW_DELETE_AFTER_MINUTES: int = 120
    ALLOW_NESTED_COMMENTS: bool = True
    ALLOW_MARKDOWN: bool = True
    ALLOW_CODE_BLOCKS: bool = True
    ALLOW_IMAGES: bool = True
    ALLOW_LINKS: bool = True

    # Moderation rules
    BANNED_KEYWORDS: list[str] = None
    SPAM_PATTERNS: list[str] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.CATEGORIES is None:
            self.CATEGORIES = [
                "general",
                "bugs",
                "features",
                "showcase",
                "announcements",
                "off-topic",
            ]

        if self.BANNED_KEYWORDS is None:
            self.BANNED_KEYWORDS = [
                "viagra",
                "casino",
                "lottery",
                "cryptocurrency",
            ]

        if self.SPAM_PATTERNS is None:
            self.SPAM_PATTERNS = [
                r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",  # URLs
                r"(?:^|\s)@\w+(?:\s|$)",  # Mentions
            ]


# Global configuration instance
forum_config = ForumConfig()


# Configuration presets
class ForumConfigPresets:
    """Pre-configured forum settings."""

    @staticmethod
    def strict_moderation() -> ForumConfig:
        """Strict moderation preset."""
        config = ForumConfig()
        config.MODERATION_ENABLED = True
        config.AUTO_MODERATION_ENABLED = True
        config.REQUIRE_APPROVAL_FOR_NEW_USERS = True
        config.SPAM_DETECTION_ENABLED = True
        config.PROFANITY_FILTER_ENABLED = True
        config.RATE_LIMIT_POSTS_PER_HOUR = 5
        config.RATE_LIMIT_COMMENTS_PER_HOUR = 20
        return config

    @staticmethod
    def permissive() -> ForumConfig:
        """Permissive preset."""
        config = ForumConfig()
        config.MODERATION_ENABLED = False
        config.AUTO_MODERATION_ENABLED = False
        config.REQUIRE_APPROVAL_FOR_NEW_USERS = False
        config.SPAM_DETECTION_ENABLED = False
        config.PROFANITY_FILTER_ENABLED = False
        config.RATE_LIMIT_POSTS_PER_HOUR = 100
        config.RATE_LIMIT_COMMENTS_PER_HOUR = 500
        return config

    @staticmethod
    def balanced() -> ForumConfig:
        """Balanced preset (default)."""
        return ForumConfig()

    @staticmethod
    def enterprise() -> ForumConfig:
        """Enterprise preset."""
        config = ForumConfig()
        config.MODERATION_ENABLED = True
        config.AUTO_MODERATION_ENABLED = True
        config.REQUIRE_APPROVAL_FOR_NEW_USERS = False
        config.SPAM_DETECTION_ENABLED = True
        config.PROFANITY_FILTER_ENABLED = True
        config.RATE_LIMIT_POSTS_PER_HOUR = 50
        config.RATE_LIMIT_COMMENTS_PER_HOUR = 200
        config.ARCHIVE_ENABLED = True
        config.NOTIFICATIONS_ENABLED = True
        config.SEARCH_ENABLED = True
        return config


# Example usage
if __name__ == "__main__":
    # Use default configuration
    print(f"Forum: {forum_config.FORUM_NAME}")
    print(f"Min post length: {forum_config.MIN_POST_CONTENT_LENGTH}")
    print(f"Categories: {forum_config.CATEGORIES}")

    # Use preset
    strict_config = ForumConfigPresets.strict_moderation()
    print(f"Strict moderation - Posts per hour: {strict_config.RATE_LIMIT_POSTS_PER_HOUR}")
