"""Observability configuration module."""

from enum import Enum
from typing import Optional

from pydantic import Field, field_validator

from .base import BaseConfig


class LogLevel(str, Enum):
    """Log level enumeration."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(str, Enum):
    """Log format enumeration."""

    JSON = "json"
    TEXT = "text"


class LogOutput(str, Enum):
    """Log output enumeration."""

    STDOUT = "stdout"
    FILE = "file"
    BOTH = "both"


class ObservabilityConfig(BaseConfig):
    """Observability configuration for logging, tracing, and monitoring."""

    # Logging configuration
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Logging level",
    )
    log_format: LogFormat = Field(
        default=LogFormat.JSON,
        description="Log format (json or text)",
    )
    log_output: LogOutput = Field(
        default=LogOutput.STDOUT,
        description="Log output destination (stdout, file, or both)",
    )
    log_file: str = Field(
        default="logs/xagent.log",
        description="Log file path",
    )
    log_max_bytes: int = Field(
        default=10485760,  # 10MB
        ge=1048576,  # 1MB minimum
        description="Maximum log file size in bytes before rotation",
    )
    log_backup_count: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of backup log files to keep",
    )

    # Tracing configuration
    trace_enabled: bool = Field(
        default=True,
        description="Enable distributed tracing",
    )
    trace_sample_rate: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Trace sampling rate (0.0 to 1.0)",
    )

    # Langfuse integration
    langfuse_enabled: bool = Field(
        default=False,
        description="Enable Langfuse integration",
    )
    langfuse_public_key: Optional[str] = Field(
        default=None,
        description="Langfuse public key",
    )
    langfuse_secret_key: Optional[str] = Field(
        default=None,
        description="Langfuse secret key",
    )
    langfuse_host: Optional[str] = Field(
        default=None,
        description="Langfuse host URL",
    )

    # Prometheus monitoring
    prometheus_enabled: bool = Field(
        default=False,
        description="Enable Prometheus metrics",
    )
    prometheus_port: int = Field(
        default=8001,
        ge=1024,
        le=65535,
        description="Prometheus metrics port",
    )
    prometheus_path: str = Field(
        default="/metrics",
        description="Prometheus metrics endpoint path",
    )

    # Sentry error tracking
    sentry_enabled: bool = Field(
        default=False,
        description="Enable Sentry error tracking",
    )
    sentry_dsn: Optional[str] = Field(
        default=None,
        description="Sentry DSN",
    )
    sentry_environment: str = Field(
        default="development",
        description="Sentry environment name",
    )
    sentry_traces_sample_rate: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Sentry traces sampling rate",
    )

    # Performance monitoring
    slow_query_threshold_ms: int = Field(
        default=1000,
        ge=100,
        description="Slow query threshold in milliseconds",
    )
    slow_api_threshold_ms: int = Field(
        default=5000,
        ge=100,
        description="Slow API threshold in milliseconds",
    )

    # Metrics collection
    metrics_enabled: bool = Field(
        default=True,
        description="Enable metrics collection",
    )
    metrics_retention_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Metrics retention period in days",
    )

    @field_validator("trace_sample_rate", "sentry_traces_sample_rate")
    @classmethod
    def validate_sample_rate(cls, v: float) -> float:
        """Validate sample rate is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Sample rate must be between 0.0 and 1.0")
        return v

    @field_validator("langfuse_enabled")
    @classmethod
    def validate_langfuse_config(cls, v: bool, info) -> bool:
        """Validate Langfuse configuration."""
        if v:
            public_key = info.data.get("langfuse_public_key")
            secret_key = info.data.get("langfuse_secret_key")
            if not public_key or not secret_key:
                raise ValueError(
                    "langfuse_public_key and langfuse_secret_key must be set "
                    "when langfuse_enabled is True"
                )
        return v

    @field_validator("sentry_enabled")
    @classmethod
    def validate_sentry_config(cls, v: bool, info) -> bool:
        """Validate Sentry configuration."""
        if v:
            dsn = info.data.get("sentry_dsn")
            if not dsn:
                raise ValueError("sentry_dsn must be set when sentry_enabled is True")
        return v

    def is_json_logging(self) -> bool:
        """Check if using JSON logging format."""
        return self.log_format == LogFormat.JSON

    def is_file_logging(self) -> bool:
        """Check if logging to file."""
        return self.log_output in [LogOutput.FILE, LogOutput.BOTH]

    def is_stdout_logging(self) -> bool:
        """Check if logging to stdout."""
        return self.log_output in [LogOutput.STDOUT, LogOutput.BOTH]
