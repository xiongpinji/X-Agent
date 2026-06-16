from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_environment_rehearsal_gate import build_environment_rehearsal_report
from scripts.commercial_stage3_staging_external_evidence_intake import (
    build_external_evidence_payloads,
    build_intake_report,
    main,
    write_evidence_reports,
)

HEAD = "7cacc8b0ddf6d088e7320062fd256009d3a94e47"
DIGEST = "sha256:b7e46872ff5d44741a884a3ccaa1cae1424427f09c86d74ebd869b490f59759e"
OTHER_DIGEST = "sha256:0000000000000000000000000000000000000000000000000000000000000000"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _input_payload(*, digest: str = DIGEST) -> dict[str, object]:
    return {
        "release_sha": HEAD,
        "staging_observability": {
            "workflow_event_broker": {
                "broker_kind": "rabbitmq",
                "health_ref": "https://evidence.example.invalid/rabbitmq-health",
            },
            "langfuse": {"trace_ref": "https://evidence.example.invalid/langfuse-trace"},
            "sentry": {"event_ref": "https://evidence.example.invalid/sentry-event"},
            "metrics": {"metrics_ref": "https://evidence.example.invalid/metrics"},
            "alerting": {"alert_ref": "https://evidence.example.invalid/alert"},
        },
        "staging_environment_protection": {
            "external_endpoint": {
                "url": "https://staging.example.invalid",
                "ingress_ref": "https://evidence.example.invalid/ingress",
            },
            "dns_tls": {
                "dns_ref": "https://evidence.example.invalid/dns",
                "tls_ref": "https://evidence.example.invalid/tls",
            },
            "secret_binding": {
                "secret_refs": ["github-actions:STAGING_LANGFUSE_PUBLIC_KEY"],
                "redaction_confirmed": True,
            },
            "deployed_image": {
                "image_ref": f"ghcr.io/xiongpinji/x-agent:feat-commercial-delivery-v1@{digest}",
                "digest": digest,
            },
            "github_environment": {"required_reviewer": "xiongpinji"},
            "owner_approval": {
                "owner": "xiongpinji",
                "approval_ref": "https://evidence.example.invalid/owner-approval",
                "approved_at": "2026-06-16T03:39:00Z",
            },
        },
    }


def test_complete_external_evidence_writes_ready_reports_and_gate_accepts(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    _write_json(input_path, _input_payload())

    payloads, checks, input_error = build_external_evidence_payloads(
        input_path=input_path,
        current_head_sha=HEAD,
        release_sha=HEAD,
        expected_image_digest=DIGEST,
    )
    results = write_evidence_reports(
        payloads,
        observability_output=tmp_path / "stage5-staging-observability-20260615.json",
        protection_output=tmp_path / "stage5-staging-environment-protection-20260615.json",
    )
    report = build_intake_report(
        input_path=input_path,
        current_head_sha=HEAD,
        release_sha=HEAD,
        expected_image_digest=DIGEST,
        write_results=results,
        checks=checks,
        input_error=input_error,
    )

    assert report.status == "stage3_staging_external_evidence_ready"
    assert report.real_external_evidence_collected is True
    assert report.mutation_performed is False
    assert report.deploy_performed is False
    assert report.workflow_dispatch_performed is False
    assert report.cluster_mutation_performed is False
    assert report.raw_secret_values_recorded is False
    assert all(result.written for result in results)
    assert all(check.status == "passed" for check in checks)

    for filename, status in {
        "stage5-staging-deploy-run-20260615.json": "staging_deploy_ready",
        "stage5-staging-smoke-tests-20260615.json": "staging_smoke_ready",
        "stage5-staging-rollback-rehearsal-20260615.json": "staging_rollback_ready",
    }.items():
        _write_json(tmp_path / filename, {"status": status, "release_sha": HEAD})

    gate = build_environment_rehearsal_report(
        "staging",
        report_dir=tmp_path,
        current_head_sha=HEAD,
        release_sha=HEAD,
    )
    assert gate.status == "staging_rehearsal_ready"
    assert gate.rehearsal_ready is True
    assert gate.missing_or_mismatched == []


def test_missing_required_fields_keep_observability_blocked(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    payload = _input_payload()
    payload["staging_observability"] = {"workflow_event_broker": {"broker_kind": "rabbitmq"}}
    _write_json(input_path, payload)

    payloads, checks, input_error = build_external_evidence_payloads(
        input_path=input_path,
        current_head_sha=HEAD,
        release_sha=HEAD,
        expected_image_digest=DIGEST,
    )
    results = write_evidence_reports(
        payloads,
        observability_output=tmp_path / "obs.json",
        protection_output=tmp_path / "protection.json",
    )
    report = build_intake_report(
        input_path=input_path,
        current_head_sha=HEAD,
        release_sha=HEAD,
        expected_image_digest=DIGEST,
        write_results=results,
        checks=checks,
        input_error=input_error,
    )

    assert report.status == "stage3_staging_external_evidence_blocked"
    assert "staging_observability" in report.missing_or_blocked_evidence
    observability = json.loads((tmp_path / "obs.json").read_text(encoding="utf-8"))
    assert observability["status"] == "staging_observability_blocked"
    assert "langfuse.trace_ref" in observability["missing_required_fields"]
    missing_check = next(check for check in checks if check.name == "staging_observability_required_fields_present")
    assert missing_check.status == "failed"


def test_secret_like_values_are_rejected_and_not_embedded(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    payload = _input_payload()
    protection = payload["staging_environment_protection"]
    assert isinstance(protection, dict)
    protection["sentry"] = {"dsn": "https://public:sk-secretvalue123456789@sentry.example.invalid/1"}
    _write_json(input_path, payload)

    payloads, checks, input_error = build_external_evidence_payloads(
        input_path=input_path,
        current_head_sha=HEAD,
        release_sha=HEAD,
        expected_image_digest=DIGEST,
    )
    results = write_evidence_reports(
        payloads,
        observability_output=tmp_path / "obs.json",
        protection_output=tmp_path / "protection.json",
    )
    report = build_intake_report(
        input_path=input_path,
        current_head_sha=HEAD,
        release_sha=HEAD,
        expected_image_digest=DIGEST,
        write_results=results,
        checks=checks,
        input_error=input_error,
    )

    assert report.status == "stage3_staging_external_evidence_blocked"
    assert report.raw_secret_values_recorded is False
    generated = json.loads((tmp_path / "protection.json").read_text(encoding="utf-8"))
    assert generated["external_evidence_input_embedded"] is False
    assert generated["raw_secret_values_recorded"] is False
    assert generated["status"] == "staging_environment_protection_blocked"
    assert "staging_environment_protection.sentry.dsn" in generated["secret_redaction_violations"]


def test_environment_protection_blocks_on_image_digest_mismatch(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    _write_json(input_path, _input_payload(digest=OTHER_DIGEST))

    payloads, checks, input_error = build_external_evidence_payloads(
        input_path=input_path,
        current_head_sha=HEAD,
        release_sha=HEAD,
        expected_image_digest=DIGEST,
    )
    results = write_evidence_reports(
        payloads,
        observability_output=tmp_path / "obs.json",
        protection_output=tmp_path / "protection.json",
    )
    report = build_intake_report(
        input_path=input_path,
        current_head_sha=HEAD,
        release_sha=HEAD,
        expected_image_digest=DIGEST,
        write_results=results,
        checks=checks,
        input_error=input_error,
    )

    assert report.status == "stage3_staging_external_evidence_blocked"
    generated = json.loads((tmp_path / "protection.json").read_text(encoding="utf-8"))
    assert generated["status"] == "staging_environment_protection_blocked"
    digest_check = next(
        check for check in checks if check.name == "staging_environment_protection_image_digest_matches_expected"
    )
    assert digest_check.status == "failed"


def test_template_or_advisory_input_cannot_be_accepted_as_real_external_evidence(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    payload = _input_payload()
    payload["template_not_external_evidence"] = True
    protection = payload["staging_environment_protection"]
    assert isinstance(protection, dict)
    deployed_image = protection["deployed_image"]
    assert isinstance(deployed_image, dict)
    deployed_image["not_external_deploy_proof"] = True
    deployed_image["source"] = "advisory_build_and_scan_only"
    _write_json(input_path, payload)

    payloads, checks, input_error = build_external_evidence_payloads(
        input_path=input_path,
        current_head_sha=HEAD,
        release_sha=HEAD,
        expected_image_digest=DIGEST,
    )
    results = write_evidence_reports(
        payloads,
        observability_output=tmp_path / "obs.json",
        protection_output=tmp_path / "protection.json",
    )
    report = build_intake_report(
        input_path=input_path,
        current_head_sha=HEAD,
        release_sha=HEAD,
        expected_image_digest=DIGEST,
        write_results=results,
        checks=checks,
        input_error=input_error,
    )

    assert report.status == "stage3_staging_external_evidence_blocked"
    assert report.real_external_evidence_collected is False
    generated = json.loads((tmp_path / "protection.json").read_text(encoding="utf-8"))
    assert generated["status"] == "staging_environment_protection_blocked"
    assert generated["template_not_evidence"] is True
    assert generated["not_external_deploy_proof"] is True
    template_check = next(check for check in checks if check.name == "staging_environment_protection_not_template")
    deploy_proof_check = next(
        check for check in checks if check.name == "staging_environment_protection_deployed_image_is_external_proof"
    )
    assert template_check.status == "failed"
    assert deploy_proof_check.status == "failed"


def test_cli_writes_summary_and_blocked_reports_for_missing_input(tmp_path: Path) -> None:
    rc = main(
        [
            "--input-json",
            str(tmp_path / "missing.json"),
            "--current-head-sha",
            HEAD,
            "--release-sha",
            HEAD,
            "--expected-image-digest",
            DIGEST,
            "--observability-output",
            str(tmp_path / "obs.json"),
            "--environment-protection-output",
            str(tmp_path / "protection.json"),
            "--output-json",
            str(tmp_path / "summary.json"),
            "--output-md",
            str(tmp_path / "summary.md"),
        ]
    )

    assert rc == 1
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    markdown = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert summary["status"] == "stage3_staging_external_evidence_blocked"
    assert summary["input_loaded"] is False
    assert summary["deploy_performed"] is False
    assert summary["workflow_dispatch_performed"] is False
    assert "Stage 3 Staging External Evidence Intake" in markdown
    assert json.loads((tmp_path / "obs.json").read_text(encoding="utf-8"))["status"] == "staging_observability_blocked"
    assert (
        json.loads((tmp_path / "protection.json").read_text(encoding="utf-8"))["status"]
        == "staging_environment_protection_blocked"
    )
