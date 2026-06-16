from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from scripts import rc_tag_consistency_gate
from scripts.rc_tag_consistency_gate import build_tag_consistency_report, write_report

EXPECTED_SHA = "1c46c851dfe8867ddae26ee0842c568c7a969d86"
OLD_SHA = "08cd6d114e0c0cb357ccea3e529aed7b2aea1045"
TAG_NAME = "x-agent-commercial-rc-20260608"


def _fake_git(monkeypatch: pytest.MonkeyPatch, *, local_sha: str, remote_sha: str) -> None:
    def fake_run(command, **_kwargs):  # noqa: ANN001
        if command[:4] == ["git", "rev-parse", "--verify", f"refs/tags/{TAG_NAME}^{{commit}}"]:
            return subprocess.CompletedProcess(command, 0, stdout=local_sha + "\n", stderr="")
        if command[:4] == ["git", "ls-remote", "--tags", "origin"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=f"{remote_sha}\trefs/tags/{TAG_NAME}\n",
                stderr="",
            )
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(rc_tag_consistency_gate.subprocess, "run", fake_run)


def test_tag_consistency_passes_when_local_and_remote_match(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_git(monkeypatch, local_sha=EXPECTED_SHA, remote_sha=EXPECTED_SHA)

    report = build_tag_consistency_report(expected_commit_sha=EXPECTED_SHA, tag_name=TAG_NAME)

    assert report.status == "passed"
    assert report.expected_commit_sha == EXPECTED_SHA
    assert [check.status for check in report.checks] == ["passed", "passed", "passed"]


def test_tag_consistency_reports_action_required_without_require_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_git(monkeypatch, local_sha=OLD_SHA, remote_sha=OLD_SHA)

    report = build_tag_consistency_report(expected_commit_sha=EXPECTED_SHA, tag_name=TAG_NAME)

    assert report.status == "action_required"
    assert any(check.name == "local_tag" and check.status == "action_required" for check in report.checks)
    assert any(check.name == "remote_tag" and check.status == "action_required" for check in report.checks)
    assert any("--require-match" in command for command in report.next_commands)


def test_tag_consistency_fails_with_require_match(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_git(monkeypatch, local_sha=OLD_SHA, remote_sha=OLD_SHA)

    report = build_tag_consistency_report(
        expected_commit_sha=EXPECTED_SHA,
        tag_name=TAG_NAME,
        require_match=True,
    )

    assert report.status == "failed"
    assert any(check.name == "remote_tag" and check.status == "failed" for check in report.checks)


def test_tag_consistency_uses_peeled_remote_ref_for_annotated_tags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(command, **_kwargs):  # noqa: ANN001
        if command[:4] == ["git", "rev-parse", "--verify", f"refs/tags/{TAG_NAME}^{{commit}}"]:
            return subprocess.CompletedProcess(command, 0, stdout=EXPECTED_SHA + "\n", stderr="")
        if command[:4] == ["git", "ls-remote", "--tags", "origin"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=(
                    f"{OLD_SHA}\trefs/tags/{TAG_NAME}\n"
                    f"{EXPECTED_SHA}\trefs/tags/{TAG_NAME}^{{}}\n"
                ),
                stderr="",
            )
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(rc_tag_consistency_gate.subprocess, "run", fake_run)

    report = build_tag_consistency_report(expected_commit_sha=EXPECTED_SHA, tag_name=TAG_NAME)

    assert report.status == "passed"
    remote_check = next(check for check in report.checks if check.name == "remote_tag")
    assert remote_check.details["actual_commit_sha"] == EXPECTED_SHA


def test_write_report_serializes_tag_checks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_git(monkeypatch, local_sha=EXPECTED_SHA, remote_sha=EXPECTED_SHA)
    report = build_tag_consistency_report(expected_commit_sha=EXPECTED_SHA, tag_name=TAG_NAME)
    output = tmp_path / "tag-report.json"

    write_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["tag_name"] == TAG_NAME
    assert payload["checks"][0]["name"] == "expected_commit"


def test_cli_require_match_returns_nonzero_for_mismatch(tmp_path: Path) -> None:
    output = tmp_path / "tag-report.json"
    missing_tag = f"x-agent-commercial-rc-test-missing-{uuid.uuid4().hex}"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/rc_tag_consistency_gate.py",
            "--expected-commit-sha",
            EXPECTED_SHA,
            "--tag-name",
            missing_tag,
            "--no-remote",
            "--require-match",
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode != 0
    assert output.exists()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
