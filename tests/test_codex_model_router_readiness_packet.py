from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_model_router_readiness_packet import (
    build_codex_model_router_readiness_packet,
    summarize_codex_model_router,
)


PACKET_POLICIES = {
    "routing_policy": "routing-policy",
    "fallback_policy": "fallback-policy",
    "cost_policy": "cost-policy",
    "safety_policy": "safety-policy",
    "model_manifest_ref": "model-manifest",
    "provider_matrix_ref": "provider-matrix",
}


def test_ready_model_route_has_routing_policy_evidence() -> None:
    packet = build_codex_model_router_readiness_packet(
        {
            **PACKET_POLICIES,
            "routes": [
                {
                    "route_id": "route-1",
                    "status": "validated",
                    "model_ref": "gpt-5.4",
                    "provider_ref": "openai",
                    "reasoning_profile": "high",
                    "model_capability_refs": ["capabilities"],
                    "provider_health_refs": ["provider-health"],
                    "reasoning_profile_refs": ["reasoning-profile"],
                    "fallback_policy_refs": ["fallback"],
                    "context_window_refs": ["context-window"],
                    "tool_call_compatibility_refs": ["tool-calls"],
                    "rate_limit_quota_refs": ["quota"],
                    "cost_policy_refs": ["cost"],
                    "safety_policy_refs": ["safety"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_model_router_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["route_count"] == 1
    assert packet["summary"]["tool_call_compatibility_ref_count"] == 1
    assert packet["next_actions"] == ["share_model_router_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_model_router_readiness_packet(
        {
            "routes": [
                {
                    "route_id": "route-1",
                    "status": "validated",
                    "model_ref": "model",
                    "provider_ref": "provider",
                    "reasoning_profile": "medium",
                    "model_capability_refs": ["capabilities"],
                    "provider_health_refs": ["health"],
                    "reasoning_profile_refs": ["reasoning"],
                    "fallback_policy_refs": ["fallback"],
                    "context_window_refs": ["context"],
                    "tool_call_compatibility_refs": ["tool"],
                    "rate_limit_quota_refs": ["quota"],
                    "cost_policy_refs": ["cost"],
                    "safety_policy_refs": ["safety"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_model_router_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "routing_policy_ref",
        "fallback_policy_ref",
        "cost_policy_ref",
        "safety_policy_ref",
        "model_manifest_ref",
        "provider_matrix_ref",
    ]


def test_failed_or_quota_exceeded_route_blocks() -> None:
    packet = build_codex_model_router_readiness_packet(
        {
            **PACKET_POLICIES,
            "routes": [
                {
                    "route_id": "route-2",
                    "status": "quota-exceeded",
                    "model_ref": "model",
                    "provider_ref": "provider",
                    "reasoning_profile": "low",
                    "model_capability_refs": ["capabilities"],
                    "provider_health_refs": ["health"],
                    "reasoning_profile_refs": ["reasoning"],
                    "fallback_policy_refs": ["fallback"],
                    "context_window_refs": ["context"],
                    "tool_call_compatibility_refs": ["tool"],
                    "rate_limit_quota_refs": ["quota"],
                    "cost_policy_refs": ["cost"],
                    "safety_policy_refs": ["safety"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_model_router_status_failed"
    assert "model_route_status_failed" in packet["routes"][0]["blockers"]
    assert packet["next_actions"] == ["resolve_model_router_blockers", "refresh_model_router_readiness"]


def test_missing_reasoning_fallback_context_and_tool_refs_needs_review() -> None:
    route = summarize_codex_model_router(
        {
            "route_id": "route-3",
            "status": "available",
            "model_ref": "model",
            "provider_ref": "provider",
            "reasoning_profile": "unknown",
            "model_capability_refs": ["capabilities"],
            "provider_health_refs": ["health"],
            "rate_limit_quota_refs": ["quota"],
            "cost_policy_refs": ["cost"],
            "safety_policy_refs": ["safety"],
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
        }
    )

    assert route.readiness_state == "needs_review"
    assert "reasoning_profile" in route.missing_refs
    assert "reasoning_profile_refs" in route.missing_refs
    assert "fallback_policy_refs" in route.missing_refs
    assert "context_window_refs" in route.missing_refs
    assert "tool_call_compatibility_refs" in route.missing_refs


def test_live_model_call_or_router_mutation_attempt_blocks_candidate() -> None:
    packet = build_codex_model_router_readiness_packet(
        {
            **PACKET_POLICIES,
            "routes": [
                {
                    "route_id": "route-4",
                    "status": "validated",
                    "model_ref": "model",
                    "provider_ref": "provider",
                    "reasoning_profile": "adaptive",
                    "model_capability_refs": ["capabilities"],
                    "provider_health_refs": ["health"],
                    "reasoning_profile_refs": ["reasoning"],
                    "fallback_policy_refs": ["fallback"],
                    "context_window_refs": ["context"],
                    "tool_call_compatibility_refs": ["tool"],
                    "rate_limit_quota_refs": ["quota"],
                    "cost_policy_refs": ["cost"],
                    "safety_policy_refs": ["safety"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "provider_api_call_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_model_router_live_call_blocked"
    assert "live_model_call_or_router_mutation_attempted" in packet["routes"][0]["blockers"]


def test_empty_payload_requests_model_router_inventory() -> None:
    packet = build_codex_model_router_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_model_router_inventory"]


def test_dataclass_like_route_is_accepted_by_summarizer() -> None:
    @dataclass
    class Route:
        route_id: str
        status: str
        model_ref: str
        provider_ref: str
        reasoning_profile: str
        model_capability_refs: list[str]
        provider_health_refs: list[str]
        reasoning_profile_refs: list[str]
        fallback_policy_refs: list[str]
        context_window_refs: list[str]
        tool_call_compatibility_refs: list[str]
        rate_limit_quota_refs: list[str]
        cost_policy_refs: list[str]
        safety_policy_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]

    route = summarize_codex_model_router(
        Route(
            "route-5",
            "selected",
            "model",
            "provider",
            "xhigh",
            ["capabilities"],
            ["health"],
            ["reasoning"],
            ["fallback"],
            ["context"],
            ["tool"],
            ["quota"],
            ["cost"],
            ["safety"],
            ["validation"],
            ["artifact"],
        )
    )

    assert route.route_id == "route-5"
    assert route.reasoning_profile == "xhigh"
    assert route.readiness_state == "ready"
