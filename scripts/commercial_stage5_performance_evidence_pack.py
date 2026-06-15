#!/usr/bin/env python3
"""Build the Stage 5 performance/capacity evidence pack.

This local pack is fail-closed and evidence-only. It summarizes the Stage 5
performance/capacity gate for controlled commercial pilot readiness without
claiming broader release readiness.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scripts.commercial_performance_capacity_gate import (
    DEFAULT_REMOTE_PR_REPORT,
    REPORT_DIR,
    PerformanceCapacityGateReport,
    _display_path,
    build_performance_capacity_gate,
)

DEFAULT_OUTPUT_JSON = REPORT_DIR / "stage5-performance-evidence-pack-20260615.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "stage5-performance-evidence-pack-20260615.md"

REQUIRED_DOMAINS = (
    "load_performance_test",
    "capacity_target",
    "latency_error_rate_thresholds",
    "cost_guardrail",
    "performance_tests_skipped_disposition",
    "resource_sizing",
)


@dataclass(frozen=True)
class EvidenceDomainSummary:
    name: str
    status: str | None
    ready: bool
    current_head_sha: str | None
    release_sha: str | None
    path: str
    details: dict[str, Any] = field(default_factory=dict)
    blocker: str | None = None


@dataclass(frozen=True)
class EvidencePackCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    blocker: str | None = None


@dataclass(frozen=True)
class Stage5PerformanceEvidencePack:
    status: str
    controlled_commercial_pilot_ready: bool
    generated_at: str
    evidence_type: str
    readiness_scope: str
    current_head_sha: str | None
    release_sha: str | None
    mutation_performed: bool
    outbound_message_sent: bool
    deploy_tag_release_performed: bool
    source_gate_status: str
    source_gate_report_path: str | None
    remote_pr_report_path: str
    remote_performance_tests_skipped: bool
    required_domains: list[EvidenceDomainSummary]
    checks: list[EvidencePackCheck]
    missing_or_blocked_evidence: list[str]
    next_actions: list[str]
    known_limits: list[str]
    integration_recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["required_domains"] = [asdict(item) for item in self.required_domains]
        payload["checks"] = [asdict(item) for item in self.checks]
        return payload


def _status(passed: bool) -> str:
    return "passed" if passed else "blocked"


def _check(name: str, passed: bool, details: dict[str, Any], blocker: str) -> EvidencePackCheck:
    return EvidencePackCheck(
        name=name,
        status=_status(passed),
        details=details,
        blocker=None if passed else blocker,
    )


def _domain_summaries(gate: PerformanceCapacityGateReport) -> list[EvidenceDomainSummary]:
    return [
        EvidenceDomainSummary(
            name=item.name,
            status=item.status,
            ready=item.ready,
            current_head_sha=item.current_head_sha,
            release_sha=item.release_sha,
            path=item.path,
            details=dict(item.details),
            blocker=item.error,
        )
        for item in gate.required_evidence
        if item.name in REQUIRED_DOMAINS
    ]


def _missing_required_domain_names(domains: Sequence[EvidenceDomainSummary]) -> list[str]:
    present = {domain.name for domain in domains}
    return [name for name in REQUIRED_DOMAINS if name not in present]


def _next_actions(missing_or_blocked: Sequence[str]) -> list[str]:
    if not missing_or_blocked:
        return [
            "Attach the JSON and Markdown evidence pack to the controlled commercial pilot readiness packet.",
            "Keep the source performance/capacity evidence immutable for the bound release SHA.",
        ]
    return [
        f"Produce or refresh local evidence for {name} and bind it to the release SHA."
        for name in missing_or_blocked
    ] + [
        "Keep controlled commercial pilot readiness blocked until all required performance/capacity evidence is present.",
        "Do not treat skipped performance-tests as acceptable without an explicit disposition artifact.",
    ]


def _integration_recommendations() -> list[str]:
    return [
        "Call this pack after the Stage 5 performance/capacity gate and before owner pilot go/no-go review.",
        "Fail the main controller when status is controlled_commercial_pilot_blocked.",
        "Surface missing_or_blocked_evidence directly in the owner review UI or handoff packet.",
        "Archive both JSON and Markdown outputs with the same release SHA as the commercial pilot readiness packet.",
    ]


def build_stage5_performance_evidence_pack(
    *,
    report_dir: Path = REPORT_DIR,
    remote_pr_report_path: Path | None = None,
    current_head_sha: str | None = None,
    release_sha: str | None = None,
    source_gate_report_path: Path | None = None,
    gate_report: PerformanceCapacityGateReport | None = None,
) -> Stage5PerformanceEvidencePack:
    gate = gate_report or build_performance_capacity_gate(
        report_dir=report_dir,
        remote_pr_report_path=remote_pr_report_path or DEFAULT_REMOTE_PR_REPORT,
        current_head_sha=current_head_sha,
        release_sha=release_sha,
    )
    domains = _domain_summaries(gate)
    missing_domain_names = _missing_required_domain_names(domains)
    blocked = sorted(set(gate.missing_or_blocked_evidence + missing_domain_names))
    all_domains_present = not missing_domain_names
    all_domains_ready = all(domain.ready for domain in domains) and all_domains_present
    skipped_has_disposition = (
        not gate.remote_performance_tests_skipped
        or "performance_tests_skipped_disposition" not in blocked
    )
    release_sha_bound = bool(gate.current_head_sha and gate.release_sha and gate.current_head_sha == gate.release_sha)
    no_side_effects = not (
        gate.mutation_performed
        or gate.outbound_message_sent
        or gate.deploy_tag_release_performed
    )
    ready = bool(gate.performance_capacity_ready and all_domains_ready and skipped_has_disposition and release_sha_bound and no_side_effects)
    checks = [
        _check(
            "all_required_domains_present",
            all_domains_present,
            {"required_domains": list(REQUIRED_DOMAINS), "missing_domains": missing_domain_names},
            "one or more required evidence domains are absent from the source gate",
        ),
        _check(
            "all_required_domains_ready",
            all_domains_ready,
            {"missing_or_blocked_evidence": blocked},
            "one or more required evidence domains are missing, blocked, or SHA-mismatched",
        ),
        _check(
            "skipped_performance_tests_disposed",
            skipped_has_disposition,
            {"remote_performance_tests_skipped": gate.remote_performance_tests_skipped},
            "performance-tests was skipped without an explicit disposition artifact",
        ),
        _check(
            "release_sha_bound",
            release_sha_bound,
            {"current_head_sha": gate.current_head_sha, "release_sha": gate.release_sha},
            "release SHA is missing or not bound to the current head SHA",
        ),
        _check(
            "no_release_side_effects",
            no_side_effects,
            {
                "mutation_performed": gate.mutation_performed,
                "outbound_message_sent": gate.outbound_message_sent,
                "deploy_tag_release_performed": gate.deploy_tag_release_performed,
            },
            "evidence pack or source gate reported a release side effect",
        ),
    ]
    return Stage5PerformanceEvidencePack(
        status="controlled_commercial_pilot_ready" if ready else "controlled_commercial_pilot_blocked",
        controlled_commercial_pilot_ready=ready,
        generated_at=gate.generated_at,
        evidence_type="stage5_performance_capacity_evidence_pack",
        readiness_scope="controlled_commercial_pilot",
        current_head_sha=gate.current_head_sha,
        release_sha=gate.release_sha,
        mutation_performed=False,
        outbound_message_sent=False,
        deploy_tag_release_performed=False,
        source_gate_status=gate.status,
        source_gate_report_path=_display_path(source_gate_report_path) if source_gate_report_path else None,
        remote_pr_report_path=gate.remote_pr_report_path,
        remote_performance_tests_skipped=gate.remote_performance_tests_skipped,
        required_domains=domains,
        checks=checks,
        missing_or_blocked_evidence=blocked,
        next_actions=_next_actions(blocked),
        known_limits=[
            "This pack summarizes existing evidence only; it does not run load tests or create capacity evidence.",
            "Readiness is limited to controlled commercial pilot review.",
            "Missing evidence, SHA mismatch, threshold breach, or skipped performance-tests without disposition keeps the pack blocked.",
        ],
        integration_recommendations=_integration_recommendations(),
    )


def render_markdown_report(pack: Stage5PerformanceEvidencePack) -> str:
    domains = "\n".join(
        f"- {item.name}: `{item.status or '<missing>'}` / ready `{item.ready}` / "
        f"head `{item.current_head_sha or '<missing>'}` / release `{item.release_sha or '<missing>'}`"
        + (f" - {item.blocker}" if item.blocker else "")
        for item in pack.required_domains
    )
    checks = "\n".join(
        f"- {item.name}: `{item.status}`" + (f" - {item.blocker}" if item.blocker else "")
        for item in pack.checks
    )
    missing = "\n".join(f"- {name}" for name in pack.missing_or_blocked_evidence) or "- none"
    actions = "\n".join(f"- {item}" for item in pack.next_actions)
    limits = "\n".join(f"- {item}" for item in pack.known_limits)
    integration = "\n".join(f"- {item}" for item in pack.integration_recommendations)
    return (
        "# Stage 5 Performance Capacity Evidence Pack\n\n"
        f"- Status: `{pack.status}`\n"
        f"- Controlled commercial pilot ready: `{pack.controlled_commercial_pilot_ready}`\n"
        f"- Readiness scope: `{pack.readiness_scope}`\n"
        f"- Current head SHA: `{pack.current_head_sha or '<missing>'}`\n"
        f"- Release SHA: `{pack.release_sha or '<missing>'}`\n"
        f"- Source gate status: `{pack.source_gate_status}`\n"
        f"- Remote performance-tests skipped: `{pack.remote_performance_tests_skipped}`\n"
        f"- Mutation performed: `{pack.mutation_performed}`\n"
        f"- Outbound message sent: `{pack.outbound_message_sent}`\n"
        f"- Deploy/tag/release performed: `{pack.deploy_tag_release_performed}`\n\n"
        "## Required Domains\n\n"
        f"{domains}\n\n"
        "## Missing Or Blocked Evidence\n\n"
        f"{missing}\n\n"
        "## Checks\n\n"
        f"{checks}\n\n"
        "## Next Actions\n\n"
        f"{actions}\n\n"
        "## Integration Recommendations\n\n"
        f"{integration}\n\n"
        "## Known Limits\n\n"
        f"{limits}\n"
    )


def write_json_report(pack: Stage5PerformanceEvidencePack, output_path: Path = DEFAULT_OUTPUT_JSON) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(pack.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(pack: Stage5PerformanceEvidencePack, output_path: Path = DEFAULT_OUTPUT_MD) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(pack), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--remote-pr-report", type=Path, default=DEFAULT_REMOTE_PR_REPORT)
    parser.add_argument("--current-head-sha", default=None)
    parser.add_argument("--release-sha", default=None)
    parser.add_argument("--source-gate-report", type=Path, default=None)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pack = build_stage5_performance_evidence_pack(
        report_dir=args.report_dir,
        remote_pr_report_path=args.remote_pr_report,
        current_head_sha=args.current_head_sha,
        release_sha=args.release_sha,
        source_gate_report_path=args.source_gate_report,
    )
    write_json_report(pack, args.output_json)
    write_markdown_report(pack, args.output_md)
    print(f"Stage 5 performance evidence pack status: {pack.status}")
    print(f"Readiness scope: {pack.readiness_scope}")
    print(f"Current head: {pack.current_head_sha or '<missing>'}")
    print(f"Release SHA: {pack.release_sha or '<missing>'}")
    print(f"Missing or blocked evidence: {', '.join(pack.missing_or_blocked_evidence) or '<none>'}")
    print(f"JSON report written to {args.output_json}")
    print(f"Markdown report written to {args.output_md}")
    for check in pack.checks:
        print(f"- {check.name}: {check.status}")
        if check.blocker:
            print(f"  blocker: {check.blocker}")
    return 0 if pack.controlled_commercial_pilot_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
