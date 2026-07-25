"""Database configuration module."""


from pydantic import Field, field_validator

from .base import BaseConfig, Environment


class DatabaseConfig(BaseConfig):
    """Database configuration with support for multiple backends."""

    # Primary database
    database_url: str = Field(
        default="sqlite:///./data/xagent.db",
        description="Primary database connection URL",
    )
    database_pool_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Database connection pool size",
    )
    database_max_overflow: int = Field(
        default=10,
        ge=0,
        le=50,
        description="Maximum overflow connections",
    )
    database_pool_recycle: int = Field(
        default=3600,
        ge=60,
        description="Connection recycle time in seconds",
    )
    database_echo: bool = Field(
        default=False,
        description="Enable SQL query logging",
    )

    # PostgreSQL specific
    postgres_enable_vector_search: bool = Field(
        default=False,
        description="Enable PostgreSQL vector search (pgvector extension)",
    )
    postgres_vector_dimensions: int = Field(
        default=1536,
        ge=1,
        le=4096,
        description="Vector embedding dimensions for pgvector",
    )

    # Memory store (for non-database backends)
    memory_store_path: str = Field(
        default="data/memory.jsonl",
        description="Path to memory store file (JSONL format)",
    )

    # Trace store
    trace_store_path: str = Field(
        default="data/traces.jsonl",
        description="Path to trace store file (JSONL format)",
    )
    run_store_path: str = Field(
        default="data/runs.jsonl",
        description="Path to run store file (JSONL format)",
    )

    # Workflow store
    workflow_store_backend: str = Field(
        default="db",
        description="Workflow store backend (file, db, auto). "
        "db=PostgreSQL/SQL (production), file=JSON files (dev), "
        "auto=try db then fall back to file.",
    )
    workflow_store_path: str = Field(
        default="data/workflows.json",
        description="Path to workflow store file (JSON format)",
    )
    workflow_run_store_path: str = Field(
        default="data/workflow_runs.jsonl",
        description="Path to workflow run store file (JSONL format)",
    )
    workflow_schedule_store_path: str = Field(
        default="data/workflow_schedules.json",
        description="Path to workflow schedule store file (JSON format)",
    )

    # Approval and audit stores
    approval_store_path: str = Field(
        default="data/approvals.json",
        description="Path to approval store file (JSON format)",
    )
    audit_store_path: str = Field(
        default="data/audit.jsonl",
        description="Path to audit store file (JSONL format)",
    )
    audit_hmac_secret: str | None = Field(
        default=None,
        description="HMAC secret for audit log integrity verification",
    )

    # API key and tool execution stores
    api_key_store_path: str = Field(
        default="data/api_keys.json",
        description="Path to API key store file (JSON format)",
    )
    tool_execution_store_path: str = Field(
        default="data/tool_executions.json",
        description="Path to tool execution store file (JSON format)",
    )

    @field_validator("audit_hmac_secret")
    @classmethod
    def validate_audit_hmac_secret(cls, v: str | None, info) -> str | None:
        """Enforce audit HMAC secret in production."""
        if not v and info.data.get("environment") == Environment.PRODUCTION:
            raise ValueError(
                "audit_hmac_secret must be set for production deployments. "
                "Generate using: python scripts/generate_secrets.py"
            )
        return v

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str, info) -> str:
        """Validate database URL format."""
        if not v:
            raise ValueError("database_url cannot be empty")
        if not any(v.startswith(prefix) for prefix in ["sqlite://", "postgresql://", "mysql://", "mongodb://"]):
            raise ValueError(
                "database_url must start with a valid scheme: "
                "sqlite://, postgresql://, mysql://, or mongodb://"
            )
        return v

    def get_database_url(self) -> str:
        """Get the database URL, expanding relative paths for SQLite."""
        if self.database_url.startswith("sqlite:///"):
            # Expand relative paths
            db_path = self.database_url.replace("sqlite:///", "")
            if not db_path.startswith("/"):
                db_path = str(self.data_dir / db_path)
            return f"sqlite:///{db_path}"
        return self.database_url

    def is_sqlite(self) -> bool:
        """Check if using SQLite backend."""
        return self.database_url.startswith("sqlite://")

    def is_postgresql(self) -> bool:
        """Check if using PostgreSQL backend."""
        return self.database_url.startswith("postgresql://")

    def is_mysql(self) -> bool:
        """Check if using MySQL backend."""
        return self.database_url.startswith("mysql://")
