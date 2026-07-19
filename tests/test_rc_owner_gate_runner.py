from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts import rc_owner_gate_runner
from scripts.rc_owner_gate_runner import build_owner_gate_runner


def _write_plan(path: Path, *, provider_command: str = "python scripts\\rc_external_smoke.py --provider deepseek") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": "action_required",
                "gates": [
                    {
                        "name": "provider",
                        "status": "ready_to_run",
                        "required_env_groups": [
                            ["XAGENT_LLM_BACKEND", "LLM_BACKEND"],
                            ["XAGENT_OLLAMA_MODEL", "OLLAMA_MODEL"],
                        ],
                        "command": provider_command,
                    },
                    {
                        "name": "feishu_webhook_contract",
                        "status": "action_required",
                        "required_env_groups": [
                            ["XAGENT_FEISHU_APP_ID", "FEISHU_APP_ID"],
                            ["XAGENT_FEISHU_APP_SECRET", "FEISHU_APP_SECRET"],
                            ["XAGENT_FEISHU_ENCRYPT_KEY", "FEISHU_ENCRYPT_KEY"],
                        ],
                        "command": "python scripts\\rc_external_smoke.py --check feishu_webhook_contract",
                    },
                    {
                        "name": "github_issue_to_pr_dry_run",
                        "status": "action_required",
                        "required_env_groups": [["XAGENT_GITHUB_TEST_ISSUE_URL", "GITHUB_TEST_ISSUE_URL"]],
                        "command": "python scripts\\rc_external_smoke.py --check github_issue_to_pr_dry_run",
                    },
                    {
                        "name": "github_issue_to_pr_execute_preflight",
                        "status": "action_required",
                        "required_env_groups": [
                            ["XAGENT_GITHUB_TOKEN", "GITHUB_TOKEN"],
                            ["XAGENT_GITHUB_TEST_ISSUE_URL", "GITHUB_TEST_ISSUE_URL"],
                        ],
                        "command": "python scripts\\rc_external_smoke.py --check github_issue_to_pr_execute_preflight",
                    },
                    {
                        "name": "hosted_github_actions_commercial_rc",
                        "status": "action_required",
                        "required_env_groups": [
                            ["XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL"],
                            ["XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA"],
                            ["XAGENT_GITHUB_TOKEN", "GITHUB_TOKEN"],
                        ],
                        "command": "python scripts\\rc_external_smoke.py --check hosted_github_actions_run",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_owner_gate_runner_dry_run_plans_allowlisted_steps(tmp_path: Path) -> None:
    plan = _write_plan(tmp_path / "rc-owner-gate-plan.json")

    report = build_owner_gate_runner(gate="provider", plan_path=plan, dry_run=True)

    assert report.status == "planned"
    assert report.steps[0].status == "planned"
    assert report.steps[0].command[0] == "python"
    assert report.steps[0].command[-6:] == [
        "scripts/rc_external_smoke.py",
        "--check",
        "provider",
        "--provider",
        "deepseek",
        "--require-configured",
    ]
    assert report.owner_gate_command[-6:] == [
        "scripts/rc_external_smoke.py",
        "--check",
        "provider",
        "--provider",
        "deepseek",
        "--require-configured",
    ]
    assert report.required_env_groups == [
        ["XAGENT_LLM_BACKEND", "LLM_BACKEND"],
        ["XAGENT_OLLAMA_MODEL", "OLLAMA_MODEL"],
    ]
    assert any(step.name == "refresh:rc_final_gate" for step in report.steps)


def test_owner_gate_runner_rejects_unknown_gate(tmp_path: Path) -> None:
    plan = _write_plan(tmp_path / "rc-owner-gate-plan.json")

    with pytest.raises(ValueError):
        build_owner_gate_runner(gate="rm -rf", plan_path=plan)


def test_owner_gate_runner_does_not_refresh_after_failed_smoke(tmp_path: Path, monkeypatch) -> None:
    plan = _write_plan(tmp_path / "rc-owner-gate-plan.json")
    monkeypatch.setenv("XAGENT_FEISHU_APP_ID", "cli_a_test")
    monkeypatch.setenv("XAGENT_FEISHU_APP_SECRET", "test-secret")
    monkeypatch.setenv("XAGENT_FEISHU_ENCRYPT_KEY", "encrypt-key")
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(list(command))
        return subprocess.CompletedProcess(command, 1, stdout="missing token", stderr="")

    monkeypatch.setattr(rc_owner_gate_runner.subprocess, "run", fake_run)

    report = build_owner_gate_runner(gate="feishu_webhook_contract", plan_path=plan)

    assert report.status == "failed"
    assert len(calls) == 1
    assert report.steps[0].name == "owner_gate:feishu_webhook_contract"


def test_owner_gate_runner_handles_missing_subprocess_output(tmp_path: Path, monkeypatch) -> None:
    plan = _write_plan(tmp_path / "rc-owner-gate-plan.json")
    monkeypatch.setenv("XAGENT_LLM_BACKEND", "ollama")
    monkeypatch.setenv("XAGENT_OLLAMA_MODEL", "qwen2.5:1.5b")

    def fake_run(command, **kwargs):  # noqa: ANN001
        return subprocess.CompletedProcess(command, 1, stdout=None, stderr=None)

    monkeypatch.setattr(rc_owner_gate_runner.subprocess, "run", fake_run)

    report = build_owner_gate_runner(gate="provider", plan_path=plan, refresh=False)

    assert report.status == "failed"
    assert report.steps[0].stdout_tail == []
    assert report.steps[0].stderr_tail == []
    assert report.steps[0].error == "command exited 1"


def test_owner_gate_runner_redacts_secret_like_subprocess_output(tmp_path: Path, monkeypatch) -> None:
    plan = _write_plan(tmp_path / "rc-owner-gate-plan.json")
    monkeypatch.setenv("XAGENT_LLM_BACKEND", "ollama")
    monkeypatch.setenv("XAGENT_OLLAMA_MODEL", "qwen2.5:1.5b")

    def fake_run(command, **kwargs):  # noqa: ANN001
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="XAGENT_GITHUB_TOKEN: ghp_" + ("a" * 40) + "\n",
            stderr="telegram_secret = should-not-leak\n",
        )

    monkeypatch.setattr(rc_owner_gate_runner.subprocess, "run", fake_run)

    report = build_owner_gate_runner(gate="provider", plan_path=plan, refresh=False)
    payload = json.dumps(report.to_dict())

    assert report.status == "failed"
    assert report.steps[0].stdout_tail == ["XAGENT_GITHUB_TOKEN: <redacted-output>"]
    assert report.steps[0].stderr_tail == ["telegram_secret = <redacted-output>"]
    assert "ghp_" not in payload
    assert "should-not-leak" not in payload


def test_owner_gate_runner_redacts_bare_token_shaped_output(tmp_path: Path, monkeypatch) -> None:
    plan = _write_plan(tmp_path / "rc-owner-gate-plan.json")
    monkeypatch.setenv("XAGENT_LLM_BACKEND", "ollama")
    monkeypatch.setenv("XAGENT_OLLAMA_MODEL", "qwen2.5:1.5b")

    def fake_run(command, **kwargs):  # noqa: ANN001
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="created token ghp_" + ("b" * 40) + "\n",
            stderr="provider returned sk-" + ("c" * 32) + "\n",
        )

    monkeypatch.setattr(rc_owner_gate_runner.subprocess, "run", fake_run)

    report = build_owner_gate_runner(gate="provider", plan_path=plan, refresh=False)
    payload = json.dumps(report.to_dict())

    assert report.status == "failed"
    assert report.steps[0].stdout_tail == ["created token <redacted-secret>"]
    assert report.steps[0].stderr_tail == ["provider returned <redacted-secret>"]
    assert "ghp_" not in payload
    assert "sk-" not in payload


def test_owner_gate_runner_refreshes_after_passed_smoke(tmp_path: Path, monkeypatch) -> None:
    plan = _write_plan(tmp_path / "rc-owner-gate-plan.json", provider_command="python scripts\\rc_external_smoke.py --provider ollama")
    monkeypatch.setenv("XAGENT_LLM_BACKEND", "ollama")
    monkeypatch.setenv("XAGENT_OLLAMA_MODEL", "qwen2.5:1.5b")
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(list(command))
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(rc_owner_gate_runner.subprocess, "run", fake_run)

    report = build_owner_gate_runner(gate="provider", plan_path=plan)

    assert report.status == "passed"
    assert len(calls) == 1 + len(rc_owner_gate_runner.REFRESH_COMMANDS)
    assert calls[0][-6:] == [
        "scripts/rc_external_smoke.py",
        "--check",
        "provider",
        "--provider",
        "ollama",
        "--require-configured",
    ]
    assert any(step.name == "refresh:rc_owner_handoff_gate" for step in report.steps)


def test_owner_gate_runner_loads_non_placeholder_env_file_values(tmp_path: Path, monkeypatch) -> None:
    plan = _write_plan(tmp_path / "rc-owner-gate-plan.json")
    env_file = tmp_path / "owner.env"
    env_file.write_text(
        "\n".join(
            [
                "# filled owner env",
                'XAGENT_GITHUB_TEST_ISSUE_URL="https://github.com/example-org/example-repo/issues/1"',
                'XAGENT_GITHUB_TOKEN="<set-in-owner-secret-store>"',
                'XAGENT_OLLAMA_MODEL="qwen2.5:1.5b"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    calls: list[dict[str, object]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append({"command": list(command), "env": dict(kwargs["env"])})
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(rc_owner_gate_runner.subprocess, "run", fake_run)

    report = build_owner_gate_runner(
        gate="github_issue_to_pr_dry_run",
        plan_path=plan,
        refresh=False,
        env_file_path=env_file,
    )

    assert report.status == "passed"
    assert report.env_file == "owner.env"
    assert report.loaded_env_names == ["XAGENT_GITHUB_TEST_ISSUE_URL", "XAGENT_OLLAMA_MODEL"]
    assert report.unresolved_env_names == ["XAGENT_GITHUB_TOKEN"]
    assert report.owner_gate_env_names == ["XAGENT_GITHUB_TEST_ISSUE_URL"]
    assert report.owner_gate_unresolved_env_names == []
    assert report.missing_env_groups == []
    assert calls[0]["env"]["XAGENT_GITHUB_TEST_ISSUE_URL"] == "https://github.com/example-org/example-repo/issues/1"
    assert calls[0]["env"].get("XAGENT_OLLAMA_MODEL") != "qwen2.5:1.5b"
    assert calls[0]["env"].get("XAGENT_GITHUB_TOKEN") != "<set-in-owner-secret-store>"


def test_owner_gate_runner_reports_selected_gate_placeholder_env_values(tmp_path: Path) -> None:
    plan = _write_plan(tmp_path / "rc-owner-gate-plan.json")
    env_file = tmp_path / "owner.env"
    env_file.write_text(
        "\n".join(
            [
                'XAGENT_GITHUB_TEST_ISSUE_URL="https://github.com/example-org/example-repo/issues/1"',
                'XAGENT_GITHUB_TOKEN="<set-in-owner-secret-store>"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = build_owner_gate_runner(
        gate="github_issue_to_pr_execute_preflight",
        plan_path=plan,
        refresh=False,
        env_file_path=env_file,
    )

    assert report.status == "failed"
    assert report.loaded_env_names == ["XAGENT_GITHUB_TEST_ISSUE_URL"]
    assert report.unresolved_env_names == ["XAGENT_GITHUB_TOKEN"]
    assert report.owner_gate_env_names == ["XAGENT_GITHUB_TEST_ISSUE_URL"]
    assert report.owner_gate_unresolved_env_names == ["XAGENT_GITHUB_TOKEN"]
    assert report.missing_env_groups == [["XAGENT_GITHUB_TOKEN", "GITHUB_TOKEN"]]
    assert "Replace owner env template placeholder values for: XAGENT_GITHUB_TOKEN." in report.next_commands
    assert report.steps[0].name == "env_preflight"


def test_owner_gate_runner_report_does_not_leak_absolute_env_file_path(tmp_path: Path, monkeypatch) -> None:
    plan = _write_plan(tmp_path / "rc-owner-gate-plan.json")
    env_file = tmp_path / "private" / "owner.env"
    env_file.parent.mkdir()
    env_file.write_text(
        'XAGENT_GITHUB_TEST_ISSUE_URL="https://github.com/example-org/example-repo/issues/1"\n',
        encoding="utf-8",
    )

    def fake_run(command, **kwargs):  # noqa: ANN001
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(rc_owner_gate_runner.subprocess, "run", fake_run)

    report = build_owner_gate_runner(
        gate="github_issue_to_pr_dry_run",
        plan_path=plan,
        refresh=False,
        env_file_path=env_file,
    )
    payload = json.dumps(report.to_dict())

    assert report.status == "passed"
    assert report.env_file == "owner.env"
    assert str(tmp_path) not in payload


def test_owner_gate_runner_scopes_env_file_values_to_selected_gate(tmp_path: Path, monkeypatch) -> None:
    plan = _write_plan(tmp_path / "rc-owner-gate-plan.json")
    env_file = tmp_path / "owner.env"
    env_file.write_text(
        "\n".join(
            [
                'XAGENT_GITHUB_TEST_ISSUE_URL="https://github.com/example-org/example-repo/issues/1"',
                'XAGENT_GITHUB_TOKEN="scope-test"',
                'XAGENT_OLLAMA_MODEL="qwen2.5:1.5b"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    calls: list[dict[str, object]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append({"command": list(command), "env": dict(kwargs["env"])})
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(rc_owner_gate_runner.subprocess, "run", fake_run)

    report = build_owner_gate_runner(
        gate="github_issue_to_pr_dry_run",
        plan_path=plan,
        refresh=False,
        env_file_path=env_file,
    )

    assert report.status == "passed"
    assert report.loaded_env_names == [
        "XAGENT_GITHUB_TEST_ISSUE_URL",
        "XAGENT_GITHUB_TOKEN",
        "XAGENT_OLLAMA_MODEL",
    ]
    assert report.owner_gate_env_names == ["XAGENT_GITHUB_TEST_ISSUE_URL"]
    assert report.missing_env_groups == []
    assert calls[0]["env"]["XAGENT_GITHUB_TEST_ISSUE_URL"] == "https://github.com/example-org/example-repo/issues/1"
    assert calls[0]["env"].get("XAGENT_GITHUB_TOKEN") != "scope-test"
    assert calls[0]["env"].get("XAGENT_OLLAMA_MODEL") != "qwen2.5:1.5b"


def test_owner_gate_runner_rejects_invalid_env_file_lines(tmp_path: Path) -> None:
    plan = _write_plan(tmp_path / "rc-owner-gate-plan.json")
    env_file = tmp_path / "owner.env"
    env_file.write_text("not-a-valid-env-line\n", encoding="utf-8")

    report = build_owner_gate_runner(
        gate="provider",
        plan_path=plan,
        refresh=False,
        env_file_path=env_file,
    )

    assert report.status == "failed"
    assert report.steps[0].name == "env_file"
    assert "not KEY=value" in str(report.steps[0].error)


def test_owner_gate_runner_rejects_empty_env_file_variable_name(tmp_path: Path) -> None:
    plan = _write_plan(tmp_path / "rc-owner-gate-plan.json")
    env_file = tmp_path / "owner.env"
    env_file.write_text("=value\n", encoding="utf-8")

    report = build_owner_gate_runner(
        gate="provider",
        plan_path=plan,
        refresh=False,
        env_file_path=env_file,
    )

    assert report.status == "failed"
    assert report.steps[0].name == "env_file"
    assert "invalid variable name" in str(report.steps[0].error)


def test_owner_gate_runner_rejects_env_names_not_declared_in_plan(tmp_path: Path) -> None:
    plan = _write_plan(tmp_path / "rc-owner-gate-plan.json")
    env_file = tmp_path / "owner.env"
    env_file.write_text("PYTHONPATH=\"C:\\\\unsafe\"\n", encoding="utf-8")

    report = build_owner_gate_runner(
        gate="provider",
        plan_path=plan,
        refresh=False,
        env_file_path=env_file,
    )

    assert report.status == "failed"
    assert report.steps[0].name == "env_file"
    assert "not allowed by owner gate plan: PYTHONPATH" in str(report.steps[0].error)


def test_owner_gate_runner_github_dry_run_does_not_require_execute_preflight(tmp_path: Path) -> None:
    plan = _write_plan(tmp_path / "rc-owner-gate-plan.json")

    report = build_owner_gate_runner(gate="github_issue_to_pr_dry_run", plan_path=plan, dry_run=True, refresh=False)

    command = report.steps[0].command
    assert "--check" in command
    assert "github_issue_to_pr_dry_run" in command
    assert "--require-configured" in command
    assert "--github-execute-preflight" not in command


def test_owner_gate_runner_reports_missing_env_groups_without_values(tmp_path: Path, monkeypatch) -> None:
    plan = _write_plan(tmp_path / "rc-owner-gate-plan.json")
    for name in (
        "XAGENT_GITHUB_TOKEN",
        "GITHUB_TOKEN",
        "XAGENT_GITHUB_TEST_ISSUE_URL",
        "GITHUB_TEST_ISSUE_URL",
    ):
        monkeypatch.delenv(name, raising=False)

    report = build_owner_gate_runner(
        gate="github_issue_to_pr_execute_preflight",
        plan_path=plan,
        dry_run=True,
        refresh=False,
    )

    assert report.status == "planned"
    assert ["XAGENT_GITHUB_TOKEN", "GITHUB_TOKEN"] in report.missing_env_groups
    assert ["XAGENT_GITHUB_TEST_ISSUE_URL", "GITHUB_TEST_ISSUE_URL"] in report.missing_env_groups
    payload = json.dumps(report.to_dict())
    assert "missing_env_groups" in payload
    assert "scope-test" not in payload


def test_owner_gate_runner_reports_remaining_missing_env_groups_after_env_file(tmp_path: Path, monkeypatch) -> None:
    plan = _write_plan(tmp_path / "rc-owner-gate-plan.json")
    env_file = tmp_path / "owner.env"
    env_file.write_text(
        'XAGENT_GITHUB_TEST_ISSUE_URL="https://github.com/example-org/example-repo/issues/1"\n',
        encoding="utf-8",
    )
    for name in ("XAGENT_GITHUB_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(name, raising=False)

    report = build_owner_gate_runner(
        gate="github_issue_to_pr_execute_preflight",
        plan_path=plan,
        dry_run=True,
        refresh=False,
        env_file_path=env_file,
    )

    assert report.missing_env_groups == [["XAGENT_GITHUB_TOKEN", "GITHUB_TOKEN"]]


def test_owner_gate_runner_non_dry_run_fails_fast_when_required_env_groups_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan = _write_plan(tmp_path / "rc-owner-gate-plan.json")
    for name in ("XAGENT_LLM_BACKEND", "LLM_BACKEND", "XAGENT_OLLAMA_MODEL", "OLLAMA_MODEL"):
        monkeypatch.delenv(name, raising=False)

    def fake_run(command, **kwargs):  # noqa: ANN001
        raise AssertionError("owner gate smoke should not run when env preflight fails")

    monkeypatch.setattr(rc_owner_gate_runner.subprocess, "run", fake_run)

    report = build_owner_gate_runner(gate="provider", plan_path=plan, refresh=False)

    assert report.status == "failed"
    assert report.steps[0].name == "env_preflight"
    assert report.steps[0].command == ["owner_gate_env_preflight"]
    assert report.steps[0].returncode is None
    assert "XAGENT_LLM_BACKEND/LLM_BACKEND" in str(report.steps[0].error)
    assert "XAGENT_OLLAMA_MODEL/OLLAMA_MODEL" in str(report.steps[0].error)
    assert report.missing_env_groups == [
        ["XAGENT_LLM_BACKEND", "LLM_BACKEND"],
        ["XAGENT_OLLAMA_MODEL", "OLLAMA_MODEL"],
    ]
    assert report.required_env_groups == report.missing_env_groups
    assert any("XAGENT_LLM_BACKEND/LLM_BACKEND" in command for command in report.next_commands)
    assert any("python scripts\\rc_owner_gate_runner.py --gate provider" in command for command in report.next_commands)


def test_owner_gate_runner_execute_preflight_includes_dry_run_and_execute_checks(tmp_path: Path) -> None:
    plan = _write_plan(tmp_path / "rc-owner-gate-plan.json")

    report = build_owner_gate_runner(gate="github_issue_to_pr_execute_preflight", plan_path=plan, dry_run=True, refresh=False)

    command = report.steps[0].command
    assert "github_issue_to_pr_dry_run" in command
    assert "github_issue_to_pr_execute_preflight" in command
    assert "--github-execute-preflight" in command


def test_owner_gate_runner_all_gate_includes_actions_preflight(tmp_path: Path) -> None:
    plan = _write_plan(tmp_path / "rc-owner-gate-plan.json", provider_command="python scripts\\rc_external_smoke.py --provider openai")

    report = build_owner_gate_runner(gate="all", plan_path=plan, dry_run=True, refresh=False)

    command = report.steps[0].command
    assert "--provider" in command
    assert "openai" in command
    assert "--telegram-live-preflight" not in command
    assert "--github-execute-preflight" in command
    assert "--github-actions-preflight" in command
    assert "--require-configured" in command
