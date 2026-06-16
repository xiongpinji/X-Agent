from __future__ import annotations

import json
from pathlib import Path

from scripts.rc_release_diff_review_gate import build_diff_review_gate


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_review(path: Path, *, count: int = 101, include_owner_gates: bool = True) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    owner_gate_lines = """
- Provider owner gate: verified through local Ollama smoke.
- feishu_webhook_contract
- github_issue_to_pr_dry_run
- github_issue_to_pr_execute_preflight
- hosted_github_actions_commercial_rc
""" if include_owner_gates else ""
    path.write_text(
        f"""
# X-Agent Commercial RC Diff Review

Status: locally acceptable for RC candidate staging after owner review.

Candidate source: docs/RC_STAGING_MANIFEST.md
Parity boundary: full_parity_claimed=false

Do not stage without owner approval:
- .agents/
- .codex/
- AGENTS.md
- COMPETITIVE_ANALYSIS_2026.md
- .xagent_runtime/

Observed local results:

- Release audit: passed, {count} candidate files, no secret-like findings, no manifest unsafe paths, no file hygiene findings.

Remaining owner gates:
{owner_gate_lines}
""",
        encoding="utf-8",
    )
    return path


def _reports(tmp_path: Path, *, count: int = 101) -> dict[str, Path]:
    paths = [f"file_{index}.py" for index in range(count)]
    release_audit = _write_json(
        tmp_path / "reports" / "rc-release-audit.json",
        {
            "status": "passed",
            "candidate_count": count,
            "manifest_count": count,
            "missing_from_manifest": [],
            "manifest_extra": [],
            "manifest_tracked_misclassified": [],
            "manifest_new_misclassified": [],
            "manifest_unsafe_paths": [],
            "secret_findings": [],
            "excluded_reference_findings": [],
            "local_path_findings": [],
            "file_hygiene_findings": [],
        },
    )
    staging = _write_json(
        tmp_path / "reports" / "rc-staging-plan.json",
        {
            "status": "planned",
            "file_count": count,
            "commands": [{"index": 1, "paths": paths}],
            "missing_files": [],
            "excluded_files": [],
            "errors": [],
        },
    )
    source = _write_json(
        tmp_path / "reports" / "rc-source-bundle.json",
        {
            "status": "created",
            "file_count": count,
            "files": [{"path": path, "size_bytes": 1, "sha256": f"{index:064x}"} for index, path in enumerate(paths)],
            "missing_files": [],
            "excluded_files": [],
            "errors": [],
        },
    )
    gap = _write_json(
        tmp_path / "reports" / "codex-hermes-gap-closure.json",
        {
            "summary": {
                "overall_status": "passed",
                "competitive_parity": {"full_parity_claimed": False},
            }
        },
    )
    owner = _write_json(
        tmp_path / "reports" / "rc-owner-gate-plan.json",
        {
            "status": "action_required",
            "gates": [
                {"name": "provider", "status": "verified"},
                {"name": "feishu_webhook_contract", "status": "action_required"},
                {"name": "github_issue_to_pr_dry_run", "status": "action_required"},
                {"name": "github_issue_to_pr_execute_preflight", "status": "action_required"},
                {"name": "hosted_github_actions_commercial_rc", "status": "action_required"},
            ],
        },
    )
    review = _write_review(tmp_path / "docs" / "RC_RELEASE_DIFF_REVIEW.md", count=count)
    return {
        "review": review,
        "release_audit": release_audit,
        "staging": staging,
        "source": source,
        "gap": gap,
        "owner": owner,
    }


def _gate(paths: dict[str, Path]):
    return build_diff_review_gate(
        review_path=paths["review"],
        release_audit_path=paths["release_audit"],
        staging_plan_path=paths["staging"],
        source_bundle_path=paths["source"],
        gap_matrix_path=paths["gap"],
        owner_gate_plan_path=paths["owner"],
    )


def test_diff_review_gate_passes_for_consistent_review_evidence(tmp_path: Path) -> None:
    report = _gate(_reports(tmp_path))

    assert report.status == "passed"
    assert report.candidate_file_count == 101
    assert {check.name: check.status for check in report.checks}["candidate_payload_consistency"] == "passed"


def test_diff_review_gate_rejects_stale_review_candidate_count(tmp_path: Path) -> None:
    paths = _reports(tmp_path, count=101)
    _write_review(paths["review"], count=74)

    report = _gate(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "review_evidence_freshness")
    assert "101 candidate files" in str(check.error)


def test_diff_review_gate_rejects_candidate_path_mismatch(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    _write_json(
        paths["staging"],
        {
            "status": "planned",
            "file_count": 101,
            "commands": [{"index": 1, "paths": ["different.py"]}],
            "missing_files": [],
            "excluded_files": [],
            "errors": [],
        },
    )

    report = _gate(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "candidate_payload_consistency")
    assert "candidate path mismatch" in str(check.error)


def test_diff_review_gate_rejects_unsafe_manifest_paths_from_release_audit(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    release = json.loads(paths["release_audit"].read_text(encoding="utf-8"))
    release["manifest_unsafe_paths"] = [{"path": "../outside.txt", "reason": "unsafe path segment"}]
    _write_json(paths["release_audit"], release)

    report = _gate(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "release_audit")
    assert "release audit manifest_unsafe_paths is not empty" in str(check.error)


def test_diff_review_gate_requires_manifest_unsafe_paths_field(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    release = json.loads(paths["release_audit"].read_text(encoding="utf-8"))
    release.pop("manifest_unsafe_paths")
    _write_json(paths["release_audit"], release)

    report = _gate(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "release_audit")
    assert "release audit manifest_unsafe_paths is missing" in str(check.error)


def test_diff_review_gate_rejects_full_parity_claim(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    _write_json(
        paths["gap"],
        {
            "summary": {
                "overall_status": "passed",
                "competitive_parity": {"full_parity_claimed": True},
            }
        },
    )

    report = _gate(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "parity_boundary")
    assert "full Codex/Hermes parity" in str(check.error)


def test_diff_review_gate_requires_pending_owner_gate_ids_in_review(tmp_path: Path) -> None:
    paths = _reports(tmp_path)
    _write_review(paths["review"], include_owner_gates=False)

    report = _gate(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "owner_gate_review")
    assert "feishu_webhook_contract" in str(check.error)
