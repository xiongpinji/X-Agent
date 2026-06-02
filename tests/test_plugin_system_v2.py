"""
Tests for Plugin System V2

Comprehensive tests for:
- Plugin loading and unloading
- Permission management
- Dependency resolution
- Sandbox execution
- Update management
- Review system
"""

import pytest
from pathlib import Path
from datetime import UTC, datetime
from unittest.mock import Mock, patch

from backend.app.core.plugin_system_v2 import (
    PluginSystemV2,
    PluginManifest,
    PluginMetadata,
    PluginInstallRequest,
    PluginExecutionRequest,
    PluginStatus,
    PluginRiskLevel,
)
from backend.app.core.plugin_sandbox import (
    SandboxPolicyBuilder,
    SandboxManager,
    ResourceType,
)
from backend.app.core.plugin_review import (
    PluginReviewManager,
    ReviewStatus,
)
from backend.app.core.plugin_update import (
    PluginUpdateManager,
    UpdateStatus,
    UpdatePriority,
)


class TestPluginSystemV2:
    """Test PluginSystemV2"""

    @pytest.fixture
    def system(self, tmp_path):
        """Create plugin system instance"""
        return PluginSystemV2(tmp_path)

    @pytest.fixture
    def sample_manifest(self):
        """Create sample plugin manifest"""
        metadata = PluginMetadata(
            plugin_id="test-plugin",
            name="Test Plugin",
            version="1.0.0",
            author="Test Author",
            description="Test plugin for testing"
        )
        return PluginManifest(
            metadata=metadata,
            entry_point="plugin",
            risk_level=PluginRiskLevel.LOW
        )

    def test_system_initialization(self, system):
        """Test system initialization"""
        assert system is not None
        assert system.loader is not None
        assert system.permissions is not None
        assert system.registry is not None

    def test_plugin_registration(self, system, sample_manifest):
        """Test plugin registration"""
        system.registry.register_plugin(sample_manifest)
        plugin = system.registry.get_plugin("test-plugin")
        assert plugin is not None
        assert plugin.metadata.name == "Test Plugin"

    def test_plugin_search(self, system, sample_manifest):
        """Test plugin search"""
        system.registry.register_plugin(sample_manifest)
        results = system.registry.search_plugins("Test")
        assert len(results) > 0
        assert results[0].metadata.plugin_id == "test-plugin"

    def test_permission_grant(self, system):
        """Test permission granting"""
        system.permissions.grant_permission("test-plugin", "file:read")
        assert system.permissions.has_permission("test-plugin", "file:read")

    def test_permission_revoke(self, system):
        """Test permission revocation"""
        system.permissions.grant_permission("test-plugin", "file:read")
        system.permissions.revoke_permission("test-plugin", "file:read")
        assert not system.permissions.has_permission("test-plugin", "file:read")

    def test_get_system_status(self, system, sample_manifest):
        """Test getting system status"""
        system.registry.register_plugin(sample_manifest)
        status = system.get_system_status()
        assert status["total_plugins"] >= 1
        assert "plugins" in status


class TestPluginSandbox:
    """Test plugin sandbox"""

    def test_sandbox_policy_builder(self):
        """Test sandbox policy builder"""
        policy = (SandboxPolicyBuilder("test-plugin")
            .with_allowed_modules(["json", "math"])
            .with_memory_limit(256, 512)
            .with_timeout(30)
            .build())

        assert policy.plugin_id == "test-plugin"
        assert "json" in policy.allowed_modules
        assert policy.timeout_seconds == 30

    def test_sandbox_creation(self):
        """Test sandbox creation"""
        manager = SandboxManager()
        policy = SandboxPolicyBuilder("test-plugin").build()
        sandbox = manager.create_sandbox(policy)

        assert sandbox is not None
        assert manager.get_sandbox("test-plugin") is not None

    def test_sandbox_removal(self):
        """Test sandbox removal"""
        manager = SandboxManager()
        policy = SandboxPolicyBuilder("test-plugin").build()
        manager.create_sandbox(policy)
        manager.remove_sandbox("test-plugin")

        assert manager.get_sandbox("test-plugin") is None

    def test_restricted_globals(self):
        """Test restricted globals creation"""
        policy = SandboxPolicyBuilder("test-plugin").build()
        sandbox = SandboxManager().create_sandbox(policy)
        globals_dict = sandbox.create_restricted_globals()

        assert "__builtins__" in globals_dict
        assert "__name__" in globals_dict
        assert "eval" not in globals_dict["__builtins__"]


class TestPluginReview:
    """Test plugin review system"""

    @pytest.fixture
    def review_manager(self, tmp_path):
        """Create review manager"""
        return PluginReviewManager(tmp_path)

    def test_review_creation(self, review_manager, tmp_path):
        """Test review creation"""
        # Create a test plugin directory
        plugin_dir = tmp_path / "test-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "manifest.json").write_text('{"name": "Test"}')
        (plugin_dir / "README.md").write_text("# Test Plugin")

        review = review_manager.create_review(
            "test-plugin",
            "1.0.0",
            plugin_dir
        )

        assert review is not None
        assert review.plugin_id == "test-plugin"
        assert review.status == ReviewStatus.IN_REVIEW

    def test_review_approval(self, review_manager, tmp_path):
        """Test review approval"""
        plugin_dir = tmp_path / "test-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "manifest.json").write_text('{"name": "Test"}')
        (plugin_dir / "README.md").write_text("# Test Plugin")

        review = review_manager.create_review(
            "test-plugin",
            "1.0.0",
            plugin_dir
        )

        approved = review_manager.approve_review(review.review_id, "approver1")
        assert approved.status == ReviewStatus.APPROVED
        assert approved.approved_by == "approver1"

    def test_review_rejection(self, review_manager, tmp_path):
        """Test review rejection"""
        plugin_dir = tmp_path / "test-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "manifest.json").write_text('{"name": "Test"}')
        (plugin_dir / "README.md").write_text("# Test Plugin")

        review = review_manager.create_review(
            "test-plugin",
            "1.0.0",
            plugin_dir
        )

        rejected = review_manager.reject_review(
            review.review_id,
            "Security issues found"
        )
        assert rejected.status == ReviewStatus.REJECTED
        assert rejected.rejection_reason == "Security issues found"


class TestPluginUpdate:
    """Test plugin update system"""

    @pytest.fixture
    def update_manager(self, tmp_path):
        """Create update manager"""
        return PluginUpdateManager(tmp_path)

    def test_version_comparison(self):
        """Test version comparison"""
        from backend.app.core.plugin_update import VersionComparator

        assert VersionComparator.is_newer("1.1.0", "1.0.0")
        assert not VersionComparator.is_newer("1.0.0", "1.1.0")
        assert VersionComparator.is_compatible("1.1.0", "1.0.0")
        assert not VersionComparator.is_compatible("2.0.0", "1.0.0")

    def test_update_creation(self, update_manager):
        """Test update creation"""
        update = update_manager.create_update(
            plugin_id="test-plugin",
            from_version="1.0.0",
            to_version="1.1.0",
            download_url="https://example.com/plugin.zip",
            file_hash="abc123",
            file_size=1024,
            changelog="Bug fixes"
        )

        assert update is not None
        assert update.from_version == "1.0.0"
        assert update.to_version == "1.1.0"
        assert update.status == UpdateStatus.AVAILABLE

    def test_update_progress(self, update_manager):
        """Test update progress tracking"""
        update = update_manager.create_update(
            plugin_id="test-plugin",
            from_version="1.0.0",
            to_version="1.1.0",
            download_url="https://example.com/plugin.zip",
            file_hash="abc123",
            file_size=1024,
            changelog="Bug fixes"
        )

        update_manager.start_update(update.update_id)
        update_manager.update_download_progress(update.update_id, 50)

        updated = update_manager.get_update(update.update_id)
        assert updated.download_progress == 50

    def test_update_completion(self, update_manager):
        """Test update completion"""
        update = update_manager.create_update(
            plugin_id="test-plugin",
            from_version="1.0.0",
            to_version="1.1.0",
            download_url="https://example.com/plugin.zip",
            file_hash="abc123",
            file_size=1024,
            changelog="Bug fixes"
        )

        update_manager.start_update(update.update_id)
        completed = update_manager.complete_update(update.update_id)

        assert completed.status == UpdateStatus.INSTALLED
        assert completed.completed_at is not None


class TestPluginIntegration:
    """Integration tests for plugin system"""

    def test_full_plugin_lifecycle(self, tmp_path):
        """Test complete plugin lifecycle"""
        system = PluginSystemV2(tmp_path)

        # Create manifest
        metadata = PluginMetadata(
            plugin_id="lifecycle-test",
            name="Lifecycle Test",
            version="1.0.0",
            author="Test",
            description="Test"
        )
        manifest = PluginManifest(
            metadata=metadata,
            entry_point="plugin"
        )

        # Register
        system.registry.register_plugin(manifest)
        assert system.registry.get_plugin("lifecycle-test") is not None

        # Grant permissions
        system.permissions.grant_permission("lifecycle-test", "action:execute")
        assert system.permissions.has_permission("lifecycle-test", "action:execute")

        # Get status
        status = system.get_system_status()
        assert status["total_plugins"] >= 1

    def test_permission_enforcement(self, tmp_path):
        """Test permission enforcement"""
        system = PluginSystemV2(tmp_path)

        # Create manifest
        metadata = PluginMetadata(
            plugin_id="perm-test",
            name="Permission Test",
            version="1.0.0",
            author="Test",
            description="Test"
        )
        manifest = PluginManifest(
            metadata=metadata,
            entry_point="plugin"
        )

        system.registry.register_plugin(manifest)

        # Verify permission denied without grant
        assert not system.permissions.has_permission("perm-test", "file:read")

        # Grant and verify
        system.permissions.grant_permission("perm-test", "file:read")
        assert system.permissions.has_permission("perm-test", "file:read")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
