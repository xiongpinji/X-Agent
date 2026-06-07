from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import rc_delivery_status
from scripts.rc_delivery_status import build_delivery_status_report, write_report

EXPECTED_SHA = "e0febc0d92ce348503e995c1a0d0bc897f5585df"
OLD_SHA = "08cd6d114e0c0cb357ccea3e529aed7b2aea1045"
TAG_NAME = "x-agent-commercial-rc-20260608-3"
RUN_URL = "https://github.com/xiongpinji/X-Agent/actions/runs/27105724396"


def _fake_git(monkeypatch: pytest.MonkeyPatch, *, head_sha: str = EXPECTED_SHA, remote_sha: str = EXPECTED_SHA) -> None:
    def fake_run(command, **_kwargs):  # noqa: ANN001
        if command == ["git", "rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(command, 0, stdout=head_sha + "\n", stderr="")
        if command == ["git", "rev-parse", "origin/codex/codex-hermes-gap-closure"]:
            return subprocess.CompletedProcess(command, 0, stdout=remote_sha + "\n", stderr="")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(rc_delivery_status.subprocess, "run", fake_run)


def _write_owner_finalize(path: Path, *, status: str = "ready_for_rc_tag", sha: str = EXPECTED_SHA) -> None:
    path.write_text(
        json.dumps(
            {
                "status": status,
                "expected_commit_sha": sha,
                "github_actions_run_url": RUN_URL,
                "github_actions_head_sha": sha,
                "can_tag_rc_now": status == "ready_for_rc_tag",
                "refresh_chain_owner_verified": status == "ready_for_rc_tag",
            }
        ),
        encoding="utf-8",
    )


def _write_tag_consistency(path: Path, *, status: str = "passed", sha: str = EXPECTED_SHA, tag_name: str = TAG_NAME) -> None:
    path.write_text(
        json.dumps(
            {
                "status": status,
                "expected_commit_sha": sha,
                "tag_name": tag_name,
            }
        ),
        encoding="utf-8",
    )


def _current_head_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout.strip().lower()


def test_delivery_status_is_ready_when_all_evidence_matches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_git(monkeypatch)
    owner = tmp_path / "owner.json"
    tag = tmp_path / "tag.json"
    _write_owner_finalize(owner)
    _write_tag_consistency(tag)

    report = build_delivery_status_report(
        expected_commit_sha=EXPECTED_SHA,
        tag_name=TAG_NAME,
        github_actions_run_url=RUN_URL,
        github_actions_head_sha=EXPECTED_SHA,
        owner_finalize_report_path=owner,
        tag_consistency_report_path=tag,
    )

    assert report.status == "commercial_rc_ready"
    assert [check.status for check in report.checks] == ["passed", "passed", "passed", "passed", "passed"]


def test_delivery_status_keeps_owner_finalize_pending_for_failed_owner_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_git(monkeypatch)
    owner = tmp_path / "owner.json"
    tag = tmp_path / "tag.json"
    _write_owner_finalize(owner, status="failed")
    _write_tag_consistency(tag)

    report = build_delivery_status_report(
        expected_commit_sha=EXPECTED_SHA,
        tag_name=TAG_NAME,
        github_actions_run_url=RUN_URL,
        github_actions_head_sha=EXPECTED_SHA,
        owner_finalize_report_path=owner,
        tag_consistency_report_path=tag,
    )

    assert report.status == "owner_finalize_pending"
    owner_check = next(check for check in report.checks if check.name == "owner_verified_finalize")
    assert owner_check.status == "action_required"
    assert any("rc_owner_verified_finalize.py" in command for command in report.next_commands)


def test_delivery_status_rejects_owner_report_for_old_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_git(monkeypatch)
    owner = tmp_path / "owner.json"
    tag = tmp_path / "tag.json"
    _write_owner_finalize(owner, sha=OLD_SHA)
    _write_tag_consistency(tag)

    report = build_delivery_status_report(
        expected_commit_sha=EXPECTED_SHA,
        tag_name=TAG_NAME,
        github_actions_run_url=RUN_URL,
        github_actions_head_sha=EXPECTED_SHA,
        owner_finalize_report_path=owner,
        tag_consistency_report_path=tag,
    )

    assert report.status == "owner_finalize_pending"
    owner_check = next(check for check in report.checks if check.name == "owner_verified_finalize")
    assert "does not match expected commit SHA" in str(owner_check.error)


def test_delivery_status_reports_tag_action_required_when_tag_report_is_stale(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_git(monkeypatch)
    owner = tmp_path / "owner.json"
    tag = tmp_path / "tag.json"
    _write_owner_finalize(owner)
    _write_tag_consistency(tag, tag_name="x-agent-commercial-rc-20260608")

    report = build_delivery_status_report(
        expected_commit_sha=EXPECTED_SHA,
        tag_name=TAG_NAME,
        github_actions_run_url=RUN_URL,
        github_actions_head_sha=EXPECTED_SHA,
        owner_finalize_report_path=owner,
        tag_consistency_report_path=tag,
    )

    assert report.status == "tag_action_required"
    tag_check = next(check for check in report.checks if check.name == "tag_consistency")
    assert tag_check.status == "action_required"


def test_delivery_status_fails_when_hosted_ci_head_sha_differs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_git(monkeypatch)
    owner = tmp_path / "owner.json"
    tag = tmp_path / "tag.json"
    _write_owner_finalize(owner)
    _write_tag_consistency(tag)

    report = build_delivery_status_report(
        expected_commit_sha=EXPECTED_SHA,
        tag_name=TAG_NAME,
        github_actions_run_url=RUN_URL,
        github_actions_head_sha=OLD_SHA,
        owner_finalize_report_path=owner,
        tag_consistency_report_path=tag,
    )

    assert report.status == "failed"
    ci_check = next(check for check in report.checks if check.name == "hosted_ci")
    assert ci_check.status == "failed"


def test_write_report_serializes_delivery_checks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_git(monkeypatch)
    owner = tmp_path / "owner.json"
    tag = tmp_path / "tag.json"
    output = tmp_path / "delivery-status.json"
    _write_owner_finalize(owner)
    _write_tag_consistency(tag)
    report = build_delivery_status_report(
        expected_commit_sha=EXPECTED_SHA,
        tag_name=TAG_NAME,
        github_actions_run_url=RUN_URL,
        github_actions_head_sha=EXPECTED_SHA,
        owner_finalize_report_path=owner,
        tag_consistency_report_path=tag,
    )

    write_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "commercial_rc_ready"
    assert payload["checks"][0]["name"] == "expected_commit"


def test_delivery_status_cli_returns_nonzero_until_owner_finalize_is_ready(tmp_path: Path) -> None:
    current_sha = _current_head_sha()
    owner = tmp_path / "owner.json"
    tag = tmp_path / "tag.json"
    output = tmp_path / "delivery-status.json"
    _write_owner_finalize(owner, status="failed", sha=current_sha)
    _write_tag_consistency(tag, sha=current_sha)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/rc_delivery_status.py",
            "--expected-commit-sha",
            current_sha,
            "--tag-name",
            TAG_NAME,
            "--github-actions-run-url",
            RUN_URL,
            "--github-actions-head-sha",
            current_sha,
            "--owner-finalize-report",
            str(owner),
            "--tag-consistency-report",
            str(tag),
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
    assert payload["status"] != "commercial_rc_ready"
    assert any(check["name"] == "owner_verified_finalize" for check in payload["checks"])
