from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_delivery_staging_review import (
    build_staging_review,
    render_markdown_review,
    write_markdown_review,
    write_report,
)


def _write_manifest(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _base_manifest(stage_paths: list[str]) -> dict[str, object]:
    return {
        "status": "original_kernel_delivery_manifest_ready",
        "stage_include_count": len(stage_paths),
        "stage_include_paths": stage_paths,
        "full_codex_parity_claimed": False,
        "entrypoints_modified": False,
        "api_router_modified": False,
        "control_plane_modified": False,
        "frontend_modified": False,
        "agent_loop_modified": False,
        "backend_core_init_modified": False,
    }


def test_staging_review_ready_for_explicit_dirty_paths(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    stage_paths = [
        "backend/app/core/storage.py",
        "tests/test_storage.py",
    ]
    _write_manifest(manifest, _base_manifest(stage_paths))

    report = build_staging_review(
        manifest_path=manifest,
        git_status_lines=[
            "?? backend/app/core/storage.py",
            "?? tests/test_storage.py",
            " M frontend/src/App.tsx",
        ],
    )

    assert report.status == "staging_review_ready"
    assert report.owner_gated is True
    assert report.mutation_performed is False
    assert report.git_stage_performed is False
    assert report.eligible_stage_count == 2
    assert report.blocked_stage_count == 0
    assert report.unchanged_stage_count == 0
    assert "git add -- backend/app/core/storage.py" in report.owner_review_commands
    assert {check.status for check in report.checks} == {"passed"}


def test_staging_review_marks_clean_manifest_paths_unchanged(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, _base_manifest(["backend/app/core/storage.py", "tests/test_storage.py"]))

    report = build_staging_review(
        manifest_path=manifest,
        git_status_lines=["?? backend/app/core/storage.py"],
    )

    assert report.status == "staging_review_ready"
    assert report.eligible_stage_count == 1
    assert report.unchanged_stage_count == 1
    clean = next(item for item in report.paths if item.status == "unchanged")
    assert clean.path == "tests/test_storage.py"


def test_staging_review_blocks_protected_paths(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, _base_manifest(["backend/app/api/workbench.py"]))

    report = build_staging_review(
        manifest_path=manifest,
        git_status_lines=[" M backend/app/api/workbench.py"],
    )

    assert report.status == "staging_review_blocked"
    assert report.blocked_stage_count == 1
    protected = next(check for check in report.checks if check.name == "no_protected_stage_paths")
    assert protected.status == "failed"
    assert report.paths[0].status == "blocked"


def test_staging_review_blocks_mismatched_stage_count(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    payload = _base_manifest(["backend/app/core/storage.py"])
    payload["stage_include_count"] = 3
    _write_manifest(manifest, payload)

    report = build_staging_review(
        manifest_path=manifest,
        git_status_lines=["?? backend/app/core/storage.py"],
    )

    assert report.status == "staging_review_blocked"
    count = next(check for check in report.checks if check.name == "stage_include_count_matches")
    assert count.status == "failed"


def test_staging_review_blocks_missing_manifest(tmp_path: Path) -> None:
    report = build_staging_review(
        manifest_path=tmp_path / "missing.json",
        git_status_lines=[],
    )

    assert report.status == "staging_review_blocked"
    readable = next(check for check in report.checks if check.name == "manifest_readable")
    assert readable.status == "failed"


def test_write_staging_review_json_and_markdown(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, _base_manifest(["backend/app/core/storage.py"]))
    report = build_staging_review(
        manifest_path=manifest,
        git_status_lines=["?? backend/app/core/storage.py"],
    )

    json_output = tmp_path / "review.json"
    md_output = tmp_path / "review.md"
    write_report(report, json_output)
    write_markdown_review(report, md_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = md_output.read_text(encoding="utf-8")
    assert payload["status"] == "staging_review_ready"
    assert "Commercial Delivery Staging Review" in markdown
    assert "backend/app/core/storage.py" in render_markdown_review(report)
