from __future__ import annotations

import json
import subprocess

from scripts.original_kernel_context_integration_report import build_report, write_report


async def test_context_integration_report_is_ready_for_temp_repo(tmp_path) -> None:
    _prepare_workspace(tmp_path)

    report = await build_report(
        workspace_root=tmp_path,
        task="Validate context module contracts for a temporary workspace.",
    )

    assert report["status"] == "original_kernel_context_integration_ready"
    assert report["evidence_type"] == "original_kernel_context_integration"
    assert report["modules"] == ["repo_context", "context_pack"]
    assert report["entrypoints_modified"] is False
    assert report["api_router_modified"] is False
    assert report["control_plane_modified"] is False
    assert report["frontend_modified"] is False
    assert report["agent_loop_modified"] is False
    assert report["backend_core_init_modified"] is False
    assert report["mutation_performed"] is False
    assert report["report_file_written"] is False
    assert report["local_workspace_read_performed"] is True
    assert report["local_git_status_read_performed"] is True
    assert report["network_mutation_performed"] is False
    assert report["agent_execution_enabled"] is False
    assert report["command_execution_enabled"] is False
    assert report["write_runner_invoked"] is False

    checks = {check["name"]: check for check in report["checks"]}
    assert checks["repo_context_contract"]["status"] == "passed"
    assert checks["repo_context_contract"]["details"]["git_is_repo"] is True
    assert checks["context_pack_contract"]["status"] == "passed"
    assert checks["context_pack_contract"]["details"]["memory_hit_count"] == 1
    assert checks["context_pack_contract"]["details"]["repo_available"] is True
    assert "AGENTS.md" in report["artifacts"]["repo_context"]["instruction_files"]
    assert "continue_task" in report["artifacts"]["context_pack"]["restore_plan"]


async def test_context_integration_write_report_records_report_file_only(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _prepare_workspace(workspace)
    output = tmp_path / "original-kernel-context-integration.json"

    report = await write_report(output, workspace_root=workspace, task="Write context report.")

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload == report
    assert payload["status"] == "original_kernel_context_integration_ready"
    assert payload["report_file_written"] is True
    assert payload["report_path"] == str(output)
    assert payload["mutation_performed"] is False
    assert payload["network_mutation_performed"] is False
    assert payload["agent_execution_enabled"] is False
    assert payload["command_execution_enabled"] is False


def _prepare_workspace(workspace) -> None:
    _run(["git", "init"], cwd=workspace)
    (workspace / "AGENTS.md").write_text("Use focused validation.\n", encoding="utf-8")
    (workspace / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\n"
        "testpaths = ['tests']\n",
        encoding="utf-8",
    )
    (workspace / "backend" / "app" / "core").mkdir(parents=True)
    (workspace / "backend" / "app" / "core" / "demo.py").write_text(
        "def run():\n    return 'ok'\n",
        encoding="utf-8",
    )
    (workspace / "tests").mkdir()
    (workspace / "tests" / "test_demo.py").write_text(
        "def test_demo():\n    assert True\n",
        encoding="utf-8",
    )


def _run(args: list[str], *, cwd) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    return completed
