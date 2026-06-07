from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import rc_owner_verified_finalize
from scripts.rc_owner_verified_finalize import build_owner_verified_finalize, write_report

EXPECTED_SHA = "643a017b3a2ae00be212d186e2681a147b46bf6b"
OLD_SHA = "08cd6d114e0c0cb357ccea3e529aed7b2aea1045"


def _is_head_command(command: object) -> bool:
    return list(command)[:3] == ["git", "rev-parse", "HEAD"] if isinstance(command, list | tuple) else False


def _head_completed_process(command: object) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(command, 0, stdout=EXPECTED_SHA + "\n", stderr="")


def _write_ready_reports(reports_dir: Path, release_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    release_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "rc-refresh-release-chain.json").write_text(
        json.dumps({"status": "passed", "owner_verified": True}),
        encoding="utf-8",
    )
    (reports_dir / "rc-final-gate.json").write_text(
        json.dumps(
            {
                "status": "ready_for_rc_tag",
                "release_decision": {"can_tag_rc_now": True},
            }
        ),
        encoding="utf-8",
    )
    (reports_dir / "rc-evidence-pack.json").write_text(
        json.dumps({"status": "passed"}),
        encoding="utf-8",
    )
    (release_dir / "x-agent-commercial-rc-receipt.json").write_text(
        json.dumps({"status": "created"}),
        encoding="utf-8",
    )


def test_finalize_runs_owner_verified_refresh_chain_with_expected_overrides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reports_dir = tmp_path / "reports"
    release_dir = tmp_path / "release"
    calls: list[dict[str, object]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        if _is_head_command(command):
            return _head_completed_process(command)
        calls.append({"command": list(command), "env": dict(kwargs["env"])})
        _write_ready_reports(reports_dir, release_dir)
        return subprocess.CompletedProcess(command, 0, stdout=b"ok", stderr=b"")

    monkeypatch.setattr(rc_owner_verified_finalize.subprocess, "run", fake_run)

    report = build_owner_verified_finalize(
        provider="ollama",
        timeout_seconds=1,
        ollama_model="qwen2.5:1.5b",
        ollama_base_url="http://127.0.0.1:11435",
        env_file=_owner_env_file(tmp_path),
        github_actions_run_url="https://github.com/xiongpinji/X-Agent/actions/runs/27100639918",
        github_actions_head_sha=EXPECTED_SHA,
        expected_commit_sha=EXPECTED_SHA,
        reports_dir=reports_dir,
        release_dir=release_dir,
    )

    command = calls[0]["command"]
    assert command[:4] == [
        sys.executable,
        "scripts/rc_refresh_release_chain.py",
        "--provider",
        "ollama",
    ]
    assert "--owner-verified" in command
    assert "--ollama-model" in command
    assert "--ollama-base-url" in command
    assert "--output" in command
    assert str(reports_dir / "rc-refresh-release-chain.json") in command
    assert report.refresh_chain_report_path == str(reports_dir / "rc-refresh-release-chain.json")
    env = calls[0]["env"]
    assert env["XAGENT_OLLAMA_MODEL"] == "qwen2.5:1.5b"
    assert env["XAGENT_OLLAMA_BASE_URL"] == "http://127.0.0.1:11435"
    assert env["XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA"] == EXPECTED_SHA
    assert report.status == "ready_for_rc_tag"
    assert report.can_tag_rc_now is True
    assert report.expected_commit_sha == EXPECTED_SHA
    assert report.refresh_chain_owner_verified is True
    assert report.loaded_env_names == [
        "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA",
        "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL",
        "XAGENT_FEISHU_APP_ID",
        "XAGENT_FEISHU_APP_SECRET",
        "XAGENT_FEISHU_ENCRYPT_KEY",
        "XAGENT_GITHUB_TEST_ISSUE_URL",
        "XAGENT_GITHUB_TOKEN",
        "XAGENT_OLLAMA_BASE_URL",
        "XAGENT_OLLAMA_MODEL",
    ]


def test_finalize_loads_owner_env_file_without_leaking_secret_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reports_dir = tmp_path / "reports"
    release_dir = tmp_path / "release"
    env_file = tmp_path / "owner.env"
    token = "ghp_" + ("a" * 40)
    app_secret = "feishu_secret_" + ("c" * 32)
    encrypt_key = "feishu_encrypt_" + ("d" * 32)
    env_file.write_text(
        "\n".join(
            [
                'XAGENT_GITHUB_TOKEN="' + token + '"',
                'XAGENT_FEISHU_APP_SECRET="' + app_secret + '"',
                'XAGENT_FEISHU_APP_ID="cli_test_app"',
                'XAGENT_FEISHU_ENCRYPT_KEY="' + encrypt_key + '"',
                'XAGENT_GITHUB_TEST_ISSUE_URL="https://github.com/acme/project/issues/1"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    def fake_run(command, **kwargs):  # noqa: ANN001
        if _is_head_command(command):
            return _head_completed_process(command)
        assert kwargs["env"]["XAGENT_GITHUB_TOKEN"] == token
        _write_ready_reports(reports_dir, release_dir)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=("token=" + token + "\nraw-secret " + app_secret + "\n").encode(),
            stderr=("raw-encrypt " + encrypt_key + "\n").encode(),
        )

    monkeypatch.setattr(rc_owner_verified_finalize.subprocess, "run", fake_run)

    report = build_owner_verified_finalize(
        provider="ollama",
        timeout_seconds=1,
        env_file=env_file,
        ollama_model="qwen2.5:1.5b",
        ollama_base_url="http://127.0.0.1:11435",
        github_actions_run_url="https://github.com/xiongpinji/X-Agent/actions/runs/27100639918",
        github_actions_head_sha=EXPECTED_SHA,
        expected_commit_sha=EXPECTED_SHA,
        reports_dir=reports_dir,
        release_dir=release_dir,
    )
    payload = json.dumps(report.to_dict())

    assert report.status == "ready_for_rc_tag"
    assert "XAGENT_GITHUB_TOKEN" in report.loaded_env_names
    assert report.skipped_env_names == []
    assert token not in payload
    assert app_secret not in payload
    assert encrypt_key not in payload
    assert report.steps[0].stdout_tail == [
        "token=<redacted-output>",
        "raw-secret <redacted-secret>",
    ]
    assert report.steps[0].stderr_tail == ["raw-encrypt <redacted-secret>"]


def test_finalize_redacts_sensitive_values_inherited_from_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reports_dir = tmp_path / "reports"
    release_dir = tmp_path / "release"
    inherited_secret = "inherited_encrypt_" + ("e" * 32)
    monkeypatch.setenv("XAGENT_FEISHU_ENCRYPT_KEY", inherited_secret)

    def fake_run(command, **_kwargs):  # noqa: ANN001
        if _is_head_command(command):
            return _head_completed_process(command)
        _write_ready_reports(reports_dir, release_dir)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=b"ok",
            stderr=("inherited " + inherited_secret + "\n").encode(),
        )

    monkeypatch.setattr(rc_owner_verified_finalize.subprocess, "run", fake_run)

    report = build_owner_verified_finalize(
        provider="ollama",
        timeout_seconds=1,
        env_file=_owner_env_file(tmp_path),
        ollama_model="qwen2.5:1.5b",
        ollama_base_url="http://127.0.0.1:11435",
        github_actions_run_url="https://github.com/xiongpinji/X-Agent/actions/runs/27100639918",
        github_actions_head_sha=EXPECTED_SHA,
        expected_commit_sha=EXPECTED_SHA,
        reports_dir=reports_dir,
        release_dir=release_dir,
    )

    payload = json.dumps(report.to_dict())
    assert inherited_secret not in payload
    assert report.steps[0].stderr_tail == ["inherited <redacted-secret>"]


def test_finalize_redacts_non_allowlisted_sensitive_environment_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reports_dir = tmp_path / "reports"
    release_dir = tmp_path / "release"
    inherited_token = "npm_token_" + ("f" * 32)
    monkeypatch.setenv("NPM_TOKEN", inherited_token)

    def fake_run(command, **_kwargs):  # noqa: ANN001
        if _is_head_command(command):
            return _head_completed_process(command)
        _write_ready_reports(reports_dir, release_dir)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=("npm " + inherited_token + "\n").encode(),
            stderr=b"",
        )

    monkeypatch.setattr(rc_owner_verified_finalize.subprocess, "run", fake_run)

    report = build_owner_verified_finalize(
        provider="ollama",
        timeout_seconds=1,
        env_file=_owner_env_file(tmp_path),
        ollama_model="qwen2.5:1.5b",
        ollama_base_url="http://127.0.0.1:11435",
        github_actions_run_url="https://github.com/xiongpinji/X-Agent/actions/runs/27100639918",
        github_actions_head_sha=EXPECTED_SHA,
        expected_commit_sha=EXPECTED_SHA,
        reports_dir=reports_dir,
        release_dir=release_dir,
    )

    payload = json.dumps(report.to_dict())
    assert inherited_token not in payload
    assert report.steps[0].stdout_tail == ["npm <redacted-secret>"]


def _owner_env_file(tmp_path: Path) -> Path:
    env_file = tmp_path / "owner.env"
    env_file.write_text(
        "\n".join(
            [
                'XAGENT_FEISHU_APP_ID="cli_test_app"',
                'XAGENT_FEISHU_APP_SECRET="cli_test_secret"',
                'XAGENT_FEISHU_ENCRYPT_KEY="cli_test_encrypt_key"',
                'XAGENT_GITHUB_TEST_ISSUE_URL="https://github.com/acme/project/issues/1"',
                'XAGENT_GITHUB_TOKEN="ghp_' + ("b" * 40) + '"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return env_file


def test_finalize_preflight_stops_before_refresh_chain_when_owner_env_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reports_dir = tmp_path / "reports"
    release_dir = tmp_path / "release"
    refresh_chain = reports_dir / "rc-refresh-release-chain.json"
    reports_dir.mkdir(parents=True)
    refresh_chain.write_text(json.dumps({"status": "passed", "owner_verified": True}), encoding="utf-8")

    def fail_if_called(command, **_kwargs):  # noqa: ANN001
        if _is_head_command(command):
            return _head_completed_process(command)
        raise AssertionError("refresh chain must not run when owner env preflight fails")

    monkeypatch.setattr(rc_owner_verified_finalize.subprocess, "run", fail_if_called)

    report = build_owner_verified_finalize(
        provider="ollama",
        timeout_seconds=1,
        ollama_model="qwen2.5:1.5b",
        ollama_base_url="http://127.0.0.1:11435",
        github_actions_run_url="https://github.com/xiongpinji/X-Agent/actions/runs/27100639918",
        github_actions_head_sha=EXPECTED_SHA,
        expected_commit_sha=EXPECTED_SHA,
        reports_dir=reports_dir,
        release_dir=release_dir,
    )

    assert report.status == "failed"
    assert report.steps[0].name == "owner_env_preflight"
    assert "XAGENT_FEISHU_APP_ID/FEISHU_APP_ID" in str(report.steps[0].error)
    assert json.loads(refresh_chain.read_text(encoding="utf-8")) == {"status": "passed", "owner_verified": True}


def test_finalize_preflight_rejects_hosted_actions_sha_for_different_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(command, **_kwargs):  # noqa: ANN001
        if _is_head_command(command):
            return _head_completed_process(command)
        raise AssertionError("refresh chain must not run when hosted Actions SHA mismatches the release commit")

    monkeypatch.setattr(rc_owner_verified_finalize.subprocess, "run", fail_if_called)

    report = build_owner_verified_finalize(
        provider="ollama",
        timeout_seconds=1,
        env_file=_owner_env_file(tmp_path),
        ollama_model="qwen2.5:1.5b",
        ollama_base_url="http://127.0.0.1:11435",
        github_actions_run_url="https://github.com/xiongpinji/X-Agent/actions/runs/27100639918",
        github_actions_head_sha=OLD_SHA,
        expected_commit_sha=EXPECTED_SHA,
        reports_dir=tmp_path / "reports",
        release_dir=tmp_path / "release",
    )

    assert report.status == "failed"
    assert report.steps[0].name == "owner_env_preflight"
    assert "must match expected release commit SHA" in str(report.steps[0].error)
    assert EXPECTED_SHA in str(report.steps[0].error)


def test_finalize_preflight_rejects_explicit_expected_sha_that_differs_from_head(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(command, **kwargs):  # noqa: ANN001
        if command[:3] == ["git", "rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(command, 0, stdout=EXPECTED_SHA + "\n", stderr="")
        raise AssertionError("refresh chain must not run when explicit expected SHA differs from HEAD")

    monkeypatch.setattr(rc_owner_verified_finalize.subprocess, "run", fake_run)

    report = build_owner_verified_finalize(
        provider="ollama",
        timeout_seconds=1,
        env_file=_owner_env_file(tmp_path),
        ollama_model="qwen2.5:1.5b",
        ollama_base_url="http://127.0.0.1:11435",
        github_actions_run_url="https://github.com/xiongpinji/X-Agent/actions/runs/27100639918",
        github_actions_head_sha=OLD_SHA,
        expected_commit_sha=OLD_SHA,
        reports_dir=tmp_path / "reports",
        release_dir=tmp_path / "release",
    )

    assert report.status == "failed"
    assert report.steps[0].name == "owner_env_preflight"
    assert "--expected-commit-sha must match current git HEAD" in str(report.steps[0].error)
    assert EXPECTED_SHA in str(report.steps[0].error)


def test_finalize_rejects_unsupported_owner_env_file_names(tmp_path: Path) -> None:
    env_file = tmp_path / "owner.env"
    env_file.write_text("PYTHONPATH=bad\n", encoding="utf-8")

    report = build_owner_verified_finalize(
        provider="ollama",
        timeout_seconds=1,
        env_file=env_file,
        reports_dir=tmp_path / "reports",
        release_dir=tmp_path / "release",
    )

    assert report.status == "failed"
    assert report.steps[0].name == "owner_env_file"
    assert "unsupported owner env name PYTHONPATH" in str(report.steps[0].error)


def test_finalize_reports_action_required_when_final_gate_is_not_tag_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reports_dir = tmp_path / "reports"
    release_dir = tmp_path / "release"

    def fake_run(command, **kwargs):  # noqa: ANN001
        if _is_head_command(command):
            return _head_completed_process(command)
        reports_dir.mkdir(parents=True, exist_ok=True)
        release_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "rc-refresh-release-chain.json").write_text(
            json.dumps({"status": "passed", "owner_verified": True}),
            encoding="utf-8",
        )
        (reports_dir / "rc-final-gate.json").write_text(
            json.dumps(
                {
                    "status": "ready_with_owner_gates",
                    "release_decision": {"can_tag_rc_now": False},
                }
            ),
            encoding="utf-8",
        )
        (reports_dir / "rc-evidence-pack.json").write_text(
            json.dumps({"status": "passed"}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout=b"ok", stderr=b"")

    monkeypatch.setattr(rc_owner_verified_finalize.subprocess, "run", fake_run)

    report = build_owner_verified_finalize(
        provider="ollama",
        timeout_seconds=1,
        env_file=_owner_env_file(tmp_path),
        ollama_model="qwen2.5:1.5b",
        ollama_base_url="http://127.0.0.1:11435",
        github_actions_run_url="https://github.com/xiongpinji/X-Agent/actions/runs/27100639918",
        github_actions_head_sha=EXPECTED_SHA,
        expected_commit_sha=EXPECTED_SHA,
        reports_dir=reports_dir,
        release_dir=release_dir,
    )

    assert report.status == "action_required"
    assert report.can_tag_rc_now is False
    assert report.final_gate_status == "ready_with_owner_gates"


def test_finalize_cli_dry_run_writes_report(tmp_path: Path) -> None:
    output = tmp_path / "finalize.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/rc_owner_verified_finalize.py",
            "--provider",
            "ollama",
            "--dry-run",
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0
    assert output.exists()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "planned"
    assert payload["dry_run"] is True
    assert payload["steps"][0]["name"] == "owner_verified_refresh_chain"
    assert payload["refresh_chain_report_path"].endswith(
        "rc-owner-verified-finalize-refresh-chain-dry-run.json"
    )


def test_write_report_serializes_finalize_steps(tmp_path: Path) -> None:
    report = build_owner_verified_finalize(
        provider="ollama",
        dry_run=True,
        timeout_seconds=1,
        reports_dir=tmp_path / "reports",
        release_dir=tmp_path / "release",
    )
    output = tmp_path / "report.json"

    write_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["provider"] == "ollama"
    assert payload["steps"][0]["name"] == "owner_verified_refresh_chain"
