"""Track D2 tests: completion contract (证据化完成判定).

Covers ``cli.evidence.build_completion_contract`` branches:
- completed run with a written file (created / modified actions)
- no-change runs (pure Q&A, no tool calls)
- fast-path runs (simple Q&A is NOT missing evidence)
- missing-evidence runs (file gone, syntax failure, write calls without
  captured file evidence, non-completed status)

Plus CLI integration: ``xagent agent run --contract <path>`` persists the
contract JSON and prints the evidence_complete verdict line.
"""

from __future__ import annotations

import json
import re
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from cli.config import CLIConfig
from cli.evidence import (
    build_completion_contract,
    save_completion_contract,
)
from cli.main import app, set_current_config

REQUIRED_KEYS = {
    "task",
    "trace_id",
    "status",
    "files_changed",
    "verifications",
    "evidence_complete",
    "missing_evidence",
}


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture(autouse=True)
def setup_config():
    set_current_config(
        CLIConfig(api_base_url="http://localhost:59999", mode="local", output_format="plain")
    )
    yield


def _write_result(path: str, previous_size=0, current_size=42, status="completed") -> dict:
    """Agent run result shape with one successful write_file call."""
    return {
        "trace_id": "trace-d2",
        "status": status,
        "task": "write a file",
        "iterations": 3,
        "tool_calls": [
            {
                "tool_name": "write_file",
                "success": True,
                "output": {
                    "path": path,
                    "written": True,
                    "previous_size": previous_size,
                    "current_size": current_size,
                },
                "arguments_preview": {"path": path},
            }
        ],
        "execution_summary": {
            "file_results": [{"tool": "write_file", "path": path, "success": True}],
            "affected_files": [path],
            "observations": ['{"verification": "passed", "tool": "write_file"}'],
        },
    }


def _fast_path_result(status="completed") -> dict:
    return {
        "trace_id": "trace-fast",
        "status": status,
        "task": "what is 2+2",
        "iterations": 1,
        "answer": "4",
        "tool_calls": [],
        "execution_summary": {"fast_path": True},
    }


class TestBuildCompletionContract:
    def test_contract_schema_keys(self, tmp_path):
        target = tmp_path / "hello.py"
        target.write_text("print('hello')\n", encoding="utf-8")
        contract = build_completion_contract(_write_result(str(target)))
        assert REQUIRED_KEYS <= set(contract.keys())
        file_keys = {"path", "action", "bytes_before", "bytes_after", "syntax_check"}
        assert file_keys <= set(contract["files_changed"][0].keys())

    def test_created_file_complete_evidence(self, tmp_path):
        target = tmp_path / "hello.py"
        target.write_text("print('hello')\n", encoding="utf-8")
        contract = build_completion_contract(_write_result(str(target)))
        assert contract["evidence_complete"] is True
        assert contract["missing_evidence"] == []
        entry = contract["files_changed"][0]
        assert entry["path"] == str(target)
        assert entry["action"] == "created"
        assert entry["bytes_before"] == 0
        assert entry["bytes_after"] == 42
        assert entry["syntax_check"] == "pass"
        # backend verification observation is carried into verifications
        assert any(v["path"] == "(backend)" for v in contract["verifications"])

    def test_modified_file_action(self, tmp_path):
        target = tmp_path / "mod.py"
        target.write_text("x = 1\n", encoding="utf-8")
        contract = build_completion_contract(
            _write_result(str(target), previous_size=100, current_size=6)
        )
        entry = contract["files_changed"][0]
        assert entry["action"] == "modified"
        assert entry["bytes_before"] == 100
        assert entry["bytes_after"] == 6
        assert contract["evidence_complete"] is True

    def test_non_py_file_syntax_skipped(self, tmp_path):
        target = tmp_path / "notes.txt"
        target.write_text("hello\n", encoding="utf-8")
        contract = build_completion_contract(_write_result(str(target)))
        assert contract["files_changed"][0]["syntax_check"] == "skipped"
        assert contract["evidence_complete"] is True

    def test_fast_path_is_complete(self):
        """Fast-path (simple Q&A) must NOT be reported as missing evidence."""
        contract = build_completion_contract(_fast_path_result())
        assert contract["evidence_complete"] is True
        assert contract["missing_evidence"] == []
        assert contract["files_changed"] == []

    def test_no_tool_calls_qa_is_complete(self):
        """Plain Q&A without fast_path flag and without tool calls is complete."""
        result = _fast_path_result()
        result["execution_summary"] = {}
        contract = build_completion_contract(result)
        assert contract["evidence_complete"] is True

    def test_missing_file_on_disk_is_incomplete(self, tmp_path):
        gone = tmp_path / "ghost.py"  # referenced but never created
        contract = build_completion_contract(_write_result(str(gone)))
        assert contract["evidence_complete"] is False
        assert any(str(gone) in m for m in contract["missing_evidence"])
        assert contract["files_changed"][0]["action"] == "missing"
        assert contract["files_changed"][0]["syntax_check"] == "fail"

    def test_syntax_failure_is_incomplete(self, tmp_path):
        target = tmp_path / "broken.py"
        target.write_text("def broken(:\n", encoding="utf-8")
        contract = build_completion_contract(_write_result(str(target)))
        assert contract["evidence_complete"] is False
        assert contract["files_changed"][0]["syntax_check"] == "fail"
        assert any("语法检查" in m for m in contract["missing_evidence"])

    def test_write_call_without_file_evidence_is_incomplete(self):
        result = {
            "trace_id": "t",
            "status": "completed",
            "task": "write something",
            "iterations": 2,
            "tool_calls": [
                {"tool_name": "write_file", "success": True, "arguments_preview": {}}
            ],
            "execution_summary": {},
        }
        contract = build_completion_contract(result)
        assert contract["evidence_complete"] is False
        assert any("未捕获到任何文件变更证据" in m for m in contract["missing_evidence"])

    def test_failed_status_is_incomplete(self, tmp_path):
        target = tmp_path / "hello.py"
        target.write_text("print('hello')\n", encoding="utf-8")
        contract = build_completion_contract(_write_result(str(target), status="failed"))
        assert contract["evidence_complete"] is False
        assert any("failed" in m for m in contract["missing_evidence"])

    def test_task_falls_back_to_result_task(self, tmp_path):
        target = tmp_path / "hello.py"
        target.write_text("print('hello')\n", encoding="utf-8")
        contract = build_completion_contract(_write_result(str(target)))
        assert contract["task"] == "write a file"
        contract2 = build_completion_contract(_write_result(str(target)), task="override")
        assert contract2["task"] == "override"


class TestSaveCompletionContract:
    def test_save_writes_json_with_all_keys(self, tmp_path):
        target = tmp_path / "hello.py"
        target.write_text("print('hello')\n", encoding="utf-8")
        contract = build_completion_contract(_write_result(str(target)))
        out = save_completion_contract(contract, tmp_path / "nested" / "contract.json")
        data = json.loads(out.read_text(encoding="utf-8"))
        assert REQUIRED_KEYS <= set(data.keys())
        assert data["trace_id"] == "trace-d2"
        assert data["evidence_complete"] is True


class TestAgentRunContractCLI:
    """CLI integration of --contract (mocked client, no real backend)."""

    def test_contract_written_and_verdict_printed(self, runner, tmp_path):
        target = tmp_path / "hello.py"
        target.write_text("print('hello')\n", encoding="utf-8")
        contract_path = tmp_path / "contract.json"

        mock_client = AsyncMock()
        mock_client.run_agent.return_value = _write_result(str(target))
        with patch("cli.commands.agent_cmd.create_client", return_value=mock_client):
            result = runner.invoke(
                app, ["agent", "run", "write a file", "--contract", str(contract_path)]
            )
        assert result.exit_code == 0, result.stdout
        data = json.loads(contract_path.read_text(encoding="utf-8"))
        assert REQUIRED_KEYS <= set(data.keys())
        assert data["evidence_complete"] is True
        plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
        assert "evidence_complete" in plain

    def test_fast_path_contract_complete(self, runner, tmp_path):
        contract_path = tmp_path / "contract.json"
        mock_client = AsyncMock()
        mock_client.run_agent.return_value = _fast_path_result()
        with patch("cli.commands.agent_cmd.create_client", return_value=mock_client):
            result = runner.invoke(
                app, ["agent", "run", "what is 2+2", "--contract", str(contract_path)]
            )
        assert result.exit_code == 0, result.stdout
        data = json.loads(contract_path.read_text(encoding="utf-8"))
        assert data["evidence_complete"] is True
        assert data["missing_evidence"] == []

    def test_missing_evidence_warns_in_terminal(self, runner, tmp_path):
        gone = tmp_path / "ghost.py"
        mock_client = AsyncMock()
        mock_client.run_agent.return_value = _write_result(str(gone))
        with patch("cli.commands.agent_cmd.create_client", return_value=mock_client):
            result = runner.invoke(app, ["agent", "run", "write a file"])
        plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
        assert "任务声明完成但缺少验证证据" in plain

    def test_headless_output_includes_contract(self, runner, tmp_path):
        contract_path = tmp_path / "contract.json"
        mock_client = AsyncMock()
        mock_client.run_agent.return_value = _fast_path_result()
        with patch("cli.commands.agent_cmd.create_client", return_value=mock_client):
            result = runner.invoke(
                app,
                ["agent", "run", "hi", "--headless", "--contract", str(contract_path)],
            )
        assert result.exit_code == 0, result.stdout
        output = json.loads(result.stdout)
        assert "completion_contract" in output
        assert output["completion_contract"]["evidence_complete"] is True
        assert output["contract_path"] == str(contract_path)
        assert contract_path.exists()
