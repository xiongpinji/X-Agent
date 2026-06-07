#!/usr/bin/env python3
"""Validate the commercial RC GitHub Actions workflow contract.

This checker is intentionally text based: it does not try to replace a hosted
GitHub Actions run. It catches local workflow drift before the owner spends
time on external CI gates.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKFLOW = ROOT / ".github" / "workflows" / "commercial-rc.yml"
DEFAULT_OUTPUT = ROOT / ".xagent_runtime" / "reports" / "rc-ci-contract.json"


@dataclass(frozen=True)
class Requirement:
    id: str
    description: str
    tokens: tuple[str, ...]


@dataclass(frozen=True)
class ForbiddenPattern:
    id: str
    description: str
    token: str


@dataclass(frozen=True)
class ContractFinding:
    id: str
    description: str
    kind: str
    missing_tokens: list[str] = field(default_factory=list)
    matched_token: str | None = None


@dataclass(frozen=True)
class CiContractReport:
    status: str
    generated_at: str
    workflow_path: str
    requirements_checked: int
    forbidden_patterns_checked: int
    findings: list[ContractFinding]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["findings"] = [asdict(finding) for finding in self.findings]
        return payload


REQUIRED_CONTAINS: tuple[Requirement, ...] = (
    Requirement(
        id="minimum_workflow_permissions",
        description="Workflow restricts the default GITHUB_TOKEN permissions to read-only repository contents.",
        tokens=("\npermissions:\n  contents: read", "fetch-depth: 0"),
    ),
    Requirement(
        id="linux_rc_job",
        description="Linux commercial RC verification job is present.",
        tokens=("commercial-rc-linux:", "name: commercial-rc-linux", "runs-on: ubuntu-latest"),
    ),
    Requirement(
        id="windows_installer_job",
        description="Windows installer dry-run job is present.",
        tokens=("commercial-rc-windows-installer:", "name: commercial-rc-windows-installer", "runs-on: windows-latest"),
    ),
    Requirement(
        id="runtime_versions",
        description="Workflow pins Python 3.11 and Node 20 setup.",
        tokens=('PYTHON_VERSION: "3.11"', 'NODE_VERSION: "20"', "actions/setup-python@v5", "actions/setup-node@v4"),
    ),
    Requirement(
        id="backend_install",
        description="Backend editable dev/CLI install and Python vulnerability-audit tool check are present.",
        tokens=('python -m pip install -e ".[dev,cli]"', "python -m pip show pip-audit"),
    ),
    Requirement(
        id="frontend_install",
        description="Frontend lockfile install is present.",
        tokens=("working-directory: frontend", "npm ci"),
    ),
    Requirement(
        id="frontend_audit_typecheck_build",
        description="Frontend audit, type-check, and build gates are present.",
        tokens=("npm audit --audit-level=moderate", "npm run type-check", "npm run build"),
    ),
    Requirement(
        id="static_release_checks",
        description="Static release checks include whitespace and RC script compilation.",
        tokens=(
            "git diff --check",
            "python -m py_compile",
            "scripts/codex_hermes_gap_matrix.py",
            "scripts/xagent_doctor.py",
            "scripts/rc_runtime_smoke.py",
            "scripts/rc_external_smoke.py",
            "scripts/rc_release_audit.py",
            "scripts/rc_release_diff_review_gate.py",
            "scripts/rc_deployment_docs_gate.py",
            "scripts/rc_ci_contract.py",
            "scripts/rc_evidence_pack.py",
            "scripts/rc_refresh_release_chain.py",
            "scripts/rc_owner_gate_plan.py",
            "scripts/rc_owner_gate_runner.py",
            "scripts/rc_owner_handoff_gate.py",
            "scripts/rc_owner_gate_checklist.py",
            "scripts/rc_owner_env_template.py",
            "scripts/rc_owner_verified_finalize.py",
            "scripts/rc_tag_consistency_gate.py",
            "scripts/rc_delivery_status.py",
            "scripts/rc_install_release_gate.py",
            "scripts/rc_supply_chain_gate.py",
            "scripts/rc_secrets_gate.py",
            "scripts/rc_artifact_integrity_gate.py",
            "scripts/rc_final_gate.py",
            "scripts/rc_release_receipt.py",
            "scripts/rc_source_bundle.py",
            "scripts/rc_staging_plan.py",
        ),
    ),
    Requirement(
        id="targeted_rc_pytest_group",
        description="Targeted RC pytest group includes all local release-gate tests.",
        tokens=(
            "tests/test_rc_runtime_smoke.py",
            "tests/test_rc_external_smoke.py",
            "tests/test_docker_compose_env_contract.py",
            "tests/test_rc_release_audit.py",
            "tests/test_rc_release_diff_review_gate.py",
            "tests/test_rc_deployment_docs_gate.py",
            "tests/test_rc_ci_contract.py",
            "tests/test_rc_evidence_pack.py",
            "tests/test_rc_refresh_release_chain.py",
            "tests/test_rc_owner_gate_plan.py",
            "tests/test_rc_owner_gate_runner.py",
            "tests/test_rc_owner_handoff_gate.py",
            "tests/test_rc_owner_gate_checklist.py",
            "tests/test_rc_owner_env_template.py",
            "tests/test_rc_owner_verified_finalize.py",
            "tests/test_rc_tag_consistency_gate.py",
            "tests/test_rc_delivery_status.py",
            "tests/test_rc_install_release_gate.py",
            "tests/test_rc_supply_chain_gate.py",
            "tests/test_rc_secrets_gate.py",
            "tests/test_rc_artifact_integrity_gate.py",
            "tests/test_rc_final_gate.py",
            "tests/test_rc_release_receipt.py",
            "tests/test_rc_source_bundle.py",
            "tests/test_rc_staging_plan.py",
        ),
    ),
    Requirement(
        id="release_gate_commands",
        description="Workflow runs every commercial RC local gate command.",
        tokens=(
            "python scripts/rc_refresh_release_chain.py --provider mock",
            "python scripts/codex_hermes_gap_matrix.py --write-report",
            "python scripts/rc_release_audit.py",
            "python scripts/rc_tag_consistency_gate.py",
            "python scripts/rc_delivery_status.py",
            "--tag-name x-agent-commercial-rc-20260608-ci-snapshot",
            "python scripts/rc_runtime_smoke.py",
            "python scripts/rc_ci_contract.py",
        ),
    ),
    Requirement(
        id="owner_external_gate_command_contract",
        description="Workflow verifies owner handoff commands keep strict env-file and external-preflight tokens.",
        tokens=(
            "Owner gate handoff command contract",
            ".xagent_runtime/reports/rc-owner-gate-plan.json",
            ".xagent_runtime/reports/rc-owner-gate-checklist.json",
            "Trigger the hosted Commercial RC Gate workflow",
            "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL",
            "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA",
            "rc_owner_gate_runner.py --gate all",
            "--env-file",
            "rc_external_smoke.py",
            "--require-configured",
            "feishu_webhook_contract",
            "--github-execute-preflight",
            "--github-actions-preflight",
        ),
    ),
    Requirement(
        id="artifact_upload",
        description="Workflow uploads all commercial RC evidence reports and logs.",
        tokens=(
            ".xagent_runtime/reports/codex-hermes-gap-closure.json",
            ".xagent_runtime/reports/rc-external-smoke.json",
            ".xagent_runtime/reports/rc-ci-contract.json",
            ".xagent_runtime/reports/rc-release-diff-review-gate.json",
            ".xagent_runtime/reports/rc-deployment-docs-gate.json",
            ".xagent_runtime/reports/rc-evidence-pack.json",
            ".xagent_runtime/reports/rc-refresh-release-chain.json",
            ".xagent_runtime/reports/rc-owner-gate-plan.json",
            ".xagent_runtime/reports/rc-owner-gate-runner.json",
            ".xagent_runtime/reports/rc-owner-handoff-gate.json",
            ".xagent_runtime/reports/rc-owner-gate-checklist.json",
            ".xagent_runtime/reports/rc-owner-gate-checklist.md",
            ".xagent_runtime/reports/rc-owner-env-template.json",
            ".xagent_runtime/reports/rc-owner-env-template.env",
            ".xagent_runtime/reports/rc-owner-env-template.ps1",
            ".xagent_runtime/reports/rc-owner-verified-finalize.json",
            ".xagent_runtime/reports/rc-tag-consistency-gate.json",
            ".xagent_runtime/reports/rc-delivery-status.json",
            ".xagent_runtime/reports/rc-install-release-gate.json",
            ".xagent_runtime/reports/rc-supply-chain-gate.json",
            ".xagent_runtime/reports/rc-secrets-gate.json",
            ".xagent_runtime/reports/rc-artifact-integrity-gate.json",
            ".xagent_runtime/reports/rc-final-gate.json",
            ".xagent_runtime/reports/rc-release-audit.json",
            ".xagent_runtime/reports/rc-source-bundle.json",
            ".xagent_runtime/reports/rc-staging-plan.json",
            ".xagent_runtime/release/x-agent-commercial-rc-receipt.json",
            ".xagent_runtime/release/*.zip",
            ".xagent_runtime/release/x-agent-commercial-rc-evidence-*.zip",
            ".xagent_runtime/release/*.zip.sha256",
            ".xagent_runtime/smoke/rc-runtime-smoke.json",
            ".xagent_runtime/smoke/rc-*.log",
        ),
    ),
)

FORBIDDEN_CONTAINS: tuple[ForbiddenPattern, ...] = (
    ForbiddenPattern(
        id="no_git_add_dot",
        description="Workflow must not stage broad worktree contents.",
        token="git add .",
    ),
    ForbiddenPattern(
        id="no_git_add_all",
        description="Workflow must not stage broad worktree contents.",
        token="git add -A",
    ),
    ForbiddenPattern(
        id="no_ready_to_tag_requirement",
        description="Normal commercial RC CI must not require owner-controlled gates to be complete.",
        token="rc_final_gate.py --require-ready-to-tag",
    ),
)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_workflow_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\\", "/")
    return "\n".join(_strip_yaml_comment(line) for line in normalized.splitlines())


def _strip_yaml_comment(line: str) -> str:
    in_single = False
    in_double = False
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\" and in_double:
            escaped = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            continue
        if char == "#" and not in_single and not in_double:
            if index == 0 or line[index - 1].isspace():
                return line[:index].rstrip()
    return line


def run_contract(workflow_path: Path = DEFAULT_WORKFLOW) -> CiContractReport:
    findings: list[ContractFinding] = []
    try:
        text = _normalize_workflow_text(workflow_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        findings.append(
            ContractFinding(
                id="workflow_missing",
                description="Commercial RC GitHub Actions workflow file is missing.",
                kind="required",
                missing_tokens=[str(workflow_path)],
            )
        )
        text = ""

    for requirement in REQUIRED_CONTAINS:
        missing = [token for token in requirement.tokens if token not in text]
        if missing:
            findings.append(
                ContractFinding(
                    id=requirement.id,
                    description=requirement.description,
                    kind="required",
                    missing_tokens=missing,
                )
            )

    for forbidden in FORBIDDEN_CONTAINS:
        if forbidden.token in text:
            findings.append(
                ContractFinding(
                    id=forbidden.id,
                    description=forbidden.description,
                    kind="forbidden",
                    matched_token=forbidden.token,
                )
            )

    return CiContractReport(
        status="passed" if not findings else "failed",
        generated_at=_utc_now(),
        workflow_path=str(workflow_path),
        requirements_checked=len(REQUIRED_CONTAINS),
        forbidden_patterns_checked=len(FORBIDDEN_CONTAINS),
        findings=findings,
    )


def write_report(report: CiContractReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the commercial RC GitHub Actions workflow contract")
    parser.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_contract(args.workflow)
    write_report(report, args.output)
    print(f"RC CI contract status: {report.status}")
    print(f"Workflow: {report.workflow_path}")
    print(f"Requirements checked: {report.requirements_checked}")
    print(f"Report written to {args.output}")
    if report.findings:
        print("Findings:")
        for finding in report.findings:
            detail = ", ".join(finding.missing_tokens) if finding.missing_tokens else finding.matched_token or ""
            print(f"- {finding.id}: {detail}")
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
