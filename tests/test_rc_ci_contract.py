from __future__ import annotations

from pathlib import Path

from scripts.rc_ci_contract import DEFAULT_WORKFLOW, run_contract


def _copy_workflow(tmp_path: Path) -> Path:
    workflow = tmp_path / "commercial-rc.yml"
    workflow.write_text(DEFAULT_WORKFLOW.read_text(encoding="utf-8"), encoding="utf-8")
    return workflow


def test_ci_contract_accepts_current_workflow() -> None:
    report = run_contract()

    assert report.status == "passed"
    assert report.findings == []
    assert report.requirements_checked >= 1


def test_ci_contract_fails_when_required_step_is_missing(tmp_path: Path) -> None:
    workflow = _copy_workflow(tmp_path)
    workflow.write_text(workflow.read_text(encoding="utf-8").replace("npm run build", ""), encoding="utf-8")

    report = run_contract(workflow)

    assert report.status == "failed"
    assert any(finding.id == "frontend_audit_typecheck_build" for finding in report.findings)


def test_ci_contract_requires_minimum_workflow_permissions(tmp_path: Path) -> None:
    workflow = _copy_workflow(tmp_path)
    workflow.write_text(
        workflow.read_text(encoding="utf-8").replace("\npermissions:\n  contents: read\n", "\n"),
        encoding="utf-8",
    )

    report = run_contract(workflow)

    assert report.status == "failed"
    assert any(finding.id == "minimum_workflow_permissions" for finding in report.findings)


def test_ci_contract_rejects_git_add_dot(tmp_path: Path) -> None:
    workflow = _copy_workflow(tmp_path)
    workflow.write_text(workflow.read_text(encoding="utf-8") + "\n          git add .\n", encoding="utf-8")

    report = run_contract(workflow)

    assert report.status == "failed"
    assert any(finding.id == "no_git_add_dot" for finding in report.findings)


def test_ci_contract_rejects_ready_to_tag_requirement_in_normal_ci(tmp_path: Path) -> None:
    workflow = _copy_workflow(tmp_path)
    workflow.write_text(
        workflow.read_text(encoding="utf-8") + "\n          python scripts/rc_final_gate.py --require-ready-to-tag\n",
        encoding="utf-8",
    )

    report = run_contract(workflow)

    assert report.status == "failed"
    assert any(finding.id == "no_ready_to_tag_requirement" for finding in report.findings)


def test_ci_contract_requires_strict_owner_external_gate_tokens(tmp_path: Path) -> None:
    workflow = _copy_workflow(tmp_path)
    workflow.write_text(workflow.read_text(encoding="utf-8").replace('"--github-actions-preflight",', ""), encoding="utf-8")

    report = run_contract(workflow)

    assert report.status == "failed"
    assert any(finding.id == "owner_external_gate_command_contract" for finding in report.findings)


def test_ci_contract_requires_hosted_actions_head_sha_handoff_token(tmp_path: Path) -> None:
    workflow = _copy_workflow(tmp_path)
    workflow.write_text(
        workflow.read_text(encoding="utf-8").replace(
            '"XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA",',
            "",
        ),
        encoding="utf-8",
    )

    report = run_contract(workflow)

    assert report.status == "failed"
    assert any(finding.id == "owner_external_gate_command_contract" for finding in report.findings)


def test_ci_contract_requires_refresh_chain_execution_not_only_uploaded_report(tmp_path: Path) -> None:
    workflow = _copy_workflow(tmp_path)
    text = workflow.read_text(encoding="utf-8")
    workflow.write_text(
        text.replace(
            "python scripts/rc_refresh_release_chain.py --provider mock",
            "# upload still includes .xagent_runtime/reports/rc-supply-chain-gate.json",
        ),
        encoding="utf-8",
    )

    report = run_contract(workflow)

    assert report.status == "failed"
    assert any(finding.id == "release_gate_commands" for finding in report.findings)


def test_ci_contract_requires_route_auth_audit_gate(tmp_path: Path) -> None:
    workflow = _copy_workflow(tmp_path)
    workflow.write_text(
        workflow.read_text(encoding="utf-8").replace(
            "python scripts/route_auth_audit.py --json > .xagent_runtime/reports/route-auth-audit.json",
            "",
        ),
        encoding="utf-8",
    )

    report = run_contract(workflow)

    assert report.status == "failed"
    assert any(finding.id == "release_gate_commands" for finding in report.findings)


def test_ci_contract_requires_deployment_hardening_gate(tmp_path: Path) -> None:
    workflow = _copy_workflow(tmp_path)
    workflow.write_text(
        workflow.read_text(encoding="utf-8").replace("python scripts/security_deployment_gate.py", ""),
        encoding="utf-8",
    )

    report = run_contract(workflow)

    assert report.status == "failed"
    assert any(finding.id == "release_gate_commands" for finding in report.findings)


def test_ci_contract_requires_production_hardening_gate(tmp_path: Path) -> None:
    workflow = _copy_workflow(tmp_path)
    workflow.write_text(
        workflow.read_text(encoding="utf-8").replace("python scripts/production_hardening_gate.py", ""),
        encoding="utf-8",
    )

    report = run_contract(workflow)

    assert report.status == "failed"
    assert any(finding.id == "release_gate_commands" for finding in report.findings)


def test_ci_contract_rejects_fail_open_security_gates(tmp_path: Path) -> None:
    workflow = _copy_workflow(tmp_path)
    text = workflow.read_text(encoding="utf-8")
    workflow.write_text(
        text.replace("python scripts/security_deployment_gate.py", "python scripts/security_deployment_gate.py || true"),
        encoding="utf-8",
    )

    report = run_contract(workflow)

    assert report.status == "failed"
    assert any(finding.id == "no_security_deployment_gate_fail_open" for finding in report.findings)


def test_ci_contract_rejects_allow_blocked_production_gate(tmp_path: Path) -> None:
    workflow = _copy_workflow(tmp_path)
    text = workflow.read_text(encoding="utf-8")
    workflow.write_text(
        text.replace("python scripts/production_hardening_gate.py", "python scripts/production_hardening_gate.py --allow-blocked"),
        encoding="utf-8",
    )

    report = run_contract(workflow)

    assert report.status == "failed"
    assert any(finding.id == "no_production_hardening_gate_allow_blocked" for finding in report.findings)


def test_ci_contract_ignores_required_tokens_in_comments(tmp_path: Path) -> None:
    workflow = _copy_workflow(tmp_path)
    text = workflow.read_text(encoding="utf-8")
    workflow.write_text(
        text.replace("npm run build", "# npm run build"),
        encoding="utf-8",
    )

    report = run_contract(workflow)

    assert report.status == "failed"
    assert any(finding.id == "frontend_audit_typecheck_build" for finding in report.findings)


def test_ci_contract_ignores_forbidden_tokens_in_comments(tmp_path: Path) -> None:
    workflow = _copy_workflow(tmp_path)
    workflow.write_text(workflow.read_text(encoding="utf-8") + "\n          # git add .\n", encoding="utf-8")

    report = run_contract(workflow)

    assert report.status == "passed"
    assert not any(finding.id == "no_git_add_dot" for finding in report.findings)
