from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_codex_parity_disposition import (
    BLOCKED_STATUS,
    EXCLUDED_STATUS,
    build_codex_parity_disposition,
    render_markdown_report,
    write_markdown_report,
    write_report,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _excluded_boundary_payload() -> dict[str, object]:
    return {
        "status": "claim_safe_docs_ready",
        "claim_boundary": {
            "allowed": "controlled commercial pilot readiness only",
            "excluded_claims": [
                "GA ready",
                "production ready",
                "full Codex parity",
            ],
        },
        "full_codex_parity_claimed": False,
    }


def test_full_parity_excluded_satisfies_disposition(tmp_path: Path) -> None:
    source = tmp_path / "claim-safe.json"
    _write_json(source, _excluded_boundary_payload())

    report = build_codex_parity_disposition(source_paths=[source], current_head_sha="abc123")

    assert report.status == EXCLUDED_STATUS
    assert report.codex_parity_disposition_satisfied is True
    assert report.current_head_sha == "abc123"
    assert report.release_sha == "abc123"
    assert report.full_codex_parity_claimed is False
    assert report.full_codex_parity_proven is False
    assert report.full_codex_parity_excluded_from_ga_claim_boundary is True
    assert report.blockers == []
    assert report.mutation_performed is False
    assert report.outbound_message_sent is False
    assert report.deploy_tag_release_performed is False


def test_disallowed_full_parity_boundary_satisfies_disposition(tmp_path: Path) -> None:
    source = tmp_path / "claim-safe.json"
    _write_json(
        source,
        {
            "status": "claim_safe_docs_ready",
            "claim_boundary": {
                "allowed": "controlled commercial pilot readiness",
                "disallowed": [
                    "GA ready",
                    "production ready",
                    "full Codex parity",
                ],
            },
            "full_codex_parity_claimed": False,
        },
    )

    report = build_codex_parity_disposition(source_paths=[source], current_head_sha="abc123")

    assert report.status == EXCLUDED_STATUS
    assert report.codex_parity_disposition_satisfied is True
    assert report.full_codex_parity_excluded_from_ga_claim_boundary is True


def test_report_json_and_markdown_are_written(tmp_path: Path) -> None:
    source = tmp_path / "claim-safe.json"
    json_output = tmp_path / "stage5-codex-parity-disposition-20260615.json"
    markdown_output = tmp_path / "stage5-codex-parity-disposition-20260615.md"
    _write_json(source, _excluded_boundary_payload())

    report = build_codex_parity_disposition(source_paths=[source], current_head_sha="abc123")
    write_report(report, json_output)
    write_markdown_report(report, markdown_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = markdown_output.read_text(encoding="utf-8")
    rendered = render_markdown_report(report)
    assert payload["status"] == EXCLUDED_STATUS
    assert payload["codex_parity_disposition_satisfied"] is True
    assert payload["current_head_sha"] == "abc123"
    assert payload["release_sha"] == "abc123"
    assert payload["full_codex_parity_proven"] is False
    assert payload["mutation_performed"] is False
    assert "# Stage 5 Codex Parity Disposition" in markdown
    assert "Full Codex parity proven: `False`" in rendered


def test_parity_proven_claim_without_required_evidence_blocks(tmp_path: Path) -> None:
    source = tmp_path / "unsupported-parity.json"
    payload = _excluded_boundary_payload()
    payload.update(
        {
            "status": "codex_parity_proven",
            "full_codex_parity_claimed": True,
            "runtime_evidence_refs": ["runtime-smoke.json"],
        }
    )
    _write_json(source, payload)

    report = build_codex_parity_disposition(source_paths=[source], current_head_sha="abc123")

    assert report.status == BLOCKED_STATUS
    assert report.codex_parity_disposition_satisfied is False
    assert report.full_codex_parity_claimed is True
    assert report.full_codex_parity_proven is False
    assert report.full_codex_parity_excluded_from_ga_claim_boundary is False
    assert report.blockers == [f"unsupported parity proven claim in {source}"]
    assert report.sources[0].missing_proof_refs == [
        "api_evidence_refs",
        "ui_evidence_refs",
        "acceptance_evidence_refs",
    ]


def test_missing_exclusion_boundary_blocks_fail_safe(tmp_path: Path) -> None:
    source = tmp_path / "weak-boundary.json"
    _write_json(
        source,
        {
            "status": "claim_safe_docs_ready",
            "claim_boundary": {
                "allowed": "commercial readiness",
            },
        },
    )

    report = build_codex_parity_disposition(source_paths=[source], current_head_sha="abc123")

    assert report.status == BLOCKED_STATUS
    assert report.codex_parity_disposition_satisfied is False
    assert report.blockers == ["claim boundary does not explicitly exclude full Codex parity"]
