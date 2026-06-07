from __future__ import annotations

import json
from pathlib import Path

from scripts.rc_release_receipt import run_release_receipt


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


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
        "inputs": {},
        "checks": checks if checks is not None else _owner_handoff_checks(),
        "next_commands": ["Give rc-owner-env-template.* to the deployment owner."],
    }


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


def _reports(tmp_path: Path) -> dict[str, Path]:
    artifact = tmp_path / "release" / "bundle.zip"
    artifact.parent.mkdir()
    artifact.write_bytes(b"zip")
    return {
        "artifact": _write_json(
            tmp_path / "reports" / "rc-artifact-integrity-gate.json",
            {
                "status": "passed",
                "artifact_path": str(artifact),
                "artifact_sha256": "a" * 64,
                "artifact_size_bytes": artifact.stat().st_size,
                "file_count": 2,
                "checks": [
                    {
                        "name": "zip_security_scan",
                        "status": "passed",
                        "details": {
                            "scanned_text_files": 2,
                            "secret_findings": [],
                            "excluded_reference_findings": [],
                            "local_path_findings": [],
                        },
                    }
                ],
            },
        ),
        "final": _write_json(
            tmp_path / "reports" / "rc-final-gate.json",
            {
                "status": "ready_with_owner_gates",
                "rc_candidate": True,
                "full_parity_claimed": False,
                "release_decision": {
                    "can_stage_candidate_files": True,
                    "can_tag_rc_now": False,
                    "reason": "owner-controlled external gates remain",
                },
                "owner_gates": [{"name": "provider", "status": "action_required", "missing": ["token"]}],
            },
        ),
        "diff_review": _write_json(
            tmp_path / "reports" / "rc-release-diff-review-gate.json",
            {
                "status": "passed",
                "checks": [{"name": "review_document", "status": "passed"}],
            },
        ),
        "deployment_docs": _write_json(
            tmp_path / "reports" / "rc-deployment-docs-gate.json",
            {
                "status": "passed",
                "checks": [{"name": "runbook_document", "status": "passed"}],
            },
        ),
        "source": _write_json(
            tmp_path / "reports" / "rc-source-bundle.json",
            {
                "status": "created",
                "manifest_path": "docs/RC_STAGING_MANIFEST.md",
                "output_path": str(artifact),
                "file_count": 2,
                "total_bytes": 100,
                "errors": [],
            },
        ),
        "staging": _write_json(
            tmp_path / "reports" / "rc-staging-plan.json",
            {
                "status": "planned",
                "manifest_path": "docs/RC_STAGING_MANIFEST.md",
                "manifest_sha256": "f" * 64,
                "file_count": 2,
                "command_count": 1,
                "missing_files": [],
                "excluded_files": [],
            },
        ),
        "owner": _write_json(
            tmp_path / "reports" / "rc-owner-gate-plan.json",
            {
                "status": "action_required",
                "gates": [
                    {
                        "name": "provider",
                        "status": "action_required",
                        "required_env_groups": [
                            ["XAGENT_LLM_BACKEND", "LLM_BACKEND"],
                            ["XAGENT_OPENAI_API_KEY", "OPENAI_API_KEY"],
                        ],
                        "configured_env": [],
                        "missing": ["provider token"],
                        "command": "python scripts\\rc_external_smoke.py --require-configured",
                        "evidence": [".xagent_runtime/reports/rc-external-smoke.json"],
                        "completion_criteria": ["Provider check status is passed"],
                    },
                    {
                        "name": "github_issue_to_pr_dry_run",
                        "status": "action_required",
                        "required_env_groups": [["XAGENT_GITHUB_TEST_ISSUE_URL"]],
                        "configured_env": [],
                        "missing": ["XAGENT_GITHUB_TEST_ISSUE_URL"],
                        "command": (
                            "python scripts\\rc_owner_gate_runner.py "
                            "--gate github_issue_to_pr_dry_run --dry-run"
                        ),
                        "evidence": [".xagent_runtime/reports/rc-external-smoke.json"],
                        "completion_criteria": ["GitHub issue dry-run check status is passed"],
                    },
                ],
            },
        ),
        "owner_handoff": _write_json(
            tmp_path / "reports" / "rc-owner-handoff-gate.json",
            _owner_handoff_report(),
        ),
        "owner_runner": _write_json(
            tmp_path / "reports" / "rc-owner-gate-runner.json",
            {
                "status": "planned",
                "generated_at": "2026-06-05T10:01:00Z",
                "selected_gate": "all",
                "dry_run": True,
                "steps": _owner_gate_runner_steps(),
                "next_commands": ["Inspect .xagent_runtime/reports/rc-owner-gate-runner.json."],
                "env_file": ".xagent_runtime/reports/rc-owner-env-template.env",
                "loaded_env_names": ["XAGENT_OLLAMA_MODEL"],
                "owner_gate_env_names": ["XAGENT_OLLAMA_MODEL"],
                "missing_env_groups": [["XAGENT_GITHUB_TOKEN", "GITHUB_TOKEN"]],
            },
        ),
        "owner_env": _write_json(
            tmp_path / "reports" / "rc-owner-env-template.json",
            {
                "status": "created",
                "env_groups": [
                    ["XAGENT_LLM_BACKEND", "LLM_BACKEND"],
                    ["XAGENT_OPENAI_API_KEY", "OPENAI_API_KEY"],
                ],
                "entries": [
                    {
                        "name": "XAGENT_LLM_BACKEND",
                        "value": "<openai|deepseek|anthropic|ollama|local>",
                        "required_by": ["provider"],
                        "aliases": ["LLM_BACKEND"],
                        "preferred": True,
                    },
                    {
                        "name": "XAGENT_OPENAI_API_KEY",
                        "value": "<set-in-owner-secret-store>",
                        "required_by": ["provider"],
                        "aliases": ["OPENAI_API_KEY"],
                        "preferred": True,
                    },
                ],
                "command_sequence": ["python scripts\\rc_external_smoke.py --require-configured"],
                "errors": [],
            },
        ),
        "owner_checklist": _write_json(
            tmp_path / "reports" / "rc-owner-gate-checklist.json",
            {
                "status": "action_required",
                "gates": [
                    {
                        "name": "provider",
                        "status": "action_required",
                        "complete": False,
                        "action_required": True,
                        "required_env_groups": [
                            ["XAGENT_LLM_BACKEND", "LLM_BACKEND"],
                            ["XAGENT_OPENAI_API_KEY", "OPENAI_API_KEY"],
                        ],
                        "configured_env": [],
                        "missing": ["provider token"],
                        "command": "python scripts\\rc_external_smoke.py --require-configured",
                        "evidence": [".xagent_runtime/reports/rc-external-smoke.json"],
                        "completion_criteria": ["Provider check status is passed"],
                    },
                    {
                        "name": "github_issue_to_pr_dry_run",
                        "status": "action_required",
                        "complete": False,
                        "action_required": True,
                        "required_env_groups": [["XAGENT_GITHUB_TEST_ISSUE_URL"]],
                        "configured_env": [],
                        "missing": ["XAGENT_GITHUB_TEST_ISSUE_URL"],
                        "command": (
                            "python scripts\\rc_owner_gate_runner.py "
                            "--gate github_issue_to_pr_dry_run --dry-run"
                        ),
                        "evidence": [".xagent_runtime/reports/rc-external-smoke.json"],
                        "completion_criteria": ["GitHub issue dry-run check status is passed"],
                    },
                ],
                "next_commands": [
                    (
                        "python scripts\\rc_owner_gate_runner.py --gate all "
                        "--env-file .xagent_runtime\\reports\\rc-owner-env-template.env"
                    ),
                    (
                        "python scripts\\rc_external_smoke.py --provider ollama --require-configured "
                        "--github-execute-preflight --github-actions-preflight"
                    ),
                ],
                "errors": [],
            },
        ),
        "install": _write_json(
            tmp_path / "reports" / "rc-install-release-gate.json",
            {
                "status": "passed",
                "checks": [
                    {"name": "windows_installer_dry_run", "status": "passed"},
                    {"name": "posix_installer_dry_run", "status": "passed"},
                    {"name": "doctor", "status": "passed"},
                    {"name": "source_bundle_report", "status": "passed"},
                    {"name": "artifact_integrity_report", "status": "passed"},
                    {"name": "staging_plan_report", "status": "passed"},
                    {"name": "release_artifact_consistency", "status": "passed"},
                ],
            },
        ),
        "single_user": _write_json(
            tmp_path / "reports" / "rc-single-user-local-gate.json",
            {
                "status": "passed",
                "checks": [
                    {"name": "rc2_release_handoff_snapshot", "status": "skipped"},
                    {"name": "install_release_gate", "status": "passed"},
                    {"name": "frontend_production_build", "status": "passed"},
                    {"name": "runtime_smoke", "status": "passed"},
                    {"name": "targeted_single_user_tests", "status": "passed"},
                ],
            },
        ),
        "supply": _write_json(
            tmp_path / "reports" / "rc-supply-chain-gate.json",
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
        ),
        "secrets": _write_json(
            tmp_path / "reports" / "rc-secrets-gate.json",
            {
                "status": "passed",
                "checks": [
                    {"name": "required_fields", "status": "passed"},
                    {"name": "secret_strength", "status": "passed"},
                    {"name": "unique_generated_values", "status": "passed"},
                    {"name": "release_audit_secret_scan", "status": "passed"},
                    {"name": "artifact_secret_scan", "status": "passed"},
                    {"name": "prohibited_secret_artifacts", "status": "passed"},
                ],
                "non_leakage_note": "Generated secret values are validated in memory and are not included in this report.",
            },
        ),
    }


def _receipt(reports: dict[str, Path], *, write_sha256: bool = True):
    return run_release_receipt(
        artifact_integrity_report=reports["artifact"],
        final_gate_report=reports["final"],
        release_diff_review_gate_report=reports["diff_review"],
        deployment_docs_gate_report=reports["deployment_docs"],
        source_bundle_report=reports["source"],
        staging_plan_report=reports["staging"],
        owner_gate_plan_report=reports["owner"],
        owner_gate_runner_report=reports["owner_runner"],
        owner_handoff_gate_report=reports["owner_handoff"],
        owner_env_template_report=reports["owner_env"],
        owner_gate_checklist_report=reports["owner_checklist"],
        install_release_gate_report=reports["install"],
        single_user_local_gate_report=reports["single_user"],
        supply_chain_gate_report=reports["supply"],
        secrets_gate_report=reports["secrets"],
        write_sha256=write_sha256,
    )


def test_release_receipt_created_and_writes_sha256_sidecar(tmp_path: Path) -> None:
    reports = _reports(tmp_path)

    receipt = _receipt(reports)

    assert receipt.status == "created"
    assert receipt.artifact["sha256"] == "a" * 64
    assert receipt.artifact["security_scan"]["local_path_finding_count"] == 0
    assert receipt.final_gate["can_tag_rc_now"] is False
    assert receipt.staging_plan["manifest_sha256"] == "f" * 64
    assert receipt.owner_gates == [{"name": "provider", "status": "action_required", "missing": ["token"]}]
    assert receipt.approval_request["approval_required_before_staging"] is True
    assert receipt.approval_request["final_gate_status"] == "ready_with_owner_gates"
    assert receipt.approval_request["artifact_sha256"] == "a" * 64
    assert receipt.approval_request["artifact_file_count"] == 2
    assert receipt.approval_request["can_tag_rc_now"] is False
    assert receipt.approval_request["full_parity_claimed"] is False
    assert receipt.approval_request["remaining_risks"] == [
        {"name": "provider", "status": "action_required", "missing": ["token"]}
    ]
    assert receipt.approval_request["exact_staging_commands"] == []
    assert receipt.approval_request["no_broad_staging_command"] is True
    assert receipt.owner_gate_evidence["status"] == "action_required"
    assert [action["name"] for action in receipt.owner_gate_next_actions] == [
        "provider",
        "github_issue_to_pr_dry_run",
    ]
    github_action = next(action for action in receipt.owner_gate_next_actions if action["name"] == "github_issue_to_pr_dry_run")
    assert github_action["required_env_groups"] == [["XAGENT_GITHUB_TEST_ISSUE_URL"]]
    assert github_action["missing"] == ["XAGENT_GITHUB_TEST_ISSUE_URL"]
    assert github_action["command"] == "python scripts\\rc_owner_gate_runner.py --gate github_issue_to_pr_dry_run --dry-run"
    assert github_action["evidence"] == [".xagent_runtime/reports/rc-external-smoke.json"]
    assert github_action["completion_criteria"] == ["GitHub issue dry-run check status is passed"]
    assert receipt.owner_handoff_gate["status"] == "passed"
    owner_env_handoff = next(
        check for check in receipt.owner_handoff_gate["checks"] if check["name"] == "owner_env_template"
    )
    assert owner_env_handoff["secret_finding_count"] == 0
    assert owner_env_handoff["local_path_finding_count"] == 0
    assert receipt.owner_env_template["status"] == "created"
    assert receipt.owner_env_template["entry_count"] == 2
    assert receipt.owner_env_template["env_groups"] == [
        ["XAGENT_LLM_BACKEND", "LLM_BACKEND"],
        ["XAGENT_OPENAI_API_KEY", "OPENAI_API_KEY"],
    ]
    assert receipt.owner_gate_checklist["status"] == "action_required"
    assert receipt.owner_gate_checklist["gate_count"] == 2
    assert receipt.owner_gate_runner["status"] == "planned"
    assert receipt.owner_gate_runner["selected_gate"] == "all"
    assert receipt.owner_gate_runner["dry_run"] is True
    assert receipt.owner_gate_runner["env_file"] == ".xagent_runtime/reports/rc-owner-env-template.env"
    assert receipt.owner_gate_runner["loaded_env_names"] == ["XAGENT_OLLAMA_MODEL"]
    assert receipt.owner_gate_runner["owner_gate_env_names"] == ["XAGENT_OLLAMA_MODEL"]
    assert receipt.owner_gate_runner["missing_env_groups"] == [["XAGENT_GITHUB_TOKEN", "GITHUB_TOKEN"]]
    assert receipt.owner_gate_runner["step_count"] == 6
    assert "--github-execute-preflight" in receipt.owner_gate_runner["steps"][0]["command"]
    assert receipt.release_diff_review_gate["status"] == "passed"
    assert receipt.deployment_docs_gate["status"] == "passed"
    assert receipt.install_release_gate["status"] == "passed"
    assert receipt.single_user_local_gate["status"] == "passed"
    assert receipt.supply_chain_gate["status"] == "passed"
    assert receipt.secrets_gate["status"] == "passed"
    assert any(check.name == "install_release_gate" and check.status == "passed" for check in receipt.checks)
    assert any(check.name == "single_user_local_gate" and check.status == "passed" for check in receipt.checks)
    assert any(check.name == "supply_chain_gate" and check.status == "passed" for check in receipt.checks)
    assert any(check.name == "secrets_gate" and check.status == "passed" for check in receipt.checks)
    assert any(check.name == "owner_handoff_gate" and check.status == "passed" for check in receipt.checks)
    assert any(check.name == "owner_env_template" and check.status == "passed" for check in receipt.checks)
    assert any(check.name == "owner_gate_checklist" and check.status == "passed" for check in receipt.checks)
    assert any(check.name == "owner_gate_runner" and check.status == "passed" for check in receipt.checks)
    assert any(check.name == "release_diff_review_gate" and check.status == "passed" for check in receipt.checks)
    assert any(check.name == "deployment_docs_gate" and check.status == "passed" for check in receipt.checks)
    assert any(check.name == "artifact_security_scan" and check.status == "passed" for check in receipt.checks)
    sidecar = Path(receipt.sidecars["sha256"])
    assert sidecar.exists()
    assert sidecar.read_text(encoding="utf-8") == f"{'a' * 64}  bundle.zip\n"


def test_release_receipt_fails_when_source_bundle_not_created(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    _write_json(reports["source"], {"status": "planned", "dry_run": True})

    receipt = _receipt(reports)

    assert receipt.status == "failed"
    assert any(check.name == "source_bundle" and check.status == "failed" for check in receipt.checks)


def test_release_receipt_fails_when_artifact_paths_do_not_match(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    other_artifact = tmp_path / "release" / "old-bundle.zip"
    other_artifact.write_bytes(b"old")
    _write_json(
        reports["artifact"],
        {
            "status": "passed",
            "artifact_path": str(other_artifact),
            "artifact_sha256": "b" * 64,
            "artifact_size_bytes": other_artifact.stat().st_size,
            "file_count": 2,
        },
    )

    receipt = _receipt(reports)

    assert receipt.status == "failed"
    check = next(item for item in receipt.checks if item.name == "release_artifact_consistency")
    assert check.status == "failed"
    assert "does not match source_bundle.output_path" in str(check.error)


def test_release_receipt_rejects_artifact_local_path_findings(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    artifact_payload = json.loads(reports["artifact"].read_text(encoding="utf-8"))
    artifact_payload["checks"][0]["status"] = "failed"
    artifact_payload["checks"][0]["details"]["local_path_findings"] = [
        {"path": "docs/handoff.txt", "pattern": "windows_user_profile"}
    ]
    _write_json(reports["artifact"], artifact_payload)

    receipt = _receipt(reports)

    assert receipt.status == "failed"
    check = next(item for item in receipt.checks if item.name == "artifact_security_scan")
    assert check.status == "failed"
    assert "local user/runtime path findings" in str(check.error)


def test_release_receipt_can_bootstrap_when_final_gate_only_has_stale_receipt(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    _write_json(
        reports["final"],
        {
            "status": "failed",
            "rc_candidate": False,
            "full_parity_claimed": False,
            "release_decision": {"can_stage_candidate_files": False, "can_tag_rc_now": False},
            "local_gates": [
                {"name": "artifact_integrity_gate", "ok": True},
                {"name": "release_receipt", "ok": False},
            ],
            "owner_gates": [{"name": "provider", "status": "action_required", "missing": ["token"]}],
        },
    )

    receipt = _receipt(reports)

    assert receipt.status == "created"
    final_check = next(item for item in receipt.checks if item.name == "final_gate")
    assert final_check.details["bootstrap_allowed"] is True


def test_release_receipt_can_bootstrap_when_final_gate_only_needs_receipt_and_evidence_refresh(
    tmp_path: Path,
) -> None:
    reports = _reports(tmp_path)
    _write_json(
        reports["final"],
        {
            "status": "failed",
            "rc_candidate": False,
            "full_parity_claimed": False,
            "release_decision": {"can_stage_candidate_files": False, "can_tag_rc_now": False},
            "local_gates": [
                {"name": "artifact_integrity_gate", "ok": True},
                {"name": "release_receipt", "status": "refresh_required", "ok": True},
                {
                    "name": "evidence_pack",
                    "status": "failed",
                    "ok": False,
                    "details": {"stale_reports": [{"name": "source_bundle"}]},
                    "error": "evidence pack is older than required release reports",
                },
            ],
            "owner_gates": [{"name": "provider", "status": "action_required", "missing": ["token"]}],
        },
    )

    receipt = _receipt(reports)

    assert receipt.status == "created"
    final_check = next(item for item in receipt.checks if item.name == "final_gate")
    assert final_check.details["bootstrap_allowed"] is True


def test_release_receipt_can_bootstrap_when_evidence_pack_only_has_receipt_cycle(
    tmp_path: Path,
) -> None:
    reports = _reports(tmp_path)
    _write_json(
        reports["final"],
        {
            "status": "failed",
            "rc_candidate": False,
            "full_parity_claimed": False,
            "release_decision": {"can_stage_candidate_files": False, "can_tag_rc_now": False},
            "local_gates": [
                {"name": "artifact_integrity_gate", "ok": True},
                {"name": "release_receipt", "status": "refresh_required", "ok": True},
                {
                    "name": "evidence_pack",
                    "status": "failed",
                    "ok": False,
                    "error": "expected ['created'], got failed; required evidence_pack checks failed: release_receipt",
                },
            ],
            "owner_gates": [{"name": "provider", "status": "action_required", "missing": ["token"]}],
        },
    )

    receipt = _receipt(reports)

    assert receipt.status == "created"
    final_check = next(item for item in receipt.checks if item.name == "final_gate")
    assert final_check.details["bootstrap_allowed"] is True


def test_release_receipt_accepts_refresh_required_final_gate(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    _write_json(
        reports["final"],
        {
            "status": "ready_with_receipt_refresh_required",
            "rc_candidate": False,
            "full_parity_claimed": False,
            "release_decision": {
                "can_stage_candidate_files": False,
                "can_tag_rc_now": False,
                "reason": "release receipt refresh required",
            },
            "owner_gates": [{"name": "provider", "status": "action_required", "missing": ["token"]}],
        },
    )

    receipt = _receipt(reports)

    assert receipt.status == "created"
    assert receipt.final_gate["status"] == "ready_with_receipt_refresh_required"
    final_check = next(item for item in receipt.checks if item.name == "final_gate")
    assert final_check.details["bootstrap_allowed"] is True


def test_release_receipt_rejects_final_gate_with_non_receipt_failure(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    _write_json(
        reports["final"],
        {
            "status": "failed",
            "local_gates": [
                {"name": "artifact_integrity_gate", "ok": False},
                {"name": "release_receipt", "ok": False},
            ],
        },
    )

    receipt = _receipt(reports)

    assert receipt.status == "failed"
    final_check = next(item for item in receipt.checks if item.name == "final_gate")
    assert final_check.status == "failed"


def test_release_receipt_can_skip_sha256_sidecar(tmp_path: Path) -> None:
    reports = _reports(tmp_path)

    receipt = _receipt(reports, write_sha256=False)

    assert receipt.status == "created"
    assert receipt.sidecars["sha256"] is None


def test_release_receipt_does_not_include_secret_values(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    secret_value = "xagent-" + ("S" * 64)

    receipt = _receipt(reports)
    payload = json.dumps(receipt.to_dict())

    assert secret_value not in payload


def test_release_receipt_owner_gate_next_actions_do_not_include_template_values(tmp_path: Path) -> None:
    reports = _reports(tmp_path)

    receipt = _receipt(reports)
    payload = json.dumps(receipt.owner_gate_next_actions)

    assert "XAGENT_OPENAI_API_KEY" in payload
    assert "<set-in-owner-secret-store>" not in payload
    assert "sk-" not in payload


def test_release_receipt_rejects_missing_owner_env_template(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    reports["owner_env"].unlink()

    receipt = _receipt(reports)

    assert receipt.status == "failed"
    check = next(item for item in receipt.checks if item.name == "owner_env_template")
    assert check.status == "failed"
    assert "missing report" in str(check.error)


def test_release_receipt_rejects_failed_owner_handoff_gate(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    _write_json(
        reports["owner_handoff"],
        {"status": "failed", "checks": [{"name": "owner_gate_plan", "status": "failed"}]},
    )

    receipt = _receipt(reports)

    assert receipt.status == "failed"
    check = next(item for item in receipt.checks if item.name == "owner_handoff_gate")
    assert check.status == "failed"
    assert "expected passed" in str(check.error)


def test_release_receipt_rejects_owner_handoff_missing_required_checks(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    _write_json(
        reports["owner_handoff"],
        _owner_handoff_report(checks=[{"name": "owner_gate_plan", "status": "passed"}]),
    )

    receipt = _receipt(reports)

    assert receipt.status == "failed"
    check = next(item for item in receipt.checks if item.name == "owner_handoff_gate")
    assert check.status == "failed"
    assert "missing required owner_handoff_gate checks" in str(check.error)


def test_release_receipt_rejects_owner_handoff_local_path_findings(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    checks = _owner_handoff_checks()
    for check in checks:
        if check["name"] == "owner_gate_checklist":
            check["details"] = {"secret_findings": [], "local_path_findings": ["redacted-local-path"]}
    _write_json(reports["owner_handoff"], _owner_handoff_report(checks=checks))

    receipt = _receipt(reports)

    assert receipt.status == "failed"
    check = next(item for item in receipt.checks if item.name == "owner_handoff_gate")
    assert check.status == "failed"
    assert "owner_gate_checklist reported local user/runtime path findings" in str(check.error)


def test_release_receipt_rejects_owner_env_template_with_secret_values(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    _write_json(
        reports["owner_env"],
        {
            "status": "created",
            "entries": [
                {
                    "name": "XAGENT_OPENAI_API_KEY",
                    "value": "sk-" + ("a" * 32),
                    "required_by": ["provider"],
                }
            ],
            "command_sequence": [],
            "errors": [],
        },
    )

    receipt = _receipt(reports)

    assert receipt.status == "failed"
    check = next(item for item in receipt.checks if item.name == "owner_env_template")
    assert check.status == "failed"
    assert "secret-like value" in str(check.error)


def test_release_receipt_rejects_missing_owner_gate_checklist(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    reports["owner_checklist"].unlink()

    receipt = _receipt(reports)

    assert receipt.status == "failed"
    check = next(item for item in receipt.checks if item.name == "owner_gate_checklist")
    assert check.status == "failed"
    assert "missing report" in str(check.error)


def test_release_receipt_rejects_owner_gate_checklist_without_gates(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    _write_json(reports["owner_checklist"], {"status": "action_required", "gates": [], "next_commands": []})

    receipt = _receipt(reports)

    assert receipt.status == "failed"
    check = next(item for item in receipt.checks if item.name == "owner_gate_checklist")
    assert check.status == "failed"
    assert "gates is missing or empty" in str(check.error)


def test_release_receipt_rejects_owner_gate_checklist_without_strict_next_commands(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    checklist = json.loads(reports["owner_checklist"].read_text(encoding="utf-8"))
    checklist["next_commands"] = [
        "python scripts\\rc_owner_gate_runner.py --gate all",
        "python scripts\\rc_external_smoke.py --require-configured",
    ]
    _write_json(reports["owner_checklist"], checklist)

    receipt = _receipt(reports)

    assert receipt.status == "failed"
    check = next(item for item in receipt.checks if item.name == "owner_gate_checklist")
    assert check.status == "failed"
    assert "--env-file" in str(check.error)
    assert "--github-actions-preflight" in str(check.error)


def test_release_receipt_rejects_missing_owner_gate_runner(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    reports["owner_runner"].unlink()

    receipt = _receipt(reports)

    assert receipt.status == "failed"
    check = next(item for item in receipt.checks if item.name == "owner_gate_runner")
    assert check.status == "failed"
    assert "missing report" in str(check.error)


def test_release_receipt_rejects_owner_gate_runner_missing_execute_preflight(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    steps = _owner_gate_runner_steps()
    command = list(steps[0]["command"])
    command.remove("--github-execute-preflight")
    steps[0]["command"] = command
    _write_json(
        reports["owner_runner"],
        {
            "status": "planned",
            "generated_at": "2026-06-05T10:01:00Z",
            "selected_gate": "all",
            "dry_run": True,
            "steps": steps,
            "next_commands": [],
        },
    )

    receipt = _receipt(reports)

    assert receipt.status == "failed"
    check = next(item for item in receipt.checks if item.name == "owner_gate_runner")
    assert check.status == "failed"
    assert "owner_gate_runner all-gate command missing token: --github-execute-preflight" in str(check.error)


def test_release_receipt_rejects_owner_gate_runner_without_env_file_evidence(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    owner_runner = json.loads(reports["owner_runner"].read_text(encoding="utf-8"))
    owner_runner.pop("env_file")
    _write_json(reports["owner_runner"], owner_runner)

    receipt = _receipt(reports)

    assert receipt.status == "failed"
    check = next(item for item in receipt.checks if item.name == "owner_gate_runner")
    assert check.status == "failed"
    assert "owner_gate_runner env_file must be .xagent_runtime/reports/rc-owner-env-template.env" in str(check.error)


def test_release_receipt_rejects_owner_gate_runner_invalid_missing_env_groups(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    owner_runner = json.loads(reports["owner_runner"].read_text(encoding="utf-8"))
    owner_runner["missing_env_groups"] = ["XAGENT_GITHUB_TOKEN"]
    _write_json(reports["owner_runner"], owner_runner)

    receipt = _receipt(reports)

    assert receipt.status == "failed"
    check = next(item for item in receipt.checks if item.name == "owner_gate_runner")
    assert check.status == "failed"
    assert "owner_gate_runner missing_env_groups must be a list of env variable name groups" in str(check.error)


def test_release_receipt_accepts_verified_owner_plan_with_fresh_evidence(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    _write_json(
        reports["owner"],
        {
            "status": "verified",
            "generated_at": "2026-06-05T11:00:00Z",
            "external_smoke_report": "reports/rc-external-smoke.json",
            "source_bundle_report": "reports/rc-source-bundle.json",
            "evidence_freshness": {"required": True, "fresh": True},
            "gates": [{"name": "provider", "status": "verified", "missing": []}],
        },
    )

    receipt = _receipt(reports)

    assert receipt.status == "created"
    assert receipt.owner_gate_evidence["evidence_freshness"]["fresh"] is True
    assert any(check.name == "owner_gate_plan_consistency" and check.status == "passed" for check in receipt.checks)


def test_release_receipt_rejects_verified_owner_plan_with_stale_evidence(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    _write_json(
        reports["owner"],
        {
            "status": "verified",
            "generated_at": "2026-06-05T11:00:00Z",
            "external_smoke_report": "reports/rc-external-smoke.json",
            "source_bundle_report": "reports/rc-source-bundle.json",
            "evidence_freshness": {
                "required": True,
                "fresh": False,
                "problems": ["external smoke evidence is older than the current source bundle"],
            },
            "gates": [{"name": "provider", "status": "verified", "missing": []}],
        },
    )

    receipt = _receipt(reports)

    assert receipt.status == "failed"
    check = next(item for item in receipt.checks if item.name == "owner_gate_plan_consistency")
    assert check.status == "failed"
    assert "evidence is not fresh" in str(check.error)


def test_release_receipt_rejects_failed_install_release_gate(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    _write_json(
        reports["install"],
        {"status": "failed", "checks": [{"name": "doctor", "status": "failed"}]},
    )

    receipt = _receipt(reports)

    assert receipt.status == "failed"
    check = next(item for item in receipt.checks if item.name == "install_release_gate")
    assert check.status == "failed"
    assert "expected passed" in str(check.error)


def test_release_receipt_rejects_failed_deployment_docs_gate(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    _write_json(
        reports["deployment_docs"],
        {"status": "failed", "checks": [{"name": "runbook_document", "status": "failed"}]},
    )

    receipt = _receipt(reports)

    assert receipt.status == "failed"
    check = next(item for item in receipt.checks if item.name == "deployment_docs_gate")
    assert check.status == "failed"
    assert "expected passed" in str(check.error)


def test_release_receipt_rejects_failed_single_user_local_gate(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    _write_json(
        reports["single_user"],
        {"status": "passed", "checks": [{"name": "runtime_smoke", "status": "failed"}]},
    )

    receipt = _receipt(reports)

    assert receipt.status == "failed"
    check = next(item for item in receipt.checks if item.name == "single_user_local_gate")
    assert check.status == "failed"
    assert "has failed checks" in str(check.error)


def test_release_receipt_rejects_failed_supply_chain_gate(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    _write_json(
        reports["supply"],
        {"status": "passed", "checks": [{"name": "npm_audit", "status": "failed"}]},
    )

    receipt = _receipt(reports)

    assert receipt.status == "failed"
    check = next(item for item in receipt.checks if item.name == "supply_chain_gate")
    assert check.status == "failed"
    assert "has failed checks" in str(check.error)


def test_release_receipt_rejects_missing_secrets_gate_checks(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    _write_json(reports["secrets"], {"status": "passed", "checks": []})

    receipt = _receipt(reports)

    assert receipt.status == "failed"
    check = next(item for item in receipt.checks if item.name == "secrets_gate")
    assert check.status == "failed"
    assert "checks is missing or empty" in str(check.error)


def test_release_receipt_approval_request_flags_broad_staging_command(tmp_path: Path) -> None:
    reports = _reports(tmp_path)
    staging = json.loads(reports["staging"].read_text(encoding="utf-8"))
    staging["commands"] = [{"index": 1, "command": "git add .", "paths": []}]
    _write_json(reports["staging"], staging)

    receipt = _receipt(reports)

    assert receipt.approval_request["exact_staging_commands"] == ["git add ."]
    assert receipt.approval_request["no_broad_staging_command"] is False
