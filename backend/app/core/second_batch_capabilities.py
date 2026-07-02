from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


CapabilityStatus = Literal["locally_verified", "contract_only", "reserved_owner_gated"]


@dataclass(frozen=True)
class SecondBatchCapability:
    capability_id: str
    name: str
    status: CapabilityStatus
    category: str
    surfaces: list[dict[str, str]] = field(default_factory=list)
    required_scopes: list[str] = field(default_factory=list)
    evidence_types: list[str] = field(default_factory=list)
    local_runtime_required: bool = False
    external_api_only: bool = True
    dry_run_verified: bool = True
    network_mutation_allowed: bool = False
    owner_gated_live_use: bool = True
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_second_batch_capability_manifest() -> dict[str, Any]:
    capabilities = [
        SecondBatchCapability(
            capability_id="external_llm_governance",
            name="External LLM API governance",
            status="locally_verified",
            category="llm",
            surfaces=[
                {"method": "GET", "path": "/api/v1/llm/providers"},
                {"method": "POST", "path": "/api/v1/llm/complete"},
                {"method": "GET", "path": "/api/v1/llm/stats"},
            ],
            required_scopes=["agent:run", "audit:read"],
            evidence_types=["llm_governance_api_gate"],
            notes=[
                "Local model providers are rejected.",
                "Live external calls require owner credentials and explicit provider configuration.",
            ],
        ),
        SecondBatchCapability(
            capability_id="api_only_rag",
            name="API-only RAG and knowledge retrieval",
            status="locally_verified",
            category="rag",
            surfaces=[
                {"method": "GET", "path": "/api/v1/rag/providers"},
                {"method": "POST", "path": "/api/v1/rag/query"},
            ],
            required_scopes=["memory:read"],
            evidence_types=["rag_governance_api_gate"],
            notes=[
                "Local vector stores are rejected for this batch.",
                "Protocol search uses an external HTTPS gateway boundary.",
            ],
        ),
        SecondBatchCapability(
            capability_id="provider_preflight",
            name="Provider runtime preflight",
            status="locally_verified",
            category="provider-governance",
            surfaces=[{"method": "GET", "path": "/api/v1/providers/preflight"}],
            required_scopes=["audit:read"],
            evidence_types=["provider_health_failover_gate", "provider_preflight_api_gate"],
            owner_gated_live_use=False,
            notes=[
                "Preflight is dry-run configuration inspection only.",
                "ready_to_call is not proof that a remote provider accepts requests.",
            ],
        ),
        SecondBatchCapability(
            capability_id="multi_agent_dispatch_contract",
            name="Multi-agent workflow dispatcher hardening",
            status="contract_only",
            category="multi-agent",
            required_scopes=["audit:read"],
            evidence_types=["agent_dispatch_contract_gate"],
            owner_gated_live_use=False,
            notes=[
                "This slice validates bounded handoff contracts.",
                "It does not spawn agents or execute delegated work.",
            ],
        ),
        SecondBatchCapability(
            capability_id="browser_workspace_verification",
            name="Browser/workspace verification harness",
            status="contract_only",
            category="verification",
            required_scopes=["audit:read"],
            evidence_types=["browser_workspace_verification_gate"],
            owner_gated_live_use=False,
            notes=[
                "Replay commands and local evidence paths are defined.",
                "AI-assisted exploration is not accepted as final proof.",
            ],
        ),
        SecondBatchCapability(
            capability_id="creative_video_protocol",
            name="Creative video external provider protocol",
            status="reserved_owner_gated",
            category="creative-video",
            surfaces=[
                {"method": "POST", "path": "/api/v1/creative-studio/shot-video"},
                {"method": "POST", "path": "/api/v1/creative-studio/video-workflow"},
            ],
            required_scopes=["workflow:control"],
            evidence_types=["creative_studio_external_video_api_only_gate"],
            notes=[
                "Creative Studio is not mounted in the main app in this batch.",
                "Image and video models are intentionally selected later by owner/provider configuration.",
            ],
        ),
        SecondBatchCapability(
            capability_id="second_batch_quality_gate",
            name="Second-batch unified quality gate",
            status="locally_verified",
            category="governance",
            surfaces=[{"method": "GET", "path": "/api/v1/capabilities/second-batch"}],
            required_scopes=["audit:read"],
            evidence_types=["second_batch_quality_gate", "second_batch_capability_manifest_gate"],
            owner_gated_live_use=False,
            notes=[
                "Aggregates local dry-run evidence reports.",
                "Passing this gate is not a public release claim.",
            ],
        ),
    ]
    capability_payloads = [capability.to_dict() for capability in capabilities]
    return {
        "manifest_id": "xagent-second-batch-capability-manifest",
        "status": "locally_verified_contracts",
        "full_release_claimed": False,
        "external_api_first": True,
        "local_model_runtime_supported": False,
        "network_mutation_allowed": False,
        "capabilities": capability_payloads,
        "summary": {
            "capability_count": len(capability_payloads),
            "locally_verified_count": sum(1 for item in capabilities if item.status == "locally_verified"),
            "contract_only_count": sum(1 for item in capabilities if item.status == "contract_only"),
            "owner_gated_count": sum(1 for item in capabilities if item.owner_gated_live_use),
            "mounted_api_surface_count": sum(len(item.surfaces) for item in capabilities if item.status == "locally_verified"),
        },
        "known_limits": [
            "This manifest is a runtime visibility surface for local capability contracts.",
            "It does not execute providers, spawn agents, launch browsers, or promote owner-gated live use.",
            "Evidence freshness is enforced by scripts/second_batch_quality_gate.py.",
        ],
    }
