"""
X-Agent Local Endpoint Package

Provides local data management, encryption, and synchronization capabilities.
"""

from backend.local.config import ConfigManager, LocalConfig, load_default_config
from backend.local.database import DatabaseConfig, LocalDatabase
from backend.local.encryption import (
    EncryptedDataStore,
    EncryptionConfig,
    EncryptionManager,
    KeyRotationManager,
    SensitiveDataClassifier,
)
from backend.local.sync_client import (
    ConflictResolutionStrategy,
    ConflictResolver,
    SyncBatch,
    SyncClient,
    SyncConflict,
    SyncDirection,
    SyncOperation,
)

__version__ = "1.0.0"
__all__ = [
    "ConfigManager",
    "ConflictResolutionStrategy",
    "ConflictResolver",
    # Database
    "DatabaseConfig",
    "EncryptedDataStore",
    # Encryption
    "EncryptionConfig",
    "EncryptionManager",
    "KeyRotationManager",
    # Config
    "LocalConfig",
    "LocalDatabase",
    "SensitiveDataClassifier",
    "SyncBatch",
    # Sync
    "SyncClient",
    "SyncConflict",
    "SyncDirection",
    "SyncOperation",
    "load_default_config",
]
