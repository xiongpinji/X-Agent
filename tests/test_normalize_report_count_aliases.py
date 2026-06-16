from __future__ import annotations

import json
from pathlib import Path

from scripts.normalize_report_count_aliases import normalize_report_count_aliases


def test_normalize_report_count_aliases_backfills_top_level_lists(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    reports_dir = source_root / ".xagent_runtime" / "reports"
    reports_dir.mkdir(parents=True)
    report = reports_dir / "rc-final-gate.json"
    report.write_text(
        json.dumps(
            {
                "kind": "rc_final_gate",
                "ok": True,
                "status": "passed",
                "checks": [{"name": "provider_tool_transcript"}],
                "gaps": [],
                "next_actions": ["Run targeted tests."],
                "next_actions_count": 1,
            }
        ),
        encoding="utf-8",
    )
    (reports_dir / "diagnostic.txt").write_text("not json", encoding="utf-8")

    payload = normalize_report_count_aliases(
        source_root=source_root,
        reports_dir=reports_dir,
        output=reports_dir / "report-count-alias-normalization.json",
    )

    updated = json.loads(report.read_text(encoding="utf-8"))
    assert updated["checks_count"] == 1
    assert updated["gaps_count"] == 0
    assert updated["next_actions_count"] == 1
    assert payload["ok"] is True
    assert payload["status"] == "passed"
    assert payload["summary"]["reports_scanned"] == 1
    assert payload["summary"]["reports_updated"] == 1
    assert payload["summary"]["count_aliases_added"] == 2
    assert payload["updated_reports"] == [
        {
            "path": ".xagent_runtime/reports/rc-final-gate.json",
            "added_count_aliases": ["checks_count", "gaps_count"],
            "added_count_aliases_count": 2,
        }
    ]


def test_normalize_report_count_aliases_dry_run_preserves_reports(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    reports_dir = source_root / ".xagent_runtime" / "reports"
    reports_dir.mkdir(parents=True)
    report = reports_dir / "pytest-evidence.json"
    original = {"kind": "pytest_evidence", "ok": True, "status": "passed", "shards": []}
    report.write_text(json.dumps(original), encoding="utf-8")

    payload = normalize_report_count_aliases(
        source_root=source_root,
        reports_dir=reports_dir,
        output=reports_dir / "report-count-alias-normalization.json",
        dry_run=True,
    )

    assert json.loads(report.read_text(encoding="utf-8")) == original
    assert payload["status"] == "planned"
    assert payload["summary"]["reports_scanned"] == 1
    assert payload["summary"]["reports_updated"] == 1
    assert payload["summary"]["count_aliases_added"] == 1


def test_normalize_report_count_aliases_skips_its_own_output(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    reports_dir = source_root / ".xagent_runtime" / "reports"
    reports_dir.mkdir(parents=True)
    output = reports_dir / "report-count-alias-normalization.json"
    output.write_text(
        json.dumps({"kind": "report_count_alias_normalization", "updated_reports": []}),
        encoding="utf-8",
    )

    payload = normalize_report_count_aliases(
        source_root=source_root,
        reports_dir=reports_dir,
        output=output,
        dry_run=True,
    )

    assert payload["summary"]["reports_scanned"] == 0
    assert payload["summary"]["reports_updated"] == 0


def test_normalize_report_count_aliases_can_scope_reports_by_name_glob(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    reports_dir = source_root / ".xagent_runtime" / "reports"
    reports_dir.mkdir(parents=True)
    delivery_report = reports_dir / "commercial-delivery-task-board.json"
    old_report = reports_dir / "old-report.json"
    delivery_report.write_text(json.dumps({"status": "ready", "tasks": []}), encoding="utf-8")
    old_report.write_text(json.dumps({"status": "ready", "tasks": []}), encoding="utf-8")

    payload = normalize_report_count_aliases(
        source_root=source_root,
        reports_dir=reports_dir,
        output=reports_dir / "report-count-alias-normalization.json",
        include_globs=["commercial-delivery-*.json"],
    )

    assert payload["include_globs"] == ["commercial-delivery-*.json"]
    assert payload["include_globs_count"] == 1
    assert payload["summary"]["reports_scanned"] == 1
    assert payload["summary"]["reports_updated"] == 1
    assert json.loads(delivery_report.read_text(encoding="utf-8"))["tasks_count"] == 0
    assert "tasks_count" not in json.loads(old_report.read_text(encoding="utf-8"))
