from __future__ import annotations

import json
from pathlib import Path

from scripts.ga_quality_gate import (
    DEFAULT_COVERAGE_THRESHOLD_PERCENT,
    build_ga_quality_gate_report,
    default_required_layers,
    main,
    parse_coverage_xml,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_coverage(path: Path, *, line_rate: float) -> None:
    path.write_text(
        f"""<?xml version="1.0" ?>
<coverage line-rate="{line_rate}" branch-rate="0.5" version="coverage.py">
  <packages />
</coverage>
""",
        encoding="utf-8",
    )


def _write_strict_evidence(report_dir: Path, *names: str) -> None:
    for layer in default_required_layers(report_dir):
        if layer.name not in names:
            continue
        _write_json(
            layer.path,
            {
                "status": "passed",
                "strict_evidence": True,
                "evidence_type": layer.evidence_type,
                "mode": "strict",
                "ga_ready": False,
                "mutation_performed": False,
            },
        )


def test_parse_coverage_xml_blocks_below_threshold(tmp_path: Path) -> None:
    coverage_xml = tmp_path / "coverage.xml"
    _write_coverage(coverage_xml, line_rate=0.9134)

    summary = parse_coverage_xml(
        coverage_xml,
        threshold_percent=DEFAULT_COVERAGE_THRESHOLD_PERCENT,
    )

    assert summary.status == "blocked"
    assert summary.line_rate == 0.9134
    assert summary.percent == 91.34
    assert summary.threshold_percent == DEFAULT_COVERAGE_THRESHOLD_PERCENT
    assert "below" in str(summary.error)


def test_report_blocks_low_coverage_and_missing_strict_evidence(tmp_path: Path) -> None:
    coverage_xml = tmp_path / "coverage.xml"
    report_dir = tmp_path / "reports"
    _write_coverage(coverage_xml, line_rate=0.52)

    report = build_ga_quality_gate_report(
        report_dir=report_dir,
        coverage_xml=coverage_xml,
    )

    assert report.status == "blocked"
    assert report.ga_ready is False
    assert report.mode == "report-only"
    assert report.full_suite_run is False
    assert report.mutation_performed is False
    assert report.coverage.status == "blocked"
    assert {"e2e_strict", "load_strict", "security_strict"}.issubset(
        set(report.missing_required_layers)
    )
    assert "coverage" in report.blocking_reasons


def test_report_ready_only_with_coverage_and_all_strict_layers(tmp_path: Path) -> None:
    coverage_xml = tmp_path / "coverage.xml"
    report_dir = tmp_path / "reports"
    _write_coverage(coverage_xml, line_rate=0.991)
    _write_strict_evidence(report_dir, "e2e_strict", "load_strict", "security_strict")

    report = build_ga_quality_gate_report(
        report_dir=report_dir,
        coverage_xml=coverage_xml,
    )

    assert report.status == "ready"
    assert report.ga_ready is True
    assert report.missing_required_layers == []
    assert report.blocking_reasons == []
    assert {layer.status for layer in report.required_layers} == {"passed"}


def test_report_blocks_strict_layers_with_wrong_evidence_type(tmp_path: Path) -> None:
    coverage_xml = tmp_path / "coverage.xml"
    report_dir = tmp_path / "reports"
    _write_coverage(coverage_xml, line_rate=0.991)
    for layer in default_required_layers(report_dir):
        _write_json(
            layer.path,
            {
                "status": "passed",
                "strict_evidence": True,
                "evidence_type": f"stale_{layer.evidence_type}",
                "mode": "strict",
            },
        )

    report = build_ga_quality_gate_report(
        report_dir=report_dir,
        coverage_xml=coverage_xml,
    )

    assert report.status == "blocked"
    assert report.ga_ready is False
    assert report.missing_required_layers == []
    assert set(report.blocked_required_layers) == {
        "e2e_strict",
        "load_strict",
        "security_strict",
    }
    assert "blocked_required_layers" in report.blocking_reasons
    for layer in report.required_layers:
        assert layer.ready is False
        assert layer.strict_evidence is True
        assert layer.status == "passed"
        assert f"expected evidence_type {layer.evidence_type}" in str(layer.error)
        assert "got stale_" in str(layer.error)


def test_missing_required_layer_blocks_even_when_other_layers_pass(tmp_path: Path) -> None:
    coverage_xml = tmp_path / "coverage.xml"
    report_dir = tmp_path / "reports"
    _write_coverage(coverage_xml, line_rate=0.98)
    _write_strict_evidence(report_dir, "e2e_strict", "security_strict")

    report = build_ga_quality_gate_report(
        report_dir=report_dir,
        coverage_xml=coverage_xml,
    )

    assert report.status == "blocked"
    assert report.ga_ready is False
    assert report.missing_required_layers == ["load_strict"]
    load_layer = next(layer for layer in report.required_layers if layer.name == "load_strict")
    assert load_layer.status == "missing"


def test_targeted_rc_118_passed_is_not_promoted_to_ga_ready(tmp_path: Path) -> None:
    coverage_xml = tmp_path / "coverage.xml"
    report_dir = tmp_path / "reports"
    targeted_rc = report_dir / "targeted-rc-118.json"
    _write_coverage(coverage_xml, line_rate=0.99)
    _write_json(
        targeted_rc,
        {
            "status": "passed",
            "scope": "targeted_rc",
            "passed": 118,
            "total": 118,
            "strict_evidence": False,
        },
    )

    report = build_ga_quality_gate_report(
        report_dir=report_dir,
        coverage_xml=coverage_xml,
        targeted_rc_reports=[targeted_rc],
    )

    assert report.status == "blocked"
    assert report.ga_ready is False
    assert report.non_ga_evidence
    assert report.non_ga_evidence[0].classification == "targeted_rc_118"
    assert "does not satisfy GA" in report.non_ga_evidence[0].reason
    assert {"e2e_strict", "load_strict", "security_strict"}.issubset(
        set(report.missing_required_layers)
    )


def test_cli_writes_report_and_requires_allow_blocked_for_zero_exit(tmp_path: Path) -> None:
    coverage_xml = tmp_path / "missing-coverage.xml"
    report_dir = tmp_path / "reports"
    output = tmp_path / "ga-quality-gate.json"

    blocked_exit = main(
        [
            "--report-dir",
            str(report_dir),
            "--coverage-xml",
            str(coverage_xml),
            "--output",
            str(output),
        ]
    )

    assert blocked_exit == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "blocked"
    assert payload["coverage"]["status"] == "missing"

    allowed_exit = main(
        [
            "--report-dir",
            str(report_dir),
            "--coverage-xml",
            str(coverage_xml),
            "--output",
            str(output),
            "--allow-blocked",
        ]
    )

    assert allowed_exit == 0
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "blocked"
