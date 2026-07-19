from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
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
    # 用户/租户管理存储后端 (P1-03): memory=进程内存(仅 dev); postgres=SQL 后端,
    # 使用 database_url 指向的数据库(生产须为 Postgres), 支持多实例共享
    admin_store_backend: str = "memory"
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
    approval_store_path: Path = PROJECT_ROOT / "data" / "approvals.json"
    api_key_store_path: Path = PROJECT_ROOT / "data" / "api_keys.json"
    audit_store_path: Path = PROJECT_ROOT / "data" / "audit.jsonl"
    audit_hmac_secret: str | None = None
    tool_execution_store_path: Path = PROJECT_ROOT / "data" / "tool_executions.json"
    playwright_headless: bool = True

    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str | None = None

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

    @field_validator("admin_store_backend")
    @classmethod
    def _validate_admin_store_backend(cls, value: str) -> str:
        """用户/租户存储后端取值校验 (P1-03)。"""
        normalized = value.strip().lower()
        valid_backends = {"memory", "postgres"}
        if normalized not in valid_backends:
            raise ValueError(
                f"Invalid admin_store_backend: {value!r}. Must be one of: {sorted(valid_backends)}"
            )
        return normalized

    @model_validator(mode="after")
    def _production_storage_fail_fast(self) -> "Settings":
        """P1-19: 生产模式存储 fail-fast 守卫。

        app_mode=production 时, 以下任一情况直接拒绝启动(一次性列出全部违规项):
        - database_url 指向 sqlite(单文件库, 多实例/多副本部署数据分裂);
        - memory_backend 为 memory/jsonl(进程内存或本地文件, 重启即丢且不可共享);
        - trace_backend 为 memory(进程内存);
        - admin_store_backend 为 memory(用户/租户库在进程内存, 重启即丢)。

        修复方向: 统一设置 XAGENT_DATABASE_URL 为 Postgres DSN, 并将
        XAGENT_MEMORY_BACKEND / XAGENT_TRACE_BACKEND / XAGENT_ADMIN_STORE_BACKEND
        设置为外部化后端(postgres 等)。
        """
        if self.app_mode != "production":
            return self

        violations: list[str] = []
        if self.database_url.strip().lower().startswith("sqlite"):
            violations.append(
                "- database_url 指向 sqlite(单文件嵌入式库, 多实例部署会数据分裂): "
                "设置 XAGENT_DATABASE_URL=postgresql+asyncpg://<user>:<pass>@<host>:5432/<db>"
            )
        if self.memory_backend.strip().lower() in {"memory", "jsonl"}:
            violations.append(
                f"- memory_backend={self.memory_backend!r} 为进程内存/本地文件后端: "
                "设置 XAGENT_MEMORY_BACKEND=postgres (或 qdrant)"
            )
        if self.trace_backend.strip().lower() == "memory":
            violations.append(
                "- trace_backend='memory' 为进程内存后端: "
                "设置 XAGENT_TRACE_BACKEND=postgres (或 langfuse)"
            )
        if self.admin_store_backend.strip().lower() == "memory":
            violations.append(
                "- admin_store_backend='memory' 使用户/租户库驻留进程内存(重启即丢, 不可多实例共享): "
                "设置 XAGENT_ADMIN_STORE_BACKEND=postgres"
            )

        if violations:
            raise ValueError(
                "生产模式 (app_mode=production) 检测到进程内存/文件/sqlite 存储, "
                "多实例部署将导致数据分裂或丢失, 拒绝启动 (P1-19 fail-fast):\n"
                + "\n".join(violations)
            )
        return self

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
