from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.commercial_artifacts_release_gate import build_artifacts_release_gate
from scripts.commercial_stage5_artifact_evidence_pack import build_artifact_evidence_pack
from scripts.commercial_stage5_artifact_evidence_templates import (
    TEMPLATE_FILENAMES,
    build_template_payloads,
    write_templates,
)


SCRIPT_PATH = Path("scripts/commercial_stage5_artifact_evidence_templates.py")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_build_template_payloads_are_blocked_templates_not_evidence(tmp_path: Path) -> None:
    payloads = build_template_payloads(
        tmp_path,
        current_head_sha="1" * 40,
        release_sha="2" * 40,
    )

    assert tuple(payloads) == TEMPLATE_FILENAMES
    for filename, payload in payloads.items():
        assert filename in TEMPLATE_FILENAMES
        assert payload["status"] == "blocked"
        assert payload["template_not_evidence"] is True
        assert payload["real_evidence_collected"] is False
        assert payload["mutation_performed"] is False
        assert payload["deploy_performed"] is False
        assert payload["owner_approval_created"] is False
        assert payload["current_head_sha"] == "1" * 40
        assert payload["release_sha"] == "2" * 40
        assert payload["expected_ready_statuses"]
        assert payload["required_owner_or_operator_actions"]

    assert payloads["stage5-image-digests-20260615.json"]["expected_ready_statuses"] == [
        "image_digests_ready",
        "passed",
    ]
    assert payloads["stage5-sbom-20260615.json"]["expected_ready_statuses"] == ["sbom_ready", "passed"]
    assert payloads["stage5-helm-package-20260615.json"]["expected_ready_statuses"] == [
        "helm_package_ready",
        "passed",
    ]


def test_write_templates_creates_all_three_files(tmp_path: Path) -> None:
    results = write_templates(
        tmp_path,
        current_head_sha="3" * 40,
        release_sha="3" * 40,
    )

    assert [result.status for result in results] == ["written", "written", "written"]
    for filename in TEMPLATE_FILENAMES:
        path = tmp_path / filename
        assert path.exists()
        payload = _read_json(path)
        assert payload["status"] == "blocked"
        assert payload["template_not_evidence"] is True
        assert payload["real_evidence_collected"] is False


def test_existing_files_are_not_overwritten_without_force(tmp_path: Path) -> None:
    existing = tmp_path / "stage5-sbom-20260615.json"
    existing.write_text('{"status": "existing-real-or-owner-file"}\n', encoding="utf-8")

    results = write_templates(
        tmp_path,
        current_head_sha="4" * 40,
        release_sha="4" * 40,
    )

    by_name = {Path(result.path).name: result for result in results}
    assert by_name["stage5-sbom-20260615.json"].status == "skipped_existing"
    assert by_name["stage5-sbom-20260615.json"].written is False
    assert _read_json(existing) == {"status": "existing-real-or-owner-file"}
    assert (tmp_path / "stage5-image-digests-20260615.json").exists()
    assert (tmp_path / "stage5-helm-package-20260615.json").exists()


def test_force_refuses_to_overwrite_real_evidence_file(tmp_path: Path) -> None:
    existing = tmp_path / "stage5-sbom-20260615.json"
    existing.write_text('{"status": "sbom_ready", "real_evidence_collected": true}\n', encoding="utf-8")

    results = write_templates(
        tmp_path,
        current_head_sha="5" * 40,
        release_sha="5" * 40,
        force=True,
    )

    by_name = {Path(result.path).name: result for result in results}
    skipped = by_name["stage5-sbom-20260615.json"]
    assert skipped.status == "skipped_existing_real_evidence"
    assert skipped.written is False
    assert skipped.error
    assert _read_json(existing) == {"status": "sbom_ready", "real_evidence_collected": True}


def test_force_overwrites_template_files(tmp_path: Path) -> None:
    for filename in TEMPLATE_FILENAMES:
        (tmp_path / filename).write_text(
            '{"status": "blocked", "template_not_evidence": true, "real_evidence_collected": false}\n',
            encoding="utf-8",
        )

    results = write_templates(
        tmp_path,
        current_head_sha="5" * 40,
        release_sha="5" * 40,
        force=True,
    )

    assert [result.status for result in results] == ["written", "written", "written"]
    assert all(result.force for result in results)
    for filename in TEMPLATE_FILENAMES:
        payload = _read_json(tmp_path / filename)
        assert payload["status"] == "blocked"
        assert payload["template_not_evidence"] is True
        assert payload["current_head_sha"] == "5" * 40


def test_artifact_release_gate_still_blocks_with_generated_templates(tmp_path: Path) -> None:
    report_dir = tmp_path / ".xagent_runtime" / "reports"
    release_dir = tmp_path / ".xagent_runtime" / "release"
    write_templates(
        report_dir,
        current_head_sha="6" * 40,
        release_sha="6" * 40,
    )

    report = build_artifacts_release_gate(
        report_dir=report_dir,
        release_dir=release_dir,
        root=tmp_path,
        current_head_sha="6" * 40,
        release_sha="6" * 40,
    )

    assert report.status == "artifacts_release_blocked"
    assert report.artifacts_release_ready is False
    assert {"image_digests", "sbom", "helm_package"}.issubset(report.missing_or_mismatched)
    assert all(
        next(item for item in report.evidence if item.name == name).status == "blocked"
        for name in ("image_digests", "sbom", "helm_package")
    )


def test_artifact_evidence_pack_still_blocks_with_generated_templates(tmp_path: Path) -> None:
    report_dir = tmp_path / ".xagent_runtime" / "reports"
    release_dir = tmp_path / ".xagent_runtime" / "release"
    write_templates(
        report_dir,
        current_head_sha="7" * 40,
        release_sha="7" * 40,
    )

    pack = build_artifact_evidence_pack(
        report_dir=report_dir,
        release_dir=release_dir,
        root=tmp_path,
        current_head_sha="7" * 40,
        release_sha="7" * 40,
    )

    assert pack.status == "artifact_evidence_pack_blocked"
    assert pack.controlled_commercial_pilot_ready is False
    assert pack.production_ready is False
    assert pack.ga_ready is False
    assert pack.deploy_performed is False
    assert {"image_digests", "sbom", "helm_package"}.issubset(pack.missing_or_mismatched)
    assert all(
        next(item for item in pack.evidence if item.name == name).status == "blocked"
        for name in ("image_digests", "sbom", "helm_package")
    )


def test_cli_defaults_to_dry_run_json_md_summary_into_tmp_path(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports"
    output_json = tmp_path / "worker-report.json"
    output_md = tmp_path / "worker-report.md"

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--report-dir",
            str(report_dir),
            "--current-head-sha",
            "8" * 40,
            "--release-sha",
            "8" * 40,
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert output_json.exists()
    assert output_md.exists()
    payload = _read_json(output_json)
    assert payload["status"] == "artifact_evidence_templates_dry_run"
    assert payload["template_not_evidence"] is True
    assert payload["real_evidence_collected"] is False
    assert payload["mutation_performed"] is False
    assert payload["deploy_performed"] is False
    assert payload["owner_approval_created"] is False
    assert payload["artifact_release_gate_expected_status"] == "artifacts_release_blocked"
    assert payload["artifact_evidence_pack_expected_status"] == "artifact_evidence_pack_blocked"
    assert len(payload["templates"]) == 3
    markdown = output_md.read_text(encoding="utf-8")
    assert "Stage 5 Artifact Evidence Templates Worker" in markdown
    assert "artifact_evidence_templates_dry_run" in markdown
    for filename in TEMPLATE_FILENAMES:
        assert not (report_dir / filename).exists()


def test_cli_requires_explicit_write_templates_flag(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports"
    output_json = tmp_path / "worker-report.json"
    output_md = tmp_path / "worker-report.md"

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--report-dir",
            str(report_dir),
            "--current-head-sha",
            "8" * 40,
            "--release-sha",
            "8" * 40,
            "--write-templates",
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = _read_json(output_json)
    assert payload["status"] == "artifact_evidence_templates_written"
    for filename in TEMPLATE_FILENAMES:
        assert (report_dir / filename).exists()
