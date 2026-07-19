"""Unified settings module combining all configuration sections."""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator

from .base import BaseConfig, Environment
from .database import DatabaseConfig
from .cache import CacheConfig
from .security import SecurityConfig
from .observability import ObservabilityConfig
from .validator import ConfigValidator, ConfigValidationError

logger = logging.getLogger(__name__)


class Settings(BaseConfig):
    """Unified settings combining all configuration sections."""

    # LLM Configuration
    llm_backend: str = Field(
        default="mock",
        description="LLM backend (mock, openai, deepseek, anthropic)",
    )
    llm_fallback_order: str = Field(
        default="",
        description="Comma-separated list of LLM backends to try in order",
    )
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key",
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model name",
    )
    deepseek_api_key: Optional[str] = Field(
        default=None,
        description="DeepSeek API key",
    )
    deepseek_model: str = Field(
        default="deepseek-chat",
        description="DeepSeek model name",
    )
    deepseek_base_url: Optional[str] = Field(
        default=None,
        description="DeepSeek base URL",
    )
    anthropic_api_key: Optional[str] = Field(
        default=None,
        description="Anthropic API key",
    )

    # Memory Configuration
    memory_backend: str = Field(
        default="memory",
        description="Memory backend (memory, jsonl, postgres, qdrant)",
    )
    embedding_backend: str = Field(
        default="local",
        description="Embedding backend (local, openai)",
    )
    openai_embedding_model: str = Field(
        default="text-embedding-3-small",
        description="OpenAI embedding model",
    )
    openai_embedding_dimensions: Optional[int] = Field(
        default=None,
        description="OpenAI embedding dimensions",
    )

    # Qdrant Configuration
    qdrant_url: str = Field(
        default="http://localhost:6333",
        description="Qdrant vector database URL",
    )
    qdrant_api_key: Optional[str] = Field(
        default=None,
        description="Qdrant API key",
    )

    # Agent Configuration
    max_iterations: int = Field(
        default=4,
        ge=1,
        le=100,
        description="Maximum agent iterations",
    )
    default_token_budget: int = Field(
        default=16000,
        ge=1000,
        description="Default token budget per run",
    )
    default_cost_budget_usd: float = Field(
        default=1.0,
        ge=0.01,
        description="Default cost budget in USD",
    )
    enable_high_risk_tools: bool = Field(
        default=False,
        description="Enable high-risk tools (use with caution)",
    )

    # Browser Configuration
    playwright_headless: bool = Field(
        default=True,
        description="Run Playwright in headless mode",
    )

    # Feature Flags
    feature_self_evolution: bool = Field(
        default=True,
        description="Enable self-evolution feature",
    )
    feature_skill_marketplace: bool = Field(
        default=True,
        description="Enable skill marketplace feature",
    )
    feature_multi_agent: bool = Field(
        default=True,
        description="Enable multi-agent feature",
    )
    feature_rpa: bool = Field(
        default=True,
        description="Enable RPA feature",
    )
    feature_multimodal: bool = Field(
        default=True,
        description="Enable multimodal feature",
    )

    # External Integrations
    skillhub_url: str = Field(
        default="https://skillhub.cn",
        description="SkillHub URL",
    )
    skillhub_api_key: Optional[str] = Field(
        default=None,
        description="SkillHub API key",
    )

    # Feishu Integration
    feishu_app_id: Optional[str] = Field(
        default=None,
        description="Feishu app ID",
    )
    feishu_app_secret: Optional[str] = Field(
        default=None,
        description="Feishu app secret",
    )
    feishu_encrypt_key: Optional[str] = Field(
        default=None,
        description="Feishu event callback encrypt key",
    )
    # DingTalk Integration
    dingtalk_webhook_url: Optional[str] = Field(
        default=None,
        description="DingTalk webhook URL",
    )

    # WeChat Integration
    wechat_app_id: Optional[str] = Field(
        default=None,
        description="WeChat app ID",
    )
    wechat_app_secret: Optional[str] = Field(
        default=None,
        description="WeChat app secret",
    )

    # Email Configuration
    smtp_host: Optional[str] = Field(
        default=None,
        description="SMTP host",
    )
    smtp_port: int = Field(
        default=587,
        ge=1,
        le=65535,
        description="SMTP port",
    )
    smtp_user: Optional[str] = Field(
        default=None,
        description="SMTP username",
    )
    smtp_password: Optional[str] = Field(
        default=None,
        description="SMTP password",
    )
    email_from: str = Field(
        default="noreply@x-agent.ai",
        description="Email from address",
    )

    # S3 Storage Configuration
    s3_endpoint: Optional[str] = Field(
        default=None,
        description="S3 endpoint URL",
    )
    s3_access_key: Optional[str] = Field(
        default=None,
        description="S3 access key",
    )
    s3_secret_key: Optional[str] = Field(
        default=None,
        description="S3 secret key",
    )
    s3_bucket: str = Field(
        default="xagent-data",
        description="S3 bucket name",
    )

    @field_validator("llm_backend")
    @classmethod
    def validate_llm_backend(cls, v: str) -> str:
        """Validate LLM backend."""
        valid_backends = ["mock", "openai", "deepseek", "anthropic"]
        if v not in valid_backends:
            raise ValueError(f"Invalid llm_backend: {v}. Must be one of: {valid_backends}")
        return v

    @field_validator("memory_backend")
    @classmethod
    def validate_memory_backend(cls, v: str) -> str:
        """Validate memory backend."""
        valid_backends = ["memory", "jsonl", "postgres", "qdrant"]
        if v not in valid_backends:
            raise ValueError(f"Invalid memory_backend: {v}. Must be one of: {valid_backends}")
        return v

    @field_validator("embedding_backend")
    @classmethod
    def validate_embedding_backend(cls, v: str) -> str:
        """Validate embedding backend."""
        valid_backends = ["local", "openai"]
        if v not in valid_backends:
            raise ValueError(f"Invalid embedding_backend: {v}. Must be one of: {valid_backends}")
        return v

    def get_database_config(self) -> DatabaseConfig:
        """Get database configuration.

        Returns:
            DatabaseConfig instance
        """
        return DatabaseConfig(**self.model_dump())

    def get_cache_config(self) -> CacheConfig:
        """Get cache configuration.

        Returns:
            CacheConfig instance
        """
        return CacheConfig(**self.model_dump())

    def get_security_config(self) -> SecurityConfig:
        """Get security configuration.

        Returns:
            SecurityConfig instance
        """
        return SecurityConfig(**self.model_dump())

    def get_observability_config(self) -> ObservabilityConfig:
        """Get observability configuration.

        Returns:
            ObservabilityConfig instance
        """
        return ObservabilityConfig(**self.model_dump())

    def validate_all(self) -> bool:
        """Validate all configuration sections.

        Returns:
            True if all validations pass

        Raises:
            ConfigValidationError: If validation fails
        """
        validator = ConfigValidator()
        return validator.validate_all(
            base_config=self,
            database_config=self.get_database_config(),
            cache_config=self.get_cache_config(),
            security_config=self.get_security_config(),
            observability_config=self.get_observability_config(),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance.

    Returns:
        Settings instance

    Raises:
        ConfigValidationError: If configuration validation fails
    """
    settings = Settings()
    try:
        settings.validate_all()
        logger.info(f"Configuration loaded successfully (environment: {settings.environment})")
    except ConfigValidationError as e:
        logger.error(f"Configuration validation failed: {e}")
        raise
    return settings


def reload_settings() -> Settings:
    """Reload settings (clears cache).

    Returns:
        New Settings instance
    """
    get_settings.cache_clear()
    return get_settings()
