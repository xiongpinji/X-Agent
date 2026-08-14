#!/usr/bin/env python3
"""Validate the commercial RC release diff review handoff.

This gate turns ``docs/RC_RELEASE_DIFF_REVIEW.md`` from a narrative review into
machine-checkable release evidence. It verifies that the review references the
same candidate payload as the release audit, staging plan, and source bundle,
keeps excluded local artifacts out of scope, and preserves the no-full-parity
claim boundary.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.rc_source_bundle import ROOT

REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_REVIEW = ROOT / "docs" / "operations" / "deployment" / "RC_RELEASE_DIFF_REVIEW.md"
DEFAULT_RELEASE_AUDIT = REPORT_DIR / "rc-release-audit.json"
DEFAULT_STAGING_PLAN = REPORT_DIR / "rc-staging-plan.json"
DEFAULT_SOURCE_BUNDLE = REPORT_DIR / "rc-source-bundle.json"
DEFAULT_GAP_MATRIX = REPORT_DIR / "codex-hermes-gap-closure.json"
DEFAULT_OWNER_GATE_PLAN = REPORT_DIR / "rc-owner-gate-plan.json"
DEFAULT_OUTPUT = REPORT_DIR / "rc-release-diff-review-gate.json"

REQUIRED_REVIEW_TOKENS = (
    "Status: locally acceptable for RC candidate staging after owner review.",
    "docs/RC_STAGING_MANIFEST.md",
    "full_parity_claimed=false",
    ".agents/",
    ".codex/",
    "AGENTS.md",
    "COMPETITIVE_ANALYSIS_2026.md",
    ".xagent_runtime/",
    "file hygiene findings",
    "manifest unsafe paths",
)

REQUIRED_AUDIT_EMPTY_FIELDS = (
    "missing_from_manifest",
    "manifest_extra",
    "manifest_tracked_misclassified",
    "manifest_new_misclassified",
    "manifest_unsafe_paths",
    "secret_findings",
    "excluded_reference_findings",
    "local_path_findings",
    "file_hygiene_findings",
)


@dataclass(frozen=True)
class DiffReviewCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class DiffReviewGateReport:
    status: str
    generated_at: str
    review_path: str
    candidate_file_count: int | None
    checks: list[DiffReviewCheck]
    next_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"missing report: {path}"
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON in {path}: {exc}"
    if not isinstance(payload, dict):
        return None, f"report is not a JSON object: {path}"
    return payload, None


def _read_text(path: Path) -> tuple[str, str | None]:
    try:
        return path.read_text(encoding="utf-8"), None
    except FileNotFoundError:
        return "", f"missing review: {path}"
    except UnicodeDecodeError as exc:
        return "", f"review is not UTF-8 text: {exc}"


def _normalized_path_list(items: Any) -> list[str]:
    paths: list[str] = []
    if not isinstance(items, list):
        return paths
    for item in items:
        if isinstance(item, str):
            path = item
        elif isinstance(item, dict):
            path = str(item.get("path") or "")
        else:
            continue
        normalized = path.replace("\\", "/").strip()
        if normalized:
            paths.append(normalized)
    return sorted(dict.fromkeys(paths))


def _staging_paths(payload: dict[str, Any] | None) -> list[str]:
    paths: list[str] = []
    if not payload:
        return paths
    commands = payload.get("commands")
    if not isinstance(commands, list):
        return paths
    for command in commands:
        if isinstance(command, dict):
            paths.extend(_normalized_path_list(command.get("paths")))
    return sorted(dict.fromkeys(paths))


def _review_document_check(review_text: str, review_error: str | None) -> DiffReviewCheck:
    problems: list[str] = []
    if review_error:
        problems.append(review_error)
    missing = [token for token in REQUIRED_REVIEW_TOKENS if token not in review_text]
    if missing:
        problems.append(f"review missing required tokens: {', '.join(missing)}")
    return DiffReviewCheck(
        name="review_document",
        status="passed" if not problems else "failed",
        details={"required_tokens": list(REQUIRED_REVIEW_TOKENS), "missing_tokens": missing},
        error="; ".join(problems) if problems else None,
    )


def _release_audit_check(payload: dict[str, Any] | None, error: str | None) -> DiffReviewCheck:
    problems: list[str] = []
    details: dict[str, Any] = {}
    if error:
        problems.append(error)
    if payload is not None:
        status = str(payload.get("status") or "")
        details["status"] = status
        details["candidate_count"] = payload.get("candidate_count")
        details["manifest_count"] = payload.get("manifest_count")
        if status != "passed":
            problems.append(f"release audit status is not passed: {status}")
        if payload.get("candidate_count") != payload.get("manifest_count"):
            problems.append("release audit candidate_count does not match manifest_count")
        for field_name in REQUIRED_AUDIT_EMPTY_FIELDS:
            values = payload.get(field_name)
            details[field_name] = values
            if field_name not in payload:
                problems.append(f"release audit {field_name} is missing")
            elif values != []:
                problems.append(f"release audit {field_name} is not empty")
    return DiffReviewCheck(
        name="release_audit",
        status="passed" if not problems else "failed",
        details=details,
        error="; ".join(problems) if problems else None,
    )


def _candidate_payload_check(
    release_payload: dict[str, Any] | None,
    staging_payload: dict[str, Any] | None,
    source_payload: dict[str, Any] | None,
) -> DiffReviewCheck:
    problems: list[str] = []
    counts = {
        "release_candidate": (release_payload or {}).get("candidate_count"),
        "release_manifest": (release_payload or {}).get("manifest_count"),
        "staging_plan": (staging_payload or {}).get("file_count"),
        "source_bundle": (source_payload or {}).get("file_count"),
    }
    if any(value is None for value in counts.values()):
        problems.append(f"missing candidate count fields: {counts}")
    elif len(set(counts.values())) != 1:
        problems.append(f"candidate count mismatch: {counts}")

    source_paths = _normalized_path_list((source_payload or {}).get("files"))
    staging_paths = _staging_paths(staging_payload)
    if not source_paths:
        problems.append("source bundle file list is missing or empty")
    if not staging_paths:
        problems.append("staging plan command paths are missing or empty")
    if source_paths and staging_paths and source_paths != staging_paths:
        problems.append(
            "candidate path mismatch: "
            f"missing_from_staging={sorted(set(source_paths).difference(staging_paths))}, "
            f"extra_in_staging={sorted(set(staging_paths).difference(source_paths))}"
        )
    for field_name in ("missing_files", "excluded_files", "errors"):
        values = (staging_payload or {}).get(field_name)
        if values not in (None, []):
            problems.append(f"staging plan {field_name} is not empty")
    for field_name in ("missing_files", "excluded_files", "errors"):
        values = (source_payload or {}).get(field_name)
        if values not in (None, []):
            problems.append(f"source bundle {field_name} is not empty")
    return DiffReviewCheck(
        name="candidate_payload_consistency",
        status="passed" if not problems else "failed",
        details={
            "counts": counts,
            "source_path_count": len(source_paths),
            "staging_path_count": len(staging_paths),
        },
        error="; ".join(problems) if problems else None,
    )


def _parity_boundary_check(gap_payload: dict[str, Any] | None, error: str | None, review_text: str) -> DiffReviewCheck:
    problems: list[str] = []
    full_parity_claimed = None
    if error:
        problems.append(error)
    if gap_payload is not None:
        full_parity_claimed = bool(
            ((gap_payload.get("summary") or {}).get("competitive_parity") or {}).get("full_parity_claimed")
        )
        if full_parity_claimed:
            problems.append("gap matrix claims full Codex/Hermes parity")
    if "full_parity_claimed=true" in review_text:
        problems.append("review text contains full_parity_claimed=true")
    return DiffReviewCheck(
        name="parity_boundary",
        status="passed" if not problems else "failed",
        details={"full_parity_claimed": full_parity_claimed},
        error="; ".join(problems) if problems else None,
    )


def _review_evidence_freshness_check(review_text: str, candidate_count: int | None) -> DiffReviewCheck:
    problems: list[str] = []
    required = f"Release audit: passed, {candidate_count} candidate files"
    if candidate_count is None:
        problems.append("candidate count is unavailable")
    elif required not in review_text:
        problems.append(f"review observed evidence must contain: {required}")
    stale_markers = ("74 candidate files", "75 candidate files", "100 candidate files")
    stale = [marker for marker in stale_markers if marker in review_text and marker != f"{candidate_count} candidate files"]
    if stale:
        problems.append(f"review contains stale candidate-count markers: {', '.join(stale)}")
    return DiffReviewCheck(
        name="review_evidence_freshness",
        status="passed" if not problems else "failed",
        details={"candidate_count": candidate_count, "required_evidence_line": required if candidate_count else None},
        error="; ".join(problems) if problems else None,
    )


def _owner_gate_review_check(owner_payload: dict[str, Any] | None, error: str | None, review_text: str) -> DiffReviewCheck:
    problems: list[str] = []
    details: dict[str, Any] = {}
    if error:
        problems.append(error)
    if owner_payload is not None:
        gates = owner_payload.get("gates")
        if not isinstance(gates, list) or not gates:
            problems.append("owner gate plan has no gates")
        else:
            pending = [
                str(gate.get("name"))
                for gate in gates
                if isinstance(gate, dict) and gate.get("status") != "verified" and gate.get("name")
            ]
            verified = [
                str(gate.get("name"))
                for gate in gates
                if isinstance(gate, dict) and gate.get("status") == "verified" and gate.get("name")
            ]
            details["pending_gates"] = pending
            details["verified_gates"] = verified
            for gate_name in pending:
                if gate_name not in review_text:
                    problems.append(f"review missing pending owner gate id: {gate_name}")
            if verified and "Provider owner gate" not in review_text:
                problems.append("review missing verified provider owner gate note")
    return DiffReviewCheck(
        name="owner_gate_review",
        status="passed" if not problems else "failed",
        details=details,
        error="; ".join(problems) if problems else None,
    )


def build_diff_review_gate(
    *,
    review_path: Path = DEFAULT_REVIEW,
    release_audit_path: Path = DEFAULT_RELEASE_AUDIT,
    staging_plan_path: Path = DEFAULT_STAGING_PLAN,
    source_bundle_path: Path = DEFAULT_SOURCE_BUNDLE,
    gap_matrix_path: Path = DEFAULT_GAP_MATRIX,
    owner_gate_plan_path: Path = DEFAULT_OWNER_GATE_PLAN,
) -> DiffReviewGateReport:
    review_text, review_error = _read_text(review_path)
    release_payload, release_error = _read_json(release_audit_path)
    staging_payload, staging_error = _read_json(staging_plan_path)
    source_payload, source_error = _read_json(source_bundle_path)
    gap_payload, gap_error = _read_json(gap_matrix_path)
    owner_payload, owner_error = _read_json(owner_gate_plan_path)
    count_value = (release_payload or {}).get("candidate_count")
    candidate_count = count_value if isinstance(count_value, int) else None

    checks = [
        _review_document_check(review_text, review_error),
        _release_audit_check(release_payload, release_error),
        DiffReviewCheck(
            "staging_plan_report",
            "passed" if staging_error is None and (staging_payload or {}).get("status") == "planned" else "failed",
            details={"status": (staging_payload or {}).get("status")},
            error=staging_error
            or (None if (staging_payload or {}).get("status") == "planned" else "staging plan status is not planned"),
        ),
        DiffReviewCheck(
            "source_bundle_report",
            "passed" if source_error is None and (source_payload or {}).get("status") == "created" else "failed",
            details={"status": (source_payload or {}).get("status")},
            error=source_error
            or (None if (source_payload or {}).get("status") == "created" else "source bundle status is not created"),
        ),
        _candidate_payload_check(release_payload, staging_payload, source_payload),
        _parity_boundary_check(gap_payload, gap_error, review_text),
        _review_evidence_freshness_check(review_text, candidate_count),
        _owner_gate_review_check(owner_payload, owner_error, review_text),
    ]
    status = "passed" if all(check.status == "passed" for check in checks) else "failed"
    return DiffReviewGateReport(
        status=status,
        generated_at=_utc_now(),
        review_path=str(review_path),
        candidate_file_count=candidate_count,
        checks=checks,
        next_commands=[
            "Refresh docs/RC_RELEASE_DIFF_REVIEW.md after candidate files or owner-gate evidence changes.",
            "Run python scripts\\rc_release_diff_review_gate.py before rc_final_gate.py.",
            "Keep full_parity_claimed=false unless a separate parity evidence process proves otherwise.",
        ],
    )


def write_report(report: DiffReviewGateReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the X-Agent commercial RC diff review")
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--release-audit", type=Path, default=DEFAULT_RELEASE_AUDIT)
    parser.add_argument("--staging-plan", type=Path, default=DEFAULT_STAGING_PLAN)
    parser.add_argument("--source-bundle", type=Path, default=DEFAULT_SOURCE_BUNDLE)
    parser.add_argument("--gap-matrix", type=Path, default=DEFAULT_GAP_MATRIX)
    parser.add_argument("--owner-gate-plan", type=Path, default=DEFAULT_OWNER_GATE_PLAN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_diff_review_gate(
        review_path=args.review,
        release_audit_path=args.release_audit,
        staging_plan_path=args.staging_plan,
        source_bundle_path=args.source_bundle,
        gap_matrix_path=args.gap_matrix,
        owner_gate_plan_path=args.owner_gate_plan,
    )
    write_report(report, args.output)
    print(f"RC release diff review gate status: {report.status}")
    print(f"Candidate files: {report.candidate_file_count}")
    print(f"Report written to {args.output}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
