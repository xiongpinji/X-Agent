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

    llm_backend: str = "auto"  # auto = 有 Key 用真实后端，无 Key 明确报错
    llm_fallback_order: str = "openai,deepseek,anthropic,ollama"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    deepseek_api_key: str | None = None
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str | None = None

    # 默认 jsonl: 本地文件存储(全功能 MemorySystem+去重), 无外部依赖, 开发开箱即用;
    # 生产必须显式设置(生产守卫会拒绝 memory/jsonl, 见 _production_storage_fail_fast)。
    memory_backend: str = "jsonl"
    database_url: str = "postgresql+asyncpg://xagent:xagent@localhost:5432/xagent_db"
    # 用户/租户管理存储后端 (P1-03): memory=进程内存(仅测试); file=JSON文件(dev/单实例);
    # postgres=SQL 后端, 使用 database_url 指向的数据库(生产须为 Postgres), 支持多实例共享
    admin_store_backend: str = "file"
    admin_store_path: Path = PROJECT_ROOT / "data" / "admin_store.json"
    memory_store_path: Path = PROJECT_ROOT / "data" / "memory.jsonl"
    embedding_backend: str = "auto"  # auto | openai | sentence-transformers | local (hash)
    embedding_model: str = "text-embedding-3-small"  # XAGENT_EMBEDDING_MODEL
    embedding_dim: int = 384  # XAGENT_EMBEDDING_DIM
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int | None = None
    postgres_enable_vector_search: bool = False
    postgres_vector_dimensions: int = 1536

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None

    # Qdrant Snapshot / Disaster Recovery
    qdrant_snapshot_enabled: bool = False  # XAGENT_QDRANT_SNAPSHOT_ENABLED
    qdrant_snapshot_keep: int = 5  # XAGENT_QDRANT_SNAPSHOT_KEEP: snapshots to retain per collection

    # Automated Backup Scheduler
    backup_enabled: bool = False  # XAGENT_BACKUP_ENABLED
    backup_dir: str = "data/backups"  # XAGENT_BACKUP_DIR
    backup_schedule: str = "0 2 * * *"  # XAGENT_BACKUP_SCHEDULE (cron)
    backup_retention_days: int = 30  # XAGENT_BACKUP_RETENTION_DAYS

    # Neo4j 图谱数据库 (可选, 用于记忆关系图谱)
    neo4j_enabled: bool = False  # 默认关闭, 生产环境可启用
    neo4j_url: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    neo4j_database: str = "neo4j"

    # Redis configuration for session storage
    redis_url: str | None = None

    trace_backend: str = "memory"
    trace_store_path: Path = PROJECT_ROOT / "data" / "traces.jsonl"
    run_store_path: Path = PROJECT_ROOT / "data" / "runs.jsonl"
    workflow_store_path: Path = PROJECT_ROOT / "data" / "workflows.json"
    workflow_run_store_path: Path = PROJECT_ROOT / "data" / "workflow_runs.jsonl"
    workflow_schedule_store_path: Path = PROJECT_ROOT / "data" / "workflow_schedules.json"
    # Workflow 存储后端: db=PostgreSQL(生产), file=JSON文件(dev), auto=尝试db降级file
    # 默认 auto: 本地开发无 Postgres 时显式降级为文件存储(WARNING), 避免启动/测试挂起;
    # 生产部署必须显式设 XAGENT_WORKFLOW_STORE_BACKEND=db(生产守卫会校验).
    workflow_store_backend: str = "auto"
    # Workflow 并行 DAG 执行配置
    workflow_max_parallel: int = 5  # 最大并行节点数 (semaphore limit)
    workflow_parallel_mode: str = "auto"  # auto | parallel | sequential
    workflow_parallel_error_strategy: str = "fail_fast"  # fail_fast | continue_others
    approval_store_path: Path = PROJECT_ROOT / "data" / "approvals.json"
    api_key_store_path: Path = PROJECT_ROOT / "data" / "api_keys.json"
    audit_store_path: Path = PROJECT_ROOT / "data" / "audit.jsonl"
    audit_hmac_secret: str | None = None

    # P1-04: 审计日志轮转与外送
    audit_rotation_enabled: bool = True
    audit_max_size_mb: int = 50
    audit_retention_days: int = 30
    audit_webhook_url: str = ""  # 空=禁用 webhook 外送
    audit_ship_enabled: bool = False  # 总开关: 是否启用审计外送
    tool_execution_store_path: Path = PROJECT_ROOT / "data" / "tool_executions.json"
    playwright_headless: bool = True

    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str | None = None

    max_iterations: int = 4
    default_token_budget: int = 16_000
    default_cost_budget_usd: float = 1.0
    enable_high_risk_tools: bool = False

    # P1-14: Context management — agent loop context window
    context_window_size: int = 128_000  # XAGENT_CONTEXT_WINDOW_SIZE: total model context window (tokens)
    context_strategy: str = "sliding_window"  # XAGENT_CONTEXT_STRATEGY: sliding_window | summarize | hybrid
    context_reserve_output: int = 4096  # XAGENT_CONTEXT_RESERVE_OUTPUT: tokens reserved for LLM output
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

    # ─── Rate Limiting & Request Size (Production Security Hardening) ────────
    rate_limit_enabled: bool | None = None  # XAGENT_RATE_LIMIT_ENABLED; None=auto (true in prod, false in dev)
    rate_limit_rpm: int = 100  # General API requests per minute per IP
    rate_limit_auth_rpm: int = 20  # Auth routes requests per minute per IP
    rate_limit_login_rpm: int = 10  # Login attempts per minute per IP
    rate_limit_register_rpm: int = 5  # Registration attempts per minute per IP
    max_request_body_size: int = 10 * 1024 * 1024  # 10MB default

    @property
    def rate_limit_active(self) -> bool:
        """Whether rate limiting is active (resolves None → mode-based default)."""
        if self.rate_limit_enabled is not None:
            return self.rate_limit_enabled
        return self.app_mode == "production"

    # P2-04: PromptGuard — prompt injection defense
    prompt_guard_enabled: bool = True
    prompt_guard_suspicious_threshold: float = 0.4
    prompt_guard_malicious_threshold: float = 0.7
    prompt_guard_action: str = "warn"  # pass | warn | sanitize | block

    # P2-06: OpenTelemetry — OTLP export
    otel_enabled: bool = False
    otel_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "xagent-api"
    otel_metric_interval: int = 60

    # P2-02: KMS 密钥管理
    kms_backend: str = "local"  # local | vault | aws_kms
    kms_local_key_path: str = ""  # 本地密钥存储目录 (空=默认 .xagent_runtime/keys)
    kms_vault_addr: str = "http://127.0.0.1:8200"
    kms_vault_token: str = ""
    kms_vault_mount: str = "transit"
    kms_vault_key_name: str = "xagent-master"
    kms_aws_key_id: str = ""
    kms_aws_region: str = "us-east-1"
    kms_auto_rotate_days: int = 90  # 0=禁用自动轮换
    kms_key_prefix: str = "xagent"

    # P2-03: GDPR 数据主体权利
    gdpr_residency_enabled: bool = False
    gdpr_default_region: str = "global"  # global | eu | cn | us | apac
    gdpr_pii_masking_enabled: bool = True
    gdpr_data_retention_days: int = 365  # 数据保留期限

    # ─── 竞品对齐能力 (2026-07) ─────────────────────────────────────────────
    # MoA 混合模型推理
    moa_enabled: bool = False
    moa_models: str = ""  # 逗号分隔模型名 (e.g. "gpt-4o,claude-3,deepseek-v2")
    moa_strategy: str = "consensus"  # consensus | best_of_n | weighted_vote
    moa_timeout: float = 60.0
    moa_min_responses: int = 2

    # Completion Contracts 证据驱动完成
    completion_contract_enabled: bool = False
    completion_require_test: bool = True
    completion_require_diff: bool = False
    completion_min_evidence: int = 1

    # Work Mode 跨应用长任务
    work_mode_enabled: bool = False
    work_mode_max_hours: float = 8.0

    # Ultra Mode 4-Agent 并行
    ultra_mode_enabled: bool = False
    ultra_max_agents: int = 4
    ultra_budget_tokens: int = 50000
    ultra_timeout_seconds: int = 600

    # ─── Payment Provider ─────────────────────────────────────────────────────
    payment_provider: str = "mock"  # mock | stripe | alipay
    stripe_api_key: str = ""
    stripe_webhook_secret: str = ""
    alipay_app_id: str = ""

    # ─── Tenant Quota Management (Commercial Deployment) ─────────────────────
    quota_enabled: bool = False  # XAGENT_QUOTA_ENABLED: enable per-tenant quota enforcement
    quota_store_path: Path = PROJECT_ROOT / "data" / "quotas.json"  # XAGENT_QUOTA_STORE_PATH

    # ─── Notification / Email Delivery ────────────────────────────────────────
    smtp_host: str = ""  # XAGENT_SMTP_HOST: SMTP server hostname (empty=use console provider)
    smtp_port: int = 587  # XAGENT_SMTP_PORT
    smtp_username: str = ""  # XAGENT_SMTP_USERNAME
    smtp_password: str = ""  # XAGENT_SMTP_PASSWORD
    smtp_from: str = ""  # XAGENT_SMTP_FROM: sender address (defaults to smtp_username)
    notification_webhook_url: str = ""  # XAGENT_NOTIFICATION_WEBHOOK_URL: fallback webhook

    # ─── Graceful Shutdown & Connection Lifecycle ──────────────────────────────
    shutdown_timeout: float = 30.0  # XAGENT_SHUTDOWN_TIMEOUT: max seconds to wait for in-flight requests
    shutdown_drain_seconds: float = 5.0  # XAGENT_SHUTDOWN_DRAIN_SECONDS: LB detection window (health→503)

    # P1-01: MCP (Model Context Protocol) — 官方 SDK 工具发现与管理
    mcp_enabled: bool = False  # opt-in：显式启用 MCP 服务器连接
    mcp_config_path: str = "config/mcp_servers.example.yaml"  # MCP 服务器配置文件路径

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
                    "Production secrets must be changed from defaults. "
                    "Set XAGENT_JWT_SECRET and XAGENT_ENCRYPTION_KEY environment variables "
                    "to strong random values (minimum 32 characters each). "
                    "Generate using: python scripts/generate_secrets.py"
                )

            # Enforce minimum length
            if len(value) < 32:
                raise ValueError("Production secrets must be at least 32 characters long")

            # Ensure sufficient entropy (at least 128 bits for 32 chars)
            if not any(c.isupper() for c in value) or not any(c.isdigit() for c in value):
                raise ValueError(
                    "Production secrets must contain uppercase letters and digits "
                    "for sufficient entropy"
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
        valid_backends = {"memory", "file", "postgres"}
        if normalized not in valid_backends:
            raise ValueError(
                f"Invalid admin_store_backend: {value!r}. Must be one of: {sorted(valid_backends)}"
            )
        return normalized

    @field_validator("context_strategy")
    @classmethod
    def _validate_context_strategy(cls, value: str) -> str:
        """P1-14: 上下文管理策略取值校验。"""
        normalized = value.strip().lower()
        valid_strategies = {"sliding_window", "summarize", "hybrid"}
        if normalized not in valid_strategies:
            raise ValueError(
                f"Invalid context_strategy: {value!r}. Must be one of: {sorted(valid_strategies)}"
            )
        return normalized

    @model_validator(mode="after")
    def _production_required_services(self) -> Settings:
        """生产模式必须配置外部服务连接 (Redis/Database)。

        确保生产环境不依赖进程内存状态，支持多实例水平扩展。
        """
        if self.app_mode != "production":
            return self

        violations: list[str] = []
        if not self.redis_url:
            violations.append(
                "- redis_url 未设置 (多实例部署需要共享状态存储): "
                "设置 XAGENT_REDIS_URL=redis://<host>:6379/0"
            )
        if not self.database_url or "localhost" in self.database_url:
            violations.append(
                "- database_url 指向 localhost 或未设置 (生产环境需外部数据库): "
                "设置 XAGENT_DATABASE_URL=postgresql+asyncpg://<user>:<pass>@<db-host>:5432/<db>"
            )

        if violations:
            raise ValueError(
                "生产模式 (app_mode=production) 缺少必要外部服务配置, 拒绝启动:\n"
                + "\n".join(violations)
            )
        return self

    @model_validator(mode="after")
    def _production_storage_fail_fast(self) -> Settings:
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
        if self.admin_store_backend.strip().lower() in {"memory", "file"}:
            violations.append(
                f"- admin_store_backend={self.admin_store_backend!r} 为进程内存/本地文件后端(重启不丢但不可多实例共享): "
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
