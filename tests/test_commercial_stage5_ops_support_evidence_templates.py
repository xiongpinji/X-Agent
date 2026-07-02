from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.commercial_ops_support_gate import build_ops_support_gate_report, default_required_evidence
from scripts.commercial_stage5_ops_evidence_pack import build_ops_evidence_pack
from scripts.commercial_stage5_ops_support_evidence_templates import (
    build_template_payloads,
    build_worker_report,
    write_markdown_report,
    write_report,
    write_templates,
)

HEAD = "a2b9b7fabc694b9f7d2a254019dacac64d89a20f"
RELEASE = "a2b9b7fabc694b9f7d2a254019dacac64d89a20f"

EXPECTED_FILENAMES = {
    "stage5-slo-sla-evidence-20260615.json",
    "stage5-alert-routing-evidence-20260615.json",
    "stage5-backup-restore-rehearsal-20260615.json",
    "stage5-incident-process-evidence-20260615.json",
    "stage5-support-escalation-evidence-20260615.json",
    "stage5-cost-capacity-guardrails-20260615.json",
    "stage5-on-call-ownership-evidence-20260615.json",
}

EXPECTED_NAMES = {
    "slo_sla",
    "alert_routing",
    "backup_restore_rehearsal",
    "incident_process",
    "support_escalation",
    "cost_capacity_guardrails",
    "on_call_ownership",
}

REQUIRED_FALSE_FIELDS = {
    "template_not_evidence": True,
    "real_evidence_collected": False,
    "mutation_performed": False,
    "deploy_performed": False,
    "owner_approval_created": False,
}


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_payloads_use_ops_support_gate_specs_and_are_blocked_templates(tmp_path: Path) -> None:
    payloads = build_template_payloads(tmp_path, current_head_sha=HEAD, release_sha=RELEASE)

    assert set(payloads) == EXPECTED_FILENAMES
    assert {payload["evidence_name"] for payload in payloads.values()} == EXPECTED_NAMES
    assert set(payloads) == {spec.path.name for spec in default_required_evidence(tmp_path)}

    for spec in default_required_evidence(tmp_path):
        payload = payloads[spec.path.name]
        assert payload["status"] == "blocked"
        assert payload["template_filename"] == spec.path.name
        assert payload["evidence_reason"] == spec.reason
        assert payload["expected_ready_statuses"] == sorted(spec.expected_statuses)
        assert payload["current_head_sha"] == HEAD
        assert payload["release_sha"] == RELEASE
        assert isinstance(payload["required_owner_or_operator_actions"], list)
        assert payload["required_owner_or_operator_actions"]
        for field, expected in REQUIRED_FALSE_FIELDS.items():
            assert payload[field] is expected


def test_write_templates_creates_all_seven_files(tmp_path: Path) -> None:
    results = write_templates(tmp_path, current_head_sha=HEAD, release_sha=RELEASE)

    assert len(results) == 7
    assert {result.name for result in results} == EXPECTED_NAMES
    assert all(result.written for result in results)
    assert all(not result.skipped_existing for result in results)
    assert {path.name for path in tmp_path.glob("*.json")} == EXPECTED_FILENAMES

    for spec in default_required_evidence(tmp_path):
        payload = _read_json(spec.path)
        assert payload["status"] == "blocked"
        assert payload["template_not_evidence"] is True
        assert payload["real_evidence_collected"] is False


def test_write_templates_does_not_overwrite_existing_files_without_force(tmp_path: Path) -> None:
    existing_path = tmp_path / "stage5-slo-sla-evidence-20260615.json"
    existing_path.write_text('{"status":"real_fixture"}\n', encoding="utf-8")

    results = write_templates(tmp_path, current_head_sha=HEAD, release_sha=RELEASE)

    skipped = next(result for result in results if result.name == "slo_sla")
    assert skipped.status == "skipped_existing"
    assert skipped.written is False
    assert skipped.skipped_existing is True
    assert _read_json(existing_path) == {"status": "real_fixture"}
    assert sum(result.written for result in results) == 6


def test_write_templates_force_overwrites_existing_files(tmp_path: Path) -> None:
    existing_path = tmp_path / "stage5-slo-sla-evidence-20260615.json"
    existing_path.write_text(
        '{"status":"blocked","template_not_evidence":true,"real_evidence_collected":false}\n',
        encoding="utf-8",
    )

    results = write_templates(tmp_path, current_head_sha=HEAD, release_sha=RELEASE, force=True)

    assert all(result.written for result in results)
    assert all(result.force for result in results)
    payload = _read_json(existing_path)
    assert payload["status"] == "blocked"
    assert payload["evidence_name"] == "slo_sla"
    assert payload["template_not_evidence"] is True


def test_write_templates_force_refuses_to_overwrite_real_evidence_file(tmp_path: Path) -> None:
    existing_path = tmp_path / "stage5-slo-sla-evidence-20260615.json"
    existing_path.write_text('{"status":"ready","real_evidence_collected":true}\n', encoding="utf-8")

    results = write_templates(tmp_path, current_head_sha=HEAD, release_sha=RELEASE, force=True)

    skipped = next(result for result in results if result.name == "slo_sla")
    assert skipped.status == "skipped_existing_real_evidence"
    assert skipped.written is False
    assert skipped.error
    assert _read_json(existing_path) == {"status": "ready", "real_evidence_collected": True}


def test_generated_templates_keep_ops_support_gate_blocked(tmp_path: Path) -> None:
    write_templates(tmp_path, current_head_sha=HEAD, release_sha=RELEASE)

    report = build_ops_support_gate_report(
        report_dir=tmp_path,
        current_head_sha=HEAD,
        release_sha=RELEASE,
        root=tmp_path,
    )

    assert report.status == "ops_support_blocked"
    assert report.ops_support_ready is False
    assert set(report.missing_or_blocked_evidence) == EXPECTED_NAMES
    assert all(item.status == "blocked" for item in report.required_evidence)
    assert all(item.ready is False for item in report.required_evidence)


def test_generated_templates_keep_ops_evidence_pack_blocked(tmp_path: Path) -> None:
    write_templates(tmp_path, current_head_sha=HEAD, release_sha=RELEASE)

    report = build_ops_evidence_pack(
        report_dir=tmp_path,
        current_head_sha=HEAD,
        release_sha=RELEASE,
        root=tmp_path,
    )

    assert report.status == "ops_support_evidence_blocked"
    assert report.controlled_commercial_pilot_ops_ready is False
    assert set(report.missing_or_blocked_evidence) == EXPECTED_NAMES
    assert all(item.status == "blocked" for item in report.evidence)
    assert all(item.ready is False for item in report.evidence)


def test_worker_report_writes_json_and_markdown(tmp_path: Path) -> None:
    results = write_templates(tmp_path / "templates", current_head_sha=HEAD, release_sha=RELEASE)
    report = build_worker_report(
        results,
        report_dir=tmp_path / "templates",
        current_head_sha=HEAD,
        release_sha=RELEASE,
    )
    output_json = tmp_path / "worker.json"
    output_md = tmp_path / "worker.md"

    write_report(report, output_json)
    write_markdown_report(report, output_md)

    payload = _read_json(output_json)
    markdown = output_md.read_text(encoding="utf-8")
    assert payload["status"] == "ops_support_evidence_templates_written"
    assert payload["template_not_evidence"] is True
    assert payload["real_evidence_collected"] is False
    assert payload["mutation_performed"] is False
    assert payload["deploy_performed"] is False
    assert payload["owner_approval_created"] is False
    assert payload["ops_support_gate_expected_status"] == "ops_support_blocked"
    assert payload["ops_support_evidence_pack_expected_status"] == "ops_support_evidence_blocked"
    assert "# Stage 5 Ops / Support Evidence Templates Worker" in markdown
    assert "ops_support_evidence_templates_written" in markdown


def test_cli_defaults_to_dry_run_worker_summary_into_tmp_path(tmp_path: Path) -> None:
    report_dir = tmp_path / "templates"
    output_json = tmp_path / "summary.json"
    output_md = tmp_path / "summary.md"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.commercial_stage5_ops_support_evidence_templates",
            "--report-dir",
            str(report_dir),
            "--current-head-sha",
            HEAD,
            "--release-sha",
            RELEASE,
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert {path.name for path in report_dir.glob("*.json")} == set()
    payload = _read_json(output_json)
    markdown = output_md.read_text(encoding="utf-8")
    assert payload["status"] == "ops_support_evidence_templates_dry_run"
    assert payload["template_not_evidence"] is True
    assert payload["real_evidence_collected"] is False
    assert "Ops / Support gate expected status: `ops_support_blocked`" in markdown


def test_cli_requires_explicit_write_templates_flag(tmp_path: Path) -> None:
    report_dir = tmp_path / "templates"
    output_json = tmp_path / "summary.json"
    output_md = tmp_path / "summary.md"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.commercial_stage5_ops_support_evidence_templates",
            "--report-dir",
            str(report_dir),
            "--current-head-sha",
            HEAD,
            "--release-sha",
            RELEASE,
            "--write-templates",
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert {path.name for path in report_dir.glob("*.json")} == EXPECTED_FILENAMES
    payload = _read_json(output_json)
    assert payload["status"] == "ops_support_evidence_templates_written"
