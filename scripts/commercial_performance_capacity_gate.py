#!/usr/bin/env python3
"""Validate Stage 5 performance and capacity evidence.

This gate is read-only. It fails closed unless performance/load evidence,
capacity targets, latency/error-rate thresholds, cost guardrails, skipped
performance-tests disposition, and resource sizing evidence are all present,
ready, and bound to the current release SHA.
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
DEFAULT_REMOTE_PR_REPORT = REPORT_DIR / "stage3-remote-ci-final-20260615.json"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "stage5-performance-capacity-gate-20260615.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "stage5-performance-capacity-gate-20260615.md"


@dataclass(frozen=True)
class RequiredPerformanceEvidenceSpec:
    name: str
    path: Path
    expected_statuses: tuple[str, ...]
    evidence_level: str
    reason: str


@dataclass(frozen=True)
class PerformanceEvidenceSummary:
    name: str
    path: str
    status: str | None
    expected_statuses: list[str]
    evidence_level: str
    current_head_sha: str | None
    release_sha: str | None
    ready: bool
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class PerformanceCapacityCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class PerformanceCapacityGateReport:
    status: str
    performance_capacity_ready: bool
    generated_at: str
    evidence_type: str
    current_head_sha: str | None
    release_sha: str | None
    mutation_performed: bool
    outbound_message_sent: bool
    deploy_tag_release_performed: bool
    remote_pr_report_path: str
    remote_performance_tests_skipped: bool
    required_evidence: list[PerformanceEvidenceSummary]
    checks: list[PerformanceCapacityCheck]
    missing_or_blocked_evidence: list[str]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["required_evidence"] = [asdict(evidence) for evidence in self.required_evidence]
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_required_evidence(report_dir: Path = REPORT_DIR) -> list[RequiredPerformanceEvidenceSpec]:
    return [
        RequiredPerformanceEvidenceSpec(
            "load_performance_test",
            report_dir / "stage5-load-performance-result-20260615.json",
            ("load_performance_ready", "performance_tests_ready", "passed"),
            "ga_hard_blocker",
            "Real load/performance test execution evidence.",
        ),
        RequiredPerformanceEvidenceSpec(
            "capacity_target",
            report_dir / "stage5-capacity-target-20260615.json",
            ("capacity_target_ready", "passed"),
            "ga_hard_blocker",
            "Documented target throughput, users, or concurrency.",
        ),
        RequiredPerformanceEvidenceSpec(
            "latency_error_rate_thresholds",
            report_dir / "stage5-latency-error-thresholds-20260615.json",
            ("latency_error_thresholds_ready", "latency_error_rate_thresholds_ready", "passed"),
            "ga_hard_blocker",
            "Measured latency and error-rate results within release thresholds.",
        ),
        RequiredPerformanceEvidenceSpec(
            "cost_guardrail",
            report_dir / "stage5-cost-guardrail-20260615.json",
            ("cost_guardrail_ready", "passed"),
            "ga_hard_blocker",
            "Projected runtime cost remains within approved guardrails.",
        ),
        RequiredPerformanceEvidenceSpec(
            "performance_tests_skipped_disposition",
            report_dir / "stage5-performance-tests-skipped-disposition-20260615.json",
            ("performance_tests_skipped_disposition_ready", "performance_tests_skip_disposition_ready", "passed"),
            "ga_hard_blocker",
            "Disposition replacing any skipped remote performance-tests check.",
        ),
        RequiredPerformanceEvidenceSpec(
            "resource_sizing",
            report_dir / "stage5-resource-sizing-20260615.json",
            ("resource_sizing_ready", "passed"),
            "ga_hard_blocker",
            "CPU, memory, replica, queue, or worker sizing evidence.",
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
    value = payload.get("status") or payload.get("report") or payload.get("package_status")
    return str(value) if value is not None else None


def _sha_value(payload: dict[str, Any] | None, key: str) -> str | None:
    if not payload:
        return None
    version_identity = payload.get("version_identity")
    if isinstance(version_identity, dict) and isinstance(version_identity.get(key), str):
        return str(version_identity[key])
    value = payload.get(key)
    if isinstance(value, str) and value:
        return value
    if key == "current_head_sha":
        for fallback in ("head_sha", "commit_sha"):
            value = payload.get(fallback)
            if isinstance(value, str) and value:
                return value
    return None


def _remote_performance_tests_skipped(payload: dict[str, Any] | None) -> bool:
    if not payload:
        return False
    check_runs = payload.get("github_actions_check_runs")
    if not isinstance(check_runs, dict):
        return False
    skipped_checks = check_runs.get("skipped_checks")
    if isinstance(skipped_checks, list):
        return any(str(check).casefold() == "performance-tests" for check in skipped_checks)
    return False


def _number(payload: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return None


def _nested_dict(payload: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _truthy_evidence(payload: dict[str, Any], keys: tuple[str, ...]) -> bool:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, dict | list) and len(value) > 0:
            return True
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, int | float) and not isinstance(value, bool):
            return True
    return False


def _threshold_details(payload: dict[str, Any]) -> tuple[bool, dict[str, Any], str | None]:
    metrics = _nested_dict(payload, ("metrics", "results", "measurements"))
    thresholds = _nested_dict(payload, ("thresholds", "limits", "guardrails"))
    source = {**metrics, **payload}
    limit_source = {**thresholds, **payload}
    p95 = _number(source, ("latency_p95_ms", "p95_latency_ms", "p95_ms"))
    max_p95 = _number(limit_source, ("max_latency_p95_ms", "latency_p95_threshold_ms", "p95_latency_threshold_ms"))
    p99 = _number(source, ("latency_p99_ms", "p99_latency_ms", "p99_ms"))
    max_p99 = _number(limit_source, ("max_latency_p99_ms", "latency_p99_threshold_ms", "p99_latency_threshold_ms"))
    error_rate = _number(source, ("error_rate", "error_rate_percent", "errors_percent"))
    max_error_rate = _number(limit_source, ("max_error_rate", "max_error_rate_percent", "error_rate_threshold"))
    details = {
        "latency_p95_ms": p95,
        "max_latency_p95_ms": max_p95,
        "latency_p99_ms": p99,
        "max_latency_p99_ms": max_p99,
        "error_rate": error_rate,
        "max_error_rate": max_error_rate,
    }
    problems: list[str] = []
    if p95 is None or max_p95 is None:
        problems.append("missing p95 latency threshold evidence")
    elif p95 > max_p95:
        problems.append("p95 latency threshold breached")
    if p99 is not None and max_p99 is not None and p99 > max_p99:
        problems.append("p99 latency threshold breached")
    if error_rate is None or max_error_rate is None:
        problems.append("missing error-rate threshold evidence")
    elif error_rate > max_error_rate:
        problems.append("error-rate threshold breached")
    return not problems, details, "; ".join(problems) if problems else None


def _cost_details(payload: dict[str, Any]) -> tuple[bool, dict[str, Any], str | None]:
    cost = _number(payload, ("estimated_monthly_cost", "projected_monthly_cost", "projected_cost"))
    limit = _number(payload, ("max_monthly_cost", "monthly_cost_budget", "cost_guardrail"))
    details = {"estimated_monthly_cost": cost, "max_monthly_cost": limit}
    if cost is None or limit is None:
        return False, details, "missing cost guardrail values"
    if cost > limit:
        return False, details, "cost guardrail breached"
    return True, details, None


def _domain_gate(name: str, payload: dict[str, Any] | None) -> tuple[bool, dict[str, Any], str | None]:
    if not payload:
        return False, {}, "missing payload"
    if name == "latency_error_rate_thresholds":
        return _threshold_details(payload)
    if name == "cost_guardrail":
        return _cost_details(payload)
    if name == "capacity_target":
        ready = _truthy_evidence(payload, ("capacity_target", "target_rps", "target_concurrency", "concurrent_users"))
        return ready, {}, None if ready else "missing capacity target evidence"
    if name == "resource_sizing":
        ready = _truthy_evidence(payload, ("resource_sizing", "resources", "replicas", "cpu", "memory"))
        return ready, {}, None if ready else "missing resource sizing evidence"
    if name == "performance_tests_skipped_disposition":
        disposed = payload.get("performance_tests_skipped_disposition") is True or payload.get("skipped_check") == "performance-tests"
        return disposed, {"performance_tests_skipped_disposition": disposed}, None if disposed else "missing performance-tests skipped disposition"
    if name == "load_performance_test":
        ready = _truthy_evidence(payload, ("load_test", "performance_test", "test_run_url", "run_id", "results"))
        return ready, {}, None if ready else "missing load/performance test evidence"
    return True, {}, None


def _evidence_summary(
    spec: RequiredPerformanceEvidenceSpec,
    *,
    current_head_sha: str | None,
    release_sha: str | None,
) -> tuple[PerformanceEvidenceSummary, dict[str, Any] | None]:
    payload, read_error = _read_json(spec.path)
    status = _status(payload)
    evidence_head = _sha_value(payload, "current_head_sha")
    evidence_release_sha = _sha_value(payload, "release_sha")
    status_ready = status in spec.expected_statuses
    head_matches = bool(current_head_sha) and evidence_head == current_head_sha
    release_matches = bool(release_sha) and evidence_release_sha == release_sha
    domain_ready, domain_details, domain_error = _domain_gate(spec.name, payload)
    problems: list[str] = []
    if read_error:
        problems.append(read_error)
    if not status_ready:
        problems.append(f"status {status or '<missing>'} not in expected statuses")
    if not head_matches:
        problems.append("current_head_sha missing or not bound to gate head")
    if not release_matches:
        problems.append("release_sha missing or not bound to gate release")
    if not domain_ready and domain_error:
        problems.append(domain_error)
    ready = not problems
    return (
        PerformanceEvidenceSummary(
            name=spec.name,
            path=_display_path(spec.path),
            status=status,
            expected_statuses=list(spec.expected_statuses),
            evidence_level=spec.evidence_level,
            current_head_sha=evidence_head,
            release_sha=evidence_release_sha,
            ready=ready,
            details=domain_details,
            error="; ".join(problems) if problems else None,
        ),
        payload,
    )


def _check(name: str, passed: bool, details: dict[str, Any], error: str) -> PerformanceCapacityCheck:
    return PerformanceCapacityCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details,
        error=None if passed else error,
    )


def _next_actions(missing_or_blocked: Sequence[str]) -> list[str]:
    if not missing_or_blocked:
        return ["Archive the performance/capacity gate JSON and Markdown reports with the Stage 5 release packet."]
    return [
        f"Produce or refresh performance/capacity evidence for {name}." for name in missing_or_blocked
    ] + ["Do not promote GA performance/capacity readiness while any evidence is missing, skipped, or SHA-mismatched."]


def build_performance_capacity_gate(
    *,
    report_dir: Path = REPORT_DIR,
    remote_pr_report_path: Path | None = None,
    required_specs: Sequence[RequiredPerformanceEvidenceSpec] | None = None,
    current_head_sha: str | None = None,
    release_sha: str | None = None,
) -> PerformanceCapacityGateReport:
    current_head_sha = current_head_sha or _git_value(["rev-parse", "HEAD"])
    release_sha = release_sha or current_head_sha
    specs = list(required_specs or default_required_evidence(report_dir))
    remote_path = remote_pr_report_path or report_dir / DEFAULT_REMOTE_PR_REPORT.name
    remote_payload, remote_error = _read_json(remote_path)
    remote_skipped = _remote_performance_tests_skipped(remote_payload)
    evidence_pairs = [
        _evidence_summary(spec, current_head_sha=current_head_sha, release_sha=release_sha)
        for spec in specs
    ]
    required_evidence = [pair[0] for pair in evidence_pairs]
    evidence_by_name = {evidence.name: evidence for evidence in required_evidence}
    missing_or_blocked = [evidence.name for evidence in required_evidence if not evidence.ready]

    all_evidence_ready = all(evidence.ready for evidence in required_evidence)
    skipped_disposition = evidence_by_name.get("performance_tests_skipped_disposition")
    skipped_disposed = bool(skipped_disposition and skipped_disposition.ready)
    release_resolved = bool(current_head_sha and release_sha)
    remote_bound = (
        not remote_error
        and bool(current_head_sha)
        and _sha_value(remote_payload, "current_head_sha") == current_head_sha
    )
    skipped_gate_ready = (not remote_skipped) or skipped_disposed
    if remote_skipped and not skipped_disposed and "performance_tests_skipped_disposition" not in missing_or_blocked:
        missing_or_blocked.append("performance_tests_skipped_disposition")
    if remote_error and "remote_pr_performance_skip_source" not in missing_or_blocked:
        missing_or_blocked.append("remote_pr_performance_skip_source")

    checks = [
        _check(
            "release_sha_resolved",
            release_resolved,
            {"current_head_sha": current_head_sha, "release_sha": release_sha},
            "current head or release SHA could not be resolved",
        ),
        _check(
            "all_required_performance_capacity_evidence_ready",
            all_evidence_ready,
            {"missing_or_blocked_evidence": missing_or_blocked},
            "required performance/capacity evidence is missing, blocked, or mismatched",
        ),
        _check(
            "remote_pr_performance_tests_skip_source_readable",
            remote_error is None,
            {"remote_pr_report_path": _display_path(remote_path), "error": remote_error},
            "remote PR report is missing or unreadable",
        ),
        _check(
            "remote_pr_report_bound_to_current_head",
            remote_bound,
            {
                "remote_head_sha": _sha_value(remote_payload, "current_head_sha"),
                "current_head_sha": current_head_sha,
            },
            "remote PR report is not bound to current head",
        ),
        _check(
            "skipped_performance_tests_disposition_ready",
            skipped_gate_ready,
            {
                "remote_performance_tests_skipped": remote_skipped,
                "disposition_ready": skipped_disposed,
            },
            "remote performance-tests check is skipped without a ready disposition",
        ),
        _check(
            "gate_has_no_release_side_effects",
            True,
            {"mutation_performed": False, "outbound_message_sent": False, "deploy_tag_release_performed": False},
            "gate attempted a release side effect",
        ),
    ]
    ready = all(check.status == "passed" for check in checks)
    return PerformanceCapacityGateReport(
        status="performance_capacity_ready" if ready else "performance_capacity_blocked",
        performance_capacity_ready=ready,
        generated_at=_utc_now(),
        evidence_type="stage5_performance_capacity_gate",
        current_head_sha=current_head_sha,
        release_sha=release_sha,
        mutation_performed=False,
        outbound_message_sent=False,
        deploy_tag_release_performed=False,
        remote_pr_report_path=_display_path(remote_path),
        remote_performance_tests_skipped=remote_skipped,
        required_evidence=required_evidence,
        checks=checks,
        missing_or_blocked_evidence=missing_or_blocked,
        next_actions=_next_actions(missing_or_blocked),
        known_limits=[
            "This gate validates evidence only; it does not run load tests, resize infrastructure, deploy, tag, release, or send messages.",
            "Skipped remote performance-tests require an explicit disposition report before readiness can pass.",
        ],
    )


def render_markdown_report(report: PerformanceCapacityGateReport) -> str:
    evidence = "\n".join(
        f"- {item.name}: `{item.status or '<missing>'}` / ready `{item.ready}` / "
        f"head `{item.current_head_sha or '<missing>'}` / release `{item.release_sha or '<missing>'}`"
        + (f" - {item.error}" if item.error else "")
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
        "# Stage 5 Performance Capacity Gate\n\n"
        f"- Status: `{report.status}`\n"
        f"- Ready: `{report.performance_capacity_ready}`\n"
        f"- Current head SHA: `{report.current_head_sha or '<missing>'}`\n"
        f"- Release SHA: `{report.release_sha or '<missing>'}`\n"
        f"- Generated at: `{report.generated_at}`\n"
        f"- Remote performance-tests skipped: `{report.remote_performance_tests_skipped}`\n"
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


def write_report(report: PerformanceCapacityGateReport, output_path: Path = DEFAULT_OUTPUT_JSON) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(report: PerformanceCapacityGateReport, output_path: Path = DEFAULT_OUTPUT_MD) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--remote-pr-report", type=Path, default=DEFAULT_REMOTE_PR_REPORT)
    parser.add_argument("--current-head-sha", default=None)
    parser.add_argument("--release-sha", default=None)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_performance_capacity_gate(
        report_dir=args.report_dir,
        remote_pr_report_path=args.remote_pr_report,
        current_head_sha=args.current_head_sha,
        release_sha=args.release_sha,
    )
    write_report(report, args.output_json)
    write_markdown_report(report, args.output_md)
    print(f"Stage 5 performance/capacity gate status: {report.status}")
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
    return 0 if report.performance_capacity_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
