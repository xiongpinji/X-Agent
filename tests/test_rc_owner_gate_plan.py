from __future__ import annotations

import json
from pathlib import Path

from scripts import rc_owner_gate_plan
from scripts.rc_owner_gate_plan import build_owner_gate_plan

EXPECTED_HEAD_SHA = "0123456789abcdef0123456789abcdef01234567"


def _write_external(path: Path, checks: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"status": "passed", "generated_at": "2026-06-05T10:00:00Z", "checks": checks}), encoding="utf-8")
    return path


def _write_source_bundle(path: Path, generated_at: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": "created",
                "generated_at": generated_at,
                "file_count": 1,
                "output_path": str(path.parent / "bundle.zip"),
            }
        ),
        encoding="utf-8",
    )
    return path


def _gate(report, name: str):
    return next(gate for gate in report.gates if gate.name == name)


def _github_execute_passed_check() -> dict[str, object]:
    return {
        "name": "github_issue_to_pr_execute_preflight",
        "status": "passed",
        "details": {
            "dry_run_status": "passed",
            "read_probe": {"status": "passed", "state": "open"},
            "permission_probe": {
                "status": "passed",
                "permissions": {"push": True},
                "least_privilege": True,
                "owner_context_permissions": [],
            },
            "mutation_performed": False,
        },
    }


def _provider_passed_check() -> dict[str, object]:
    return {
        "name": "provider",
        "status": "passed",
        "details": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "sentinel": "xagent-rc-ok",
            "sentinel_matched": True,
        },
    }


def _feishu_webhook_passed_check() -> dict[str, object]:
    return {
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
    }


def _github_dry_run_passed_check() -> dict[str, object]:
    return {
        "name": "github_issue_to_pr_dry_run",
        "status": "passed",
        "details": {
            "repo_full_name": "acme/project",
            "issue_number": 42,
            "branch_name": "xagent/issue-42",
            "execute_allowed": False,
            "steps": ["parse_issue", "draft_pull_request_payload"],
        },
    }


def _hosted_actions_passed_check() -> dict[str, object]:
    return {
        "name": "hosted_github_actions_run",
        "status": "passed",
        "details": {
            "run_url": "https://github.com/acme/x/actions/runs/1",
            "run_status": "completed",
            "conclusion": "success",
            "workflow_name": "Commercial RC Gate",
            "workflow_path": ".github/workflows/commercial-rc.yml",
            "workflow_verified": True,
            "expected_head_sha": EXPECTED_HEAD_SHA,
            "head_sha": EXPECTED_HEAD_SHA,
            "head_sha_verified": True,
            "jobs_verified": True,
            "required_jobs": {
                "commercial-rc-linux": {"found": True, "status": "completed", "conclusion": "success"},
                "commercial-rc-windows-installer": {"found": True, "status": "completed", "conclusion": "success"},
            },
            "artifact_verified": True,
            "required_artifact": "commercial-rc-evidence",
            "mutation_performed": False,
        },
    }


def test_owner_gate_plan_reports_missing_default_resources(tmp_path: Path, monkeypatch) -> None:
    for name in (
        "XAGENT_LLM_BACKEND",
        "LLM_BACKEND",
        "XAGENT_FEISHU_APP_ID",
        "XAGENT_FEISHU_APP_SECRET",
        "XAGENT_FEISHU_ENCRYPT_KEY",
        "XAGENT_GITHUB_TOKEN",
        "XAGENT_GITHUB_TEST_ISSUE_URL",
        "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA",
    ):
        monkeypatch.delenv(name, raising=False)

    report = build_owner_gate_plan(external_smoke_path=tmp_path / "missing.json")

    assert report.status == "action_required"
    assert _gate(report, "provider").status == "action_required"
    assert _gate(report, "hosted_github_actions_commercial_rc").status == "action_required"
    assert any("rc_external_smoke.py" in command for command in report.next_commands)
    owner_runner_command = next(command for command in report.next_commands if "rc_owner_gate_runner.py --gate all" in command)
    assert "--env-file .xagent_runtime\\reports\\rc-owner-env-template.env" in owner_runner_command
    combined_external_smoke = next(command for command in report.next_commands if "rc_external_smoke.py --provider" in command)
    assert "--telegram-live-preflight" not in combined_external_smoke
    assert "--check provider" in combined_external_smoke
    assert "--check feishu_webhook_contract" in combined_external_smoke
    assert "--check github_issue_to_pr_dry_run" in combined_external_smoke
    assert "--check github_issue_to_pr_execute_preflight" in combined_external_smoke
    assert "--check hosted_github_actions_run" in combined_external_smoke
    assert "--github-execute-preflight" in combined_external_smoke
    assert "--github-actions-preflight" in combined_external_smoke
    trigger_index = next(
        index for index, command in enumerate(report.next_commands) if "Trigger the hosted Commercial RC Gate workflow" in command
    )
    run_url_index = next(
        index for index, command in enumerate(report.next_commands) if "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL" in command
    )
    head_sha_index = next(
        index for index, command in enumerate(report.next_commands) if "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA" in command
    )
    runner_index = next(index for index, command in enumerate(report.next_commands) if "rc_owner_gate_runner.py" in command)
    smoke_index = next(index for index, command in enumerate(report.next_commands) if "rc_external_smoke.py" in command)
    assert trigger_index < run_url_index < head_sha_index < runner_index < smoke_index


def test_owner_gate_plan_single_gate_commands_are_scoped(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_LLM_BACKEND", "ollama")

    report = build_owner_gate_plan(external_smoke_path=tmp_path / "missing.json")

    provider_command = _gate(report, "provider").command
    feishu_command = _gate(report, "feishu_webhook_contract").command
    github_dry_run_command = _gate(report, "github_issue_to_pr_dry_run").command
    provider_gate = _gate(report, "provider")
    assert provider_command == (
        "python scripts\\rc_external_smoke.py --check provider --provider ollama --require-configured"
    )
    assert "--github-execute-preflight" not in provider_command
    assert "--check provider" in provider_command
    assert ["XAGENT_OLLAMA_MODEL", "OLLAMA_MODEL"] in provider_gate.required_env_groups
    assert ["XAGENT_OLLAMA_BASE_URL", "OLLAMA_BASE_URL"] in provider_gate.required_env_groups
    assert any("ollama run <model>" in item for item in provider_gate.notes)
    assert any('Reply with exactly: xagent-rc-ok' in item for item in provider_gate.notes)
    assert any("ASCII-only local directory" in item for item in provider_gate.notes)
    assert any("ollama run <model>" in item for item in provider_gate.completion_criteria)
    assert any("ASCII-only local path" in item for item in provider_gate.completion_criteria)
    assert feishu_command == "python scripts\\rc_external_smoke.py --check feishu_webhook_contract --require-configured"
    assert "--telegram-live-preflight" not in feishu_command
    assert "--github-execute-preflight" not in feishu_command
    assert github_dry_run_command == (
        "python scripts\\rc_external_smoke.py --check github_issue_to_pr_dry_run --require-configured"
    )
    assert "--github-execute-preflight" not in github_dry_run_command


def test_owner_gate_plan_is_ready_when_required_env_exists(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_LLM_BACKEND", "openai")
    monkeypatch.setenv("XAGENT_OPENAI_API_KEY", "sk-test-value")
    monkeypatch.setenv("XAGENT_FEISHU_APP_ID", "cli_a_test")
    monkeypatch.setenv("XAGENT_FEISHU_APP_SECRET", "app-secret")
    monkeypatch.setenv("XAGENT_FEISHU_ENCRYPT_KEY", "encrypt-key")
    monkeypatch.setenv("XAGENT_GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("XAGENT_GITHUB_TEST_ISSUE_URL", "https://github.com/acme/project/issues/42")

    report = build_owner_gate_plan(external_smoke_path=tmp_path / "missing.json")

    assert _gate(report, "provider").status == "ready_to_run"
    assert _gate(report, "feishu_webhook_contract").status == "ready_to_run"
    assert _gate(report, "github_issue_to_pr_execute_preflight").status == "ready_to_run"
    assert "sk-test-value" not in json.dumps(report.to_dict())
    assert "ghp_test" not in json.dumps(report.to_dict())


def test_owner_gate_plan_documents_github_execute_permission_probe(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("XAGENT_GITHUB_TEST_ISSUE_URL", "https://github.com/acme/project/issues/42")

    report = build_owner_gate_plan(external_smoke_path=tmp_path / "missing.json")

    gate = _gate(report, "github_issue_to_pr_execute_preflight")
    assert any("permissions.push=true" in item for item in gate.completion_criteria)


def test_owner_gate_plan_uses_external_smoke_passed_checks(tmp_path: Path, monkeypatch) -> None:
    external = _write_external(
        tmp_path / "rc-external-smoke.json",
        [
            _provider_passed_check(),
            _feishu_webhook_passed_check(),
            _github_dry_run_passed_check(),
            _github_execute_passed_check(),
        ],
    )
    monkeypatch.delenv("XAGENT_LLM_BACKEND", raising=False)

    report = build_owner_gate_plan(external_smoke_path=external)

    assert _gate(report, "provider").status == "verified"
    assert _gate(report, "github_issue_to_pr_execute_preflight").status == "verified"
    assert _gate(report, "hosted_github_actions_commercial_rc").status == "action_required"


def test_owner_gate_plan_rejects_weak_provider_evidence(tmp_path: Path, monkeypatch) -> None:
    external = _write_external(
        tmp_path / "rc-external-smoke.json",
        [{"name": "provider", "status": "passed"}],
    )

    report = build_owner_gate_plan(external_smoke_path=external)

    gate = _gate(report, "provider")
    assert gate.status == "action_required"
    assert any("sentinel_matched=true" in item for item in gate.missing)


def test_owner_gate_plan_propagates_provider_smoke_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_LLM_BACKEND", "ollama")
    external = _write_external(
        tmp_path / "rc-external-smoke.json",
        [
            {
                "name": "provider",
                "status": "skipped",
                "missing": ["Reinstall or move the selected model."],
                "error": "HTTP Error 500: Internal Server Error",
            }
        ],
    )

    report = build_owner_gate_plan(external_smoke_path=external)

    gate = _gate(report, "provider")
    assert gate.status == "action_required"
    assert "Reinstall or move the selected model." in gate.missing
    assert any("HTTP Error 500" in item for item in gate.missing)


def test_owner_gate_plan_rejects_weak_feishu_evidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_FEISHU_APP_ID", "cli_a_test")
    monkeypatch.setenv("XAGENT_FEISHU_APP_SECRET", "app-secret")
    monkeypatch.setenv("XAGENT_FEISHU_ENCRYPT_KEY", "encrypt-key")
    external = _write_external(
        tmp_path / "rc-external-smoke.json",
        [{"name": "feishu_webhook_contract", "status": "passed"}],
    )

    report = build_owner_gate_plan(external_smoke_path=external)

    gate = _gate(report, "feishu_webhook_contract")
    assert gate.status == "action_required"
    assert any("valid_signature_accepted=true" in item for item in gate.missing)
    assert any("invalid_signature_rejected=true" in item for item in gate.missing)
    assert any("mutation_performed=false" in item for item in gate.missing)


def test_owner_gate_plan_rejects_weak_github_dry_run_evidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_GITHUB_TEST_ISSUE_URL", "https://github.com/acme/project/issues/42")
    external = _write_external(
        tmp_path / "rc-external-smoke.json",
        [{"name": "github_issue_to_pr_dry_run", "status": "passed"}],
    )

    report = build_owner_gate_plan(external_smoke_path=external)

    gate = _gate(report, "github_issue_to_pr_dry_run")
    assert gate.status == "action_required"
    assert any("execute_allowed=false" in item for item in gate.missing)


def test_owner_gate_plan_rejects_weak_github_execute_evidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("XAGENT_GITHUB_TEST_ISSUE_URL", "https://github.com/acme/project/issues/42")
    external = _write_external(
        tmp_path / "rc-external-smoke.json",
        [{"name": "github_issue_to_pr_execute_preflight", "status": "passed"}],
    )

    report = build_owner_gate_plan(external_smoke_path=external)

    gate = _gate(report, "github_issue_to_pr_execute_preflight")
    assert gate.status == "action_required"
    assert any("permission_probe.permissions.push=true" in item for item in gate.missing)


def test_owner_gate_plan_rejects_overbroad_github_execute_evidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("XAGENT_GITHUB_TEST_ISSUE_URL", "https://github.com/acme/project/issues/42")
    external = _write_external(
        tmp_path / "rc-external-smoke.json",
        [
            {
                "name": "github_issue_to_pr_execute_preflight",
                "status": "passed",
                "details": {
                    "dry_run_status": "passed",
                    "read_probe": {"status": "passed", "state": "open"},
                    "permission_probe": {
                        "status": "passed",
                        "permissions": {"push": True},
                        "least_privilege": False,
                        "overbroad_permissions": ["admin"],
                    },
                    "mutation_performed": False,
                },
            }
        ],
    )

    report = build_owner_gate_plan(external_smoke_path=external)

    gate = _gate(report, "github_issue_to_pr_execute_preflight")
    assert gate.status == "action_required"
    assert any("least_privilege=true" in item for item in gate.missing)


def test_owner_gate_plan_accepts_github_owner_context_permissions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("XAGENT_GITHUB_TEST_ISSUE_URL", "https://github.com/acme/project/issues/42")
    external = _write_external(
        tmp_path / "rc-external-smoke.json",
        [
            {
                "name": "github_issue_to_pr_execute_preflight",
                "status": "passed",
                "details": {
                    "dry_run_status": "passed",
                    "read_probe": {"status": "passed", "state": "open"},
                    "permission_probe": {
                        "status": "passed",
                        "permissions": {"push": True, "admin": True, "maintain": True},
                        "least_privilege": True,
                        "owner_context_permissions": ["admin", "maintain"],
                    },
                    "mutation_performed": False,
                },
            }
        ],
    )

    report = build_owner_gate_plan(external_smoke_path=external)

    gate = _gate(report, "github_issue_to_pr_execute_preflight")
    assert gate.status == "verified"


def test_owner_gate_plan_rejects_closed_github_execute_issue_evidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("XAGENT_GITHUB_TEST_ISSUE_URL", "https://github.com/acme/project/issues/42")
    external = _write_external(
        tmp_path / "rc-external-smoke.json",
        [
            {
                "name": "github_issue_to_pr_execute_preflight",
                "status": "passed",
                "details": {
                    "dry_run_status": "passed",
                    "read_probe": {"status": "passed", "state": "closed"},
                    "permission_probe": {
                        "status": "passed",
                        "permissions": {"push": True},
                        "least_privilege": True,
                        "owner_context_permissions": [],
                    },
                    "mutation_performed": False,
                },
            }
        ],
    )

    report = build_owner_gate_plan(external_smoke_path=external)

    gate = _gate(report, "github_issue_to_pr_execute_preflight")
    assert gate.status == "action_required"
    assert any("read_probe.state=open" in item for item in gate.missing)


def test_owner_gate_plan_verifies_feishu_webhook_contract(tmp_path: Path, monkeypatch) -> None:
    external = _write_external(
        tmp_path / "rc-external-smoke.json",
        [_feishu_webhook_passed_check()],
    )
    monkeypatch.setenv("XAGENT_FEISHU_APP_ID", "cli_a_test")
    monkeypatch.setenv("XAGENT_FEISHU_APP_SECRET", "app-secret")
    monkeypatch.setenv("XAGENT_FEISHU_ENCRYPT_KEY", "encrypt-key")

    report = build_owner_gate_plan(external_smoke_path=external)

    gate = _gate(report, "feishu_webhook_contract")
    assert gate.status == "verified"
    assert any("feishu_webhook_contract" in item for item in gate.evidence)


def test_owner_gate_plan_requires_hosted_ci_run_probe_when_run_url_recorded(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL", "https://github.com/acme/x/actions/runs/1")
    monkeypatch.setenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA", EXPECTED_HEAD_SHA)

    report = build_owner_gate_plan(external_smoke_path=tmp_path / "missing.json")

    gate = _gate(report, "hosted_github_actions_commercial_rc")
    assert gate.status == "action_required"
    assert "github-actions-preflight" in gate.missing[0]
    assert "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL" in gate.configured_env
    assert "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA" in gate.configured_env


def test_owner_gate_plan_requires_hosted_ci_head_sha_when_run_url_recorded(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL", "https://github.com/acme/x/actions/runs/1")
    monkeypatch.delenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA", raising=False)

    report = build_owner_gate_plan(external_smoke_path=tmp_path / "missing.json")

    gate = _gate(report, "hosted_github_actions_commercial_rc")
    assert gate.status == "action_required"
    assert any("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA" in item for item in gate.missing)


def test_owner_gate_plan_rejects_invalid_hosted_ci_head_sha_format(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL", "https://github.com/acme/x/actions/runs/1")
    monkeypatch.setenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA", "main")

    report = build_owner_gate_plan(external_smoke_path=tmp_path / "missing.json")

    gate = _gate(report, "hosted_github_actions_commercial_rc")
    assert gate.status == "action_required"
    assert any("40-character hex git commit SHA" in item for item in gate.missing)
    assert not any("github-actions-preflight" in item for item in gate.missing)


def test_owner_gate_plan_verifies_hosted_ci_when_run_probe_passed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL", "https://github.com/acme/x/actions/runs/1")
    monkeypatch.setenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA", EXPECTED_HEAD_SHA)
    monkeypatch.setenv("XAGENT_GITHUB_TOKEN", "ghp_test")
    external = _write_external(
        tmp_path / "rc-external-smoke.json",
        [_hosted_actions_passed_check()],
    )

    report = build_owner_gate_plan(external_smoke_path=external)

    gate = _gate(report, "hosted_github_actions_commercial_rc")
    assert gate.status == "verified"
    assert gate.missing == []


def test_owner_gate_plan_rejects_weak_hosted_ci_evidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL", "https://github.com/acme/x/actions/runs/1")
    monkeypatch.setenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA", EXPECTED_HEAD_SHA)
    monkeypatch.setenv("XAGENT_GITHUB_TOKEN", "ghp_test")
    external = _write_external(
        tmp_path / "rc-external-smoke.json",
        [{"name": "hosted_github_actions_run", "status": "passed"}],
    )

    report = build_owner_gate_plan(external_smoke_path=external)

    gate = _gate(report, "hosted_github_actions_commercial_rc")
    assert gate.status == "action_required"
    assert any("head_sha_verified=true" in item for item in gate.missing)
    assert any("jobs_verified=true" in item for item in gate.missing)
    assert any("artifact_verified=true" in item for item in gate.missing)


def test_owner_gate_plan_rejects_run_only_hosted_ci_evidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL", "https://github.com/acme/x/actions/runs/1")
    monkeypatch.setenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA", EXPECTED_HEAD_SHA)
    monkeypatch.setenv("XAGENT_GITHUB_TOKEN", "ghp_test")
    external = _write_external(
        tmp_path / "rc-external-smoke.json",
        [
            {
                "name": "hosted_github_actions_run",
                "status": "passed",
                "details": {
                    "run_url": "https://github.com/acme/x/actions/runs/1",
                    "run_status": "completed",
                    "conclusion": "success",
                    "mutation_performed": False,
                },
            }
        ],
    )

    report = build_owner_gate_plan(external_smoke_path=external)

    gate = _gate(report, "hosted_github_actions_commercial_rc")
    assert gate.status == "action_required"
    assert any("workflow_verified=true" in item for item in gate.missing)
    assert any("head_sha_verified=true" in item for item in gate.missing)
    assert any("jobs_verified=true" in item for item in gate.missing)


def test_owner_gate_plan_rejects_hosted_ci_evidence_with_invalid_sha_shape(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL", "https://github.com/acme/x/actions/runs/1")
    monkeypatch.setenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA", EXPECTED_HEAD_SHA)
    monkeypatch.setenv("XAGENT_GITHUB_TOKEN", "ghp_test")
    passed = _hosted_actions_passed_check()
    assert isinstance(passed["details"], dict)
    passed["details"]["expected_head_sha"] = "short"
    passed["details"]["head_sha"] = "short"
    passed["details"]["head_sha_verified"] = True
    external = _write_external(tmp_path / "rc-external-smoke.json", [passed])

    report = build_owner_gate_plan(external_smoke_path=external)

    gate = _gate(report, "hosted_github_actions_commercial_rc")
    assert gate.status == "action_required"
    assert any("head_sha_verified=true" in item for item in gate.missing)


def test_owner_gate_plan_rejects_invalid_hosted_ci_run_url(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL", "not-a-run-url")

    report = build_owner_gate_plan(external_smoke_path=tmp_path / "missing.json")

    gate = _gate(report, "hosted_github_actions_commercial_rc")
    assert gate.status == "action_required"
    assert "valid GitHub Actions run URL" in gate.missing[0]


def test_owner_gate_plan_downgrades_verified_gates_when_external_evidence_is_stale(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL", "https://github.com/acme/x/actions/runs/1")
    monkeypatch.setenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA", EXPECTED_HEAD_SHA)
    monkeypatch.setenv("XAGENT_GITHUB_TOKEN", "ghp_test")
    external = _write_external(
        tmp_path / "reports" / "rc-external-smoke.json",
        [
            _provider_passed_check(),
            _feishu_webhook_passed_check(),
            _github_dry_run_passed_check(),
            _github_execute_passed_check(),
            _hosted_actions_passed_check(),
        ],
    )
    source_bundle = _write_source_bundle(tmp_path / "reports" / "rc-source-bundle.json", "2026-06-05T11:00:00Z")

    report = build_owner_gate_plan(external_smoke_path=external, source_bundle_path=source_bundle)

    assert report.status == "action_required"
    assert report.evidence_freshness["fresh"] is False
    assert all(gate.status == "action_required" for gate in report.gates)
    assert all("external smoke evidence is older" in gate.missing[0] for gate in report.gates)


def test_owner_gate_plan_keeps_verified_gates_when_external_evidence_is_fresh(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL", "https://github.com/acme/x/actions/runs/1")
    monkeypatch.setenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA", EXPECTED_HEAD_SHA)
    monkeypatch.setenv("XAGENT_GITHUB_TOKEN", "ghp_test")
    external = _write_external(
        tmp_path / "reports" / "rc-external-smoke.json",
        [
            _provider_passed_check(),
            _feishu_webhook_passed_check(),
            _github_dry_run_passed_check(),
            _github_execute_passed_check(),
            _hosted_actions_passed_check(),
        ],
    )
    source_bundle = _write_source_bundle(tmp_path / "reports" / "rc-source-bundle.json", "2026-06-05T09:00:00Z")

    report = build_owner_gate_plan(external_smoke_path=external, source_bundle_path=source_bundle)

    assert report.status == "verified"
    assert report.evidence_freshness["fresh"] is True
    assert all(gate.status == "verified" for gate in report.gates)


def test_owner_gate_plan_reports_repo_relative_handoff_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(rc_owner_gate_plan, "ROOT", tmp_path)
    external = _write_external(
        tmp_path / ".xagent_runtime" / "reports" / "rc-external-smoke.json",
        [_provider_passed_check()],
    )
    source_bundle = _write_source_bundle(
        tmp_path / ".xagent_runtime" / "reports" / "rc-source-bundle.json",
        "2026-06-05T09:00:00Z",
    )

    report = build_owner_gate_plan(external_smoke_path=external, source_bundle_path=source_bundle)
    payload = report.to_dict()
    text = json.dumps(payload, ensure_ascii=False)

    assert payload["external_smoke_report"] == ".xagent_runtime/reports/rc-external-smoke.json"
    assert payload["source_bundle_report"] == ".xagent_runtime/reports/rc-source-bundle.json"
    assert str(tmp_path) not in text
    assert "/" + "/".join(["home", "runner"]) + "/" not in text
    assert "\\Users\\" not in text
