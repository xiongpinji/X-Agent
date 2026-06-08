"""Security tests for path sandbox isolation."""

from __future__ import annotations

import os

import pytest
from pathlib import Path

from backend.app.core.tools import _resolve_tool_path, _resolve_tool_root, _is_path_forbidden
from backend.app.core.approvals import ApprovalSubjectType
from backend.app.core.sandbox.security import get_enterprise_safety_policy, list_enterprise_safety_policies

# These assertions hardcode POSIX system paths (/etc, /sys, ...). On Windows,
# Path("/etc") resolves to a drive-relative path (e.g. C:\etc) and never matches
# the POSIX entries in _FORBIDDEN_PATHS, so the POSIX-specific protection cannot
# be exercised. The Windows equivalents (C:\Windows, ...) are covered separately.
posix_only = pytest.mark.skipif(
    os.name == "nt",
    reason="POSIX-specific system paths; not meaningful on Windows filesystems.",
)


class TestPathSandboxIsolation:
    """Test path sandbox isolation to prevent directory traversal attacks."""

    def test_path_within_project_root_allowed(self, tmp_path):
        """Test that paths within project root are allowed."""
        # This test assumes PROJECT_ROOT is set correctly
        from backend.app.settings import PROJECT_ROOT

        project_root = Path(PROJECT_ROOT)
        test_file = project_root / "test.txt"

        # Should not raise
        result = _resolve_tool_path(str(test_file))
        assert result.is_relative_to(project_root)

    def test_path_outside_project_root_denied(self):
        """Test that paths outside project root are denied."""
        # Try to access /etc/passwd. Either denial reason is valid: the
        # forbidden-system-directory guard fires before the project-root check,
        # so accept whichever PermissionError reaches first.
        with pytest.raises(
            PermissionError,
            match="(must be within project directory|system directory forbidden)",
        ):
            _resolve_tool_path("/etc/passwd")

    def test_path_traversal_attack_denied(self):
        """Test that path traversal attacks are denied."""
        from backend.app.settings import PROJECT_ROOT

        project_root = Path(PROJECT_ROOT)
        # Try to escape project root using ..
        malicious_path = str(project_root / ".." / ".." / "etc" / "passwd")

        with pytest.raises(PermissionError, match="must be within project directory"):
            _resolve_tool_path(malicious_path)

    @posix_only
    def test_forbidden_system_directories_denied(self):
        """Test that forbidden system directories are denied."""
        forbidden_paths = [
            "/etc",
            "/sys",
            "/proc",
            "/dev",
            "/boot",
            "/root",
            "/var/log",
        ]

        for path in forbidden_paths:
            with pytest.raises(PermissionError, match="system directory forbidden"):
                _resolve_tool_path(path)

    def test_root_within_project_root_allowed(self, tmp_path):
        """Test that roots within project root are allowed."""
        from backend.app.settings import PROJECT_ROOT

        project_root = Path(PROJECT_ROOT)
        test_dir = project_root / "test_dir"

        # Should not raise
        result = _resolve_tool_root(str(test_dir))
        assert result.is_relative_to(project_root)

    def test_root_outside_project_root_denied(self):
        """Test that roots outside project root are denied."""
        # Either denial reason is valid: the forbidden-system-directory guard
        # fires before the project-root check.
        with pytest.raises(
            PermissionError,
            match="(must be within project directory|system directory forbidden)",
        ):
            _resolve_tool_root("/etc")

    def test_root_traversal_attack_denied(self):
        """Test that root traversal attacks are denied."""
        from backend.app.settings import PROJECT_ROOT

        project_root = Path(PROJECT_ROOT)
        malicious_root = str(project_root / ".." / ".." / "etc")

        with pytest.raises(PermissionError, match="must be within project directory"):
            _resolve_tool_root(malicious_root)

    @posix_only
    def test_forbidden_root_directories_denied(self):
        """Test that forbidden root directories are denied."""
        forbidden_roots = [
            "/etc",
            "/sys",
            "/proc",
            "/dev",
            "/boot",
            "/root",
            "/var/log",
        ]

        for root in forbidden_roots:
            with pytest.raises(PermissionError, match="system directory forbidden"):
                _resolve_tool_root(root)

    def test_expanduser_in_path_resolution(self):
        """Test that ~ is expanded in path resolution."""
        from backend.app.settings import PROJECT_ROOT

        project_root = Path(PROJECT_ROOT)
        # Create a path with ~ that would be within project root after expansion
        # This is a bit tricky to test without mocking, so we just verify it doesn't crash
        try:
            # This might fail if ~ expands outside project root, which is expected
            _resolve_tool_path("~/test.txt")
        except PermissionError:
            # Expected if ~ is outside project root
            pass

    @posix_only
    def test_is_path_forbidden_checks(self):
        """Test forbidden path checking."""
        assert _is_path_forbidden(Path("/etc"))
        assert _is_path_forbidden(Path("/sys"))
        assert _is_path_forbidden(Path("/proc"))
        assert _is_path_forbidden(Path("/dev"))
        assert _is_path_forbidden(Path("/boot"))
        assert _is_path_forbidden(Path("/root"))
        assert _is_path_forbidden(Path("/var/log"))
        assert _is_path_forbidden(Path("/var/spool"))
        assert _is_path_forbidden(Path("/tmp"))
        assert _is_path_forbidden(Path("/var/tmp"))

    def test_is_path_forbidden_allows_safe_paths(self):
        """Test that safe paths are not forbidden."""
        from backend.app.settings import PROJECT_ROOT

        project_root = Path(PROJECT_ROOT)
        assert not _is_path_forbidden(project_root)
        assert not _is_path_forbidden(project_root / "src")
        assert not _is_path_forbidden(project_root / "tests")

    @posix_only
    def test_case_insensitive_forbidden_path_check(self):
        """Test that forbidden path check is case-insensitive."""
        # On case-insensitive filesystems, /ETC should also be forbidden
        assert _is_path_forbidden(Path("/ETC"))
        assert _is_path_forbidden(Path("/Etc"))
        assert _is_path_forbidden(Path("/SYS"))

    def test_symlink_attack_prevention(self):
        """Test that symlink attacks are prevented."""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            from backend.app.settings import PROJECT_ROOT

            project_root = Path(PROJECT_ROOT)

            # Create a symlink pointing outside project root
            symlink_path = Path(tmpdir) / "malicious_link"
            try:
                symlink_path.symlink_to("/etc/passwd")

                # Try to resolve the symlink. The symlink points at /etc/passwd,
                # which trips the forbidden-system-directory guard first; the
                # symlink-target guard would also reject it. Accept any of the
                # three valid denial messages — all mean the attack was blocked.
                with pytest.raises(
                    PermissionError,
                    match="(must be within project directory|system directory forbidden|Symlink target must be within)",
                ):
                    _resolve_tool_path(str(symlink_path))
            except (OSError, NotImplementedError):
                # Symlinks might not be supported on this system
                pytest.skip("Symlinks not supported on this system")

    def test_double_encoding_attack_prevention(self):
        """Test that double encoding attacks are prevented."""
        from backend.app.settings import PROJECT_ROOT

        project_root = Path(PROJECT_ROOT)

        # Try various encoding tricks
        malicious_paths = [
            str(project_root / "..%2F..%2Fetc%2Fpasswd"),
            str(project_root / "..%252F..%252Fetc%252Fpasswd"),
        ]

        for path in malicious_paths:
            try:
                result = _resolve_tool_path(path)
                # If it doesn't raise, verify it's still within project root
                assert result.is_relative_to(project_root)
            except PermissionError:
                # Also acceptable
                pass

    def test_null_byte_injection_prevention(self):
        """Test that null byte injection is prevented."""
        from backend.app.settings import PROJECT_ROOT

        project_root = Path(PROJECT_ROOT)

        # Try null byte injection
        try:
            _resolve_tool_path(str(project_root / "test.txt\x00/etc/passwd"))
        except (ValueError, PermissionError):
            # Expected - either ValueError from Path or PermissionError from our check
            pass


class TestEnterpriseSafetyPolicyContract:
    def test_mutating_subjects_are_owner_admin_audit_gated(self):
        policies = list_enterprise_safety_policies()
        subjects = {policy.subject_type for policy in policies}

        assert {
            ApprovalSubjectType.COMMAND,
            ApprovalSubjectType.FILE_CHANGE,
            ApprovalSubjectType.NETWORK_REQUEST,
            ApprovalSubjectType.MCP_ELICITATION,
            ApprovalSubjectType.BROWSER_ACTION,
            ApprovalSubjectType.CHANNEL_SEND,
            ApprovalSubjectType.ISSUE_TO_PR_EXECUTE,
        }.issubset(subjects)

        for policy in policies:
            assert policy.owner_gate_required is True
            assert policy.admin_policy_required is True
            assert policy.audit_required is True
            assert policy.blocked_without_approval is True
            assert policy.default_sandbox_profile
            assert "approve_once" in policy.allowed_decision_types
            assert "deny" in policy.allowed_decision_types
            assert "abort" in policy.allowed_decision_types

    def test_specific_network_policy_is_default_deny(self):
        policy = get_enterprise_safety_policy(ApprovalSubjectType.NETWORK_REQUEST)

        assert policy is not None
        assert policy.default_sandbox_profile == "network_default_deny"
        assert policy.to_dict()["subject_type"] == "network_request"
