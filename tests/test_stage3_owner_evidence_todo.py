from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_stage3_staging_external_evidence_intake import build_owner_draft_payload, write_owner_draft
from scripts.stage3_owner_evidence_todo import build_stage3_owner_evidence_todo, main

HEAD = "dca6a063e9c21ee5e420d3346c28735b17a92fdf"
DIGEST = "sha256:" + "a" * 64


def test_owner_evidence_todo_lists_template_fields(tmp_path: Path) -> None:
    draft_json = tmp_path / "owner-draft.json"
    payload = build_owner_draft_payload(
        current_head_sha=HEAD,
        release_sha=HEAD,
        expected_image_digest=DIGEST,
        domain="xagent.example.com",
    )
    write_owner_draft(payload, output_json=draft_json, output_md=tmp_path / "owner-draft.md")

    report = build_stage3_owner_evidence_todo(draft_json)

    assert report.status == "stage3_owner_evidence_todo_ready"
    assert report.mutation_performed is False
    assert report.deploy_performed is False
    assert report.workflow_dispatch_performed is False
    assert report.raw_secret_values_recorded is False
    fields = {item.field: item for item in report.items}
    assert fields["template_not_external_evidence"].category == "final_toggle"
    assert fields["staging_environment_protection.secret_binding.redaction_confirmed"].category == "final_toggle"
    assert fields["staging_environment_protection.deployed_image.not_external_deploy_proof"].category == "final_toggle"
    assert fields["staging_environment_protection.owner_approval.approval_ref"].category == "owner_decision"
    assert fields["staging_environment_protection.secret_binding.secret_refs"].category == "owner_secret_ref"
    assert "draft is still marked template_not_external_evidence=true" in report.blocked_reasons
    assert report.todo_count == len(report.items)


def test_owner_evidence_todo_clear_when_real_refs_are_present(tmp_path: Path) -> None:
    draft_json = tmp_path / "owner-draft.json"
    payload = build_owner_draft_payload(
        current_head_sha=HEAD,
        release_sha=HEAD,
        expected_image_digest=DIGEST,
        domain="xagent.example.com",
    )
    payload["template_not_external_evidence"] = False
    payload["staging_deploy_run"].update(
        {
            "deploy_ref": "https://evidence.example/deploy",
            "image_ref": "registry.example/xagent@sha256:" + "b" * 64,
            "completed_at": "2026-06-18T00:00:00Z",
            "external_evidence_ref": "https://evidence.example/deploy-log",
            "checks": [{"name": "deploy", "status": "passed"}],
        }
    )
    payload["staging_smoke_tests"].update(
        {
            "health_ref": "https://evidence.example/health",
            "ready_ref": "https://evidence.example/ready",
            "smoke_ref": "https://evidence.example/smoke",
            "completed_at": "2026-06-18T00:01:00Z",
            "external_evidence_ref": "https://evidence.example/smoke-log",
            "checks": [{"name": "smoke", "status": "passed"}],
        }
    )
    payload["staging_rollback_rehearsal"].update(
        {
            "rollback_ref": "https://evidence.example/rollback",
            "post_rollback_health_ref": "https://evidence.example/post-health",
            "post_rollback_ready_ref": "https://evidence.example/post-ready",
            "completed_at": "2026-06-18T00:02:00Z",
            "external_evidence_ref": "https://evidence.example/rollback-log",
            "checks": [{"name": "rollback", "status": "passed"}],
        }
    )
    payload["staging_observability"]["workflow_event_broker"]["health_ref"] = "https://evidence.example/broker"
    payload["staging_observability"]["langfuse"]["trace_ref"] = "https://evidence.example/trace"
    payload["staging_observability"]["sentry"]["event_ref"] = "https://evidence.example/sentry"
    payload["staging_observability"]["metrics"]["metrics_ref"] = "https://evidence.example/metrics"
    payload["staging_observability"]["alerting"]["alert_ref"] = "https://evidence.example/alert-or-exception"
    protection = payload["staging_environment_protection"]
    protection["external_endpoint"].update(
        {
            "health_ref": "https://evidence.example/health-ref",
            "ready_ref": "https://evidence.example/ready-ref",
            "ingress_ref": "https://evidence.example/nginx",
        }
    )
    protection["dns_tls"].update(
        {
            "dns_ref": "https://evidence.example/dns",
            "tls_ref": "https://evidence.example/tls",
        }
    )
    protection["secret_binding"].update(
        {
            "secret_refs": ["secret-manager://xagent/stage3"],
            "redaction_confirmed": True,
        }
    )
    protection["deployed_image"].update(
        {
            "image_ref": "registry.example/xagent@sha256:" + "b" * 64,
            "digest": DIGEST,
            "not_external_deploy_proof": False,
        }
    )
    protection["github_environment"]["required_reviewer"] = "xiongpinji"
    protection["owner_approval"].update(
        {
            "owner": "xiongpinji",
            "approval_ref": "https://evidence.example/approval",
            "approved_at": "2026-06-18T00:03:00Z",
        }
    )
    draft_json.write_text(json.dumps(payload), encoding="utf-8")

    report = build_stage3_owner_evidence_todo(draft_json)

    assert report.status == "stage3_owner_evidence_todo_clear"
    assert report.todo_count == 0
    assert report.items == []
    assert report.blocked_reasons == []


def test_owner_evidence_todo_cli_writes_reports_without_secrets(tmp_path: Path) -> None:
    draft_json = tmp_path / "owner-draft.json"
    output_json = tmp_path / "todo.json"
    output_md = tmp_path / "todo.md"
    payload = build_owner_draft_payload(current_head_sha=HEAD, release_sha=HEAD, domain="xagent.example.com")
    write_owner_draft(payload, output_json=draft_json, output_md=tmp_path / "owner-draft.md")

    rc = main(
        [
            "--input-json",
            str(draft_json),
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ]
    )

    assert rc == 0
    generated = json.loads(output_json.read_text(encoding="utf-8"))
    markdown = output_md.read_text(encoding="utf-8")
    assert generated["status"] == "stage3_owner_evidence_todo_ready"
    assert generated["mutation_performed"] is False
    assert generated["raw_secret_values_recorded"] is False
    assert "Stage3 Owner Evidence Todo" in markdown
    assert "## What To Do Next" in markdown
    assert "## Grouped Todo" in markdown
    assert "Owner Decisions You Must Approve" in markdown
    assert "Codex Can Prefill After Real DNS/TLS" in markdown
    assert "Secret References Only" in markdown
    assert "Final Switches After Review" in markdown
    assert "Do not edit secret values into any file" in markdown
    assert "## Field Detail" in markdown
    assert "sk-" not in markdown
    assert "password=" not in markdown.lower()


def test_owner_evidence_todo_reports_missing_input(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"

    report = build_stage3_owner_evidence_todo(missing)

    assert report.status == "stage3_owner_evidence_todo_ready"
    assert any("input draft is missing" in reason for reason in report.blocked_reasons)
    assert report.mutation_performed is False
