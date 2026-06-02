"""
X-Agent Local Sync Integration Tests

Comprehensive test suite for local sync module integration.
"""

from __future__ import annotations

import json
import pytest
import tempfile
from base64 import b64decode
from datetime import datetime, UTC
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from backend.local.database import LocalDatabase, DatabaseConfig
from backend.local.config import LocalConfig, ConfigManager
from backend.local.encryption import EncryptionManager, EncryptionConfig
from backend.local.sync_client import SyncClient, SyncDirection, ConflictResolutionStrategy
from backend.local.migration import DatabaseMigration, DataMigration, initialize_local_database


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def temp_db_path():
    """Create temporary database path."""
    # Windows 上 sqlite(尤其 WAL 模式)关闭后句柄可能延迟释放，导致
    # TemporaryDirectory 的 rmtree 触发 WinError 32(文件被占用)。
    # ignore_cleanup_errors 让清理失败不致命(Python 3.10+)。
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        yield Path(tmpdir) / "test.db"


@pytest.fixture
def db_config(temp_db_path):
    """Create database configuration."""
    return DatabaseConfig(
        db_path=str(temp_db_path),
        timeout=30.0,
        enable_wal=True,
        enable_foreign_keys=True,
    )


@pytest.fixture
def local_db(db_config):
    """Create and initialize local database."""
    db = LocalDatabase(db_config)
    db.initialize()
    yield db
    db.close()


@pytest.fixture
def local_config():
    """Create local configuration."""
    return LocalConfig(
        db_path="~/.xagent/test.db",
        sync_enabled=True,
        sync_interval_seconds=300,
        encryption_enabled=True,
    )


@pytest.fixture
def encryption_manager():
    """Create encryption manager."""
    config = EncryptionConfig()
    manager = EncryptionManager(config)
    manager.generate_master_key()
    return manager


# ============================================================================
# DATABASE TESTS
# ============================================================================


class TestLocalDatabase:
    """Test local database operations."""

    def test_database_initialization(self, local_db):
        """Test database initialization."""
        assert local_db.config.db_path.exists()

    def test_set_and_get_metadata(self, local_db):
        """Test metadata operations."""
        metadata_id = local_db.set_metadata(
            entity_type="memory",
            entity_id="mem_123",
            local_version=1,
            cloud_version=0,
            is_encrypted=False,
        )

        assert metadata_id is not None

        metadata = local_db.get_metadata("memory", "mem_123")
        assert metadata is not None
        assert metadata["entity_type"] == "memory"
        assert metadata["entity_id"] == "mem_123"

    def test_sync_state_operations(self, local_db):
        """Test sync state operations."""
        local_db.update_sync_state(
            entity_type="memory",
            entity_id="mem_123",
            state="SYNCED",
        )

        state = local_db.get_sync_state("memory", "mem_123")
        assert state is not None
        assert state["state"] == "SYNCED"

    def test_conflict_logging(self, local_db):
        """Test conflict logging."""
        conflict_id = local_db.log_conflict(
            entity_type="memory",
            entity_id="mem_123",
            conflict_type="UPDATE_CONFLICT",
            local_data={"content": "local"},
            cloud_data={"content": "cloud"},
            local_version=1,
            cloud_version=2,
        )

        assert conflict_id is not None

        conflicts = local_db.get_unresolved_conflicts()
        assert len(conflicts) > 0

    def test_conflict_resolution(self, local_db):
        """Test conflict resolution."""
        conflict_id = local_db.log_conflict(
            entity_type="memory",
            entity_id="mem_123",
            conflict_type="UPDATE_CONFLICT",
            local_data={"content": "local"},
            cloud_data={"content": "cloud"},
        )

        local_db.resolve_conflict(
            conflict_id=conflict_id,
            resolution_strategy="LAST_WRITE_WINS",
            resolved_data={"content": "resolved"},
            resolved_by="user_123",
        )

        conflicts = local_db.get_unresolved_conflicts()
        assert len(conflicts) == 0

    def test_sync_queue_operations(self, local_db):
        """Test sync queue operations."""
        queue_id = local_db.enqueue_sync(
            entity_type="memory",
            entity_id="mem_123",
            operation="UPDATE",
            data={"content": "updated"},
            priority=1,
        )

        assert queue_id is not None

        pending = local_db.get_pending_syncs()
        assert len(pending) > 0

        local_db.mark_sync_completed(queue_id, success=True)

        pending = local_db.get_pending_syncs()
        assert len(pending) == 0

    def test_offline_queue_operations(self, local_db):
        """Test offline queue operations."""
        queue_id = local_db.enqueue_offline(
            entity_type="memory",
            entity_id="mem_123",
            operation="UPDATE",
            data={"content": "offline"},
            priority=1,
        )

        assert queue_id is not None

        offline_ops = local_db.get_offline_operations()
        assert len(offline_ops) > 0

        local_db.mark_offline_synced(queue_id)

        offline_ops = local_db.get_offline_operations()
        assert len(offline_ops) == 0

    def test_sync_history_recording(self, local_db):
        """Test sync history recording."""
        local_db.record_sync_history(
            sync_batch_id="batch_123",
            entity_type="memory",
            entity_id="mem_123",
            operation="UPDATE",
            direction="upload",
            status="success",
            duration_ms=100,
        )

        history = local_db.get_sync_history()
        assert len(history) > 0

    def test_cache_operations(self, local_db):
        """Test cache operations."""
        local_db.set_cache(
            entity_type="memory",
            entity_id="mem_123",
            cache_key="test_key",
            cache_value={"data": "test"},
            ttl_seconds=3600,
        )

        cached = local_db.get_cache("test_key")
        assert cached is not None

    def test_sync_statistics(self, local_db):
        """Test sync statistics."""
        # Enqueue some operations
        local_db.enqueue_sync(
            entity_type="memory",
            entity_id="mem_123",
            operation="UPDATE",
            data={"content": "test"},
        )

        stats = local_db.get_sync_stats()
        assert stats["pending_syncs"] >= 1

    def test_database_size(self, local_db):
        """Test database size calculation."""
        size_info = local_db.get_database_size()
        assert "database_size_bytes" in size_info
        assert "database_size_mb" in size_info


# ============================================================================
# CONFIGURATION TESTS
# ============================================================================


class TestConfiguration:
    """Test configuration management."""

    def test_local_config_creation(self, local_config):
        """Test local config creation."""
        assert local_config.db_path == "~/.xagent/test.db"
        assert local_config.sync_enabled is True

    def test_config_to_dict(self, local_config):
        """Test config to dictionary conversion."""
        config_dict = local_config.to_dict()
        assert isinstance(config_dict, dict)
        assert "db_path" in config_dict

    def test_config_to_json(self, local_config):
        """Test config to JSON conversion."""
        json_str = local_config.to_json()
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert "db_path" in parsed

    def test_config_from_dict(self):
        """Test config from dictionary."""
        config_dict = {
            "db_path": "~/.xagent/test.db",
            "sync_enabled": True,
        }
        config = LocalConfig.from_dict(config_dict)
        assert config.db_path == "~/.xagent/test.db"

    def test_config_manager_singleton(self):
        """Test config manager singleton."""
        manager1 = ConfigManager()
        manager2 = ConfigManager()
        assert manager1 is manager2


# ============================================================================
# ENCRYPTION TESTS
# ============================================================================


class TestEncryption:
    """Test encryption operations."""

    def test_master_key_generation(self, encryption_manager):
        """Test master key generation."""
        key = encryption_manager.generate_master_key()
        assert len(key) == 32  # 256 bits

    def test_key_derivation(self, encryption_manager):
        """Test key derivation from password."""
        password = "test_password"
        key, salt = encryption_manager.derive_key_from_password(password)
        assert len(key) == 32
        assert len(salt) == 16

    def test_encryption_decryption(self, encryption_manager):
        """Test encryption and decryption."""
        plaintext = b"test data"
        # encrypt() 返回含 base64 字段的 dict(encrypted_data/iv/salt 均为 base64 字符串)
        result = encryption_manager.encrypt(plaintext)

        # 密文字节应不等于明文;iv/salt 解码后是裸字节(12/16)
        assert b64decode(result["encrypted_data"]) != plaintext
        assert len(b64decode(result["iv"])) == 12
        assert len(b64decode(result["salt"])) == 16

        # decrypt() 吃 base64 字符串,返回明文 bytes
        decrypted = encryption_manager.decrypt(
            result["encrypted_data"], result["iv"], result["salt"]
        )
        assert decrypted == plaintext


# ============================================================================
# SYNC CLIENT TESTS
# ============================================================================


class TestSyncClient:
    """Test sync client operations."""

    @pytest.mark.asyncio
    async def test_sync_client_initialization(self, local_db):
        """Test sync client initialization."""
        cloud_client = Mock()
        sync_client = SyncClient(local_db, cloud_client)

        assert sync_client.db is local_db
        assert sync_client.cloud_api_client is cloud_client

    @pytest.mark.asyncio
    async def test_enqueue_operation(self, local_db):
        """Test enqueue operation."""
        cloud_client = Mock()
        sync_client = SyncClient(local_db, cloud_client)

        queue_id = await sync_client.enqueue_operation(
            entity_type="memory",
            entity_id="mem_123",
            operation="UPDATE",
            data={"content": "test"},
            priority=1,
        )

        assert queue_id is not None

    @pytest.mark.asyncio
    async def test_offline_mode(self, local_db):
        """Test offline mode."""
        cloud_client = Mock()
        sync_client = SyncClient(local_db, cloud_client)

        sync_client.set_offline_mode(True)
        assert sync_client._offline_mode is True

        sync_client.set_offline_mode(False)
        assert sync_client._offline_mode is False

    @pytest.mark.asyncio
    async def test_sync_callback_registration(self, local_db):
        """Test sync callback registration."""
        cloud_client = Mock()
        sync_client = SyncClient(local_db, cloud_client)

        callback = Mock()
        sync_client.register_sync_callback(callback)

        assert len(sync_client._sync_callbacks) > 0


# ============================================================================
# MIGRATION TESTS
# ============================================================================


class TestMigration:
    """Test database migration."""

    def test_database_migration_v1(self, local_db):
        """Test v1 migration."""
        migration = DatabaseMigration(local_db)
        migration.migrate_v1_initial()

        # Verify tables exist
        conn = local_db._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='local_metadata'
        """)
        assert cursor.fetchone() is not None

    def test_migration_status(self, local_db):
        """Test migration status."""
        migration = DatabaseMigration(local_db)
        migration.migrate_v1_initial()

        status = migration.get_migration_status()
        assert status["initialized"] is True
        assert status["current_version"] == "1.0"

    def test_initialize_local_database(self, temp_db_path):
        """Test local database initialization."""
        db = initialize_local_database(str(temp_db_path))

        assert db.config.db_path.exists()
        db.close()


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestIntegration:
    """Test integration scenarios."""

    def test_full_sync_workflow(self, local_db):
        """Test full sync workflow."""
        # 1. Enqueue operation
        queue_id = local_db.enqueue_sync(
            entity_type="memory",
            entity_id="mem_123",
            operation="UPDATE",
            data={"content": "updated"},
        )

        # 2. Set metadata
        local_db.set_metadata(
            entity_type="memory",
            entity_id="mem_123",
            local_version=1,
            cloud_version=0,
        )

        # 3. Update sync state
        local_db.update_sync_state(
            entity_type="memory",
            entity_id="mem_123",
            state="SYNCING",
        )

        # 4. Mark completed
        local_db.mark_sync_completed(queue_id, success=True)

        # 5. Record history
        local_db.record_sync_history(
            sync_batch_id="batch_123",
            entity_type="memory",
            entity_id="mem_123",
            operation="UPDATE",
            direction="upload",
            status="success",
        )

        # Verify
        pending = local_db.get_pending_syncs()
        assert len(pending) == 0

    def test_conflict_resolution_workflow(self, local_db):
        """Test conflict resolution workflow."""
        # 1. Log conflict
        conflict_id = local_db.log_conflict(
            entity_type="memory",
            entity_id="mem_123",
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

    def test_offline_to_online_workflow(self, local_db):
        """Test offline to online workflow."""
        # 1. Enqueue offline operation
        offline_id = local_db.enqueue_offline(
            entity_type="memory",
            entity_id="mem_123",
            operation="UPDATE",
            data={"content": "offline"},
        )

        # 2. Verify offline operation
        offline_ops = local_db.get_offline_operations()
        assert len(offline_ops) > 0

        # 3. Mark as synced
        local_db.mark_offline_synced(offline_id)

        # 4. Verify sync
        offline_ops = local_db.get_offline_operations()
        assert len(offline_ops) == 0


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================


class TestPerformance:
    """Test performance characteristics."""

    def test_bulk_enqueue_performance(self, local_db):
        """Test bulk enqueue performance."""
        import time

        start = time.time()

        for i in range(100):
            local_db.enqueue_sync(
                entity_type="memory",
                entity_id=f"mem_{i}",
                operation="UPDATE",
                data={"content": f"test_{i}"},
            )

        duration = time.time() - start

        # Should complete in reasonable time
        assert duration < 5.0

    def test_query_performance(self, local_db):
        """Test query performance."""
        import time

        # Enqueue operations
        for i in range(100):
            local_db.enqueue_sync(
                entity_type="memory",
                entity_id=f"mem_{i}",
                operation="UPDATE",
                data={"content": f"test_{i}"},
            )

        start = time.time()

        # Query pending syncs
        for _ in range(10):
            local_db.get_pending_syncs()

        duration = time.time() - start

        # Should complete quickly
        assert duration < 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
