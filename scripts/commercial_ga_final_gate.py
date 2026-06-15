#!/usr/bin/env python3
"""Run the Stage 5 commercial GA final gate.

This gate distinguishes a controlled pilot handoff from full commercial GA.
It reads evidence reports only and writes a local gate report. It does not
deploy, tag, release, trigger workflows, or send customer/channel messages.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, ROOT, _utc_now

DEFAULT_STAGE4_PACKAGE = REPORT_DIR / "stage4-pilot-handoff-package-20260615.json"
DEFAULT_REMOTE_PR_REPORT = REPORT_DIR / "stage3-remote-ci-final-20260615.json"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-ga-final-gate.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-ga-final-gate.md"


@dataclass(frozen=True)
class RequiredEvidenceSpec:
    name: str
    path: Path
    expected_statuses: tuple[str, ...]
    evidence_level: str
    reason: str


@dataclass(frozen=True)
class GAEvidenceSummary:
    name: str
    path: str
    status: str | None
    expected_statuses: list[str]
    evidence_level: str
    sha256: str | None
    size_bytes: int | None
    release_sha: str | None
    ready: bool
    error: str | None = None


@dataclass(frozen=True)
class GAFinalGateCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class GAFinalGateReport:
    status: str
    generated_at: str
    evidence_type: str
    branch: str | None
    current_head_sha: str | None
    remote_branch_sha: str | None
    release_sha: str | None
    ga_ready: bool
    production_ready: bool
    full_commercial_delivery_complete: bool
    controlled_pilot_ready: bool
    full_codex_parity_claimed: bool
    mutation_performed: bool
    outbound_message_sent: bool
    deploy_tag_release_performed: bool
    stage4_package_status: str | None
    remote_pr_gate_status: str | None
    required_evidence: list[GAEvidenceSummary]
    checks: list[GAFinalGateCheck]
    missing_or_blocked_evidence: list[str]
    claim_boundary: dict[str, Any]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["required_evidence"] = [asdict(evidence) for evidence in self.required_evidence]
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def default_required_evidence(report_dir: Path = REPORT_DIR) -> list[RequiredEvidenceSpec]:
    return [
        RequiredEvidenceSpec(
            "real_staging_rehearsal",
            report_dir / "stage3-staging-rehearsal-result-20260615.json",
            ("staging_rehearsal_ready", "passed"),
            "ga_hard_blocker",
            "Real staging deploy, smoke, rollback, and observability proof.",
        ),
        RequiredEvidenceSpec(
            "production_rehearsal",
            report_dir / "stage5-production-rehearsal-result-20260615.json",
            ("production_rehearsal_ready", "passed"),
            "ga_hard_blocker",
            "Production or production-equivalent deploy, smoke, rollback, and release proof.",
        ),
        RequiredEvidenceSpec(
            "security_compliance",
            report_dir / "stage5-security-compliance-gate-20260615.json",
            ("security_compliance_ready", "passed"),
            "ga_hard_blocker",
            "Security scanner, risk acceptance, tenant/RBAC/audit, retention, and compliance proof.",
        ),
        RequiredEvidenceSpec(
            "ops_support",
            report_dir / "stage5-ops-support-gate-20260615.json",
            ("ops_support_ready", "passed"),
            "ga_hard_blocker",
            "SLO/SLA, alerting, backup/restore, incident, capacity, cost, and support proof.",
        ),
        RequiredEvidenceSpec(
            "claim_safe_docs",
            report_dir / "stage5-claim-safe-docs-gate-20260615.json",
            ("claim_safe_docs_ready", "passed"),
            "claim_guardrail",
            "Customer-facing docs and release notes mapped to current evidence.",
        ),
        RequiredEvidenceSpec(
            "single_sha_evidence_index",
            report_dir / "stage5-single-sha-evidence-index-20260615.json",
            ("single_sha_evidence_index_ready", "passed"),
            "ga_hard_blocker",
            "Every GA claim bound to one release SHA, run URL, artifact digest, image digest, and rollback target.",
        ),
        RequiredEvidenceSpec(
            "performance_capacity",
            report_dir / "stage5-performance-capacity-gate-20260615.json",
            ("performance_capacity_ready", "passed"),
            "ga_hard_blocker",
            "Performance, capacity, and cost readiness replacing the skipped PR performance check.",
        ),
        RequiredEvidenceSpec(
            "codex_parity_disposition",
            report_dir / "stage5-codex-parity-disposition-20260615.json",
            ("codex_parity_excluded", "codex_parity_proven", "passed"),
            "claim_guardrail",
            "Full Codex parity is either proven by runtime/API/UI evidence or explicitly excluded.",
        ),
    ]


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
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


def _sha256_file(path: Path) -> tuple[str | None, int | None, str | None]:
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None, None, f"report not found: {_display_path(path)}"
    except OSError as exc:
        return None, None, f"could not read report {_display_path(path)}: {exc}"
    return hashlib.sha256(data).hexdigest(), len(data), None


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


def _git_status_lines() -> list[str]:
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ["<git status unavailable>"]
    if completed.returncode != 0:
        return ["<git status failed>"]
    return [line for line in completed.stdout.splitlines() if line.strip()]


def _status(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    value = payload.get("status") or payload.get("package_status") or payload.get("report")
    return str(value) if value is not None else None


def _release_sha(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    version_identity = payload.get("version_identity")
    if isinstance(version_identity, dict) and version_identity.get("current_head_sha"):
        return str(version_identity["current_head_sha"])
    for key in ("release_sha", "current_head_sha", "head_sha", "commit_sha"):
        if payload.get(key):
            return str(payload[key])
    return None


def _boolean_claim(payloads: Sequence[dict[str, Any] | None], key: str) -> bool:
    return any(isinstance(payload, dict) and payload.get(key) is True for payload in payloads)


def _evidence_summary(spec: RequiredEvidenceSpec) -> tuple[GAEvidenceSummary, dict[str, Any] | None]:
    payload, read_error = _read_json(spec.path)
    sha256, size_bytes, digest_error = _sha256_file(spec.path)
    status = _status(payload)
    ready = status in spec.expected_statuses and not read_error and not digest_error
    return (
        GAEvidenceSummary(
            name=spec.name,
            path=_display_path(spec.path),
            status=status,
            expected_statuses=list(spec.expected_statuses),
            evidence_level=spec.evidence_level,
            sha256=sha256,
            size_bytes=size_bytes,
            release_sha=_release_sha(payload),
            ready=ready,
            error=read_error or digest_error or None if ready else read_error or digest_error,
        ),
        payload,
    )


def _check(name: str, passed: bool, details: dict[str, Any], error: str) -> GAFinalGateCheck:
    return GAFinalGateCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details,
        error=None if passed else error,
    )


def _remote_pr_gate_status(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    check_runs = payload.get("github_actions_check_runs")
    if not isinstance(check_runs, dict):
        return None
    if check_runs.get("failed") == 0 and check_runs.get("in_progress") == 0:
        return "passed"
    return "not_met"


def _claim_scan_gate(payload: dict[str, Any] | None) -> tuple[bool, dict[str, Any]]:
    status = _status(payload)
    violations = payload.get("violations") if isinstance(payload, dict) else None
    violation_count = len(violations) if isinstance(violations, list) else None
    ready_flag = payload.get("claim_safe_docs_ready") if isinstance(payload, dict) else None
    ready = (
        status in {"claim_safe_docs_ready", "passed"}
        and ready_flag is not False
        and violation_count in {None, 0}
    )
    return ready, {
        "status": status,
        "claim_safe_docs_ready": ready_flag,
        "violation_count": violation_count,
        "blocked_phrase_count": payload.get("blocked_phrase_count") if isinstance(payload, dict) else None,
    }


def _single_sha_index_gate(
    payload: dict[str, Any] | None,
    *,
    current_head_sha: str | None,
) -> tuple[bool, dict[str, Any]]:
    status = _status(payload)
    missing = payload.get("missing_or_mismatched") if isinstance(payload, dict) else None
    missing_count = len(missing) if isinstance(missing, list) else None
    selected_sha = payload.get("selected_sha") if isinstance(payload, dict) else None
    index_head = payload.get("current_head_sha") if isinstance(payload, dict) else None
    ready_flag = payload.get("single_sha_evidence_index_ready") if isinstance(payload, dict) else None
    selected_sha_matches = not selected_sha or not current_head_sha or selected_sha == current_head_sha
    index_head_matches = not index_head or not current_head_sha or index_head == current_head_sha
    ready = (
        status in {"single_sha_evidence_index_ready", "passed"}
        and ready_flag is not False
        and missing_count in {None, 0}
        and selected_sha_matches
        and index_head_matches
    )
    return ready, {
        "status": status,
        "single_sha_evidence_index_ready": ready_flag,
        "selected_sha": selected_sha,
        "current_head_sha": current_head_sha,
        "index_current_head_sha": index_head,
        "missing_or_mismatched": missing if isinstance(missing, list) else None,
        "selected_sha_matches_current_head": selected_sha_matches,
        "index_head_matches_current_head": index_head_matches,
    }


def _next_actions(missing_or_blocked: Sequence[str]) -> list[str]:
    if not missing_or_blocked:
        return [
            "Archive commercial-ga-final-gate.json and commercial-ga-final-gate.md with the GA release packet.",
            "Use the same release SHA for tag, release, deploy, and customer docs.",
        ]
    return [
        f"Produce or refresh GA evidence for {name}." for name in missing_or_blocked
    ] + [
        "Keep customer-facing wording bounded to controlled pilot readiness until this gate returns commercial_ga_ready.",
        "Do not deploy, tag, release, or send customer messages from this gate script.",
    ]


def _known_limits(status: str) -> list[str]:
    if status == "commercial_ga_ready":
        return [
            "This gate proves GA evidence presence and consistency only; actual deploy/tag/release steps remain separate owner-approved operations.",
            "Full Codex parity may be claimed only if the parity disposition evidence explicitly proves it.",
        ]
    return [
        "Controlled commercial pilot evidence cannot be promoted to GA evidence.",
        "Real staging and production proof must be supplied by separate owner-approved operations.",
        "Security, compliance, ops, support, claim-safe docs, single-SHA, and performance evidence remain mandatory.",
        "Full Codex parity is not claimed by this gate.",
    ]


def build_ga_final_gate_report(
    *,
    report_dir: Path = REPORT_DIR,
    stage4_package_path: Path | None = None,
    remote_pr_report_path: Path | None = None,
    required_specs: Sequence[RequiredEvidenceSpec] | None = None,
    branch: str | None = None,
    current_head_sha: str | None = None,
    remote_branch_sha: str | None = None,
    git_status_lines: Sequence[str] | None = None,
    remote_branch: str = "origin/feat/commercial-delivery-v1",
) -> GAFinalGateReport:
    stage4_path = stage4_package_path or report_dir / DEFAULT_STAGE4_PACKAGE.name
    remote_path = remote_pr_report_path or report_dir / DEFAULT_REMOTE_PR_REPORT.name
    required_specs = list(required_specs or default_required_evidence(report_dir))
    stage4_payload, _stage4_error = _read_json(stage4_path)
    remote_payload, _remote_error = _read_json(remote_path)
    evidence_pairs = [_evidence_summary(spec) for spec in required_specs]
    required_evidence = [pair[0] for pair in evidence_pairs]
    required_payloads = [pair[1] for pair in evidence_pairs]
    required_payload_by_name = {
        spec.name: payload for spec, (_summary, payload) in zip(required_specs, evidence_pairs, strict=False)
    }

    branch = branch or _git_value(["rev-parse", "--abbrev-ref", "HEAD"])
    current_head_sha = current_head_sha or _git_value(["rev-parse", "HEAD"])
    remote_branch_sha = remote_branch_sha or _git_value(["rev-parse", remote_branch])
    status_lines = list(git_status_lines if git_status_lines is not None else _git_status_lines())

    stage4_status = _status(stage4_payload)
    remote_gate_status = _remote_pr_gate_status(remote_payload)
    controlled_pilot_ready = stage4_status == "stage4_pilot_handoff_ready_with_staging_owner_blocked"
    stage4_head = _release_sha(stage4_payload)
    remote_head = _release_sha(remote_payload)

    missing_or_blocked = [evidence.name for evidence in required_evidence if not evidence.ready]
    claim_scan_ready, claim_scan_details = _claim_scan_gate(required_payload_by_name.get("claim_safe_docs"))
    single_sha_index_ready, single_sha_index_details = _single_sha_index_gate(
        required_payload_by_name.get("single_sha_evidence_index"),
        current_head_sha=current_head_sha,
    )
    for name, ready in (
        ("claim_safe_docs", claim_scan_ready),
        ("single_sha_evidence_index", single_sha_index_ready),
    ):
        if not ready and name not in missing_or_blocked:
            missing_or_blocked.append(name)
    ready_evidence_shas = {
        evidence.name: evidence.release_sha for evidence in required_evidence if evidence.ready
    }
    same_sha_evidence = all(
        evidence.release_sha == current_head_sha
        for evidence in required_evidence
        if evidence.ready and evidence.release_sha
    )
    all_required_ready = all(evidence.ready for evidence in required_evidence) and claim_scan_ready and single_sha_index_ready
    current_head_remote_bound = bool(current_head_sha) and remote_branch_sha == current_head_sha
    stage4_current_bound = bool(current_head_sha) and stage4_head == current_head_sha
    remote_gate_current_bound = bool(current_head_sha) and remote_head == current_head_sha
    worktree_clean = len(status_lines) == 0
    payloads: list[dict[str, Any] | None] = [stage4_payload, remote_payload, *required_payloads]
    source_claims_ga = _boolean_claim(payloads, "ga_ready")
    source_claims_full_delivery = _boolean_claim(payloads, "full_commercial_delivery_complete")
    source_claims_production = _boolean_claim(payloads, "production_ready")
    source_claims_full_parity = _boolean_claim(payloads, "full_codex_parity_claimed")
    parity_proven = any(_status(payload) == "codex_parity_proven" for payload in required_payloads)
    no_unsupported_claim_flags = not (
        source_claims_ga
        or source_claims_full_delivery
        or source_claims_production
        or (source_claims_full_parity and not parity_proven)
    )

    checks = [
        _check(
            "stage4_controlled_pilot_package_ready",
            controlled_pilot_ready,
            {"stage4_package_status": stage4_status, "stage4_head": stage4_head},
            "Stage 4 controlled pilot handoff package is missing or not ready.",
        ),
        _check(
            "remote_pr_gate_current_head_passed",
            remote_gate_status == "passed" and remote_gate_current_bound,
            {"remote_pr_gate_status": remote_gate_status, "remote_head": remote_head},
            "Remote PR gate is missing, not passed, or not bound to current head.",
        ),
        _check(
            "current_head_matches_remote_branch",
            current_head_remote_bound,
            {"current_head_sha": current_head_sha, "remote_branch_sha": remote_branch_sha},
            "Current head does not match the remote branch head.",
        ),
        _check(
            "stage4_package_bound_to_current_head",
            stage4_current_bound,
            {"current_head_sha": current_head_sha, "stage4_head": stage4_head},
            "Stage 4 package is not bound to current head.",
        ),
        _check(
            "claim_safe_docs_gate_ready",
            claim_scan_ready,
            claim_scan_details,
            "Claim-safe docs gate is missing, blocked, or has unallowlisted violations.",
        ),
        _check(
            "single_sha_evidence_index_gate_ready",
            single_sha_index_ready,
            single_sha_index_details,
            "Single-SHA evidence index is missing, blocked, mismatched, or incomplete.",
        ),
        _check(
            "all_required_ga_evidence_ready",
            all_required_ready,
            {"missing_or_blocked_evidence": missing_or_blocked},
            "One or more required GA evidence reports are missing or not ready.",
        ),
        _check(
            "ready_evidence_bound_to_current_head",
            same_sha_evidence,
            {"ready_evidence_release_shas": ready_evidence_shas, "current_head_sha": current_head_sha},
            "One or more ready GA evidence reports are not bound to current head.",
        ),
        _check(
            "release_worktree_boundary_clean",
            worktree_clean,
            {"dirty_entry_count": len(status_lines), "sample": status_lines[:20]},
            "Worktree is dirty; GA package boundary is not clean.",
        ),
        _check(
            "no_unsupported_ga_or_parity_claim_flags",
            no_unsupported_claim_flags,
            {
                "ga_ready_claimed_by_sources": source_claims_ga,
                "production_ready_claimed_by_sources": source_claims_production,
                "full_commercial_delivery_claimed_by_sources": source_claims_full_delivery,
                "full_codex_parity_claimed_by_sources": source_claims_full_parity,
                "parity_proven": parity_proven,
            },
            "A source report claims GA, production, full delivery, or unsupported full parity before the final gate passes.",
        ),
    ]
    ga_ready = all(check.status == "passed" for check in checks)
    status = "commercial_ga_ready" if ga_ready else "commercial_ga_blocked"
    return GAFinalGateReport(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_ga_final_gate",
        branch=branch,
        current_head_sha=current_head_sha,
        remote_branch_sha=remote_branch_sha,
        release_sha=current_head_sha if ga_ready else None,
        ga_ready=ga_ready,
        production_ready=ga_ready,
        full_commercial_delivery_complete=ga_ready,
        controlled_pilot_ready=controlled_pilot_ready,
        full_codex_parity_claimed=source_claims_full_parity and parity_proven and ga_ready,
        mutation_performed=False,
        outbound_message_sent=False,
        deploy_tag_release_performed=False,
        stage4_package_status=stage4_status,
        remote_pr_gate_status=remote_gate_status,
        required_evidence=required_evidence,
        checks=checks,
        missing_or_blocked_evidence=missing_or_blocked,
        claim_boundary={
            "allowed_when_blocked": "controlled commercial pilot readiness only",
            "allowed_when_ready": "commercial GA readiness for the bound release SHA",
            "forbidden_until_ready": [
                "GA ready",
                "production ready",
                "full commercial delivery complete",
                "full Codex parity unless explicitly proven",
                "staging proven without real staging evidence",
            ],
        },
        next_actions=_next_actions(missing_or_blocked),
        known_limits=_known_limits(status),
    )


def render_markdown_report(report: GAFinalGateReport) -> str:
    checks = "\n".join(
        f"- {check.name}: `{check.status}`" + (f" - {check.error}" if check.error else "")
        for check in report.checks
    )
    evidence = "\n".join(
        f"- {item.name}: `{item.status or '<missing>'}` / ready `{item.ready}` / sha `{item.release_sha or '<missing>'}`"
        for item in report.required_evidence
    )
    missing = "\n".join(f"- {name}" for name in report.missing_or_blocked_evidence) or "- none"
    actions = "\n".join(f"- {item}" for item in report.next_actions)
    limits = "\n".join(f"- {item}" for item in report.known_limits)
    return (
        "# Commercial GA Final Gate\n\n"
        f"- Status: `{report.status}`\n"
        f"- Generated at: `{report.generated_at}`\n"
        f"- Branch: `{report.branch}`\n"
        f"- Current head: `{report.current_head_sha}`\n"
        f"- Remote branch head: `{report.remote_branch_sha}`\n"
        f"- GA ready: `{report.ga_ready}`\n"
        f"- Production ready: `{report.production_ready}`\n"
        f"- Full commercial delivery complete: `{report.full_commercial_delivery_complete}`\n"
        f"- Controlled pilot ready: `{report.controlled_pilot_ready}`\n"
        f"- Full Codex parity claimed: `{report.full_codex_parity_claimed}`\n"
        f"- Mutation performed by gate: `{report.mutation_performed}`\n"
        f"- Outbound message sent by gate: `{report.outbound_message_sent}`\n"
        f"- Deploy/tag/release performed by gate: `{report.deploy_tag_release_performed}`\n\n"
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


def write_report(report: GAFinalGateReport, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(report: GAFinalGateReport, output_path: Path = DEFAULT_MARKDOWN_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--remote-branch", default="origin/feat/commercial-delivery-v1")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_ga_final_gate_report(report_dir=args.report_dir, remote_branch=args.remote_branch)
    write_report(report, args.output_json)
    write_markdown_report(report, args.output_md)
    print(f"Commercial GA final gate status: {report.status}")
    print(f"Current head: {report.current_head_sha or '<missing>'}")
    print(f"GA ready: {report.ga_ready}")
    print(f"Controlled pilot ready: {report.controlled_pilot_ready}")
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
    return 0 if report.ga_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
