"""Configuration validator module for comprehensive validation and health checks."""

import logging
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from .base import BaseConfig, Environment
from .database import DatabaseConfig
from .cache import CacheConfig
from .security import SecurityConfig
from .observability import ObservabilityConfig


logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Configuration validation error."""

    pass


class ConfigValidator:
    """Comprehensive configuration validator."""

    def __init__(self):
        """Initialize validator."""
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_all(
        self,
        base_config: BaseConfig,
        database_config: DatabaseConfig,
        cache_config: CacheConfig,
        security_config: SecurityConfig,
        observability_config: ObservabilityConfig,
    ) -> bool:
        """Validate all configuration sections.

        Args:
            base_config: Base configuration
            database_config: Database configuration
            cache_config: Cache configuration
            security_config: Security configuration
            observability_config: Observability configuration

        Returns:
            True if all validations pass, False otherwise

        Raises:
            ConfigValidationError: If critical validation fails
        """
        self.errors.clear()
        self.warnings.clear()

        # Validate individual sections
        self._validate_base(base_config)
        self._validate_database(database_config, base_config)
        self._validate_cache(cache_config, base_config)
        self._validate_security(security_config, base_config)
        self._validate_observability(observability_config, base_config)

        # Validate cross-section dependencies
        self._validate_dependencies(
            base_config, database_config, cache_config, security_config, observability_config
        )

        # Log results
        if self.errors:
            logger.error(f"Configuration validation failed with {len(self.errors)} error(s)")
            for error in self.errors:
                logger.error(f"  - {error}")

        if self.warnings:
            logger.warning(f"Configuration validation found {len(self.warnings)} warning(s)")
            for warning in self.warnings:
                logger.warning(f"  - {warning}")

        if self.errors:
            raise ConfigValidationError(
                f"Configuration validation failed: {'; '.join(self.errors)}"
            )

        return True

    def _validate_base(self, config: BaseConfig) -> None:
        """Validate base configuration."""
        if not config.app_name:
            self.errors.append("app_name cannot be empty")

        if not config.project_root.exists():
            self.errors.append(f"project_root does not exist: {config.project_root}")

        if not config.data_dir.exists():
            try:
                config.data_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self.errors.append(f"Cannot create data_dir: {e}")

        if not config.logs_dir.exists():
            try:
                config.logs_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self.errors.append(f"Cannot create logs_dir: {e}")

    def _validate_database(self, config: DatabaseConfig, base_config: BaseConfig) -> None:
        """Validate database configuration."""
        if not config.database_url:
            self.errors.append("database_url cannot be empty")
            return

        # Validate connection pool settings
        if config.database_pool_size < 1:
            self.errors.append("database_pool_size must be at least 1")

        if config.database_max_overflow < 0:
            self.errors.append("database_max_overflow cannot be negative")

        # Validate PostgreSQL specific settings
        if config.is_postgresql():
            if config.postgres_vector_dimensions < 1:
                self.errors.append("postgres_vector_dimensions must be at least 1")

        # Validate audit configuration for production
        if base_config.is_production() and not config.audit_hmac_secret:
            self.errors.append(
                "audit_hmac_secret must be set for production deployments"
            )

    def _validate_cache(self, config: CacheConfig, base_config: BaseConfig) -> None:
        """Validate cache configuration."""
        if config.has_redis():
            try:
                redis_url = config.get_redis_url()
                if not redis_url:
                    self.errors.append("Redis URL is invalid")
            except Exception as e:
                self.errors.append(f"Invalid Redis configuration: {e}")

        # Validate cache TTL settings
        if config.cache_ttl_short >= config.cache_ttl_default:
            self.warnings.append(
                "cache_ttl_short should be less than cache_ttl_default"
            )

        if config.cache_ttl_default >= config.cache_ttl_long:
            self.warnings.append(
                "cache_ttl_default should be less than cache_ttl_long"
            )

        # Warn if no Redis in production
        if base_config.is_production() and not config.has_redis():
            self.warnings.append(
                "Redis is not configured in production. "
                "Consider enabling Redis for better performance."
            )

    def _validate_security(self, config: SecurityConfig, base_config: BaseConfig) -> None:
        """Validate security configuration."""
        # Validate JWT configuration
        if len(config.jwt_secret) < 32:
            self.errors.append("jwt_secret must be at least 32 characters long")

        if len(config.encryption_key) < 32:
            self.errors.append("encryption_key must be at least 32 characters long")

        # Validate production secrets
        if base_config.is_production():
            default_jwt = "change-this-to-a-random-64-char-string"
            default_encryption = "change-this-to-32-char-hex-string"

            if config.jwt_secret == default_jwt:
                self.errors.append(
                    "jwt_secret must be changed from default in production"
                )

            if config.encryption_key == default_encryption:
                self.errors.append(
                    "encryption_key must be changed from default in production"
                )

        # Validate CORS configuration
        origins = config.get_cors_origins_list()
        if not origins:
            self.errors.append("At least one CORS origin must be configured")

        if base_config.is_production():
            if "*" in origins:
                self.errors.append(
                    "CORS wildcard origin (*) is not allowed in production"
                )

        # Validate HTTPS requirement in production
        if base_config.is_production() and not config.require_https:
            self.errors.append("HTTPS is required in production mode")

        # Validate SSL certificate paths if HTTPS is required
        if config.require_https:
            if not config.ssl_cert_path or not config.ssl_key_path:
                self.errors.append(
                    "ssl_cert_path and ssl_key_path must be set when require_https is True"
                )

    def _validate_observability(
        self, config: ObservabilityConfig, base_config: BaseConfig
    ) -> None:
        """Validate observability configuration."""
        # Validate Langfuse configuration
        if config.langfuse_enabled:
            if not config.langfuse_public_key or not config.langfuse_secret_key:
                self.errors.append(
                    "langfuse_public_key and langfuse_secret_key must be set "
                    "when langfuse_enabled is True"
                )

        # Validate Sentry configuration
        if config.sentry_enabled:
            if not config.sentry_dsn:
                self.errors.append("sentry_dsn must be set when sentry_enabled is True")

        # Validate log file path
        if config.is_file_logging():
            log_dir = config.logs_dir
            if not log_dir.exists():
                try:
                    log_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    self.errors.append(f"Cannot create logs directory: {e}")

    def _validate_dependencies(
        self,
        base_config: BaseConfig,
        database_config: DatabaseConfig,
        cache_config: CacheConfig,
        security_config: SecurityConfig,
        observability_config: ObservabilityConfig,
    ) -> None:
        """Validate cross-section dependencies."""
        # Validate that production environment has all required settings
        if base_config.is_production():
            if not security_config.jwt_secret or security_config.jwt_secret.startswith("change-"):
                self.errors.append("Production environment requires a valid jwt_secret")

            if not security_config.encryption_key or security_config.encryption_key.startswith("change-"):
                self.errors.append("Production environment requires a valid encryption_key")

            if not database_config.audit_hmac_secret:
                self.errors.append("Production environment requires audit_hmac_secret")

    def get_summary(self) -> Dict[str, Any]:
        """Get validation summary.

        Returns:
            Dictionary with validation results
        """
        return {
            "valid": len(self.errors) == 0,
            "errors": self.errors,
            "warnings": self.warnings,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }
