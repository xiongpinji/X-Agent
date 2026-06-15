from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_stage5_environment_evidence_pack import (
    PRODUCTION_REQUIRED_EVIDENCE,
    STAGING_REQUIRED_EVIDENCE,
    build_environment_evidence_pack,
    render_markdown_report,
    write_json_report,
    write_markdown_report,
)

HEAD = "a2b9b7fabc694b9f7d2a254019dacac64d89a20f"
OTHER_SHA = "b1f4706448f53643396d0c45bb6e8ba4755e1dfe"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _evidence(names: tuple[str, ...], *, sha: str = HEAD, blocked: str | None = None) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for name in names:
        ready = name != blocked
        records.append(
            {
                "name": name,
                "path": f".xagent_runtime/reports/{name}.json",
                "status": "passed" if ready else "blocked",
                "bound_sha": sha,
                "sha_matches_release": sha == HEAD,
                "ready": ready,
                "error": None if ready else "fixture blocker",
            }
        )
    return records


def _write_rehearsal_report(
    path: Path,
    environment: str,
    *,
    sha: str = HEAD,
    ready: bool = True,
    blocked_item: str | None = None,
) -> None:
    names = STAGING_REQUIRED_EVIDENCE if environment == "staging" else PRODUCTION_REQUIRED_EVIDENCE
    status = f"{environment}_rehearsal_ready" if ready else f"{environment}_rehearsal_blocked"
    _write_json(
        path,
        {
            "status": status,
            "environment": environment,
            "current_head_sha": HEAD,
            "release_sha": sha,
            "rehearsal_ready": ready,
            "mutation_performed": False,
            "outbound_message_sent": False,
            "deploy_tag_release_performed": False,
            "workflow_dispatch_performed": False,
            "cluster_mutation_performed_by_gate": False,
            "evidence": _evidence(names, sha=sha, blocked=blocked_item),
            "missing_or_mismatched": [blocked_item] if blocked_item else [],
        },
    )


def test_pack_blocks_when_staging_rehearsal_is_blocked(tmp_path: Path) -> None:
    staging = tmp_path / "staging.json"
    production = tmp_path / "production.json"
    _write_rehearsal_report(staging, "staging", ready=False, blocked_item="staging_smoke_tests")
    _write_rehearsal_report(production, "production")

    report = build_environment_evidence_pack(
        staging_report=staging,
        production_report=production,
        current_head_sha=HEAD,
    )

    assert report.status == "environment_rehearsal_evidence_pack_blocked"
    assert report.controlled_commercial_pilot_readiness is False
    assert "staging_smoke_tests" in report.missing_or_blocked_evidence
    assert report.mutation_performed is False
    assert report.deploy_performed is False
    assert report.workflow_dispatch_performed is False


def test_pack_blocks_when_production_rehearsal_is_missing(tmp_path: Path) -> None:
    staging = tmp_path / "staging.json"
    production = tmp_path / "missing-production.json"
    _write_rehearsal_report(staging, "staging")

    report = build_environment_evidence_pack(
        staging_report=staging,
        production_report=production,
        current_head_sha=HEAD,
    )

    assert report.status == "environment_rehearsal_evidence_pack_blocked"
    assert set(report.missing_or_blocked_evidence) == set(PRODUCTION_REQUIRED_EVIDENCE)
    production_summary = next(item for item in report.reports if item.environment == "production")
    assert production_summary.ready is False
    assert "missing rehearsal report" in production_summary.errors[0]


def test_pack_accepts_complete_ready_fixture(tmp_path: Path) -> None:
    staging = tmp_path / "staging.json"
    production = tmp_path / "production.json"
    _write_rehearsal_report(staging, "staging")
    _write_rehearsal_report(production, "production")

    report = build_environment_evidence_pack(
        staging_report=staging,
        production_report=production,
        current_head_sha=HEAD,
    )

    assert report.status == "environment_rehearsal_evidence_pack_ready"
    assert report.controlled_commercial_pilot_readiness is True
    assert report.release_sha == HEAD
    assert report.missing_or_blocked_evidence == []
    assert report.claim_boundary["allowed"] == "controlled commercial pilot readiness"
    assert "GA ready" in report.claim_boundary["forbidden"]


def test_pack_blocks_on_sha_mismatch(tmp_path: Path) -> None:
    staging = tmp_path / "staging.json"
    production = tmp_path / "production.json"
    _write_rehearsal_report(staging, "staging", sha=OTHER_SHA)
    _write_rehearsal_report(production, "production")

    report = build_environment_evidence_pack(
        staging_report=staging,
        production_report=production,
        current_head_sha=HEAD,
        release_sha=HEAD,
    )

    assert report.status == "environment_rehearsal_evidence_pack_blocked"
    staging_summary = next(item for item in report.reports if item.environment == "staging")
    assert "report release_sha does not match selected release_sha" in staging_summary.errors
    assert set(report.missing_or_blocked_evidence) == set(STAGING_REQUIRED_EVIDENCE)


def test_pack_writes_json_and_markdown(tmp_path: Path) -> None:
    staging = tmp_path / "staging.json"
    production = tmp_path / "production.json"
    output_json = tmp_path / "pack.json"
    output_md = tmp_path / "pack.md"
    _write_rehearsal_report(staging, "staging")
    _write_rehearsal_report(production, "production")
    report = build_environment_evidence_pack(
        staging_report=staging,
        production_report=production,
        current_head_sha=HEAD,
    )

    write_json_report(report, output_json)
    write_markdown_report(report, output_md)

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    markdown = output_md.read_text(encoding="utf-8")
    assert payload["status"] == "environment_rehearsal_evidence_pack_ready"
    assert payload["deploy_performed"] is False
    assert "Stage 5 Environment Rehearsal Evidence Pack" in markdown
    assert "production ready" in markdown
    assert render_markdown_report(report) == markdown
