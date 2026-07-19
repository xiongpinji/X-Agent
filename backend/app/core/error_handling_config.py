"""
Error Handling Configuration Examples

This file provides practical configuration examples for different scenarios.
"""

from backend.app.core.circuit_breaker import CircuitBreakerConfig
from backend.app.core.retry import RetryConfig


# ============================================================================
# RETRY CONFIGURATIONS
# ============================================================================

# Configuration for transient network failures
TRANSIENT_FAILURE_RETRY = RetryConfig(
    max_attempts=3,
    initial_delay=1.0,
    max_delay=10.0,
    exponential_base=2.0,
    jitter=True,
    jitter_range=(0.5, 1.5),
    timeout=30.0,
)

# Configuration for rate-limited APIs
RATE_LIMITED_API_RETRY = RetryConfig(
    max_attempts=5,
    initial_delay=2.0,
    max_delay=60.0,
    exponential_base=2.0,
    jitter=True,
    jitter_range=(0.8, 1.2),
    timeout=300.0,
)

# Configuration for database operations
DATABASE_OPERATION_RETRY = RetryConfig(
    max_attempts=3,
    initial_delay=0.1,
    max_delay=1.0,
    exponential_base=2.0,
    jitter=False,
    timeout=5.0,
)

# Configuration for LLM API calls
LLM_API_RETRY = RetryConfig(
    max_attempts=3,
    initial_delay=1.0,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True,
    jitter_range=(0.5, 1.5),
    timeout=60.0,
)

# Configuration for external service calls
EXTERNAL_SERVICE_RETRY = RetryConfig(
    max_attempts=4,
    initial_delay=0.5,
    max_delay=20.0,
    exponential_base=2.0,
    jitter=True,
    jitter_range=(0.6, 1.4),
    timeout=45.0,
)

# Configuration for quick retries (cache, memory)
QUICK_RETRY = RetryConfig(
    max_attempts=2,
    initial_delay=0.05,
    max_delay=0.5,
    exponential_base=2.0,
    jitter=False,
    timeout=2.0,
)

# Configuration for aggressive retries (critical operations)
AGGRESSIVE_RETRY = RetryConfig(
    max_attempts=5,
    initial_delay=0.5,
    max_delay=30.0,
    exponential_base=1.5,
    jitter=True,
    jitter_range=(0.7, 1.3),
    timeout=120.0,
)


# ============================================================================
# CIRCUIT BREAKER CONFIGURATIONS
# ============================================================================

# Configuration for external APIs
EXTERNAL_API_CIRCUIT_BREAKER = CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=60.0,
    success_threshold=2,
    half_open_max_calls=1,
)

# Configuration for database connections
DATABASE_CIRCUIT_BREAKER = CircuitBreakerConfig(
    failure_threshold=3,
    recovery_timeout=30.0,
    success_threshold=1,
    half_open_max_calls=1,
)

# Configuration for cache services
CACHE_CIRCUIT_BREAKER = CircuitBreakerConfig(
    failure_threshold=10,
    recovery_timeout=120.0,
    success_threshold=3,
    half_open_max_calls=2,
)

# Configuration for LLM services
LLM_SERVICE_CIRCUIT_BREAKER = CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=60.0,
    success_threshold=2,
    half_open_max_calls=1,
)

# Configuration for memory services
MEMORY_SERVICE_CIRCUIT_BREAKER = CircuitBreakerConfig(
    failure_threshold=8,
    recovery_timeout=45.0,
    success_threshold=2,
    half_open_max_calls=2,
)

# Configuration for search services
SEARCH_SERVICE_CIRCUIT_BREAKER = CircuitBreakerConfig(
    failure_threshold=10,
    recovery_timeout=90.0,
    success_threshold=3,
    half_open_max_calls=2,
)

# Configuration for sensitive services (strict)
SENSITIVE_SERVICE_CIRCUIT_BREAKER = CircuitBreakerConfig(
    failure_threshold=2,
    recovery_timeout=120.0,
    success_threshold=1,
    half_open_max_calls=1,
)

# Configuration for resilient services (lenient)
RESILIENT_SERVICE_CIRCUIT_BREAKER = CircuitBreakerConfig(
    failure_threshold=15,
    recovery_timeout=30.0,
    success_threshold=5,
    half_open_max_calls=3,
)


# ============================================================================
# COMBINED CONFIGURATIONS FOR COMMON SCENARIOS
# ============================================================================

class ServiceConfigurations:
    """Pre-configured settings for common services."""

    # LLM Service Configuration
    LLM_SERVICE = {
        "retry": LLM_API_RETRY,
        "circuit_breaker": LLM_SERVICE_CIRCUIT_BREAKER,
        "enable_degradation": True,
        "cache_ttl": 300,
    }

    # Database Service Configuration
    DATABASE_SERVICE = {
        "retry": DATABASE_OPERATION_RETRY,
        "circuit_breaker": DATABASE_CIRCUIT_BREAKER,
        "enable_degradation": False,
        "cache_ttl": 0,
    }

    # Cache Service Configuration
    CACHE_SERVICE = {
        "retry": QUICK_RETRY,
        "circuit_breaker": CACHE_CIRCUIT_BREAKER,
        "enable_degradation": True,
        "cache_ttl": 60,
    }

    # Memory Service Configuration
    MEMORY_SERVICE = {
        "retry": TRANSIENT_FAILURE_RETRY,
        "circuit_breaker": MEMORY_SERVICE_CIRCUIT_BREAKER,
        "enable_degradation": True,
        "cache_ttl": 300,
    }

    # Search Service Configuration
    SEARCH_SERVICE = {
        "retry": EXTERNAL_SERVICE_RETRY,
        "circuit_breaker": SEARCH_SERVICE_CIRCUIT_BREAKER,
        "enable_degradation": True,
        "cache_ttl": 600,
    }

    # External API Configuration
    EXTERNAL_API = {
        "retry": RATE_LIMITED_API_RETRY,
        "circuit_breaker": EXTERNAL_API_CIRCUIT_BREAKER,
        "enable_degradation": True,
        "cache_ttl": 300,
    }


# ============================================================================
# ENVIRONMENT-SPECIFIC CONFIGURATIONS
# ============================================================================

class EnvironmentConfigurations:
    """Environment-specific error handling configurations."""

    # Development environment - lenient, verbose logging
    DEVELOPMENT = {
        "retry": RetryConfig(
            max_attempts=2,
            initial_delay=0.1,
            max_delay=1.0,
            exponential_base=2.0,
            jitter=False,
            timeout=10.0,
        ),
        "circuit_breaker": CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=10.0,
            success_threshold=1,
        ),
        "enable_monitoring": True,
        "log_level": "DEBUG",
    }

    # Staging environment - balanced
    STAGING = {
        "retry": RetryConfig(
            max_attempts=3,
            initial_delay=0.5,
            max_delay=10.0,
            exponential_base=2.0,
            jitter=True,
            timeout=30.0,
        ),
        "circuit_breaker": CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=60.0,
            success_threshold=2,
        ),
        "enable_monitoring": True,
        "log_level": "INFO",
    }

    # Production environment - strict, resilient
    PRODUCTION = {
        "retry": RetryConfig(
            max_attempts=4,
            initial_delay=1.0,
            max_delay=30.0,
            exponential_base=2.0,
            jitter=True,
            timeout=60.0,
        ),
        "circuit_breaker": CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=120.0,
            success_threshold=3,
        ),
        "enable_monitoring": True,
        "enable_alerting": True,
        "log_level": "WARNING",
    }


# ============================================================================
# FEATURE FLAG CONFIGURATIONS
# ============================================================================

class FeatureFlagConfigurations:
    """Feature flag configurations for graceful degradation."""

    # Default feature flags
    DEFAULT_FLAGS = {
        "advanced_search": True,
        "memory_fusion": True,
        "agent_collaboration": True,
        "real_time_updates": True,
        "analytics": True,
    }

    # Degraded mode feature flags (reduced functionality)
    DEGRADED_FLAGS = {
        "advanced_search": False,
        "memory_fusion": False,
        "agent_collaboration": False,
        "real_time_updates": False,
        "analytics": False,
    }

    # Minimal mode feature flags (basic functionality only)
    MINIMAL_FLAGS = {
        "advanced_search": False,
        "memory_fusion": False,
        "agent_collaboration": False,
        "real_time_updates": False,
        "analytics": False,
    }


# ============================================================================
# DEGRADATION LEVEL CONFIGURATIONS
# ============================================================================

class DegradationLevelConfigurations:
    """Degradation level configurations."""

    # Full service - all features available
    FULL_SERVICE = {
        "level": "full_service",
        "cache_ttl": 300,
        "use_cache": True,
        "use_defaults": False,
    }

    # Reduced features - some features disabled
    REDUCED_FEATURES = {
        "level": "reduced_features",
        "cache_ttl": 600,
        "use_cache": True,
        "use_defaults": True,
    }

    # Basic features - only core functionality
    BASIC_FEATURES = {
        "level": "basic_features",
        "cache_ttl": 1200,
        "use_cache": True,
        "use_defaults": True,
    }

    # Minimal service - emergency mode
    MINIMAL_SERVICE = {
        "level": "minimal_service",
        "cache_ttl": 3600,
        "use_cache": True,
        "use_defaults": True,
    }

    # Unavailable - service down
    UNAVAILABLE = {
        "level": "unavailable",
        "cache_ttl": 0,
        "use_cache": False,
        "use_defaults": False,
    }


# ============================================================================
# MONITORING ALERT THRESHOLDS
# ============================================================================

class MonitoringThresholds:
    """Monitoring alert thresholds."""

    # Error rate thresholds (errors per second)
    ERROR_RATE_THRESHOLDS = {
        "warning": 0.01,      # 1% error rate
        "critical": 0.05,     # 5% error rate
    }

    # Circuit breaker thresholds
    CIRCUIT_BREAKER_THRESHOLDS = {
        "open_duration_warning": 300,      # 5 minutes
        "open_duration_critical": 600,     # 10 minutes
    }

    # Retry success rate thresholds
    RETRY_SUCCESS_RATE_THRESHOLDS = {
        "warning": 0.5,       # 50% success rate
        "critical": 0.2,      # 20% success rate
    }

    # Degradation thresholds
    DEGRADATION_THRESHOLDS = {
        "duration_warning": 300,           # 5 minutes
        "duration_critical": 600,          # 10 minutes
    }

    # Response time thresholds (milliseconds)
    RESPONSE_TIME_THRESHOLDS = {
        "warning": 1000,      # 1 second
        "critical": 5000,     # 5 seconds
    }


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

"""
Example 1: Using pre-configured service settings

from backend.app.core.error_handling_config import ServiceConfigurations

config = ServiceConfigurations.LLM_SERVICE
retry_config = config["retry"]
circuit_breaker_config = config["circuit_breaker"]


Example 2: Using environment-specific settings

import os
from backend.app.core.error_handling_config import EnvironmentConfigurations

env = os.getenv("ENVIRONMENT", "development")
env_config = getattr(EnvironmentConfigurations, env.upper())


Example 3: Creating custom configuration

from backend.app.core.retry import RetryConfig
from backend.app.core.circuit_breaker import CircuitBreakerConfig

custom_retry = RetryConfig(
    max_attempts=5,
    initial_delay=0.5,
    max_delay=20.0,
)

custom_breaker = CircuitBreakerConfig(
    failure_threshold=10,
    recovery_timeout=120.0,
)
"""
