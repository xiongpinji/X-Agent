from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_terminal_command_readiness_packet import (
    build_codex_terminal_command_readiness_packet,
    summarize_codex_terminal_command,
)


PACKET_POLICIES = {
    "command_policy": "command-policy",
    "permission_policy": "permission-policy",
    "sandbox_policy": "sandbox-policy",
    "redaction_policy": "redaction-policy",
    "command_manifest_ref": "command-manifest",
    "execution_governance_ref": "execution-governance",
}


def test_ready_terminal_command_has_governance_evidence() -> None:
    packet = build_codex_terminal_command_readiness_packet(
        {
            **PACKET_POLICIES,
            "commands": [
                {
                    "command_id": "command-1",
                    "status": "validated",
                    "command_ref": "pytest tests/test_x.py",
                    "working_directory_ref": "workspace-root",
                    "permission_refs": ["permission"],
                    "sandbox_refs": ["sandbox"],
                    "timeout_refs": ["timeout"],
                    "stdout_transcript_refs": ["stdout"],
                    "stderr_transcript_refs": ["stderr"],
                    "exit_code_refs": ["exit-code"],
                    "redaction_refs": ["redaction"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_terminal_command_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["command_count"] == 1
    assert packet["summary"]["exit_code_ref_count"] == 1
    assert packet["next_actions"] == ["share_terminal_command_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_terminal_command_readiness_packet(
        {
            "commands": [
                {
                    "command_id": "command-1",
                    "status": "validated",
                    "command_ref": "pytest",
                    "working_directory_ref": "workspace",
                    "permission_refs": ["permission"],
                    "sandbox_refs": ["sandbox"],
                    "timeout_refs": ["timeout"],
                    "stdout_transcript_refs": ["stdout"],
                    "exit_code_refs": ["exit-code"],
                    "redaction_refs": ["redaction"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_terminal_command_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "command_policy_ref",
        "permission_policy_ref",
        "sandbox_policy_ref",
        "redaction_policy_ref",
        "command_manifest_ref",
        "execution_governance_ref",
    ]


def test_failed_command_requires_stderr_transcript_and_blocks() -> None:
    packet = build_codex_terminal_command_readiness_packet(
        {
            **PACKET_POLICIES,
            "commands": [
                {
                    "command_id": "command-2",
                    "status": "timed-out",
                    "command_ref": "pytest",
                    "working_directory_ref": "workspace",
                    "permission_refs": ["permission"],
                    "sandbox_refs": ["sandbox"],
                    "timeout_refs": ["timeout"],
                    "stdout_transcript_refs": ["stdout"],
                    "exit_code_refs": ["exit-code"],
                    "redaction_refs": ["redaction"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    command = packet["commands"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_terminal_command_status_failed"
    assert "stderr_transcript_refs" in command["missing_refs"]
    assert packet["next_actions"] == [
        "resolve_terminal_command_blockers",
        "refresh_terminal_command_readiness",
    ]


def test_missing_permission_sandbox_timeout_output_and_redaction_refs_needs_review() -> None:
    command = summarize_codex_terminal_command(
        {
            "command_id": "command-3",
            "status": "recorded",
            "command_ref": "pytest",
            "working_directory_ref": "workspace",
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
        }
    )

    assert command.readiness_state == "needs_review"
    assert "permission_refs" in command.missing_refs
    assert "sandbox_refs" in command.missing_refs
    assert "timeout_refs" in command.missing_refs
    assert "stdout_transcript_refs" in command.missing_refs
    assert "exit_code_refs" in command.missing_refs
    assert "redaction_refs" in command.missing_refs


def test_live_command_execution_or_process_spawn_attempt_blocks_candidate() -> None:
    packet = build_codex_terminal_command_readiness_packet(
        {
            **PACKET_POLICIES,
            "commands": [
                {
                    "command_id": "command-4",
                    "status": "validated",
                    "command_ref": "pytest",
                    "working_directory_ref": "workspace",
                    "permission_refs": ["permission"],
                    "sandbox_refs": ["sandbox"],
                    "timeout_refs": ["timeout"],
                    "stdout_transcript_refs": ["stdout"],
                    "stderr_transcript_refs": ["stderr"],
                    "exit_code_refs": ["exit-code"],
                    "redaction_refs": ["redaction"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "process_spawn_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_terminal_command_live_execution_blocked"
    assert "live_command_execution_attempted" in packet["commands"][0]["blockers"]


def test_empty_payload_requests_terminal_command_inventory() -> None:
    packet = build_codex_terminal_command_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_terminal_command_inventory"]


def test_dataclass_like_command_is_accepted_by_summarizer() -> None:
    @dataclass
    class Command:
        command_id: str
        status: str
        command_ref: str
        working_directory_ref: str
        permission_refs: list[str]
        sandbox_refs: list[str]
        timeout_refs: list[str]
        stdout_transcript_refs: list[str]
        stderr_transcript_refs: list[str]
        exit_code_refs: list[str]
        redaction_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]

    command = summarize_codex_terminal_command(
        Command(
            "command-5",
            "passed",
            "pytest",
            "workspace",
            ["permission"],
            ["sandbox"],
            ["timeout"],
            ["stdout"],
            ["stderr"],
            ["exit-code"],
            ["redaction"],
            ["validation"],
            ["artifact"],
        )
    )

    assert command.command_id == "command-5"
    assert command.status == "passed"
    assert command.readiness_state == "ready"
