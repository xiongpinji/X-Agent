#!/usr/bin/env python3
"""Build the Stage 5 Codex parity disposition report.

This gate is intentionally fail-safe. It can satisfy the commercial GA final
gate by recording that full Codex parity is excluded from the current claim
boundary, or it can block when parity is asserted without sufficient evidence.
It does not prove GA, production readiness, or full commercial delivery.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_CLAIM_BOUNDARY_REPORT = REPORT_DIR / "stage5-claim-safe-docs-gate-20260615.json"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "stage5-codex-parity-disposition-20260615.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "stage5-codex-parity-disposition-20260615.md"

EXCLUDED_STATUS = "codex_parity_excluded"
BLOCKED_STATUS = "codex_parity_blocked"

CLAIM_BOUNDARY = {
    "allowed": "controlled commercial pilot readiness only",
    "excluded_claims": [
        "full Codex parity",
        "full parity",
        "full competitor parity",
        "GA ready",
        "production ready",
    ],
}

PROVEN_STATUS_VALUES = {"codex_parity_proven", "parity_proven", "passed"}
PARITY_CLAIM_KEYS = (
    "full_codex_parity_claimed",
    "codex_parity_proven",
    "full_parity_claimed",
    "full_competitor_parity_claimed",
)
REQUIRED_PROOF_REF_KEYS = (
    "runtime_evidence_refs",
    "api_evidence_refs",
    "ui_evidence_refs",
    "acceptance_evidence_refs",
)


@dataclass(frozen=True)
class SourceDisposition:
    path: str
    status: str | None
    boundary_excludes_full_codex_parity: bool
    parity_proven_claimed: bool
    parity_proof_sufficient: bool
    missing_proof_refs: list[str]
    error: str | None = None


@dataclass(frozen=True)
class CodexParityDispositionReport:
    status: str
    codex_parity_disposition_satisfied: bool
    generated_at: str
    evidence_type: str
    current_head_sha: str | None
    release_sha: str | None
    full_codex_parity_claimed: bool
    full_codex_parity_proven: bool
    full_codex_parity_excluded_from_ga_claim_boundary: bool
    mutation_performed: bool
    outbound_message_sent: bool
    deploy_tag_release_performed: bool
    sources: list[SourceDisposition]
    blockers: list[str]
    claim_boundary: dict[str, Any]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["sources"] = [asdict(source) for source in self.sources]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


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
    for key in ("status", "disposition", "parity_status", "report"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        values: list[str] = []
        for child in value.values():
            values.extend(_string_values(child))
        return values
    if isinstance(value, list):
        values = []
        for child in value:
            values.extend(_string_values(child))
        return values
    return []


def _boundary_excludes_full_codex_parity(payload: dict[str, Any] | None) -> bool:
    if not payload:
        return False
    boundary = payload.get("claim_boundary")
    if not isinstance(boundary, dict):
        return False
    lowered_values = [value.casefold() for value in _string_values(boundary)]
    has_full_codex_parity = any("full codex parity" in value for value in lowered_values)
    has_disallowed_list = any(
        "full codex parity" in value.casefold()
        for value in _string_values(boundary.get("disallowed"))
    )
    has_exclusion_context = any(
        token in value
        for value in lowered_values
        for token in ("excluded", "disallowed", "forbidden", "not claimed", "only")
    )
    return has_disallowed_list or (has_full_codex_parity and has_exclusion_context)


def _parity_proven_claimed(payload: dict[str, Any] | None) -> bool:
    if not payload:
        return False
    status = _status(payload)
    status_claimed = status in {"codex_parity_proven", "parity_proven"}
    boolean_claimed = any(payload.get(key) is True for key in PARITY_CLAIM_KEYS)
    return status_claimed or boolean_claimed


def _non_empty_ref_list(payload: dict[str, Any], key: str) -> bool:
    value = payload.get(key)
    return isinstance(value, list) and any(isinstance(item, str) and item.strip() for item in value)


def _missing_proof_refs(payload: dict[str, Any] | None) -> list[str]:
    if not payload:
        return list(REQUIRED_PROOF_REF_KEYS)
    return [key for key in REQUIRED_PROOF_REF_KEYS if not _non_empty_ref_list(payload, key)]


def _parity_proof_sufficient(payload: dict[str, Any] | None) -> bool:
    if not payload:
        return False
    status = _status(payload)
    return (
        status in PROVEN_STATUS_VALUES
        and payload.get("full_codex_parity_claimed") is True
        and not _missing_proof_refs(payload)
    )


def _source_disposition(path: Path) -> SourceDisposition:
    payload, error = _read_json(path)
    status = _status(payload)
    claimed = _parity_proven_claimed(payload)
    sufficient = _parity_proof_sufficient(payload) if claimed else False
    return SourceDisposition(
        path=_display_path(path),
        status=status,
        boundary_excludes_full_codex_parity=_boundary_excludes_full_codex_parity(payload),
        parity_proven_claimed=claimed,
        parity_proof_sufficient=sufficient,
        missing_proof_refs=[] if not claimed else _missing_proof_refs(payload),
        error=error,
    )


def _next_actions(status: str, blockers: Sequence[str]) -> list[str]:
    if status == EXCLUDED_STATUS:
        return [
            "Archive the Codex parity disposition with Stage 5 evidence.",
            "Keep customer-facing wording scoped to controlled commercial pilot readiness.",
        ]
    return [
        "Remove unsupported full Codex parity claims or attach runtime/API/UI/acceptance proof refs.",
        "Refresh the Codex parity disposition before rerunning the commercial GA final gate.",
        *[f"Resolve blocker: {blocker}" for blocker in blockers],
    ]


def _known_limits(status: str) -> list[str]:
    common = [
        "This report does not perform deploy, tag, release, or outbound messaging operations.",
        "This report does not declare GA readiness, production readiness, or full commercial delivery completion.",
    ]
    if status == EXCLUDED_STATUS:
        return [
            *common,
            "Full Codex parity is excluded from the current commercial GA claim boundary.",
            "The satisfied disposition means the final gate may proceed without a full parity claim.",
        ]
    return [
        *common,
        "Full Codex parity remains unproven until runtime, API, UI, and acceptance evidence refs are supplied.",
    ]


def build_codex_parity_disposition(
    *,
    source_paths: Sequence[Path] | None = None,
    current_head_sha: str | None = None,
) -> CodexParityDispositionReport:
    paths = list(source_paths or [DEFAULT_CLAIM_BOUNDARY_REPORT])
    sources = [_source_disposition(path) for path in paths]
    resolved_head = current_head_sha or _git_value(["rev-parse", "HEAD"])
    unsupported_claim_sources = [
        source.path
        for source in sources
        if source.parity_proven_claimed and not source.parity_proof_sufficient
    ]
    blockers = [
        f"unsupported parity proven claim in {path}" for path in unsupported_claim_sources
    ]
    boundary_excluded = any(source.boundary_excludes_full_codex_parity for source in sources)
    parity_claimed = any(source.parity_proven_claimed for source in sources)

    if blockers:
        status = BLOCKED_STATUS
    elif boundary_excluded:
        status = EXCLUDED_STATUS
    else:
        status = BLOCKED_STATUS
        blockers.append("claim boundary does not explicitly exclude full Codex parity")

    satisfied = status == EXCLUDED_STATUS
    return CodexParityDispositionReport(
        status=status,
        codex_parity_disposition_satisfied=satisfied,
        generated_at=_utc_now(),
        evidence_type="stage5_codex_parity_disposition",
        current_head_sha=resolved_head,
        release_sha=resolved_head,
        full_codex_parity_claimed=parity_claimed,
        full_codex_parity_proven=False,
        full_codex_parity_excluded_from_ga_claim_boundary=boundary_excluded and not blockers,
        mutation_performed=False,
        outbound_message_sent=False,
        deploy_tag_release_performed=False,
        sources=sources,
        blockers=blockers,
        claim_boundary=CLAIM_BOUNDARY,
        next_actions=_next_actions(status, blockers),
        known_limits=_known_limits(status),
    )


def render_markdown_report(report: CodexParityDispositionReport) -> str:
    source_lines = [
        "| Path | Status | Boundary excludes full parity | Parity claimed | Proof sufficient | Missing proof refs | Error |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for source in report.sources:
        missing = ", ".join(source.missing_proof_refs) or "<none>"
        error = (source.error or "").replace("|", "\\|") or "<none>"
        source_lines.append(
            f"| `{source.path}` | `{source.status or '<missing>'}` | "
            f"`{source.boundary_excludes_full_codex_parity}` | "
            f"`{source.parity_proven_claimed}` | `{source.parity_proof_sufficient}` | "
            f"`{missing}` | {error} |"
        )
    blockers = "\n".join(f"- {blocker}" for blocker in report.blockers) or "- none"
    actions = "\n".join(f"- {action}" for action in report.next_actions)
    limits = "\n".join(f"- {limit}" for limit in report.known_limits)
    return (
        "# Stage 5 Codex Parity Disposition\n\n"
        f"- Status: `{report.status}`\n"
        f"- Disposition satisfied: `{report.codex_parity_disposition_satisfied}`\n"
        f"- Current head SHA: `{report.current_head_sha or '<missing>'}`\n"
        f"- Release SHA: `{report.release_sha or '<missing>'}`\n"
        f"- Full Codex parity claimed: `{report.full_codex_parity_claimed}`\n"
        f"- Full Codex parity proven: `{report.full_codex_parity_proven}`\n"
        "- Full Codex parity excluded from GA claim boundary: "
        f"`{report.full_codex_parity_excluded_from_ga_claim_boundary}`\n"
        f"- Mutation performed: `{report.mutation_performed}`\n"
        f"- Outbound message sent: `{report.outbound_message_sent}`\n"
        f"- Deploy/tag/release performed: `{report.deploy_tag_release_performed}`\n\n"
        "## Sources\n\n"
        + "\n".join(source_lines)
        + "\n\n## Blockers\n\n"
        f"{blockers}\n\n"
        "## Next Actions\n\n"
        f"{actions}\n\n"
        "## Known Limits\n\n"
        f"{limits}\n"
    )


def write_report(report: CodexParityDispositionReport, output_path: Path = DEFAULT_OUTPUT_JSON) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(
    report: CodexParityDispositionReport,
    output_path: Path = DEFAULT_OUTPUT_MD,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(report), encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        action="append",
        type=Path,
        dest="sources",
        help="JSON source report to inspect. Defaults to the Stage 5 claim-safe docs gate.",
    )
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_codex_parity_disposition(source_paths=args.sources)
    write_report(report, args.output_json)
    write_markdown_report(report, args.output_md)
    print(f"Codex parity disposition status: {report.status}")
    print(f"Disposition satisfied: {report.codex_parity_disposition_satisfied}")
    print(f"Full Codex parity claimed: {report.full_codex_parity_claimed}")
    print(f"Full Codex parity proven: {report.full_codex_parity_proven}")
    print(f"Blockers: {', '.join(report.blockers) or '<none>'}")
    print(f"JSON report written to {args.output_json}")
    print(f"Markdown report written to {args.output_md}")
    return 0 if report.codex_parity_disposition_satisfied else 1


if __name__ == "__main__":
    raise SystemExit(main())
