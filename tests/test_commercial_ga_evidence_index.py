from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_ga_evidence_index import (
    EvidenceSpec,
    build_single_sha_evidence_index,
    write_markdown_report,
    write_report,
)

HEAD = "98c7919cf1a5784ad776172e3cf4f3b43cb2e24d"
OTHER_SHA = "62f567982fc33b6f8d72c4f3a8d8e192698d0c92"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _specs(report_dir: Path) -> list[EvidenceSpec]:
    return [
        EvidenceSpec("source_tree", report_dir / "source.json", ("ready",), "ga_required"),
        EvidenceSpec("remote_ci", report_dir / "remote.json", ("passed",), "ga_required"),
        EvidenceSpec("real_staging_rehearsal", report_dir / "staging.json", ("ready",), "ga_required"),
        EvidenceSpec("production_rehearsal", report_dir / "production.json", ("ready",), "ga_required"),
        EvidenceSpec("security_compliance", report_dir / "security.json", ("ready",), "ga_required"),
        EvidenceSpec("ops_support", report_dir / "ops.json", ("ready",), "ga_required"),
        EvidenceSpec("claim_safe_docs", report_dir / "claims.json", ("ready",), "claim_guardrail"),
        EvidenceSpec("performance_capacity", report_dir / "performance.json", ("ready",), "ga_required"),
        EvidenceSpec("codex_parity_disposition", report_dir / "parity.json", ("codex_parity_excluded",), "claim_guardrail"),
        EvidenceSpec("artifacts_release", report_dir / "artifacts.json", ("ready",), "ga_required"),
        EvidenceSpec("customer_handoff", report_dir / "handoff.json", ("ready",), "ga_required"),
    ]


def _write_all_ready(report_dir: Path, *, sha: str = HEAD) -> None:
    for spec in _specs(report_dir):
        status = "codex_parity_excluded" if spec.name == "codex_parity_disposition" else "ready"
        if spec.name == "remote_ci":
            status = "passed"
        _write_json(
            spec.path,
            {
                "status": status,
                "release_sha": sha,
                "mutation_performed": False,
                "outbound_message_sent": False,
                "deploy_tag_release_performed": False,
            },
        )


def test_all_missing_fail_closed(tmp_path: Path) -> None:
    report = build_single_sha_evidence_index(
        report_dir=tmp_path,
        selected_sha=HEAD,
        current_head_sha=HEAD,
        specs=_specs(tmp_path),
    )

    assert report.status == "single_sha_evidence_index_blocked"
    assert report.single_sha_evidence_index_ready is False
    assert set(report.missing_or_mismatched) == {spec.name for spec in _specs(tmp_path)}
    assert all(item.ready is False for item in report.evidence_items)
    assert all(item.error and "report not found" in item.error for item in report.evidence_items)
    assert report.mutation_performed is False
    assert report.outbound_message_sent is False
    assert report.deploy_tag_release_performed is False


def test_sha_mismatch_fails(tmp_path: Path) -> None:
    _write_all_ready(tmp_path, sha=OTHER_SHA)

    report = build_single_sha_evidence_index(
        report_dir=tmp_path,
        selected_sha=HEAD,
        current_head_sha=HEAD,
        specs=_specs(tmp_path),
    )

    assert report.status == "single_sha_evidence_index_blocked"
    assert report.single_sha_evidence_index_ready is False
    assert set(report.missing_or_mismatched) == {spec.name for spec in _specs(tmp_path)}
    assert all(item.bound_sha == OTHER_SHA for item in report.evidence_items)
    assert all(item.sha_matches_selected is False for item in report.evidence_items)


def test_all_ready_and_single_sha_passes(tmp_path: Path) -> None:
    _write_all_ready(tmp_path, sha=HEAD)

    report = build_single_sha_evidence_index(
        report_dir=tmp_path,
        selected_sha=HEAD,
        current_head_sha=HEAD,
        specs=_specs(tmp_path),
    )

    assert report.status == "single_sha_evidence_index_ready"
    assert report.single_sha_evidence_index_ready is True
    assert report.missing_or_mismatched == []
    assert all(item.ready for item in report.evidence_items)
    assert all(item.bound_sha == HEAD for item in report.evidence_items)


def test_current_repository_run_blocks_with_json_shape(tmp_path: Path) -> None:
    report = build_single_sha_evidence_index(selected_sha=HEAD, current_head_sha=HEAD)
    json_output = tmp_path / "index.json"
    markdown_output = tmp_path / "index.md"

    write_report(report, json_output)
    write_markdown_report(report, markdown_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = markdown_output.read_text(encoding="utf-8")
    assert payload["status"] == "single_sha_evidence_index_blocked"
    assert payload["single_sha_evidence_index_ready"] is False
    assert payload["selected_sha"] == HEAD
    assert payload["current_head_sha"] == HEAD
    assert payload["mutation_performed"] is False
    assert payload["outbound_message_sent"] is False
    assert payload["deploy_tag_release_performed"] is False
    assert "evidence_items" in payload
    assert "missing_or_mismatched" in payload
    assert "claim_boundary" in payload
    assert len(payload["evidence_items"]) >= 11
    assert "real_staging_rehearsal" in payload["missing_or_mismatched"]
    assert "# Stage 5 Single-SHA Evidence Index" in markdown
