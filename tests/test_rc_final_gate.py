from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.rc_final_gate import run_final_gate


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_bytes(path: Path, payload: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def _verified_external_checks() -> list[dict[str, object]]:
    return [
        {
            "name": "provider",
            "status": "passed",
            "details": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "sentinel": "xagent-rc-ok",
                "sentinel_matched": True,
            },
        },
        {
            "name": "feishu_webhook_contract",
            "status": "passed",
            "details": {
                "app_id_configured": True,
                "app_secret_configured": True,
                "encrypt_key_configured": True,
                "valid_signature_accepted": True,
                "invalid_signature_rejected": True,
                "missing_signature_rejected": True,
                "event_accepted": True,
                "duplicate_rejected": True,
                "event_id": "rc-feishu-smoke",
                "event_type": "im.message.receive_v1",
                "message_id": "om_rc_smoke",
                "outbound_mocked": True,
                "mutation_performed": False,
            },
        },
        {
            "name": "github_issue_to_pr_dry_run",
            "status": "passed",
            "details": {
                "repo_full_name": "acme/project",
                "issue_number": 42,
                "branch_name": "xagent/issue-42",
                "execute_allowed": False,
                "steps": ["parse_issue", "draft_pull_request_payload"],
            },
        },
        {
            "name": "github_issue_to_pr_execute_preflight",
            "status": "passed",
            "details": {
                "dry_run_status": "passed",
                "read_probe": {"status": "passed"},
                "permission_probe": {
                    "status": "passed",
                    "permissions": {"push": True},
                },
                "mutation_performed": False,
            },
        },
        {
            "name": "hosted_github_actions_run",
            "status": "passed",
            "details": {
                "run_url": "https://github.com/acme/x/actions/runs/1",
                "run_status": "completed",
                "conclusion": "success",
                "mutation_performed": False,
            },
        },
    ]


def _candidate_files() -> list[str]:
    return [
        ".github/workflows/commercial-rc.yml",
        "docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md",
        "scripts/rc_final_gate.py",
    ]


def _source_bundle_files(paths: list[str]) -> list[dict[str, object]]:
    return [
        {
            "path": path,
            "size_bytes": 100 + index,
            "sha256": f"{index:064x}",
        }
        for index, path in enumerate(paths, start=1)
    ]


def _staging_plan_payload(paths: list[str], *, errors: list[str] | None = None) -> dict[str, object]:
    return {
        "status": "planned",
        "generated_at": "2026-06-05T10:01:00Z",
        "file_count": len(paths),
        "command_count": 1 if paths else 0,
        "commands": [
            {
                "index": 1,
                "file_count": len(paths),
                "command": "git add -- " + " ".join(f'"{path}"' for path in paths),
                "paths": paths,
            }
        ]
        if paths
        else [],
        "missing_files": [],
        "excluded_files": [],
        "errors": errors or [],
    }


def _gate_summary(checks: list[dict[str, object]]) -> dict[str, object]:
    return {"status": "passed", "checks": checks}


def _owner_handoff_checks() -> list[dict[str, object]]:
    return [
        {"name": "owner_gate_plan", "status": "passed", "details": {}},
        {
            "name": "owner_env_template",
            "status": "passed",
            "details": {"secret_findings": [], "local_path_findings": []},
        },
        {
            "name": "owner_gate_checklist",
            "status": "passed",
            "details": {"secret_findings": [], "local_path_findings": []},
        },
        {"name": "evidence_paths", "status": "passed", "details": {}},
    ]


def _owner_handoff_report(checks: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "status": "passed",
        "generated_at": "2026-06-05T10:01:00Z",
        "inputs": {},
        "checks": checks if checks is not None else _owner_handoff_checks(),
        "next_commands": ["Give rc-owner-env-template.* to the deployment owner."],
    }


def _owner_handoff_receipt_summary() -> dict[str, object]:
    return {
        "status": "passed",
        "checks": [
            {"name": "owner_gate_plan", "status": "passed"},
            {
                "name": "owner_env_template",
                "status": "passed",
                "secret_finding_count": 0,
                "local_path_finding_count": 0,
            },
            {
                "name": "owner_gate_checklist",
                "status": "passed",
                "secret_finding_count": 0,
                "local_path_finding_count": 0,
            },
            {"name": "evidence_paths", "status": "passed"},
        ],
        "next_commands": ["Give rc-owner-env-template.* to the deployment owner."],
    }


def _owner_env_template_summary() -> dict[str, object]:
    return {
        "status": "created",
        "entry_count": 2,
        "variable_names": ["XAGENT_LLM_BACKEND", "XAGENT_OPENAI_API_KEY"],
        "env_groups": [["XAGENT_LLM_BACKEND", "LLM_BACKEND"], ["XAGENT_OPENAI_API_KEY", "OPENAI_API_KEY"]],
        "errors": [],
    }


def _owner_gate_checklist_summary() -> dict[str, object]:
    return {
        "status": "action_required",
        "gate_count": 1,
        "complete_count": 0,
        "next_commands": ["python scripts\\rc_external_smoke.py --require-configured"],
        "errors": [],
    }


def _owner_gate_runner_receipt_summary() -> dict[str, object]:
    steps = _owner_gate_runner_steps()
    return {
        "status": "planned",
        "generated_at": "2026-06-05T10:01:00Z",
        "selected_gate": "all",
        "dry_run": True,
        "env_file": ".xagent_runtime/reports/rc-owner-env-template.env",
        "loaded_env_names": ["XAGENT_OLLAMA_MODEL"],
        "owner_gate_env_names": ["XAGENT_OLLAMA_MODEL"],
        "missing_env_groups": [["XAGENT_GITHUB_TOKEN", "GITHUB_TOKEN"]],
        "step_count": len(steps),
        "steps": steps,
        "next_commands": ["Inspect .xagent_runtime/reports/rc-owner-gate-runner.json."],
    }


def _owner_gate_next_actions() -> list[dict[str, object]]:
    return [
        {
            "name": "provider",
            "status": "action_required",
            "complete": False,
            "required_env_groups": [["XAGENT_LLM_BACKEND", "LLM_BACKEND"], ["XAGENT_OPENAI_API_KEY", "OPENAI_API_KEY"]],
            "configured_env": [],
            "missing": ["Set XAGENT_OPENAI_API_KEY or OPENAI_API_KEY."],
            "command": "python scripts\\rc_external_smoke.py --check provider --require-configured",
            "evidence": [".xagent_runtime/reports/rc-external-smoke.json"],
            "completion_criteria": ["Provider check status is passed by real external evidence."],
        }
    ]


def _receipt_checks() -> list[dict[str, object]]:
    return [
        {"name": "artifact_security_scan", "status": "passed"},
        {"name": "artifact_integrity_gate", "status": "passed"},
        {"name": "final_gate", "status": "passed"},
        {"name": "release_diff_review_gate", "status": "passed"},
        {"name": "deployment_docs_gate", "status": "passed"},
        {"name": "source_bundle", "status": "passed"},
        {"name": "staging_plan", "status": "passed"},
        {"name": "owner_gate_plan", "status": "passed"},
        {"name": "owner_gate_plan_consistency", "status": "passed"},
        {"name": "owner_gate_runner", "status": "passed"},
        {"name": "owner_handoff_gate", "status": "passed"},
        {"name": "owner_env_template", "status": "passed"},
        {"name": "owner_gate_checklist", "status": "passed"},
        {"name": "install_release_gate", "status": "passed"},
        {"name": "single_user_local_gate", "status": "passed"},
        {"name": "supply_chain_gate", "status": "passed"},
        {"name": "secrets_gate", "status": "passed"},
        {"name": "release_artifact_consistency", "status": "passed"},
    ]


def _approval_request(
    *,
    receipt_path: Path,
    release_bundle: Path,
    artifact_sha256: str,
    candidate_files: list[str],
    candidate_count: int,
) -> dict[str, object]:
    return {
        "approval_required_before_staging": True,
        "final_gate_status": "ready_with_owner_gates",
        "can_stage_candidate_files": True,
        "can_tag_rc_now": False,
        "full_parity_claimed": False,
        "artifact_path": str(release_bundle),
        "artifact_sha256": artifact_sha256,
        "artifact_file_count": candidate_count,
        "receipt_path": str(receipt_path),
        "sha256_sidecar": str(release_bundle) + ".sha256",
        "remaining_risks": [{"name": "provider", "status": "action_required", "missing": ["token"]}],
        "exact_staging_commands": [
            "git add -- " + " ".join(f'"{path}"' for path in candidate_files)
        ],
        "no_broad_staging_command": True,
    }


def _install_checks() -> list[dict[str, object]]:
    return [
        {"name": "windows_installer_dry_run", "status": "passed"},
        {"name": "posix_installer_dry_run", "status": "passed"},
        {"name": "doctor", "status": "passed"},
        {"name": "source_bundle_report", "status": "passed"},
        {"name": "artifact_integrity_report", "status": "passed"},
        {"name": "staging_plan_report", "status": "passed"},
        {"name": "release_artifact_consistency", "status": "passed"},
    ]


def _supply_checks() -> list[dict[str, object]]:
    return [
        {"name": "python_manifest", "status": "passed"},
        {"name": "python_lockfile", "status": "passed"},
        {"name": "frontend_lockfile", "status": "passed"},
        {"name": "npm_audit", "status": "passed"},
        {"name": "ci_dependency_contract", "status": "passed"},
        {"name": "release_dependency_evidence", "status": "passed"},
    ]


def _secrets_checks() -> list[dict[str, object]]:
    return [
        {"name": "required_fields", "status": "passed"},
        {"name": "secret_strength", "status": "passed"},
        {"name": "unique_generated_values", "status": "passed"},
        {"name": "release_audit_secret_scan", "status": "passed"},
        {"name": "artifact_secret_scan", "status": "passed"},
        {"name": "prohibited_secret_artifacts", "status": "passed"},
    ]


def _owner_gate_runner_steps() -> list[dict[str, object]]:
    return [
        {
            "name": "owner_gate:all",
            "status": "planned",
            "returncode": None,
            "command": [
                "python",
                "scripts/rc_external_smoke.py",
                "--provider",
                "ollama",
                "--github-execute-preflight",
                "--github-actions-preflight",
                "--require-configured",
            ],
        },
        {"name": "refresh:rc_owner_gate_plan", "status": "planned", "returncode": None, "command": ["python"]},
        {"name": "refresh:rc_owner_env_template", "status": "planned", "returncode": None, "command": ["python"]},
        {"name": "refresh:rc_owner_gate_checklist", "status": "planned", "returncode": None, "command": ["python"]},
        {"name": "refresh:rc_owner_handoff_gate", "status": "planned", "returncode": None, "command": ["python"]},
        {"name": "refresh:rc_final_gate", "status": "planned", "returncode": None, "command": ["python"]},
    ]


def _evidence_pack_checks() -> list[dict[str, object]]:
    return [
        {"name": "release_receipt", "status": "passed"},
        {"name": "required_files", "status": "passed"},
        {"name": "artifact_consistency", "status": "passed"},
        {"name": "owner_gate_runner_evidence", "status": "passed"},
        {"name": "evidence_pack_freshness", "status": "passed"},
        {"name": "evidence_secret_scan", "status": "passed"},
        {"name": "evidence_local_path_privacy_scan", "status": "passed"},
    ]


def _inputs(tmp_path: Path, *, external_checks: list[dict[str, object]] | None = None) -> dict[str, Path]:
    release_bundle = _write_bytes(tmp_path / "release" / "bundle.zip", b"x-agent source bundle\n")
    release_bundle_sha = hashlib.sha256(release_bundle.read_bytes()).hexdigest()
    release_bundle_size = release_bundle.stat().st_size
    evidence_zip = _write_bytes(tmp_path / "release" / "evidence.zip", b"x-agent evidence pack\n")
    evidence_zip_sha = hashlib.sha256(evidence_zip.read_bytes()).hexdigest()
    candidate_files = _candidate_files()
    candidate_count = len(candidate_files)
    return {
        "gap_matrix": _write_json(
            tmp_path / "reports" / "codex-hermes-gap-closure.json",
            {
                "generated_at": "2026-06-05T10:01:00Z",
                "summary": {
                    "overall_status": "passed",
                    "counts": {"passed": 9, "failed": 0},
                    "competitive_parity": {"full_parity_claimed": False},
                }
            },
        ),
        "release_audit": _write_json(
            tmp_path / "reports" / "rc-release-audit.json",
            {
                "status": "passed",
                "generated_at": "2026-06-05T10:01:00Z",
                "candidate_count": candidate_count,
                "manifest_count": candidate_count,
                "missing_from_manifest": [],
                "manifest_extra": [],
                "secret_findings": [],
                "excluded_reference_findings": [],
            },
        ),
        "runtime_smoke": _write_json(
            tmp_path / "smoke" / "rc-runtime-smoke.json",
            {
                "status": "passed",
                "generated_at": "2026-06-05T10:01:00Z",
                "backend_base_url": "http://127.0.0.1:8765",
            },
        ),
        "external_smoke": _write_json(
            tmp_path / "reports" / "rc-external-smoke.json",
            {
                "status": "passed",
                "generated_at": "2026-06-05T10:01:00Z",
                "require_configured": False,
                "checks": external_checks
                if external_checks is not None
                else [
                    {
                        "name": "provider",
                        "status": "skipped",
                        "missing": ["Set XAGENT_LLM_BACKEND to openai, deepseek, anthropic, or ollama."],
                    }
                ],
            },
        ),
        "ci_contract": _write_json(
            tmp_path / "reports" / "rc-ci-contract.json",
            {
                "status": "passed",
                "generated_at": "2026-06-05T10:01:00Z",
                "workflow_path": ".github/workflows/commercial-rc.yml",
                "requirements_checked": 10,
                "forbidden_patterns_checked": 3,
                "findings": [],
            },
        ),
        "refresh_release_chain": _write_json(
            tmp_path / "reports" / "rc-refresh-release-chain.json",
            {
                "status": "passed",
                "generated_at": "2026-06-05T10:01:00Z",
                "provider": "ollama",
                "owner_verified": True,
                "dry_run": False,
                "steps": [
                    {
                        "name": "external_smoke",
                        "status": "passed",
                        "command": [
                            "python",
                            "scripts/rc_external_smoke.py",
                            "--check",
                            "provider",
                            "--check",
                            "feishu_webhook_contract",
                            "--check",
                            "github_issue_to_pr_dry_run",
                            "--check",
                            "github_issue_to_pr_execute_preflight",
                            "--check",
                            "hosted_github_actions_run",
                            "--require-configured",
                            "--github-execute-preflight",
                            "--github-actions-preflight",
                        ],
                    },
                    {"name": "final_gate_final", "status": "passed"},
                ],
            },
        ),
        "release_diff_review_gate": _write_json(
            tmp_path / "reports" / "rc-release-diff-review-gate.json",
            {
                "status": "passed",
                "generated_at": "2026-06-05T10:01:00Z",
                "candidate_file_count": candidate_count,
                "checks": [{"name": "review_document", "status": "passed"}],
            },
        ),
        "deployment_docs_gate": _write_json(
            tmp_path / "reports" / "rc-deployment-docs-gate.json",
            {
                "status": "passed",
                "generated_at": "2026-06-05T10:01:00Z",
                "checks": [{"name": "runbook_document", "status": "passed"}],
            },
        ),
        "owner_gate_plan": _write_json(
            tmp_path / "reports" / "rc-owner-gate-plan.json",
            {
                "status": "action_required",
                "generated_at": "2026-06-05T10:01:00Z",
                "gates": [{"name": "provider", "status": "action_required", "missing": ["token"]}],
                "next_commands": ["python scripts\\rc_external_smoke.py --require-configured"],
            },
        ),
        "owner_gate_runner": _write_json(
            tmp_path / "reports" / "rc-owner-gate-runner.json",
            {
                "status": "planned",
                "generated_at": "2026-06-05T10:01:00Z",
                "selected_gate": "all",
                "dry_run": True,
                "env_file": ".xagent_runtime/reports/rc-owner-env-template.env",
                "loaded_env_names": ["XAGENT_OLLAMA_MODEL"],
                "owner_gate_env_names": ["XAGENT_OLLAMA_MODEL"],
                "missing_env_groups": [["XAGENT_GITHUB_TOKEN", "GITHUB_TOKEN"]],
                "steps": _owner_gate_runner_steps(),
                "next_commands": ["Inspect .xagent_runtime/reports/rc-owner-gate-runner.json."],
            },
        ),
        "owner_env_template": _write_json(
            tmp_path / "reports" / "rc-owner-env-template.json",
            {
                "status": "created",
                "generated_at": "2026-06-05T10:01:00Z",
                "entry_count": 2,
                "errors": [],
            },
        ),
        "owner_gate_checklist": _write_json(
            tmp_path / "reports" / "rc-owner-gate-checklist.json",
            {
                "status": "action_required",
                "generated_at": "2026-06-05T10:01:00Z",
                "gate_count": 1,
                "errors": [],
            },
        ),
        "owner_handoff_gate": _write_json(
            tmp_path / "reports" / "rc-owner-handoff-gate.json",
            _owner_handoff_report(),
        ),
        "install_release_gate": _write_json(
            tmp_path / "reports" / "rc-install-release-gate.json",
            {
                "status": "passed",
                "generated_at": "2026-06-05T10:01:00Z",
                "checks": _install_checks(),
            },
        ),
        "single_user_local_gate": _write_json(
            tmp_path / "reports" / "rc-single-user-local-gate.json",
            {
                "status": "passed",
                "generated_at": "2026-06-05T10:01:00Z",
                "scope": "single-machine single-user local validation",
                "mode": "mock provider; no external Feishu/GitHub mutations",
                "checks": [
                    {"name": "rc2_release_handoff_snapshot", "status": "skipped"},
                    {"name": "install_release_gate", "status": "passed"},
                    {"name": "frontend_production_build", "status": "passed"},
                    {"name": "runtime_smoke", "status": "passed"},
                    {"name": "targeted_single_user_tests", "status": "passed"},
                ],
            },
        ),
        "supply_chain_gate": _write_json(
            tmp_path / "reports" / "rc-supply-chain-gate.json",
            {
                "status": "passed",
                "generated_at": "2026-06-05T10:01:00Z",
                "checks": _supply_checks(),
            },
        ),
        "secrets_gate": _write_json(
            tmp_path / "reports" / "rc-secrets-gate.json",
            {
                "status": "passed",
                "generated_at": "2026-06-05T10:01:00Z",
                "checks": _secrets_checks(),
                "generated_value_count": 7,
                "unique_value_count": 7,
                "required_fields": [
                    "AUDIT_HMAC_SECRET",
                    "BOOTSTRAP_API_KEY",
                    "ENCRYPTION_KEY",
                    "JWT_SECRET",
                    "NEO4J_PASSWORD",
                    "S3_ACCESS_KEY",
                    "S3_SECRET_KEY",
                ],
                "non_leakage_note": "Generated secret values are validated in memory and are not included in this report.",
            },
        ),
        "source_bundle": _write_json(
            tmp_path / "reports" / "rc-source-bundle.json",
            {
                "status": "created",
                "generated_at": "2026-06-05T10:00:00Z",
                "file_count": candidate_count,
                "dry_run": False,
                "output_path": str(release_bundle),
                "files": _source_bundle_files(candidate_files),
                "clean_tracked_files": [],
                "errors": [],
            },
        ),
        "artifact_integrity_gate": _write_json(
            tmp_path / "reports" / "rc-artifact-integrity-gate.json",
            {
                "status": "passed",
                "generated_at": "2026-06-05T10:01:00Z",
                "artifact_path": str(release_bundle),
                "artifact_sha256": release_bundle_sha,
                "artifact_size_bytes": release_bundle_size,
                "file_count": candidate_count,
                "checks": [
                    {"name": "source_bundle_report", "status": "passed"},
                    {"name": "artifact_file", "status": "passed"},
                    {"name": "zip_contents", "status": "passed"},
                    {"name": "workspace_contents", "status": "passed"},
                    {"name": "zip_security_scan", "status": "passed"},
                ],
            },
        ),
        "release_receipt": _write_json(
            tmp_path / "release" / "x-agent-commercial-rc-receipt.json",
            {
                "status": "created",
                "generated_at": "2026-06-05T10:02:00Z",
                "artifact": {
                    "path": str(release_bundle),
                    "sha256": release_bundle_sha,
                    "size_bytes": release_bundle_size,
                    "file_count": candidate_count,
                    "security_scan": {
                        "zip_security_scan_status": "passed",
                        "scanned_text_files": 3,
                        "secret_finding_count": 0,
                        "excluded_reference_finding_count": 0,
                        "local_path_finding_count": 0,
                    },
                },
                "final_gate": {"status": "ready_with_owner_gates"},
                "source_bundle": {"status": "created", "output_path": str(release_bundle), "file_count": candidate_count},
                "owner_gate_next_actions": _owner_gate_next_actions(),
                "owner_env_template": _owner_env_template_summary(),
                "owner_gate_runner": _owner_gate_runner_receipt_summary(),
                "owner_handoff_gate": _owner_handoff_receipt_summary(),
                "owner_gate_checklist": _owner_gate_checklist_summary(),
                "release_diff_review_gate": _gate_summary([{"name": "review_document", "status": "passed"}]),
                "deployment_docs_gate": _gate_summary([{"name": "runbook_document", "status": "passed"}]),
                "install_release_gate": _gate_summary(_install_checks()),
                "single_user_local_gate": _gate_summary(
                    [
                        {"name": "rc2_release_handoff_snapshot", "status": "passed"},
                        {"name": "install_release_gate", "status": "passed"},
                        {"name": "frontend_production_build", "status": "passed"},
                        {"name": "runtime_smoke", "status": "passed"},
                        {"name": "targeted_single_user_tests", "status": "passed"},
                    ]
                ),
                "supply_chain_gate": _gate_summary(_supply_checks()),
                "secrets_gate": _gate_summary(_secrets_checks()),
                "checks": _receipt_checks(),
                "sidecars": {"sha256": str(release_bundle) + ".sha256"},
                "approval_request": _approval_request(
                    receipt_path=tmp_path / "release" / "x-agent-commercial-rc-receipt.json",
                    release_bundle=release_bundle,
                    artifact_sha256=release_bundle_sha,
                    candidate_files=candidate_files,
                    candidate_count=candidate_count,
                ),
            },
        ),
        "evidence_pack": _write_json(
            tmp_path / "reports" / "rc-evidence-pack.json",
            {
                "status": "created",
                "generated_at": "2026-06-05T10:03:00Z",
                "receipt_path": str(tmp_path / "release" / "x-agent-commercial-rc-receipt.json"),
                "output_path": str(evidence_zip),
                "pack_sha256": evidence_zip_sha,
                "file_count": 24,
                "files": [],
                "checks": _evidence_pack_checks(),
            },
        ),
        "staging_plan": _write_json(
            tmp_path / "reports" / "rc-staging-plan.json",
            _staging_plan_payload(candidate_files),
        ),
    }


def test_final_gate_reports_owner_gates_without_failing_local_candidate(tmp_path: Path) -> None:
    report = run_final_gate(_inputs(tmp_path))

    assert report.status == "ready_with_owner_gates"
    assert report.rc_candidate is True
    assert report.release_decision["can_stage_candidate_files"] is True
    assert report.release_decision["can_tag_rc_now"] is False
    assert report.owner_gates[0].name == "provider"


def test_final_gate_still_blocks_when_external_smoke_passes_but_owner_plan_has_action_required(tmp_path: Path) -> None:
    report = run_final_gate(
        _inputs(
            tmp_path,
            external_checks=[
                {"name": "provider", "status": "passed", "missing": []},
                {"name": "feishu_webhook_contract", "status": "passed", "missing": []},
            ],
        )
    )

    assert report.status == "ready_with_owner_gates"
    assert report.release_decision["can_tag_rc_now"] is False
    assert any(gate.name == "provider" and gate.status == "action_required" for gate in report.owner_gates)


def test_final_gate_reports_feishu_external_owner_gate(tmp_path: Path) -> None:
    report = run_final_gate(
        _inputs(
            tmp_path,
            external_checks=[
                {"name": "feishu_webhook_contract", "status": "skipped", "missing": ["feishu app"]},
            ],
        )
    )

    feishu_gates = [gate for gate in report.owner_gates if gate.name == "feishu_webhook_contract"]
    assert len(feishu_gates) == 1
    assert feishu_gates[0].missing == ["feishu app"]


def test_final_gate_merges_hosted_actions_run_owner_gate(tmp_path: Path) -> None:
    report = run_final_gate(
        _inputs(
            tmp_path,
            external_checks=[
                {"name": "hosted_github_actions_run", "status": "skipped", "missing": ["run probe"]},
            ],
        )
    )

    hosted_gates = [gate for gate in report.owner_gates if gate.name == "hosted_github_actions_commercial_rc"]
    assert len(hosted_gates) == 1
    assert "run probe" in hosted_gates[0].missing


def test_final_gate_ready_to_tag_when_external_and_owner_plan_gates_are_verified(tmp_path: Path) -> None:
    inputs = _inputs(
        tmp_path,
        external_checks=_verified_external_checks(),
    )
    _write_json(
        inputs["owner_gate_plan"],
        {
            "status": "verified",
            "generated_at": "2026-06-05T10:01:00Z",
            "gates": [
                {"name": "provider", "status": "verified", "missing": []},
                {"name": "feishu_webhook_contract", "status": "verified", "missing": []},
                {"name": "github_issue_to_pr_dry_run", "status": "verified", "missing": []},
                {"name": "github_issue_to_pr_execute_preflight", "status": "verified", "missing": []},
                {"name": "hosted_github_actions_commercial_rc", "status": "verified", "missing": []},
            ],
            "evidence_freshness": {"required": True, "fresh": True},
            "next_commands": [],
        },
    )
    receipt = json.loads(inputs["release_receipt"].read_text(encoding="utf-8"))
    receipt["final_gate"] = {"status": "ready_for_rc_tag"}
    receipt["approval_request"]["final_gate_status"] = "ready_for_rc_tag"
    receipt["approval_request"]["can_tag_rc_now"] = True
    receipt["approval_request"]["remaining_risks"] = []
    _write_json(inputs["release_receipt"], receipt)

    report = run_final_gate(inputs)

    assert report.status == "ready_for_rc_tag"
    assert report.release_decision["can_tag_rc_now"] is True
    assert report.owner_gates == []


def test_final_gate_rejects_future_dated_external_smoke_even_when_owner_gates_verified(tmp_path: Path) -> None:
    inputs = _inputs(
        tmp_path,
        external_checks=_verified_external_checks(),
    )
    external_smoke = json.loads(inputs["external_smoke"].read_text(encoding="utf-8"))
    external_smoke["generated_at"] = "2999-01-01T00:00:00Z"
    _write_json(inputs["external_smoke"], external_smoke)
    _write_json(
        inputs["owner_gate_plan"],
        {
            "status": "verified",
            "generated_at": "2026-06-05T10:01:00Z",
            "gates": [
                {"name": "provider", "status": "verified", "missing": []},
                {"name": "feishu_webhook_contract", "status": "verified", "missing": []},
                {"name": "github_issue_to_pr_dry_run", "status": "verified", "missing": []},
                {"name": "github_issue_to_pr_execute_preflight", "status": "verified", "missing": []},
                {"name": "hosted_github_actions_commercial_rc", "status": "verified", "missing": []},
            ],
            "evidence_freshness": {"required": True, "fresh": True},
            "next_commands": [],
        },
    )
    receipt = json.loads(inputs["release_receipt"].read_text(encoding="utf-8"))
    receipt["final_gate"] = {"status": "ready_for_rc_tag"}
    receipt["approval_request"]["final_gate_status"] = "ready_for_rc_tag"
    receipt["approval_request"]["can_tag_rc_now"] = True
    receipt["approval_request"]["remaining_risks"] = []
    _write_json(inputs["release_receipt"], receipt)

    report = run_final_gate(inputs)

    assert report.status == "failed"
    assert report.release_decision["can_tag_rc_now"] is False
    gate = next(item for item in report.local_gates if item.name == "external_smoke")
    assert gate.ok is False
    assert "external_smoke generated_at is in the future" in str(gate.error)


def test_final_gate_allows_receipt_only_refresh_cycle_when_owner_gates_verified(
    tmp_path: Path,
) -> None:
    inputs = _inputs(
        tmp_path,
        external_checks=_verified_external_checks(),
    )
    _write_json(
        inputs["owner_gate_plan"],
        {
            "status": "verified",
            "generated_at": "2026-06-05T10:01:00Z",
            "gates": [
                {"name": "provider", "status": "verified", "missing": []},
                {"name": "feishu_webhook_contract", "status": "verified", "missing": []},
                {"name": "github_issue_to_pr_dry_run", "status": "verified", "missing": []},
                {"name": "github_issue_to_pr_execute_preflight", "status": "verified", "missing": []},
                {"name": "hosted_github_actions_commercial_rc", "status": "verified", "missing": []},
            ],
            "evidence_freshness": {"required": True, "fresh": True},
            "next_commands": [],
        },
    )
    receipt = json.loads(inputs["release_receipt"].read_text(encoding="utf-8"))
    receipt["final_gate"] = {"status": "ready_with_receipt_refresh_required"}
    receipt["approval_request"]["final_gate_status"] = "ready_with_receipt_refresh_required"
    receipt["approval_request"]["can_tag_rc_now"] = False
    receipt["approval_request"]["remaining_risks"] = []
    _write_json(inputs["release_receipt"], receipt)

    report = run_final_gate(inputs)

    assert report.status == "ready_for_rc_tag"
    assert report.release_decision["can_tag_rc_now"] is True
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert gate.ok is True
    assert gate.status == "created"


def test_final_gate_fails_when_owner_gate_plan_verified_with_stale_evidence(tmp_path: Path) -> None:
    inputs = _inputs(
        tmp_path,
        external_checks=_verified_external_checks(),
    )
    _write_json(
        inputs["owner_gate_plan"],
        {
            "status": "verified",
            "generated_at": "2026-06-05T10:01:00Z",
            "gates": [
                {"name": "provider", "status": "verified", "missing": []},
                {"name": "feishu_webhook_contract", "status": "verified", "missing": []},
                {"name": "github_issue_to_pr_dry_run", "status": "verified", "missing": []},
                {"name": "github_issue_to_pr_execute_preflight", "status": "verified", "missing": []},
                {"name": "hosted_github_actions_commercial_rc", "status": "verified", "missing": []},
            ],
            "evidence_freshness": {
                "required": True,
                "fresh": False,
                "problems": ["external smoke evidence is older than the current source bundle"],
            },
            "next_commands": [],
        },
    )
    receipt = json.loads(inputs["release_receipt"].read_text(encoding="utf-8"))
    receipt["final_gate"] = {"status": "ready_for_rc_tag"}
    receipt["approval_request"]["final_gate_status"] = "ready_for_rc_tag"
    receipt["approval_request"]["can_tag_rc_now"] = True
    receipt["approval_request"]["remaining_risks"] = []
    _write_json(inputs["release_receipt"], receipt)

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "owner_gate_plan_freshness")
    assert gate.ok is False
    assert "evidence is not fresh" in str(gate.error)


def test_final_gate_fails_when_owner_gate_plan_verified_without_freshness_summary(tmp_path: Path) -> None:
    inputs = _inputs(
        tmp_path,
        external_checks=_verified_external_checks(),
    )
    _write_json(
        inputs["owner_gate_plan"],
        {
            "status": "verified",
            "generated_at": "2026-06-05T10:01:00Z",
            "gates": [{"name": "provider", "status": "verified", "missing": []}],
            "next_commands": [],
        },
    )
    receipt = json.loads(inputs["release_receipt"].read_text(encoding="utf-8"))
    receipt["final_gate"] = {"status": "ready_for_rc_tag"}
    receipt["approval_request"]["final_gate_status"] = "ready_for_rc_tag"
    receipt["approval_request"]["can_tag_rc_now"] = True
    receipt["approval_request"]["remaining_risks"] = []
    _write_json(inputs["release_receipt"], receipt)

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "owner_gate_plan_freshness")
    assert gate.ok is False
    assert "evidence_freshness is missing" in str(gate.error)


def test_final_gate_fails_when_owner_gate_runner_report_missing(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    inputs["owner_gate_runner"].unlink()

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "owner_gate_runner")
    assert gate.ok is False
    assert "report missing" in str(gate.error)


def test_final_gate_fails_when_owner_gate_runner_all_command_missing_execute_preflight(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    steps = _owner_gate_runner_steps()
    command = list(steps[0]["command"])
    command.remove("--github-execute-preflight")
    steps[0]["command"] = command
    _write_json(
        inputs["owner_gate_runner"],
        {
            "status": "planned",
            "generated_at": "2026-06-05T10:01:00Z",
            "selected_gate": "all",
            "dry_run": True,
            "steps": steps,
            "next_commands": [],
        },
    )

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "owner_gate_runner")
    assert gate.ok is False
    assert "owner gate runner all-gate command missing token: --github-execute-preflight" in str(gate.error)


def test_final_gate_fails_when_owner_gate_runner_env_file_evidence_missing(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    owner_runner = json.loads(inputs["owner_gate_runner"].read_text(encoding="utf-8"))
    owner_runner.pop("env_file")
    _write_json(inputs["owner_gate_runner"], owner_runner)

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "owner_gate_runner")
    assert gate.ok is False
    assert "owner gate runner env_file must be .xagent_runtime/reports/rc-owner-env-template.env" in str(gate.error)


def test_final_gate_fails_when_owner_gate_runner_missing_env_groups_invalid(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    owner_runner = json.loads(inputs["owner_gate_runner"].read_text(encoding="utf-8"))
    owner_runner["missing_env_groups"] = ["XAGENT_GITHUB_TOKEN"]
    _write_json(inputs["owner_gate_runner"], owner_runner)

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "owner_gate_runner")
    assert gate.ok is False
    assert "owner gate runner missing_env_groups must be a list of env variable name groups" in str(gate.error)


def test_final_gate_fails_when_local_gate_fails(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(inputs["release_audit"], {"status": "failed", "missing_from_manifest": ["new.py"]})

    report = run_final_gate(inputs)

    assert report.status == "failed"
    assert report.rc_candidate is False
    assert any(gate.name == "release_audit" and not gate.ok for gate in report.local_gates)


def test_final_gate_fails_when_source_bundle_failed(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(inputs["source_bundle"], {"status": "failed", "errors": ["manifest includes excluded paths"]})

    report = run_final_gate(inputs)

    assert report.status == "failed"
    assert any(gate.name == "source_bundle" and not gate.ok for gate in report.local_gates)


def test_final_gate_fails_when_source_bundle_is_only_planned(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(inputs["source_bundle"], {"status": "planned", "dry_run": True, "file_count": 81, "errors": []})

    report = run_final_gate(inputs)

    assert report.status == "failed"
    assert any(gate.name == "source_bundle" and not gate.ok for gate in report.local_gates)


def test_final_gate_fails_when_artifact_integrity_gate_fails(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(
        inputs["artifact_integrity_gate"],
        {"status": "failed", "checks": [{"name": "zip_contents", "status": "failed"}]},
    )

    report = run_final_gate(inputs)

    assert report.status == "failed"
    assert any(gate.name == "artifact_integrity_gate" and not gate.ok for gate in report.local_gates)


def test_final_gate_fails_when_artifact_integrity_required_check_missing(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(
        inputs["artifact_integrity_gate"],
        {
            "status": "passed",
            "artifact_path": str(tmp_path / "release" / "bundle.zip"),
            "artifact_sha256": "a" * 64,
            "artifact_size_bytes": 1234,
            "file_count": len(_candidate_files()),
            "checks": [
                {"name": "source_bundle_report", "status": "passed"},
                {"name": "artifact_file", "status": "passed"},
                {"name": "zip_contents", "status": "passed"},
                {"name": "workspace_contents", "status": "passed"},
            ],
        },
    )

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "artifact_integrity_gate")
    assert gate.ok is False
    assert "missing required artifact_integrity_gate checks: zip_security_scan" in str(gate.error)


def test_final_gate_fails_when_source_artifact_zip_sha_mismatches(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    (tmp_path / "release" / "bundle.zip").write_bytes(b"tampered source bundle\n")

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "artifact_integrity_gate")
    assert gate.ok is False
    assert "artifact integrity SHA-256 does not match current file" in str(gate.error)


def test_final_gate_fails_when_release_receipt_missing(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    inputs["release_receipt"].unlink()

    report = run_final_gate(inputs)

    assert report.status == "ready_with_receipt_refresh_required"
    assert report.rc_candidate is False
    assert report.release_decision["can_stage_candidate_files"] is False
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert gate.ok is True
    assert gate.status == "refresh_required"
    assert "report missing" in str(gate.error)


def test_final_gate_fails_when_evidence_pack_missing(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    inputs["evidence_pack"].unlink()

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "evidence_pack")
    assert gate.status == "failed"
    assert "report missing" in str(gate.error)


def test_final_gate_allows_missing_evidence_pack_only_for_bootstrap(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    inputs["evidence_pack"].unlink()

    report = run_final_gate(inputs, allow_missing_evidence_pack=True)

    assert report.status == "ready_with_owner_gates"
    assert report.rc_candidate is True
    assert report.release_decision["bootstrap_allowed"] is True
    gate = next(item for item in report.local_gates if item.name == "evidence_pack")
    assert gate.ok is True
    assert gate.status == "bootstrap_allowed"
    assert gate.details["bootstrap_allowed"] is True


def test_final_gate_allows_running_refresh_chain_only_for_bootstrap(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    refresh_payload = json.loads(inputs["refresh_release_chain"].read_text(encoding="utf-8"))
    refresh_payload["status"] = "running"
    _write_json(inputs["refresh_release_chain"], refresh_payload)

    bootstrap_report = run_final_gate(inputs, allow_missing_evidence_pack=True)
    strict_report = run_final_gate(inputs)

    assert bootstrap_report.status == "ready_with_owner_gates"
    bootstrap_gate = next(item for item in bootstrap_report.local_gates if item.name == "refresh_release_chain")
    assert bootstrap_gate.ok is True
    assert bootstrap_gate.status == "running"

    assert strict_report.status == "failed"
    strict_gate = next(item for item in strict_report.local_gates if item.name == "refresh_release_chain")
    assert strict_gate.ok is False
    assert strict_gate.status == "running"


def test_final_gate_rejects_planned_refresh_chain_in_strict_mode(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    refresh_payload = json.loads(inputs["refresh_release_chain"].read_text(encoding="utf-8"))
    refresh_payload["status"] = "planned"
    refresh_payload["dry_run"] = True
    _write_json(inputs["refresh_release_chain"], refresh_payload)

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "refresh_release_chain")
    assert gate.ok is False
    assert gate.status == "planned"
    assert "dry_run must be false" in str(gate.error)


def test_final_gate_requires_owner_verified_refresh_chain_for_tag_ready(tmp_path: Path) -> None:
    inputs = _inputs(
        tmp_path,
        external_checks=_verified_external_checks(),
    )
    refresh_payload = json.loads(inputs["refresh_release_chain"].read_text(encoding="utf-8"))
    refresh_payload["owner_verified"] = False
    _write_json(inputs["refresh_release_chain"], refresh_payload)
    _write_json(
        inputs["owner_gate_plan"],
        {
            "status": "verified",
            "generated_at": "2026-06-05T10:01:00Z",
            "gates": [
                {"name": "provider", "status": "verified", "missing": []},
                {"name": "feishu_webhook_contract", "status": "verified", "missing": []},
                {"name": "github_issue_to_pr_dry_run", "status": "verified", "missing": []},
                {"name": "github_issue_to_pr_execute_preflight", "status": "verified", "missing": []},
                {"name": "hosted_github_actions_commercial_rc", "status": "verified", "missing": []},
            ],
            "evidence_freshness": {"required": True, "fresh": True},
            "next_commands": [],
        },
    )
    receipt = json.loads(inputs["release_receipt"].read_text(encoding="utf-8"))
    receipt["final_gate"] = {"status": "ready_for_rc_tag"}
    receipt["approval_request"]["final_gate_status"] = "ready_for_rc_tag"
    receipt["approval_request"]["can_tag_rc_now"] = True
    receipt["approval_request"]["remaining_risks"] = []
    _write_json(inputs["release_receipt"], receipt)

    report = run_final_gate(inputs)

    assert report.status == "ready_with_owner_gates"
    assert report.release_decision["can_tag_rc_now"] is False
    gate = next(item for item in report.owner_gates if item.name == "refresh_release_chain_owner_verified")
    assert gate.status == "action_required"
    assert "--owner-verified" in gate.missing[0]


def test_final_gate_fails_when_evidence_pack_required_check_failed(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    checks = _evidence_pack_checks()
    for check in checks:
        if check["name"] == "evidence_pack_freshness":
            check["status"] = "failed"
            break
    _write_json(
        inputs["evidence_pack"],
        {
            "status": "created",
            "generated_at": "2026-06-05T10:03:00Z",
            "receipt_path": str(inputs["release_receipt"]),
            "output_path": str(tmp_path / "release" / "evidence.zip"),
            "pack_sha256": "b" * 64,
            "file_count": 24,
            "files": [],
            "checks": checks,
        },
    )

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "evidence_pack")
    assert gate.status == "failed"
    assert "required evidence_pack checks failed: evidence_pack_freshness" in str(gate.error)


def test_final_gate_fails_when_evidence_pack_zip_sha_mismatches(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    pack = json.loads(inputs["evidence_pack"].read_text(encoding="utf-8"))
    pack["pack_sha256"] = "c" * 64
    _write_json(inputs["evidence_pack"], pack)

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "evidence_pack")
    assert gate.status == "failed"
    assert "evidence pack SHA-256 does not match current file" in str(gate.error)


def test_final_gate_fails_when_evidence_pack_timestamp_is_in_future(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    pack = json.loads(inputs["evidence_pack"].read_text(encoding="utf-8"))
    pack["generated_at"] = "2999-01-01T00:00:00Z"
    _write_json(inputs["evidence_pack"], pack)

    report = run_final_gate(inputs)

    gate = next(item for item in report.local_gates if item.name == "evidence_pack")
    assert gate.status == "failed"
    assert "evidence pack generated_at is in the future" in str(gate.error)


def test_final_gate_fails_when_evidence_pack_is_older_than_receipt(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    pack = json.loads(inputs["evidence_pack"].read_text(encoding="utf-8"))
    pack["generated_at"] = "2026-06-05T10:01:59Z"
    _write_json(inputs["evidence_pack"], pack)

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "evidence_pack")
    assert gate.status == "failed"
    assert "evidence pack is older than required release reports" in str(gate.error)
    assert any(item["name"] == "release_receipt" for item in gate.details["stale_reports"])


def test_final_gate_allows_stale_evidence_pack_only_for_bootstrap(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    pack = json.loads(inputs["evidence_pack"].read_text(encoding="utf-8"))
    pack["generated_at"] = "2026-06-05T10:01:59Z"
    _write_json(inputs["evidence_pack"], pack)

    report = run_final_gate(inputs, allow_missing_evidence_pack=True)

    assert report.status == "ready_with_owner_gates"
    gate = next(item for item in report.local_gates if item.name == "evidence_pack")
    assert gate.ok is True
    assert gate.status == "bootstrap_allowed"
    assert gate.details["bootstrap_allowed"] is True
    assert any(item["name"] == "release_receipt" for item in gate.details["stale_reports"])


def test_final_gate_allows_previous_failed_evidence_pack_freshness_only_for_bootstrap(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    checks = _evidence_pack_checks()
    for check in checks:
        if check["name"] == "evidence_pack_freshness":
            check["status"] = "failed"
            break
    _write_json(
        inputs["evidence_pack"],
        {
            "status": "failed",
            "generated_at": "2026-06-05T10:03:00Z",
            "receipt_path": str(inputs["release_receipt"]),
            "output_path": str(tmp_path / "release" / "evidence.zip"),
            "pack_sha256": "b" * 64,
            "file_count": 24,
            "files": [],
            "checks": checks,
        },
    )

    report = run_final_gate(inputs, allow_missing_evidence_pack=True)

    assert report.status == "ready_with_owner_gates"
    gate = next(item for item in report.local_gates if item.name == "evidence_pack")
    assert gate.status == "bootstrap_allowed"
    assert gate.details["bootstrap_allowed"] is True


def test_final_gate_allows_previous_failed_evidence_pack_receipt_only_for_bootstrap(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    checks = _evidence_pack_checks()
    for check in checks:
        if check["name"] == "release_receipt":
            check["status"] = "failed"
            break
    _write_json(
        inputs["evidence_pack"],
        {
            "status": "failed",
            "generated_at": "2026-06-05T10:03:00Z",
            "receipt_path": str(inputs["release_receipt"]),
            "output_path": str(tmp_path / "release" / "evidence.zip"),
            "pack_sha256": "b" * 64,
            "file_count": 24,
            "files": [],
            "checks": checks,
        },
    )

    bootstrap_report = run_final_gate(inputs, allow_missing_evidence_pack=True)
    strict_report = run_final_gate(inputs)

    assert bootstrap_report.status == "ready_with_owner_gates"
    bootstrap_gate = next(item for item in bootstrap_report.local_gates if item.name == "evidence_pack")
    assert bootstrap_gate.status == "bootstrap_allowed"
    assert bootstrap_gate.details["bootstrap_allowed"] is True

    assert strict_report.status == "failed"
    strict_gate = next(item for item in strict_report.local_gates if item.name == "evidence_pack")
    assert strict_gate.status == "failed"


def test_final_gate_fails_when_release_receipt_artifact_mismatches(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(
        inputs["release_receipt"],
        {
            "status": "created",
            "generated_at": "2026-06-05T10:02:00Z",
            "artifact": {
                "path": str(tmp_path / "release" / "old-bundle.zip"),
                "sha256": "b" * 64,
            },
            "checks": [{"name": "release_artifact_consistency", "status": "passed"}],
        },
    )

    report = run_final_gate(inputs)

    assert report.status == "ready_with_receipt_refresh_required"
    assert report.rc_candidate is False
    assert report.release_decision["can_stage_candidate_files"] is False
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert gate.ok is True
    assert gate.status == "refresh_required"
    assert "does not match artifact integrity" in str(gate.error)


def test_final_gate_accepts_refreshed_receipt_from_refresh_required_state(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    release_bundle = tmp_path / "release" / "bundle.zip"
    release_bundle_sha = hashlib.sha256(release_bundle.read_bytes()).hexdigest()
    release_bundle_size = release_bundle.stat().st_size
    candidate_files = _candidate_files()
    _write_json(
        inputs["release_receipt"],
        {
            "status": "created",
            "generated_at": "2026-06-05T10:02:00Z",
            "artifact": {
                "path": str(release_bundle),
                "sha256": release_bundle_sha,
                "size_bytes": release_bundle_size,
                "file_count": len(candidate_files),
                "security_scan": {
                    "zip_security_scan_status": "passed",
                    "scanned_text_files": 3,
                    "secret_finding_count": 0,
                    "excluded_reference_finding_count": 0,
                    "local_path_finding_count": 0,
                },
            },
            "final_gate": {
                "status": "ready_with_receipt_refresh_required",
                "bootstrap_allowed": False,
            },
            "owner_gate_next_actions": _owner_gate_next_actions(),
            "owner_env_template": _owner_env_template_summary(),
            "owner_gate_runner": _owner_gate_runner_receipt_summary(),
            "owner_handoff_gate": _owner_handoff_receipt_summary(),
            "owner_gate_checklist": _owner_gate_checklist_summary(),
            "release_diff_review_gate": _gate_summary([{"name": "review_document", "status": "passed"}]),
            "deployment_docs_gate": _gate_summary([{"name": "runbook_document", "status": "passed"}]),
            "install_release_gate": _gate_summary(_install_checks()),
            "single_user_local_gate": _gate_summary(
                [
                    {"name": "rc2_release_handoff_snapshot", "status": "passed"},
                    {"name": "install_release_gate", "status": "passed"},
                    {"name": "frontend_production_build", "status": "passed"},
                    {"name": "runtime_smoke", "status": "passed"},
                    {"name": "targeted_single_user_tests", "status": "passed"},
                ]
            ),
            "supply_chain_gate": _gate_summary(_supply_checks()),
            "secrets_gate": _gate_summary(_secrets_checks()),
            "checks": _receipt_checks(),
            "approval_request": _approval_request(
                receipt_path=inputs["release_receipt"],
                release_bundle=release_bundle,
                artifact_sha256=release_bundle_sha,
                candidate_files=candidate_files,
                candidate_count=len(candidate_files),
            ),
        },
    )
    receipt = json.loads(inputs["release_receipt"].read_text(encoding="utf-8"))
    receipt["approval_request"]["final_gate_status"] = "ready_with_receipt_refresh_required"
    _write_json(inputs["release_receipt"], receipt)

    report = run_final_gate(inputs)

    assert report.status == "ready_with_owner_gates"
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert gate.ok is True
    assert gate.status == "created"


def test_final_gate_requires_receipt_refresh_when_receipt_missing_local_gate_sections(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(
        inputs["release_receipt"],
        {
            "status": "created",
            "generated_at": "2026-06-05T10:02:00Z",
            "artifact": {
                "path": str(tmp_path / "release" / "bundle.zip"),
                "sha256": "a" * 64,
                "file_count": len(_candidate_files()),
            },
            "final_gate": {"status": "ready_with_owner_gates"},
            "checks": [
                {"name": "artifact_integrity_gate", "status": "passed"},
                {"name": "final_gate", "status": "passed"},
                {"name": "source_bundle", "status": "passed"},
                {"name": "staging_plan", "status": "passed"},
                {"name": "owner_gate_plan", "status": "passed"},
                {"name": "owner_gate_plan_consistency", "status": "passed"},
                {"name": "release_artifact_consistency", "status": "passed"},
            ],
        },
    )

    report = run_final_gate(inputs)

    assert report.status == "ready_with_receipt_refresh_required"
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert gate.ok is True
    assert gate.status == "refresh_required"
    assert "receipt missing install_release_gate summary" in str(gate.error)
    assert "receipt missing required checks" in str(gate.error)


def test_final_gate_requires_receipt_refresh_when_owner_handoff_sections_missing(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    receipt = json.loads(inputs["release_receipt"].read_text(encoding="utf-8"))
    receipt.pop("owner_env_template")
    receipt.pop("owner_gate_checklist")
    receipt["checks"] = [
        check
        for check in receipt["checks"]
        if check["name"] not in {"owner_env_template", "owner_gate_checklist"}
    ]
    _write_json(inputs["release_receipt"], receipt)

    report = run_final_gate(inputs)

    assert report.status == "ready_with_receipt_refresh_required"
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert gate.status == "refresh_required"
    assert "receipt missing owner_env_template summary" in str(gate.error)
    assert "receipt missing owner_gate_checklist summary" in str(gate.error)
    assert "receipt missing required checks" in str(gate.error)


def test_final_gate_requires_receipt_refresh_when_owner_gate_runner_summary_missing(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    receipt = json.loads(inputs["release_receipt"].read_text(encoding="utf-8"))
    receipt.pop("owner_gate_runner")
    receipt["checks"] = [
        check
        for check in receipt["checks"]
        if check["name"] != "owner_gate_runner"
    ]
    _write_json(inputs["release_receipt"], receipt)

    report = run_final_gate(inputs)

    assert report.status == "ready_with_receipt_refresh_required"
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert gate.status == "refresh_required"
    assert "receipt missing owner_gate_runner summary" in str(gate.error)
    assert "receipt missing required checks" in str(gate.error)


def test_final_gate_requires_receipt_refresh_when_approval_request_missing(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    receipt = json.loads(inputs["release_receipt"].read_text(encoding="utf-8"))
    receipt.pop("approval_request")
    _write_json(inputs["release_receipt"], receipt)

    report = run_final_gate(inputs)

    assert report.status == "ready_with_receipt_refresh_required"
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert "receipt missing approval_request summary" in str(gate.error)


def test_final_gate_requires_receipt_refresh_when_owner_gate_runner_summary_missing_execute_preflight(
    tmp_path: Path,
) -> None:
    inputs = _inputs(tmp_path)
    receipt = json.loads(inputs["release_receipt"].read_text(encoding="utf-8"))
    command = list(receipt["owner_gate_runner"]["steps"][0]["command"])
    command.remove("--github-execute-preflight")
    receipt["owner_gate_runner"]["steps"][0]["command"] = command
    _write_json(inputs["release_receipt"], receipt)

    report = run_final_gate(inputs)

    assert report.status == "ready_with_receipt_refresh_required"
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert gate.status == "refresh_required"
    assert "receipt owner_gate_runner all-gate command missing token: --github-execute-preflight" in str(gate.error)


def test_final_gate_requires_receipt_refresh_when_owner_gate_runner_summary_missing_env_file(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    receipt = json.loads(inputs["release_receipt"].read_text(encoding="utf-8"))
    receipt["owner_gate_runner"].pop("env_file")
    _write_json(inputs["release_receipt"], receipt)

    report = run_final_gate(inputs)

    assert report.status == "ready_with_receipt_refresh_required"
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert gate.status == "refresh_required"
    assert "receipt owner_gate_runner.env_file must be .xagent_runtime/reports/rc-owner-env-template.env" in str(gate.error)


def test_final_gate_requires_receipt_refresh_when_owner_gate_runner_summary_invalid_missing_env_groups(
    tmp_path: Path,
) -> None:
    inputs = _inputs(tmp_path)
    receipt = json.loads(inputs["release_receipt"].read_text(encoding="utf-8"))
    receipt["owner_gate_runner"]["missing_env_groups"] = ["XAGENT_GITHUB_TOKEN"]
    _write_json(inputs["release_receipt"], receipt)

    report = run_final_gate(inputs)

    assert report.status == "ready_with_receipt_refresh_required"
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert gate.status == "refresh_required"
    assert "receipt owner_gate_runner.missing_env_groups must be a list of env variable name groups" in str(gate.error)


def test_final_gate_requires_receipt_refresh_when_owner_env_template_summary_invalid_env_groups(
    tmp_path: Path,
) -> None:
    inputs = _inputs(tmp_path)
    receipt = json.loads(inputs["release_receipt"].read_text(encoding="utf-8"))
    receipt["owner_env_template"]["env_groups"] = ["XAGENT_LLM_BACKEND"]
    _write_json(inputs["release_receipt"], receipt)

    report = run_final_gate(inputs)

    assert report.status == "ready_with_receipt_refresh_required"
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert gate.status == "refresh_required"
    assert "receipt owner_env_template.env_groups must be a list of env variable name groups" in str(gate.error)


def test_final_gate_requires_receipt_refresh_when_owner_handoff_summary_is_stale(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    receipt = json.loads(inputs["release_receipt"].read_text(encoding="utf-8"))
    receipt["owner_handoff_gate"] = _gate_summary([{"name": "owner_gate_plan", "status": "passed"}])
    _write_json(inputs["release_receipt"], receipt)

    report = run_final_gate(inputs)

    assert report.status == "ready_with_receipt_refresh_required"
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert gate.status == "refresh_required"
    assert "receipt owner_handoff_gate missing required checks" in str(gate.error)


def test_final_gate_requires_receipt_refresh_when_owner_handoff_privacy_count_not_clean(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    receipt = json.loads(inputs["release_receipt"].read_text(encoding="utf-8"))
    for check in receipt["owner_handoff_gate"]["checks"]:
        if check["name"] == "owner_gate_checklist":
            check["local_path_finding_count"] = 1
    _write_json(inputs["release_receipt"], receipt)

    report = run_final_gate(inputs)

    assert report.status == "ready_with_receipt_refresh_required"
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert gate.status == "refresh_required"
    assert "receipt owner_handoff_gate.owner_gate_checklist.local_path_finding_count must be 0" in str(gate.error)


def test_final_gate_requires_receipt_refresh_when_owner_gate_next_actions_missing(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    receipt = json.loads(inputs["release_receipt"].read_text(encoding="utf-8"))
    receipt.pop("owner_gate_next_actions")
    _write_json(inputs["release_receipt"], receipt)

    report = run_final_gate(inputs)

    assert report.status == "ready_with_receipt_refresh_required"
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert gate.status == "refresh_required"
    assert "receipt owner_gate_next_actions is missing or empty" in str(gate.error)


def test_final_gate_requires_receipt_refresh_when_owner_gate_next_action_is_incomplete(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    receipt = json.loads(inputs["release_receipt"].read_text(encoding="utf-8"))
    receipt["owner_gate_next_actions"] = [
        {
            "name": "github_issue_to_pr_dry_run",
            "status": "action_required",
            "required_env_groups": [["XAGENT_GITHUB_TEST_ISSUE_URL"]],
            "missing": ["XAGENT_GITHUB_TEST_ISSUE_URL"],
            "command": "",
            "evidence": [],
            "completion_criteria": [],
        }
    ]
    _write_json(inputs["release_receipt"], receipt)

    report = run_final_gate(inputs)

    assert report.status == "ready_with_receipt_refresh_required"
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert gate.status == "refresh_required"
    assert "receipt owner_gate_next_actions.github_issue_to_pr_dry_run.command is missing" in str(gate.error)
    assert "receipt owner_gate_next_actions.github_issue_to_pr_dry_run.evidence is missing" in str(gate.error)
    assert "receipt owner_gate_next_actions.github_issue_to_pr_dry_run.completion_criteria is missing" in str(gate.error)


def test_final_gate_requires_receipt_refresh_when_receipt_local_gate_check_failed(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    receipt_checks = _receipt_checks()
    for check in receipt_checks:
        if check["name"] == "supply_chain_gate":
            check["status"] = "failed"
    _write_json(
        inputs["release_receipt"],
        {
            "status": "created",
            "generated_at": "2026-06-05T10:02:00Z",
            "artifact": {
                "path": str(tmp_path / "release" / "bundle.zip"),
                "sha256": "a" * 64,
                "file_count": len(_candidate_files()),
            },
            "final_gate": {"status": "ready_with_owner_gates"},
            "owner_gate_next_actions": _owner_gate_next_actions(),
            "owner_env_template": _owner_env_template_summary(),
            "owner_gate_runner": _owner_gate_runner_receipt_summary(),
            "owner_handoff_gate": _owner_handoff_receipt_summary(),
            "owner_gate_checklist": _owner_gate_checklist_summary(),
            "install_release_gate": _gate_summary(_install_checks()),
            "deployment_docs_gate": _gate_summary([{"name": "runbook_document", "status": "passed"}]),
            "supply_chain_gate": _gate_summary(_supply_checks()),
            "secrets_gate": _gate_summary(_secrets_checks()),
            "checks": receipt_checks,
        },
    )

    report = run_final_gate(inputs)

    assert report.status == "ready_with_receipt_refresh_required"
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert gate.status == "refresh_required"
    assert "receipt contains failed checks: supply_chain_gate" in str(gate.error)


def test_final_gate_requires_receipt_refresh_when_artifact_security_scan_not_clean(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    receipt = json.loads(inputs["release_receipt"].read_text(encoding="utf-8"))
    receipt["artifact"]["security_scan"]["local_path_finding_count"] = 1
    _write_json(inputs["release_receipt"], receipt)

    report = run_final_gate(inputs)

    assert report.status == "ready_with_receipt_refresh_required"
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert gate.status == "refresh_required"
    assert "receipt artifact.security_scan.local_path_finding_count must be 0" in str(gate.error)


def test_final_gate_requires_receipt_refresh_when_receipt_is_older_than_artifact_report(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(
        inputs["release_receipt"],
        {
            "status": "created",
            "generated_at": "2026-06-05T10:00:59Z",
            "artifact": {
                "path": str(tmp_path / "release" / "bundle.zip"),
                "sha256": "a" * 64,
                "file_count": len(_candidate_files()),
            },
            "final_gate": {"status": "ready_with_owner_gates"},
            "owner_gate_next_actions": _owner_gate_next_actions(),
            "owner_env_template": _owner_env_template_summary(),
            "owner_gate_runner": _owner_gate_runner_receipt_summary(),
            "owner_handoff_gate": _owner_handoff_receipt_summary(),
            "owner_gate_checklist": _owner_gate_checklist_summary(),
            "install_release_gate": _gate_summary(_install_checks()),
            "deployment_docs_gate": _gate_summary([{"name": "runbook_document", "status": "passed"}]),
            "supply_chain_gate": _gate_summary(_supply_checks()),
            "secrets_gate": _gate_summary(_secrets_checks()),
            "checks": _receipt_checks(),
        },
    )

    report = run_final_gate(inputs)

    assert report.status == "ready_with_receipt_refresh_required"
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert gate.status == "refresh_required"
    assert "older than artifact integrity report" in str(gate.error)


def test_final_gate_requires_receipt_refresh_when_receipt_is_older_than_owner_handoff(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    owner_handoff = json.loads(inputs["owner_handoff_gate"].read_text(encoding="utf-8"))
    owner_handoff["generated_at"] = "2026-06-05T10:03:00Z"
    _write_json(inputs["owner_handoff_gate"], owner_handoff)

    report = run_final_gate(inputs)

    assert report.status == "ready_with_receipt_refresh_required"
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert gate.status == "refresh_required"
    assert "older than owner handoff gate report" in str(gate.error)


def test_final_gate_requires_receipt_refresh_when_receipt_is_older_than_owner_gate_plan(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    owner_plan = json.loads(inputs["owner_gate_plan"].read_text(encoding="utf-8"))
    owner_plan["generated_at"] = "2026-06-05T10:03:00Z"
    _write_json(inputs["owner_gate_plan"], owner_plan)

    report = run_final_gate(inputs)

    assert report.status == "ready_with_receipt_refresh_required"
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert gate.status == "refresh_required"
    assert "older than owner gate plan report" in str(gate.error)


def test_final_gate_requires_receipt_refresh_when_receipt_is_older_than_owner_env_template(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    owner_env = json.loads(inputs["owner_env_template"].read_text(encoding="utf-8"))
    owner_env["generated_at"] = "2026-06-05T10:03:00Z"
    _write_json(inputs["owner_env_template"], owner_env)

    report = run_final_gate(inputs)

    assert report.status == "ready_with_receipt_refresh_required"
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert gate.status == "refresh_required"
    assert "older than owner env template report" in str(gate.error)


def test_final_gate_requires_receipt_refresh_when_receipt_is_older_than_owner_gate_checklist(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    owner_checklist = json.loads(inputs["owner_gate_checklist"].read_text(encoding="utf-8"))
    owner_checklist["generated_at"] = "2026-06-05T10:03:00Z"
    _write_json(inputs["owner_gate_checklist"], owner_checklist)

    report = run_final_gate(inputs)

    assert report.status == "ready_with_receipt_refresh_required"
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert gate.status == "refresh_required"
    assert "older than owner gate checklist report" in str(gate.error)


def test_final_gate_requires_receipt_refresh_when_receipt_is_older_than_owner_gate_runner(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    owner_runner = json.loads(inputs["owner_gate_runner"].read_text(encoding="utf-8"))
    owner_runner["generated_at"] = "2026-06-05T10:03:00Z"
    _write_json(inputs["owner_gate_runner"], owner_runner)

    report = run_final_gate(inputs)

    assert report.status == "ready_with_receipt_refresh_required"
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert gate.status == "refresh_required"
    assert "older than owner gate runner report" in str(gate.error)


def test_final_gate_requires_receipt_refresh_when_receipt_is_older_than_install_release_gate(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    install_gate = json.loads(inputs["install_release_gate"].read_text(encoding="utf-8"))
    install_gate["generated_at"] = "2026-06-05T10:03:00Z"
    _write_json(inputs["install_release_gate"], install_gate)

    report = run_final_gate(inputs)

    assert report.status == "ready_with_receipt_refresh_required"
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert gate.status == "refresh_required"
    assert "older than install release gate report" in str(gate.error)


def test_final_gate_requires_receipt_refresh_when_receipt_timestamp_invalid(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(
        inputs["release_receipt"],
        {
            "status": "created",
            "generated_at": "not-a-time",
            "artifact": {
                "path": str(tmp_path / "release" / "bundle.zip"),
                "sha256": "a" * 64,
                "file_count": len(_candidate_files()),
            },
            "final_gate": {"status": "ready_with_owner_gates"},
            "owner_gate_next_actions": _owner_gate_next_actions(),
            "owner_env_template": _owner_env_template_summary(),
            "owner_gate_runner": _owner_gate_runner_receipt_summary(),
            "owner_handoff_gate": _owner_handoff_receipt_summary(),
            "owner_gate_checklist": _owner_gate_checklist_summary(),
            "install_release_gate": _gate_summary(_install_checks()),
            "deployment_docs_gate": _gate_summary([{"name": "runbook_document", "status": "passed"}]),
            "supply_chain_gate": _gate_summary(_supply_checks()),
            "secrets_gate": _gate_summary(_secrets_checks()),
            "checks": _receipt_checks(),
        },
    )

    report = run_final_gate(inputs)

    assert report.status == "ready_with_receipt_refresh_required"
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert gate.status == "refresh_required"
    assert "generated_at is missing or invalid" in str(gate.error)


def test_final_gate_requires_receipt_refresh_when_receipt_timestamp_in_future(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    receipt = json.loads(inputs["release_receipt"].read_text(encoding="utf-8"))
    receipt["generated_at"] = "2999-01-01T00:00:00Z"
    _write_json(inputs["release_receipt"], receipt)

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "release_receipt")
    assert gate.status == "refresh_required"
    assert "receipt generated_at is in the future" in str(gate.error)
    evidence_gate = next(item for item in report.local_gates if item.name == "evidence_pack")
    assert evidence_gate.status == "failed"


def test_final_gate_passes_release_report_consistency_when_staging_and_bundle_match(tmp_path: Path) -> None:
    report = run_final_gate(_inputs(tmp_path))

    gate = next(item for item in report.local_gates if item.name == "release_report_consistency")
    assert gate.ok is True
    assert gate.status == "passed"
    assert gate.details["source_path_count"] == len(_candidate_files())
    assert gate.details["staging_path_count"] == len(_candidate_files())


def test_final_gate_fails_when_staging_file_count_mismatches_source_bundle(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    paths = _candidate_files()
    staging_payload = _staging_plan_payload(paths)
    staging_payload["file_count"] = len(paths) + 1
    _write_json(inputs["staging_plan"], staging_payload)

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "release_report_consistency")
    assert gate.ok is False
    assert "file_count mismatch" in str(gate.error)


def test_final_gate_fails_when_release_audit_count_mismatches_source_bundle(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(
        inputs["release_audit"],
        {
            "status": "passed",
            "candidate_count": len(_candidate_files()) - 1,
            "manifest_count": len(_candidate_files()) - 1,
            "missing_from_manifest": [],
            "manifest_extra": [],
            "secret_findings": [],
            "excluded_reference_findings": [],
        },
    )

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "release_report_consistency")
    assert gate.ok is False
    assert "file_count mismatch" in str(gate.error)


def test_final_gate_fails_when_release_audit_manifest_extra_is_not_empty(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(
        inputs["release_audit"],
        {
            "status": "passed",
            "candidate_count": len(_candidate_files()),
            "manifest_count": len(_candidate_files()),
            "missing_from_manifest": [],
            "manifest_extra": ["backend/app/main.py"],
            "secret_findings": [],
            "excluded_reference_findings": [],
        },
    )

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "release_report_consistency")
    assert gate.ok is False
    assert "release_audit.manifest_extra is not empty" in str(gate.error)


def test_final_gate_fails_when_staging_command_paths_omit_source_bundle_file(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(inputs["staging_plan"], _staging_plan_payload(_candidate_files()[:-1]))

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "release_report_consistency")
    assert gate.ok is False
    assert "staging/source path mismatch" in str(gate.error)


def test_final_gate_fails_when_staging_plan_has_dirty_validation_lists(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    staging_payload = _staging_plan_payload(_candidate_files(), errors=["manifest includes excluded paths"])
    staging_payload["missing_files"] = ["missing.py"]
    _write_json(inputs["staging_plan"], staging_payload)

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "release_report_consistency")
    assert gate.ok is False
    assert "staging_plan.missing_files is not empty" in str(gate.error)
    assert "staging_plan.errors is not empty" in str(gate.error)


def test_final_gate_requires_receipt_refresh_when_receipt_file_count_is_stale(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(
        inputs["release_receipt"],
        {
            "status": "created",
            "generated_at": "2026-06-05T10:02:00Z",
            "artifact": {
                "path": str(tmp_path / "release" / "bundle.zip"),
                "sha256": "a" * 64,
                "file_count": len(_candidate_files()) - 1,
            },
            "final_gate": {"status": "ready_with_owner_gates"},
            "checks": [{"name": "release_artifact_consistency", "status": "passed"}],
        },
    )

    report = run_final_gate(inputs)

    assert report.status == "ready_with_receipt_refresh_required"
    assert report.rc_candidate is False
    assert report.release_decision["can_stage_candidate_files"] is False
    gate = next(item for item in report.local_gates if item.name == "release_report_consistency")
    assert gate.ok is True
    assert gate.status == "refresh_required"
    assert "artifact.file_count does not match current reports" in str(gate.error)


def test_final_gate_fails_when_staging_plan_failed(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(inputs["staging_plan"], {"status": "failed", "errors": ["manifest includes excluded paths"]})

    report = run_final_gate(inputs)

    assert report.status == "failed"
    assert any(gate.name == "staging_plan" and not gate.ok for gate in report.local_gates)


def test_final_gate_fails_when_ci_contract_failed(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(inputs["ci_contract"], {"status": "failed", "findings": [{"id": "frontend_build"}]})

    report = run_final_gate(inputs)

    assert report.status == "failed"
    assert any(gate.name == "ci_contract" and not gate.ok for gate in report.local_gates)


def test_final_gate_requires_evidence_pack_refresh_after_refresh_chain_changes(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    payload = json.loads(inputs["refresh_release_chain"].read_text(encoding="utf-8"))
    payload["generated_at"] = "2026-06-05T10:04:00Z"
    _write_json(inputs["refresh_release_chain"], payload)

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "evidence_pack")
    assert gate.status == "failed"
    assert any(item["name"] == "refresh_release_chain" for item in gate.details["stale_reports"])


def test_final_gate_allows_refresh_chain_fixed_point_after_evidence_pack(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    payload = json.loads(inputs["refresh_release_chain"].read_text(encoding="utf-8"))
    payload["generated_at"] = "2026-06-05T10:04:00Z"
    payload["steps"] = [
        {"name": "evidence_pack_after_receipt", "status": "passed"},
        {"name": "final_gate_final", "status": "passed"},
    ]
    _write_json(inputs["refresh_release_chain"], payload)

    report = run_final_gate(inputs)

    gate = next(item for item in report.local_gates if item.name == "evidence_pack")
    assert gate.status == "passed"
    assert gate.ok is True


def test_final_gate_bootstrap_allows_deployment_docs_state_only_refresh(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(
        inputs["deployment_docs_gate"],
        {
            "status": "failed",
            "generated_at": "2026-06-05T10:01:00Z",
            "checks": [
                {"name": "runbook_document", "status": "passed"},
                {"name": "release_state_docs", "status": "failed"},
                {"name": "overclaim_boundary_docs", "status": "failed"},
            ],
        },
    )

    report = run_final_gate(inputs, allow_missing_evidence_pack=True)

    gate = next(item for item in report.local_gates if item.name == "deployment_docs_gate")
    assert gate.ok is True
    assert gate.status == "bootstrap_allowed"
    assert gate.details["bootstrap_allowed"] is True


def test_final_gate_fails_when_owner_gate_plan_missing(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    inputs["owner_gate_plan"].unlink()

    report = run_final_gate(inputs)

    assert report.status == "failed"
    assert any(gate.name == "owner_gate_plan" and not gate.ok for gate in report.local_gates)


def test_final_gate_fails_when_owner_env_template_missing(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    inputs["owner_env_template"].unlink()

    report = run_final_gate(inputs)

    assert report.status == "failed"
    assert any(gate.name == "owner_env_template" and not gate.ok for gate in report.local_gates)


def test_final_gate_fails_when_owner_gate_checklist_missing(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    inputs["owner_gate_checklist"].unlink()

    report = run_final_gate(inputs)

    assert report.status == "failed"
    assert any(gate.name == "owner_gate_checklist" and not gate.ok for gate in report.local_gates)


def test_final_gate_fails_when_owner_handoff_required_checks_missing(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(
        inputs["owner_handoff_gate"],
        _owner_handoff_report(checks=[{"name": "owner_gate_plan", "status": "passed"}]),
    )

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "owner_handoff_gate")
    assert gate.ok is False
    assert "missing required owner_handoff_gate checks" in str(gate.error)


def test_final_gate_fails_when_owner_handoff_privacy_findings_present(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    checks = _owner_handoff_checks()
    for check in checks:
        if check["name"] == "owner_env_template":
            check["details"] = {"secret_findings": [], "local_path_findings": ["redacted-local-path"]}
    _write_json(inputs["owner_handoff_gate"], _owner_handoff_report(checks=checks))

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "owner_handoff_gate")
    assert gate.ok is False
    assert "owner_env_template reported local user/runtime path findings" in str(gate.error)


def test_final_gate_fails_when_install_release_gate_fails(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(inputs["install_release_gate"], {"status": "failed", "checks": [{"name": "doctor", "status": "failed"}]})

    report = run_final_gate(inputs)

    assert report.status == "failed"
    assert any(gate.name == "install_release_gate" and not gate.ok for gate in report.local_gates)


def test_final_gate_fails_when_install_release_required_check_missing(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(
        inputs["install_release_gate"],
        {
            "status": "passed",
            "checks": [
                {"name": "windows_installer_dry_run", "status": "passed"},
                {"name": "posix_installer_dry_run", "status": "passed"},
                {"name": "doctor", "status": "passed"},
                {"name": "source_bundle_report", "status": "passed"},
                {"name": "artifact_integrity_report", "status": "passed"},
                {"name": "staging_plan_report", "status": "passed"},
            ],
        },
    )

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "install_release_gate")
    assert gate.ok is False
    assert "missing required install_release_gate checks: release_artifact_consistency" in str(gate.error)


def test_final_gate_fails_when_single_user_local_gate_missing(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    inputs["single_user_local_gate"].unlink()

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "single_user_local_gate")
    assert gate.ok is False
    assert "report missing" in str(gate.error)


def test_final_gate_fails_when_single_user_required_check_missing(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(
        inputs["single_user_local_gate"],
        {
            "status": "passed",
            "checks": [
                {"name": "rc2_release_handoff_snapshot", "status": "passed"},
                {"name": "install_release_gate", "status": "passed"},
                {"name": "frontend_production_build", "status": "passed"},
                {"name": "runtime_smoke", "status": "passed"},
            ],
        },
    )

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "single_user_local_gate")
    assert gate.ok is False
    assert "missing required single_user_local_gate checks: targeted_single_user_tests" in str(gate.error)


def test_final_gate_allows_optional_single_user_handoff_snapshot_skipped(tmp_path: Path) -> None:
    report = run_final_gate(_inputs(tmp_path))

    gate = next(item for item in report.local_gates if item.name == "single_user_local_gate")
    assert gate.ok is True
    assert gate.status == "passed"


def test_final_gate_fails_when_supply_chain_gate_fails(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(inputs["supply_chain_gate"], {"status": "failed", "checks": [{"name": "npm_audit", "status": "failed"}]})

    report = run_final_gate(inputs)

    assert report.status == "failed"
    assert any(gate.name == "supply_chain_gate" and not gate.ok for gate in report.local_gates)


def test_final_gate_fails_when_supply_chain_required_check_missing(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(
        inputs["supply_chain_gate"],
        {
                "status": "passed",
                "checks": [
                    {"name": "python_manifest", "status": "passed"},
                    {"name": "python_lockfile", "status": "passed"},
                    {"name": "frontend_lockfile", "status": "passed"},
                    {"name": "npm_audit", "status": "passed"},
                    {"name": "ci_dependency_contract", "status": "passed"},
                ],
            },
    )

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "supply_chain_gate")
    assert gate.ok is False
    assert "missing required supply_chain_gate checks: release_dependency_evidence" in str(gate.error)


def test_final_gate_fails_when_python_lockfile_check_missing(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(
        inputs["supply_chain_gate"],
        {
            "status": "passed",
            "checks": [
                {"name": "python_manifest", "status": "passed"},
                {"name": "frontend_lockfile", "status": "passed"},
                {"name": "npm_audit", "status": "passed"},
                {"name": "ci_dependency_contract", "status": "passed"},
                {"name": "release_dependency_evidence", "status": "passed"},
            ],
        },
    )

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "supply_chain_gate")
    assert gate.ok is False
    assert "missing required supply_chain_gate checks: python_lockfile" in str(gate.error)


def test_final_gate_fails_when_secrets_gate_fails(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(inputs["secrets_gate"], {"status": "failed", "checks": [{"name": "secret_strength", "status": "failed"}]})

    report = run_final_gate(inputs)

    assert report.status == "failed"
    assert any(gate.name == "secrets_gate" and not gate.ok for gate in report.local_gates)


def test_final_gate_fails_when_secrets_gate_missing_artifact_scan(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(
        inputs["secrets_gate"],
        {
            "status": "passed",
            "checks": [
                {"name": "required_fields", "status": "passed"},
                {"name": "secret_strength", "status": "passed"},
                {"name": "unique_generated_values", "status": "passed"},
                {"name": "release_audit_secret_scan", "status": "passed"},
            ],
            "generated_value_count": 7,
            "unique_value_count": 7,
            "required_fields": [
                "AUDIT_HMAC_SECRET",
                "BOOTSTRAP_API_KEY",
                "ENCRYPTION_KEY",
                "JWT_SECRET",
                "NEO4J_PASSWORD",
                "S3_ACCESS_KEY",
                "S3_SECRET_KEY",
            ],
        },
    )

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "secrets_gate")
    assert gate.ok is False
    assert "missing required secrets checks: artifact_secret_scan" in str(gate.error)


def test_final_gate_fails_when_required_secrets_subcheck_fails(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(
        inputs["secrets_gate"],
        {
            "status": "passed",
            "checks": [
                {"name": "required_fields", "status": "passed"},
                {"name": "secret_strength", "status": "passed"},
                {"name": "unique_generated_values", "status": "passed"},
                {"name": "release_audit_secret_scan", "status": "passed"},
                {"name": "artifact_secret_scan", "status": "failed"},
            ],
            "generated_value_count": 7,
            "unique_value_count": 7,
            "required_fields": [
                "AUDIT_HMAC_SECRET",
                "BOOTSTRAP_API_KEY",
                "ENCRYPTION_KEY",
                "JWT_SECRET",
                "NEO4J_PASSWORD",
                "S3_ACCESS_KEY",
                "S3_SECRET_KEY",
            ],
        },
    )

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "secrets_gate")
    assert gate.ok is False
    assert "required secrets checks failed: artifact_secret_scan" in str(gate.error)


def test_final_gate_rejects_full_parity_claim(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path, external_checks=[{"name": "provider", "status": "passed", "missing": []}])
    _write_json(
        inputs["gap_matrix"],
        {
            "summary": {
                "overall_status": "passed",
                "competitive_parity": {"full_parity_claimed": True},
            }
        },
    )

    report = run_final_gate(inputs)

    assert report.status == "failed"
    assert report.rc_candidate is False
    assert report.full_parity_claimed is True
    assert report.release_decision["can_tag_rc_now"] is False
