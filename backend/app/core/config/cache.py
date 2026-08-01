"""Cache configuration module."""


from pydantic import Field, field_validator

from .base import BaseConfig


class CacheConfig(BaseConfig):
    """Cache configuration with support for multiple backends."""

    # Redis configuration
    redis_url: str | None = Field(
        default=None,
        description="Redis connection URL (redis://host:port/db)",
    )
    redis_password: str | None = Field(
        default=None,
        description="Redis password (if not in URL)",
    )
    redis_db: int = Field(
        default=0,
        ge=0,
        le=15,
        description="Redis database number",
    )
    redis_socket_timeout: int = Field(
        default=5,
        ge=1,
        description="Redis socket timeout in seconds",
    )
    redis_socket_connect_timeout: int = Field(
        default=5,
        ge=1,
        description="Redis connection timeout in seconds",
    )
    redis_max_connections: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Maximum Redis connections in pool",
    )

    # Cache settings
    cache_ttl_default: int = Field(
        default=3600,
        ge=60,
        description="Default cache TTL in seconds",
    )
    cache_ttl_short: int = Field(
        default=300,
        ge=60,
        description="Short cache TTL in seconds",
    )
    cache_ttl_long: int = Field(
        default=86400,
        ge=3600,
        description="Long cache TTL in seconds",
    )

    # Session cache
    session_cache_ttl: int = Field(
        default=86400,
        ge=3600,
        description="Session cache TTL in seconds (24 hours)",
    )

    # Memory cache (fallback)
    memory_cache_max_size: int = Field(
        default=1000,
        ge=100,
        le=100000,
        description="Maximum items in memory cache",
    )

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, v: str | None) -> str | None:
        """Validate Redis URL format."""
        if v is None or v.strip() == "":
            return None
        if not v.startswith("redis://"):
            raise ValueError("redis_url must start with 'redis://'")
        return v

    def has_redis(self) -> bool:
        """Check if Redis is configured."""
        return self.redis_url is not None

    def get_redis_url(self) -> str | None:
        """Get the Redis URL with password if provided."""
        if not self.redis_url:
            return None

        # If password is provided separately, inject it into the URL
        if self.redis_password and "@" not in self.redis_url:
            # Format: redis://password@host:port/db
            url_parts = self.redis_url.replace("redis://", "").split("/")
            host_port = url_parts[0]
            db = url_parts[1] if len(url_parts) > 1 else self.redis_db
            return f"redis://:{self.redis_password}@{host_port}/{db}"

        return self.redis_url
