#!/usr/bin/env python3
"""Validate Stage 5 Ops / Support evidence.

This gate is fail-closed. It reads evidence reports only and writes a local
gate report. It does not deploy, tag, release, mutate runtime state, or send
outbound support/customer messages.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, ROOT, _utc_now

DEFAULT_OUTPUT_JSON = REPORT_DIR / "stage5-ops-support-gate-20260615.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "stage5-ops-support-gate-20260615.md"

READY_STATUSES = {"ready", "passed"}


@dataclass(frozen=True)
class OpsSupportEvidenceSpec:
    name: str
    path: Path
    expected_statuses: tuple[str, ...] = ("ready", "passed")
    reason: str = ""


@dataclass(frozen=True)
class OpsSupportEvidenceSummary:
    name: str
    path: str
    status: str | None
    expected_statuses: list[str]
    release_sha: str | None
    current_head_sha: str | None
    ready: bool
    error: str | None = None


@dataclass(frozen=True)
class OpsSupportGateCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class OpsSupportGateReport:
    status: str
    generated_at: str
    evidence_type: str
    current_head_sha: str | None
    release_sha: str | None
    ops_support_ready: bool
    mutation_performed: bool
    outbound_message_sent: bool
    deploy_tag_release_performed: bool
    required_evidence: list[OpsSupportEvidenceSummary]
    checks: list[OpsSupportGateCheck]
    missing_or_blocked_evidence: list[str]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["required_evidence"] = [asdict(evidence) for evidence in self.required_evidence]
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def default_required_evidence(report_dir: Path = REPORT_DIR) -> list[OpsSupportEvidenceSpec]:
    return [
        OpsSupportEvidenceSpec(
            "slo_sla",
            report_dir / "stage5-slo-sla-evidence-20260615.json",
            reason="SLO/SLA objectives, measurement windows, error budgets, and customer support response targets.",
        ),
        OpsSupportEvidenceSpec(
            "alert_routing",
            report_dir / "stage5-alert-routing-evidence-20260615.json",
            reason="Alert routing, severity mapping, notification channels, and tested receiver ownership.",
        ),
        OpsSupportEvidenceSpec(
            "backup_restore_rehearsal",
            report_dir / "stage5-backup-restore-rehearsal-20260615.json",
            reason="Backup/restore rehearsal with RPO/RTO and verification outcome.",
        ),
        OpsSupportEvidenceSpec(
            "incident_process",
            report_dir / "stage5-incident-process-evidence-20260615.json",
            reason="Incident declaration, triage, comms, postmortem, and severity process.",
        ),
        OpsSupportEvidenceSpec(
            "support_escalation",
            report_dir / "stage5-support-escalation-evidence-20260615.json",
            reason="Support escalation path, owner handoff, and customer-impact routing.",
        ),
        OpsSupportEvidenceSpec(
            "cost_capacity_guardrails",
            report_dir / "stage5-cost-capacity-guardrails-20260615.json",
            reason="Cost budgets, capacity thresholds, throttling, and scale guardrails.",
        ),
        OpsSupportEvidenceSpec(
            "on_call_ownership",
            report_dir / "stage5-on-call-ownership-evidence-20260615.json",
            reason="On-call schedule, service ownership, backup owner, and escalation coverage.",
        ),
    ]


def _display_path(path: Path, *, root: Path = ROOT) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
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
    for key in ("status", "ops_status", "report", "result"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _release_sha(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    version_identity = payload.get("version_identity")
    if isinstance(version_identity, dict):
        for key in ("release_sha", "current_head_sha", "head_sha", "commit_sha"):
            value = version_identity.get(key)
            if isinstance(value, str) and value:
                return value
    for key in ("release_sha", "current_head_sha", "head_sha", "commit_sha"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _current_head_sha(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    version_identity = payload.get("version_identity")
    if isinstance(version_identity, dict):
        value = version_identity.get("current_head_sha")
        if isinstance(value, str) and value:
            return value
    value = payload.get("current_head_sha")
    return value if isinstance(value, str) and value else None


def _evidence_summary(
    spec: OpsSupportEvidenceSpec,
    *,
    current_head_sha: str | None,
    root: Path,
) -> tuple[OpsSupportEvidenceSummary, dict[str, Any] | None]:
    payload, read_error = _read_json(spec.path)
    status = _status(payload)
    release_sha = _release_sha(payload)
    evidence_head = _current_head_sha(payload)
    expected = set(spec.expected_statuses)
    problems: list[str] = []
    if read_error:
        problems.append(read_error)
    if status not in expected:
        problems.append(f"expected status {sorted(expected)}, got {status or '<missing>'}")
    if not release_sha:
        problems.append("release_sha missing")
    if release_sha and current_head_sha and release_sha != current_head_sha:
        problems.append("release_sha does not match current head")
    if not evidence_head:
        problems.append("current_head_sha missing")
    if evidence_head and current_head_sha and evidence_head != current_head_sha:
        problems.append("current_head_sha does not match current head")
    ready = not problems
    return (
        OpsSupportEvidenceSummary(
            name=spec.name,
            path=_display_path(spec.path, root=root),
            status=status,
            expected_statuses=sorted(expected),
            release_sha=release_sha,
            current_head_sha=evidence_head,
            ready=ready,
            error="; ".join(problems) if problems else None,
        ),
        payload,
    )


def _check(name: str, passed: bool, details: dict[str, Any], error: str) -> OpsSupportGateCheck:
    return OpsSupportGateCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details,
        error=None if passed else error,
    )


def _next_actions(missing_or_blocked: Sequence[str]) -> list[str]:
    if not missing_or_blocked:
        return ["Archive the Ops / Support gate JSON and Markdown reports with the Stage 5 release packet."]
    return [
        f"Produce or refresh current-head-bound Ops / Support evidence for {name}."
        for name in missing_or_blocked
    ] + [
        "Keep the commercial GA final gate blocked until every Ops / Support evidence item is ready.",
        "Do not deploy, tag, release, or send outbound support/customer messages from this gate.",
    ]


def build_ops_support_gate_report(
    *,
    report_dir: Path = REPORT_DIR,
    required_specs: Sequence[OpsSupportEvidenceSpec] | None = None,
    current_head_sha: str | None = None,
    release_sha: str | None = None,
    root: Path = ROOT,
) -> OpsSupportGateReport:
    resolved_head = current_head_sha or _git_value(["rev-parse", "HEAD"])
    specs = list(required_specs or default_required_evidence(report_dir))
    evidence_pairs = [
        _evidence_summary(spec, current_head_sha=resolved_head, root=root)
        for spec in specs
    ]
    required_evidence = [pair[0] for pair in evidence_pairs]
    missing_or_blocked = [evidence.name for evidence in required_evidence if not evidence.ready]

    evidence_release_shas = {
        evidence.name: evidence.release_sha for evidence in required_evidence if evidence.release_sha
    }
    evidence_head_shas = {
        evidence.name: evidence.current_head_sha for evidence in required_evidence if evidence.current_head_sha
    }
    resolved_release_sha = release_sha or resolved_head
    all_evidence_ready = len(missing_or_blocked) == 0
    release_sha_resolved = bool(resolved_release_sha)
    gate_release_matches_head = bool(resolved_head) and resolved_release_sha == resolved_head
    evidence_release_bound = all(
        evidence.release_sha == resolved_head and evidence.current_head_sha == resolved_head
        for evidence in required_evidence
    )
    ready = all_evidence_ready and release_sha_resolved and gate_release_matches_head and evidence_release_bound

    checks = [
        _check(
            "all_required_ops_support_evidence_ready",
            all_evidence_ready,
            {"missing_or_blocked_evidence": missing_or_blocked},
            "One or more required Ops / Support evidence reports are missing or not ready.",
        ),
        _check(
            "required_evidence_bound_to_current_head",
            evidence_release_bound,
            {
                "current_head_sha": resolved_head,
                "evidence_release_shas": evidence_release_shas,
                "evidence_current_head_shas": evidence_head_shas,
            },
            "One or more Ops / Support evidence reports are not bound to current head.",
        ),
        _check(
            "gate_release_sha_bound_to_current_head",
            release_sha_resolved and gate_release_matches_head,
            {"current_head_sha": resolved_head, "release_sha": resolved_release_sha},
            "Gate release_sha is missing or does not match current head.",
        ),
        _check(
            "gate_has_no_release_side_effects",
            True,
            {
                "mutation_performed": False,
                "outbound_message_sent": False,
                "deploy_tag_release_performed": False,
            },
            "gate attempted a release side effect",
        ),
    ]
    status = "ops_support_ready" if ready else "ops_support_blocked"
    return OpsSupportGateReport(
        status=status,
        generated_at=_utc_now(),
        evidence_type="stage5_ops_support_gate",
        current_head_sha=resolved_head,
        release_sha=resolved_release_sha,
        ops_support_ready=ready,
        mutation_performed=False,
        outbound_message_sent=False,
        deploy_tag_release_performed=False,
        required_evidence=required_evidence,
        checks=checks,
        missing_or_blocked_evidence=missing_or_blocked,
        next_actions=_next_actions(missing_or_blocked),
        known_limits=[
            "This gate validates Ops / Support evidence presence, status, and SHA binding only.",
            "This gate does not deploy, tag, release, mutate runtime state, page on-call, or send outbound messages.",
            "Current workspace evidence must be refreshed separately by owner-approved operations.",
        ],
    )


def render_markdown_report(report: OpsSupportGateReport) -> str:
    evidence = "\n".join(
        f"- {item.name}: `{item.status or '<missing>'}` / ready `{item.ready}` / "
        f"release_sha `{item.release_sha or '<missing>'}`"
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
        "# Stage 5 Ops / Support Gate\n\n"
        f"- Status: `{report.status}`\n"
        f"- Ops / Support ready: `{report.ops_support_ready}`\n"
        f"- Current head SHA: `{report.current_head_sha or '<missing>'}`\n"
        f"- Release SHA: `{report.release_sha or '<missing>'}`\n"
        f"- Generated at: `{report.generated_at}`\n"
        f"- Mutation performed: `{report.mutation_performed}`\n"
        f"- Outbound message sent: `{report.outbound_message_sent}`\n"
        f"- Deploy/tag/release performed: `{report.deploy_tag_release_performed}`\n\n"
        "## Required Evidence\n\n"
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


def write_report(report: OpsSupportGateReport, output_path: Path = DEFAULT_OUTPUT_JSON) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(report: OpsSupportGateReport, output_path: Path = DEFAULT_OUTPUT_MD) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--current-head-sha", default=None)
    parser.add_argument("--release-sha", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_ops_support_gate_report(
        report_dir=args.report_dir,
        current_head_sha=args.current_head_sha,
        release_sha=args.release_sha,
    )
    write_report(report, args.output_json)
    write_markdown_report(report, args.output_md)
    print(f"Stage 5 Ops / Support gate status: {report.status}")
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
    return 0 if report.ops_support_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
