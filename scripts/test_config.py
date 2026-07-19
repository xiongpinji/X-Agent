"""Test environment configuration for X-Agent."""

import os
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Test directories
TESTS_DIR = PROJECT_ROOT / "tests"
UNIT_TESTS_DIR = TESTS_DIR
INTEGRATION_TESTS_DIR = TESTS_DIR
E2E_TESTS_DIR = TESTS_DIR / "e2e"
RUNTIME_TESTS_DIR = TESTS_DIR / "runtime"
CONTRACT_TESTS_DIR = TESTS_DIR / "contracts"

# Report directories
REPORTS_DIR = PROJECT_ROOT / "test-reports"
COVERAGE_DIR = PROJECT_ROOT / "coverage-reports"

# Environment variables for testing
TEST_ENV_VARS = {
    "APP_MODE": "test",
    "XAGENT_AUDIT_HMAC_SECRET": "test-audit-secret-key-12345",
    "XAGENT_BOOTSTRAP_API_KEY": "bootstrap-test-key",
    "DATABASE_URL": "postgresql://test:test@localhost:5432/xagent_test",
    "REDIS_URL": "redis://localhost:6379/1",
    "QDRANT_URL": "http://localhost:6333",
    "LANGFUSE_PUBLIC_KEY": "test-public-key",
    "LANGFUSE_SECRET_KEY": "test-secret-key",
    "OPENAI_API_KEY": "sk-test-key",
    "LOG_LEVEL": "DEBUG",
    "ENABLE_TRACING": "true",
    "ENABLE_METRICS": "true",
}

# Test database configuration
TEST_DB_CONFIG = {
    "host": os.getenv("TEST_DB_HOST", "localhost"),
    "port": int(os.getenv("TEST_DB_PORT", "5432")),
    "user": os.getenv("TEST_DB_USER", "test"),
    "password": os.getenv("TEST_DB_PASSWORD", "test"),
    "database": os.getenv("TEST_DB_NAME", "xagent_test"),
}

# Test Redis configuration
TEST_REDIS_CONFIG = {
    "host": os.getenv("TEST_REDIS_HOST", "localhost"),
    "port": int(os.getenv("TEST_REDIS_PORT", "6379")),
    "db": int(os.getenv("TEST_REDIS_DB", "1")),
}

# Test Qdrant configuration
TEST_QDRANT_CONFIG = {
    "url": os.getenv("TEST_QDRANT_URL", "http://localhost:6333"),
    "api_key": os.getenv("TEST_QDRANT_API_KEY", None),
}

# Test categories
TEST_CATEGORIES = {
    "unit": {
        "description": "Unit tests for individual components",
        "timeout": 300,
        "parallel": True,
        "markers": ["not e2e", "not integration"],
    },
    "integration": {
        "description": "Integration tests for component interactions",
        "timeout": 600,
        "parallel": False,
        "markers": ["integration", "not e2e"],
    },
    "contracts": {
        "description": "Contract tests for API validation",
        "timeout": 300,
        "parallel": True,
        "markers": ["contracts"],
    },
    "runtime": {
        "description": "Runtime behavior tests",
        "timeout": 300,
        "parallel": False,
        "markers": ["runtime"],
    },
    "e2e": {
        "description": "End-to-end workflow tests",
        "timeout": 900,
        "parallel": False,
        "markers": ["e2e"],
    },
}

# Coverage configuration
COVERAGE_CONFIG = {
    "source": ["backend", "data", "scripts"],
    "omit": [
        "*/tests/*",
        "*/test_*.py",
        "*/__pycache__/*",
        "*/site-packages/*",
    ],
    "targets": {
        "backend/app": 0.85,
        "backend/core": 0.90,
        "data": 0.80,
        "scripts": 0.75,
    },
    "fail_under": 0.70,
}

# Pytest configuration
PYTEST_CONFIG = {
    "asyncio_mode": "auto",
    "asyncio_default_fixture_loop_scope": "function",
    "asyncio_default_test_loop_scope": "function",
    "testpaths": ["tests"],
    "pythonpath": ["."],
    "markers": [
        "e2e: end-to-end contract tests",
        "runtime: runtime shape and helper tests",
        "contracts: import and interface contract tests",
        "integration: integration tests",
        "unit: unit tests",
        "slow: slow running tests",
        "requires_db: tests requiring database",
        "requires_redis: tests requiring Redis",
        "requires_qdrant: tests requiring Qdrant",
    ],
    "addopts": [
        "--strict-markers",
        "--tb=short",
        "--disable-warnings",
    ],
}

# Test data configuration
TEST_DATA_CONFIG = {
    "fixtures_dir": TESTS_DIR / "fixtures",
    "mock_data_dir": TESTS_DIR / "mock_data",
    "temp_dir": PROJECT_ROOT / ".test_temp",
}

# Mock service configuration
MOCK_SERVICES = {
    "openai": {
        "enabled": True,
        "base_url": "http://localhost:8001",
        "api_key": "test-key",
    },
    "langfuse": {
        "enabled": True,
        "base_url": "http://localhost:8002",
        "public_key": "test-public",
        "secret_key": "test-secret",
    },
    "qdrant": {
        "enabled": True,
        "url": "http://localhost:6333",
    },
}

# Performance thresholds
PERFORMANCE_THRESHOLDS = {
    "unit_test_timeout": 5,  # seconds
    "integration_test_timeout": 30,  # seconds
    "e2e_test_timeout": 60,  # seconds
    "api_response_time": 1.0,  # seconds
    "database_query_time": 0.5,  # seconds
}

# Retry configuration
RETRY_CONFIG = {
    "max_retries": 3,
    "retry_delay": 1,  # seconds
    "backoff_factor": 2,
}

# Logging configuration
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        },
        "detailed": {
            "format": "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s"
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "standard",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.FileHandler",
            "level": "DEBUG",
            "formatter": "detailed",
            "filename": "test-reports/test.log",
        },
    },
    "root": {
        "level": "DEBUG",
        "handlers": ["console", "file"],
    },
}


def setup_test_environment():
    """Set up test environment variables."""
    for key, value in TEST_ENV_VARS.items():
        os.environ.setdefault(key, value)

    # Create necessary directories
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    COVERAGE_DIR.mkdir(parents=True, exist_ok=True)
    TEST_DATA_CONFIG["temp_dir"].mkdir(parents=True, exist_ok=True)


def get_test_config(category: str) -> dict:
    """Get configuration for a specific test category."""
    return TEST_CATEGORIES.get(category, {})


def get_coverage_target(module: str) -> float:
    """Get coverage target for a specific module."""
    return COVERAGE_CONFIG["targets"].get(module, COVERAGE_CONFIG["fail_under"])
