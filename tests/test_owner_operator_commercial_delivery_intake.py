from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.owner_operator_commercial_delivery_intake import (
    build_intake_report,
    build_template_payload,
    write_json,
)

SHA = "adbce7a93854870ef665fe03c39051491a90b9d6"
OTHER_SHA = "0000000000000000000000000000000000000000"


def _complete_payload() -> dict[str, object]:
    payload = build_template_payload(SHA)
    owner = payload["owner_gate_refs"]
    assert isinstance(owner, dict)
    owner["owner_approval"] = {
        "target_sha": SHA,
        "approval_ref": "https://evidence.example.invalid/owner-approval",
        "approval_timestamp": "2026-06-17T10:00:00Z",
        "approver_identity_ref": "owner:x-agent-release",
        "approved_scope": "sha+stage3+commercial-rc",
    }
    owner["provider"] = {
        "provider_backend": "openai",
        "model_ref": "gpt-5.4",
        "credential_variable_name": "XAGENT_OPENAI_API_KEY",
        "provider_smoke_ref": "run:provider-smoke",
        "status": "passed",
    }
    owner["feishu_webhook_contract"] = {
        "app_id_variable_name": "XAGENT_FEISHU_APP_ID",
        "app_secret_variable_name": "XAGENT_FEISHU_APP_SECRET",
        "encrypt_key_variable_name": "XAGENT_FEISHU_ENCRYPT_KEY",
        "verification_ref": "run:feishu-contract",
        "status": "passed",
    }
    owner["github_issue_to_pr_dry_run"] = {
        "disposable_issue_ref": "https://github.example.invalid/org/repo/issues/1",
        "repository_ref": "org/repo",
        "dry_run_ref": "run:issue-to-pr-dry-run",
        "no_execute_mutation_status": "passed",
    }
    owner["github_issue_to_pr_execute_preflight"] = {
        "github_token_variable_name": "XAGENT_GITHUB_TOKEN",
        "disposable_issue_ref": "https://github.example.invalid/org/repo/issues/1",
        "issue_probe_ref": "run:issue-probe",
        "repo_permission_probe_ref": "run:repo-permission-probe",
        "no_mutation_status": "passed",
    }
    owner["hosted_github_actions_commercial_rc"] = {
        "run_ref": "https://github.example.invalid/org/repo/actions/runs/123",
        "head_sha": SHA,
        "linux_job_status": "success",
        "windows_installer_job_status": "success",
        "evidence_artifact_ref": "artifact:commercial-rc-evidence",
        "artifact_digest_ref": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
    }
    owner["refresh_release_chain_owner_verified"] = {
        "owner_verified_ref": "run:owner-verified-refresh",
        "status": "passed",
        "timestamp": "2026-06-17T10:30:00Z",
    }

    stage3 = payload["stage3_production_refs"]
    assert isinstance(stage3, dict)
    stage3["external_endpoint"] = {
        "public_https_endpoint": "https://x-agent.example.invalid",
        "health_url": "https://x-agent.example.invalid/health",
        "ready_url": "https://x-agent.example.invalid/ready",
        "smoke_run_ref": "run:external-smoke",
        "smoke_status": "passed",
        "timestamp": "2026-06-17T10:10:00Z",
    }
    stage3["dns_tls_lb_ingress"] = {
        "hostname": "x-agent.example.invalid",
        "dns_record_ref": "dns:x-agent",
        "tls_certificate_ref": "tls:x-agent",
        "ingress_ref": "ingress:x-agent",
        "load_balancer_ref": "lb:x-agent",
        "environment_name": "stage3",
    }
    stage3["deployed_image"] = {
        "image_ref": "ghcr.io/example/x-agent@sha256:2222222222222222222222222222222222222222222222222222222222222222",
        "digest": "sha256:2222222222222222222222222222222222222222222222222222222222222222",
        "workload_imageid_ref": "k8s:pod/x-agent imageID sha256:2222",
        "provenance_ref": "artifact:provenance",
        "rollout_ref": "rollout:x-agent",
    }
    stage3["observability"] = {
        "metrics_ref": "dashboard:metrics",
        "alert_ref": "alert:x-agent",
        "log_search_ref": "logs:correlation-123",
        "rabbitmq_health_ref": "rabbitmq:health",
        "langfuse_trace_ref": "trace:langfuse",
        "sentry_event_ref": "sentry:event",
    }
    stage3["runtime_bindings"] = {
        "db_binding_ref": "binding:db",
        "redis_binding_ref": "binding:redis",
        "rabbitmq_binding_ref": "binding:rabbitmq",
        "qdrant_binding_ref": "binding:qdrant",
        "neo4j_binding_ref": "binding:neo4j",
        "langfuse_binding_ref": "binding:langfuse",
        "sentry_event_ref": "sentry:event",
    }
    stage3["external_secret_eso"] = {
        "eso_ready_ref": "eso:ready",
        "cluster_secret_store_name": "xagent-secret-store",
        "cluster_secret_store_ready_ref": "clustersecretstore:xagent ready",
        "external_secret_object_refs": ["externalsecret:xagent-app synced"],
        "target_secret_object_names": ["xagent-app-secrets"],
        "expected_key_names": ["DATABASE_URL", "REDIS_URL", "RABBITMQ_URL"],
        "workload_secretkeyref_refs": ["deployment:xagent-api envFrom secretKeyRef"],
    }
    stage3["rollback"] = {
        "rollback_run_ref": "run:rollback",
        "rollback_target_ref": "release:previous",
        "pre_rollback_digest": "sha256:2222222222222222222222222222222222222222222222222222222222222222",
        "post_rollback_digest": "sha256:3333333333333333333333333333333333333333333333333333333333333333",
        "post_rollback_health_ref": "health:post-rollback",
        "started_at": "2026-06-17T10:15:00Z",
        "completed_at": "2026-06-17T10:20:00Z",
    }
    stage3["owner_approval"] = {
        "approval_ref": "https://evidence.example.invalid/stage3-approval",
        "approval_timestamp": "2026-06-17T10:00:00Z",
        "approver_identity_ref": "owner:x-agent-release",
        "environment_name": "stage3",
        "release_sha": SHA,
    }
    stage3["stage3_run_artifacts"] = {
        "stage3_run_ref": "run:stage3",
        "stage3_artifact_ref": "artifact:stage3-evidence",
        "stage3_artifact_digest_ref": "sha256:4444444444444444444444444444444444444444444444444444444444444444",
    }
    stage3["production_readiness_acceptance"] = {
        "acceptance_ref": "https://evidence.example.invalid/prod-readiness",
        "acceptance_timestamp": "2026-06-17T10:40:00Z",
        "accepted_sha_environment_boundary": f"{SHA}:stage3",
    }

    panda = payload["panda_frontend_decisions"]
    assert isinstance(panda, dict)
    for key, section in panda.items():
        assert isinstance(section, dict)
        section["disposition"] = "include"
        section["owner_ref"] = f"review:{key}"
        section["tag_impact"] = "required"
        if "paths" in section:
            section["paths"] = ["frontend/src/panda/assets/roles/reference-ceo.png"]
        if "paths_or_pattern" in section:
            section["paths_or_pattern"] = "frontend/src/panda/assets/roles/*.png"
        if "artifact_refs" in section:
            section["artifact_refs"] = [".xagent_runtime/reports/frontend-browser-smoke.json"]
        if "refs" in section:
            section["refs"] = [f"ref:{key}"]
        if "wording" in section:
            section["wording"] = "Panda frontend bounded smoke evidence available."
        if "permitted_wording" in section:
            section["permitted_wording"] = "Bounded Panda/browser evidence only."
    return payload


def test_missing_input_blocks_without_mutation(tmp_path: Path) -> None:
    report = build_intake_report(tmp_path / "missing.json")

    assert report.status == "owner_operator_commercial_delivery_intake_blocked"
    assert report.input_loaded is False
    assert report.ready_for_review is False
    assert report.mutation_performed is False
    assert report.owner_gate_execution_performed is False
    assert report.stage3_execution_performed is False
    assert report.release_refresh_performed is False
    assert report.final_gate_performed is False


def test_complete_owner_operator_input_is_ready_for_review(tmp_path: Path) -> None:
    input_path = tmp_path / "owner-input.json"
    write_json(_complete_payload(), input_path)

    report = build_intake_report(input_path)

    assert report.status == "owner_operator_commercial_delivery_intake_ready_for_review"
    assert report.ready_for_review is True
    assert report.intake_only_not_evidence is True
    assert report.missing_fields == []
    assert report.redaction_violations == []
    assert report.rejected_inputs == []
    assert report.tag_blockers == []
    assert all(check.status == "passed" for check in report.checks)


def test_missing_owner_gate_refs_block_review(tmp_path: Path) -> None:
    payload = _complete_payload()
    owner = payload["owner_gate_refs"]
    assert isinstance(owner, dict)
    provider = owner["provider"]
    assert isinstance(provider, dict)
    provider["provider_smoke_ref"] = ""
    input_path = tmp_path / "owner-input.json"
    write_json(payload, input_path)

    report = build_intake_report(input_path)

    assert report.ready_for_review is False
    assert "owner_gate_refs.provider.provider_smoke_ref" in report.missing_fields
    assert "owner/operator returned input has missing required fields" in report.tag_blockers


def test_missing_stage3_runtime_bindings_and_eso_refs_block_review(tmp_path: Path) -> None:
    payload = _complete_payload()
    stage3 = payload["stage3_production_refs"]
    assert isinstance(stage3, dict)
    runtime = stage3["runtime_bindings"]
    eso = stage3["external_secret_eso"]
    assert isinstance(runtime, dict)
    assert isinstance(eso, dict)
    runtime["redis_binding_ref"] = ""
    eso["workload_secretkeyref_refs"] = []
    input_path = tmp_path / "owner-input.json"
    write_json(payload, input_path)

    report = build_intake_report(input_path)

    assert report.ready_for_review is False
    assert "stage3_production_refs.runtime_bindings.redis_binding_ref" in report.missing_fields
    assert "stage3_production_refs.external_secret_eso.workload_secretkeyref_refs" in report.missing_fields
    assert "owner/operator returned input has missing required fields" in report.tag_blockers


def test_secret_values_are_rejected_without_embedding_secret(tmp_path: Path) -> None:
    payload = _complete_payload()
    owner = payload["owner_gate_refs"]
    assert isinstance(owner, dict)
    provider = owner["provider"]
    assert isinstance(provider, dict)
    provider["secret"] = "sk-thismustnotbeaccepted123456"
    input_path = tmp_path / "owner-input.json"
    write_json(payload, input_path)

    report = build_intake_report(input_path)
    serialized = json.dumps(report.to_dict())

    assert report.ready_for_review is False
    assert "owner_gate_refs.provider.secret" in report.redaction_violations
    assert "sk-thismustnotbeaccepted123456" not in serialized
    assert report.raw_secret_values_recorded is False


def test_secret_aliases_and_bearer_values_are_rejected_without_embedding_secret(tmp_path: Path) -> None:
    payload = _complete_payload()
    owner = payload["owner_gate_refs"]
    assert isinstance(owner, dict)
    provider = owner["provider"]
    assert isinstance(provider, dict)
    provider["client_secret"] = "not-written-to-report"
    provider["access_token"] = "Bearer abcdefghijklmnopqrstuvwxyz1234567890"
    input_path = tmp_path / "owner-input.json"
    write_json(payload, input_path)

    report = build_intake_report(input_path)
    serialized = json.dumps(report.to_dict())

    assert report.ready_for_review is False
    assert "owner_gate_refs.provider.client_secret" in report.redaction_violations
    assert "owner_gate_refs.provider.access_token" in report.redaction_violations
    assert "Bearer abcdefghijklmnopqrstuvwxyz1234567890" not in serialized
    assert "not-written-to-report" not in serialized


def test_sha_mismatch_blocks_intake(tmp_path: Path) -> None:
    payload = _complete_payload()
    owner = payload["owner_gate_refs"]
    assert isinstance(owner, dict)
    hosted = owner["hosted_github_actions_commercial_rc"]
    assert isinstance(hosted, dict)
    hosted["head_sha"] = OTHER_SHA
    input_path = tmp_path / "owner-input.json"
    write_json(payload, input_path)

    report = build_intake_report(input_path)

    assert report.ready_for_review is False
    assert "owner_gate_refs.hosted_github_actions_commercial_rc.head_sha" in report.rejected_inputs
    assert "owner/operator returned input has SHA boundary mismatches" in report.tag_blockers


def test_sha_boundary_substring_mismatch_blocks_intake(tmp_path: Path) -> None:
    payload = _complete_payload()
    stage3 = payload["stage3_production_refs"]
    assert isinstance(stage3, dict)
    acceptance = stage3["production_readiness_acceptance"]
    assert isinstance(acceptance, dict)
    acceptance["accepted_sha_environment_boundary"] = f"{OTHER_SHA}:stage3"
    input_path = tmp_path / "owner-input.json"
    write_json(payload, input_path)

    report = build_intake_report(input_path)

    assert report.ready_for_review is False
    assert "stage3_production_refs.production_readiness_acceptance.accepted_sha_environment_boundary" in (
        report.rejected_inputs
    )
    assert "owner/operator returned input has SHA boundary mismatches" in report.tag_blockers


def test_failed_critical_status_blocks_intake(tmp_path: Path) -> None:
    payload = _complete_payload()
    owner = payload["owner_gate_refs"]
    stage3 = payload["stage3_production_refs"]
    assert isinstance(owner, dict)
    assert isinstance(stage3, dict)
    provider = owner["provider"]
    endpoint = stage3["external_endpoint"]
    assert isinstance(provider, dict)
    assert isinstance(endpoint, dict)
    provider["status"] = "failed"
    endpoint["smoke_status"] = "blocked"
    input_path = tmp_path / "owner-input.json"
    write_json(payload, input_path)

    report = build_intake_report(input_path)

    assert report.ready_for_review is False
    assert "owner_gate_refs.provider.status" in report.rejected_inputs
    assert "stage3_production_refs.external_endpoint.smoke_status" in report.rejected_inputs
    assert "owner/operator returned input has non-passing critical status fields" in report.tag_blockers


def test_invalid_panda_disposition_blocks_intake(tmp_path: Path) -> None:
    payload = _complete_payload()
    panda = payload["panda_frontend_decisions"]
    assert isinstance(panda, dict)
    script = panda["panda_qa_smoke_script"]
    assert isinstance(script, dict)
    script["disposition"] = "approve"
    input_path = tmp_path / "owner-input.json"
    write_json(payload, input_path)

    report = build_intake_report(input_path)

    assert report.ready_for_review is False
    assert "panda_frontend_decisions.panda_qa_smoke_script.disposition" in report.rejected_inputs
    assert "Panda/frontend returned decisions contain invalid dispositions" in report.tag_blockers


def test_cli_writes_template_and_blocked_report(tmp_path: Path) -> None:
    template = tmp_path / "template.json"
    report = tmp_path / "report.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/owner_operator_commercial_delivery_intake.py",
            "--input",
            str(tmp_path / "missing.json"),
            "--output",
            str(report),
            "--template-output",
            str(template),
            "--write-template",
            "--fail-blocked",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 1
    assert template.exists()
    assert report.exists()
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["status"] == "owner_operator_commercial_delivery_intake_blocked"
