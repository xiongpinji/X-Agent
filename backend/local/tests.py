"""
X-Agent Local Endpoint Tests

Comprehensive test suite for local database, sync, encryption, and configuration.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from backend.local.config import ConfigManager, LocalConfig
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
    SyncClient,
    SyncConflict,
)

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def temp_db_path():
    """Create temporary database path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test.db"


@pytest.fixture
def db_config(temp_db_path):
    """Create database configuration."""
    return DatabaseConfig(db_path=temp_db_path)


@pytest.fixture
def local_db(db_config):
    """Create local database instance."""
    db = LocalDatabase(db_config)
    db.initialize()
    yield db
    db.close()


@pytest.fixture
def encryption_config():
    """Create encryption configuration."""
    return EncryptionConfig()


@pytest.fixture
def encryption_manager(encryption_config):
    """Create encryption manager."""
    manager = EncryptionManager(encryption_config)
    manager.generate_master_key()
    return manager


@pytest.fixture
def local_config():
    """Create local configuration."""
    return LocalConfig()


# ============================================================================
# DATABASE TESTS
# ============================================================================

class TestLocalDatabase:
    """Test local database operations."""

    def test_database_initialization(self, local_db):
        """Test database initialization."""
        assert local_db._initialized
        assert local_db.config.db_path.exists()

    def test_set_and_get_metadata(self, local_db):
        """Test metadata operations."""
        metadata_id = local_db.set_metadata(
            entity_type="memory",
            entity_id="test-123",
            local_version=1,
            cloud_version=0,
            checksum="abc123",
        )

        assert metadata_id is not None

        metadata = local_db.get_metadata("memory", "test-123")
        assert metadata is not None
        assert metadata["entity_type"] == "memory"
        assert metadata["entity_id"] == "test-123"
        assert metadata["local_version"] == 1

    def test_sync_state_operations(self, local_db):
        """Test sync state operations."""
        local_db.update_sync_state(
            entity_type="workflow",
            entity_id="wf-123",
            state="synced",
        )

        state = local_db.get_sync_state("workflow", "wf-123")
        assert state is not None
        assert state["state"] == "synced"

    def test_conflict_logging(self, local_db):
        """Test conflict logging."""
        conflict_id = local_db.log_conflict(
            entity_type="memory",
            entity_id="mem-123",
            conflict_type="UPDATE_CONFLICT",
            local_data={"content": "local"},
            cloud_data={"content": "cloud"},
            local_version=2,
            cloud_version=1,
        )

        assert conflict_id is not None

        conflicts = local_db.get_unresolved_conflicts()
        assert len(conflicts) > 0
        assert conflicts[0]["conflict_type"] == "UPDATE_CONFLICT"

    def test_conflict_resolution(self, local_db):
        """Test conflict resolution."""
        conflict_id = local_db.log_conflict(
            entity_type="memory",
            entity_id="mem-123",
            conflict_type="UPDATE_CONFLICT",
            local_data={"content": "local"},
            cloud_data={"content": "cloud"},
        )

        local_db.resolve_conflict(
            conflict_id=conflict_id,
            resolution_strategy="LAST_WRITE_WINS",
            resolved_data={"content": "resolved"},
            resolved_by="system",
        )

        conflicts = local_db.get_unresolved_conflicts()
        assert len(conflicts) == 0

    def test_sync_queue_operations(self, local_db):
        """Test sync queue operations."""
        queue_id = local_db.enqueue_sync(
            entity_type="memory",
            entity_id="mem-123",
            operation="UPDATE",
            data={"content": "test"},
            priority=1,
        )

        assert queue_id is not None

        pending = local_db.get_pending_syncs()
        assert len(pending) > 0
        assert pending[0]["entity_id"] == "mem-123"

        local_db.mark_sync_completed(queue_id, success=True)

        pending = local_db.get_pending_syncs()
        assert len(pending) == 0

    def test_offline_queue_operations(self, local_db):
        """Test offline queue operations."""
        queue_id = local_db.enqueue_offline(
            entity_type="workflow",
            entity_id="wf-123",
            operation="CREATE",
            data={"name": "test"},
            priority=0,
        )

        assert queue_id is not None

        offline_ops = local_db.get_offline_operations()
        assert len(offline_ops) > 0

        local_db.mark_offline_synced(queue_id)

        offline_ops = local_db.get_offline_operations()
        assert len(offline_ops) == 0

    def test_sync_history_recording(self, local_db):
        """Test sync history recording."""
        batch_id = "batch-123"

        local_db.record_sync_history(
            sync_batch_id=batch_id,
            entity_type="memory",
            entity_id="mem-123",
            operation="UPDATE",
            direction="upload",
            status="success",
            duration_ms=100,
        )

        history = local_db.get_sync_history()
        assert len(history) > 0
        assert history[0]["sync_batch_id"] == batch_id

    def test_cache_operations(self, local_db):
        """Test cache operations."""
        local_db.set_cache(
            entity_type="memory",
            entity_id="mem-123",
            cache_key="test-key",
            cache_value={"data": "test"},
            ttl_seconds=3600,
        )

        cached = local_db.get_cache("test-key")
        assert cached is not None

    def test_sync_statistics(self, local_db):
        """Test sync statistics."""
        local_db.enqueue_sync(
            entity_type="memory",
            entity_id="mem-123",
            operation="UPDATE",
            data={"content": "test"},
        )

        stats = local_db.get_sync_stats()
        assert stats["pending_syncs"] == 1
        assert stats["offline_operations"] == 0


# ============================================================================
# ENCRYPTION TESTS
# ============================================================================

class TestEncryption:
    """Test encryption operations."""

    def test_master_key_generation(self, encryption_manager):
        """Test master key generation."""
        key = encryption_manager.generate_master_key()
        assert len(key) == 32  # 256 bits

    def test_encrypt_decrypt_string(self, encryption_manager):
        """Test string encryption/decryption."""
        plaintext = "sensitive data"

        encrypted = encryption_manager.encrypt(plaintext)
        assert "encrypted_data" in encrypted
        assert "iv" in encrypted

        decrypted = encryption_manager.decrypt_to_string(
            encrypted["encrypted_data"],
            encrypted["iv"],
            encrypted["salt"],
        )

        assert decrypted == plaintext

    def test_encrypt_decrypt_dict(self, encryption_manager):
        """Test dictionary encryption/decryption."""
        plaintext = {"api_key": "secret123", "token": "abc"}

        encrypted = encryption_manager.encrypt(plaintext)

        decrypted = encryption_manager.decrypt_to_dict(
            encrypted["encrypted_data"],
            encrypted["iv"],
            encrypted["salt"],
        )

        assert decrypted == plaintext

    def test_password_key_derivation(self, encryption_manager):
        """Test password-based key derivation."""
        password = "mypassword"

        key1, salt = encryption_manager.derive_key_from_password(password)
        assert len(key1) == 32

        key2, _ = encryption_manager.derive_key_from_password(password, salt)
        assert key1 == key2

    def test_hash_operations(self, encryption_manager):
        """Test hash operations."""
        data = "test data"

        hash_value = encryption_manager.hash_data(data)
        assert len(hash_value) == 64  # SHA-256 hex

        assert encryption_manager.verify_hash(data, hash_value)
        assert not encryption_manager.verify_hash("other data", hash_value)

    def test_sensitive_data_classification(self):
        """Test sensitive data classification."""
        assert SensitiveDataClassifier.is_sensitive({"api_key": "secret"})
        assert SensitiveDataClassifier.is_sensitive({"password": "secret"})
        assert not SensitiveDataClassifier.is_sensitive({"name": "John"})

        sensitivity = SensitiveDataClassifier.classify({"api_key": "secret"})
        assert sensitivity == "secret"

    def test_encrypted_data_store(self, encryption_manager):
        """Test encrypted data store."""
        store = EncryptedDataStore(encryption_manager)

        data = {"api_key": "secret123"}

        stored = store.encrypt_and_store(
            data=data,
            entity_type="config",
            entity_id="cfg-123",
            data_type="api_key",
        )

        assert stored["is_encrypted"]
        assert stored["sensitivity"] == "secret"

        retrieved = store.decrypt_and_retrieve(stored)
        assert retrieved == data

    def test_key_rotation(self, encryption_manager):
        """Test key rotation."""
        rotation_manager = KeyRotationManager(encryption_manager)

        new_key = os.urandom(32)
        new_version = rotation_manager.rotate_key(new_key)

        assert new_version == 2
        assert rotation_manager.get_current_version() == 2
        assert rotation_manager.get_key_version(2) == new_key


# ============================================================================
# SYNC CLIENT TESTS
# ============================================================================

class TestSyncClient:
    """Test sync client operations."""

    @pytest.mark.asyncio
    async def test_enqueue_operation(self, local_db):
        """Test operation enqueueing."""
        mock_api = AsyncMock()
        sync_client = SyncClient(local_db, mock_api)

        queue_id = await sync_client.enqueue_operation(
            entity_type="memory",
            entity_id="mem-123",
            operation="UPDATE",
            data={"content": "test"},
            priority=1,
        )

        assert queue_id is not None

    @pytest.mark.asyncio
    async def test_offline_mode(self, local_db):
        """Test offline mode."""
        mock_api = AsyncMock()
        sync_client = SyncClient(local_db, mock_api)

        sync_client.set_offline_mode(True)
        assert sync_client._offline_mode

        await sync_client.enqueue_operation(
            entity_type="memory",
            entity_id="mem-123",
            operation="UPDATE",
            data={"content": "test"},
        )

        offline_ops = local_db.get_offline_operations()
        assert len(offline_ops) > 0

    @pytest.mark.asyncio
    async def test_sync_status(self, local_db):
        """Test sync status."""
        mock_api = AsyncMock()
        sync_client = SyncClient(local_db, mock_api)

        status = sync_client.get_sync_status()
        assert "is_syncing" in status
        assert "offline_mode" in status
        assert "pending_syncs" in status

    @pytest.mark.asyncio
    async def test_conflict_resolution_last_write_wins(self):
        """Test last-write-wins conflict resolution."""
        resolver = ConflictResolver()

        conflict = SyncConflict(
            entity_type="memory",
            entity_id="mem-123",
            conflict_type="UPDATE_CONFLICT",
            local_data={"content": "local", "updated_at": 100},
            cloud_data={"content": "cloud", "updated_at": 50},
        )

        resolution = await resolver.resolve(
            conflict,
            ConflictResolutionStrategy.LAST_WRITE_WINS,
        )

        assert resolution is not None
        assert resolution.resolved_data == conflict.local_data

    @pytest.mark.asyncio
    async def test_conflict_resolution_merge(self):
        """Test merge conflict resolution."""
        resolver = ConflictResolver()

        conflict = SyncConflict(
            entity_type="memory",
            entity_id="mem-123",
            conflict_type="UPDATE_CONFLICT",
            local_data={"field1": "local", "field2": "local2"},
            cloud_data={"field1": "cloud", "field3": "cloud3"},
        )

        resolution = await resolver.resolve(
            conflict,
            ConflictResolutionStrategy.MERGE,
        )

        assert resolution is not None
        assert "field1" in resolution.resolved_data
        assert "field2" in resolution.resolved_data
        assert "field3" in resolution.resolved_data


# ============================================================================
# CONFIGURATION TESTS
# ============================================================================

class TestConfiguration:
    """Test configuration management."""

    def test_local_config_creation(self, local_config):
        """Test local config creation."""
        assert local_config.sync_enabled
        assert local_config.encryption_enabled
        assert local_config.cache_enabled

    def test_config_to_dict(self, local_config):
        """Test config to dictionary."""
        config_dict = local_config.to_dict()
        assert isinstance(config_dict, dict)
        assert "db_path" in config_dict
        assert "sync_enabled" in config_dict

    def test_config_to_json(self, local_config):
        """Test config to JSON."""
        json_str = local_config.to_json()
        assert isinstance(json_str, str)

        parsed = json.loads(json_str)
        assert parsed["sync_enabled"] == local_config.sync_enabled

    def test_config_from_dict(self):
        """Test config from dictionary."""
        config_dict = {
            "db_path": "/tmp/test.db",
            "sync_enabled": False,
            "encryption_enabled": True,
        }

        config = LocalConfig.from_dict(config_dict)
        assert config.db_path == "/tmp/test.db"
        assert not config.sync_enabled
        assert config.encryption_enabled

    def test_config_file_operations(self):
        """Test config file operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            # Create and save config
            config = LocalConfig(sync_enabled=False)
            config.save_to_file(config_path)

            assert config_path.exists()

            # Load config
            loaded_config = LocalConfig.from_file(config_path)
            assert not loaded_config.sync_enabled

    def test_config_manager_singleton(self):
        """Test config manager singleton."""
        manager1 = ConfigManager()
        manager2 = ConfigManager()

        assert manager1 is manager2

    def test_config_manager_operations(self):
        """Test config manager operations."""
        config = LocalConfig(sync_enabled=False)
        ConfigManager.initialize(config)

        retrieved = ConfigManager.get_config()
        assert not retrieved.sync_enabled

        ConfigManager.update_config(sync_enabled=True)
        updated = ConfigManager.get_config()
        assert updated.sync_enabled


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests."""

    def test_full_workflow(self, local_db, encryption_manager):
        """Test full workflow."""
        # 1. Set metadata
        local_db.set_metadata(
            entity_type="memory",
            entity_id="mem-123",
            local_version=1,
        )

        # 2. Enqueue sync
        queue_id = local_db.enqueue_sync(
            entity_type="memory",
            entity_id="mem-123",
            operation="UPDATE",
            data={"content": "test"},
        )

        # 3. Get pending syncs
        pending = local_db.get_pending_syncs()
        assert len(pending) > 0

        # 4. Mark completed
        local_db.mark_sync_completed(queue_id)

        # 5. Verify completion
        pending = local_db.get_pending_syncs()
        assert len(pending) == 0

    def test_encryption_workflow(self, encryption_manager):
        """Test encryption workflow."""
        # 1. Generate key
        key = encryption_manager.generate_master_key()
        assert key is not None

        # 2. Encrypt data
        plaintext = {"api_key": "secret", "token": "abc"}
        encrypted = encryption_manager.encrypt(plaintext)

        # 3. Decrypt data
        decrypted = encryption_manager.decrypt_to_dict(
            encrypted["encrypted_data"],
            encrypted["iv"],
            encrypted["salt"],
        )

        assert decrypted == plaintext

    def test_conflict_workflow(self, local_db):
        """Test conflict workflow."""
        # 1. Log conflict
        conflict_id = local_db.log_conflict(
            entity_type="memory",
            entity_id="mem-123",
            conflict_type="UPDATE_CONFLICT",
            local_data={"content": "local"},
            cloud_data={"content": "cloud"},
        )

        # 2. Get unresolved conflicts
        conflicts = local_db.get_unresolved_conflicts()
        assert len(conflicts) > 0

        # 3. Resolve conflict
        local_db.resolve_conflict(
            conflict_id=conflict_id,
            resolution_strategy="LAST_WRITE_WINS",
            resolved_data={"content": "resolved"},
        )

        # 4. Verify resolution
        conflicts = local_db.get_unresolved_conflicts()
        assert len(conflicts) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
