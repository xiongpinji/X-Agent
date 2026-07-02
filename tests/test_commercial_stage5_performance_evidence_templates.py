from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.commercial_performance_capacity_gate import (
    build_performance_capacity_gate,
    default_required_evidence,
)
from scripts.commercial_stage5_performance_evidence_pack import (
    REQUIRED_DOMAINS,
    build_stage5_performance_evidence_pack,
)
from scripts.commercial_stage5_performance_evidence_templates import (
    build_report,
    build_template_payloads,
    render_markdown_report,
    write_markdown_report,
    write_report,
    write_templates,
)

HEAD = "84ee203bf6676f3abf86a8f534269e624a99917d"
OTHER_HEAD = "62f567982fc33b6f8d72c4f3a8d8e192698d0c92"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_remote_report(path: Path, *, skipped: bool = True) -> None:
    skipped_checks = ["performance-tests"] if skipped else []
    _write_json(
        path,
        {
            "report": "stage3-remote-ci-final-20260615",
            "head_sha": HEAD,
            "remote_branch_sha": HEAD,
            "github_actions_check_runs": {
                "failed": 0,
                "in_progress": 0,
                "completed_skipped": len(skipped_checks),
                "skipped_checks": skipped_checks,
            },
        },
    )


def test_build_template_payloads_uses_performance_gate_specs(tmp_path: Path) -> None:
    payloads = build_template_payloads(tmp_path, current_head_sha=HEAD, release_sha=HEAD)
    specs = default_required_evidence(tmp_path)

    assert [payload["name"] for payload in payloads] == [spec.name for spec in specs]
    assert [Path(str(payload["path"])).name for payload in payloads] == [spec.path.name for spec in specs]
    assert {payload["name"] for payload in payloads} == {
        "load_performance_test",
        "capacity_target",
        "latency_error_rate_thresholds",
        "cost_guardrail",
        "performance_tests_skipped_disposition",
        "resource_sizing",
    }
    for payload, spec in zip(payloads, specs, strict=True):
        assert payload["status"] == "blocked"
        assert payload["template_not_evidence"] is True
        assert payload["real_evidence_collected"] is False
        assert payload["mutation_performed"] is False
        assert payload["deploy_performed"] is False
        assert payload["owner_approval_created"] is False
        assert payload["current_head_sha"] == HEAD
        assert payload["release_sha"] == HEAD
        assert payload["expected_ready_statuses"] == list(spec.expected_statuses)
        assert payload["status"] not in payload["expected_ready_statuses"]
        assert payload["required_owner_or_operator_actions"]
        assert payload["placeholders"]


def test_write_templates_creates_all_six_blocked_skeletons(tmp_path: Path) -> None:
    results = write_templates(tmp_path, current_head_sha=HEAD, release_sha=HEAD)

    assert len(results) == 6
    assert {result.status for result in results} == {"created"}
    assert all(result.written for result in results)
    for spec in default_required_evidence(tmp_path):
        payload = json.loads(spec.path.read_text(encoding="utf-8"))
        assert payload["name"] == spec.name
        assert payload["status"] == "blocked"
        assert payload["template_not_evidence"] is True
        assert payload["real_evidence_collected"] is False
        assert payload["mutation_performed"] is False
        assert payload["deploy_performed"] is False
        assert payload["owner_approval_created"] is False


def test_write_templates_does_not_overwrite_existing_files_without_force(tmp_path: Path) -> None:
    target = tmp_path / "stage5-load-performance-result-20260615.json"
    _write_json(target, {"status": "real_evidence_fixture", "current_head_sha": OTHER_HEAD})

    results = write_templates(tmp_path, current_head_sha=HEAD, release_sha=HEAD)

    assert json.loads(target.read_text(encoding="utf-8")) == {
        "status": "real_evidence_fixture",
        "current_head_sha": OTHER_HEAD,
    }
    skipped = next(result for result in results if result.name == "load_performance_test")
    assert skipped.status == "skipped_existing"
    assert skipped.written is False
    assert skipped.template_not_evidence is True
    assert skipped.real_evidence_collected is False


def test_write_templates_force_overwrites_template_files(tmp_path: Path) -> None:
    target = tmp_path / "stage5-load-performance-result-20260615.json"
    _write_json(
        target,
        {"status": "blocked", "template_not_evidence": True, "real_evidence_collected": False},
    )

    results = write_templates(tmp_path, current_head_sha=HEAD, release_sha=HEAD, force=True)

    overwritten = next(result for result in results if result.name == "load_performance_test")
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert overwritten.status == "overwritten"
    assert overwritten.written is True
    assert payload["status"] == "blocked"
    assert payload["current_head_sha"] == HEAD
    assert payload["release_sha"] == HEAD
    assert payload["template_not_evidence"] is True


def test_write_templates_force_refuses_to_overwrite_real_evidence_file(tmp_path: Path) -> None:
    target = tmp_path / "stage5-load-performance-result-20260615.json"
    _write_json(target, {"status": "load_performance_ready", "real_evidence_collected": True})

    results = write_templates(tmp_path, current_head_sha=HEAD, release_sha=HEAD, force=True)

    skipped = next(result for result in results if result.name == "load_performance_test")
    assert skipped.status == "skipped_existing_real_evidence"
    assert skipped.written is False
    assert skipped.error
    assert json.loads(target.read_text(encoding="utf-8")) == {
        "status": "load_performance_ready",
        "real_evidence_collected": True,
    }


def test_performance_capacity_gate_and_pack_stay_blocked_with_templates(tmp_path: Path) -> None:
    remote = tmp_path / "remote.json"
    _write_remote_report(remote)
    write_templates(tmp_path, current_head_sha=HEAD, release_sha=HEAD)

    gate = build_performance_capacity_gate(
        report_dir=tmp_path,
        remote_pr_report_path=remote,
        current_head_sha=HEAD,
        release_sha=HEAD,
    )
    pack = build_stage5_performance_evidence_pack(
        report_dir=tmp_path,
        remote_pr_report_path=remote,
        current_head_sha=HEAD,
        release_sha=HEAD,
    )

    assert gate.status == "performance_capacity_blocked"
    assert gate.performance_capacity_ready is False
    assert set(gate.missing_or_blocked_evidence) == set(REQUIRED_DOMAINS)
    assert {item.status for item in gate.required_evidence} == {"blocked"}
    assert all(item.ready is False for item in gate.required_evidence)
    assert pack.status == "controlled_commercial_pilot_blocked"
    assert pack.controlled_commercial_pilot_ready is False
    assert set(pack.missing_or_blocked_evidence) == set(REQUIRED_DOMAINS)


def test_report_writers_emit_json_and_markdown_summary(tmp_path: Path) -> None:
    payloads = build_template_payloads(tmp_path, current_head_sha=HEAD, release_sha=HEAD)
    results = write_templates(tmp_path, current_head_sha=HEAD, release_sha=HEAD)
    report = build_report(
        report_dir=tmp_path,
        payloads=payloads,
        write_results=results,
        current_head_sha=HEAD,
        release_sha=HEAD,
    )
    output_json = tmp_path / "controller-stage5-performance-templates-worker-20260615.json"
    output_md = tmp_path / "controller-stage5-performance-templates-worker-20260615.md"

    write_report(report, output_json)
    write_markdown_report(report, output_md)

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    markdown = output_md.read_text(encoding="utf-8")
    assert payload["status"] == "performance_evidence_templates_written"
    assert payload["template_not_evidence"] is True
    assert payload["real_evidence_collected"] is False
    assert payload["mutation_performed"] is False
    assert payload["deploy_performed"] is False
    assert payload["owner_approval_created"] is False
    assert len(payload["templates"]) == 6
    assert "# Stage 5 Performance Evidence Templates" in markdown
    assert "Template not evidence: `True`" in markdown
    assert render_markdown_report(report) == markdown


def test_cli_defaults_to_dry_run_json_and_markdown_summary(tmp_path: Path) -> None:
    output_json = tmp_path / "worker.json"
    output_md = tmp_path / "worker.md"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/commercial_stage5_performance_evidence_templates.py",
            "--report-dir",
            str(tmp_path / "reports"),
            "--current-head-sha",
            HEAD,
            "--release-sha",
            HEAD,
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    markdown = output_md.read_text(encoding="utf-8")
    assert payload["status"] == "performance_evidence_templates_dry_run"
    assert payload["current_head_sha"] == HEAD
    assert payload["release_sha"] == HEAD
    assert payload["template_not_evidence"] is True
    assert payload["real_evidence_collected"] is False
    assert len(payload["write_results"]) == 6
    assert all(result["status"] == "dry_run" for result in payload["write_results"])
    assert all(not result["written"] for result in payload["write_results"])
    assert "Stage 5 performance evidence template status" in completed.stdout
    assert "Owner approval created: False" in completed.stdout
    assert "# Stage 5 Performance Evidence Templates" in markdown


def test_cli_requires_explicit_write_templates_flag(tmp_path: Path) -> None:
    output_json = tmp_path / "worker.json"
    output_md = tmp_path / "worker.md"
    report_dir = tmp_path / "reports"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/commercial_stage5_performance_evidence_templates.py",
            "--report-dir",
            str(report_dir),
            "--current-head-sha",
            HEAD,
            "--release-sha",
            HEAD,
            "--write-templates",
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["status"] == "performance_evidence_templates_written"
    assert all(result["written"] for result in payload["write_results"])
    assert len(list(report_dir.glob("*.json"))) == 6
