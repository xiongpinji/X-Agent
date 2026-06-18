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


def _write_default_staging_ready_evidence(
    report_dir: Path,
    *,
    sha: str = HEAD,
    intake_metadata: bool = True,
    external_environment_metadata: bool = True,
) -> None:
    statuses = {
        "stage5-staging-deploy-run-20260615.json": "staging_deploy_ready",
        "stage5-staging-smoke-tests-20260615.json": "staging_smoke_ready",
        "stage5-staging-rollback-rehearsal-20260615.json": "staging_rollback_ready",
        "stage5-staging-observability-20260615.json": "staging_observability_ready",
        "stage5-staging-environment-protection-20260615.json": "staging_environment_protection_ready",
    }
    for filename, status in statuses.items():
        payload: dict[str, object] = {
            "status": status,
            "release_sha": sha,
            "current_head_sha": sha,
            "evidence_url": f"https://example.invalid/{filename}",
        }
        if external_environment_metadata and filename in {
            "stage5-staging-deploy-run-20260615.json",
            "stage5-staging-smoke-tests-20260615.json",
            "stage5-staging-rollback-rehearsal-20260615.json",
        }:
            payload.update(
                {
                    "real_external_evidence_collected": True,
                    "environment": "staging",
                    "external_evidence_ref": f"https://stage3.example.invalid/evidence/{filename}",
                    "template_not_evidence": False,
                    "raw_secret_values_recorded": False,
                    "workflow_dispatch_performed": False,
                    "outbound_message_sent": False,
                    "tag_performed": False,
                    "release_performed": False,
                    "checks": [
                        {"name": f"{filename}-external-reference", "status": "passed"},
                        {"name": f"{filename}-redaction", "status": "passed"},
                    ],
                }
            )
        if intake_metadata and filename in {
            "stage5-staging-observability-20260615.json",
            "stage5-staging-environment-protection-20260615.json",
        }:
            payload.update(
                {
                    "real_external_evidence_collected": True,
                    "template_not_evidence": False,
                    "external_evidence_input_path": "owner/stage3-evidence.json",
                    "external_evidence_input_embedded": False,
                    "raw_secret_values_recorded": False,
                    "deploy_performed_by_intake": False,
                    "workflow_dispatch_performed": False,
                    "cluster_mutation_performed_by_intake": False,
                    "outbound_message_sent": False,
                    "checks": [
                        {"name": f"{filename}-required-fields", "status": "passed"},
                        {"name": f"{filename}-secret-redaction", "status": "passed"},
                    ],
                }
            )
        _write_json(report_dir / filename, payload)


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


def test_default_staging_rehearsal_accepts_intake_backed_observability_and_protection(
    tmp_path: Path,
) -> None:
    _write_default_staging_ready_evidence(tmp_path)

    report = build_environment_rehearsal_report(
        "staging",
        report_dir=tmp_path,
        current_head_sha=HEAD,
        release_sha=HEAD,
    )

    assert report.status == "staging_rehearsal_ready"
    assert report.rehearsal_ready is True
    assert report.missing_or_mismatched == []
    intake_items = {
        item.name: item
        for item in report.evidence
        if item.name in {"staging_observability", "staging_environment_protection"}
    }
    assert set(intake_items) == {"staging_observability", "staging_environment_protection"}
    assert all(item.external_evidence_metadata_required for item in intake_items.values())
    assert all(item.external_evidence_metadata_valid for item in intake_items.values())
    assert all(item.real_external_evidence_collected is True for item in intake_items.values())
    environment_items = {
        item.name: item
        for item in report.evidence
        if item.name in {"staging_deploy_run", "staging_smoke_tests", "staging_rollback_rehearsal"}
    }
    assert set(environment_items) == {"staging_deploy_run", "staging_smoke_tests", "staging_rollback_rehearsal"}
    assert all(item.external_environment_metadata_required for item in environment_items.values())
    assert all(item.external_environment_metadata_valid for item in environment_items.values())


def test_default_staging_rehearsal_rejects_handwritten_ready_external_evidence(
    tmp_path: Path,
) -> None:
    _write_default_staging_ready_evidence(tmp_path, intake_metadata=False)

    report = build_environment_rehearsal_report(
        "staging",
        report_dir=tmp_path,
        current_head_sha=HEAD,
        release_sha=HEAD,
    )

    assert report.status == "staging_rehearsal_blocked"
    assert set(report.missing_or_mismatched) == {
        "staging_observability",
        "staging_environment_protection",
    }
    for item in report.evidence:
        if item.name in {"staging_observability", "staging_environment_protection"}:
            assert item.external_evidence_metadata_required is True
            assert item.external_evidence_metadata_valid is False
            assert item.error is not None
            assert "real_external_evidence_collected must be true" in item.error
            assert "external_evidence_input_path is missing" in item.error
            assert "intake checks are missing" in item.error


def test_default_staging_rehearsal_rejects_local_equivalent_deploy_smoke_and_rollback(
    tmp_path: Path,
) -> None:
    _write_default_staging_ready_evidence(tmp_path)
    for filename in (
        "stage5-staging-deploy-run-20260615.json",
        "stage5-staging-smoke-tests-20260615.json",
        "stage5-staging-rollback-rehearsal-20260615.json",
    ):
        path = tmp_path / filename
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.update(
            {
                "evidence_class": "local_staging_equivalent",
                "claim_boundary": {"forbidden": ["external staging proven", "GA ready"]},
                "real_external_evidence_collected": False,
                "checks": [{"name": "local-only", "status": "passed"}],
            }
        )
        _write_json(path, payload)

    report = build_environment_rehearsal_report(
        "staging",
        report_dir=tmp_path,
        current_head_sha=HEAD,
        release_sha=HEAD,
    )

    assert report.status == "staging_rehearsal_blocked"
    assert set(report.missing_or_mismatched) == {
        "staging_deploy_run",
        "staging_smoke_tests",
        "staging_rollback_rehearsal",
    }
    for item in report.evidence:
        if item.name in {"staging_deploy_run", "staging_smoke_tests", "staging_rollback_rehearsal"}:
            assert item.external_environment_metadata_required is True
            assert item.external_environment_metadata_valid is False
            assert item.error is not None
            assert "real_external_evidence_collected must be true" in item.error
            assert "evidence_class local_staging_equivalent is not external Stage3 evidence" in item.error
            assert "claim_boundary forbids using this report as external Stage3 evidence" in item.error


def test_default_staging_rehearsal_rejects_external_environment_failed_checks(
    tmp_path: Path,
) -> None:
    _write_default_staging_ready_evidence(tmp_path)
    smoke = tmp_path / "stage5-staging-smoke-tests-20260615.json"
    payload = json.loads(smoke.read_text(encoding="utf-8"))
    payload["checks"] = [{"name": "stage3_smoke_ready_probe", "status": "failed"}]
    payload["external_evidence_ref"] = ""
    payload["evidence_url"] = ""
    _write_json(smoke, payload)

    report = build_environment_rehearsal_report(
        "staging",
        report_dir=tmp_path,
        current_head_sha=HEAD,
        release_sha=HEAD,
    )

    assert report.status == "staging_rehearsal_blocked"
    assert report.missing_or_mismatched == ["staging_smoke_tests"]
    item = next(item for item in report.evidence if item.name == "staging_smoke_tests")
    assert item.external_environment_metadata_valid is False
    assert item.error is not None
    assert "external evidence reference is missing" in item.error
    assert "external environment checks are not all passed: stage3_smoke_ready_probe" in item.error


def test_default_staging_rehearsal_rejects_failed_intake_metadata(tmp_path: Path) -> None:
    _write_default_staging_ready_evidence(tmp_path)
    observability = tmp_path / "stage5-staging-observability-20260615.json"
    payload = json.loads(observability.read_text(encoding="utf-8"))
    payload["checks"] = [{"name": "staging_observability_required_fields_present", "status": "failed"}]
    payload["raw_secret_values_recorded"] = True
    _write_json(observability, payload)

    report = build_environment_rehearsal_report(
        "staging",
        report_dir=tmp_path,
        current_head_sha=HEAD,
        release_sha=HEAD,
    )

    assert report.status == "staging_rehearsal_blocked"
    assert report.missing_or_mismatched == ["staging_observability"]
    item = next(item for item in report.evidence if item.name == "staging_observability")
    assert item.external_evidence_metadata_valid is False
    assert item.error is not None
    assert "raw_secret_values_recorded must be false" in item.error
    assert "intake checks are not all passed: staging_observability_required_fields_present" in item.error
