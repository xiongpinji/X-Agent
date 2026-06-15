from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_performance_capacity_gate import (
    build_performance_capacity_gate,
    render_markdown_report,
    write_markdown_report,
    write_report,
)

HEAD = "84ee203bf6676f3abf86a8f534269e624a99917d"
OTHER_HEAD = "62f567982fc33b6f8d72c4f3a8d8e192698d0c92"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_remote_report(path: Path, *, head: str = HEAD, skipped: bool = True) -> None:
    skipped_checks = ["performance-tests"] if skipped else []
    _write_json(
        path,
        {
            "report": "stage3-remote-ci-final-20260615",
            "head_sha": head,
            "remote_branch_sha": head,
            "github_actions_check_runs": {
                "failed": 0,
                "in_progress": 0,
                "completed_skipped": len(skipped_checks),
                "skipped_checks": skipped_checks,
            },
        },
    )


def _base_payload(status: str, *, head: str = HEAD, release_sha: str = HEAD) -> dict[str, object]:
    return {
        "status": status,
        "current_head_sha": head,
        "release_sha": release_sha,
    }


def _write_complete_evidence(report_dir: Path, *, head: str = HEAD, release_sha: str = HEAD) -> None:
    _write_json(
        report_dir / "stage5-load-performance-result-20260615.json",
        {
            **_base_payload("load_performance_ready", head=head, release_sha=release_sha),
            "test_run_url": "https://ci.example/runs/perf-1",
            "results": {"requests": 50000},
        },
    )
    _write_json(
        report_dir / "stage5-capacity-target-20260615.json",
        {
            **_base_payload("capacity_target_ready", head=head, release_sha=release_sha),
            "target_rps": 120,
            "concurrent_users": 80,
        },
    )
    _write_json(
        report_dir / "stage5-latency-error-thresholds-20260615.json",
        {
            **_base_payload("latency_error_thresholds_ready", head=head, release_sha=release_sha),
            "latency_p95_ms": 180,
            "max_latency_p95_ms": 250,
            "latency_p99_ms": 320,
            "max_latency_p99_ms": 500,
            "error_rate": 0.002,
            "max_error_rate": 0.01,
        },
    )
    _write_json(
        report_dir / "stage5-cost-guardrail-20260615.json",
        {
            **_base_payload("cost_guardrail_ready", head=head, release_sha=release_sha),
            "estimated_monthly_cost": 800,
            "max_monthly_cost": 1000,
        },
    )
    _write_json(
        report_dir / "stage5-performance-tests-skipped-disposition-20260615.json",
        {
            **_base_payload("performance_tests_skipped_disposition_ready", head=head, release_sha=release_sha),
            "performance_tests_skipped_disposition": True,
            "skipped_check": "performance-tests",
        },
    )
    _write_json(
        report_dir / "stage5-resource-sizing-20260615.json",
        {
            **_base_payload("resource_sizing_ready", head=head, release_sha=release_sha),
            "resource_sizing": {"replicas": 3, "cpu": "1000m", "memory": "2Gi"},
        },
    )


def test_performance_capacity_gate_blocks_when_all_evidence_missing(tmp_path: Path) -> None:
    remote = tmp_path / "remote.json"
    _write_remote_report(remote)

    report = build_performance_capacity_gate(
        report_dir=tmp_path,
        remote_pr_report_path=remote,
        current_head_sha=HEAD,
        release_sha=HEAD,
    )

    assert report.status == "performance_capacity_blocked"
    assert report.performance_capacity_ready is False
    assert set(report.missing_or_blocked_evidence) == {
        "load_performance_test",
        "capacity_target",
        "latency_error_rate_thresholds",
        "cost_guardrail",
        "performance_tests_skipped_disposition",
        "resource_sizing",
    }


def test_performance_capacity_gate_passes_complete_temporary_evidence(tmp_path: Path) -> None:
    remote = tmp_path / "remote.json"
    _write_remote_report(remote)
    _write_complete_evidence(tmp_path)

    report = build_performance_capacity_gate(
        report_dir=tmp_path,
        remote_pr_report_path=remote,
        current_head_sha=HEAD,
        release_sha=HEAD,
    )

    assert report.status == "performance_capacity_ready"
    assert report.performance_capacity_ready is True
    assert report.current_head_sha == HEAD
    assert report.release_sha == HEAD
    assert report.missing_or_blocked_evidence == []
    assert {check.status for check in report.checks} == {"passed"}
    assert all(evidence.ready for evidence in report.required_evidence)


def test_performance_capacity_gate_blocks_skipped_check_without_disposition(tmp_path: Path) -> None:
    remote = tmp_path / "remote.json"
    _write_remote_report(remote, skipped=True)
    _write_complete_evidence(tmp_path)
    (tmp_path / "stage5-performance-tests-skipped-disposition-20260615.json").unlink()

    report = build_performance_capacity_gate(
        report_dir=tmp_path,
        remote_pr_report_path=remote,
        current_head_sha=HEAD,
        release_sha=HEAD,
    )

    assert report.status == "performance_capacity_blocked"
    assert "performance_tests_skipped_disposition" in report.missing_or_blocked_evidence
    skip_check = next(check for check in report.checks if check.name == "skipped_performance_tests_disposition_ready")
    assert skip_check.status == "failed"


def test_performance_capacity_gate_blocks_threshold_breach(tmp_path: Path) -> None:
    remote = tmp_path / "remote.json"
    _write_remote_report(remote)
    _write_complete_evidence(tmp_path)
    _write_json(
        tmp_path / "stage5-latency-error-thresholds-20260615.json",
        {
            **_base_payload("latency_error_thresholds_ready"),
            "latency_p95_ms": 350,
            "max_latency_p95_ms": 250,
            "error_rate": 0.02,
            "max_error_rate": 0.01,
        },
    )

    report = build_performance_capacity_gate(
        report_dir=tmp_path,
        remote_pr_report_path=remote,
        current_head_sha=HEAD,
        release_sha=HEAD,
    )

    assert report.status == "performance_capacity_blocked"
    assert "latency_error_rate_thresholds" in report.missing_or_blocked_evidence
    thresholds = next(item for item in report.required_evidence if item.name == "latency_error_rate_thresholds")
    assert thresholds.error is not None
    assert "threshold breached" in thresholds.error


def test_performance_capacity_gate_blocks_sha_mismatch(tmp_path: Path) -> None:
    remote = tmp_path / "remote.json"
    _write_remote_report(remote)
    _write_complete_evidence(tmp_path, head=OTHER_HEAD, release_sha=OTHER_HEAD)

    report = build_performance_capacity_gate(
        report_dir=tmp_path,
        remote_pr_report_path=remote,
        current_head_sha=HEAD,
        release_sha=HEAD,
    )

    assert report.status == "performance_capacity_blocked"
    assert set(report.missing_or_blocked_evidence) == {
        "load_performance_test",
        "capacity_target",
        "latency_error_rate_thresholds",
        "cost_guardrail",
        "performance_tests_skipped_disposition",
        "resource_sizing",
    }
    sha_error = next(item.error for item in report.required_evidence if item.name == "load_performance_test")
    assert sha_error is not None
    assert "current_head_sha missing or not bound" in sha_error


def test_performance_capacity_gate_writes_json_and_markdown(tmp_path: Path) -> None:
    remote = tmp_path / "remote.json"
    _write_remote_report(remote)
    _write_complete_evidence(tmp_path)
    report = build_performance_capacity_gate(
        report_dir=tmp_path,
        remote_pr_report_path=remote,
        current_head_sha=HEAD,
        release_sha=HEAD,
    )
    output_json = tmp_path / "stage5-performance-capacity-gate-20260615.json"
    output_md = tmp_path / "stage5-performance-capacity-gate-20260615.md"

    write_report(report, output_json)
    write_markdown_report(report, output_md)

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    markdown = output_md.read_text(encoding="utf-8")
    assert payload["status"] == "performance_capacity_ready"
    assert payload["current_head_sha"] == HEAD
    assert payload["release_sha"] == HEAD
    assert payload["mutation_performed"] is False
    assert payload["outbound_message_sent"] is False
    assert payload["deploy_tag_release_performed"] is False
    assert "# Stage 5 Performance Capacity Gate" in markdown
    assert "performance_capacity_ready" in markdown
    assert render_markdown_report(report) == markdown
