from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_environment_rehearsal_gate import (
    RehearsalEvidenceSpec,
    build_environment_rehearsal_report,
    render_markdown_report,
    write_markdown_report,
    write_report,
)

HEAD = "84ee203bf6676f3abf86a8f534269e624a99917d"
OTHER_SHA = "b1f4706448f53643396d0c45bb6e8ba4755e1dfe"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _specs(report_dir: Path, environment: str) -> list[RehearsalEvidenceSpec]:
    return [
        RehearsalEvidenceSpec(
            f"{environment}_deploy",
            report_dir / f"{environment}-deploy.json",
            (f"{environment}_deploy_ready", "passed"),
            "deploy evidence",
        ),
        RehearsalEvidenceSpec(
            f"{environment}_smoke",
            report_dir / f"{environment}-smoke.json",
            (f"{environment}_smoke_ready", "passed"),
            "smoke evidence",
        ),
        RehearsalEvidenceSpec(
            f"{environment}_rollback",
            report_dir / f"{environment}-rollback.json",
            (f"{environment}_rollback_ready", "passed"),
            "rollback evidence",
        ),
    ]


def _write_ready_evidence(report_dir: Path, environment: str, *, sha: str = HEAD) -> None:
    for spec in _specs(report_dir, environment):
        _write_json(
            spec.path,
            {
                "status": spec.expected_statuses[0],
                "release_sha": sha,
                "evidence_url": f"https://example.invalid/{spec.name}",
            },
        )


def test_staging_rehearsal_blocks_when_evidence_missing(tmp_path: Path) -> None:
    report = build_environment_rehearsal_report(
        "staging",
        report_dir=tmp_path,
        current_head_sha=HEAD,
        specs=_specs(tmp_path, "staging"),
    )

    assert report.status == "staging_rehearsal_blocked"
    assert report.rehearsal_ready is False
    assert set(report.missing_or_mismatched) == {
        "staging_deploy",
        "staging_smoke",
        "staging_rollback",
    }
    assert report.workflow_dispatch_performed is False
    assert report.cluster_mutation_performed_by_gate is False


def test_production_rehearsal_accepts_complete_temporary_evidence(tmp_path: Path) -> None:
    _write_ready_evidence(tmp_path, "production")

    report = build_environment_rehearsal_report(
        "production",
        report_dir=tmp_path,
        current_head_sha=HEAD,
        specs=_specs(tmp_path, "production"),
    )

    assert report.status == "production_rehearsal_ready"
    assert report.rehearsal_ready is True
    assert report.release_sha == HEAD
    assert report.missing_or_mismatched == []
    assert all(item.ready for item in report.evidence)


def test_rehearsal_blocks_when_required_evidence_is_blocked(tmp_path: Path) -> None:
    _write_ready_evidence(tmp_path, "staging")
    _write_json(
        tmp_path / "staging-smoke.json",
        {
            "status": "staging_smoke_blocked",
            "release_sha": HEAD,
        },
    )

    report = build_environment_rehearsal_report(
        "staging",
        report_dir=tmp_path,
        current_head_sha=HEAD,
        specs=_specs(tmp_path, "staging"),
    )

    assert report.status == "staging_rehearsal_blocked"
    assert "staging_smoke" in report.missing_or_mismatched
    smoke = next(item for item in report.evidence if item.name == "staging_smoke")
    assert smoke.error is not None
    assert "not in expected statuses" in smoke.error


def test_rehearsal_blocks_on_sha_mismatch(tmp_path: Path) -> None:
    _write_ready_evidence(tmp_path, "production", sha=OTHER_SHA)

    report = build_environment_rehearsal_report(
        "production",
        report_dir=tmp_path,
        current_head_sha=HEAD,
        specs=_specs(tmp_path, "production"),
    )

    assert report.status == "production_rehearsal_blocked"
    assert set(report.missing_or_mismatched) == {
        "production_deploy",
        "production_smoke",
        "production_rollback",
    }
    assert all(item.bound_sha == OTHER_SHA for item in report.evidence)


def test_rehearsal_gate_writes_json_and_markdown(tmp_path: Path) -> None:
    _write_ready_evidence(tmp_path, "staging")
    report = build_environment_rehearsal_report(
        "staging",
        report_dir=tmp_path,
        current_head_sha=HEAD,
        specs=_specs(tmp_path, "staging"),
    )
    output_json = tmp_path / "stage3-staging-rehearsal-result-20260615.json"
    output_md = tmp_path / "stage3-staging-rehearsal-result-20260615.md"

    write_report(report, output_json)
    write_markdown_report(report, output_md)

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    markdown = output_md.read_text(encoding="utf-8")
    assert payload["status"] == "staging_rehearsal_ready"
    assert payload["release_sha"] == HEAD
    assert "Stage 5 Staging Rehearsal Gate" in markdown
    assert render_markdown_report(report) == markdown
