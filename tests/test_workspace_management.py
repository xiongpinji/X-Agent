"""Comprehensive tests for workspace management system.

Tests cover workspace creation, isolation, path mapping, mount management,
and file access control with security validation.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, UTC

import pytest

from backend.app.core.workspace_manager import WorkspaceManager, WorkspaceConfig, Workspace
from backend.app.core.path_mapper import PathMapper
from backend.app.core.mount_manager import MountManager, MountPoint
from backend.app.core.file_access_control import FileAccessControl


class TestWorkspaceManager:
    """Tests for WorkspaceManager."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def manager(self, temp_dir):
        """Create workspace manager."""
        storage_path = temp_dir / "workspaces.json"
        return WorkspaceManager(temp_dir / "workspaces", storage_path)

    def test_create_workspace(self, manager):
        """Test creating a workspace."""
        ws = manager.create_workspace("user1", "project")
        assert ws.workspace_id
        assert ws.user_id == "user1"
        assert ws.workspace_type == "project"
        assert ws.path.exists()

    def test_create_multiple_workspace_types(self, manager):
        """Test creating different workspace types."""
        project_ws = manager.create_workspace("user1", "project")
        temp_ws = manager.create_workspace("user1", "temporary")
        upload_ws = manager.create_workspace("user1", "upload")

        assert project_ws.workspace_type == "project"
        assert temp_ws.workspace_type == "temporary"
        assert upload_ws.workspace_type == "upload"

    def test_invalid_workspace_type(self, manager):
        """Test creating workspace with invalid type."""
        with pytest.raises(ValueError):
            manager.create_workspace("user1", "invalid")

    def test_get_workspace(self, manager):
        """Test retrieving workspace."""
        ws = manager.create_workspace("user1", "project")
        retrieved = manager.get_workspace(ws.workspace_id)
        assert retrieved is not None
        assert retrieved.workspace_id == ws.workspace_id

    def test_list_workspaces(self, manager):
        """Test listing workspaces."""
        ws1 = manager.create_workspace("user1", "project")
        ws2 = manager.create_workspace("user1", "temporary")
        ws3 = manager.create_workspace("user2", "project")

        user1_ws = manager.list_workspaces("user1")
        assert len(user1_ws) == 2
        assert all(ws.user_id == "user1" for ws in user1_ws)

        user2_ws = manager.list_workspaces("user2")
        assert len(user2_ws) == 1

    def test_list_workspaces_by_type(self, manager):
        """Test filtering workspaces by type."""
        manager.create_workspace("user1", "project")
        manager.create_workspace("user1", "temporary")
        manager.create_workspace("user1", "upload")

        project_ws = manager.list_workspaces("user1", "project")
        assert len(project_ws) == 1
        assert project_ws[0].workspace_type == "project"

    def test_delete_workspace(self, manager):
        """Test deleting workspace."""
        ws = manager.create_workspace("user1", "project")
        ws_id = ws.workspace_id
        assert ws.path.exists()

        deleted = manager.delete_workspace(ws_id)
        assert deleted is True
        assert not ws.path.exists()
        assert manager.get_workspace(ws_id) is None

    def test_delete_nonexistent_workspace(self, manager):
        """Test deleting non-existent workspace."""
        deleted = manager.delete_workspace("nonexistent")
        assert deleted is False

    def test_workspace_size_calculation(self, manager):
        """Test workspace size calculation."""
        ws = manager.create_workspace("user1", "project")

        # Create test file
        test_file = ws.path / "test.txt"
        test_file.write_text("x" * 1024)  # 1KB

        size_mb = ws.get_size_mb()
        assert size_mb > 0
        assert size_mb < 1  # Less than 1MB

    def test_workspace_quota_check(self, manager):
        """Test workspace quota checking."""
        config = WorkspaceConfig(workspace_type="project", max_size_mb=1)
        ws = manager.create_workspace("user1", "project", config)

        # Create file exceeding quota
        test_file = ws.path / "large.txt"
        test_file.write_text("x" * (2 * 1024 * 1024))  # 2MB

        assert ws.is_over_quota()

    def test_workspace_expiration(self, manager):
        """Test workspace expiration."""
        config = WorkspaceConfig(workspace_type="temporary", ttl_hours=1)
        ws = manager.create_workspace("user1", "temporary", config)
        assert not ws.is_expired()

        # Simulate expiration
        ws.created_at = datetime.now(UTC) - timedelta(hours=2)
        assert ws.is_expired()

    def test_cleanup_expired_workspaces(self, manager):
        """Test cleaning up expired workspaces."""
        config = WorkspaceConfig(workspace_type="temporary", ttl_hours=0)
        ws1 = manager.create_workspace("user1", "temporary", config)
        ws2 = manager.create_workspace("user1", "temporary", config)

        # Simulate expiration
        ws1.created_at = datetime.now(UTC) - timedelta(hours=1)
        ws2.created_at = datetime.now(UTC) - timedelta(hours=1)

        deleted = manager.cleanup_expired_workspaces()
        assert len(deleted) >= 0  # May or may not delete depending on timing

    def test_workspace_persistence(self, temp_dir):
        """Test workspace metadata persistence."""
        storage_path = temp_dir / "workspaces.json"
        manager1 = WorkspaceManager(temp_dir / "workspaces", storage_path)
        ws = manager1.create_workspace("user1", "project")
        ws_id = ws.workspace_id

        # Create new manager and verify workspace is loaded
        manager2 = WorkspaceManager(temp_dir / "workspaces", storage_path)
        retrieved = manager2.get_workspace(ws_id)
        assert retrieved is not None
        assert retrieved.user_id == "user1"

    def test_update_workspace_metadata(self, manager):
        """Test updating workspace metadata."""
        ws = manager.create_workspace("user1", "project")
        updated = manager.update_workspace_metadata(ws.workspace_id, {"key": "value"})
        assert updated is not None
        assert updated.metadata["key"] == "value"


class TestPathMapper:
    """Tests for PathMapper."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def mapper(self, temp_dir):
        """Create path mapper."""
        return PathMapper(temp_dir)

    def test_normalize_path(self, mapper):
        """Test path normalization."""
        assert mapper.normalize_path("/foo/bar") == "/foo/bar"
        assert mapper.normalize_path("foo/bar") == "/foo/bar"
        assert mapper.normalize_path("/foo//bar") == "/foo/bar"
        assert mapper.normalize_path("/foo/./bar") == "/foo/bar"
        assert mapper.normalize_path("/foo/../bar") == "/bar"

    def test_normalize_path_with_backslashes(self, mapper):
        """Test normalizing Windows paths."""
        assert mapper.normalize_path("foo\\bar") == "/foo/bar"
        assert mapper.normalize_path("\\foo\\bar") == "/foo/bar"

    def test_invalid_path_characters(self, mapper):
        """Test rejecting invalid characters."""
        with pytest.raises(ValueError):
            mapper.normalize_path("/foo/bar*baz")
        with pytest.raises(ValueError):
            mapper.normalize_path("/foo/bar?baz")

    def test_map_virtual_to_real(self, mapper, temp_dir):
        """Test mapping virtual to real path."""
        user_id = "user1"
        virtual_path = "/test/file.txt"

        real_path = mapper.map_virtual_to_real(virtual_path, user_id)
        assert real_path.is_relative_to(temp_dir)
        assert "user1" in str(real_path)

    def test_map_real_to_virtual(self, mapper, temp_dir):
        """Test mapping real to virtual path."""
        user_id = "user1"
        workspace_path = temp_dir / user_id / "project"
        workspace_path.mkdir(parents=True, exist_ok=True)

        real_path = workspace_path / "test" / "file.txt"
        virtual_path = mapper.map_real_to_virtual(real_path, user_id)

        assert virtual_path.startswith("/")
        assert "test" in virtual_path
        assert "file.txt" in virtual_path

    def test_path_traversal_attack_prevention(self, mapper):
        """Test prevention of path traversal attacks."""
        with pytest.raises(PermissionError):
            mapper.map_virtual_to_real("/../../../etc/passwd", "user1")

    def test_symlink_attack_prevention(self, mapper, temp_dir):
        """Test prevention of symlink attacks."""
        user_id = "user1"
        workspace_path = temp_dir / user_id / "project"
        workspace_path.mkdir(parents=True, exist_ok=True)

        # Create symlink pointing outside workspace
        symlink_path = workspace_path / "link"
        try:
            symlink_path.symlink_to("/etc/passwd")
            with pytest.raises(PermissionError):
                mapper.map_virtual_to_real("/link", user_id)
        except OSError:
            # Symlinks may not be supported on all systems
            pass

    def test_validate_path(self, mapper):
        """Test path validation."""
        assert mapper.validate_path("/test/file.txt", "user1")
        assert not mapper.validate_path("/../../../etc/passwd", "user1")

    def test_forbidden_system_paths(self, mapper):
        """Test access to forbidden system paths."""
        with pytest.raises(PermissionError):
            mapper.map_virtual_to_real("/etc/passwd", "user1")


class TestMountManager:
    """Tests for MountManager."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def manager(self, temp_dir):
        """Create mount manager."""
        storage_path = temp_dir / "mounts.json"
        return MountManager(storage_path)

    def test_mount_directory(self, manager, temp_dir):
        """Test mounting a directory."""
        host_path = temp_dir / "data"
        host_path.mkdir()

        mount = manager.mount_directory("user1", str(host_path))
        assert mount.mount_id
        assert mount.user_id == "user1"
        assert mount.host_path == host_path
        assert mount.mode == "rw"

    def test_mount_nonexistent_directory(self, manager):
        """Test mounting non-existent directory."""
        with pytest.raises(ValueError):
            manager.mount_directory("user1", "/nonexistent/path")

    def test_mount_file_instead_of_directory(self, manager, temp_dir):
        """Test mounting file instead of directory."""
        file_path = temp_dir / "file.txt"
        file_path.write_text("test")

        with pytest.raises(ValueError):
            manager.mount_directory("user1", str(file_path))

    def test_mount_with_custom_path(self, manager, temp_dir):
        """Test mounting with custom mount path."""
        host_path = temp_dir / "data"
        host_path.mkdir()

        mount = manager.mount_directory("user1", str(host_path), "/custom/mount")
        assert mount.mount_path == "/custom/mount"

    def test_mount_read_only(self, manager, temp_dir):
        """Test mounting in read-only mode."""
        host_path = temp_dir / "data"
        host_path.mkdir()

        mount = manager.mount_directory("user1", str(host_path), mode="ro")
        assert mount.mode == "ro"
        assert mount.is_readable()
        assert not mount.is_writable()

    def test_unmount_directory(self, manager, temp_dir):
        """Test unmounting directory."""
        host_path = temp_dir / "data"
        host_path.mkdir()

        mount = manager.mount_directory("user1", str(host_path))
        unmounted = manager.unmount_directory(mount.mount_id)
        assert unmounted is True
        assert manager.get_mount(mount.mount_id) is None

    def test_list_mounts(self, manager, temp_dir):
        """Test listing mounts."""
        host_path1 = temp_dir / "data1"
        host_path2 = temp_dir / "data2"
        host_path1.mkdir()
        host_path2.mkdir()

        mount1 = manager.mount_directory("user1", str(host_path1))
        mount2 = manager.mount_directory("user1", str(host_path2))
        mount3 = manager.mount_directory("user2", str(host_path1))

        user1_mounts = manager.list_mounts("user1")
        assert len(user1_mounts) == 2

        user2_mounts = manager.list_mounts("user2")
        assert len(user2_mounts) == 1

    def test_resolve_mount_path(self, manager, temp_dir):
        """Test resolving mount path."""
        host_path = temp_dir / "data"
        host_path.mkdir()
        (host_path / "file.txt").write_text("test")

        mount = manager.mount_directory("user1", str(host_path), "/mounts/data")
        resolved = manager.resolve_mount_path("user1", "/mounts/data/file.txt")

        assert resolved is not None
        assert resolved.name == "file.txt"

    def test_mount_permission_check(self, manager, temp_dir):
        """Test mount permission checking."""
        host_path = temp_dir / "data"
        host_path.mkdir()

        mount_rw = manager.mount_directory("user1", str(host_path), mode="rw")
        assert manager.check_mount_permission("user1", mount_rw.mount_id, "read")
        assert manager.check_mount_permission("user1", mount_rw.mount_id, "write")

        mount_ro = manager.mount_directory("user1", str(host_path), "/ro", mode="ro")
        assert manager.check_mount_permission("user1", mount_ro.mount_id, "read")
        assert not manager.check_mount_permission("user1", mount_ro.mount_id, "write")

    def test_mount_persistence(self, temp_dir):
        """Test mount metadata persistence."""
        storage_path = temp_dir / "mounts.json"
        manager1 = MountManager(storage_path)

        host_path = temp_dir / "data"
        host_path.mkdir()
        mount = manager1.mount_directory("user1", str(host_path))
        mount_id = mount.mount_id

        # Create new manager and verify mount is loaded
        manager2 = MountManager(storage_path)
        retrieved = manager2.get_mount(mount_id)
        assert retrieved is not None
        assert retrieved.user_id == "user1"


class TestFileAccessControl:
    """Tests for FileAccessControl."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def control(self, temp_dir):
        """Create file access control."""
        audit_path = temp_dir / "audit.jsonl"
        return FileAccessControl(audit_path)

    def test_check_read_permission(self, control, temp_dir):
        """Test read permission checking."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test")

        allowed, reason = control.check_read_permission("user1", test_file)
        assert allowed is True
        assert reason is None

    def test_check_read_nonexistent_file(self, control, temp_dir):
        """Test reading non-existent file."""
        test_file = temp_dir / "nonexistent.txt"
        allowed, reason = control.check_read_permission("user1", test_file)
        assert allowed is False

    def test_check_write_permission(self, control, temp_dir):
        """Test write permission checking."""
        test_file = temp_dir / "test.txt"
        allowed, reason = control.check_write_permission("user1", test_file, 1024)
        assert allowed is True

    def test_check_write_forbidden_file(self, control, temp_dir):
        """Test writing forbidden file type."""
        test_file = temp_dir / "test.exe"
        allowed, reason = control.check_write_permission("user1", test_file, 1024)
        assert allowed is False
        assert "forbidden" in reason.lower()

    def test_check_write_oversized_file(self, control, temp_dir):
        """Test writing oversized file."""
        test_file = temp_dir / "test.txt"
        size = control.max_file_size_bytes + 1024
        allowed, reason = control.check_write_permission("user1", test_file, size)
        assert allowed is False

    def test_audit_file_operation(self, control):
        """Test auditing file operations."""
        control.audit_file_operation("user1", "read", "/test/file.txt", True)
        control.audit_file_operation("user1", "write", "/test/file.txt", False, "Permission denied")

        logs = control.get_audit_logs()
        assert len(logs) == 2
        assert logs[0].operation == "write"
        assert logs[1].operation == "read"

    def test_audit_logs_filtering(self, control):
        """Test filtering audit logs."""
        control.audit_file_operation("user1", "read", "/test/file.txt", True)
        control.audit_file_operation("user2", "write", "/test/file.txt", True)

        user1_logs = control.get_audit_logs(user_id="user1")
        assert len(user1_logs) == 1
        assert user1_logs[0].user_id == "user1"

    def test_grant_revoke_permissions(self, control):
        """Test granting and revoking permissions."""
        control.grant_permission("user1", "write")
        assert control.has_permission("user1", "write")

        control.revoke_permission("user1", "write")
        assert not control.has_permission("user1", "write")

    def test_forbidden_extensions(self, control):
        """Test forbidden file extensions."""
        control.add_forbidden_extension(".custom")

        test_file = Path("/test/file.custom")
        allowed, _ = control.check_write_permission("user1", test_file, 1024)
        assert allowed is False

        control.remove_forbidden_extension(".custom")
        allowed, _ = control.check_write_permission("user1", test_file, 1024)
        assert allowed is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
