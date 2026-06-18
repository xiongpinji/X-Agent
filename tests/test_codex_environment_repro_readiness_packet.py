from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_environment_repro_readiness_packet import (
    build_codex_environment_repro_readiness_packet,
    summarize_codex_environment_repro,
)


PACKET_POLICIES = {
    "environment_policy": "environment-policy",
    "sandbox_policy": "sandbox-policy",
    "redaction_policy": "redaction-policy",
    "reproducibility_policy": "repro-policy",
    "environment_manifest_ref": "environment-manifest",
    "validation_matrix_ref": "validation-matrix",
}


def test_ready_environment_repro_has_reproducibility_evidence() -> None:
    packet = build_codex_environment_repro_readiness_packet(
        {
            **PACKET_POLICIES,
            "reproducibility": [
                {
                    "repro_id": "repro-1",
                    "status": "validated",
                    "workspace_ref": "workspace-1",
                    "runtime_profile": "python-3.11-node-22",
                    "source": "sandbox",
                    "workspace_snapshot_refs": ["workspace-snapshot"],
                    "dependency_lock_refs": ["uv-lock"],
                    "runtime_version_refs": ["python-version", "node-version"],
                    "command_transcript_refs": ["command-transcript"],
                    "sandbox_profile_refs": ["sandbox-profile"],
                    "env_var_redaction_refs": ["env-redaction"],
                    "test_command_refs": ["pytest tests/test_x.py"],
                    "failure_reproduction_refs": ["failure-repro"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_environment_repro_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["repro_count"] == 1
    assert packet["summary"]["dependency_lock_ref_count"] == 1
    assert packet["next_actions"] == ["share_environment_repro_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_environment_repro_readiness_packet(
        {
            "repros": [
                {
                    "repro_id": "repro-1",
                    "status": "validated",
                    "workspace_ref": "workspace-1",
                    "runtime_profile": "python-3.11",
                    "source": "local",
                    "workspace_snapshot_refs": ["snapshot"],
                    "dependency_lock_refs": ["lock"],
                    "runtime_version_refs": ["runtime"],
                    "command_transcript_refs": ["transcript"],
                    "sandbox_profile_refs": ["sandbox"],
                    "env_var_redaction_refs": ["redaction"],
                    "test_command_refs": ["pytest"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_environment_repro_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "environment_policy_ref",
        "sandbox_policy_ref",
        "redaction_policy_ref",
        "reproducibility_policy_ref",
        "environment_manifest_ref",
        "validation_matrix_ref",
    ]


def test_failed_environment_repro_requires_failure_reproduction_refs_and_blocks() -> None:
    packet = build_codex_environment_repro_readiness_packet(
        {
            **PACKET_POLICIES,
            "repros": [
                {
                    "repro_id": "repro-2",
                    "status": "unreproducible",
                    "workspace_ref": "workspace-2",
                    "runtime_profile": "python-3.11",
                    "source": "ci",
                    "workspace_snapshot_refs": ["snapshot"],
                    "dependency_lock_refs": ["lock"],
                    "runtime_version_refs": ["runtime"],
                    "command_transcript_refs": ["transcript"],
                    "sandbox_profile_refs": ["sandbox"],
                    "env_var_redaction_refs": ["redaction"],
                    "test_command_refs": ["pytest"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    repro = packet["reproducibility"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_environment_repro_status_failed"
    assert "failure_reproduction_refs" in repro["missing_refs"]
    assert packet["next_actions"] == [
        "resolve_environment_repro_blockers",
        "refresh_environment_repro_readiness",
    ]


def test_missing_snapshot_lock_runtime_and_redaction_refs_needs_review() -> None:
    repro = summarize_codex_environment_repro(
        {
            "repro_id": "repro-3",
            "status": "available",
            "workspace_ref": "workspace-3",
            "runtime_profile": "python-3.11",
            "source": "remote",
            "command_transcript_refs": ["transcript"],
            "sandbox_profile_refs": ["sandbox"],
            "test_command_refs": ["pytest"],
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
        }
    )

    assert repro.readiness_state == "needs_review"
    assert "workspace_snapshot_refs" in repro.missing_refs
    assert "dependency_lock_refs" in repro.missing_refs
    assert "runtime_version_refs" in repro.missing_refs
    assert "env_var_redaction_refs" in repro.missing_refs


def test_live_environment_mutation_or_command_execution_attempt_blocks_candidate() -> None:
    packet = build_codex_environment_repro_readiness_packet(
        {
            **PACKET_POLICIES,
            "repros": [
                {
                    "repro_id": "repro-4",
                    "status": "validated",
                    "workspace_ref": "workspace-4",
                    "runtime_profile": "python-3.11",
                    "source": "sandbox",
                    "workspace_snapshot_refs": ["snapshot"],
                    "dependency_lock_refs": ["lock"],
                    "runtime_version_refs": ["runtime"],
                    "command_transcript_refs": ["transcript"],
                    "sandbox_profile_refs": ["sandbox"],
                    "env_var_redaction_refs": ["redaction"],
                    "test_command_refs": ["pytest"],
                    "failure_reproduction_refs": ["failure-repro"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "command_execution_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_environment_repro_live_mutation_blocked"
    assert "live_environment_mutation_attempted" in packet["reproducibility"][0]["blockers"]


def test_empty_payload_requests_environment_repro_inventory() -> None:
    packet = build_codex_environment_repro_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_environment_repro_inventory"]


def test_dataclass_like_repro_is_accepted_by_summarizer() -> None:
    @dataclass
    class Repro:
        repro_id: str
        status: str
        workspace_ref: str
        runtime_profile: str
        source: str
        workspace_snapshot_refs: list[str]
        dependency_lock_refs: list[str]
        runtime_version_refs: list[str]
        command_transcript_refs: list[str]
        sandbox_profile_refs: list[str]
        env_var_redaction_refs: list[str]
        test_command_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]

    repro = summarize_codex_environment_repro(
        Repro(
            "repro-5",
            "passed",
            "workspace-5",
            "python-3.11",
            "custom",
            ["snapshot"],
            ["lock"],
            ["runtime"],
            ["transcript"],
            ["sandbox"],
            ["redaction"],
            ["pytest"],
            ["validation"],
            ["artifact"],
        )
    )

    assert repro.repro_id == "repro-5"
    assert repro.status == "passed"
    assert repro.readiness_state == "ready"
