#!/usr/bin/env python3
"""Build a fail-closed Stage 5 security evidence pack.

This pack summarizes local evidence reports for controlled commercial pilot
readiness. It does not run scanners, claim real security certification, deploy,
tag, publish, or include raw secret values from source reports.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "stage5-security-evidence-pack-20260615.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "stage5-security-evidence-pack-20260615.md"

READY_STATUS = "controlled_commercial_pilot_security_evidence_ready"
BLOCKED_STATUS = "controlled_commercial_pilot_security_evidence_blocked"
DEFAULT_EXPECTED_STATUSES = ("ready", "passed")
BLOCKING_SEVERITIES = {"high", "critical"}
RESOLVED_FINDING_STATUSES = {"accepted", "closed", "false_positive", "fixed", "remediated", "resolved"}

SENSITIVE_KEY_RE = re.compile(
    r"(api[_-]?key|auth|bearer|client[_-]?secret|credential|jwt|password|private[_-]?key|secret|token)",
    re.IGNORECASE,
)
SECRET_VALUE_RE = re.compile(
    r"(?i)(gh[pousr]_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{20,}|"
    r"AKIA[0-9A-Z]{16}|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})"
)
KEY_VALUE_SECRET_RE = re.compile(
    r"(?i)\b(api[_-]?key|authorization|client[_-]?secret|password|secret|token)\s*[:=]\s*([^\s,;]+)"
)


@dataclass(frozen=True)
class EvidenceSpec:
    name: str
    path: Path
    expected_statuses: tuple[str, ...] = DEFAULT_EXPECTED_STATUSES
    required_for: str = "controlled_commercial_pilot_readiness"
    reason: str = ""


@dataclass(frozen=True)
class EvidenceItem:
    name: str
    path: str
    status: str | None
    expected_statuses: list[str]
    required_for: str
    ready: bool
    generated_at: str | None = None
    current_head_sha: str | None = None
    release_sha: str | None = None
    finding_count: int = 0
    unresolved_blocking_finding_count: int = 0
    secret_leakage_detected: bool = False
    risk_acceptance_recorded: bool | None = None
    sanitized_summary: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class PackCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class Stage5SecurityEvidencePack:
    status: str
    generated_at: str
    evidence_type: str
    readiness_scope: str
    current_head_sha: str | None
    release_sha: str | None
    security_evidence_ready: bool
    mutation_performed: bool
    outbound_message_sent: bool
    deploy_tag_release_performed: bool
    required_evidence: list[EvidenceItem]
    checks: list[PackCheck]
    missing_or_blocked_evidence: list[str]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["required_evidence"] = [asdict(item) for item in self.required_evidence]
        payload["checks"] = [asdict(check) for check in self.checks]
        return _redact(payload)


def default_required_evidence(report_dir: Path = REPORT_DIR) -> list[EvidenceSpec]:
    return [
        EvidenceSpec(
            "security_scanner_bandit",
            report_dir / "stage5-security-scanner-bandit-20260615.json",
            reason="Bandit or equivalent static security scanner evidence.",
        ),
        EvidenceSpec(
            "dependency_audit",
            report_dir / "stage5-dependency-audit-20260615.json",
            reason="Dependency audit evidence.",
        ),
        EvidenceSpec(
            "secret_scan",
            report_dir / "stage5-secret-scan-20260615.json",
            reason="Secret scan evidence without raw secret disclosure.",
        ),
        EvidenceSpec(
            "rbac_tenant_isolation",
            report_dir / "stage5-rbac-tenant-isolation-20260615.json",
            reason="RBAC and tenant isolation evidence.",
        ),
        EvidenceSpec(
            "audit_log",
            report_dir / "stage5-audit-log-20260615.json",
            reason="Audit log coverage evidence.",
        ),
        EvidenceSpec(
            "retention_compliance_signoff",
            report_dir / "stage5-retention-compliance-signoff-20260615.json",
            reason="Retention compliance signoff evidence.",
        ),
        EvidenceSpec(
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


def _redact(value: Any, *, parent_key: str = "") -> Any:
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if SENSITIVE_KEY_RE.search(key_text):
                redacted[key_text] = "<redacted>"
            else:
                redacted[key_text] = _redact(item, parent_key=key_text)
        return redacted
    if isinstance(value, list):
        return [_redact(item, parent_key=parent_key) for item in value]
    if isinstance(value, str):
        if SENSITIVE_KEY_RE.search(parent_key):
            return "<redacted>"
        text = SECRET_VALUE_RE.sub("<redacted-secret>", value)
        return KEY_VALUE_SECRET_RE.sub(lambda match: f"{match.group(1)}=<redacted>", text)
    return value


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"report not found: {_display_path(path)}"
    except json.JSONDecodeError as exc:
        return None, f"report is not valid JSON: {_display_path(path)}: {exc.msg}"
    except OSError as exc:
        return None, f"could not read report: {_display_path(path)}: {exc.__class__.__name__}"
    if not isinstance(payload, dict):
        return None, f"report is not a JSON object: {_display_path(path)}"
    return payload, None


def _string_field(payload: Mapping[str, Any] | None, keys: Sequence[str]) -> str | None:
    if not payload:
        return None
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _status(payload: Mapping[str, Any] | None) -> str | None:
    return _string_field(payload, ("status", "result", "report"))


def _release_sha(payload: Mapping[str, Any] | None) -> str | None:
    if not payload:
        return None
    version_identity = payload.get("version_identity")
    if isinstance(version_identity, Mapping):
        value = version_identity.get("release_sha") or version_identity.get("current_head_sha")
        if isinstance(value, str) and value:
            return value
    return _string_field(payload, ("release_sha", "current_head_sha", "head_sha", "commit_sha", "sha"))


def _current_head_sha(payload: Mapping[str, Any] | None) -> str | None:
    if not payload:
        return None
    version_identity = payload.get("version_identity")
    if isinstance(version_identity, Mapping):
        value = version_identity.get("current_head_sha")
        if isinstance(value, str) and value:
            return value
    return _string_field(payload, ("current_head_sha", "head_sha", "commit_sha", "sha")) or _release_sha(payload)


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().casefold()
        if lowered in {"1", "clean", "none", "passed", "ready", "true", "y", "yes"}:
            return True
        if lowered in {"0", "blocked", "detected", "failed", "false", "n", "no", "present"}:
            return False
    if isinstance(value, int):
        return value != 0
    return None


def _finding_lists(payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not payload:
        return []
    findings: list[Mapping[str, Any]] = []
    for key in ("alerts", "findings", "issues", "results", "vulnerabilities"):
        value = payload.get(key)
        if isinstance(value, list):
            findings.extend(item for item in value if isinstance(item, Mapping))
    return findings


def _unresolved_blocking_finding_count(payload: Mapping[str, Any] | None) -> int:
    count = 0
    for finding in _finding_lists(payload):
        severity = str(finding.get("severity") or finding.get("issue_severity") or finding.get("level") or "").casefold()
        status = str(finding.get("status") or finding.get("state") or "open").casefold()
        resolved = bool(finding.get("resolved") is True) or status in RESOLVED_FINDING_STATUSES
        if severity in BLOCKING_SEVERITIES and not resolved:
            count += 1
    return count


def _secret_leakage_detected(payload: Mapping[str, Any] | None) -> bool:
    if not payload:
        return False
    for key in (
        "leaked_secrets_detected",
        "leaks_detected",
        "secret_leakage",
        "secret_leakage_detected",
        "secrets_leaked",
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


def _risk_acceptance_recorded(payload: Mapping[str, Any] | None) -> bool | None:
    if not payload:
        return None
    for key in ("risk_acceptance_recorded", "risk_acceptance_register_recorded", "risk_register_recorded"):
        if key in payload:
            return _as_bool(payload[key])
    for key in ("accepted_risks", "risk_acceptances", "risk_register"):
        value = payload.get(key)
        if isinstance(value, list):
            return len(value) > 0
    signoff = payload.get("signoff")
    if isinstance(signoff, Mapping):
        return _as_bool(signoff.get("risk_acceptance_recorded"))
    return None


def _sanitized_summary(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    summary: dict[str, Any] = {}
    for key in ("scanner", "tool", "summary", "coverage", "signoff", "policy_refs", "report_id"):
        if key in payload:
            summary[key] = payload[key]
    summary["finding_count"] = len(_finding_lists(payload))
    return _redact(summary)


def _evidence_item(
    spec: EvidenceSpec,
    *,
    expected_current_head_sha: str | None,
    expected_release_sha: str | None,
) -> EvidenceItem:
    payload, read_error = _read_json(spec.path)
    status = _status(payload)
    current_head_sha = _current_head_sha(payload)
    release_sha = _release_sha(payload)
    generated_at = _string_field(payload, ("generated_at", "created_at", "updated_at"))
    finding_count = len(_finding_lists(payload))
    blocking_count = _unresolved_blocking_finding_count(payload)
    secret_leakage = _secret_leakage_detected(payload)
    risk_recorded = _risk_acceptance_recorded(payload)
    problems: list[str] = []

    if read_error:
        problems.append(read_error)
    if status not in spec.expected_statuses:
        problems.append(f"expected status {list(spec.expected_statuses)}, got {status or '<missing>'}")
    if not current_head_sha or current_head_sha != expected_current_head_sha:
        problems.append("current_head_sha is missing or does not match expected head")
    if not release_sha or release_sha != expected_release_sha:
        problems.append("release_sha is missing or does not match expected release SHA")
    if blocking_count:
        problems.append("unresolved high or critical findings are present")
    if secret_leakage:
        problems.append("secret leakage is present")
    if spec.name == "risk_acceptance_register" and risk_recorded is not True:
        problems.append("risk acceptance register is missing or not recorded")

    return EvidenceItem(
        name=spec.name,
        path=_display_path(spec.path),
        status=status,
        expected_statuses=list(spec.expected_statuses),
        required_for=spec.required_for,
        ready=not problems,
        generated_at=generated_at,
        current_head_sha=current_head_sha,
        release_sha=release_sha,
        finding_count=finding_count,
        unresolved_blocking_finding_count=blocking_count,
        secret_leakage_detected=secret_leakage,
        risk_acceptance_recorded=risk_recorded,
        sanitized_summary=_sanitized_summary(payload),
        error="; ".join(problems) if problems else None,
    )


def _check(name: str, passed: bool, details: dict[str, Any], error: str) -> PackCheck:
    return PackCheck(
        name=name,
        status="passed" if passed else "failed",
        details=_redact(details),
        error=None if passed else error,
    )


def _next_actions(missing_or_blocked: Sequence[str], risk_recorded: bool) -> list[str]:
    if not missing_or_blocked and risk_recorded:
        return ["Attach this evidence pack to the controlled commercial pilot readiness packet."]
    actions = [f"Produce or refresh local Stage 5 evidence for {name}." for name in missing_or_blocked]
    if not risk_recorded:
        actions.append("Record the risk acceptance register before any controlled pilot readiness claim.")
    return actions


def _known_limits() -> list[str]:
    return [
        "This evidence pack summarizes local reports only; it does not run scanners or audits.",
        "Ready means controlled commercial pilot evidence readiness only, not GA or production readiness.",
        "Raw report details are reduced and redacted to avoid leaking secrets in JSON or Markdown output.",
        "This pack does not deploy, tag, release, publish, or send outbound messages.",
    ]


def build_stage5_security_evidence_pack(
    *,
    report_dir: Path = REPORT_DIR,
    required_specs: Sequence[EvidenceSpec] | None = None,
    current_head_sha: str | None = None,
    release_sha: str | None = None,
) -> Stage5SecurityEvidencePack:
    resolved_head = current_head_sha or _git_value(["rev-parse", "HEAD"])
    resolved_release_sha = release_sha or resolved_head
    specs = list(required_specs or default_required_evidence(report_dir))
    evidence = [
        _evidence_item(
            spec,
            expected_current_head_sha=resolved_head,
            expected_release_sha=resolved_release_sha,
        )
        for spec in specs
    ]
    missing_or_blocked = [item.name for item in evidence if not item.ready]
    secret_leakage_sources = [item.name for item in evidence if item.secret_leakage_detected]
    blocking_sources = [item.name for item in evidence if item.unresolved_blocking_finding_count > 0]
    risk_recorded = any(
        item.name == "risk_acceptance_register" and item.risk_acceptance_recorded is True
        for item in evidence
    )
    all_evidence_ready = not missing_or_blocked
    shas_bound = bool(resolved_head and resolved_release_sha) and all(
        item.current_head_sha == resolved_head and item.release_sha == resolved_release_sha
        for item in evidence
    )

    checks = [
        _check(
            "required_stage5_security_evidence_present",
            all_evidence_ready,
            {"missing_or_blocked_evidence": missing_or_blocked},
            "One or more required Stage 5 evidence reports are missing or blocked.",
        ),
        _check(
            "evidence_bound_to_current_head_and_release_sha",
            shas_bound,
            {"current_head_sha": resolved_head, "release_sha": resolved_release_sha},
            "One or more evidence reports are not bound to current head and release SHA.",
        ),
        _check(
            "no_unresolved_high_or_critical_findings",
            not blocking_sources,
            {"blocking_evidence_sources": blocking_sources},
            "Unresolved high or critical security findings are present.",
        ),
        _check(
            "no_secret_leakage_reported",
            not secret_leakage_sources,
            {"secret_leakage_sources": secret_leakage_sources},
            "Secret leakage is reported by one or more evidence sources.",
        ),
        _check(
            "risk_acceptance_register_recorded",
            risk_recorded,
            {"risk_acceptance_recorded": risk_recorded},
            "Risk acceptance register is missing or not recorded.",
        ),
        _check(
            "pack_has_no_release_side_effects",
            True,
            {"mutation_performed": False, "outbound_message_sent": False, "deploy_tag_release_performed": False},
            "Evidence pack attempted a release side effect.",
        ),
    ]
    ready = all(check.status == "passed" for check in checks)
    return Stage5SecurityEvidencePack(
        status=READY_STATUS if ready else BLOCKED_STATUS,
        generated_at=_utc_now(),
        evidence_type="stage5_security_evidence_pack",
        readiness_scope="controlled_commercial_pilot_readiness",
        current_head_sha=resolved_head,
        release_sha=resolved_release_sha,
        security_evidence_ready=ready,
        mutation_performed=False,
        outbound_message_sent=False,
        deploy_tag_release_performed=False,
        required_evidence=evidence,
        checks=checks,
        missing_or_blocked_evidence=missing_or_blocked,
        next_actions=_next_actions(missing_or_blocked, risk_recorded),
        known_limits=_known_limits(),
    )


def render_markdown_report(report: Stage5SecurityEvidencePack) -> str:
    payload = report.to_dict()
    evidence = "\n".join(
        f"- {item['name']}: `{item.get('status') or '<missing>'}` / ready `{item['ready']}` / "
        f"findings `{item['finding_count']}` / blockers `{item['unresolved_blocking_finding_count']}`"
        + (f" / error: {item['error']}" if item.get("error") else "")
        for item in payload["required_evidence"]
    )
    checks = "\n".join(
        f"- {check['name']}: `{check['status']}`" + (f" - {check['error']}" if check.get("error") else "")
        for check in payload["checks"]
    )
    missing = "\n".join(f"- {name}" for name in payload["missing_or_blocked_evidence"]) or "- none"
    actions = "\n".join(f"- {item}" for item in payload["next_actions"])
    limits = "\n".join(f"- {item}" for item in payload["known_limits"])
    return (
        "# Stage 5 Security Evidence Pack\n\n"
        f"- Status: `{payload['status']}`\n"
        f"- Scope: `{payload['readiness_scope']}`\n"
        f"- Security evidence ready: `{payload['security_evidence_ready']}`\n"
        f"- Current head SHA: `{payload.get('current_head_sha') or '<missing>'}`\n"
        f"- Release SHA: `{payload.get('release_sha') or '<missing>'}`\n"
        f"- Generated at: `{payload['generated_at']}`\n"
        f"- Mutation performed: `{payload['mutation_performed']}`\n"
        f"- Outbound message sent: `{payload['outbound_message_sent']}`\n"
        f"- Deploy/tag/release performed: `{payload['deploy_tag_release_performed']}`\n\n"
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


def write_report(report: Stage5SecurityEvidencePack, output_path: Path = DEFAULT_OUTPUT_JSON) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(report: Stage5SecurityEvidencePack, output_path: Path = DEFAULT_OUTPUT_MD) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Stage 5 security evidence pack.")
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--current-head-sha", default=None)
    parser.add_argument("--release-sha", default=None)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_stage5_security_evidence_pack(
        report_dir=args.report_dir,
        current_head_sha=args.current_head_sha,
        release_sha=args.release_sha,
    )
    write_report(report, args.output_json)
    write_markdown_report(report, args.output_md)
    print(f"Stage 5 security evidence pack status: {report.status}")
    print(f"Readiness scope: {report.readiness_scope}")
    print(f"Missing or blocked evidence: {', '.join(report.missing_or_blocked_evidence) or '<none>'}")
    print(f"JSON report written to {args.output_json}")
    print(f"Markdown report written to {args.output_md}")
    return 0 if report.security_evidence_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
