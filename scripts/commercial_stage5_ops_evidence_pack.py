#!/usr/bin/env python3
"""Build a fail-closed Stage 5 Ops / Support evidence pack.

This pack is read-only over local evidence files. It can support controlled
commercial pilot readiness only. It does not prove general availability,
production readiness, or full commercial delivery.
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

DEFAULT_OUTPUT_JSON = REPORT_DIR / "stage5-ops-support-evidence-pack-20260615.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "stage5-ops-support-evidence-pack-20260615.md"

READY_STATUSES = frozenset({"ready", "passed"})
FORBIDDEN_TRUE_FIELDS = (
    "ga_ready",
    "production_ready",
    "full_commercial_delivery_complete",
    "full_codex_parity_claimed",
)


@dataclass(frozen=True)
class OpsEvidenceSource:
    name: str
    path: Path
    expected_statuses: tuple[str, ...] = ("ready", "passed")


@dataclass(frozen=True)
class OpsEvidenceItem:
    name: str
    path: str
    status: str | None
    expected_statuses: list[str]
    release_sha: str | None
    current_head_sha: str | None
    evidence_refs: list[str]
    summary: str | None
    ready: bool
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OpsEvidencePackCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class OpsEvidencePackReport:
    status: str
    generated_at: str
    evidence_type: str
    claim_boundary: dict[str, Any]
    current_head_sha: str | None
    release_sha: str | None
    controlled_commercial_pilot_ops_ready: bool
    mutation_performed: bool
    outbound_message_sent: bool
    deploy_tag_release_performed: bool
    evidence: list[OpsEvidenceItem]
    checks: list[OpsEvidencePackCheck]
    missing_or_blocked_evidence: list[str]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence"] = [asdict(item) for item in self.evidence]
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def default_evidence_sources(report_dir: Path = REPORT_DIR) -> list[OpsEvidenceSource]:
    return [
        OpsEvidenceSource("slo_sla", report_dir / "stage5-slo-sla-evidence-20260615.json"),
        OpsEvidenceSource("alert_routing", report_dir / "stage5-alert-routing-evidence-20260615.json"),
        OpsEvidenceSource(
            "backup_restore_rehearsal",
            report_dir / "stage5-backup-restore-rehearsal-20260615.json",
        ),
        OpsEvidenceSource("incident_process", report_dir / "stage5-incident-process-evidence-20260615.json"),
        OpsEvidenceSource("support_escalation", report_dir / "stage5-support-escalation-evidence-20260615.json"),
        OpsEvidenceSource(
            "cost_capacity_guardrails",
            report_dir / "stage5-cost-capacity-guardrails-20260615.json",
        ),
        OpsEvidenceSource("on_call_ownership", report_dir / "stage5-on-call-ownership-evidence-20260615.json"),
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
        return None, f"missing evidence file: {path}"
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"could not read evidence file: {exc}"
    if not isinstance(payload, dict):
        return None, "evidence file is not a JSON object"
    return payload, None


def _git_head() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
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
    for key in ("status", "ops_status", "result"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _version_value(payload: dict[str, Any] | None, key: str) -> str | None:
    if not payload:
        return None
    version_identity = payload.get("version_identity")
    if isinstance(version_identity, dict):
        value = version_identity.get(key)
        if isinstance(value, str) and value:
            return value
    value = payload.get(key)
    return value if isinstance(value, str) and value else None


def _release_sha(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    for key in ("release_sha", "current_head_sha", "head_sha", "commit_sha"):
        value = _version_value(payload, key)
        if value:
            return value
    return None


def _current_head_sha(payload: dict[str, Any] | None) -> str | None:
    return _version_value(payload, "current_head_sha")


def _list_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _summary(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    for key in ("summary", "evidence_summary", "description"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _forbidden_claims(payload: dict[str, Any] | None) -> list[str]:
    if not payload:
        return []
    return [field for field in FORBIDDEN_TRUE_FIELDS if payload.get(field) is True]


def _evidence_item(
    source: OpsEvidenceSource,
    *,
    current_head_sha: str | None,
    root: Path,
) -> OpsEvidenceItem:
    payload, read_error = _read_json(source.path)
    status = _status(payload)
    release_sha = _release_sha(payload)
    evidence_head = _current_head_sha(payload)
    expected = sorted(source.expected_statuses)
    errors: list[str] = []

    if read_error:
        errors.append(read_error)
    if status not in set(source.expected_statuses):
        errors.append(f"expected status {expected}, got {status or '<missing>'}")
    if not release_sha:
        errors.append("release_sha missing")
    if not evidence_head:
        errors.append("current_head_sha missing")
    if release_sha and current_head_sha and release_sha != current_head_sha:
        errors.append("release_sha does not match current head")
    if evidence_head and current_head_sha and evidence_head != current_head_sha:
        errors.append("current_head_sha does not match current head")

    forbidden = _forbidden_claims(payload)
    if forbidden:
        errors.append(f"forbidden readiness claim fields set true: {', '.join(forbidden)}")

    return OpsEvidenceItem(
        name=source.name,
        path=_display_path(source.path, root=root),
        status=status,
        expected_statuses=expected,
        release_sha=release_sha,
        current_head_sha=evidence_head,
        evidence_refs=_list_strings(payload.get("evidence_refs") if payload else None),
        summary=_summary(payload),
        ready=not errors,
        errors=errors,
    )


def _check(name: str, passed: bool, details: dict[str, Any], error: str) -> OpsEvidencePackCheck:
    return OpsEvidencePackCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details,
        error=None if passed else error,
    )


def _next_actions(missing_or_blocked: Sequence[str]) -> list[str]:
    if not missing_or_blocked:
        return ["Archive the local Stage 5 Ops / Support evidence pack with the controlled pilot packet."]
    return [
        f"Produce or refresh current-head-bound local evidence for {name}."
        for name in missing_or_blocked
    ] + [
        "Keep owner-facing language scoped to controlled commercial pilot readiness.",
        "Do not deploy, tag, release, page on-call, or send customer/support messages from this evidence pack.",
    ]


def build_ops_evidence_pack(
    *,
    report_dir: Path = REPORT_DIR,
    sources: Sequence[OpsEvidenceSource] | None = None,
    current_head_sha: str | None = None,
    release_sha: str | None = None,
    root: Path = ROOT,
) -> OpsEvidencePackReport:
    resolved_head = current_head_sha or _git_head()
    resolved_release_sha = release_sha or resolved_head
    evidence_sources = list(sources or default_evidence_sources(report_dir))
    evidence = [
        _evidence_item(source, current_head_sha=resolved_head, root=root)
        for source in evidence_sources
    ]
    missing_or_blocked = [item.name for item in evidence if not item.ready]
    all_evidence_ready = not missing_or_blocked
    release_sha_bound = bool(resolved_head) and resolved_release_sha == resolved_head
    evidence_bound = all(
        item.release_sha == resolved_head and item.current_head_sha == resolved_head
        for item in evidence
    )
    no_forbidden_claims = all(
        not any(field in " ".join(item.errors) for field in FORBIDDEN_TRUE_FIELDS)
        for item in evidence
    )
    ready = all_evidence_ready and release_sha_bound and evidence_bound and no_forbidden_claims

    checks = [
        _check(
            "all_required_ops_support_evidence_ready",
            all_evidence_ready,
            {"missing_or_blocked_evidence": missing_or_blocked},
            "One or more required Ops / Support evidence files are missing, blocked, or malformed.",
        ),
        _check(
            "evidence_bound_to_release_sha",
            evidence_bound,
            {
                "release_sha": resolved_release_sha,
                "current_head_sha": resolved_head,
                "evidence_release_shas": {item.name: item.release_sha for item in evidence},
                "evidence_current_head_shas": {item.name: item.current_head_sha for item in evidence},
            },
            "One or more Ops / Support evidence files are not bound to the current release SHA.",
        ),
        _check(
            "pack_release_sha_bound_to_current_head",
            release_sha_bound,
            {"release_sha": resolved_release_sha, "current_head_sha": resolved_head},
            "Evidence pack release_sha is missing or does not match current head.",
        ),
        _check(
            "no_forbidden_readiness_claims",
            no_forbidden_claims,
            {"forbidden_true_fields": list(FORBIDDEN_TRUE_FIELDS)},
            "One or more source reports claim readiness beyond the controlled pilot boundary.",
        ),
        _check(
            "pack_has_no_side_effects",
            True,
            {
                "mutation_performed": False,
                "outbound_message_sent": False,
                "deploy_tag_release_performed": False,
            },
            "Evidence pack attempted a side effect.",
        ),
    ]

    return OpsEvidencePackReport(
        status="controlled_commercial_pilot_ops_ready" if ready else "ops_support_evidence_blocked",
        generated_at=_utc_now(),
        evidence_type="stage5_ops_support_evidence_pack",
        claim_boundary={
            "allowed": "controlled commercial pilot readiness only",
            "forbidden": [
                "general availability readiness",
                "production readiness",
                "full commercial delivery completion",
                "full Codex parity",
            ],
        },
        current_head_sha=resolved_head,
        release_sha=resolved_release_sha,
        controlled_commercial_pilot_ops_ready=ready,
        mutation_performed=False,
        outbound_message_sent=False,
        deploy_tag_release_performed=False,
        evidence=evidence,
        checks=checks,
        missing_or_blocked_evidence=missing_or_blocked,
        next_actions=_next_actions(missing_or_blocked),
        known_limits=[
            "This pack only summarizes local evidence files and SHA binding.",
            "This pack does not create or simulate real operations readiness evidence.",
            "This pack performs no deployment, release, paging, backup, restore, or support-message mutation.",
        ],
    )


def render_markdown_report(report: OpsEvidencePackReport) -> str:
    evidence_lines = "\n".join(
        f"- {item.name}: `{item.status or '<missing>'}` / ready `{item.ready}` / "
        f"release_sha `{item.release_sha or '<missing>'}`"
        + (f" / errors: {'; '.join(item.errors)}" if item.errors else "")
        for item in report.evidence
    )
    check_lines = "\n".join(
        f"- {check.name}: `{check.status}`" + (f" - {check.error}" if check.error else "")
        for check in report.checks
    )
    missing_lines = "\n".join(f"- {name}" for name in report.missing_or_blocked_evidence) or "- none"
    next_actions = "\n".join(f"- {item}" for item in report.next_actions)
    known_limits = "\n".join(f"- {item}" for item in report.known_limits)
    return (
        "# Stage 5 Ops / Support Evidence Pack\n\n"
        f"- Status: `{report.status}`\n"
        "- Claim boundary: `controlled commercial pilot readiness only`\n"
        f"- Controlled pilot Ops ready: `{report.controlled_commercial_pilot_ops_ready}`\n"
        f"- Current head SHA: `{report.current_head_sha or '<missing>'}`\n"
        f"- Release SHA: `{report.release_sha or '<missing>'}`\n"
        f"- Generated at: `{report.generated_at}`\n"
        f"- Mutation performed: `{report.mutation_performed}`\n"
        f"- Outbound message sent: `{report.outbound_message_sent}`\n"
        f"- Deploy/tag/release performed: `{report.deploy_tag_release_performed}`\n\n"
        "## Evidence\n\n"
        f"{evidence_lines}\n\n"
        "## Missing Or Blocked Evidence\n\n"
        f"{missing_lines}\n\n"
        "## Checks\n\n"
        f"{check_lines}\n\n"
        "## Next Actions\n\n"
        f"{next_actions}\n\n"
        "## Known Limits\n\n"
        f"{known_limits}\n"
    )


def write_report(report: OpsEvidencePackReport, output_path: Path = DEFAULT_OUTPUT_JSON) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(report: OpsEvidencePackReport, output_path: Path = DEFAULT_OUTPUT_MD) -> None:
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
    report = build_ops_evidence_pack(
        report_dir=args.report_dir,
        current_head_sha=args.current_head_sha,
        release_sha=args.release_sha,
    )
    write_report(report, args.output_json)
    write_markdown_report(report, args.output_md)

    print(f"Stage 5 Ops / Support evidence pack status: {report.status}")
    print(f"Current head: {report.current_head_sha or '<missing>'}")
    print(f"Release SHA: {report.release_sha or '<missing>'}")
    print(f"Missing or blocked evidence: {', '.join(report.missing_or_blocked_evidence) or '<none>'}")
    print(f"JSON report written to {args.output_json}")
    print(f"Markdown report written to {args.output_md}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.controlled_commercial_pilot_ops_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
