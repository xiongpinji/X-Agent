"""Track B2 CLI tests: local tools list, doctor, health diagnostics, evidence.

Covers:
- ``xagent tools list --mode local`` (and global ``--mode local``)
- ``LocalClient.list_tools`` reading the runtime ToolRegistry manifest
- ``xagent doctor`` checks (pass/warn/fail semantics + suggestions)
- ``xagent health`` no-service diagnostic text
- ``cli.evidence.build_evidence`` completion-evidence extraction
"""

from __future__ import annotations

import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


def _plain(text: str) -> str:
    """Strip ANSI escape sequences and collapse whitespace for assertions."""
    return re.sub(r"\s+", " ", re.sub(r"\x1b\[[0-9;]*m", "", text))

import pytest
from typer.testing import CliRunner

from cli.client import LocalClient
from cli.config import CLIConfig
from cli.main import app, set_current_config


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def local_config():
    return CLIConfig(
        api_base_url="http://localhost:59999",  # dead port: nothing listening
        mode="local",
        output_format="plain",
    )


@pytest.fixture(autouse=True)
def setup_config(local_config):
    set_current_config(local_config)
    yield


SAMPLE_MANIFEST = [
    {
        "name": "read_file",
        "description": "Read a text file from disk.",
        "risk_level": "low",
        "required_scope": "tool:read_file",
        "parameters": {"type": "object"},
    },
    {
        "name": "write_file",
        "description": "Write a text file to disk with optional backup.",
        "risk_level": "high",
        "required_scope": "tool:write_file",
        "parameters": {"type": "object"},
    },
]


class TestLocalToolsList:
    """tools list must work in local mode with the same shape as HTTP mode."""

    def test_local_client_list_tools_reads_registry_manifest(self, local_config):
        """LocalClient.list_tools returns agent.tools.manifest()."""
        client = LocalClient(local_config)
        client._initialized = True
        client._agent = SimpleNamespace(
            tools=SimpleNamespace(manifest=lambda: SAMPLE_MANIFEST)
        )

        import asyncio

        tools = asyncio.run(client.list_tools())
        assert tools == SAMPLE_MANIFEST
        names = {t["name"] for t in tools}
        assert {"read_file", "write_file"} <= names
        # Same shape as HTTP mode (manifest keys).
        for tool in tools:
            assert {"name", "description", "risk_level", "required_scope"} <= set(tool)

    def test_tools_list_local_mode_cli(self, runner):
        """xagent --mode local tools list prints the tool table, exit 0."""
        mock_client = AsyncMock()
        mock_client.list_tools.return_value = SAMPLE_MANIFEST

        with patch("cli.commands.tools_cmd.create_client", return_value=mock_client):
            result = runner.invoke(app, ["--mode", "local", "tools", "list"])
        assert result.exit_code == 0, result.stdout
        assert "read_file" in result.stdout
        assert "write_file" in result.stdout
        assert "high" in result.stdout  # risk level column
        assert "not yet supported" not in result.stdout

    def test_tools_list_mode_option_after_subcommand(self, runner):
        """--mode is accepted after the subcommand too (codex-style)."""
        mock_client = AsyncMock()
        mock_client.list_tools.return_value = SAMPLE_MANIFEST

        with patch("cli.commands.tools_cmd.create_client", return_value=mock_client):
            result = runner.invoke(app, ["tools", "list", "--mode", "local"])
        assert result.exit_code == 0, result.stdout
        assert "read_file" in result.stdout

    def test_tools_list_invalid_mode_option(self, runner):
        result = runner.invoke(app, ["tools", "list", "--mode", "bogus"])
        assert result.exit_code == 2


class TestDoctorCommand:
    """xagent doctor self-checks."""

    def test_run_doctor_checks_covers_all_items(self):
        from cli.commands.doctor import run_doctor_checks

        checks = run_doctor_checks()
        names = [c.name for c in checks]
        assert names == [
            "python_version",
            "backend_import",
            "database_url",
            "llm_keys",
            "playwright",
            "sandbox_subprocess",
            "data_dir_writable",
        ]
        for check in checks:
            assert check.status in {"pass", "warn", "fail"}
            if check.status != "pass":
                assert check.suggestion, f"{check.name} lacks fix suggestion"

    def test_doctor_cli_outputs_all_checks(self, runner):
        result = runner.invoke(app, ["doctor"])
        # Warnings allowed -> exit 0; failures -> exit 1. Either way all
        # check items must be printed.
        assert result.exit_code in (0, 1), result.stdout
        for name in (
            "python_version",
            "backend_import",
            "database_url",
            "llm_keys",
            "playwright",
            "sandbox_subprocess",
            "data_dir_writable",
        ):
            assert name in result.stdout

    def test_doctor_sqlite_without_aiosqlite_fails(self):
        from cli.commands import doctor as doctor_mod

        fake = SimpleNamespace(database_url="sqlite:///./data/xagent.db")
        with patch.object(doctor_mod, "_load_settings", return_value=(fake, None)):
            check = doctor_mod._check_database_url()
        assert check.status == "fail"
        assert "aiosqlite" in check.suggestion

    def test_doctor_sqlite_with_aiosqlite_passes(self):
        from cli.commands import doctor as doctor_mod

        fake = SimpleNamespace(database_url="sqlite+aiosqlite:///./data/xagent.db")
        with patch.object(doctor_mod, "_load_settings", return_value=(fake, None)):
            check = doctor_mod._check_database_url()
        assert check.status == "pass"

    def test_doctor_llm_keys_missing_fails(self):
        from cli.commands import doctor as doctor_mod

        fake = SimpleNamespace(
            deepseek_api_key=None,
            openai_api_key=None,
            anthropic_api_key=None,
            llm_backend="deepseek",
        )
        with patch.object(doctor_mod, "_load_settings", return_value=(fake, None)):
            check = doctor_mod._check_llm_keys()
        assert check.status == "fail"
        assert "XAGENT_DEEPSEEK_API_KEY" in check.suggestion

    def test_doctor_llm_keys_mock_backend_warns(self):
        from cli.commands import doctor as doctor_mod

        fake = SimpleNamespace(
            deepseek_api_key=None,
            openai_api_key=None,
            anthropic_api_key=None,
            llm_backend="mock",
        )
        with patch.object(doctor_mod, "_load_settings", return_value=(fake, None)):
            check = doctor_mod._check_llm_keys()
        assert check.status == "warn"

    def test_doctor_llm_keys_configured_passes(self):
        from cli.commands import doctor as doctor_mod

        fake = SimpleNamespace(
            deepseek_api_key="sk-test",
            openai_api_key=None,
            anthropic_api_key=None,
            llm_backend="deepseek",
        )
        with patch.object(doctor_mod, "_load_settings", return_value=(fake, None)):
            check = doctor_mod._check_llm_keys()
        assert check.status == "pass"
        assert "deepseek" in check.message


class TestHealthDiagnostics:
    """health must give actionable diagnostics when no service is running."""

    def test_health_connection_failure_shows_startup_hint(self, runner):
        mock_client = AsyncMock()
        mock_client.health_check.return_value = {
            "status": "unhealthy",
            "error": "Failed to connect to http://localhost:59999: All connection attempts failed",
            "hint": "无法连接 http://localhost:59999，请先启动服务: uvicorn backend.app.main:app --port 8000",
        }
        with patch("cli.client.create_client", return_value=mock_client):
            result = runner.invoke(app, ["health"])
        assert result.exit_code == 1
        out = _plain(result.stdout)
        assert "无法连接" in out
        assert "uvicorn backend.app.main:app --port 8000" in out
        # No unhelpful "Unknown error" / swallowed typer.Exit double message.
        assert "Unknown error" not in out
        assert "Health check failed:" not in out

    def test_health_unhealthy_without_error_key_is_readable(self, runner):
        mock_client = AsyncMock()
        mock_client.health_check.return_value = {"status": "weird"}
        with patch("cli.client.create_client", return_value=mock_client):
            result = runner.invoke(app, ["health"])
        assert result.exit_code == 1
        assert "no status reported" in result.stdout

    def test_health_ok_status_treated_healthy(self, runner):
        """Backend /health returns {"status": "ok"} — must count as healthy."""
        mock_client = AsyncMock()
        mock_client.health_check.return_value = {"status": "healthy", "service": "x-agent"}
        with patch("cli.client.create_client", return_value=mock_client):
            result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        assert "healthy" in result.stdout.lower()

    def test_health_mode_override_local(self, runner):
        mock_client = AsyncMock()
        mock_client.health_check.return_value = {"status": "healthy", "mode": "local"}
        with patch("cli.client.create_client", return_value=mock_client):
            result = runner.invoke(app, ["health", "--mode", "local"])
        assert result.exit_code == 0


class TestEvidence:
    """cli.evidence completion-evidence extraction."""

    def _result(self, path: str) -> dict:
        return {
            "trace_id": "trace-b2",
            "status": "completed",
            "iterations": 3,
            "tool_calls": [
                {
                    "tool_name": "write_file",
                    "success": True,
                    "output": {"path": path, "written": True, "previous_size": 0, "current_size": 42},
                    "arguments_preview": {"path": path},
                }
            ],
            "execution_summary": {
                "file_results": [{"tool": "write_file", "path": path, "success": True}],
                "affected_files": [path],
                "observations": ['{"verification": "passed", "tool": "write_file"}'],
            },
        }

    def test_build_evidence_extracts_files_and_trace(self, tmp_path):
        from cli.evidence import build_evidence

        target = tmp_path / "hello.py"
        target.write_text("print('hello')\n", encoding="utf-8")

        evidence = build_evidence(self._result(str(target)))
        assert evidence["trace_id"] == "trace-b2"
        assert evidence["status"] == "completed"
        assert len(evidence["changed_files"]) == 1
        entry = evidence["changed_files"][0]
        assert entry["path"] == str(target)
        assert entry["tool"] == "write_file"
        assert entry["size_change"] == "0 -> 42 bytes"
        checks = {(v["check"], v["passed"]) for v in evidence["verification"]}
        assert ("exists", True) in checks
        assert ("syntax", True) in checks
        assert evidence["backend_verification"]

    def test_build_evidence_syntax_failure_detected(self, tmp_path):
        from cli.evidence import build_evidence

        target = tmp_path / "broken.py"
        target.write_text("def broken(:\n", encoding="utf-8")

        evidence = build_evidence(self._result(str(target)))
        syntax = [v for v in evidence["verification"] if v["check"] == "syntax"]
        assert syntax and syntax[0]["passed"] is False

    def test_build_evidence_fast_path_no_changes(self):
        from cli.evidence import build_evidence

        result = {
            "trace_id": "t",
            "status": "completed",
            "iterations": 1,
            "tool_calls": [],
            "execution_summary": {"fast_path": True},
        }
        evidence = build_evidence(result)
        assert evidence["fast_path"] is True
        assert evidence["changed_files"] == []
        assert evidence["verification"] == []

    def test_agent_run_headless_includes_evidence(self, runner):
        mock_client = AsyncMock()
        mock_client.run_agent.return_value = {
            "trace_id": "trace-headless",
            "status": "completed",
            "answer": "done",
            "iterations": 1,
            "tool_calls": [],
            "execution_summary": {"fast_path": True},
        }
        with patch("cli.commands.agent_cmd.create_client", return_value=mock_client):
            result = runner.invoke(app, ["agent", "run", "say hi", "--headless"])
        assert result.exit_code == 0, result.stdout
        import json

        payload = json.loads(result.stdout)
        assert payload["trace_id"] == "trace-headless"
        assert payload["evidence"]["fast_path"] is True
        assert payload["evidence"]["trace_id"] == "trace-headless"
