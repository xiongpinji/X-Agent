"""归档自 tests/test_security_hardening.py（2026-08-04 死代码收敛）
测试对象 tool_sandbox 已归档（归档态不可运行）。
"""

class TestToolSandbox:
    """Test tool sandbox functionality."""

    def test_sandbox_file_listing(self, tmp_path):
        """Test safe directory listing."""
        sandbox = ToolSandbox(tmp_path)

        # Create test files
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.txt").write_text("content2")
        (tmp_path / "subdir").mkdir()

        # List directory
        items = sandbox.list_directory(tmp_path)

        assert len(items) == 3
        assert any(item["name"] == "file1.txt" for item in items)
        assert any(item["name"] == "file2.txt" for item in items)
        assert any(item["name"] == "subdir" for item in items)

    def test_file_size_limit(self, tmp_path):
        """Test file size limit enforcement."""
        sandbox = ToolSandbox(tmp_path, max_file_size=100)

        # Create a large file
        large_file = tmp_path / "large.txt"
        large_file.write_text("x" * 1000)

        # Should reject file exceeding size limit
        with pytest.raises(Exception):
            sandbox.validate_file_size(str(large_file))


