from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_claim_scan import (
    build_claim_scan_report,
    render_markdown,
    write_reports,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_positive_claims_are_blocked(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        "\n".join(
            [
                "# X-Agent",
                "X-Agent is GA ready for customer rollout.",
                "Status: Production-Ready",
                "The SDK production-ready package is included.",
                "The Helm production-ready chart is included.",
            ]
        ),
    )

    report = build_claim_scan_report(
        root=tmp_path,
        scan_paths=("README.md",),
        current_head_sha="a" * 40,
    )

    assert report.status == "claim_safe_docs_blocked"
    assert report.claim_safe_docs_ready is False
    phrases = {match.phrase for match in report.violations}
    assert "GA ready" in phrases
    assert "unqualified Status: Production-Ready" in phrases
    assert "SDK production-ready" in phrases
    assert "Helm production-ready" in phrases
    assert report.allowed_matches == []
    assert report.blocked_phrase_count == len(report.violations)


def test_negative_and_boundary_context_is_allowed(tmp_path: Path) -> None:
    _write(
        tmp_path / "RELEASE_NOTES_v1.0.0.md",
        "\n".join(
            [
                "# Draft notes",
                "Forbidden claims:",
                "- GA ready",
                "- production ready",
                "- full Codex parity",
                "This RC pilot does not claim commercial delivery complete.",
                "不得声明 customer delivery complete.",
            ]
        ),
    )

    report = build_claim_scan_report(
        root=tmp_path,
        scan_paths=("RELEASE_NOTES_v1.0.0.md",),
        current_head_sha="b" * 40,
    )

    assert report.status == "claim_safe_docs_ready"
    assert report.claim_safe_docs_ready is True
    assert report.violations == []
    assert {match.phrase for match in report.allowed_matches} >= {
        "GA ready",
        "production ready",
        "full Codex parity",
        "commercial delivery complete",
        "customer delivery complete",
    }
    assert report.blocked_phrase_count == len(report.allowed_matches)


def test_missing_files_are_recorded_as_skipped(tmp_path: Path) -> None:
    _write(tmp_path / "README.md", "Controlled commercial pilot readiness only.\n")

    report = build_claim_scan_report(
        root=tmp_path,
        scan_paths=("README.md", "DEPLOYMENT.md"),
        current_head_sha="c" * 40,
    )

    assert report.status == "claim_safe_docs_ready"
    assert [item.path for item in report.scanned_files] == ["README.md"]
    assert len(report.skipped_files) == 1
    assert report.skipped_files[0].path == "DEPLOYMENT.md"
    assert report.skipped_files[0].reason == "missing"


def test_report_json_structure_and_markdown(tmp_path: Path) -> None:
    _write(tmp_path / "docs" / "COMMERCIAL_DEPLOYMENT_RUNBOOK.md", "Not GA ready; RC only.\n")
    output = tmp_path / "reports" / "claim.json"
    markdown = tmp_path / "reports" / "claim.md"

    report = build_claim_scan_report(
        root=tmp_path,
        scan_paths=("docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md",),
        current_head_sha="d" * 40,
    )
    write_reports(report, output, markdown)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "claim_safe_docs_ready"
    assert payload["claim_safe_docs_ready"] is True
    assert payload["current_head_sha"] == "d" * 40
    assert payload["mutation_performed"] is False
    assert payload["outbound_message_sent"] is False
    assert payload["claim_boundary"]["allowed"] == "controlled commercial pilot readiness"
    assert payload["blocked_phrase_count"] == 1
    assert payload["violations"] == []
    assert payload["allowed_matches"][0]["phrase"] == "GA ready"
    assert payload["scanned_files"][0]["path"] == "docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md"
    assert payload["skipped_files"] == []

    rendered = render_markdown(report)
    assert "claim_safe_docs_ready" in rendered
    assert "Allowed Boundary Matches" in markdown.read_text(encoding="utf-8")
