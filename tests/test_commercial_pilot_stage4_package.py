from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.commercial_pilot_stage4_package import (
    build_stage4_package,
    render_markdown_package,
    write_markdown_package,
    write_report,
)

CURRENT_HEAD = "62f567982fc33b6f8d72c4f3a8d8e192698d0c92"
PILOT_SHA = "765d44b69da061caba6585a4cee0105bbf3310a7"
RC_SHA = "592141f35520df62578a00cbb805eeaa7371a940"
PILOT_TAG = "x-agent-commercial-pilot-feishu-20260608"
RC_TAG = "x-agent-commercial-rc-20260608-6"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_stage4_inputs(report_dir: Path, *, remote_head: str = CURRENT_HEAD, parity: bool = False) -> None:
    _write_json(
        report_dir / "stage2-remote-ci-final-20260615.json",
        {
            "report": "stage2-remote-ci-final-20260615",
            "head_sha": "42a81034beb29b8c2d5cb4ecf27327f88ac0058e",
            "stage2_exit_gate": "met",
        },
    )
    _write_json(
        report_dir / "stage3-static-remediation-result-20260615.json",
        {
            "report": "stage3-static-remediation-result-20260615",
            "static_remediation_gate": "met",
            "real_staging_rehearsal_gate": "not_met",
            "full_codex_parity_claimed": False,
            "mutation_performed": False,
            "outbound_message_sent": False,
        },
    )
    _write_json(
        report_dir / "stage3-remote-ci-final-20260615.json",
        {
            "report": "stage3-remote-ci-final-20260615",
            "head_sha": remote_head,
            "remote_branch_sha": remote_head,
            "pull_request": {
                "number": 2,
                "url": "https://github.com/xiongpinji/X-Agent/pull/2",
                "state": "open",
                "draft": False,
                "mergeable_state": "clean",
                "title": "feat: Commercial Delivery v1 - Controlled Pilot Readiness",
            },
            "github_actions_check_runs": {
                "total_count": 28,
                "completed_success": 27,
                "completed_skipped": 1,
                "failed": 0,
                "in_progress": 0,
                "skipped_checks": ["performance-tests"],
            },
            "static_remediation_remote_gate": "met",
            "real_staging_rehearsal_gate": "not_met",
            "full_codex_parity_claimed": False,
            "mutation_performed": False,
            "outbound_message_sent": False,
        },
    )
    _write_json(
        report_dir / "commercial-pilot-final-gate.json",
        {
            "status": "final_gate_ready",
            "full_codex_parity_claimed": parity,
            "mutation_performed": False,
            "outbound_message_sent": False,
        },
    )
    _write_json(
        report_dir / "commercial-pilot-delivery-receipt.json",
        {
            "status": "delivery_receipt_ready",
            "pilot_channel": "feishu",
            "pilot_tag_name": PILOT_TAG,
            "pilot_commit_sha": PILOT_SHA,
            "rc_tag_name": RC_TAG,
            "rc_commit_sha": RC_SHA,
            "outbound_owner_gate_status": "preview",
            "full_codex_parity_claimed": False,
            "mutation_performed": False,
            "outbound_message_sent": False,
        },
    )
    _write_json(
        report_dir / "commercial-pilot-acceptance-gate.json",
        {
            "status": "pilot_acceptance_ready",
            "pilot_channel": "feishu",
            "pilot_tag_name": PILOT_TAG,
            "pilot_commit_sha": PILOT_SHA,
            "rc_tag_name": RC_TAG,
            "rc_commit_sha": RC_SHA,
            "full_codex_parity_claimed": False,
            "mutation_performed": False,
            "outbound_message_sent": False,
        },
    )
    _write_json(
        report_dir / "commercial-pilot-handoff-index.json",
        {
            "status": "handoff_index_ready",
            "full_codex_parity_claimed": False,
            "mutation_performed": False,
            "outbound_message_sent": False,
        },
    )
    _write_json(
        report_dir / "commercial-pilot-customer-acceptance-pack.json",
        {
            "status": "customer_acceptance_pack_ready",
            "pilot_channel": "feishu",
            "pilot_tag_name": PILOT_TAG,
            "pilot_commit_sha": PILOT_SHA,
            "rc_tag_name": RC_TAG,
            "rc_commit_sha": RC_SHA,
            "outbound_owner_gate_status": "preview",
            "full_codex_parity_claimed": False,
            "mutation_performed": False,
            "outbound_message_sent": False,
        },
    )


def test_stage4_package_ready_with_staging_owner_blocked(tmp_path: Path) -> None:
    _write_stage4_inputs(tmp_path)

    report = build_stage4_package(
        report_dir=tmp_path,
        branch="feat/commercial-delivery-v1",
        current_head_sha=CURRENT_HEAD,
        remote_branch_sha=CURRENT_HEAD,
    )

    assert report.package_status == "stage4_pilot_handoff_ready_with_staging_owner_blocked"
    assert report.version_identity["current_head_sha"] == CURRENT_HEAD
    assert report.remote_pr_gate["status"] == "passed"
    assert report.stage3_static_remediation_gate == "met"
    assert report.real_staging_rehearsal_gate == "not_met"
    assert report.historical_pilot_identity["pilot_commit_sha"] == PILOT_SHA
    assert report.historical_pilot_identity["current_head_is_historical_pilot_commit"] is False
    assert report.full_codex_parity_claimed is False
    assert report.mutation_performed is False
    assert report.outbound_message_sent is False
    assert {check.status for check in report.checks} == {"passed"}


def test_stage4_package_blocks_when_current_head_is_not_remote_gate_head(tmp_path: Path) -> None:
    _write_stage4_inputs(tmp_path, remote_head="42a81034beb29b8c2d5cb4ecf27327f88ac0058e")

    report = build_stage4_package(
        report_dir=tmp_path,
        branch="feat/commercial-delivery-v1",
        current_head_sha=CURRENT_HEAD,
        remote_branch_sha=CURRENT_HEAD,
    )

    assert report.package_status == "stage4_pilot_handoff_blocked"
    head_check = next(check for check in report.checks if check.name == "current_head_bound_to_remote_pr_gate")
    assert head_check.status == "failed"


def test_stage4_package_blocks_total_parity_claim_in_sources(tmp_path: Path) -> None:
    _write_stage4_inputs(tmp_path, parity=True)

    report = build_stage4_package(
        report_dir=tmp_path,
        branch="feat/commercial-delivery-v1",
        current_head_sha=CURRENT_HEAD,
        remote_branch_sha=CURRENT_HEAD,
    )

    assert report.package_status == "stage4_pilot_handoff_blocked"
    parity_check = next(check for check in report.checks if check.name == "no_codex_total_parity_claim")
    assert parity_check.status == "failed"


def test_stage4_markdown_avoids_forbidden_success_phrases(tmp_path: Path) -> None:
    _write_stage4_inputs(tmp_path)
    report = build_stage4_package(
        report_dir=tmp_path,
        branch="feat/commercial-delivery-v1",
        current_head_sha=CURRENT_HEAD,
        remote_branch_sha=CURRENT_HEAD,
    )

    rendered = render_markdown_package(report)

    forbidden = re.compile(
        r"GA ready|production ready|full commercial delivery complete|full Codex parity|staging proven",
        re.IGNORECASE,
    )
    assert not forbidden.search(rendered)
    assert "real_staging_rehearsal_gate" not in rendered
    assert "Real staging rehearsal gate: `not_met`" in rendered


def test_write_stage4_package_json_and_markdown(tmp_path: Path) -> None:
    _write_stage4_inputs(tmp_path / "reports")
    report = build_stage4_package(
        report_dir=tmp_path / "reports",
        branch="feat/commercial-delivery-v1",
        current_head_sha=CURRENT_HEAD,
        remote_branch_sha=CURRENT_HEAD,
    )
    json_output = tmp_path / "stage4.json"
    markdown_output = tmp_path / "stage4.md"

    write_report(report, json_output)
    write_markdown_package(report, markdown_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = markdown_output.read_text(encoding="utf-8")
    assert payload["package_status"] == "stage4_pilot_handoff_ready_with_staging_owner_blocked"
    assert payload["real_staging_rehearsal_gate"] == "not_met"
    assert payload["historical_pilot_identity"]["pilot_commit_sha"] == PILOT_SHA
    assert "# Stage 4 Pilot Handoff Package" in markdown
