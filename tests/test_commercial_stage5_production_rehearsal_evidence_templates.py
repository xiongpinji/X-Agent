from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_environment_rehearsal_gate import (
    build_environment_rehearsal_report,
    default_evidence_specs,
)
from scripts.commercial_stage5_production_rehearsal_evidence_templates import (
    build_template_payloads,
    main,
    write_templates,
)

HEAD = "84ee203bf6676f3abf86a8f534269e624a99917d"
RELEASE_SHA = "b1f4706448f53643396d0c45bb6e8ba4755e1dfe"


def test_build_template_payloads_uses_production_gate_specs(tmp_path: Path) -> None:
    specs = default_evidence_specs("production", tmp_path)
    payloads = build_template_payloads(tmp_path, current_head_sha=HEAD, release_sha=RELEASE_SHA)

    assert set(payloads) == {spec.path.name for spec in specs}
    assert len(payloads) == 5

    for spec in specs:
        payload = payloads[spec.path.name]
        assert payload["status"] == "blocked"
        assert payload["evidence_name"] == spec.name
        assert Path(payload["evidence_path"]) == spec.path
        assert payload["template_filename"] == spec.path.name
        assert payload["template_not_evidence"] is True
        assert payload["real_evidence_collected"] is False
        assert payload["mutation_performed"] is False
        assert payload["deploy_performed"] is False
        assert payload["owner_approval_created"] is False
        assert payload["workflow_dispatch_performed"] is False
        assert payload["expected_ready_statuses"] == list(spec.expected_statuses)
        assert payload["current_head_sha"] == HEAD
        assert payload["release_sha"] == RELEASE_SHA
        assert payload["required_owner_or_operator_actions"]


def test_write_templates_creates_all_five_blocked_files(tmp_path: Path) -> None:
    results = write_templates(tmp_path, current_head_sha=HEAD, release_sha=HEAD)

    assert len(results) == 5
    assert all(result.written for result in results)
    assert not any(result.skipped_existing for result in results)

    for spec in default_evidence_specs("production", tmp_path):
        payload = json.loads(spec.path.read_text(encoding="utf-8"))
        assert payload["status"] == "blocked"
        assert payload["template_not_evidence"] is True
        assert payload["real_evidence_collected"] is False
        assert payload["current_head_sha"] == HEAD
        assert payload["release_sha"] == HEAD


def test_existing_files_are_not_overwritten_without_force(tmp_path: Path) -> None:
    write_templates(tmp_path, current_head_sha=HEAD, release_sha=HEAD)
    first_spec = default_evidence_specs("production", tmp_path)[0]
    first_spec.path.write_text('{"status":"existing-real-evidence"}\n', encoding="utf-8")

    results = write_templates(tmp_path, current_head_sha=RELEASE_SHA, release_sha=RELEASE_SHA)

    assert all(result.skipped_existing for result in results)
    assert json.loads(first_spec.path.read_text(encoding="utf-8")) == {"status": "existing-real-evidence"}


def test_force_overwrites_template_files(tmp_path: Path) -> None:
    first_spec = default_evidence_specs("production", tmp_path)[0]
    first_spec.path.parent.mkdir(parents=True, exist_ok=True)
    first_spec.path.write_text(
        '{"status":"blocked","template_not_evidence":true,"real_evidence_collected":false}\n',
        encoding="utf-8",
    )

    results = write_templates(tmp_path, current_head_sha=HEAD, release_sha=RELEASE_SHA, force=True)

    assert any(result.name == first_spec.name and result.written for result in results)
    payload = json.loads(first_spec.path.read_text(encoding="utf-8"))
    assert payload["status"] == "blocked"
    assert payload["template_not_evidence"] is True
    assert payload["release_sha"] == RELEASE_SHA


def test_force_refuses_to_overwrite_real_evidence_file(tmp_path: Path) -> None:
    first_spec = default_evidence_specs("production", tmp_path)[0]
    first_spec.path.parent.mkdir(parents=True, exist_ok=True)
    first_spec.path.write_text(
        '{"status":"production_deploy_rehearsal_ready","real_evidence_collected":true}\n',
        encoding="utf-8",
    )

    results = write_templates(tmp_path, current_head_sha=HEAD, release_sha=RELEASE_SHA, force=True)

    skipped = next(item for item in results if item.name == first_spec.name)
    assert skipped.status == "skipped_existing_real_evidence"
    assert skipped.written is False
    assert skipped.error
    assert json.loads(first_spec.path.read_text(encoding="utf-8")) == {
        "status": "production_deploy_rehearsal_ready",
        "real_evidence_collected": True,
    }


def test_environment_rehearsal_gate_still_blocks_with_generated_templates(tmp_path: Path) -> None:
    write_templates(tmp_path, current_head_sha=HEAD, release_sha=HEAD)

    report = build_environment_rehearsal_report(
        "production",
        report_dir=tmp_path,
        current_head_sha=HEAD,
        release_sha=HEAD,
    )

    assert report.status == "production_rehearsal_blocked"
    assert report.rehearsal_ready is False
    assert set(report.missing_or_mismatched) == {
        spec.name for spec in default_evidence_specs("production", tmp_path)
    }
    assert all(item.status == "blocked" for item in report.evidence)
    assert all(not item.ready for item in report.evidence)
    assert report.mutation_performed is False
    assert report.deploy_tag_release_performed is False
    assert report.workflow_dispatch_performed is False


def test_cli_defaults_to_dry_run_json_markdown_summary(tmp_path: Path) -> None:
    output_json = tmp_path / "worker.json"
    output_md = tmp_path / "worker.md"

    rc = main(
        [
            "--report-dir",
            str(tmp_path),
            "--current-head-sha",
            HEAD,
            "--release-sha",
            HEAD,
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ]
    )

    assert rc == 0
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    markdown = output_md.read_text(encoding="utf-8")
    assert payload["status"] == "production_rehearsal_evidence_templates_dry_run"
    assert payload["template_not_evidence"] is True
    assert payload["real_evidence_collected"] is False
    assert payload["deploy_performed"] is False
    assert payload["owner_approval_created"] is False
    assert payload["workflow_dispatch_performed"] is False
    assert len(payload["templates"]) == 5
    assert all(item["status"] == "dry_run" for item in payload["templates"])
    assert all(not spec.path.exists() for spec in default_evidence_specs("production", tmp_path))
    assert "Stage 5 Production Rehearsal Evidence Templates Worker" in markdown


def test_cli_requires_explicit_write_templates_flag(tmp_path: Path) -> None:
    output_json = tmp_path / "worker.json"
    output_md = tmp_path / "worker.md"

    rc = main(
        [
            "--report-dir",
            str(tmp_path),
            "--current-head-sha",
            HEAD,
            "--release-sha",
            HEAD,
            "--write-templates",
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ]
    )

    assert rc == 0
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["status"] == "production_rehearsal_evidence_templates_written"
    assert all(item["written"] for item in payload["templates"])
    assert all(spec.path.exists() for spec in default_evidence_specs("production", tmp_path))
