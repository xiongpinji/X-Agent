from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import rc_refresh_release_chain
from scripts.rc_refresh_release_chain import build_refresh_chain, write_report


def test_refresh_chain_dry_run_plans_dependency_order() -> None:
    report = build_refresh_chain(provider="ollama", dry_run=True)

    assert report.status == "planned"
    assert [step.name for step in report.steps] == [
        "release_audit",
        "staging_plan",
        "source_bundle",
        "artifact_integrity_gate",
        "external_smoke",
        "owner_gate_plan",
        "owner_env_template",
        "owner_gate_runner_dry_run",
        "owner_gate_checklist",
        "owner_handoff_gate",
        "ci_contract",
        "release_diff_review_gate",
        "deployment_docs_gate_bootstrap",
        "install_release_gate",
        "supply_chain_gate",
        "secrets_gate",
        "final_gate_bootstrap",
        "release_receipt",
        "final_gate",
        "evidence_pack",
        "deployment_docs_gate",
        "final_gate_after_docs",
        "release_receipt_after_docs",
        "final_gate_after_receipt",
        "evidence_pack_after_receipt",
        "final_gate_final",
        "evidence_pack_final",
    ]
    assert all(step.status == "planned" for step in report.steps)
    assert all(step.command[0] == "python" for step in report.steps)
    assert report.owner_verified is False
    assert report.steps[0].command[-1] == "--manifest-candidates"
    assert report.steps[4].command[-2:] == ["--provider", "ollama"]
    assert report.steps[5].command[-2:] == ["--provider", "ollama"]
    for step_name in ("final_gate_bootstrap", "final_gate", "final_gate_after_docs", "final_gate_after_receipt"):
        command = next(step.command for step in report.steps if step.name == step_name)
        assert "--allow-missing-evidence-pack" in command
    final_command = next(step.command for step in report.steps if step.name == "final_gate_final")
    assert "--allow-missing-evidence-pack" not in final_command
    runner_command = next(step.command for step in report.steps if step.name == "owner_gate_runner_dry_run")
    assert "--env-file" in runner_command
    assert ".xagent_runtime/reports/rc-owner-env-template.env" in runner_command
    supply_command = next(step.command for step in report.steps if step.name == "supply_chain_gate")
    assert supply_command[-1] == "scripts/rc_supply_chain_gate.py"


def test_refresh_chain_mock_provider_does_not_force_provider_flag() -> None:
    report = build_refresh_chain(provider="mock", dry_run=True)

    external_command = next(step.command for step in report.steps if step.name == "external_smoke")
    owner_plan_command = next(step.command for step in report.steps if step.name == "owner_gate_plan")
    assert "--provider" not in external_command
    assert "--provider" not in owner_plan_command


def test_refresh_chain_owner_verified_uses_strict_external_smoke() -> None:
    report = build_refresh_chain(provider="ollama", dry_run=True, owner_verified=True)

    external_command = next(step.command for step in report.steps if step.name == "external_smoke")

    assert report.owner_verified is True
    assert external_command == [
        "python",
        "scripts/rc_external_smoke.py",
        "--check",
        "provider",
        "--check",
        "feishu_webhook_contract",
        "--check",
        "github_issue_to_pr_dry_run",
        "--check",
        "github_issue_to_pr_execute_preflight",
        "--check",
        "hosted_github_actions_run",
        "--require-configured",
        "--github-execute-preflight",
        "--github-actions-preflight",
        "--provider",
        "ollama",
    ]


def test_refresh_chain_owner_verified_rejects_mock_provider() -> None:
    with pytest.raises(ValueError, match="non-mock provider"):
        build_refresh_chain(provider="mock", dry_run=True, owner_verified=True)


def test_refresh_chain_non_owner_mode_refuses_to_overwrite_verified_owner_external_smoke(
    tmp_path: Path,
    monkeypatch,
) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "rc-external-smoke.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "require_configured": True,
                "checks": [
                    {"name": "provider", "status": "passed"},
                    {"name": "feishu_webhook_contract", "status": "passed"},
                    {"name": "github_issue_to_pr_dry_run", "status": "passed"},
                    {"name": "github_issue_to_pr_execute_preflight", "status": "passed"},
                    {"name": "hosted_github_actions_run", "status": "passed"},
                ],
            }
        ),
        encoding="utf-8",
    )
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(list(command))
        return subprocess.CompletedProcess(command, 0, stdout=b"ok", stderr=b"")

    monkeypatch.setattr(rc_refresh_release_chain, "REPORT_DIR", reports)
    monkeypatch.setattr(rc_refresh_release_chain.subprocess, "run", fake_run)

    report = build_refresh_chain(provider="ollama", timeout_seconds=1)

    assert report.status == "failed"
    assert report.steps == [
        rc_refresh_release_chain.RefreshStep(
            name="owner_evidence_guard",
            command=["python", "scripts/rc_refresh_release_chain.py", "--owner-verified"],
            status="failed",
            returncode=None,
            error=report.steps[0].error,
        )
    ]
    assert "would be overwritten" in str(report.steps[0].error)
    assert calls == []


def test_refresh_chain_passes_provider_env_overrides(monkeypatch) -> None:
    captured_envs: list[dict[str, str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        captured_envs.append(dict(kwargs["env"]))
        return subprocess.CompletedProcess(command, 0, stdout=b"ok", stderr=b"")

    monkeypatch.setattr(rc_refresh_release_chain.subprocess, "run", fake_run)

    overrides = {
        "XAGENT_OLLAMA_MODEL": "qwen2.5:1.5b",
        "XAGENT_OLLAMA_BASE_URL": "http://127.0.0.1:11435",
    }
    report = build_refresh_chain(provider="ollama", timeout_seconds=1, provider_env_overrides=overrides)

    assert report.status == "passed"
    assert report.provider_env_overrides == overrides
    assert captured_envs
    assert all(env["XAGENT_OLLAMA_MODEL"] == "qwen2.5:1.5b" for env in captured_envs)
    assert all(env["XAGENT_OLLAMA_BASE_URL"] == "http://127.0.0.1:11435" for env in captured_envs)


def test_refresh_chain_rejects_unsupported_provider_env_overrides() -> None:
    with pytest.raises(ValueError, match="XAGENT_OPENAI_API_KEY"):
        build_refresh_chain(
            provider="ollama",
            dry_run=True,
            provider_env_overrides={"XAGENT_OPENAI_API_KEY": "sk-" + ("a" * 32)},
        )


def test_refresh_chain_rejects_unsupported_provider() -> None:
    with pytest.raises(ValueError):
        build_refresh_chain(provider="unknown")


def test_refresh_chain_stops_after_failed_step(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(list(command))
        return subprocess.CompletedProcess(command, 1, stdout="bad", stderr="")

    monkeypatch.setattr(rc_refresh_release_chain.subprocess, "run", fake_run)

    report = build_refresh_chain(provider="ollama", timeout_seconds=1)

    assert report.status == "failed"
    assert len(calls) == 1
    assert [step.name for step in report.steps] == ["release_audit"]


def test_refresh_chain_can_continue_after_failed_step(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(list(command))
        return subprocess.CompletedProcess(command, 1 if len(calls) == 1 else 0, stdout="ok", stderr="")

    monkeypatch.setattr(rc_refresh_release_chain.subprocess, "run", fake_run)

    report = build_refresh_chain(provider="ollama", timeout_seconds=1, stop_on_failure=False)

    assert report.status == "failed"
    assert len(calls) == len(report.steps)
    assert report.steps[0].status == "failed"
    assert report.steps[-1].name == "evidence_pack_final"


def test_refresh_chain_decodes_non_utf8_subprocess_output(monkeypatch) -> None:
    def fake_run(command, **kwargs):  # noqa: ANN001
        return subprocess.CompletedProcess(command, 0, stdout="本地输出".encode("gbk"), stderr=b"")

    monkeypatch.setattr(rc_refresh_release_chain.subprocess, "run", fake_run)

    report = build_refresh_chain(provider="ollama", timeout_seconds=1)

    assert report.status == "passed"
    assert report.steps[0].stdout_tail == ["本地输出"]


def test_refresh_chain_redacts_secret_like_output_lines(monkeypatch) -> None:
    def fake_run(command, **kwargs):  # noqa: ANN001
        return subprocess.CompletedProcess(command, 0, stdout=b"XAGENT_GITHUB_TOKEN: required_by=gate\n", stderr=b"")

    monkeypatch.setattr(rc_refresh_release_chain.subprocess, "run", fake_run)

    report = build_refresh_chain(provider="ollama", timeout_seconds=1)

    assert report.status == "passed"
    assert report.steps[0].stdout_tail == ["XAGENT_GITHUB_TOKEN: <redacted-output>"]
    assert "required_by" not in report.steps[0].stdout_tail[0]


def test_refresh_chain_redacts_bare_token_shaped_output(monkeypatch) -> None:
    def fake_run(command, **kwargs):  # noqa: ANN001
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=("created token sk-" + ("a" * 32) + "\n").encode(),
            stderr=("github value ghp_" + ("b" * 40) + "\n").encode(),
        )

    monkeypatch.setattr(rc_refresh_release_chain.subprocess, "run", fake_run)

    report = build_refresh_chain(provider="ollama", timeout_seconds=1)
    payload = json.dumps(report.to_dict())

    assert report.status == "passed"
    assert report.steps[0].stdout_tail == ["created token <redacted-secret>"]
    assert report.steps[0].stderr_tail == ["github value <redacted-secret>"]
    assert "sk-" not in payload
    assert "ghp_" not in payload


def test_refresh_chain_writes_running_report_before_evidence_pack(tmp_path: Path, monkeypatch) -> None:
    snapshots: list[dict[str, object]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        return subprocess.CompletedProcess(command, 0, stdout=b"ok", stderr=b"")

    original_write_report = rc_refresh_release_chain.write_report

    def spy_write_report(report, output_path):  # noqa: ANN001
        snapshots.append(report.to_dict())
        original_write_report(report, output_path)

    monkeypatch.setattr(rc_refresh_release_chain.subprocess, "run", fake_run)
    monkeypatch.setattr(rc_refresh_release_chain, "write_report", spy_write_report)

    report_path = tmp_path / "rc-refresh-release-chain.json"
    report = build_refresh_chain(provider="ollama", timeout_seconds=1, report_path=report_path)

    assert report.status == "passed"
    assert snapshots[0]["status"] == "running"
    assert snapshots[0]["steps"][-1]["name"] == "secrets_gate"
    assert any(
        snapshot["status"] == "running" and snapshot["steps"][-1]["name"] == "final_gate"
        for snapshot in snapshots
    )
    assert any(
        snapshot["status"] == "running" and snapshot["steps"][-1]["name"] == "release_receipt_after_docs"
        for snapshot in snapshots
    )
    assert any(
        snapshot["status"] == "passed" and snapshot["steps"][-1]["name"] == "evidence_pack_after_receipt"
        for snapshot in snapshots
    )
    assert any(
        snapshot["status"] == "passed" and snapshot["steps"][-1]["name"] == "final_gate_final"
        for snapshot in snapshots
    )


def test_refresh_chain_writes_passed_snapshot_before_final_evidence_pack(tmp_path: Path, monkeypatch) -> None:
    snapshots: list[dict[str, object]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        return subprocess.CompletedProcess(command, 0, stdout=b"ok", stderr=b"")

    original_write_report = rc_refresh_release_chain.write_report

    def spy_write_report(report, output_path):  # noqa: ANN001
        snapshots.append(report.to_dict())
        original_write_report(report, output_path)

    monkeypatch.setattr(rc_refresh_release_chain.subprocess, "run", fake_run)
    monkeypatch.setattr(rc_refresh_release_chain, "write_report", spy_write_report)

    report_path = tmp_path / "rc-refresh-release-chain.json"
    report = build_refresh_chain(provider="ollama", timeout_seconds=1, report_path=report_path)

    assert report.status == "passed"
    assert snapshots[-1]["status"] == "passed"
    assert snapshots[-1]["steps"][-1]["name"] == "evidence_pack_final"
    assert snapshots[-1]["steps"][-1]["status"] == "passed"
    assert json.loads(report_path.read_text(encoding="utf-8"))["status"] == "passed"


def test_refresh_chain_report_includes_owner_gate_summary(tmp_path: Path, monkeypatch) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "rc-final-gate.json").write_text(
        json.dumps({"status": "ready_with_owner_gates", "release_decision": {"can_tag_rc_now": False}}),
        encoding="utf-8",
    )
    (reports / "rc-owner-gate-plan.json").write_text(
        json.dumps(
            {
                "status": "action_required",
                "gates": [
                    {
                        "name": "provider",
                        "status": "ready_to_run",
                        "missing": [],
                        "configured_env": ["XAGENT_OLLAMA_MODEL"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (reports / "rc-external-smoke.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "checks": [
                    {
                        "name": "provider",
                        "status": "skipped",
                        "missing": ["Start Ollama."],
                        "error": "HTTP Error 500",
                    },
                    {
                        "name": "hosted_github_actions_run",
                        "status": "passed",
                        "missing": [],
                        "error": None,
                        "details": {
                            "run_url": "https://github.com/acme/project/actions/runs/123",
                            "workflow_verified": True,
                            "expected_head_sha": "0123456789abcdef0123456789abcdef01234567",
                            "head_sha": "0123456789abcdef0123456789abcdef01234567",
                            "head_sha_verified": True,
                            "jobs_verified": True,
                            "artifact_verified": True,
                            "mutation_performed": False,
                            "token": "ghp_" + ("a" * 40),
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(rc_refresh_release_chain, "REPORT_DIR", reports)

    report = build_refresh_chain(provider="ollama", dry_run=True)

    assert report.owner_gate_summary["final_gate_status"] == "ready_with_owner_gates"
    assert report.owner_gate_summary["can_tag_rc_now"] is False
    assert report.owner_gate_summary["owner_gates"][0]["status"] == "ready_to_run"
    assert report.owner_gate_summary["external_checks"][0]["status"] == "skipped"
    hosted_check = report.owner_gate_summary["external_checks"][1]
    assert hosted_check["details"]["head_sha_verified"] is True
    assert hosted_check["details"]["head_sha"] == "0123456789abcdef0123456789abcdef01234567"
    assert "token" not in hosted_check["details"]


def test_write_report_serializes_steps(tmp_path: Path) -> None:
    report = build_refresh_chain(provider="ollama", dry_run=True)
    output = tmp_path / "rc-refresh-release-chain.json"

    write_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "planned"
    assert payload["steps"][0]["name"] == "release_audit"
    assert payload["steps"][-1]["name"] == "evidence_pack_final"


def test_refresh_chain_cli_writes_dry_run_report(tmp_path: Path) -> None:
    output = tmp_path / "rc-refresh-release-chain.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/rc_refresh_release_chain.py",
            "--provider",
            "ollama",
            "--ollama-model",
            "qwen2.5:1.5b",
            "--ollama-base-url",
            "http://127.0.0.1:11435",
            "--dry-run",
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0
    assert "planned" in result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "planned"
    assert payload["owner_verified"] is False
    assert payload["provider_env_overrides"] == {
        "XAGENT_OLLAMA_MODEL": "qwen2.5:1.5b",
        "XAGENT_OLLAMA_BASE_URL": "http://127.0.0.1:11435",
    }


def test_refresh_chain_cli_writes_owner_verified_dry_run_report(tmp_path: Path) -> None:
    output = tmp_path / "rc-refresh-release-chain.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/rc_refresh_release_chain.py",
            "--provider",
            "ollama",
            "--owner-verified",
            "--dry-run",
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0
    assert "Owner verified: True" in result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["owner_verified"] is True
    external_step = next(step for step in payload["steps"] if step["name"] == "external_smoke")
    assert "--require-configured" in external_step["command"]
    assert "--github-execute-preflight" in external_step["command"]
    assert "--github-actions-preflight" in external_step["command"]
