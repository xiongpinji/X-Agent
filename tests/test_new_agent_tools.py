"""Unit tests for new agent tools: grep_code, detect_test_command, git/status API."""

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.core.contracts import RunContext
from backend.app.core.policy import ToolPolicyEngine
from backend.app.core.tools import build_default_tool_registry


def _make_registry():
    """Build a tool registry with all tools enabled."""
    return build_default_tool_registry(ToolPolicyEngine(enable_high_risk_tools=True))


def _ctx():
    return RunContext(tenant_id="test", user_id="tester", permission_scope=["tools:*"])


# ─── grep_code tool tests ─────────────────────────────────────────────────────


@pytest.fixture
def sample_project(tmp_path):
    """Create a small project structure for grep testing."""
    (tmp_path / "main.py").write_text(
        "import os\n\ndef hello(name: str) -> str:\n    return f'Hello {name}'\n\n\ndef goodbye(name: str) -> str:\n    return f'Bye {name}'\n",
        encoding="utf-8",
    )
    (tmp_path / "utils.py").write_text(
        "import os\nimport sys\n\ndef helper():\n    pass\n",
        encoding="utf-8",
    )
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "deep.py").write_text("def deep_func():\n    return 42\n", encoding="utf-8")
    # Binary file that should be skipped
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    return tmp_path


@pytest.mark.asyncio
async def test_grep_code_basic(sample_project):
    """grep_code finds matching lines with line numbers."""
    registry = _make_registry()
    record = await registry.execute(_ctx(), "grep_code", {"pattern": "def hello", "path": str(sample_project)})
    result = record.output

    assert record.success is True
    assert result["files_matched"] == 1
    assert result["matches"][0]["file"] == "main.py"
    assert result["matches"][0]["matches"][0]["line"] == 3
    assert "hello" in result["matches"][0]["matches"][0]["content"]


@pytest.mark.asyncio
async def test_grep_code_regex(sample_project):
    """grep_code supports regex patterns."""
    registry = _make_registry()
    record = await registry.execute(_ctx(), "grep_code", {"pattern": r"def \w+\(", "path": str(sample_project)})
    result = record.output

    assert record.success is True
    assert result["files_matched"] >= 2


@pytest.mark.asyncio
async def test_grep_code_file_glob(sample_project):
    """grep_code respects file_glob filter."""
    registry = _make_registry()
    record = await registry.execute(
        _ctx(), "grep_code", {"pattern": "import", "path": str(sample_project), "file_glob": "utils.py"}
    )
    result = record.output

    assert record.success is True
    assert result["files_matched"] == 1
    assert result["matches"][0]["file"] == "utils.py"


@pytest.mark.asyncio
async def test_grep_code_invalid_regex(sample_project):
    """grep_code returns error for invalid regex."""
    registry = _make_registry()
    record = await registry.execute(_ctx(), "grep_code", {"pattern": "[invalid", "path": str(sample_project)})
    result = record.output

    assert result["success"] is False
    assert "Invalid regex" in result["error"]


@pytest.mark.asyncio
async def test_grep_code_no_matches(sample_project):
    """grep_code returns empty matches when nothing found."""
    registry = _make_registry()
    record = await registry.execute(
        _ctx(), "grep_code", {"pattern": "zzz_nonexistent_zzz", "path": str(sample_project)}
    )
    result = record.output

    assert result["success"] is True
    assert result["files_matched"] == 0
    assert result["matches"] == []


# ─── detect_test_command tool tests ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_detect_test_command_python(tmp_path):
    """Detects Python project and returns pytest command."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")

    registry = _make_registry()
    record = await registry.execute(_ctx(), "detect_test_command", {"path": str(tmp_path)})
    result = record.output

    assert result["success"] is True
    assert len(result["detected"]) >= 1
    assert result["detected"][0]["language"] == "python"
    assert "pytest" in result["primary_command"]


@pytest.mark.asyncio
async def test_detect_test_command_node(tmp_path):
    """Detects Node.js project and returns test command."""
    (tmp_path / "package.json").write_text(
        '{"scripts": {"test": "vitest run"}}', encoding="utf-8"
    )

    registry = _make_registry()
    record = await registry.execute(_ctx(), "detect_test_command", {"path": str(tmp_path)})
    result = record.output

    assert result["success"] is True
    assert any(d["language"] == "javascript/typescript" for d in result["detected"])
    assert "vitest" in result["primary_command"]


@pytest.mark.asyncio
async def test_detect_test_command_rust(tmp_path):
    """Detects Rust project."""
    (tmp_path / "Cargo.toml").write_text("[package]\nname='test'\n", encoding="utf-8")

    registry = _make_registry()
    record = await registry.execute(_ctx(), "detect_test_command", {"path": str(tmp_path)})
    result = record.output

    assert result["success"] is True
    assert result["detected"][0]["language"] == "rust"
    assert result["primary_command"] == "cargo test"


@pytest.mark.asyncio
async def test_detect_test_command_empty(tmp_path):
    """Returns empty detected list for unknown project."""
    registry = _make_registry()
    record = await registry.execute(_ctx(), "detect_test_command", {"path": str(tmp_path)})
    result = record.output

    assert result["success"] is True
    assert result["detected"] == []
    assert result["primary_command"] is None


# ─── _trim_observation tests ──────────────────────────────────────────────────


def test_trim_observation_short():
    """Short text is not trimmed."""
    from backend.app.core.agent.loop import AgentLoop

    text = "Hello world"
    assert AgentLoop._trim_observation(text) == text


def test_trim_observation_long():
    """Long text is trimmed with head+tail preserved."""
    from backend.app.core.agent.loop import AgentLoop

    text = "A" * 10000
    result = AgentLoop._trim_observation(text, max_chars=1000)
    assert len(result) < 1100  # Slightly over due to separator
    assert "TRUNCATED" in result
    assert result.startswith("AAA")
    assert result.endswith("AAA")


def test_trim_observation_boundary():
    """Text exactly at max_chars is not trimmed."""
    from backend.app.core.agent.loop import AgentLoop

    text = "B" * 4000
    assert AgentLoop._trim_observation(text) == text
