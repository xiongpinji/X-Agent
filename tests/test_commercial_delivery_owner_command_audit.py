from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.commercial_delivery_owner_command_audit import (
    build_owner_command_audit,
    render_markdown_audit,
    write_markdown_audit,
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


def _write_inputs(tmp_path: Path, *, commands: list[str] | None = None) -> dict[str, Path]:
    owner_packet = tmp_path / "owner-packet.json"
    staging_review = tmp_path / "staging-review.json"
    manifest = tmp_path / "manifest.json"
    stage_paths = _stage_paths()
    stage_commands = commands if commands is not None else [f"git add -- '{path}'" for path in stage_paths]
    _write_json(
        owner_packet,
        {
            "status": "owner_staging_packet_ready",
            "owner_gated": True,
            "stage_paths": stage_paths,
            "stage_path_digest": _digest_values(stage_paths),
            "stage_commands": stage_commands,
            "stage_command_digest": _digest_values(stage_commands),
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        staging_review,
        {
            "status": "staging_review_ready",
            "owner_gated": True,
            "paths": [{"path": path, "status": "eligible"} for path in stage_paths],
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        manifest,
        {
            "status": "original_kernel_delivery_manifest_ready",
            "stage_include_paths": stage_paths,
            "full_codex_parity_claimed": False,
        },
    )
    return {
        "owner_packet_path": owner_packet,
        "staging_review_path": staging_review,
        "manifest_path": manifest,
    }


def test_owner_command_audit_ready_for_exact_commands(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    report = build_owner_command_audit(**paths)

    assert report.status == "owner_command_audit_ready"
    assert report.evidence_type == "commercial_delivery_owner_command_audit"
    assert report.owner_gated is True
    assert report.mutation_performed is False
    assert report.git_stage_performed is False
    assert report.git_commit_performed is False
    assert report.git_push_performed is False
    assert report.network_mutation_performed is False
    assert report.agent_execution_enabled is False
    assert report.command_count == 2
    assert report.expected_path_count == 2
    assert report.command_paths == _stage_paths()
    assert report.command_path_digest == _digest_values(_stage_paths())
    assert report.expected_path_digest == _digest_values(_stage_paths())
    assert report.owner_packet_stage_path_digest == _digest_values(_stage_paths())
    assert report.command_digest == _digest_values([f"git add -- '{path}'" for path in _stage_paths()])
    assert report.owner_packet_stage_command_digest == report.command_digest
    assert {check.status for check in report.checks} == {"passed"}


def test_owner_command_audit_blocks_broad_command(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, commands=["git add ."])

    report = build_owner_command_audit(**paths)

    assert report.status == "owner_command_audit_blocked"
    assert report.broad_commands == ["git add ."]
    broad = next(check for check in report.checks if check.name == "no_broad_stage_commands")
    strict = next(check for check in report.checks if check.name == "commands_are_strict_git_add_path_commands")
    assert broad.status == "failed"
    assert strict.status == "failed"


def test_owner_command_audit_blocks_missing_and_unexpected_paths(tmp_path: Path) -> None:
    paths = _write_inputs(
        tmp_path,
        commands=[
            "git add -- 'backend/app/core/storage.py'",
            "git add -- 'scripts/unexpected.py'",
        ],
    )

    report = build_owner_command_audit(**paths)

    assert report.status == "owner_command_audit_blocked"
    assert report.missing_command_paths == ["tests/test_storage.py"]
    assert report.unexpected_command_paths == ["scripts/unexpected.py"]
    exact = next(check for check in report.checks if check.name == "command_paths_match_expected_paths")
    assert exact.status == "failed"


def test_owner_command_audit_blocks_duplicate_paths(tmp_path: Path) -> None:
    paths = _write_inputs(
        tmp_path,
        commands=[
            "git add -- 'backend/app/core/storage.py'",
            "git add -- 'backend/app/core/storage.py'",
            "git add -- 'tests/test_storage.py'",
        ],
    )

    report = build_owner_command_audit(**paths)

    assert report.status == "owner_command_audit_blocked"
    assert report.duplicate_command_paths == ["backend/app/core/storage.py"]
    duplicate = next(check for check in report.checks if check.name == "no_duplicate_command_paths")
    assert duplicate.status == "failed"


def test_owner_command_audit_blocks_protected_paths(tmp_path: Path) -> None:
    paths = _write_inputs(
        tmp_path,
        commands=[
            "git add -- 'backend/app/core/storage.py'",
            "git add -- 'backend/app/api/workbench.py'",
        ],
    )
    packet = json.loads(paths["owner_packet_path"].read_text(encoding="utf-8"))
    packet["stage_paths"] = ["backend/app/core/storage.py", "backend/app/api/workbench.py"]
    packet["stage_path_digest"] = _digest_values(packet["stage_paths"])
    paths["owner_packet_path"].write_text(json.dumps(packet), encoding="utf-8")

    report = build_owner_command_audit(**paths)

    assert report.status == "owner_command_audit_blocked"
    assert report.protected_command_paths == ["backend/app/api/workbench.py"]
    protected = next(check for check in report.checks if check.name == "no_protected_command_paths")
    assert protected.status == "failed"


def test_owner_command_audit_writes_json_and_markdown(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    report = build_owner_command_audit(**paths)
    json_output = tmp_path / "audit.json"
    md_output = tmp_path / "audit.md"

    write_report(report, json_output)
    write_markdown_audit(report, md_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = md_output.read_text(encoding="utf-8")
    assert payload["status"] == "owner_command_audit_ready"
    assert payload["command_path_digest"] == report.command_path_digest
    assert payload["owner_packet_stage_command_digest"] == report.owner_packet_stage_command_digest
    assert "Commercial Delivery Owner Command Audit" in markdown
    assert f"Command path digest: `{report.command_path_digest}`" in markdown
    assert f"Command digest: `{report.command_digest}`" in markdown
    assert "backend/app/core/storage.py" in render_markdown_audit(report)


def test_owner_command_audit_blocks_digest_mismatch(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    packet = json.loads(paths["owner_packet_path"].read_text(encoding="utf-8"))
    packet["stage_command_digest"] = "0" * 64
    paths["owner_packet_path"].write_text(json.dumps(packet), encoding="utf-8")

    report = build_owner_command_audit(**paths)

    assert report.status == "owner_command_audit_blocked"
    digest = next(check for check in report.checks if check.name == "stage_command_digest_matches_owner_packet")
    assert digest.status == "failed"
