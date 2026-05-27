"""Configuration management system for X-Agent.

This module provides a comprehensive configuration management system with:
- Environment isolation (dev/test/prod)
- Configuration validation and type checking
- Sensitive configuration encryption
- Dynamic configuration updates
- Configuration hot-reload support
"""

from .base import BaseConfig, Environment
from .database import DatabaseConfig
from .cache import CacheConfig
from .security import SecurityConfig
from .observability import ObservabilityConfig
from .settings import Settings, get_settings

__all__ = [
    "BaseConfig",
    "Environment",
    "DatabaseConfig",
    "CacheConfig",
    "SecurityConfig",
    "ObservabilityConfig",
    "Settings",
    "get_settings",
]
