from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", env_prefix="XAGENT_")

    app_name: str = "X-Agent"
    app_mode: str = "development"
    static_dir: Path = PROJECT_ROOT / "frontend"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    require_api_key: bool = False
    bootstrap_api_key: str | None = None
    bootstrap_api_key_sha256: str | None = None

    llm_backend: str = "mock"
    llm_fallback_order: str = ""
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    deepseek_api_key: str | None = None
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str | None = None

    memory_backend: str = "memory"
    database_url: str = "sqlite:///./data/xagent.db"
    memory_store_path: Path = PROJECT_ROOT / "data" / "memory.jsonl"
    embedding_backend: str = "local"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int | None = None
    postgres_enable_vector_search: bool = False
    postgres_vector_dimensions: int = 1536

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None

    # Redis configuration for session storage
    redis_url: str | None = None

    trace_backend: str = "memory"
    trace_store_path: Path = PROJECT_ROOT / "data" / "traces.jsonl"
    run_store_path: Path = PROJECT_ROOT / "data" / "runs.jsonl"
    workflow_store_path: Path = PROJECT_ROOT / "data" / "workflows.json"
    workflow_run_store_path: Path = PROJECT_ROOT / "data" / "workflow_runs.jsonl"
    workflow_schedule_store_path: Path = PROJECT_ROOT / "data" / "workflow_schedules.json"
    control_mode_store_path: Path = PROJECT_ROOT / "data" / "control_modes.json"
    approval_store_path: Path = PROJECT_ROOT / "data" / "approvals.json"
    api_key_store_path: Path = PROJECT_ROOT / "data" / "api_keys.json"
    audit_store_path: Path = PROJECT_ROOT / "data" / "audit.jsonl"
    audit_hmac_secret: str | None = None
    tool_execution_store_path: Path = PROJECT_ROOT / "data" / "tool_executions.json"
    playwright_headless: bool = True

    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str | None = None
    feishu_app_id: str | None = None
    feishu_app_secret: str | None = None
    feishu_encrypt_key: str | None = None
    feishu_base_url: str = "https://open.feishu.cn"

    max_iterations: int = 4
    default_token_budget: int = 16_000
    default_cost_budget_usd: float = 1.0
    enable_high_risk_tools: bool = False
    github_webhook_secret: str | None = None

    # Security settings - CRITICAL: Must be set via environment variables in production
    jwt_secret: str = Field(
        default="change-this-to-a-random-64-char-string",
        description="JWT signing secret (minimum 32 characters, must be changed in production)"
    )
    encryption_key: str = Field(
        default="change-this-to-32-char-hex-string",
        description="Encryption key for sensitive data (minimum 32 characters, must be changed in production)"
    )

    @field_validator("audit_hmac_secret")
    @classmethod
    def _validate_audit_hmac_secret(cls, value: str | None, info) -> str | None:
        if not value and info.data.get("app_mode") == "production":
            raise ValueError("audit_hmac_secret must be set for production deployments")
        return value

    @field_validator("jwt_secret", "encryption_key")
    @classmethod
    def _validate_production_secrets(cls, value: str, info) -> str:
        """Enforce strong secrets in production mode.

        SECURITY: Prevents use of default secrets in production which could
        allow authentication bypass and data exposure.
        """
        app_mode = info.data.get("app_mode", "development")
        if app_mode == "production":
            # List of known default values that must be changed
            default_values = [
                "change-this-to-a-random-64-char-string",
                "change-this-to-32-char-hex-string",
                "default",
                "secret",
                "key",
                "",
            ]

            # Check if value matches any default
            if value.lower() in [d.lower() for d in default_values]:
                raise ValueError(
                    f"Production secrets must be changed from defaults. "
                    f"Set XAGENT_JWT_SECRET and XAGENT_ENCRYPTION_KEY environment variables "
                    f"to strong random values (minimum 32 characters each). "
                    f"Generate using: python scripts/generate_secrets.py"
                )

            # Enforce minimum length
            if len(value) < 32:
                raise ValueError(f"Production secrets must be at least 32 characters long")

            # Ensure sufficient entropy (at least 128 bits for 32 chars)
            if not any(c.isupper() for c in value) or not any(c.isdigit() for c in value):
                raise ValueError(
                    f"Production secrets must contain uppercase letters and digits "
                    f"for sufficient entropy"
                )

        return value

    @field_validator("github_webhook_secret")
    @classmethod
    def _validate_github_webhook_secret(cls, value: str | None, info) -> str | None:
        if not value and info.data.get("app_mode") == "production":
            import logging
            logging.getLogger(__name__).warning(
                "XAGENT_GITHUB_WEBHOOK_SECRET is not set — GitHub webhooks will be unauthenticated"
            )
        return value

    @field_validator("cors_origins")
    @classmethod
    def _normalize_cors_origins(cls, value: str) -> str:
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if not origins:
            raise ValueError("cors_origins must contain at least one origin")
        # Prevent wildcard in production
        if "*" in origins:
            app_mode = os.getenv("XAGENT_APP_MODE", "development")
            if app_mode == "production":
                raise ValueError("CORS wildcard (*) is not allowed in production mode")
        return ",".join(origins)


@lru_cache
def get_settings() -> Settings:
    return Settings()
