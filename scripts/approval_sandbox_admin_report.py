#!/usr/bin/env python3
"""Build a read-only approval, sandbox, and enterprise-admin contract report."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from backend.app.core.approvals import (
    APPROVAL_SUBJECT_ACTIONS,
    ApprovalDecisionType,
    ApprovalSubjectType,
)
from backend.app.core.sandbox.security import list_enterprise_safety_policies
from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, _utc_now

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPORT_DIR / "approval-sandbox-admin-report.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "approval-sandbox-admin-report.md"

GOVERNED_SUBJECTS = (
    ApprovalSubjectType.COMMAND,
    ApprovalSubjectType.FILE_CHANGE,
    ApprovalSubjectType.NETWORK_REQUEST,
    ApprovalSubjectType.MCP_ELICITATION,
    ApprovalSubjectType.BROWSER_ACTION,
    ApprovalSubjectType.CHANNEL_SEND,
    ApprovalSubjectType.ISSUE_TO_PR_EXECUTE,
)

DECISION_TYPES = (
    ApprovalDecisionType.APPROVE_ONCE,
    ApprovalDecisionType.APPROVE_FOR_RUN,
    ApprovalDecisionType.APPROVE_FOR_SESSION,
    ApprovalDecisionType.DENY,
    ApprovalDecisionType.ABORT,
)

CODEX_APPROVAL_SOURCES = (
    "https://developers.openai.com/codex/agent-approvals-security",
    "https://developers.openai.com/codex/enterprise/admin-setup",
    "https://developers.openai.com/codex/app/features",
)


@dataclass(frozen=True)
class ApprovalSandboxAdminCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class ApprovalSubjectContract:
    subject_type: str
    action: str
    decision_types: list[str]
    default_sandbox_profile: str
    minimum_risk_level: str
    owner_gate_required: bool
    admin_policy_required: bool
    audit_required: bool
    blocked_without_approval: bool
    execution_adapter: dict[str, Any]


@dataclass(frozen=True)
class ApprovalSandboxAdminReport:
    status: str
    generated_at: str
    evidence_type: str
    full_codex_parity_claimed: bool
    dry_run: bool
    mutation_performed: bool
    network_mutation_performed: bool
    owner_gate_required: bool
    subjects: list[str]
    decision_types: list[str]
    contracts: list[ApprovalSubjectContract]
    checks: list[ApprovalSandboxAdminCheck]
    official_sources: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["contracts"] = [asdict(item) for item in self.contracts]
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def _contracts() -> list[ApprovalSubjectContract]:
    policies = {policy.subject_type: policy for policy in list_enterprise_safety_policies()}
    contracts: list[ApprovalSubjectContract] = []
    for subject in GOVERNED_SUBJECTS:
        policy = policies[subject]
        contracts.append(
            ApprovalSubjectContract(
                subject_type=subject.value,
                action=APPROVAL_SUBJECT_ACTIONS[subject],
                decision_types=[item.value for item in DECISION_TYPES],
                default_sandbox_profile=policy.default_sandbox_profile,
                minimum_risk_level=policy.minimum_risk_level.value,
                owner_gate_required=policy.owner_gate_required,
                admin_policy_required=policy.admin_policy_required,
                audit_required=policy.audit_required,
                blocked_without_approval=policy.blocked_without_approval,
                execution_adapter={
                    "state": "contract_only_owner_gated",
                    "mutation_enabled": False,
                    "requires_explicit_execute": True,
                },
            )
        )
    return contracts


def _build_checks(report_payload: dict[str, Any]) -> list[ApprovalSandboxAdminCheck]:
    contracts = report_payload["contracts"]
    expected_subjects = [item.value for item in GOVERNED_SUBJECTS]
    expected_decisions = [item.value for item in DECISION_TYPES]
    observed_subjects = [item["subject_type"] for item in contracts]
    unsafe_contracts = [
        item["subject_type"]
        for item in contracts
        if item["owner_gate_required"] is not True
        or item["admin_policy_required"] is not True
        or item["audit_required"] is not True
        or item["blocked_without_approval"] is not True
        or item["execution_adapter"].get("mutation_enabled") is not False
    ]
    decision_mismatches = [
        item["subject_type"]
        for item in contracts
        if item["decision_types"] != expected_decisions
    ]
    return [
        ApprovalSandboxAdminCheck(
            name="approval_subjects_complete",
            status="passed" if observed_subjects == expected_subjects else "failed",
            details={"observed": observed_subjects, "expected": expected_subjects},
            error=None if observed_subjects == expected_subjects else "approval subjects are incomplete",
        ),
        ApprovalSandboxAdminCheck(
            name="decision_types_complete",
            status="passed" if not decision_mismatches else "failed",
            details={"expected": expected_decisions, "mismatches": decision_mismatches},
            error=None if not decision_mismatches else "one or more subjects have incomplete decision types",
        ),
        ApprovalSandboxAdminCheck(
            name="owner_admin_audit_gates_required",
            status="passed" if not unsafe_contracts else "failed",
            details={"unsafe_contracts": unsafe_contracts},
            error=None if not unsafe_contracts else "one or more contracts can bypass owner/admin/audit gates",
        ),
        ApprovalSandboxAdminCheck(
            name="dry_run_only",
            status="passed" if report_payload["dry_run"] is True else "failed",
            details={"dry_run": report_payload["dry_run"]},
            error=None if report_payload["dry_run"] is True else "report is not dry-run",
        ),
        ApprovalSandboxAdminCheck(
            name="no_network_mutation",
            status="passed" if report_payload["network_mutation_performed"] is False else "failed",
            details={"network_mutation_performed": report_payload["network_mutation_performed"]},
            error=None
            if report_payload["network_mutation_performed"] is False
            else "network mutation was performed",
        ),
        ApprovalSandboxAdminCheck(
            name="no_full_codex_parity_claim",
            status="passed" if report_payload["full_codex_parity_claimed"] is False else "failed",
            details={"full_codex_parity_claimed": report_payload["full_codex_parity_claimed"]},
            error=None
            if report_payload["full_codex_parity_claimed"] is False
            else "report claims full Codex parity",
        ),
    ]


def build_approval_sandbox_admin_report() -> ApprovalSandboxAdminReport:
    contracts = _contracts()
    report_payload: dict[str, Any] = {
        "status": "approval_sandbox_admin_contract_ready",
        "generated_at": _utc_now(),
        "evidence_type": "approval_sandbox_enterprise_admin_contract",
        "full_codex_parity_claimed": False,
        "dry_run": True,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "owner_gate_required": True,
        "subjects": [item.value for item in GOVERNED_SUBJECTS],
        "decision_types": [item.value for item in DECISION_TYPES],
        "contracts": [asdict(item) for item in contracts],
        "official_sources": list(CODEX_APPROVAL_SOURCES),
        "known_limits": [
            "This report is read-only and does not execute commands, file changes, network requests, MCP elicitations, browser actions, channel sends, or GitHub issue-to-PR mutations.",
            "Enterprise admin policy persistence remains a future owner-gated adapter.",
            "Approval decisions are normalized, but full Codex approval, sandbox, and enterprise admin parity is not claimed.",
            "Runtime enforcement for every product surface must continue to be validated by the specific adapter tests before enabling execution.",
        ],
    }
    checks = _build_checks(report_payload)
    if any(check.status == "failed" for check in checks):
        report_payload["status"] = "approval_sandbox_admin_contract_blocked"
    return ApprovalSandboxAdminReport(
        contracts=contracts,
        checks=checks,
        **{key: value for key, value in report_payload.items() if key not in {"contracts"}},
    )


def render_markdown_report(report: ApprovalSandboxAdminReport) -> str:
    contracts = "\n".join(
        (
            f"- `{item.subject_type}`: action `{item.action}`, sandbox "
            f"`{item.default_sandbox_profile}`, min risk `{item.minimum_risk_level}`"
        )
        for item in report.contracts
    )
    checks = "\n".join(f"- {check.name}: `{check.status}`" for check in report.checks)
    limits = "\n".join(f"- {item}" for item in report.known_limits)
    sources = "\n".join(f"- {source}" for source in report.official_sources)
    return (
        "# X-Agent Approval Sandbox Admin Report\n\n"
        f"- Status: `{report.status}`\n"
        f"- Generated at: `{report.generated_at}`\n"
        f"- Dry run: `{report.dry_run}`\n"
        f"- Mutation performed: `{report.mutation_performed}`\n"
        f"- Network mutation performed: `{report.network_mutation_performed}`\n"
        f"- Full Codex parity claimed: `{report.full_codex_parity_claimed}`\n\n"
        "## Decision Types\n\n"
        f"`{', '.join(report.decision_types)}`\n\n"
        "## Subject Contracts\n\n"
        f"{contracts}\n\n"
        "## Checks\n\n"
        f"{checks}\n\n"
        "## Official Codex Sources\n\n"
        f"{sources}\n\n"
        "## Known Limits\n\n"
        f"{limits}\n"
    )


def write_report(report: ApprovalSandboxAdminReport, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(
    report: ApprovalSandboxAdminReport,
    output_path: Path = DEFAULT_MARKDOWN_OUTPUT,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_approval_sandbox_admin_report()
    write_report(report, args.output)
    write_markdown_report(report, args.markdown_output)
    print(f"Approval sandbox/admin report status: {report.status}")
    print(f"JSON report written to {args.output}")
    print(f"Markdown report written to {args.markdown_output}")
    print(f"Full Codex parity claimed: {report.full_codex_parity_claimed}")
    print(f"Mutation performed: {report.mutation_performed}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "approval_sandbox_admin_contract_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
