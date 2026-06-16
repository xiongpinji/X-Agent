from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import commercial_pilot_handoff_status
from scripts.commercial_pilot_handoff_status import build_handoff_status_report, write_report

PILOT_SHA = "765d44b69da061caba6585a4cee0105bbf3310a7"
OLD_SHA = "5877b0b273a8d4abd1fad1ce501d673c6cd06f32"
RC_SHA = "592141f35520df62578a00cbb805eeaa7371a940"
RC_TAG = "x-agent-commercial-rc-20260608-6"
PILOT_TAG = "x-agent-commercial-pilot-feishu-20260608"
RUN_URL = "https://github.com/xiongpinji/X-Agent/actions/runs/27119766813"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _fake_git(
    monkeypatch: pytest.MonkeyPatch,
    *,
    head_sha: str = PILOT_SHA,
    remote_sha: str = PILOT_SHA,
    local_tag_sha: str | None = PILOT_SHA,
    remote_tag_sha: str | None = PILOT_SHA,
) -> None:
    def fake_run(command, **_kwargs):  # noqa: ANN001
        if command == ["git", "rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(command, 0, stdout=head_sha + "\n", stderr="")
        if command == ["git", "cat-file", "-e", f"{PILOT_SHA}^{{commit}}"]:
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        if command == [
            "git",
            "ls-remote",
            "--heads",
            "origin",
            "refs/heads/codex/codex-hermes-gap-closure",
        ]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=f"{remote_sha}\trefs/heads/codex/codex-hermes-gap-closure\n",
                stderr="",
            )
        if command == ["git", "merge-base", "--is-ancestor", PILOT_SHA, remote_sha]:
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        if command == ["git", "rev-parse", "--verify", f"refs/tags/{PILOT_TAG}^{{commit}}"]:
            if local_tag_sha is None:
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="missing local tag")
            return subprocess.CompletedProcess(command, 0, stdout=local_tag_sha + "\n", stderr="")
        if command == [
            "git",
            "ls-remote",
            "--tags",
            "origin",
            f"refs/tags/{PILOT_TAG}",
            f"refs/tags/{PILOT_TAG}^{{}}",
        ]:
            if remote_tag_sha is None:
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            return subprocess.CompletedProcess(command, 0, stdout=f"{remote_tag_sha}\trefs/tags/{PILOT_TAG}\n", stderr="")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(commercial_pilot_handoff_status.subprocess, "run", fake_run)


def _write_rc_delivery(path: Path, *, status: str = "commercial_rc_ready", sha: str = RC_SHA) -> None:
    _write_json(
        path,
        {
            "status": status,
            "tag_name": RC_TAG,
            "expected_commit_sha": sha,
        },
    )


def _write_feishu_live(path: Path, *, outbound_message_sent: bool = False) -> None:
    _write_json(
        path,
        {
            "status": "passed",
            "channel": "feishu",
            "evidence_type": "commercial_pilot_feishu_live",
            "event_type": "im.message.receive_v1",
            "tenant_key_present": True,
            "message_id_present": True,
            "chat_id_present": True,
            "content_present": True,
            "signature_mode": "lark_sha256",
            "encrypted_callback": True,
            "app_id_configured": True,
            "app_secret_configured": True,
            "encrypt_key_configured": True,
            "mutation_performed": False,
            "outbound_message_sent": outbound_message_sent,
            "checks": [
                {"name": "event_accepted", "status": "passed"},
                {"name": "sender_present", "status": "passed"},
                {"name": "message_id_present", "status": "passed"},
                {"name": "no_outbound_mutation", "status": "passed"},
            ],
        },
    )


def _write_pilot_readiness(path: Path, *, status: str = "pilot_ready", parity: bool = False) -> None:
    _write_json(
        path,
        {
            "status": status,
            "rc_tag": RC_TAG,
            "rc_commit": RC_SHA,
            "pilot_channel": "feishu",
            "full_codex_parity_claimed": parity,
        },
    )


def _write_refresh_chain(path: Path, *, status: str = "pilot_ready", parity: bool = False) -> None:
    _write_json(
        path,
        {
            "status": status,
            "pilot_channel": "feishu",
            "readiness_report_path": "commercial-pilot-readiness.json",
            "full_codex_parity_claimed": parity,
            "steps": [
                {"name": "core_entrypoints", "status": "passed"},
                {"name": "commercial_pilot_readiness", "status": "passed"},
            ],
        },
    )


def _write_all_reports(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    rc = tmp_path / "rc-delivery-status.json"
    feishu = tmp_path / "commercial-pilot-feishu-live.json"
    readiness = tmp_path / "commercial-pilot-readiness.json"
    refresh = tmp_path / "commercial-pilot-refresh-chain.json"
    _write_rc_delivery(rc)
    _write_feishu_live(feishu)
    _write_pilot_readiness(readiness)
    _write_refresh_chain(refresh)
    return rc, feishu, readiness, refresh


def test_handoff_status_is_ready_when_all_evidence_and_tag_match(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_git(monkeypatch)
    rc, feishu, readiness, refresh = _write_all_reports(tmp_path)

    report = build_handoff_status_report(
        expected_pilot_commit_sha=PILOT_SHA,
        pilot_tag_name=PILOT_TAG,
        expected_rc_commit_sha=RC_SHA,
        rc_tag_name=RC_TAG,
        github_actions_run_url=RUN_URL,
        github_actions_head_sha=PILOT_SHA,
        rc_delivery_report_path=rc,
        feishu_live_report_path=feishu,
        pilot_readiness_report_path=readiness,
        refresh_chain_report_path=refresh,
    )

    assert report.status == "pilot_handoff_ready"
    assert report.full_codex_parity_claimed is False
    assert {check.status for check in report.checks} == {"passed"}


def test_handoff_status_requires_pilot_tag_when_evidence_is_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_git(monkeypatch, local_tag_sha=None, remote_tag_sha=None)
    rc, feishu, readiness, refresh = _write_all_reports(tmp_path)

    report = build_handoff_status_report(
        expected_pilot_commit_sha=PILOT_SHA,
        pilot_tag_name=PILOT_TAG,
        expected_rc_commit_sha=RC_SHA,
        rc_tag_name=RC_TAG,
        github_actions_run_url=RUN_URL,
        github_actions_head_sha=PILOT_SHA,
        rc_delivery_report_path=rc,
        feishu_live_report_path=feishu,
        pilot_readiness_report_path=readiness,
        refresh_chain_report_path=refresh,
    )

    assert report.status == "pilot_tag_action_required"
    tag_check = next(check for check in report.checks if check.name == "pilot_tag_consistency")
    assert tag_check.status == "action_required"
    assert any(command.startswith("git tag ") for command in report.next_commands)


def test_handoff_status_rejects_feishu_live_evidence_with_outbound_send(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_git(monkeypatch)
    rc, feishu, readiness, refresh = _write_all_reports(tmp_path)
    _write_feishu_live(feishu, outbound_message_sent=True)

    report = build_handoff_status_report(
        expected_pilot_commit_sha=PILOT_SHA,
        pilot_tag_name=PILOT_TAG,
        expected_rc_commit_sha=RC_SHA,
        rc_tag_name=RC_TAG,
        github_actions_run_url=RUN_URL,
        github_actions_head_sha=PILOT_SHA,
        rc_delivery_report_path=rc,
        feishu_live_report_path=feishu,
        pilot_readiness_report_path=readiness,
        refresh_chain_report_path=refresh,
    )

    assert report.status == "failed"
    feishu_check = next(check for check in report.checks if check.name == "feishu_live_evidence")
    assert feishu_check.status == "failed"
    assert "outbound_message_sent" in str(feishu_check.details["mismatches"])


def test_handoff_status_rejects_stale_rc_baseline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_git(monkeypatch)
    rc, feishu, readiness, refresh = _write_all_reports(tmp_path)
    _write_rc_delivery(rc, sha=OLD_SHA)

    report = build_handoff_status_report(
        expected_pilot_commit_sha=PILOT_SHA,
        pilot_tag_name=PILOT_TAG,
        expected_rc_commit_sha=RC_SHA,
        rc_tag_name=RC_TAG,
        github_actions_run_url=RUN_URL,
        github_actions_head_sha=PILOT_SHA,
        rc_delivery_report_path=rc,
        feishu_live_report_path=feishu,
        pilot_readiness_report_path=readiness,
        refresh_chain_report_path=refresh,
    )

    assert report.status == "failed"
    rc_check = next(check for check in report.checks if check.name == "rc_baseline")
    assert "does not match expected pilot baseline" in str(rc_check.error)


def test_handoff_status_rejects_full_codex_parity_claim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_git(monkeypatch)
    rc, feishu, readiness, refresh = _write_all_reports(tmp_path)
    _write_pilot_readiness(readiness, parity=True)

    report = build_handoff_status_report(
        expected_pilot_commit_sha=PILOT_SHA,
        pilot_tag_name=PILOT_TAG,
        expected_rc_commit_sha=RC_SHA,
        rc_tag_name=RC_TAG,
        github_actions_run_url=RUN_URL,
        github_actions_head_sha=PILOT_SHA,
        rc_delivery_report_path=rc,
        feishu_live_report_path=feishu,
        pilot_readiness_report_path=readiness,
        refresh_chain_report_path=refresh,
    )

    assert report.status == "failed"
    readiness_check = next(check for check in report.checks if check.name == "pilot_readiness")
    assert "full Codex parity" in str(readiness_check.error)


def test_write_report_serializes_handoff_checks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_git(monkeypatch)
    rc, feishu, readiness, refresh = _write_all_reports(tmp_path)
    output = tmp_path / "commercial-pilot-handoff-status.json"
    report = build_handoff_status_report(
        expected_pilot_commit_sha=PILOT_SHA,
        pilot_tag_name=PILOT_TAG,
        expected_rc_commit_sha=RC_SHA,
        rc_tag_name=RC_TAG,
        github_actions_run_url=RUN_URL,
        github_actions_head_sha=PILOT_SHA,
        rc_delivery_report_path=rc,
        feishu_live_report_path=feishu,
        pilot_readiness_report_path=readiness,
        refresh_chain_report_path=refresh,
    )

    write_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pilot_handoff_ready"
    assert payload["checks"][0]["name"] == "pilot_commit"
    assert payload["full_codex_parity_claimed"] is False


def test_cli_writes_pending_report_and_returns_nonzero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _fake_git(monkeypatch, local_tag_sha=None, remote_tag_sha=None)
    rc, feishu, readiness, refresh = _write_all_reports(tmp_path)
    output = tmp_path / "commercial-pilot-handoff-status.json"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "scripts/commercial_pilot_handoff_status.py",
            "--expected-pilot-commit-sha",
            PILOT_SHA,
            "--pilot-tag-name",
            PILOT_TAG,
            "--expected-rc-commit-sha",
            RC_SHA,
            "--rc-tag-name",
            RC_TAG,
            "--github-actions-run-url",
            RUN_URL,
            "--github-actions-head-sha",
            PILOT_SHA,
            "--rc-delivery-report",
            str(rc),
            "--feishu-live-report",
            str(feishu),
            "--pilot-readiness-report",
            str(readiness),
            "--refresh-chain-report",
            str(refresh),
            "--output",
            str(output),
        ],
    )
    exit_code = commercial_pilot_handoff_status.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Commercial pilot handoff status: pilot_tag_action_required" in captured.out
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pilot_tag_action_required"
