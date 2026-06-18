#!/usr/bin/env python3
"""Build a fail-closed GA quality gate report from existing local evidence.

The default mode is intentionally read-only: this script parses existing
coverage and evidence reports, writes one gate JSON report, and never runs the
full test suite, deploys, edits deployment configuration, or changes branch
protection.
"""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "ga-quality-gate.json"
DEFAULT_COVERAGE_XML = ROOT / "coverage.xml"
DEFAULT_COVERAGE_THRESHOLD_PERCENT = 95.0
READY_STATUS = "ready"
BLOCKED_STATUS = "blocked"
DEFAULT_MODE = "report-only"


@dataclass(frozen=True)
class RequiredLayerSpec:
    name: str
    path: Path
    evidence_type: str
    expected_statuses: tuple[str, ...] = ("passed", "ready")
    reason: str = ""


@dataclass(frozen=True)
class CoverageSummary:
    path: str
    status: str
    line_rate: float | None
    percent: float | None
    threshold_percent: float
    error: str | None = None


@dataclass(frozen=True)
class RequiredLayerSummary:
    name: str
    path: str
    evidence_type: str
    status: str
    expected_statuses: list[str]
    strict_evidence: bool
    ready: bool
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NonGAEvidenceSummary:
    path: str
    status: str
    classification: str
    reason: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GAQualityGateReport:
    status: str
    generated_at: str
    evidence_type: str
    mode: str
    ga_ready: bool
    coverage: CoverageSummary
    required_layers: list[RequiredLayerSummary]
    missing_required_layers: list[str]
    blocked_required_layers: list[str]
    blocking_reasons: list[str]
    non_ga_evidence: list[NonGAEvidenceSummary]
    read_only: bool
    full_suite_run: bool
    mutation_performed: bool
    deploy_production_modified: bool
    branch_protection_modified: bool
    claim_boundary: dict[str, Any]
    next_actions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def default_required_layers(report_dir: Path = REPORT_DIR) -> list[RequiredLayerSpec]:
    return [
        RequiredLayerSpec(
            name="e2e_strict",
            path=report_dir / "ga-e2e-strict.json",
            evidence_type="ga_e2e_strict",
            reason="GA requires strict end-to-end evidence, not targeted or smoke-only checks.",
        ),
        RequiredLayerSpec(
            name="load_strict",
            path=report_dir / "ga-load-strict.json",
            evidence_type="ga_load_strict",
            reason="GA requires strict load or capacity evidence.",
        ),
        RequiredLayerSpec(
            name="security_strict",
            path=report_dir / "ga-security-strict.json",
            evidence_type="ga_security_strict",
            reason="GA requires strict security evidence.",
        ),
    ]


def parse_coverage_xml(
    coverage_xml: Path = DEFAULT_COVERAGE_XML,
    *,
    threshold_percent: float = DEFAULT_COVERAGE_THRESHOLD_PERCENT,
) -> CoverageSummary:
    display = _display_path(coverage_xml)
    try:
        root = ET.parse(coverage_xml).getroot()
    except FileNotFoundError:
        return CoverageSummary(
            path=display,
            status="missing",
            line_rate=None,
            percent=None,
            threshold_percent=threshold_percent,
            error="coverage.xml not found",
        )
    except (OSError, ET.ParseError) as exc:
        return CoverageSummary(
            path=display,
            status="invalid",
            line_rate=None,
            percent=None,
            threshold_percent=threshold_percent,
            error=f"could not parse coverage.xml: {exc}",
        )

    try:
        line_rate, percent = _coverage_values(root)
    except ValueError as exc:
        return CoverageSummary(
            path=display,
            status="invalid",
            line_rate=None,
            percent=None,
            threshold_percent=threshold_percent,
            error=str(exc),
        )

    rounded_percent = round(percent, 2)
    status = READY_STATUS if rounded_percent >= threshold_percent else BLOCKED_STATUS
    error = None
    if status == BLOCKED_STATUS:
        error = f"coverage {rounded_percent:.2f}% is below GA threshold {threshold_percent:.2f}%"
    return CoverageSummary(
        path=display,
        status=status,
        line_rate=line_rate,
        percent=rounded_percent,
        threshold_percent=threshold_percent,
        error=error,
    )


def _coverage_values(root: ET.Element) -> tuple[float, float]:
    raw_line_rate = root.attrib.get("line-rate")
    if raw_line_rate is not None:
        value = float(raw_line_rate)
        if value < 0:
            raise ValueError("coverage line-rate cannot be negative")
        if value <= 1:
            return value, value * 100
        return value / 100, value

    lines_valid = root.attrib.get("lines-valid")
    lines_covered = root.attrib.get("lines-covered")
    if lines_valid is None or lines_covered is None:
        raise ValueError("coverage.xml is missing line-rate or lines-covered/lines-valid")
    valid = float(lines_valid)
    covered = float(lines_covered)
    if valid <= 0:
        raise ValueError("coverage.xml lines-valid must be greater than zero")
    line_rate = covered / valid
    return line_rate, line_rate * 100


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "report missing"
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"
    except OSError as exc:
        return None, f"could not read report: {exc}"
    if not isinstance(payload, dict):
        return None, "report is not a JSON object"
    return payload, None


def _status(payload: dict[str, Any] | None) -> str:
    if payload is None:
        return "missing"
    for key in ("status", "result", "report_status"):
        value = payload.get(key)
        if value is not None:
            return str(value)
    return ""


def _strict_evidence(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    return payload.get("strict_evidence") is True


def _layer_summary(spec: RequiredLayerSpec) -> RequiredLayerSummary:
    payload, error = _read_json(spec.path)
    status = _status(payload)
    strict_evidence = _strict_evidence(payload)
    actual_evidence_type = payload.get("evidence_type") if isinstance(payload, dict) else None
    evidence_type_matches = actual_evidence_type == spec.evidence_type
    expected = list(spec.expected_statuses)
    ready = (
        payload is not None
        and error is None
        and status in spec.expected_statuses
        and strict_evidence
        and evidence_type_matches
    )
    details: dict[str, Any] = {}
    if isinstance(payload, dict):
        for key in (
            "evidence_type",
            "mode",
            "generated_at",
            "run_id",
            "commit_sha",
            "current_head_sha",
            "release_sha",
            "ga_ready",
        ):
            if key in payload:
                details[key] = payload[key]
    if error is None and payload is not None and not strict_evidence:
        error = "strict_evidence must be true for GA"
    if error is None and payload is not None and status not in spec.expected_statuses:
        error = f"expected status in {expected}, got {status or '<missing>'}"
    if error is None and payload is not None and not evidence_type_matches:
        got = actual_evidence_type if actual_evidence_type is not None else "<missing>"
        error = f"expected evidence_type {spec.evidence_type}, got {got}"
    return RequiredLayerSummary(
        name=spec.name,
        path=_display_path(spec.path),
        evidence_type=spec.evidence_type,
        status=status,
        expected_statuses=expected,
        strict_evidence=strict_evidence,
        ready=ready,
        error=None if ready else error,
        details=details,
    )


def _default_targeted_rc_reports(report_dir: Path) -> list[Path]:
    patterns = ("*targeted*rc*118*.json", "*rc*118*.json", "*118*passed*.json")
    found: list[Path] = []
    for pattern in patterns:
        found.extend(report_dir.glob(pattern))
    return sorted(dict.fromkeys(found))


def _non_ga_evidence(path: Path) -> NonGAEvidenceSummary | None:
    payload, error = _read_json(path)
    if payload is None:
        return None
    status = _status(payload)
    passed = payload.get("passed")
    total = payload.get("total")
    scope = str(payload.get("scope") or payload.get("mode") or payload.get("evidence_type") or "")
    path_text = path.name.lower()
    looks_like_targeted_rc = (
        "targeted" in scope.lower()
        or "targeted" in path_text
        or payload.get("targeted") is True
        or payload.get("targeted_rc") is True
    )
    is_118_passed = status == "passed" and passed == 118 and total == 118
    if not (looks_like_targeted_rc or is_118_passed):
        return None
    classification = "targeted_rc_118" if is_118_passed else "targeted_rc"
    reason = "Targeted RC evidence does not satisfy GA strict e2e/load/security evidence requirements."
    if error:
        reason = f"{reason} Read note: {error}"
    return NonGAEvidenceSummary(
        path=_display_path(path),
        status=status,
        classification=classification,
        reason=reason,
        details={
            "scope": scope,
            "passed": passed,
            "total": total,
            "strict_evidence": payload.get("strict_evidence"),
        },
    )


def build_ga_quality_gate_report(
    *,
    report_dir: Path = REPORT_DIR,
    coverage_xml: Path = DEFAULT_COVERAGE_XML,
    output_path: Path = DEFAULT_OUTPUT,
    threshold_percent: float = DEFAULT_COVERAGE_THRESHOLD_PERCENT,
    mode: str = DEFAULT_MODE,
    required_layers: list[RequiredLayerSpec] | None = None,
    targeted_rc_reports: list[Path] | None = None,
) -> GAQualityGateReport:
    coverage = parse_coverage_xml(coverage_xml, threshold_percent=threshold_percent)
    layer_specs = required_layers or default_required_layers(report_dir)
    layers = [_layer_summary(spec) for spec in layer_specs]
    missing_required_layers = [layer.name for layer in layers if layer.status == "missing"]
    blocked_required_layers = [
        layer.name for layer in layers if layer.status != "missing" and not layer.ready
    ]
    targeted_paths = (
        targeted_rc_reports if targeted_rc_reports is not None else _default_targeted_rc_reports(report_dir)
    )
    non_ga = [
        summary
        for summary in (_non_ga_evidence(path) for path in targeted_paths)
        if summary is not None
    ]

    blocking_reasons: list[str] = []
    if coverage.status != READY_STATUS:
        blocking_reasons.append("coverage")
    if missing_required_layers:
        blocking_reasons.append("missing_required_layers")
    if blocked_required_layers:
        blocking_reasons.append("blocked_required_layers")

    ga_ready = not blocking_reasons
    status = READY_STATUS if ga_ready else BLOCKED_STATUS
    return GAQualityGateReport(
        status=status,
        generated_at=_utc_now(),
        evidence_type="ga_quality_gate",
        mode=mode,
        ga_ready=ga_ready,
        coverage=coverage,
        required_layers=layers,
        missing_required_layers=missing_required_layers,
        blocked_required_layers=blocked_required_layers,
        blocking_reasons=blocking_reasons,
        non_ga_evidence=non_ga,
        read_only=True,
        full_suite_run=False,
        mutation_performed=False,
        deploy_production_modified=False,
        branch_protection_modified=False,
        claim_boundary={
            "allowed_when_blocked": "report current GA blockers only",
            "forbidden_when_blocked": [
                "GA ready",
                "production ready",
                "full commercial delivery complete",
                "targeted RC 118 passed equals GA ready",
            ],
            "output_path": _display_path(output_path),
        },
        next_actions=_next_actions(coverage, missing_required_layers, blocked_required_layers),
    )


def _next_actions(
    coverage: CoverageSummary,
    missing_required_layers: list[str],
    blocked_required_layers: list[str],
) -> list[str]:
    actions: list[str] = []
    if coverage.status != READY_STATUS:
        actions.append("Produce a fresh coverage.xml at or above the GA threshold.")
    for layer in missing_required_layers:
        actions.append(f"Produce strict GA evidence for {layer}.")
    for layer in blocked_required_layers:
        actions.append(f"Refresh {layer} so status is ready/passed and strict_evidence is true.")
    if not actions:
        actions.append("Keep this gate separate from deploy-production and branch protection changes.")
    return actions


def write_report(report: GAQualityGateReport, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=[DEFAULT_MODE], default=DEFAULT_MODE)
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--coverage-xml", type=Path, default=DEFAULT_COVERAGE_XML)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--threshold-percent",
        type=float,
        default=DEFAULT_COVERAGE_THRESHOLD_PERCENT,
    )
    parser.add_argument(
        "--targeted-rc-report",
        action="append",
        type=Path,
        dest="targeted_rc_reports",
        default=None,
        help="Known targeted RC report to record as non-GA evidence.",
    )
    parser.add_argument(
        "--allow-blocked",
        action="store_true",
        help="Return success after writing a blocked report.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_ga_quality_gate_report(
        report_dir=args.report_dir,
        coverage_xml=args.coverage_xml,
        output_path=args.output,
        threshold_percent=args.threshold_percent,
        mode=args.mode,
        targeted_rc_reports=args.targeted_rc_reports,
    )
    write_report(report, args.output)
    print(f"GA quality gate status: {report.status}")
    print(f"GA ready: {report.ga_ready}")
    print(f"Coverage: {report.coverage.percent if report.coverage.percent is not None else '<missing>'}")
    print(f"Missing required layers: {', '.join(report.missing_required_layers) or '<none>'}")
    print(f"Blocked required layers: {', '.join(report.blocked_required_layers) or '<none>'}")
    print(f"Report written to {args.output}")
    return 0 if report.ga_ready or args.allow_blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
