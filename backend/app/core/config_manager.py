"""Configuration management for X-Agent production environment."""

import json
import logging
import os
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class Environment(StrEnum):
    """Deployment environments."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class DatabaseConfig:
    """Database configuration."""
    host: str
    port: int = 5432
    user: str = "xagent"
    password: str = ""
    database: str = "xagent"
    pool_size: int = 20
    max_overflow: int = 10
    ssl_mode: str = "prefer"

    @property
    def url(self) -> str:
        """Generate database URL."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class RedisConfig:
    """Redis configuration."""
    host: str
    port: int = 6379
    password: str | None = None
    db: int = 0
    ssl: bool = False

    @property
    def url(self) -> str:
        """Generate Redis URL."""
        protocol = "rediss" if self.ssl else "redis"
        auth = f":{self.password}@" if self.password else ""
        return f"{protocol}://{auth}{self.host}:{self.port}/{self.db}"


@dataclass
class QdrantConfig:
    """Qdrant configuration."""
    url: str
    api_key: str | None = None
    timeout: int = 30


@dataclass
class LLMConfig:
    """LLM configuration."""
    provider: str = "openai"
    api_key: str = ""
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 2000
    timeout: int = 30


@dataclass
class SecurityConfig:
    """Security configuration."""
    jwt_secret: str
    api_key_salt: str
    cors_origins: list
    require_https: bool = True
    require_api_key: bool = True
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 1000
    rate_limit_window: int = 60


@dataclass
class MonitoringConfig:
    """Monitoring configuration."""
    prometheus_enabled: bool = True
    prometheus_port: int = 9090
    langfuse_enabled: bool = True
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    jaeger_enabled: bool = True
    jaeger_host: str = "localhost"
    jaeger_port: int = 6831


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    format: str = "json"
    file: str | None = None
    max_size_mb: int = 100
    backup_count: int = 10
    mask_sensitive: bool = True


@dataclass
class AppConfig:
    """Main application configuration."""
    environment: Environment
    app_name: str = "X-Agent"
    version: str = "0.1.0"
    debug: bool = False

    database: DatabaseConfig = None
    redis: RedisConfig = None
    qdrant: QdrantConfig = None
    llm: LLMConfig = None
    security: SecurityConfig = None
    monitoring: MonitoringConfig = None
    logging: LoggingConfig = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON."""
        return json.dumps(self.to_dict(), indent=2)

    def to_yaml(self) -> str:
        """Convert to YAML."""
        return yaml.dump(self.to_dict(), default_flow_style=False)

    @classmethod
    def from_env(cls, environment: Environment) -> 'AppConfig':
        """Load configuration from environment variables."""

        db_config = DatabaseConfig(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 5432)),
            user=os.getenv('DB_USER', 'xagent'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'xagent'),
            pool_size=int(os.getenv('DB_POOL_SIZE', 20)),
            max_overflow=int(os.getenv('DB_MAX_OVERFLOW', 10)),
        )

        redis_config = RedisConfig(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            password=os.getenv('REDIS_PASSWORD'),
            db=int(os.getenv('REDIS_DB', 0)),
        )

        qdrant_config = QdrantConfig(
            url=os.getenv('QDRANT_URL', 'http://localhost:6333'),
            api_key=os.getenv('QDRANT_API_KEY'),
        )

        llm_config = LLMConfig(
            provider=os.getenv('LLM_PROVIDER', 'openai'),
            api_key=os.getenv('LLM_API_KEY', ''),
            model=os.getenv('LLM_MODEL', 'gpt-4'),
        )

        security_config = SecurityConfig(
            jwt_secret=os.getenv('JWT_SECRET', ''),
            api_key_salt=os.getenv('API_KEY_SALT', ''),
            cors_origins=os.getenv('CORS_ORIGINS', 'http://localhost:3000').split(','),
            require_https=os.getenv('REQUIRE_HTTPS', 'true').lower() == 'true',
            require_api_key=os.getenv('REQUIRE_API_KEY', 'true').lower() == 'true',
        )

        monitoring_config = MonitoringConfig(
            prometheus_enabled=os.getenv('PROMETHEUS_ENABLED', 'true').lower() == 'true',
            langfuse_enabled=os.getenv('LANGFUSE_ENABLED', 'true').lower() == 'true',
            langfuse_public_key=os.getenv('LANGFUSE_PUBLIC_KEY', ''),
            langfuse_secret_key=os.getenv('LANGFUSE_SECRET_KEY', ''),
        )

        logging_config = LoggingConfig(
            level=os.getenv('LOG_LEVEL', 'INFO'),
            format=os.getenv('LOG_FORMAT', 'json'),
            file=os.getenv('LOG_FILE'),
        )

        return cls(
            environment=environment,
            app_name=os.getenv('APP_NAME', 'X-Agent'),
            version=os.getenv('APP_VERSION', '0.1.0'),
            debug=os.getenv('DEBUG', 'false').lower() == 'true',
            database=db_config,
            redis=redis_config,
            qdrant=qdrant_config,
            llm=llm_config,
            security=security_config,
            monitoring=monitoring_config,
            logging=logging_config,
        )

    @classmethod
    def from_file(cls, config_file: str) -> 'AppConfig':
        """Load configuration from file."""
        path = Path(config_file)

        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_file}")

        with open(path) as f:
            if config_file.endswith('.json'):
                data = json.load(f)
            elif config_file.endswith('.yaml') or config_file.endswith('.yml'):
                data = yaml.safe_load(f)
            else:
                raise ValueError(f"Unsupported config file format: {config_file}")

        # Parse configuration
        environment = Environment(data.get('environment', 'production'))

        db_data = data.get('database', {})
        db_config = DatabaseConfig(**db_data)

        redis_data = data.get('redis', {})
        redis_config = RedisConfig(**redis_data)

        qdrant_data = data.get('qdrant', {})
        qdrant_config = QdrantConfig(**qdrant_data)

        llm_data = data.get('llm', {})
        llm_config = LLMConfig(**llm_data)

        security_data = data.get('security', {})
        security_config = SecurityConfig(**security_data)

        monitoring_data = data.get('monitoring', {})
        monitoring_config = MonitoringConfig(**monitoring_data)

        logging_data = data.get('logging', {})
        logging_config = LoggingConfig(**logging_data)

        return cls(
            environment=environment,
            app_name=data.get('app_name', 'X-Agent'),
            version=data.get('version', '0.1.0'),
            debug=data.get('debug', False),
            database=db_config,
            redis=redis_config,
            qdrant=qdrant_config,
            llm=llm_config,
            security=security_config,
            monitoring=monitoring_config,
            logging=logging_config,
        )

    def validate(self) -> bool:
        """Validate configuration."""
        errors = []

        # Validate database
        if not self.database.host:
            errors.append("Database host is required")
        if not self.database.password and self.environment == Environment.PRODUCTION:
            errors.append("Database password is required in production")

        # Validate security
        if not self.security.jwt_secret or len(self.security.jwt_secret) < 32:
            errors.append("JWT secret must be at least 32 characters")
        if not self.security.api_key_salt or len(self.security.api_key_salt) < 16:
            errors.append("API key salt must be at least 16 characters")

        # Validate LLM
        if not self.llm.api_key and self.environment == Environment.PRODUCTION:
            errors.append("LLM API key is required in production")

        if errors:
            for error in errors:
                logger.error(f"Configuration validation error: {error}")
            return False

        logger.info("Configuration validation passed")
        return True


class ConfigManager:
    """Manages application configuration."""

    _instance: AppConfig | None = None

    @classmethod
    def initialize(cls, config_file: str | None = None, environment: Environment | None = None) -> AppConfig:
        """Initialize configuration manager."""

        if config_file:
            cls._instance = AppConfig.from_file(config_file)
        elif environment:
            cls._instance = AppConfig.from_env(environment)
        else:
            env = os.getenv('APP_MODE', 'production')
            cls._instance = AppConfig.from_env(Environment(env))

        if not cls._instance.validate():
            raise ValueError("Configuration validation failed")

        return cls._instance

    @classmethod
    def get(cls) -> AppConfig:
        """Get current configuration."""
        if cls._instance is None:
            cls.initialize()
        return cls._instance

    @classmethod
    def reload(cls, config_file: str | None = None) -> AppConfig:
        """Reload configuration."""
        cls._instance = None
        return cls.initialize(config_file)


# Global configuration instance
def get_config() -> AppConfig:
    """Get application configuration."""
    return ConfigManager.get()
