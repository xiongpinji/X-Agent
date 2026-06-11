from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.commercial_delivery_owner_staging_rollback_plan import (
    build_owner_staging_rollback_plan,
    render_markdown_plan,
    write_markdown_plan,
    write_report,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _digest_values(values: list[str]) -> str:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _digest_path_set(values: list[str]) -> str:
    return _digest_values(sorted(set(values)))


def _write_inputs(
    tmp_path: Path,
    *,
    staged: bool = False,
    unexpected: bool = False,
    protected: bool = False,
    preflight_status: str = "owner_staging_preflight_ready",
    cached_paths_reverse_order: bool = False,
) -> dict[str, Path]:
    paths = {
        "owner_staging_packet_path": tmp_path / "owner-staging-packet.json",
        "owner_staging_preflight_path": tmp_path / "owner-staging-preflight.json",
        "owner_post_staging_verifier_path": tmp_path / "owner-post-staging-verifier.json",
        "owner_post_stage_commit_gate_path": tmp_path / "owner-post-stage-commit-gate.json",
        "owner_commit_packet_path": tmp_path / "owner-commit-packet.json",
    }
    stage_paths = ["backend/app/core/storage.py", "tests/test_storage.py"]
    cached_paths = list(reversed(stage_paths)) if staged and cached_paths_reverse_order else stage_paths if staged else []
    unexpected_paths = ["frontend/src/App.tsx"] if unexpected else []
    protected_paths = ["backend/app/main.py"] if protected else []
    _write_json(
        paths["owner_staging_packet_path"],
        {
            "status": "owner_staging_packet_ready",
            "owner_gated": True,
            "stage_paths": stage_paths,
            "stage_path_digest": _digest_values(stage_paths),
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_staging_preflight_path"],
        {
            "status": preflight_status,
            "owner_gated": True,
            "cached_staged_path_count": len(cached_paths),
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_post_staging_verifier_path"],
        {
            "status": "owner_post_staging_verification_blocked" if not staged else "owner_post_staging_verification_ready",
            "owner_gated": True,
            "cached_staged_path_count": len(cached_paths) + len(unexpected_paths) + len(protected_paths),
            "cached_staged_paths": cached_paths + unexpected_paths + protected_paths,
            "cached_staged_path_set_digest": _digest_path_set(cached_paths) if cached_paths else None,
            "unexpected_cached_paths": unexpected_paths,
            "protected_cached_paths": unexpected_paths + protected_paths,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_post_stage_commit_gate_path"],
        {
            "status": "owner_post_stage_commit_gate_blocked",
            "commit_allowed": False,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_commit_packet_path"],
        {
            "status": "owner_commit_packet_blocked",
            "commit_allowed": False,
            "full_codex_parity_claimed": False,
        },
    )
    return paths


def test_rollback_plan_ready_before_staging_with_explicit_reset_commands(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    plan = build_owner_staging_rollback_plan(**paths)

    assert plan.status == "owner_staging_rollback_plan_ready"
    assert plan.evidence_type == "commercial_delivery_owner_staging_rollback_plan"
    assert plan.owner_gated is True
    assert plan.mutation_performed is False
    assert plan.git_stage_performed is False
    assert plan.git_reset_performed is False
    assert plan.git_commit_performed is False
    assert plan.git_push_performed is False
    assert plan.network_mutation_performed is False
    assert plan.agent_execution_enabled is False
    assert plan.full_codex_parity_claimed is False
    assert plan.rollback_available is True
    assert plan.rollback_required is False
    assert plan.reset_command_count == 2
    assert plan.stage_path_digest == _digest_values(["backend/app/core/storage.py", "tests/test_storage.py"])
    assert plan.reset_path_digest == plan.stage_path_digest
    assert plan.owner_packet_stage_path_digest == plan.stage_path_digest
    assert plan.rollback_commands == [
        "git reset -- 'backend/app/core/storage.py'",
        "git reset -- 'tests/test_storage.py'",
    ]
    assert {check.status for check in plan.checks} == {"passed"}


def test_rollback_plan_marks_required_after_failed_post_stage_gate(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, staged=True)

    plan = build_owner_staging_rollback_plan(**paths)

    assert plan.status == "owner_staging_rollback_plan_ready"
    assert plan.rollback_required is True
    assert plan.rollback_available is True
    assert plan.summary["cached_staged_path_count"] == 2


def test_rollback_plan_accepts_post_staging_preflight_blocked_with_verified_cached_paths(tmp_path: Path) -> None:
    paths = _write_inputs(
        tmp_path,
        staged=True,
        preflight_status="owner_staging_preflight_blocked",
        cached_paths_reverse_order=True,
    )

    plan = build_owner_staging_rollback_plan(**paths)

    assert plan.status == "owner_staging_rollback_plan_ready"
    assert plan.reset_path_digest != plan.owner_packet_stage_path_digest
    assert plan.summary["reset_path_set_digest"] == _digest_path_set(
        ["backend/app/core/storage.py", "tests/test_storage.py"]
    )
    assert plan.summary["owner_staging_preflight_accounted_for"] is True
    assert next(check for check in plan.checks if check.name == "owner_staging_preflight_accounted_for").status == "passed"
    assert next(check for check in plan.checks if check.name == "rollback_path_digest_matches_owner_packet").status == "passed"


def test_rollback_plan_blocks_ordered_packet_digest_mismatch_after_staging(tmp_path: Path) -> None:
    paths = _write_inputs(
        tmp_path,
        staged=True,
        preflight_status="owner_staging_preflight_blocked",
        cached_paths_reverse_order=True,
    )
    packet = json.loads(paths["owner_staging_packet_path"].read_text(encoding="utf-8"))
    packet["stage_path_digest"] = _digest_values(list(reversed(packet["stage_paths"])))
    paths["owner_staging_packet_path"].write_text(json.dumps(packet), encoding="utf-8")

    plan = build_owner_staging_rollback_plan(**paths)

    assert plan.status == "owner_staging_rollback_plan_blocked"
    digest = next(check for check in plan.checks if check.name == "rollback_path_digest_matches_owner_packet")
    assert digest.status == "failed"


def test_rollback_plan_blocks_unexpected_cached_paths(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, staged=True, unexpected=True)

    plan = build_owner_staging_rollback_plan(**paths)

    assert plan.status == "owner_staging_rollback_plan_blocked"
    assert next(check for check in plan.checks if check.name == "rollback_paths_known").status == "failed"
    assert next(check for check in plan.checks if check.name == "rollback_path_digest_matches_owner_packet").status == "failed"
    assert next(check for check in plan.checks if check.name == "no_unexpected_cached_paths").status == "failed"
    assert next(check for check in plan.checks if check.name == "no_protected_cached_paths").status == "failed"


def test_rollback_plan_blocks_protected_cached_paths(tmp_path: Path) -> None:
    paths = _write_inputs(
        tmp_path,
        staged=True,
        protected=True,
        preflight_status="owner_staging_preflight_blocked",
    )

    plan = build_owner_staging_rollback_plan(**paths)

    assert plan.status == "owner_staging_rollback_plan_blocked"
    assert next(check for check in plan.checks if check.name == "rollback_paths_known").status == "failed"
    assert next(check for check in plan.checks if check.name == "no_protected_cached_paths").status == "failed"
    assert next(check for check in plan.checks if check.name == "owner_staging_preflight_accounted_for").status == "failed"


def test_rollback_plan_blocks_missing_packet(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    paths["owner_staging_packet_path"].unlink()

    plan = build_owner_staging_rollback_plan(**paths)

    assert plan.status == "owner_staging_rollback_plan_blocked"
    assert next(check for check in plan.checks if check.name == "reports_readable").status == "failed"
    assert next(check for check in plan.checks if check.name == "owner_staging_packet_ready").status == "failed"


def test_rollback_plan_writes_json_and_markdown(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    plan = build_owner_staging_rollback_plan(**paths)
    json_output = tmp_path / "rollback.json"
    md_output = tmp_path / "rollback.md"

    write_report(plan, json_output)
    write_markdown_plan(plan, md_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = md_output.read_text(encoding="utf-8")
    assert payload["status"] == "owner_staging_rollback_plan_ready"
    assert payload["stage_path_digest"] == plan.stage_path_digest
    assert payload["reset_path_digest"] == plan.reset_path_digest
    assert "Commercial Delivery Owner Staging Rollback Plan" in markdown
    assert f"Stage path digest: `{plan.stage_path_digest}`" in markdown
    assert f"Reset path digest: `{plan.reset_path_digest}`" in markdown
    assert "git reset -- 'backend/app/core/storage.py'" in render_markdown_plan(plan)


def test_rollback_plan_blocks_packet_path_digest_mismatch(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    packet = json.loads(paths["owner_staging_packet_path"].read_text(encoding="utf-8"))
    packet["stage_path_digest"] = "0" * 64
    paths["owner_staging_packet_path"].write_text(json.dumps(packet), encoding="utf-8")

    plan = build_owner_staging_rollback_plan(**paths)

    assert plan.status == "owner_staging_rollback_plan_blocked"
    digest = next(check for check in plan.checks if check.name == "rollback_path_digest_matches_owner_packet")
    assert digest.status == "failed"
