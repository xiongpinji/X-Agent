from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.commercial_delivery_owner_post_staging_verifier import (
    build_owner_post_staging_verification,
    render_markdown_verification,
    write_markdown_verification,
    write_report,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _stage_paths() -> list[str]:
    return ["backend/app/core/storage.py", "tests/test_storage.py"]


def _digest_values(values: list[str]) -> str:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _path_set_digest(paths: list[str]) -> str:
    return _digest_values(sorted(set(paths)))


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
    stage_commands = [f"git add -- '{path}'" for path in stage_paths]
    return {
        "status": "owner_staging_packet_ready",
        "owner_gated": True,
        "stage_paths": stage_paths,
        "stage_path_digest": _digest_values(stage_paths),
        "stage_commands": stage_commands,
        "stage_command_digest": _digest_values(stage_commands),
        "blocked_stage_count": 0,
        "summary": {
            "secondary_pending_count": 0,
            "secondary_handoff_next_count": 1,
            "secondary_handoff_next_queue": ["integration_review_action_status_board.py"],
            "secondary_handoff_completed_count": 44,
            "secondary_handoff_latest_completed_candidate": "integration_review_answer_action_matrix.py",
        },
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


def test_owner_post_staging_verifier_ready_for_exact_cached_paths(tmp_path: Path) -> None:
    packet, staging, manifest = _write_inputs(tmp_path)

    report = build_owner_post_staging_verification(
        owner_packet_path=packet,
        staging_review_path=staging,
        manifest_path=manifest,
        cached_diff_lines=list(reversed(_stage_paths())),
    )

    assert report.status == "owner_post_staging_verification_ready"
    assert report.evidence_type == "commercial_delivery_owner_post_staging_verification"
    assert report.owner_gated is True
    assert report.mutation_performed is False
    assert report.git_stage_performed is False
    assert report.git_commit_performed is False
    assert report.git_push_performed is False
    assert report.network_mutation_performed is False
    assert report.agent_execution_enabled is False
    assert report.full_codex_parity_claimed is False
    assert report.expected_stage_path_count == 2
    assert report.cached_staged_path_count == 2
    assert report.stage_path_digest == _digest_values(_stage_paths())
    assert report.stage_command_digest == _digest_values([f"git add -- '{path}'" for path in _stage_paths()])
    assert report.expected_stage_path_set_digest == _path_set_digest(_stage_paths())
    assert report.cached_staged_path_set_digest == _path_set_digest(_stage_paths())
    assert report.summary["secondary_pending_count"] == 0
    assert report.summary["secondary_handoff_next_count"] == 1
    assert report.summary["secondary_handoff_next_queue"] == ["integration_review_action_status_board.py"]
    assert report.summary["secondary_handoff_completed_count"] == 44
    assert report.summary["secondary_handoff_latest_completed_candidate"] == "integration_review_answer_action_matrix.py"
    assert report.summary["owner_action_required"] is False
    assert report.summary["blocking_reasons"] == []
    assert report.missing_cached_paths == []
    assert report.unexpected_cached_paths == []
    assert {check.status for check in report.checks} == {"passed"}


def test_owner_post_staging_verifier_blocks_empty_index(tmp_path: Path) -> None:
    packet, staging, manifest = _write_inputs(tmp_path)

    report = build_owner_post_staging_verification(
        owner_packet_path=packet,
        staging_review_path=staging,
        manifest_path=manifest,
        cached_diff_lines=[],
    )

    assert report.status == "owner_post_staging_verification_blocked"
    assert report.cached_staged_path_count == 0
    assert report.expected_stage_path_set_digest == _path_set_digest(_stage_paths())
    assert report.cached_staged_path_set_digest is None
    assert report.summary["secondary_handoff_next_queue"] == ["integration_review_action_status_board.py"]
    assert report.summary["owner_action_required"] is True
    assert report.summary["blocking_reasons"] == [
        "cached_paths_present_after_owner_staging",
        "cached_paths_match_owner_packet",
        "cached_path_set_digest_matches_expected_paths",
    ]
    present = next(check for check in report.checks if check.name == "cached_paths_present_after_owner_staging")
    assert present.status == "failed"
    digest = next(check for check in report.checks if check.name == "cached_path_set_digest_matches_expected_paths")
    assert digest.status == "failed"


def test_owner_post_staging_verifier_blocks_missing_cached_path(tmp_path: Path) -> None:
    packet, staging, manifest = _write_inputs(tmp_path)

    report = build_owner_post_staging_verification(
        owner_packet_path=packet,
        staging_review_path=staging,
        manifest_path=manifest,
        cached_diff_lines=["backend/app/core/storage.py"],
    )

    assert report.status == "owner_post_staging_verification_blocked"
    assert report.missing_cached_paths == ["tests/test_storage.py"]
    exact = next(check for check in report.checks if check.name == "cached_paths_match_owner_packet")
    assert exact.status == "failed"
    digest = next(check for check in report.checks if check.name == "cached_path_set_digest_matches_expected_paths")
    assert digest.status == "failed"


def test_owner_post_staging_verifier_blocks_packet_stage_path_digest_drift(tmp_path: Path) -> None:
    packet, staging, manifest = _write_inputs(tmp_path)
    payload = json.loads(packet.read_text(encoding="utf-8"))
    payload["stage_path_digest"] = "0" * 64
    packet.write_text(json.dumps(payload), encoding="utf-8")

    report = build_owner_post_staging_verification(
        owner_packet_path=packet,
        staging_review_path=staging,
        manifest_path=manifest,
        cached_diff_lines=_stage_paths(),
    )

    assert report.status == "owner_post_staging_verification_blocked"
    check = next(check for check in report.checks if check.name == "packet_stage_path_digest_matches_stage_paths")
    assert check.status == "failed"


def test_owner_post_staging_verifier_blocks_packet_stage_command_digest_drift(tmp_path: Path) -> None:
    packet, staging, manifest = _write_inputs(tmp_path)
    payload = json.loads(packet.read_text(encoding="utf-8"))
    payload["stage_command_digest"] = "1" * 64
    packet.write_text(json.dumps(payload), encoding="utf-8")

    report = build_owner_post_staging_verification(
        owner_packet_path=packet,
        staging_review_path=staging,
        manifest_path=manifest,
        cached_diff_lines=_stage_paths(),
    )

    assert report.status == "owner_post_staging_verification_blocked"
    check = next(check for check in report.checks if check.name == "packet_stage_command_digest_matches_stage_commands")
    assert check.status == "failed"


def test_owner_post_staging_verifier_blocks_unexpected_cached_path(tmp_path: Path) -> None:
    packet, staging, manifest = _write_inputs(tmp_path)

    report = build_owner_post_staging_verification(
        owner_packet_path=packet,
        staging_review_path=staging,
        manifest_path=manifest,
        cached_diff_lines=_stage_paths() + ["scripts/unexpected.py"],
    )

    assert report.status == "owner_post_staging_verification_blocked"
    assert report.unexpected_cached_paths == ["scripts/unexpected.py"]
    exact = next(check for check in report.checks if check.name == "cached_paths_match_owner_packet")
    assert exact.status == "failed"


def test_owner_post_staging_verifier_blocks_protected_cached_path(tmp_path: Path) -> None:
    paths = ["backend/app/api/workbench.py"]
    packet, staging, manifest = _write_inputs(tmp_path, paths=paths)

    report = build_owner_post_staging_verification(
        owner_packet_path=packet,
        staging_review_path=staging,
        manifest_path=manifest,
        cached_diff_lines=paths,
    )

    assert report.status == "owner_post_staging_verification_blocked"
    assert report.protected_cached_paths == paths
    protected = next(check for check in report.checks if check.name == "no_protected_cached_paths")
    assert protected.status == "failed"


def test_owner_post_staging_verifier_blocks_full_codex_parity_claim(tmp_path: Path) -> None:
    packet, staging, manifest = _write_inputs(tmp_path)
    payload = _manifest()
    payload["full_codex_parity_claimed"] = True
    _write_json(manifest, payload)

    report = build_owner_post_staging_verification(
        owner_packet_path=packet,
        staging_review_path=staging,
        manifest_path=manifest,
        cached_diff_lines=_stage_paths(),
    )

    assert report.status == "owner_post_staging_verification_blocked"
    assert report.full_codex_parity_claimed is True
    parity = next(check for check in report.checks if check.name == "no_full_codex_parity_claim")
    assert parity.status == "failed"


def test_owner_post_staging_verifier_writes_json_and_markdown(tmp_path: Path) -> None:
    packet, staging, manifest = _write_inputs(tmp_path)
    report = build_owner_post_staging_verification(
        owner_packet_path=packet,
        staging_review_path=staging,
        manifest_path=manifest,
        cached_diff_lines=_stage_paths(),
    )

    json_output = tmp_path / "post-stage.json"
    md_output = tmp_path / "post-stage.md"
    write_report(report, json_output)
    write_markdown_verification(report, md_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = md_output.read_text(encoding="utf-8")
    assert payload["status"] == "owner_post_staging_verification_ready"
    assert payload["stage_path_digest"] == report.stage_path_digest
    assert payload["stage_command_digest"] == report.stage_command_digest
    assert payload["expected_stage_path_set_digest"] == report.expected_stage_path_set_digest
    assert payload["cached_staged_path_set_digest"] == report.cached_staged_path_set_digest
    assert payload["summary"]["secondary_handoff_next_queue"] == ["integration_review_action_status_board.py"]
    assert payload["summary"]["blocking_reasons"] == []
    assert payload["summary"]["owner_action_required"] is False
    assert "Commercial Delivery Owner Post-Staging Verification" in markdown
    assert "Owner action required: `false`" in markdown
    assert "Blocking reasons: ``" in markdown
    assert f"Stage path digest: `{report.stage_path_digest}`" in markdown
    assert f"Stage command digest: `{report.stage_command_digest}`" in markdown
    assert f"Expected stage path set digest: `{report.expected_stage_path_set_digest}`" in markdown
    assert f"Cached staged path set digest: `{report.cached_staged_path_set_digest}`" in markdown
    assert "backend/app/core/storage.py" in render_markdown_verification(report)
