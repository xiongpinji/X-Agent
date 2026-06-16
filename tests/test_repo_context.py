from __future__ import annotations

import os
import subprocess
import time

import pytest

from backend.app.core.repo_context import build_repo_context


def test_repo_context_builds_git_instructions_recent_files_and_test_config(tmp_path) -> None:
    _run(["git", "init"], cwd=tmp_path)
    _run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path)
    _run(["git", "config", "user.name", "Test User"], cwd=tmp_path)

    (tmp_path / "AGENTS.md").write_text("Use focused tests.\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\n"
        "asyncio_mode = 'auto'\n"
        "testpaths = ['tests']\n",
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_demo.py").write_text("def test_demo():\n    assert True\n", encoding="utf-8")
    (tmp_path / "old.py").write_text("old = True\n", encoding="utf-8")
    _run(["git", "add", "."], cwd=tmp_path)
    _run(["git", "commit", "-m", "initial"], cwd=tmp_path)

    time.sleep(0.01)
    (tmp_path / "newer.py").write_text("newer = True\n", encoding="utf-8")
    (tmp_path / "old.py").write_text("old = False\n", encoding="utf-8")

    context = build_repo_context(tmp_path, max_recent_files=5)

    assert context["kind"] == "xagent_repo_context"
    assert context["workspace_path"] == str(tmp_path.resolve())
    assert context["git_status"]["available"] is True
    assert context["git_status"]["is_repo"] is True
    assert context["git_status"]["dirty"] is True
    assert context["git_status"]["entry_count"] == 2
    assert any(entry["path"] == "old.py" for entry in context["git_status"]["entries"])
    assert any(entry["path"] == "newer.py" for entry in context["git_status"]["entries"])

    instruction_paths = [item["path"] for item in context["instruction_files"]]
    assert instruction_paths == ["AGENTS.md", "README.md", "pyproject.toml"]
    assert context["instruction_files"][0]["preview"] == "Use focused tests.\n"

    recent_paths = [item["path"] for item in context["recent_modified_files"]]
    assert "newer.py" in recent_paths
    assert ".git/config" not in recent_paths
    assert "tests" in context["test_config"]["discovered_test_dirs"]
    assert context["test_config"]["pytest"]["source"] == "pyproject.toml"
    assert context["test_config"]["pytest"]["options"]["testpaths"] == ["tests"]
    assert context["test_config"]["suggested_commands"] == ["pytest tests"]


def test_repo_context_filters_paths_that_escape_workspace(tmp_path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    try:
        if os.name != "nt":
            (tmp_path / "escape.txt").symlink_to(outside)
        elif hasattr(os, "symlink"):
            try:
                (tmp_path / "escape.txt").symlink_to(outside)
            except OSError:
                pytest.skip("symlink creation is not available on this Windows host")
        else:
            pytest.skip("symlink creation is not available on this host")

        (tmp_path / "inside.py").write_text("inside = True\n", encoding="utf-8")

        context = build_repo_context(tmp_path)

        recent_paths = [item["path"] for item in context["recent_modified_files"]]
        assert "inside.py" in recent_paths
        assert "escape.txt" not in recent_paths
    finally:
        outside.unlink(missing_ok=True)


def test_repo_context_rejects_missing_workspace(tmp_path) -> None:
    with pytest.raises(ValueError, match="Workspace does not exist"):
        build_repo_context(tmp_path / "missing")


def _run(args: list[str], *, cwd) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    return completed
