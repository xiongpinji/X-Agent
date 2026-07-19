"""
X-Agent Local Endpoint Package

Provides local data management, encryption, and synchronization capabilities.
"""

from backend.local.config import LocalConfig, ConfigManager, load_default_config
from backend.local.database import DatabaseConfig, LocalDatabase
from backend.local.encryption import (
    EncryptionConfig,
    EncryptionManager,
    SensitiveDataClassifier,
    EncryptedDataStore,
    KeyRotationManager,
)
from backend.local.sync_client import (
    SyncClient,
    SyncOperation,
    SyncConflict,
    SyncBatch,
    SyncDirection,
    ConflictResolutionStrategy,
    ConflictResolver,
)

__version__ = "1.0.0"
__all__ = [
    # Config
    "LocalConfig",
    "ConfigManager",
    "load_default_config",
    # Database
    "DatabaseConfig",
    "LocalDatabase",
    # Encryption
    "EncryptionConfig",
    "EncryptionManager",
    "SensitiveDataClassifier",
    "EncryptedDataStore",
    "KeyRotationManager",
    # Sync
    "SyncClient",
    "SyncOperation",
    "SyncConflict",
    "SyncBatch",
    "SyncDirection",
    "ConflictResolutionStrategy",
    "ConflictResolver",
]
