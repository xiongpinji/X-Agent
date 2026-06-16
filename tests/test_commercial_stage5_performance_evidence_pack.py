from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_stage5_performance_evidence_pack import (
    REQUIRED_DOMAINS,
    build_stage5_performance_evidence_pack,
    render_markdown_report,
    write_json_report,
    write_markdown_report,
)

HEAD = "84ee203bf6676f3abf86a8f534269e624a99917d"


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


def _base_payload(status: str) -> dict[str, object]:
    return {
        "status": status,
        "current_head_sha": HEAD,
        "release_sha": HEAD,
    }


def _write_ready_evidence(report_dir: Path) -> None:
    _write_json(
        report_dir / "stage5-load-performance-result-20260615.json",
        {
            **_base_payload("load_performance_ready"),
            "run_id": "perf-run-1",
            "results": {"requests": 50000},
        },
    )
    _write_json(
        report_dir / "stage5-capacity-target-20260615.json",
        {
            **_base_payload("capacity_target_ready"),
            "target_rps": 120,
            "concurrent_users": 80,
        },
    )
    _write_json(
        report_dir / "stage5-latency-error-thresholds-20260615.json",
        {
            **_base_payload("latency_error_rate_thresholds_ready"),
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
            **_base_payload("cost_guardrail_ready"),
            "estimated_monthly_cost": 800,
            "max_monthly_cost": 1000,
        },
    )
    _write_json(
        report_dir / "stage5-performance-tests-skipped-disposition-20260615.json",
        {
            **_base_payload("performance_tests_skipped_disposition_ready"),
            "performance_tests_skipped_disposition": True,
            "skipped_check": "performance-tests",
        },
    )
    _write_json(
        report_dir / "stage5-resource-sizing-20260615.json",
        {
            **_base_payload("resource_sizing_ready"),
            "resource_sizing": {"replicas": 3, "cpu": "1000m", "memory": "2Gi"},
        },
    )


def test_evidence_pack_blocks_when_source_evidence_missing(tmp_path: Path) -> None:
    remote = tmp_path / "remote.json"
    _write_remote_report(remote)

    pack = build_stage5_performance_evidence_pack(
        report_dir=tmp_path,
        remote_pr_report_path=remote,
        current_head_sha=HEAD,
        release_sha=HEAD,
    )

    assert pack.status == "controlled_commercial_pilot_blocked"
    assert pack.controlled_commercial_pilot_ready is False
    assert set(pack.missing_or_blocked_evidence) == set(REQUIRED_DOMAINS)
    assert pack.mutation_performed is False
    assert pack.outbound_message_sent is False
    assert pack.deploy_tag_release_performed is False


def test_evidence_pack_passes_ready_fixture(tmp_path: Path) -> None:
    remote = tmp_path / "remote.json"
    _write_remote_report(remote)
    _write_ready_evidence(tmp_path)

    pack = build_stage5_performance_evidence_pack(
        report_dir=tmp_path,
        remote_pr_report_path=remote,
        current_head_sha=HEAD,
        release_sha=HEAD,
    )

    assert pack.status == "controlled_commercial_pilot_ready"
    assert pack.controlled_commercial_pilot_ready is True
    assert pack.readiness_scope == "controlled_commercial_pilot"
    assert pack.current_head_sha == HEAD
    assert pack.release_sha == HEAD
    assert pack.missing_or_blocked_evidence == []
    assert {check.status for check in pack.checks} == {"passed"}
    assert {domain.name for domain in pack.required_domains} == set(REQUIRED_DOMAINS)
    assert all(domain.ready for domain in pack.required_domains)


def test_evidence_pack_blocks_threshold_evidence_missing(tmp_path: Path) -> None:
    remote = tmp_path / "remote.json"
    _write_remote_report(remote)
    _write_ready_evidence(tmp_path)
    _write_json(
        tmp_path / "stage5-latency-error-thresholds-20260615.json",
        {
            **_base_payload("latency_error_rate_thresholds_ready"),
            "latency_p95_ms": 180,
            "max_latency_p95_ms": 250,
        },
    )

    pack = build_stage5_performance_evidence_pack(
        report_dir=tmp_path,
        remote_pr_report_path=remote,
        current_head_sha=HEAD,
        release_sha=HEAD,
    )

    assert pack.status == "controlled_commercial_pilot_blocked"
    assert "latency_error_rate_thresholds" in pack.missing_or_blocked_evidence
    threshold_domain = next(domain for domain in pack.required_domains if domain.name == "latency_error_rate_thresholds")
    assert threshold_domain.blocker is not None
    assert "missing error-rate threshold evidence" in threshold_domain.blocker


def test_evidence_pack_blocks_skipped_performance_tests_without_disposition(tmp_path: Path) -> None:
    remote = tmp_path / "remote.json"
    _write_remote_report(remote, skipped=True)
    _write_ready_evidence(tmp_path)
    (tmp_path / "stage5-performance-tests-skipped-disposition-20260615.json").unlink()

    pack = build_stage5_performance_evidence_pack(
        report_dir=tmp_path,
        remote_pr_report_path=remote,
        current_head_sha=HEAD,
        release_sha=HEAD,
    )

    assert pack.status == "controlled_commercial_pilot_blocked"
    assert "performance_tests_skipped_disposition" in pack.missing_or_blocked_evidence
    skip_check = next(check for check in pack.checks if check.name == "skipped_performance_tests_disposed")
    assert skip_check.status == "blocked"


def test_evidence_pack_writes_json_and_markdown(tmp_path: Path) -> None:
    remote = tmp_path / "remote.json"
    _write_remote_report(remote)
    _write_ready_evidence(tmp_path)
    pack = build_stage5_performance_evidence_pack(
        report_dir=tmp_path,
        remote_pr_report_path=remote,
        current_head_sha=HEAD,
        release_sha=HEAD,
        source_gate_report_path=tmp_path / "source-gate.json",
    )
    output_json = tmp_path / "stage5-performance-evidence-pack-20260615.json"
    output_md = tmp_path / "stage5-performance-evidence-pack-20260615.md"

    write_json_report(pack, output_json)
    write_markdown_report(pack, output_md)

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    markdown = output_md.read_text(encoding="utf-8")
    assert payload["status"] == "controlled_commercial_pilot_ready"
    assert payload["readiness_scope"] == "controlled_commercial_pilot"
    assert payload["mutation_performed"] is False
    assert payload["outbound_message_sent"] is False
    assert payload["deploy_tag_release_performed"] is False
    assert "# Stage 5 Performance Capacity Evidence Pack" in markdown
    assert "controlled_commercial_pilot_ready" in markdown
    assert render_markdown_report(pack) == markdown
