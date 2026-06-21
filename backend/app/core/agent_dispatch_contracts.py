from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


DispatchPattern = Literal["sequential", "parallel", "router", "orchestrator", "evaluator"]


@dataclass(frozen=True)
class AgentHandoffContract:
    task_id: str
    target_agent: str
    objective: str
    input_refs: list[str] = field(default_factory=list)
    output_schema_ref: str = "json"
    timeout_seconds: int = 600
    max_cost_usd: float = 1.0
    max_retries: int = 1
    required_artifacts: list[str] = field(default_factory=list)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.task_id.strip():
            errors.append("task_id is required")
        if not self.target_agent.strip():
            errors.append("target_agent is required")
        if not self.objective.strip():
            errors.append("objective is required")
        if self.timeout_seconds <= 0:
            errors.append("timeout_seconds must be positive")
        if self.max_cost_usd < 0:
            errors.append("max_cost_usd must be non-negative")
        if self.max_retries < 0:
            errors.append("max_retries must be non-negative")
        if not self.required_artifacts:
            errors.append("required_artifacts must not be empty")
        return errors


@dataclass(frozen=True)
class AgentWorkflowDispatchContract:
    workflow_id: str
    pattern: DispatchPattern
    handoffs: list[AgentHandoffContract]
    fan_in_required: bool = True
    max_parallel_agents: int = 3
    total_cost_budget_usd: float = 3.0
    trace_required: bool = True
    audit_required: bool = True

    def validate(self) -> dict[str, Any]:
        errors: list[str] = []
        if not self.workflow_id.strip():
            errors.append("workflow_id is required")
        if not self.handoffs:
            errors.append("handoffs must not be empty")
        if self.max_parallel_agents <= 0:
            errors.append("max_parallel_agents must be positive")
        if self.total_cost_budget_usd < 0:
            errors.append("total_cost_budget_usd must be non-negative")
        if self.pattern == "parallel" and self.max_parallel_agents < 2:
            errors.append("parallel workflows require max_parallel_agents >= 2")
        if self.fan_in_required is not True:
            errors.append("fan_in_required must be true")
        if self.trace_required is not True:
            errors.append("trace_required must be true")
        if self.audit_required is not True:
            errors.append("audit_required must be true")

        seen: set[str] = set()
        for index, handoff in enumerate(self.handoffs):
            if handoff.task_id in seen:
                errors.append(f"duplicate handoff task_id: {handoff.task_id}")
            seen.add(handoff.task_id)
            errors.extend(f"handoffs[{index}].{error}" for error in handoff.validate())

        estimated_cost = sum(handoff.max_cost_usd for handoff in self.handoffs)
        if estimated_cost > self.total_cost_budget_usd:
            errors.append("handoff cost budgets exceed total_cost_budget_usd")

        return {
            "valid": not errors,
            "errors": errors,
            "handoff_count": len(self.handoffs),
            "estimated_cost_usd": round(estimated_cost, 8),
            "max_parallel_agents": self.max_parallel_agents,
            "fan_in_required": self.fan_in_required,
            "trace_required": self.trace_required,
            "audit_required": self.audit_required,
        }


def build_default_second_batch_dispatch_contract() -> AgentWorkflowDispatchContract:
    return AgentWorkflowDispatchContract(
        workflow_id="second-batch-upgrade-dispatch",
        pattern="parallel",
        max_parallel_agents=3,
        total_cost_budget_usd=3.0,
        handoffs=[
            AgentHandoffContract(
                task_id="b2-rag-review",
                target_agent="reviewer",
                objective="Review API-only RAG governance for auth, tenant isolation, and budget guards.",
                input_refs=["backend/app/api/rag_governance.py", "tests/test_rag_governance_api.py"],
                required_artifacts=["review_report", "verification_commands"],
            ),
            AgentHandoffContract(
                task_id="b2-provider-health-review",
                target_agent="provider-health",
                objective="Verify provider readiness reports are redacted and API-only.",
                input_refs=["scripts/provider_health_failover_gate.py"],
                required_artifacts=["provider_matrix", "redaction_evidence"],
            ),
        ],
    )
