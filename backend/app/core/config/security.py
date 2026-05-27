"""Security configuration module."""

from typing import Optional

from pydantic import Field, field_validator

from .base import BaseConfig, Environment


class SecurityConfig(BaseConfig):
    """Security configuration with encryption and authentication settings."""

    # JWT configuration
    jwt_secret: str = Field(
        default="change-this-to-a-random-64-char-string",
        min_length=32,
        description="JWT signing secret (minimum 32 characters)",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm",
    )
    jwt_access_token_expire_minutes: int = Field(
        default=15,
        ge=1,
        le=1440,
        description="JWT access token expiration in minutes",
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7,
        ge=1,
        le=365,
        description="JWT refresh token expiration in days",
    )

    # Encryption configuration
    encryption_key: str = Field(
        default="change-this-to-32-char-hex-string",
        min_length=32,
        description="Encryption key for sensitive data (minimum 32 characters)",
    )
    encryption_algorithm: str = Field(
        default="AES-256-GCM",
        description="Encryption algorithm",
    )

    # Password hashing
    bcrypt_cost: int = Field(
        default=12,
        ge=4,
        le=31,
        description="Bcrypt cost factor (higher = slower but more secure)",
    )

    # API key configuration
    require_api_key: bool = Field(
        default=False,
        description="Require API key for all requests",
    )
    bootstrap_api_key: Optional[str] = Field(
        default=None,
        description="Bootstrap API key for initial setup",
    )
    bootstrap_api_key_sha256: Optional[str] = Field(
        default=None,
        description="SHA256 hash of bootstrap API key",
    )
    api_key_expiration_days: int = Field(
        default=90,
        ge=1,
        le=3650,
        description="API key expiration in days",
    )

    # CORS configuration
    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        description="Comma-separated list of allowed CORS origins",
    )
    cors_allow_credentials: bool = Field(
        default=True,
        description="Allow credentials in CORS requests",
    )
    cors_allow_methods: str = Field(
        default="GET,POST,PUT,DELETE,PATCH,OPTIONS",
        description="Allowed HTTP methods for CORS",
    )
    cors_allow_headers: str = Field(
        default="*",
        description="Allowed headers for CORS",
    )

    # Rate limiting
    rate_limit_default: int = Field(
        default=100,
        ge=1,
        description="Default rate limit (requests per window)",
    )
    rate_limit_auth: int = Field(
        default=20,
        ge=1,
        description="Rate limit for authentication endpoints",
    )
    rate_limit_agent_run: int = Field(
        default=10,
        ge=1,
        description="Rate limit for agent run endpoints",
    )
    rate_limit_admin: int = Field(
        default=500,
        ge=1,
        description="Rate limit for admin endpoints",
    )
    rate_limit_window_seconds: int = Field(
        default=60,
        ge=1,
        le=3600,
        description="Rate limit window in seconds",
    )

    # Account lockout
    max_login_attempts: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum login attempts before lockout",
    )
    lockout_duration_minutes: int = Field(
        default=15,
        ge=1,
        le=1440,
        description="Account lockout duration in minutes",
    )

    # HTTPS/TLS
    require_https: bool = Field(
        default=False,
        description="Require HTTPS for all requests",
    )
    ssl_cert_path: Optional[str] = Field(
        default=None,
        description="Path to SSL certificate file",
    )
    ssl_key_path: Optional[str] = Field(
        default=None,
        description="Path to SSL key file",
    )

    @field_validator("jwt_secret", "encryption_key")
    @classmethod
    def validate_production_secrets(cls, v: str, info) -> str:
        """Enforce strong secrets in production mode."""
        environment = info.data.get("environment", Environment.DEVELOPMENT)
        if environment == Environment.PRODUCTION:
            default_jwt = "change-this-to-a-random-64-char-string"
            default_encryption = "change-this-to-32-char-hex-string"
            if v == default_jwt or v == default_encryption:
                raise ValueError(
                    f"Production secrets must be changed from defaults. "
                    f"Set JWT_SECRET and ENCRYPTION_KEY to strong random values. "
                    f"Generate using: python scripts/generate_secrets.py"
                )
            if len(v) < 32:
                raise ValueError(f"Production secrets must be at least 32 characters long")
        return v

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, v: str) -> str:
        """Validate and normalize CORS origins."""
        origins = [origin.strip() for origin in v.split(",") if origin.strip()]
        if not origins:
            raise ValueError("cors_origins must contain at least one origin")
        return ",".join(origins)

    @field_validator("require_https")
    @classmethod
    def validate_https_requirement(cls, v: bool, info) -> bool:
        """Enforce HTTPS in production."""
        environment = info.data.get("environment", Environment.DEVELOPMENT)
        if environment == Environment.PRODUCTION and not v:
            raise ValueError("HTTPS is required in production mode")
        return v

    def get_cors_origins_list(self) -> list[str]:
        """Get CORS origins as a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def is_secure_mode(self) -> bool:
        """Check if running in secure mode (production)."""
        return self.environment == Environment.PRODUCTION
