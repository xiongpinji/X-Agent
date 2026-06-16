from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_delivery_owner_staging_preflight import (
    build_owner_staging_preflight,
    render_markdown_preflight,
    write_markdown_preflight,
    write_report,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _stage_paths() -> list[str]:
    return ["backend/app/core/storage.py", "tests/test_storage.py"]


def _manifest(paths: list[str] | None = None) -> dict[str, object]:
    stage_paths = paths or _stage_paths()
    return {
        "status": "original_kernel_delivery_manifest_ready",
        "stage_include_count": len(stage_paths),
        "stage_include_paths": stage_paths,
        "full_codex_parity_claimed": False,
    }


def _staging_review(paths: list[str] | None = None) -> dict[str, object]:
    stage_paths = paths or _stage_paths()
    return {
        "status": "staging_review_ready",
        "owner_gated": True,
        "eligible_stage_count": len(stage_paths),
        "blocked_stage_count": 0,
        "full_codex_parity_claimed": False,
        "paths": [
            {"path": path, "status": "eligible", "exists": True, "dirty": True}
            for path in stage_paths
        ],
    }


def _owner_packet(paths: list[str] | None = None) -> dict[str, object]:
    stage_paths = paths or _stage_paths()
    return {
        "status": "owner_staging_packet_ready",
        "owner_gated": True,
        "stage_paths": stage_paths,
        "stage_commands": [f"git add -- '{path}'" for path in stage_paths],
        "blocked_stage_count": 0,
        "full_codex_parity_claimed": False,
    }


def _write_inputs(tmp_path: Path, *, paths: list[str] | None = None) -> tuple[Path, Path, Path]:
    packet = tmp_path / "packet.json"
    staging = tmp_path / "staging.json"
    manifest = tmp_path / "manifest.json"
    _write_json(packet, _owner_packet(paths))
    _write_json(staging, _staging_review(paths))
    _write_json(manifest, _manifest(paths))
    return packet, staging, manifest


def test_owner_staging_preflight_ready_for_exact_owner_commands(tmp_path: Path) -> None:
    packet, staging, manifest = _write_inputs(tmp_path)

    report = build_owner_staging_preflight(
        owner_packet_path=packet,
        staging_review_path=staging,
        manifest_path=manifest,
        cached_diff_lines=[],
    )

    assert report.status == "owner_staging_preflight_ready"
    assert report.evidence_type == "commercial_delivery_owner_staging_preflight"
    assert report.owner_gated is True
    assert report.mutation_performed is False
    assert report.git_stage_performed is False
    assert report.git_commit_performed is False
    assert report.git_push_performed is False
    assert report.network_mutation_performed is False
    assert report.agent_execution_enabled is False
    assert report.full_codex_parity_claimed is False
    assert report.stage_command_count == 2
    assert report.stage_path_count == 2
    assert report.cached_staged_path_count == 0
    assert report.parsed_stage_paths == _stage_paths()
    assert {check.status for check in report.checks} == {"passed"}


def test_owner_staging_preflight_blocks_broad_stage_commands(tmp_path: Path) -> None:
    packet, staging, manifest = _write_inputs(tmp_path)
    payload = _owner_packet()
    payload["stage_commands"] = ["git add ."]
    _write_json(packet, payload)

    report = build_owner_staging_preflight(
        owner_packet_path=packet,
        staging_review_path=staging,
        manifest_path=manifest,
        cached_diff_lines=[],
    )

    assert report.status == "owner_staging_preflight_blocked"
    assert report.broad_stage_commands == ["git add ."]
    broad = next(check for check in report.checks if check.name == "no_broad_stage_commands")
    assert broad.status == "failed"


def test_owner_staging_preflight_blocks_protected_stage_paths(tmp_path: Path) -> None:
    protected_paths = ["backend/app/api/workbench.py"]
    packet, staging, manifest = _write_inputs(tmp_path, paths=protected_paths)

    report = build_owner_staging_preflight(
        owner_packet_path=packet,
        staging_review_path=staging,
        manifest_path=manifest,
        cached_diff_lines=[],
    )

    assert report.status == "owner_staging_preflight_blocked"
    assert report.protected_stage_paths == protected_paths
    protected = next(check for check in report.checks if check.name == "no_protected_stage_paths")
    assert protected.status == "failed"


def test_owner_staging_preflight_blocks_cached_index_drift(tmp_path: Path) -> None:
    packet, staging, manifest = _write_inputs(tmp_path)

    report = build_owner_staging_preflight(
        owner_packet_path=packet,
        staging_review_path=staging,
        manifest_path=manifest,
        cached_diff_lines=["backend/app/core/storage.py"],
    )

    assert report.status == "owner_staging_preflight_blocked"
    assert report.cached_staged_path_count == 1
    cached = next(
        check for check in report.checks if check.name == "no_cached_staged_paths_before_owner_staging"
    )
    assert cached.status == "failed"


def test_owner_staging_preflight_blocks_packet_staging_mismatch(tmp_path: Path) -> None:
    packet, staging, manifest = _write_inputs(tmp_path)
    payload = _owner_packet(["backend/app/core/storage.py"])
    _write_json(packet, payload)

    report = build_owner_staging_preflight(
        owner_packet_path=packet,
        staging_review_path=staging,
        manifest_path=manifest,
        cached_diff_lines=[],
    )

    assert report.status == "owner_staging_preflight_blocked"
    mismatch = next(check for check in report.checks if check.name == "packet_paths_match_staging_review")
    assert mismatch.status == "failed"


def test_owner_staging_preflight_blocks_full_codex_parity_claim(tmp_path: Path) -> None:
    packet, staging, manifest = _write_inputs(tmp_path)
    payload = _manifest()
    payload["full_codex_parity_claimed"] = True
    _write_json(manifest, payload)

    report = build_owner_staging_preflight(
        owner_packet_path=packet,
        staging_review_path=staging,
        manifest_path=manifest,
        cached_diff_lines=[],
    )

    assert report.status == "owner_staging_preflight_blocked"
    assert report.full_codex_parity_claimed is True
    parity = next(check for check in report.checks if check.name == "no_full_codex_parity_claim")
    assert parity.status == "failed"


def test_owner_staging_preflight_writes_json_and_markdown(tmp_path: Path) -> None:
    packet, staging, manifest = _write_inputs(tmp_path)
    report = build_owner_staging_preflight(
        owner_packet_path=packet,
        staging_review_path=staging,
        manifest_path=manifest,
        cached_diff_lines=[],
    )

    json_output = tmp_path / "preflight.json"
    md_output = tmp_path / "preflight.md"
    write_report(report, json_output)
    write_markdown_preflight(report, md_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = md_output.read_text(encoding="utf-8")
    assert payload["status"] == "owner_staging_preflight_ready"
    assert "Commercial Delivery Owner Staging Preflight" in markdown
    assert "backend/app/core/storage.py" in render_markdown_preflight(report)
