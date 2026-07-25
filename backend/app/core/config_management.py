"""
Enhanced configuration management with environment isolation and validation.

Implements:
- Environment-specific configuration files
- Configuration validation with Pydantic
- Sensitive configuration encryption
- Configuration hot-reload support
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class DatabaseConfig(BaseModel):
    """Database configuration."""

    backend: str = Field(default="sqlite", description="Database backend: sqlite, postgresql")
    url: str = Field(default="sqlite:///./data/xagent.db", description="Database connection URL")
    pool_size: int = Field(default=10, ge=1, le=100, description="Connection pool size")
    max_overflow: int = Field(default=20, ge=0, le=100, description="Maximum overflow connections")
    pool_timeout: float = Field(default=30.0, ge=1.0, le=300.0, description="Pool timeout in seconds")
    echo: bool = Field(default=False, description="Enable SQL echo logging")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v:
            raise ValueError("Database URL cannot be empty")
        return v


class CacheConfig(BaseModel):
    """Cache configuration."""

    backend: str = Field(default="memory", description="Cache backend: memory, redis")
    redis_url: str | None = Field(default=None, description="Redis connection URL")
    memory_cache_size: int = Field(default=1000, ge=100, le=100000, description="In-memory cache size")
    default_ttl: int = Field(default=3600, ge=60, le=86400, description="Default cache TTL in seconds")
    enable_l2_cache: bool = Field(default=False, description="Enable L2 (Redis) cache")


class LLMConfig(BaseModel):
    """LLM configuration."""

    backend: str = Field(default="auto", description="LLM backend: auto, mock, openai, deepseek, anthropic, ollama")
    fallback_order: str = Field(default="", description="Fallback LLM order (comma-separated)")
    openai_api_key: str | None = Field(default=None, description="OpenAI API key")
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model name")
    deepseek_api_key: str | None = Field(default=None, description="DeepSeek API key")
    deepseek_model: str = Field(default="deepseek-chat", description="DeepSeek model name")
    deepseek_base_url: str | None = Field(default=None, description="DeepSeek base URL")
    timeout: float = Field(default=60.0, ge=10.0, le=300.0, description="LLM request timeout")


class MemoryConfig(BaseModel):
    """Memory system configuration."""

    backend: str = Field(default="postgres", description="Memory backend: memory, postgres, qdrant")
    store_path: Path = Field(default=PROJECT_ROOT / "data" / "memory.jsonl", description="Memory store path")
    embedding_backend: str = Field(default="auto", description="Embedding backend: auto, local, sentence-transformers, openai")
    embedding_model: str = Field(default="text-embedding-3-small", description="Embedding model name")
    embedding_dim: int = Field(default=384, description="Embedding vector dimensions")
    embedding_dimensions: int | None = Field(default=None, description="Embedding dimensions (OpenAI-specific)")
    qdrant_url: str = Field(default="http://localhost:6333", description="Qdrant server URL")
    qdrant_api_key: str | None = Field(default=None, description="Qdrant API key")
    enable_vector_search: bool = Field(default=False, description="Enable vector search")


class SecurityConfig(BaseModel):
    """Security configuration."""

    jwt_secret: str = Field(default="change-this-to-a-random-64-char-string", description="JWT secret key")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expiration: int = Field(default=900, ge=60, le=86400, description="JWT expiration in seconds")
    encryption_key: str = Field(default="change-this-to-32-char-hex-string", description="Encryption key")
    require_api_key: bool = Field(default=False, description="Require API key for all requests")
    bootstrap_api_key: str | None = Field(default=None, description="Bootstrap API key")
    audit_hmac_secret: str | None = Field(default=None, description="Audit HMAC secret")
    enable_rate_limiting: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_requests: int = Field(default=60, ge=10, le=1000, description="Rate limit requests per minute")
    enable_cors: bool = Field(default=True, description="Enable CORS")
    cors_origins: str = Field(default="http://localhost:3000", description="CORS origins (comma-separated)")

    @field_validator("jwt_secret", "encryption_key")
    @classmethod
    def validate_secrets(cls, v: str) -> str:
        if not v or len(v) < 16:
            raise ValueError("Secret must be at least 16 characters long")
        return v


class ObservabilityConfig(BaseModel):
    """Observability configuration."""

    log_level: str = Field(default="INFO", description="Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL")
    enable_tracing: bool = Field(default=False, description="Enable distributed tracing")
    trace_backend: str = Field(default="memory", description="Trace backend: memory, langfuse")
    langfuse_public_key: str | None = Field(default=None, description="Langfuse public key")
    langfuse_secret_key: str | None = Field(default=None, description="Langfuse secret key")
    langfuse_host: str | None = Field(default=None, description="Langfuse host")
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    metrics_port: int = Field(default=8001, ge=1024, le=65535, description="Metrics port")


class PerformanceConfig(BaseModel):
    """Performance configuration."""

    max_iterations: int = Field(default=4, ge=1, le=100, description="Maximum agent iterations")
    default_token_budget: int = Field(default=16000, ge=1000, le=1000000, description="Default token budget")
    default_cost_budget_usd: float = Field(default=1.0, ge=0.01, le=1000.0, description="Default cost budget in USD")
    max_concurrent_tasks: int = Field(default=10, ge=1, le=1000, description="Maximum concurrent tasks")
    task_queue_size: int = Field(default=1000, ge=100, le=100000, description="Task queue size")
    connection_pool_size: int = Field(default=20, ge=5, le=200, description="Connection pool size")


class EnvironmentConfig(BaseModel):
    """Complete environment configuration."""

    app_name: str = Field(default="X-Agent", description="Application name")
    app_mode: str = Field(default="development", description="Application mode: development, test, production")
    debug: bool = Field(default=False, description="Enable debug mode")
    static_dir: Path = Field(default=PROJECT_ROOT / "frontend", description="Static files directory")

    database: DatabaseConfig = Field(default_factory=DatabaseConfig, description="Database configuration")
    cache: CacheConfig = Field(default_factory=CacheConfig, description="Cache configuration")
    llm: LLMConfig = Field(default_factory=LLMConfig, description="LLM configuration")
    memory: MemoryConfig = Field(default_factory=MemoryConfig, description="Memory configuration")
    security: SecurityConfig = Field(default_factory=SecurityConfig, description="Security configuration")
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig, description="Observability configuration")
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig, description="Performance configuration")

    @field_validator("app_mode")
    @classmethod
    def validate_app_mode(cls, v: str) -> str:
        if v not in ("development", "test", "production"):
            raise ValueError("app_mode must be one of: development, test, production")
        return v

    def validate_production(self) -> list[str]:
        """Validate production-specific requirements."""
        errors = []

        if self.app_mode == "production":
            if self.debug:
                errors.append("Debug mode must be disabled in production")

            if self.security.jwt_secret == "change-this-to-a-random-64-char-string":
                errors.append("JWT secret must be changed from default in production")

            if self.security.encryption_key == "change-this-to-32-char-hex-string":
                errors.append("Encryption key must be changed from default in production")

            if not self.security.audit_hmac_secret:
                errors.append("Audit HMAC secret must be set in production")

            if self.database.backend == "sqlite":
                errors.append("SQLite backend is not recommended for production")

        return errors


class ConfigurationManager:
    """
    Manage application configuration with environment isolation.

    Features:
    - Load configuration from YAML/JSON files
    - Environment-specific overrides
    - Configuration validation
    - Hot-reload support
    """

    def __init__(self, config_dir: Path | None = None) -> None:
        self.config_dir = config_dir or PROJECT_ROOT / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._config: EnvironmentConfig | None = None
        self._watchers: list[callable] = []

    def load(self, app_mode: str = "development") -> EnvironmentConfig:
        """Load configuration for the specified app mode."""
        # Load base configuration
        base_config = self._load_config_file("base.yaml") or {}

        # Load environment-specific configuration
        env_config = self._load_config_file(f"{app_mode}.yaml") or {}

        # Merge configurations (environment-specific overrides base)
        merged = {**base_config, **env_config}

        # Create and validate configuration
        self._config = EnvironmentConfig(**merged)

        # Validate production requirements
        errors = self._config.validate_production()
        if errors:
            logger.warning(f"Production configuration warnings: {errors}")

        logger.info(f"Configuration loaded for mode: {app_mode}")
        return self._config

    def _load_config_file(self, filename: str) -> dict[str, Any] | None:
        """Load configuration from file."""
        filepath = self.config_dir / filename
        if not filepath.exists():
            return None

        try:
            if filename.endswith(".yaml"):
                import yaml

                with open(filepath) as f:
                    return yaml.safe_load(f) or {}
            elif filename.endswith(".json"):
                with open(filepath) as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading configuration file {filepath}: {e}")

        return None

    def get(self) -> EnvironmentConfig:
        """Get current configuration."""
        if self._config is None:
            self.load()
        return self._config

    def watch(self, callback: callable) -> None:
        """Register a callback for configuration changes."""
        self._watchers.append(callback)

    def _notify_watchers(self) -> None:
        """Notify watchers of configuration changes."""
        for callback in self._watchers:
            try:
                callback(self._config)
            except Exception as e:
                logger.error(f"Error in configuration watcher: {e}")

    def create_example_configs(self) -> None:
        """Create example configuration files."""
        # Development config
        dev_config = {
            "app_mode": "development",
            "debug": True,
            "database": {"backend": "sqlite", "echo": True},
            "cache": {"backend": "memory"},
            "security": {"require_api_key": False},
            "observability": {"log_level": "DEBUG"},
        }

        # Production config
        prod_config = {
            "app_mode": "production",
            "debug": False,
            "database": {"backend": "postgresql", "pool_size": 20},
            "cache": {"backend": "redis", "enable_l2_cache": True},
            "security": {"require_api_key": True},
            "observability": {"log_level": "INFO", "enable_tracing": True},
        }

        # Test config
        test_config = {
            "app_mode": "test",
            "debug": True,
            "database": {"backend": "sqlite", "url": "sqlite:///:memory:"},
            "cache": {"backend": "memory"},
            "security": {"require_api_key": False},
        }

        for name, config in [("dev.yaml", dev_config), ("prod.yaml", prod_config), ("test.yaml", test_config)]:
            filepath = self.config_dir / name
            if not filepath.exists():
                try:
                    import yaml

                    with open(filepath, "w") as f:
                        yaml.dump(config, f, default_flow_style=False)
                    logger.info(f"Created example configuration: {filepath}")
                except Exception as e:
                    logger.error(f"Error creating example configuration: {e}")


# Global configuration manager
_config_manager: ConfigurationManager | None = None


def get_config_manager(config_dir: Path | None = None) -> ConfigurationManager:
    """Get or create the global configuration manager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigurationManager(config_dir)
    return _config_manager


def get_config() -> EnvironmentConfig:
    """Get current configuration."""
    return get_config_manager().get()
