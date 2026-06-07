from __future__ import annotations

import json
from pathlib import Path

import scripts.rc_single_user_local_gate as gate
from scripts.rc_single_user_local_gate import (
    CommandRun,
    check_existing_report,
    run_single_user_local_gate,
)


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _command_run(command: list[str], *, returncode: int = 0, stdout: str = "", stderr: str = "") -> CommandRun:
    return CommandRun(
        command=command,
        cwd=str(gate.ROOT),
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=0.01,
    )


def test_existing_report_accepts_rc2_handoff_status(tmp_path: Path) -> None:
    report_path = _write_json(
        tmp_path / "handoff.json",
        {
            "status": "created_and_validated",
            "tag": "x-agent-commercial-rc-20260608-2",
            "commit": "abc123",
            "release_url": "https://github.com/xiongpinji/X-Agent/releases/tag/test",
        },
    )

    check = check_existing_report(
        report_path,
        name="rc2_release_handoff_snapshot",
        expected={"created_and_validated"},
        required=True,
    )

    assert check.status == "passed"
    assert check.details["tag"] == "x-agent-commercial-rc-20260608-2"


def test_existing_report_can_skip_optional_missing_report(tmp_path: Path) -> None:
    check = check_existing_report(
        tmp_path / "missing.json",
        name="rc2_release_handoff_snapshot",
        expected={"created_and_validated"},
        required=False,
    )

    assert check.status == "skipped"
    assert check.details["reason"] == "report missing"


def test_report_status_check_rejects_nonzero_command(tmp_path: Path) -> None:
    run = _command_run(["python", "scripts/example.py"], returncode=1, stderr="boom")

    check = gate._report_status_check(
        name="example",
        run=run,
        report_path=tmp_path / "missing.json",
        expected_report_status={"passed"},
    )

    assert check.status == "failed"
    assert check.error == "command exited nonzero"
    assert check.details["stderr_tail"] == "boom"


def test_report_status_check_requires_expected_json_status(tmp_path: Path) -> None:
    report_path = _write_json(tmp_path / "report.json", {"status": "failed"})
    run = _command_run(["python", "scripts/example.py"])

    check = gate._report_status_check(
        name="example",
        run=run,
        report_path=report_path,
        expected_report_status={"passed"},
    )

    assert check.status == "failed"
    assert "expected report status" in str(check.error)
    assert check.details["report_status"] == "failed"


def test_single_user_gate_aggregates_all_checks(tmp_path: Path, monkeypatch) -> None:
    rc2 = _write_json(tmp_path / "rc2.json", {"status": "created_and_validated"})

    monkeypatch.setattr(
        gate,
        "run_install_release_gate",
        lambda report_path, timeout_seconds: gate.SingleUserCheck("install_release_gate", "passed"),
    )
    monkeypatch.setattr(
        gate,
        "run_frontend_build",
        lambda timeout_seconds: gate.SingleUserCheck("frontend_production_build", "passed"),
    )
    monkeypatch.setattr(
        gate,
        "run_runtime_smoke",
        lambda report_path, timeout_seconds, backend_only: gate.SingleUserCheck("runtime_smoke", "passed"),
    )
    monkeypatch.setattr(
        gate,
        "run_targeted_tests",
        lambda timeout_seconds: gate.SingleUserCheck("targeted_single_user_tests", "passed"),
    )

    report = run_single_user_local_gate(
        output_path=tmp_path / "single-user.json",
        rc2_handoff_report_path=rc2,
        require_rc2_handoff=True,
    )

    assert report.status == "passed"
    assert [check.name for check in report.checks] == [
        "rc2_release_handoff_snapshot",
        "install_release_gate",
        "frontend_production_build",
        "runtime_smoke",
        "targeted_single_user_tests",
    ]


def test_single_user_gate_can_stop_on_failure(tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr(
        gate,
        "run_install_release_gate",
        lambda report_path, timeout_seconds: gate.SingleUserCheck("install_release_gate", "failed", error="bad install"),
    )

    def unexpected_frontend(timeout_seconds: float) -> gate.SingleUserCheck:
        calls.append("frontend")
        return gate.SingleUserCheck("frontend_production_build", "passed")

    monkeypatch.setattr(gate, "run_frontend_build", unexpected_frontend)

    report = run_single_user_local_gate(
        output_path=tmp_path / "single-user.json",
        rc2_handoff_report_path=tmp_path / "missing-optional.json",
        stop_on_failure=True,
    )

    assert report.status == "failed"
    assert calls == []
    assert [check.name for check in report.checks] == [
        "rc2_release_handoff_snapshot",
        "install_release_gate",
    ]


def test_targeted_tests_command_disables_repo_coverage(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> CommandRun:
        captured["command"] = command
        return _command_run(command)

    monkeypatch.setattr(gate, "_run_command", fake_run)

    check = gate.run_targeted_tests(timeout_seconds=5)

    assert check.status == "passed"
    command = captured["command"]
    assert isinstance(command, list)
    assert "tests/test_rc_single_user_local_gate.py" in command
    assert "-p" in command
    assert "no:cov" in command
    assert "addopts=" in command


def test_output_tail_redacts_secret_like_values() -> None:
    raw = "XAGENT_TOKEN=xagent-" + ("a" * 32) + "\nstdout ghp_" + ("b" * 40)

    tail = gate._tail(raw)

    assert "XAGENT_TOKEN=<redacted-output>" in tail
    assert "<redacted-secret>" in tail
    assert "xagent-" not in tail
    assert "ghp_" not in tail
