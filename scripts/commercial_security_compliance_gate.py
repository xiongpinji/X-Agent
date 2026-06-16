#!/usr/bin/env python3
"""Validate Stage 5 security and compliance evidence.

This gate is fail-closed. It reads security/compliance evidence reports only
and writes a local JSON/Markdown report. It does not mutate release state,
send outbound messages, deploy, tag, or publish artifacts.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "stage5-security-compliance-gate-20260615.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "stage5-security-compliance-gate-20260615.md"

READY_STATUS = "security_compliance_ready"
BLOCKED_STATUS = "security_compliance_blocked"
DEFAULT_EXPECTED_STATUSES = ("ready", "passed")
BLOCKING_SEVERITIES = {"high", "critical"}
RESOLVED_FINDING_STATUSES = {"resolved", "fixed", "closed", "remediated", "false_positive", "accepted"}


@dataclass(frozen=True)
class SecurityEvidenceSpec:
    name: str
    path: Path
    expected_statuses: tuple[str, ...] = DEFAULT_EXPECTED_STATUSES
    evidence_level: str = "security_compliance_hard_blocker"
    reason: str = ""


@dataclass(frozen=True)
class SecurityEvidenceSummary:
    name: str
    path: str
    status: str | None
    expected_statuses: list[str]
    evidence_level: str
    release_sha: str | None
    current_head_sha: str | None
    ready: bool
    unresolved_blocking_findings: list[dict[str, Any]] = field(default_factory=list)
    secret_leakage_detected: bool = False
    risk_acceptance_recorded: bool | None = None
    error: str | None = None


@dataclass(frozen=True)
class SecurityComplianceCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class SecurityComplianceGateReport:
    status: str
    generated_at: str
    evidence_type: str
    current_head_sha: str | None
    release_sha: str | None
    security_compliance_ready: bool
    mutation_performed: bool
    outbound_message_sent: bool
    deploy_tag_release_performed: bool
    required_evidence: list[SecurityEvidenceSummary]
    checks: list[SecurityComplianceCheck]
    missing_or_blocked_evidence: list[str]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["required_evidence"] = [asdict(evidence) for evidence in self.required_evidence]
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def default_required_evidence(report_dir: Path = REPORT_DIR) -> list[SecurityEvidenceSpec]:
    return [
        SecurityEvidenceSpec(
            "security_scanner_bandit",
            report_dir / "stage5-security-scanner-bandit-20260615.json",
            reason="Static security scanner/Bandit evidence with no unresolved high or critical findings.",
        ),
        SecurityEvidenceSpec(
            "dependency_audit",
            report_dir / "stage5-dependency-audit-20260615.json",
            reason="Dependency audit evidence with no unresolved high or critical vulnerabilities.",
        ),
        SecurityEvidenceSpec(
            "secret_scan",
            report_dir / "stage5-secret-scan-20260615.json",
            reason="Secret scan evidence proving no secret leakage.",
        ),
        SecurityEvidenceSpec(
            "rbac_tenant_isolation",
            report_dir / "stage5-rbac-tenant-isolation-20260615.json",
            reason="RBAC and tenant isolation evidence.",
        ),
        SecurityEvidenceSpec(
            "audit_log",
            report_dir / "stage5-audit-log-20260615.json",
            reason="Audit logging evidence.",
        ),
        SecurityEvidenceSpec(
            "retention_compliance_signoff",
            report_dir / "stage5-retention-compliance-signoff-20260615.json",
            reason="Retention/compliance signoff evidence.",
        ),
        SecurityEvidenceSpec(
            "risk_acceptance_register",
            report_dir / "stage5-risk-acceptance-register-20260615.json",
            reason="Risk acceptance register evidence.",
        ),
    ]


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"report not found: {_display_path(path)}"
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"could not read report {_display_path(path)}: {exc}"
    if not isinstance(payload, dict):
        return None, f"report is not a JSON object: {_display_path(path)}"
    return payload, None


def _git_value(args: Sequence[str]) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _status(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    for key in ("status", "result", "report"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _release_sha(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    version_identity = payload.get("version_identity")
    if isinstance(version_identity, dict) and isinstance(version_identity.get("current_head_sha"), str):
        return version_identity["current_head_sha"]
    for key in ("release_sha", "current_head_sha", "head_sha", "commit_sha", "sha"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _current_head_sha(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    version_identity = payload.get("version_identity")
    if isinstance(version_identity, dict) and isinstance(version_identity.get("current_head_sha"), str):
        return version_identity["current_head_sha"]
    value = payload.get("current_head_sha")
    return value if isinstance(value, str) and value else _release_sha(payload)


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().casefold()
        if lowered in {"true", "yes", "y", "1", "passed", "ready", "none", "clean"}:
            return True
        if lowered in {"false", "no", "n", "0", "failed", "blocked", "detected", "present"}:
            return False
    if isinstance(value, int):
        return value != 0
    return None


def _secret_leakage_detected(payload: dict[str, Any] | None) -> bool:
    if not payload:
        return False
    for key in (
        "secret_leakage_detected",
        "secret_leakage",
        "secrets_leaked",
        "leaked_secrets_detected",
        "leaks_detected",
    ):
        if key in payload:
            value = _as_bool(payload[key])
            if value is not None:
                return value
    for key in ("leaked_secrets", "secret_findings", "secrets"):
        value = payload.get(key)
        if isinstance(value, list) and value:
            return True
        if isinstance(value, int) and value > 0:
            return True
    return False


def _finding_lists(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    findings: list[dict[str, Any]] = []
    for key in ("findings", "vulnerabilities", "issues", "alerts"):
        value = payload.get(key)
        if isinstance(value, list):
            findings.extend(item for item in value if isinstance(item, dict))
    return findings


def _unresolved_blocking_findings(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    unresolved: list[dict[str, Any]] = []
    for finding in _finding_lists(payload):
        severity = str(finding.get("severity") or finding.get("level") or "").casefold()
        status = str(finding.get("status") or finding.get("state") or "open").casefold()
        resolved = bool(finding.get("resolved") is True) or status in RESOLVED_FINDING_STATUSES
        if severity in BLOCKING_SEVERITIES and not resolved:
            unresolved.append(
                {
                    "id": finding.get("id") or finding.get("rule_id") or finding.get("cve") or "<unknown>",
                    "severity": severity,
                    "status": status,
                    "title": finding.get("title") or finding.get("message") or finding.get("description"),
                }
            )
    return unresolved


def _risk_acceptance_recorded(payload: dict[str, Any] | None) -> bool | None:
    if not payload:
        return None
    for key in ("risk_acceptance_recorded", "risk_register_recorded", "risk_acceptance_register_recorded"):
        if key in payload:
            return _as_bool(payload[key])
    for key in ("accepted_risks", "risk_acceptances", "risk_register"):
        value = payload.get(key)
        if isinstance(value, list):
            return len(value) > 0
    if isinstance(payload.get("signoff"), dict):
        return _as_bool(payload["signoff"].get("risk_acceptance_recorded"))
    return None


def _evidence_summary(
    spec: SecurityEvidenceSpec,
    *,
    expected_current_head_sha: str | None,
    expected_release_sha: str | None,
) -> tuple[SecurityEvidenceSummary, dict[str, Any] | None]:
    payload, read_error = _read_json(spec.path)
    status = _status(payload)
    release_sha = _release_sha(payload)
    current_head_sha = _current_head_sha(payload)
    unresolved = _unresolved_blocking_findings(payload)
    secret_leakage = _secret_leakage_detected(payload)
    risk_recorded = _risk_acceptance_recorded(payload)
    problems: list[str] = []
    if read_error:
        problems.append(read_error)
    if status not in spec.expected_statuses:
        problems.append(f"expected status {list(spec.expected_statuses)}, got {status or '<missing>'}")
    if not current_head_sha or current_head_sha != expected_current_head_sha:
        problems.append("report current_head_sha is missing or does not match current head")
    if not release_sha or release_sha != expected_release_sha:
        problems.append("report release_sha is missing or does not match release SHA")
    if unresolved:
        problems.append("unresolved high or critical findings are present")
    if secret_leakage:
        problems.append("secret leakage is present")
    return (
        SecurityEvidenceSummary(
            name=spec.name,
            path=_display_path(spec.path),
            status=status,
            expected_statuses=list(spec.expected_statuses),
            evidence_level=spec.evidence_level,
            release_sha=release_sha,
            current_head_sha=current_head_sha,
            ready=not problems,
            unresolved_blocking_findings=unresolved,
            secret_leakage_detected=secret_leakage,
            risk_acceptance_recorded=risk_recorded,
            error="; ".join(problems) if problems else None,
        ),
        payload,
    )


def _check(name: str, passed: bool, details: dict[str, Any], error: str) -> SecurityComplianceCheck:
    return SecurityComplianceCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details,
        error=None if passed else error,
    )


def _next_actions(missing_or_blocked: Sequence[str], risk_recorded: bool) -> list[str]:
    if not missing_or_blocked and risk_recorded:
        return ["Archive this JSON and Markdown report with the Stage 5 release packet."]
    actions = [
        f"Produce or refresh security/compliance evidence for {name}."
        for name in missing_or_blocked
    ]
    if not risk_recorded:
        actions.append("Record the risk acceptance register and rerun this gate.")
    return actions


def _known_limits() -> list[str]:
    return [
        "This gate reads evidence reports only; it does not run scanners or mutate release state.",
        "This gate does not deploy, tag, release, or send outbound messages.",
        "Ready status is only valid for evidence bound to the current head and release SHA.",
    ]


def build_security_compliance_gate(
    *,
    report_dir: Path = REPORT_DIR,
    required_specs: Sequence[SecurityEvidenceSpec] | None = None,
    current_head_sha: str | None = None,
    release_sha: str | None = None,
) -> SecurityComplianceGateReport:
    resolved_head = current_head_sha or _git_value(["rev-parse", "HEAD"])
    resolved_release_sha = release_sha or resolved_head
    specs = list(required_specs or default_required_evidence(report_dir))
    evidence_pairs = [
        _evidence_summary(
            spec,
            expected_current_head_sha=resolved_head,
            expected_release_sha=resolved_release_sha,
        )
        for spec in specs
    ]
    evidence = [pair[0] for pair in evidence_pairs]
    missing_or_blocked = [item.name for item in evidence if not item.ready]
    unresolved = {
        item.name: item.unresolved_blocking_findings
        for item in evidence
        if item.unresolved_blocking_findings
    }
    secret_leakage_sources = [item.name for item in evidence if item.secret_leakage_detected]
    risk_sources = [
        item.name
        for item in evidence
        if item.name == "risk_acceptance_register" and item.risk_acceptance_recorded is True
    ]
    risk_recorded = bool(risk_sources)
    all_evidence_ready = not missing_or_blocked
    shas_resolved = bool(resolved_head and resolved_release_sha)
    shas_bound = shas_resolved and all(
        item.current_head_sha == resolved_head and item.release_sha == resolved_release_sha
        for item in evidence
    )
    no_unresolved = not unresolved
    no_secret_leakage = not secret_leakage_sources

    checks = [
        _check(
            "required_security_compliance_evidence_ready",
            all_evidence_ready,
            {"missing_or_blocked_evidence": missing_or_blocked},
            "One or more required security/compliance evidence reports are missing or not ready.",
        ),
        _check(
            "evidence_bound_to_current_head_and_release_sha",
            shas_bound,
            {"current_head_sha": resolved_head, "release_sha": resolved_release_sha},
            "One or more evidence reports are not bound to current head and release SHA.",
        ),
        _check(
            "no_unresolved_high_or_critical_findings",
            no_unresolved,
            {"unresolved_blocking_findings": unresolved},
            "Unresolved high or critical security findings are present.",
        ),
        _check(
            "no_secret_leakage",
            no_secret_leakage,
            {"secret_leakage_sources": secret_leakage_sources},
            "Secret leakage evidence is present.",
        ),
        _check(
            "risk_acceptance_recorded",
            risk_recorded,
            {"risk_acceptance_sources": risk_sources},
            "Risk acceptance register is missing or not recorded.",
        ),
        _check(
            "gate_has_no_release_side_effects",
            True,
            {"mutation_performed": False, "outbound_message_sent": False, "deploy_tag_release_performed": False},
            "Gate attempted a release side effect.",
        ),
    ]
    ready = all(check.status == "passed" for check in checks)
    return SecurityComplianceGateReport(
        status=READY_STATUS if ready else BLOCKED_STATUS,
        generated_at=_utc_now(),
        evidence_type="stage5_security_compliance_gate",
        current_head_sha=resolved_head,
        release_sha=resolved_release_sha,
        security_compliance_ready=ready,
        mutation_performed=False,
        outbound_message_sent=False,
        deploy_tag_release_performed=False,
        required_evidence=evidence,
        checks=checks,
        missing_or_blocked_evidence=missing_or_blocked,
        next_actions=_next_actions(missing_or_blocked, risk_recorded),
        known_limits=_known_limits(),
    )


def render_markdown_report(report: SecurityComplianceGateReport) -> str:
    evidence = "\n".join(
        f"- {item.name}: `{item.status or '<missing>'}` / ready `{item.ready}` / "
        f"head `{item.current_head_sha or '<missing>'}` / release `{item.release_sha or '<missing>'}`"
        + (f" / error: {item.error}" if item.error else "")
        for item in report.required_evidence
    )
    checks = "\n".join(
        f"- {check.name}: `{check.status}`" + (f" - {check.error}" if check.error else "")
        for check in report.checks
    )
    missing = "\n".join(f"- {name}" for name in report.missing_or_blocked_evidence) or "- none"
    actions = "\n".join(f"- {item}" for item in report.next_actions)
    limits = "\n".join(f"- {item}" for item in report.known_limits)
    return (
        "# Stage 5 Security Compliance Gate\n\n"
        f"- Status: `{report.status}`\n"
        f"- Ready: `{report.security_compliance_ready}`\n"
        f"- Current head SHA: `{report.current_head_sha or '<missing>'}`\n"
        f"- Release SHA: `{report.release_sha or '<missing>'}`\n"
        f"- Generated at: `{report.generated_at}`\n"
        f"- Mutation performed: `{report.mutation_performed}`\n"
        f"- Outbound message sent: `{report.outbound_message_sent}`\n"
        f"- Deploy/tag/release performed: `{report.deploy_tag_release_performed}`\n\n"
        "## Evidence\n\n"
        f"{evidence}\n\n"
        "## Missing Or Blocked Evidence\n\n"
        f"{missing}\n\n"
        "## Checks\n\n"
        f"{checks}\n\n"
        "## Next Actions\n\n"
        f"{actions}\n\n"
        "## Known Limits\n\n"
        f"{limits}\n"
    )


def write_report(report: SecurityComplianceGateReport, output_path: Path = DEFAULT_OUTPUT_JSON) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(report: SecurityComplianceGateReport, output_path: Path = DEFAULT_OUTPUT_MD) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Stage 5 security/compliance evidence.")
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--current-head-sha", default=None)
    parser.add_argument("--release-sha", default=None)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_security_compliance_gate(
        report_dir=args.report_dir,
        current_head_sha=args.current_head_sha,
        release_sha=args.release_sha,
    )
    write_report(report, args.output_json)
    write_markdown_report(report, args.output_md)
    print(f"Stage 5 security compliance gate status: {report.status}")
    print(f"Current head: {report.current_head_sha or '<missing>'}")
    print(f"Release SHA: {report.release_sha or '<missing>'}")
    print(f"Missing or blocked evidence: {', '.join(report.missing_or_blocked_evidence) or '<none>'}")
    print(f"JSON report written to {args.output_json}")
    print(f"Markdown report written to {args.output_md}")
    print(f"Mutation performed: {report.mutation_performed}")
    print(f"Outbound message sent: {report.outbound_message_sent}")
    print(f"Deploy/tag/release performed: {report.deploy_tag_release_performed}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.security_compliance_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
