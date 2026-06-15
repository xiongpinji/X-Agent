from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_ga_final_gate import (
    RequiredEvidenceSpec,
    build_ga_final_gate_report,
    render_markdown_report,
    write_markdown_report,
    write_report,
)

HEAD = "f1e89ffd6bbb3a35b175b9f0ff0ce41873bf77c8"
PILOT_SHA = "765d44b69da061caba6585a4cee0105bbf3310a7"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _specs(report_dir: Path) -> list[RequiredEvidenceSpec]:
    return [
        RequiredEvidenceSpec("real_staging_rehearsal", report_dir / "staging.json", ("passed",), "ga_hard_blocker", "staging"),
        RequiredEvidenceSpec("production_rehearsal", report_dir / "production.json", ("passed",), "ga_hard_blocker", "production"),
        RequiredEvidenceSpec("security_compliance", report_dir / "security.json", ("passed",), "ga_hard_blocker", "security"),
        RequiredEvidenceSpec("ops_support", report_dir / "ops.json", ("passed",), "ga_hard_blocker", "ops"),
        RequiredEvidenceSpec("claim_safe_docs", report_dir / "claims.json", ("passed",), "claim_guardrail", "claims"),
        RequiredEvidenceSpec("single_sha_evidence_index", report_dir / "index.json", ("passed",), "ga_hard_blocker", "index"),
        RequiredEvidenceSpec("performance_capacity", report_dir / "performance.json", ("passed",), "ga_hard_blocker", "performance"),
        RequiredEvidenceSpec(
            "codex_parity_disposition",
            report_dir / "parity.json",
            ("codex_parity_excluded", "codex_parity_proven"),
            "claim_guardrail",
            "parity",
        ),
    ]


def _write_stage4_and_remote(report_dir: Path, *, head: str = HEAD) -> None:
    _write_json(
        report_dir / "stage4.json",
        {
            "package_status": "stage4_pilot_handoff_ready_with_staging_owner_blocked",
            "version_identity": {"current_head_sha": head},
            "historical_pilot_identity": {
                "pilot_commit_sha": PILOT_SHA,
                "current_head_is_historical_pilot_commit": False,
            },
            "real_staging_rehearsal_gate": "not_met",
            "full_codex_parity_claimed": False,
            "mutation_performed": False,
            "outbound_message_sent": False,
        },
    )
    _write_json(
        report_dir / "remote.json",
        {
            "report": "stage3-remote-ci-final-20260615",
            "head_sha": head,
            "remote_branch_sha": head,
            "github_actions_check_runs": {
                "total_count": 28,
                "completed_success": 27,
                "completed_skipped": 1,
                "failed": 0,
                "in_progress": 0,
            },
            "full_codex_parity_claimed": False,
        },
    )


def _write_all_ga_evidence(report_dir: Path, *, release_sha: str = HEAD, parity_status: str = "codex_parity_excluded") -> None:
    for spec in _specs(report_dir):
        status = parity_status if spec.name == "codex_parity_disposition" else "passed"
        _write_json(
            spec.path,
            {
                "status": status,
                "release_sha": release_sha,
                "ga_ready": False,
                "production_ready": False,
                "full_commercial_delivery_complete": False,
                "full_codex_parity_claimed": False,
            },
        )


def test_ga_final_gate_ready_only_when_all_required_evidence_is_ready(tmp_path: Path) -> None:
    _write_stage4_and_remote(tmp_path)
    _write_all_ga_evidence(tmp_path)

    report = build_ga_final_gate_report(
        report_dir=tmp_path,
        stage4_package_path=tmp_path / "stage4.json",
        remote_pr_report_path=tmp_path / "remote.json",
        required_specs=_specs(tmp_path),
        branch="feat/commercial-delivery-v1",
        current_head_sha=HEAD,
        remote_branch_sha=HEAD,
        git_status_lines=[],
    )

    assert report.status == "commercial_ga_ready"
    assert report.ga_ready is True
    assert report.production_ready is True
    assert report.full_commercial_delivery_complete is True
    assert report.controlled_pilot_ready is True
    assert report.full_codex_parity_claimed is False
    assert report.missing_or_blocked_evidence == []
    assert {check.status for check in report.checks} == {"passed"}


def test_ga_final_gate_blocks_missing_required_evidence(tmp_path: Path) -> None:
    _write_stage4_and_remote(tmp_path)

    report = build_ga_final_gate_report(
        report_dir=tmp_path,
        stage4_package_path=tmp_path / "stage4.json",
        remote_pr_report_path=tmp_path / "remote.json",
        required_specs=_specs(tmp_path),
        branch="feat/commercial-delivery-v1",
        current_head_sha=HEAD,
        remote_branch_sha=HEAD,
        git_status_lines=[],
    )

    assert report.status == "commercial_ga_blocked"
    assert report.ga_ready is False
    assert "real_staging_rehearsal" in report.missing_or_blocked_evidence
    evidence_check = next(check for check in report.checks if check.name == "all_required_ga_evidence_ready")
    assert evidence_check.status == "failed"


def test_ga_final_gate_blocks_ready_evidence_for_wrong_sha(tmp_path: Path) -> None:
    _write_stage4_and_remote(tmp_path)
    _write_all_ga_evidence(tmp_path, release_sha="62f567982fc33b6f8d72c4f3a8d8e192698d0c92")

    report = build_ga_final_gate_report(
        report_dir=tmp_path,
        stage4_package_path=tmp_path / "stage4.json",
        remote_pr_report_path=tmp_path / "remote.json",
        required_specs=_specs(tmp_path),
        branch="feat/commercial-delivery-v1",
        current_head_sha=HEAD,
        remote_branch_sha=HEAD,
        git_status_lines=[],
    )

    assert report.status == "commercial_ga_blocked"
    sha_check = next(check for check in report.checks if check.name == "ready_evidence_bound_to_current_head")
    assert sha_check.status == "failed"


def test_ga_final_gate_blocks_dirty_worktree(tmp_path: Path) -> None:
    _write_stage4_and_remote(tmp_path)
    _write_all_ga_evidence(tmp_path)

    report = build_ga_final_gate_report(
        report_dir=tmp_path,
        stage4_package_path=tmp_path / "stage4.json",
        remote_pr_report_path=tmp_path / "remote.json",
        required_specs=_specs(tmp_path),
        branch="feat/commercial-delivery-v1",
        current_head_sha=HEAD,
        remote_branch_sha=HEAD,
        git_status_lines=[" M DEPLOYMENT.md"],
    )

    assert report.status == "commercial_ga_blocked"
    dirty_check = next(check for check in report.checks if check.name == "release_worktree_boundary_clean")
    assert dirty_check.status == "failed"


def test_ga_final_gate_blocks_pilot_only_package(tmp_path: Path) -> None:
    _write_stage4_and_remote(tmp_path)
    _write_json(
        tmp_path / "stage4.json",
        {
            "package_status": "stage4_pilot_handoff_blocked",
            "version_identity": {"current_head_sha": HEAD},
        },
    )
    _write_all_ga_evidence(tmp_path)

    report = build_ga_final_gate_report(
        report_dir=tmp_path,
        stage4_package_path=tmp_path / "stage4.json",
        remote_pr_report_path=tmp_path / "remote.json",
        required_specs=_specs(tmp_path),
        branch="feat/commercial-delivery-v1",
        current_head_sha=HEAD,
        remote_branch_sha=HEAD,
        git_status_lines=[],
    )

    assert report.status == "commercial_ga_blocked"
    pilot_check = next(check for check in report.checks if check.name == "stage4_controlled_pilot_package_ready")
    assert pilot_check.status == "failed"


def test_write_ga_final_gate_json_and_markdown(tmp_path: Path) -> None:
    _write_stage4_and_remote(tmp_path)
    report = build_ga_final_gate_report(
        report_dir=tmp_path,
        stage4_package_path=tmp_path / "stage4.json",
        remote_pr_report_path=tmp_path / "remote.json",
        required_specs=_specs(tmp_path),
        branch="feat/commercial-delivery-v1",
        current_head_sha=HEAD,
        remote_branch_sha=HEAD,
        git_status_lines=[],
    )
    json_output = tmp_path / "gate.json"
    markdown_output = tmp_path / "gate.md"

    write_report(report, json_output)
    write_markdown_report(report, markdown_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = markdown_output.read_text(encoding="utf-8")
    assert payload["status"] == "commercial_ga_blocked"
    assert payload["ga_ready"] is False
    assert "# Commercial GA Final Gate" in markdown
    assert "GA ready: `False`" in render_markdown_report(report)
