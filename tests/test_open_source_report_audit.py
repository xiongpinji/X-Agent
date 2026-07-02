from __future__ import annotations

from backend.app.core.open_source_api import OpenSourceCandidateRecord, OpenSourceDiscoveryReport, OpenSourceStatus
from backend.app.core.open_source_report_audit import audit_open_source_candidate, audit_open_source_report


def test_audit_open_source_report_accepts_mainline_report_model() -> None:
    report = OpenSourceDiscoveryReport(
        query="desktop automation",
        candidates=[
            OpenSourceCandidateRecord(
                name="pywinauto",
                source="seed",
                url="https://github.com/pywinauto/pywinauto",
                license="BSD-3-Clause",
                score=0.91,
                status=OpenSourceStatus.SHORTLISTED,
            )
        ],
        shortlist=[],
        blocked=[],
        snapshot={"provider_count": 1},
    )

    audit = audit_open_source_report(report)

    assert audit["kind"] == "open_source_report_audit"
    assert audit["ok"] is True
    assert audit["status"] == "passed"
    assert audit["summary"]["candidate_count"] == 1
    assert audit["summary"]["provider_count"] == 1
    assert audit["issues"] == []


def test_candidate_audit_flags_missing_license_low_score_archived_and_blocked() -> None:
    candidate = {
        "name": "old-tool",
        "source": "github",
        "url": "https://example.com/old-tool",
        "score": 0.2,
        "status": "blocked",
        "metadata": {"archived": True},
    }

    audit = audit_open_source_candidate(candidate)

    assert audit.risk_flags == ("missing_license", "low_score", "archived", "blocked")
    assert audit.normalized_score == 0.2


def test_report_audit_reports_duplicate_urls_and_medium_issues() -> None:
    report = {
        "query": "vector database",
        "providers": ["registry"],
        "candidates": [
            {"name": "alpha", "source": "registry", "url": "https://example.com/shared", "license": "MIT", "score": 0.8},
            {"name": "beta", "source": "registry", "url": "https://example.com/shared", "license": "", "score": 0.7},
        ],
        "shortlist": [],
        "blocked": [],
    }

    audit = audit_open_source_report(report)

    assert audit["ok"] is True
    assert audit["status"] == "passed"
    assert audit["duplicate_urls"] == ["https://example.com/shared"]
    assert [issue["code"] for issue in audit["issues"]] == [
        "open_source_candidate_missing_license",
        "open_source_duplicate_candidate_url",
    ]


def test_report_audit_requires_review_for_empty_or_providerless_report() -> None:
    audit = audit_open_source_report({"query": "missing"})

    assert audit["ok"] is False
    assert audit["status"] == "review_required"
    assert audit["summary"]["candidate_count"] == 0
    assert [issue["code"] for issue in audit["issues"]] == [
        "open_source_report_empty",
        "open_source_report_no_providers",
    ]


def test_report_audit_normalizes_original_kernel_hundred_point_scores() -> None:
    audit = audit_open_source_report(
        {
            "query": "desktop automation",
            "providers": ["seed"],
            "candidates": [
                {
                    "name": "UI-TARS-desktop",
                    "source": "seed",
                    "url": "https://github.com/bytedance/UI-TARS-desktop",
                    "license": "Apache-2.0",
                    "score": 75,
                }
            ],
        }
    )

    assert audit["summary"]["max_score"] == 0.75
    assert audit["candidates"][0]["normalized_score"] == 0.75
