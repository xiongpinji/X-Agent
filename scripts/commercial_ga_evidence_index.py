from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "stage5-single-sha-evidence-index-20260615.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "stage5-single-sha-evidence-index-20260615.md"

CLAIM_BOUNDARY = {
    "allowed": "controlled commercial pilot readiness only",
    "excluded_claims": [
        "GA ready",
        "general availability ready",
        "production ready",
        "full commercial delivery complete",
        "full Codex parity",
        "production deploy/tag/release complete",
    ],
}


@dataclass(frozen=True)
class EvidenceSpec:
    name: str
    path: Path
    expected_statuses: tuple[str, ...]
    evidence_level: str
    required: bool = True


@dataclass(frozen=True)
class EvidenceItem:
    name: str
    path: str
    status: str | None
    expected_statuses: list[str]
    sha_fields_found: dict[str, str]
    bound_sha: str | None
    sha_matches_selected: bool
    ready: bool
    evidence_level: str
    error: str | None = None


@dataclass(frozen=True)
class SingleShaEvidenceIndexReport:
    status: str
    single_sha_evidence_index_ready: bool
    selected_sha: str | None
    current_head_sha: str | None
    generated_at: str
    evidence_items: list[EvidenceItem]
    missing_or_mismatched: list[str]
    mutation_performed: bool
    outbound_message_sent: bool
    deploy_tag_release_performed: bool
    claim_boundary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence_items"] = [asdict(item) for item in self.evidence_items]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def _run_git(args: list[str]) -> tuple[str | None, str | None]:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        return None, str(exc)
    if completed.returncode != 0:
        return None, (completed.stderr or completed.stdout).strip() or f"git exited {completed.returncode}"
    return completed.stdout.strip(), None


def resolve_current_head_sha() -> str | None:
    stdout, error = _run_git(["rev-parse", "HEAD"])
    if error:
        return None
    return stdout


def default_evidence_specs(report_dir: Path = REPORT_DIR) -> list[EvidenceSpec]:
    return [
        EvidenceSpec(
            "source_tree",
            report_dir / "stage4-pilot-handoff-package-20260615.json",
            ("stage4_pilot_handoff_ready_with_staging_owner_blocked",),
            "controlled_pilot_source_tree",
        ),
        EvidenceSpec(
            "remote_ci",
            report_dir / "stage3-remote-ci-final-20260615.json",
            ("stage3-remote-ci-final-20260615", "passed"),
            "remote_pr_gate",
        ),
        EvidenceSpec(
            "real_staging_rehearsal",
            report_dir / "stage3-staging-rehearsal-result-20260615.json",
            ("staging_rehearsal_ready", "passed"),
            "ga_required",
        ),
        EvidenceSpec(
            "production_rehearsal",
            report_dir / "stage5-production-rehearsal-result-20260615.json",
            ("production_rehearsal_ready", "passed"),
            "ga_required",
        ),
        EvidenceSpec(
            "security_compliance",
            report_dir / "stage5-security-compliance-gate-20260615.json",
            ("security_compliance_ready", "passed"),
            "ga_required",
        ),
        EvidenceSpec(
            "ops_support",
            report_dir / "stage5-ops-support-gate-20260615.json",
            ("ops_support_ready", "passed"),
            "ga_required",
        ),
        EvidenceSpec(
            "claim_safe_docs",
            report_dir / "stage5-claim-safe-docs-gate-20260615.json",
            ("claim_safe_docs_ready", "passed"),
            "claim_guardrail",
        ),
        EvidenceSpec(
            "performance_capacity",
            report_dir / "stage5-performance-capacity-gate-20260615.json",
            ("performance_capacity_ready", "passed"),
            "ga_required",
        ),
        EvidenceSpec(
            "codex_parity_disposition",
            report_dir / "stage5-codex-parity-disposition-20260615.json",
            ("codex_parity_excluded", "codex_parity_proven", "passed"),
            "claim_guardrail",
        ),
        EvidenceSpec(
            "artifacts_release",
            report_dir / "stage5-artifacts-release-gate-20260615.json",
            ("artifacts_release_ready", "passed"),
            "ga_required",
        ),
        EvidenceSpec(
            "customer_handoff",
            report_dir / "stage4-pilot-handoff-package-20260615.json",
            ("stage4_pilot_handoff_ready_with_staging_owner_blocked", "customer_handoff_ready", "passed"),
            "controlled_pilot_handoff",
        ),
    ]


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


def _status_from_payload(payload: dict[str, Any]) -> str | None:
    for key in ("status", "package_status", "report", "final_gate_status"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    remote_status = payload.get("remote_pr_gate")
    if isinstance(remote_status, dict):
        value = remote_status.get("status")
        if isinstance(value, str) and value:
            return value
    return None


def _is_sha_key(key: str) -> bool:
    lowered = key.lower()
    return lowered == "sha" or lowered.endswith("_sha") or lowered.endswith("sha") or "commit_sha" in lowered


def _collect_sha_fields(value: Any, *, prefix: str = "") -> dict[str, str]:
    found: dict[str, str] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            if _is_sha_key(str(key)) and isinstance(child, str) and child:
                found[child_prefix] = child
            found.update(_collect_sha_fields(child, prefix=child_prefix))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_prefix = f"{prefix}[{index}]"
            found.update(_collect_sha_fields(child, prefix=child_prefix))
    return found


def _bound_sha(sha_fields: dict[str, str]) -> str | None:
    preferred_fragments = (
        "release_sha",
        "current_head_sha",
        "head_sha",
        "remote_branch_sha",
        "selected_sha",
    )
    preferred_values = {
        value
        for key, value in sha_fields.items()
        if value and any(fragment in key.lower() for fragment in preferred_fragments)
    }
    if len(preferred_values) == 1:
        return next(iter(preferred_values))
    if len(preferred_values) > 1:
        return None

    unique_values = {value for value in sha_fields.values() if value}
    if len(unique_values) == 1:
        return next(iter(unique_values))
    return None


def build_evidence_item(spec: EvidenceSpec, *, selected_sha: str | None) -> EvidenceItem:
    payload, read_error = _read_json(spec.path)
    if payload is None:
        return EvidenceItem(
            name=spec.name,
            path=_display_path(spec.path),
            status=None,
            expected_statuses=list(spec.expected_statuses),
            sha_fields_found={},
            bound_sha=None,
            sha_matches_selected=False,
            ready=False,
            evidence_level=spec.evidence_level,
            error=read_error,
        )

    status = _status_from_payload(payload)
    sha_fields_found = _collect_sha_fields(payload)
    bound_sha = _bound_sha(sha_fields_found)
    status_ready = status in spec.expected_statuses
    sha_matches_selected = bool(selected_sha and bound_sha == selected_sha)
    error = None
    if not status_ready:
        error = f"status {status or '<missing>'} not in expected statuses"
    elif not sha_fields_found:
        error = "no SHA fields found in evidence report"
    elif bound_sha is None:
        error = "evidence report contains multiple distinct SHA values"
    elif not sha_matches_selected:
        error = "evidence SHA does not match selected_sha"

    return EvidenceItem(
        name=spec.name,
        path=_display_path(spec.path),
        status=status,
        expected_statuses=list(spec.expected_statuses),
        sha_fields_found=sha_fields_found,
        bound_sha=bound_sha,
        sha_matches_selected=sha_matches_selected,
        ready=status_ready and sha_matches_selected,
        evidence_level=spec.evidence_level,
        error=error,
    )


def build_single_sha_evidence_index(
    *,
    report_dir: Path = REPORT_DIR,
    selected_sha: str | None = None,
    current_head_sha: str | None = None,
    specs: list[EvidenceSpec] | None = None,
) -> SingleShaEvidenceIndexReport:
    resolved_head = current_head_sha or resolve_current_head_sha()
    resolved_selected_sha = selected_sha or resolved_head
    evidence_specs = specs or default_evidence_specs(report_dir)
    evidence_items = [
        build_evidence_item(spec, selected_sha=resolved_selected_sha)
        for spec in evidence_specs
    ]
    missing_or_mismatched = [
        item.name
        for item in evidence_items
        if not item.ready
    ]
    ready = not missing_or_mismatched and resolved_selected_sha is not None
    status = "single_sha_evidence_index_ready" if ready else "single_sha_evidence_index_blocked"
    return SingleShaEvidenceIndexReport(
        status=status,
        single_sha_evidence_index_ready=ready,
        selected_sha=resolved_selected_sha,
        current_head_sha=resolved_head,
        generated_at=_utc_now(),
        evidence_items=evidence_items,
        missing_or_mismatched=missing_or_mismatched,
        mutation_performed=False,
        outbound_message_sent=False,
        deploy_tag_release_performed=False,
        claim_boundary=CLAIM_BOUNDARY,
    )


def render_markdown_report(report: SingleShaEvidenceIndexReport) -> str:
    lines = [
        "# Stage 5 Single-SHA Evidence Index",
        "",
        f"Status: `{report.status}`",
        f"Ready: `{report.single_sha_evidence_index_ready}`",
        f"Selected SHA: `{report.selected_sha or '<missing>'}`",
        f"Current HEAD SHA: `{report.current_head_sha or '<missing>'}`",
        f"Generated at: `{report.generated_at}`",
        "",
        "Claim boundary: controlled commercial pilot readiness only; GA, production-ready, full commercial delivery, and full Codex parity claims remain excluded.",
        "",
        "## Evidence Items",
        "",
        "| Name | Status | SHA match | Ready | Error |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in report.evidence_items:
        error = (item.error or "").replace("|", "\\|")
        lines.append(
            f"| `{item.name}` | `{item.status or '<missing>'}` | `{item.sha_matches_selected}` | `{item.ready}` | {error} |"
        )
    lines.extend(
        [
            "",
            "## Missing Or Mismatched",
            "",
            ", ".join(f"`{name}`" for name in report.missing_or_mismatched) or "`<none>`",
            "",
            "Mutation performed: `False`",
            "Outbound message sent: `False`",
            "Deploy/tag/release performed: `False`",
        ]
    )
    return "\n".join(lines) + "\n"


def write_report(report: SingleShaEvidenceIndexReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(report: SingleShaEvidenceIndexReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Stage 5 single-SHA GA evidence index.")
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--selected-sha", default=None)
    parser.add_argument("--current-head-sha", default=None)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_single_sha_evidence_index(
        report_dir=args.report_dir,
        selected_sha=args.selected_sha,
        current_head_sha=args.current_head_sha,
    )
    write_report(report, args.output_json)
    write_markdown_report(report, args.output_md)
    print(f"Single-SHA evidence index status: {report.status}")
    print(f"Selected SHA: {report.selected_sha or '<missing>'}")
    print(f"Current HEAD SHA: {report.current_head_sha or '<missing>'}")
    print(f"Missing or mismatched: {', '.join(report.missing_or_mismatched) or '<none>'}")
    print(f"Mutation performed: {report.mutation_performed}")
    print(f"Outbound message sent: {report.outbound_message_sent}")
    print(f"Deploy/tag/release performed: {report.deploy_tag_release_performed}")
    print(f"JSON report written to {args.output_json}")
    print(f"Markdown report written to {args.output_md}")
    return 0 if report.single_sha_evidence_index_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
