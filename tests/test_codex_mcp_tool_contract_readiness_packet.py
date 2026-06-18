from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_mcp_tool_contract_readiness_packet import (
    build_codex_mcp_tool_contract_readiness_packet,
    summarize_codex_mcp_tool_contract,
)


PACKET_POLICIES = {
    "tool_contract_policy": "tool-contract-policy",
    "mcp_server_policy": "mcp-server-policy",
    "permission_policy": "permission-policy",
    "schema_policy": "schema-policy",
    "tool_manifest_ref": "tool-manifest",
    "tool_contract_matrix_ref": "tool-contract-matrix",
}


def test_ready_mcp_tool_contract_has_contract_evidence() -> None:
    packet = build_codex_mcp_tool_contract_readiness_packet(
        {
            **PACKET_POLICIES,
            "tools": [
                {
                    "tool_id": "tool-1",
                    "status": "validated",
                    "tool_ref": "mcp.tool.search",
                    "mcp_server_ref": "server-ref",
                    "tool_schema_refs": ["tool-schema"],
                    "tool_permission_refs": ["permission"],
                    "argument_schema_refs": ["argument-schema"],
                    "result_schema_refs": ["result-schema"],
                    "failure_taxonomy_refs": ["failure-taxonomy"],
                    "discovery_refs": ["discovery"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_mcp_tool_contract_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["tool_count"] == 1
    assert packet["summary"]["argument_schema_ref_count"] == 1
    assert packet["next_actions"] == ["share_mcp_tool_contract_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_mcp_tool_contract_readiness_packet(
        {
            "tools": [
                {
                    "tool_id": "tool-1",
                    "status": "validated",
                    "tool_ref": "mcp.tool.search",
                    "mcp_server_ref": "server-ref",
                    "tool_schema_refs": ["tool-schema"],
                    "tool_permission_refs": ["permission"],
                    "argument_schema_refs": ["argument-schema"],
                    "result_schema_refs": ["result-schema"],
                    "discovery_refs": ["discovery"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_mcp_tool_contract_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "tool_contract_policy_ref",
        "mcp_server_policy_ref",
        "permission_policy_ref",
        "schema_policy_ref",
        "tool_manifest_ref",
        "tool_contract_matrix_ref",
    ]


def test_failed_or_disabled_tool_requires_failure_taxonomy_and_blocks() -> None:
    packet = build_codex_mcp_tool_contract_readiness_packet(
        {
            **PACKET_POLICIES,
            "tools": [
                {
                    "tool_id": "tool-2",
                    "status": "disabled",
                    "tool_ref": "mcp.tool.write",
                    "mcp_server_ref": "server-ref",
                    "tool_schema_refs": ["tool-schema"],
                    "tool_permission_refs": ["permission"],
                    "argument_schema_refs": ["argument-schema"],
                    "result_schema_refs": ["result-schema"],
                    "discovery_refs": ["discovery"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    tool = packet["tools"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_mcp_tool_contract_status_failed"
    assert "failure_taxonomy_refs" in tool["missing_refs"]
    assert packet["next_actions"] == [
        "resolve_mcp_tool_contract_blockers",
        "refresh_mcp_tool_contract_readiness",
    ]


def test_missing_schema_permission_discovery_and_validation_refs_needs_review() -> None:
    tool = summarize_codex_mcp_tool_contract(
        {
            "tool_id": "tool-3",
            "status": "recorded",
            "tool_ref": "mcp.tool.search",
            "mcp_server_ref": "server-ref",
            "artifact_refs": ["artifact"],
        }
    )

    assert tool.readiness_state == "needs_review"
    assert "tool_schema_refs" in tool.missing_refs
    assert "tool_permission_refs" in tool.missing_refs
    assert "argument_schema_refs" in tool.missing_refs
    assert "result_schema_refs" in tool.missing_refs
    assert "discovery_refs" in tool.missing_refs
    assert "validation_receipt_refs" in tool.missing_refs


def test_live_mcp_call_or_tool_registration_attempt_blocks_candidate() -> None:
    packet = build_codex_mcp_tool_contract_readiness_packet(
        {
            **PACKET_POLICIES,
            "tools": [
                {
                    "tool_id": "tool-4",
                    "status": "validated",
                    "tool_ref": "mcp.tool.write",
                    "mcp_server_ref": "server-ref",
                    "tool_schema_refs": ["tool-schema"],
                    "tool_permission_refs": ["permission"],
                    "argument_schema_refs": ["argument-schema"],
                    "result_schema_refs": ["result-schema"],
                    "failure_taxonomy_refs": ["failure-taxonomy"],
                    "discovery_refs": ["discovery"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "tool_registration_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_mcp_tool_contract_live_mutation_blocked"
    assert "live_mcp_tool_mutation_attempted" in packet["tools"][0]["blockers"]


def test_empty_payload_requests_mcp_tool_contract_inventory() -> None:
    packet = build_codex_mcp_tool_contract_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_mcp_tool_contract_inventory"]


def test_dataclass_like_tool_contract_is_accepted_by_summarizer() -> None:
    @dataclass
    class ToolContract:
        tool_id: str
        status: str
        tool_ref: str
        mcp_server_ref: str
        tool_schema_refs: list[str]
        tool_permission_refs: list[str]
        argument_schema_refs: list[str]
        result_schema_refs: list[str]
        failure_taxonomy_refs: list[str]
        discovery_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]

    tool = summarize_codex_mcp_tool_contract(
        ToolContract(
            "tool-5",
            "passed",
            "mcp.tool.search",
            "server-ref",
            ["tool-schema"],
            ["permission"],
            ["argument-schema"],
            ["result-schema"],
            ["failure-taxonomy"],
            ["discovery"],
            ["validation"],
            ["artifact"],
        )
    )

    assert tool.tool_id == "tool-5"
    assert tool.status == "passed"
    assert tool.readiness_state == "ready"
