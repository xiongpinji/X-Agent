"""Configuration tests."""

import os
import pytest
from pathlib import Path

from backend.app.core.config.base import BaseConfig, Environment
from backend.app.core.config.database import DatabaseConfig
from backend.app.core.config.cache import CacheConfig
from backend.app.core.config.security import SecurityConfig
from backend.app.core.config.observability import ObservabilityConfig
from backend.app.core.config.validator import ConfigValidator, ConfigValidationError
from backend.app.core.config.encryption import ConfigEncryption, EncryptionError
from backend.app.core.config.settings import Settings, get_settings, reload_settings


class TestBaseConfig:
    """Test base configuration."""

    def test_environment_detection(self):
        """Test environment detection."""
        config = BaseConfig(environment="development")
        assert config.is_development()
        assert not config.is_production()
        assert not config.is_test()

    def test_environment_validation(self):
        """Test environment validation."""
        with pytest.raises(ValueError):
            BaseConfig(environment="invalid")

    def test_path_creation(self):
        """Test path creation."""
        config = BaseConfig()
        assert config.data_dir.exists()
        assert config.logs_dir.exists()


class TestDatabaseConfig:
    """Test database configuration."""

    def test_sqlite_detection(self):
        """Test SQLite detection."""
        config = DatabaseConfig(database_url="sqlite:///./data/test.db")
        assert config.is_sqlite()
        assert not config.is_postgresql()

    def test_postgresql_detection(self):
        """Test PostgreSQL detection."""
        config = DatabaseConfig(database_url="postgresql://user:pass@localhost/db")
        assert config.is_postgresql()
        assert not config.is_sqlite()

    def test_invalid_database_url(self):
        """Test invalid database URL."""
        with pytest.raises(ValueError):
            DatabaseConfig(database_url="invalid://url")

    def test_audit_hmac_production_requirement(self):
        """Test audit HMAC secret requirement in production."""
        with pytest.raises(ValueError):
            DatabaseConfig(
                environment="production",
                database_url="postgresql://user:pass@localhost/db",
                audit_hmac_secret=None,
            )


class TestCacheConfig:
    """Test cache configuration."""

    def test_redis_url_validation(self):
        """Test Redis URL validation."""
        config = CacheConfig(redis_url="redis://localhost:6379/0")
        assert config.has_redis()

    def test_invalid_redis_url(self):
        """Test invalid Redis URL."""
        with pytest.raises(ValueError):
            CacheConfig(redis_url="invalid://localhost")

    def test_cache_ttl_validation(self):
        """Test cache TTL validation."""
        config = CacheConfig(
            cache_ttl_short=300,
            cache_ttl_default=3600,
            cache_ttl_long=86400,
        )
        assert config.cache_ttl_short < config.cache_ttl_default
        assert config.cache_ttl_default < config.cache_ttl_long


class TestSecurityConfig:
    """Test security configuration."""

    def test_jwt_secret_length(self):
        """Test JWT secret length requirement."""
        with pytest.raises(ValueError):
            SecurityConfig(jwt_secret="short")

    def test_encryption_key_length(self):
        """Test encryption key length requirement."""
        with pytest.raises(ValueError):
            SecurityConfig(encryption_key="short")

    def test_production_secret_validation(self):
        """Test production secret validation."""
        with pytest.raises(ValueError):
            SecurityConfig(
                environment="production",
                jwt_secret="change-this-to-a-random-64-char-string",
            )

    def test_cors_origins_validation(self):
        """Test CORS origins validation."""
        config = SecurityConfig(
            cors_origins="http://localhost:3000,http://localhost:8000"
        )
        origins = config.get_cors_origins_list()
        assert len(origins) == 2

    def test_cors_wildcard_production_rejection(self):
        """Test CORS wildcard rejection in production."""
        with pytest.raises(ValueError):
            SecurityConfig(
                environment="production",
                cors_origins="*",
                require_https=True,
                jwt_secret="a" * 64,
                encryption_key="b" * 64,
            )


class TestObservabilityConfig:
    """Test observability configuration."""

    def test_log_level_validation(self):
        """Test log level validation."""
        config = ObservabilityConfig(log_level="INFO")
        assert config.log_level.value == "INFO"

    def test_sample_rate_validation(self):
        """Test sample rate validation."""
        with pytest.raises(ValueError):
            ObservabilityConfig(trace_sample_rate=1.5)

    def test_langfuse_validation(self):
        """Test Langfuse configuration validation."""
        with pytest.raises(ValueError):
            ObservabilityConfig(
                langfuse_enabled=True,
                langfuse_public_key=None,
            )

    def test_sentry_validation(self):
        """Test Sentry configuration validation."""
        with pytest.raises(ValueError):
            ObservabilityConfig(
                sentry_enabled=True,
                sentry_dsn=None,
            )


class TestConfigValidator:
    """Test configuration validator."""

    def test_validate_all_development(self):
        """Test validation for development environment."""
        validator = ConfigValidator()
        base_config = BaseConfig(environment="development")
        database_config = DatabaseConfig()
        cache_config = CacheConfig()
        security_config = SecurityConfig()
        observability_config = ObservabilityConfig()

        result = validator.validate_all(
            base_config,
            database_config,
            cache_config,
            security_config,
            observability_config,
        )
        assert result is True

    def test_validate_all_production_failure(self):
        """Test validation failure for production without proper config."""
        validator = ConfigValidator()
        base_config = BaseConfig(environment="production")
        database_config = DatabaseConfig(
            environment="production",
            database_url="postgresql://user:pass@localhost/db",
            audit_hmac_secret="secret",
        )
        cache_config = CacheConfig()
        security_config = SecurityConfig(
            environment="production",
            jwt_secret="a" * 64,
            encryption_key="b" * 64,
            require_https=True,
        )
        observability_config = ObservabilityConfig()

        with pytest.raises(ConfigValidationError):
            validator.validate_all(
                base_config,
                database_config,
                cache_config,
                security_config,
                observability_config,
            )


class TestConfigEncryption:
    """Test configuration encryption."""

    def test_encrypt_decrypt(self):
        """Test encryption and decryption."""
        encryption = ConfigEncryption("a" * 32)
        original = "sensitive-data"
        encrypted = encryption.encrypt(original)
        decrypted = encryption.decrypt(encrypted)
        assert decrypted == original

    def test_invalid_key_length(self):
        """Test invalid key length."""
        with pytest.raises(EncryptionError):
            ConfigEncryption("short")

    def test_encrypt_dict(self):
        """Test dictionary encryption."""
        encryption = ConfigEncryption("a" * 32)
        data = {"api_key": "secret", "public": "value"}
        encrypted = encryption.encrypt_dict(data, ["api_key"])
        assert encrypted["api_key"] != "secret"
        assert encrypted["public"] == "value"

    def test_decrypt_dict(self):
        """Test dictionary decryption."""
        encryption = ConfigEncryption("a" * 32)
        data = {"api_key": "secret", "public": "value"}
        encrypted = encryption.encrypt_dict(data, ["api_key"])
        decrypted = encryption.decrypt_dict(encrypted, ["api_key"])
        assert decrypted["api_key"] == "secret"
        assert decrypted["public"] == "value"


class TestSettings:
    """Test unified settings."""

    def test_get_settings(self):
        """Test getting settings."""
        settings = get_settings()
        assert settings is not None
        assert settings.app_name == "X-Agent"

    def test_settings_caching(self):
        """Test settings caching."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_reload_settings(self):
        """Test reloading settings."""
        settings1 = get_settings()
        settings2 = reload_settings()
        assert settings1 is not settings2

    def test_get_config_sections(self):
        """Test getting configuration sections."""
        settings = get_settings()
        db_config = settings.get_database_config()
        cache_config = settings.get_cache_config()
        security_config = settings.get_security_config()
        observability_config = settings.get_observability_config()

        assert isinstance(db_config, DatabaseConfig)
        assert isinstance(cache_config, CacheConfig)
        assert isinstance(security_config, SecurityConfig)
        assert isinstance(observability_config, ObservabilityConfig)

    def test_llm_backend_validation(self):
        """Test LLM backend validation."""
        with pytest.raises(ValueError):
            Settings(llm_backend="invalid")

    def test_memory_backend_validation(self):
        """Test memory backend validation."""
        with pytest.raises(ValueError):
            Settings(memory_backend="invalid")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
