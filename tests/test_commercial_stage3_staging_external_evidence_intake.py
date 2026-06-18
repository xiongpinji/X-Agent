from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_environment_rehearsal_gate import build_environment_rehearsal_report
from scripts.commercial_stage3_staging_external_evidence_intake import (
    DEFAULT_INPUT_JSON,
    build_owner_draft_payload,
    build_external_evidence_payloads,
    build_intake_report,
    main,
    write_owner_draft,
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
        "staging_deploy_run": {
            "deploy_ref": "https://evidence.example.invalid/stage3-deploy",
            "image_ref": f"ghcr.io/xiongpinji/x-agent:stage3@{digest}",
            "operator": "xiongpinji",
            "completed_at": "2026-06-16T03:35:00Z",
            "external_evidence_ref": "https://evidence.example.invalid/stage3-deploy",
            "checks": [
                {"name": "stage3_deploy_run_completed", "status": "passed"},
                {"name": "stage3_deploy_release_sha_verified", "status": "passed"},
            ],
        },
        "staging_smoke_tests": {
            "health_ref": "https://evidence.example.invalid/health-probe",
            "ready_ref": "https://evidence.example.invalid/ready-probe",
            "smoke_ref": "https://evidence.example.invalid/stage3-smoke",
            "operator": "xiongpinji",
            "completed_at": "2026-06-16T03:36:00Z",
            "external_evidence_ref": "https://evidence.example.invalid/stage3-smoke",
            "checks": [
                {"name": "stage3_health_probe_passed", "status": "passed"},
                {"name": "stage3_ready_probe_passed", "status": "passed"},
                {"name": "stage3_smoke_suite_passed", "status": "passed"},
            ],
        },
        "staging_rollback_rehearsal": {
            "rollback_ref": "https://evidence.example.invalid/stage3-rollback",
            "post_rollback_health_ref": "https://evidence.example.invalid/post-rollback-health",
            "post_rollback_ready_ref": "https://evidence.example.invalid/post-rollback-ready",
            "operator": "xiongpinji",
            "completed_at": "2026-06-16T03:37:00Z",
            "external_evidence_ref": "https://evidence.example.invalid/stage3-rollback",
            "checks": [
                {"name": "stage3_rollback_rehearsal_completed", "status": "passed"},
                {"name": "stage3_post_rollback_health_passed", "status": "passed"},
                {"name": "stage3_post_rollback_ready_passed", "status": "passed"},
            ],
        },
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
                "health_ref": "https://evidence.example.invalid/health-probe",
                "ready_ref": "https://evidence.example.invalid/ready-probe",
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
    assert {result.name for result in results} == {
        "staging_deploy_run",
        "staging_smoke_tests",
        "staging_rollback_rehearsal",
        "staging_observability",
        "staging_environment_protection",
    }
    assert all(check.status == "passed" for check in checks)
    assert json.loads((tmp_path / "stage5-staging-deploy-run-20260615.json").read_text(encoding="utf-8"))[
        "status"
    ] == "staging_deploy_ready"
    assert json.loads((tmp_path / "stage5-staging-smoke-tests-20260615.json").read_text(encoding="utf-8"))[
        "status"
    ] == "staging_smoke_ready"
    assert json.loads((tmp_path / "stage5-staging-rollback-rehearsal-20260615.json").read_text(encoding="utf-8"))[
        "status"
    ] == "staging_rollback_ready"

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


def test_missing_external_deploy_reference_keeps_stage3_rehearsal_blocked(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    payload = _input_payload()
    deploy = payload["staging_deploy_run"]
    assert isinstance(deploy, dict)
    deploy.pop("external_evidence_ref")
    _write_json(input_path, payload)

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

    assert report.status == "stage3_staging_external_evidence_blocked"
    assert "staging_deploy_run" in report.missing_or_blocked_evidence
    deploy_report = json.loads((tmp_path / "stage5-staging-deploy-run-20260615.json").read_text(encoding="utf-8"))
    assert deploy_report["status"] == "staging_deploy_run_blocked"
    ref_check = next(check for check in checks if check.name == "staging_deploy_run_external_reference_present")
    assert ref_check.status == "failed"

    gate = build_environment_rehearsal_report(
        "staging",
        report_dir=tmp_path,
        current_head_sha=HEAD,
        release_sha=HEAD,
    )
    assert gate.status == "staging_rehearsal_blocked"
    assert "staging_deploy_run" in gate.missing_or_mismatched


def test_failed_external_rollback_check_keeps_stage3_rehearsal_blocked(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    payload = _input_payload()
    rollback = payload["staging_rollback_rehearsal"]
    assert isinstance(rollback, dict)
    rollback["checks"] = [{"name": "stage3_rollback_rehearsal_completed", "status": "failed"}]
    _write_json(input_path, payload)

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

    assert report.status == "stage3_staging_external_evidence_blocked"
    assert "staging_rollback_rehearsal" in report.missing_or_blocked_evidence
    rollback_report = json.loads(
        (tmp_path / "stage5-staging-rollback-rehearsal-20260615.json").read_text(encoding="utf-8")
    )
    assert rollback_report["status"] == "staging_rollback_rehearsal_blocked"
    checks_passed = next(
        check for check in checks if check.name == "staging_rollback_rehearsal_external_checks_passed"
    )
    assert checks_passed.status == "failed"

    gate = build_environment_rehearsal_report(
        "staging",
        report_dir=tmp_path,
        current_head_sha=HEAD,
        release_sha=HEAD,
    )
    assert gate.status == "staging_rehearsal_blocked"
    assert "staging_rollback_rehearsal" in gate.missing_or_mismatched


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


def test_environment_protection_requires_public_https_domain_endpoint(tmp_path: Path) -> None:
    for unsafe_url in (
        "http://stage3.example.com",
        "https://111.228.49.160",
        "https://xagent.111.228.49.160.sslip.io",
        "https://localhost",
    ):
        input_path = tmp_path / f"{unsafe_url.replace(':', '_').replace('/', '_')}.json"
        payload = _input_payload()
        protection = payload["staging_environment_protection"]
        assert isinstance(protection, dict)
        endpoint = protection["external_endpoint"]
        assert isinstance(endpoint, dict)
        endpoint["url"] = unsafe_url
        _write_json(input_path, payload)

        payloads, checks, input_error = build_external_evidence_payloads(
            input_path=input_path,
            current_head_sha=HEAD,
            release_sha=HEAD,
            expected_image_digest=DIGEST,
        )
        results = write_evidence_reports(
            payloads,
            observability_output=tmp_path / f"{input_path.stem}-obs.json",
            protection_output=tmp_path / f"{input_path.stem}-protection.json",
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
        endpoint_check = next(
            check
            for check in checks
            if check.name == "staging_environment_protection_external_endpoint_uses_public_https_domain"
        )
        assert endpoint_check.status == "failed"
        generated = payloads["staging_environment_protection"]
        assert generated["status"] == "staging_environment_protection_blocked"
        assert generated["external_endpoint_validation_errors"]


def test_environment_protection_requires_health_and_ready_probe_refs(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    payload = _input_payload()
    protection = payload["staging_environment_protection"]
    assert isinstance(protection, dict)
    endpoint = protection["external_endpoint"]
    assert isinstance(endpoint, dict)
    endpoint.pop("health_ref")
    endpoint.pop("ready_ref")
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
    generated = json.loads((tmp_path / "protection.json").read_text(encoding="utf-8"))
    assert "external_endpoint.health_ref" in generated["missing_required_fields"]
    assert "external_endpoint.ready_ref" in generated["missing_required_fields"]


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


def test_owner_draft_contains_required_fields_and_stays_template(tmp_path: Path) -> None:
    draft_json = tmp_path / "owner-draft.json"
    draft_md = tmp_path / "owner-draft.md"

    payload = build_owner_draft_payload(
        current_head_sha=HEAD,
        release_sha=HEAD,
        expected_image_digest=DIGEST,
        domain="stage3.example.com",
        owner="xiongpinji",
    )
    write_owner_draft(payload, output_json=draft_json, output_md=draft_md)

    generated = json.loads(draft_json.read_text(encoding="utf-8"))
    markdown = draft_md.read_text(encoding="utf-8")
    assert generated["template_not_external_evidence"] is True
    assert generated["release_sha"] == HEAD
    assert generated["staging_deploy_run"]["checks"][0]["status"] == "blocked"
    assert generated["staging_smoke_tests"]["checks"][0]["status"] == "blocked"
    assert generated["staging_rollback_rehearsal"]["checks"][0]["status"] == "blocked"
    assert generated["staging_environment_protection"]["external_endpoint"]["url"] == "https://stage3.example.com"
    assert generated["staging_environment_protection"]["secret_binding"]["redaction_confirmed"] is False
    assert generated["staging_environment_protection"]["deployed_image"]["not_external_deploy_proof"] is True
    assert "Stage 3 Owner Evidence Draft" in markdown
    assert "Beginner Fill Order" in markdown
    assert "What Codex Can Fill After You Provide The Domain" in markdown
    assert "What The Owner Must Decide" in markdown
    assert "Exact JSON Fields To Replace" in markdown
    assert "Temporary wildcard DNS such as `sslip.io` is not accepted" in markdown
    assert "`staging_environment_protection.external_endpoint.health_ref`" in markdown
    assert "`staging_observability.alerting.alert_ref`" in markdown
    assert "API key values" in markdown

    for field_name in (
        "workflow_event_broker.health_ref",
        "langfuse.trace_ref",
        "sentry.event_ref",
        "metrics.metrics_ref",
        "alerting.alert_ref",
    ):
        assert field_name not in _missing_fields_from(generated["staging_observability"])

    for field_name in (
        "external_endpoint.url",
        "external_endpoint.health_ref",
        "external_endpoint.ready_ref",
        "external_endpoint.ingress_ref",
        "dns_tls.dns_ref",
        "dns_tls.tls_ref",
        "secret_binding.secret_refs",
        "deployed_image.image_ref",
        "deployed_image.digest",
        "github_environment.required_reviewer",
        "owner_approval.owner",
        "owner_approval.approval_ref",
        "owner_approval.approved_at",
    ):
        assert field_name not in _missing_fields_from(generated["staging_environment_protection"])

    assert "deploy_ref" not in _missing_fields_from(generated["staging_deploy_run"])
    assert "smoke_ref" not in _missing_fields_from(generated["staging_smoke_tests"])
    assert "rollback_ref" not in _missing_fields_from(generated["staging_rollback_rehearsal"])

    serialized = json.dumps(generated, ensure_ascii=False)
    assert "sk-" not in serialized
    assert "ghp_" not in serialized
    assert "Bearer " not in serialized


def test_owner_draft_prefills_https_probe_refs_from_ready_preflight(tmp_path: Path) -> None:
    preflight_report = tmp_path / "stage3-https-preflight.json"
    _write_json(
        preflight_report,
        {
            "status": "stage3_https_preflight_ready",
            "endpoint": "https://stage3.example.com",
            "checks": [
                {"name": "domain_shape", "status": "passed"},
                {"name": "dns_points_to_expected_ip", "status": "passed"},
                {"name": "trusted_https_tls", "status": "passed"},
                {"name": "https_health_probe", "status": "passed"},
                {"name": "https_ready_probe", "status": "passed"},
            ],
        },
    )

    payload = build_owner_draft_payload(
        current_head_sha=HEAD,
        release_sha=HEAD,
        expected_image_digest=DIGEST,
        domain="ignored.example.com",
        https_preflight_report=preflight_report,
    )
    protection = payload["staging_environment_protection"]
    assert isinstance(protection, dict)
    endpoint = protection["external_endpoint"]
    dns_tls = protection["dns_tls"]
    assert isinstance(endpoint, dict)
    assert isinstance(dns_tls, dict)

    assert payload["template_not_external_evidence"] is True
    assert payload["prefill_refs"]["https_preflight_applied"] is True
    assert endpoint["url"] == "https://stage3.example.com"
    assert endpoint["health_ref"].endswith("stage3-https-preflight.json#checks.https_health_probe")
    assert endpoint["ready_ref"].endswith("stage3-https-preflight.json#checks.https_ready_probe")
    assert dns_tls["dns_ref"].endswith("stage3-https-preflight.json#checks.dns_points_to_expected_ip")
    assert dns_tls["tls_ref"].endswith("stage3-https-preflight.json#checks.trusted_https_tls")

    draft_json = tmp_path / "owner-draft.json"
    draft_md = tmp_path / "owner-draft.md"
    write_owner_draft(payload, output_json=draft_json, output_md=draft_md)
    markdown = draft_md.read_text(encoding="utf-8")
    assert "prefill_refs.https_preflight_applied" in markdown
    assert "They are still references only" in markdown

    payloads, checks, input_error = build_external_evidence_payloads(
        input_path=draft_json,
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
        input_path=draft_json,
        current_head_sha=HEAD,
        release_sha=HEAD,
        expected_image_digest=DIGEST,
        write_results=results,
        checks=checks,
        input_error=input_error,
    )
    assert report.status == "stage3_staging_external_evidence_blocked"


def test_owner_draft_rejects_blocked_https_preflight(tmp_path: Path) -> None:
    preflight_report = tmp_path / "stage3-https-preflight.json"
    _write_json(
        preflight_report,
        {
            "status": "stage3_https_preflight_blocked",
            "endpoint": "https://stage3.example.com",
            "checks": [
                {"name": "domain_shape", "status": "passed"},
                {"name": "dns_points_to_expected_ip", "status": "failed"},
            ],
        },
    )

    try:
        build_owner_draft_payload(
            current_head_sha=HEAD,
            release_sha=HEAD,
            https_preflight_report=preflight_report,
        )
    except ValueError as exc:
        assert "HTTPS preflight report is not ready" in str(exc)
    else:
        raise AssertionError("blocked HTTPS preflight report should not prefill owner draft")


def test_owner_draft_cli_reports_blocked_https_preflight_without_traceback(tmp_path: Path) -> None:
    preflight_report = tmp_path / "stage3-https-preflight.json"
    draft_json = tmp_path / "owner-draft.json"
    draft_md = tmp_path / "owner-draft.md"
    _write_json(preflight_report, {"status": "stage3_https_preflight_blocked"})

    rc = main(
        [
            "--write-owner-draft",
            "--current-head-sha",
            HEAD,
            "--release-sha",
            HEAD,
            "--https-preflight-report",
            str(preflight_report),
            "--owner-draft-json",
            str(draft_json),
            "--owner-draft-md",
            str(draft_md),
        ]
    )

    assert rc == 2
    assert not draft_json.exists()
    assert not draft_md.exists()


def test_owner_draft_is_not_accepted_by_intake_until_replaced_with_real_evidence(tmp_path: Path) -> None:
    draft_json = tmp_path / "owner-draft.json"
    payload = build_owner_draft_payload(
        current_head_sha=HEAD,
        release_sha=HEAD,
        expected_image_digest=DIGEST,
        domain="stage3.example.com",
    )
    write_owner_draft(payload, output_json=draft_json, output_md=tmp_path / "owner-draft.md")

    payloads, checks, input_error = build_external_evidence_payloads(
        input_path=draft_json,
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
        input_path=draft_json,
        current_head_sha=HEAD,
        release_sha=HEAD,
        expected_image_digest=DIGEST,
        write_results=results,
        checks=checks,
        input_error=input_error,
    )

    assert report.status == "stage3_staging_external_evidence_blocked"
    assert set(report.missing_or_blocked_evidence) == {
        "staging_deploy_run",
        "staging_smoke_tests",
        "staging_rollback_rehearsal",
        "staging_observability",
        "staging_environment_protection",
    }
    assert next(check for check in checks if check.name == "staging_observability_not_template").status == "failed"
    assert next(check for check in checks if check.name == "staging_environment_protection_not_template").status == "failed"
    assert (
        next(
            check
            for check in checks
            if check.name == "staging_environment_protection_deployed_image_is_external_proof"
        ).status
        == "failed"
    )


def test_owner_draft_cli_writes_separate_files_without_touching_official_input(tmp_path: Path) -> None:
    draft_json = tmp_path / "draft.json"
    draft_md = tmp_path / "draft.md"
    official_input = tmp_path / "official-input.json"
    _write_json(official_input, {"release_sha": "keep-this-file"})

    rc = main(
        [
            "--write-owner-draft",
            "--current-head-sha",
            HEAD,
            "--release-sha",
            HEAD,
            "--expected-image-digest",
            DIGEST,
            "--domain",
            "stage3.example.com",
            "--owner-draft-json",
            str(draft_json),
            "--owner-draft-md",
            str(draft_md),
            "--input-json",
            str(official_input),
        ]
    )

    assert rc == 0
    assert json.loads(official_input.read_text(encoding="utf-8")) == {"release_sha": "keep-this-file"}
    assert json.loads(draft_json.read_text(encoding="utf-8"))["template_not_external_evidence"] is True
    assert "Stage 3 Owner Evidence Draft" in draft_md.read_text(encoding="utf-8")


def test_owner_draft_refuses_to_overwrite_default_input_without_force(tmp_path: Path) -> None:
    output_md = tmp_path / "draft.md"
    rc = main(
        [
            "--write-owner-draft",
            "--current-head-sha",
            HEAD,
            "--release-sha",
            HEAD,
            "--owner-draft-json",
            str(DEFAULT_INPUT_JSON),
            "--owner-draft-md",
            str(output_md),
        ]
    )

    assert rc == 2
    assert not output_md.exists()


def _missing_fields_from(section: dict[str, object]) -> set[str]:
    missing: set[str] = set()

    def nested_value(dotted_path: str) -> object | None:
        value: object = section
        for part in dotted_path.split("."):
            if not isinstance(value, dict) or part not in value:
                return None
            value = value[part]
        return value

    required = {
        "workflow_event_broker.health_ref",
        "langfuse.trace_ref",
        "sentry.event_ref",
        "metrics.metrics_ref",
        "alerting.alert_ref",
        "external_endpoint.url",
        "external_endpoint.health_ref",
        "external_endpoint.ready_ref",
        "external_endpoint.ingress_ref",
        "dns_tls.dns_ref",
        "dns_tls.tls_ref",
        "secret_binding.secret_refs",
        "deployed_image.image_ref",
        "deployed_image.digest",
        "github_environment.required_reviewer",
        "owner_approval.owner",
        "owner_approval.approval_ref",
        "owner_approval.approved_at",
    }
    for field_name in required:
        value = nested_value(field_name)
        if not value:
            missing.add(field_name)
    return missing
