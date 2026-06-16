from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.app.core.contracts import RiskLevel, RunContext

# This file is unchanged - circuit_breaker.py is a new file


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    ABORTED = "aborted"


class ApprovalSubjectType(StrEnum):
    COMMAND = "command"
    FILE_CHANGE = "file_change"
    NETWORK_REQUEST = "network_request"
    MCP_ELICITATION = "mcp_elicitation"
    BROWSER_ACTION = "browser_action"
    CHANNEL_SEND = "channel_send"
    ISSUE_TO_PR_EXECUTE = "issue_to_pr_execute"
    TOOL = "tool"
    WORKFLOW = "workflow"


class ApprovalDecisionType(StrEnum):
    APPROVE_ONCE = "approve_once"
    APPROVE_FOR_RUN = "approve_for_run"
    APPROVE_FOR_SESSION = "approve_for_session"
    DENY = "deny"
    ABORT = "abort"


APPROVAL_SUBJECT_ACTIONS: dict[ApprovalSubjectType, str] = {
    ApprovalSubjectType.COMMAND: "command.execute",
    ApprovalSubjectType.FILE_CHANGE: "file_change.apply",
    ApprovalSubjectType.NETWORK_REQUEST: "network.request",
    ApprovalSubjectType.MCP_ELICITATION: "mcp.elicitation.respond",
    ApprovalSubjectType.BROWSER_ACTION: "browser.action.execute",
    ApprovalSubjectType.CHANNEL_SEND: "channel.send",
    ApprovalSubjectType.ISSUE_TO_PR_EXECUTE: "issue_to_pr.execute",
    ApprovalSubjectType.TOOL: "tool.execute",
    ApprovalSubjectType.WORKFLOW: "workflow.execute",
}

APPROVAL_SUBJECT_RESOURCE_TYPES: dict[ApprovalSubjectType, str] = {
    ApprovalSubjectType.COMMAND: "command",
    ApprovalSubjectType.FILE_CHANGE: "file_change",
    ApprovalSubjectType.NETWORK_REQUEST: "network_request",
    ApprovalSubjectType.MCP_ELICITATION: "mcp_elicitation",
    ApprovalSubjectType.BROWSER_ACTION: "browser_action",
    ApprovalSubjectType.CHANNEL_SEND: "channel_send",
    ApprovalSubjectType.ISSUE_TO_PR_EXECUTE: "issue_to_pr_execute",
    ApprovalSubjectType.TOOL: "tool",
    ApprovalSubjectType.WORKFLOW: "workflow",
}


def infer_approval_subject_type(resource_type: str, action: str) -> ApprovalSubjectType:
    """Infer the normalized approval subject from legacy resource/action fields."""
    for subject_type, subject_action in APPROVAL_SUBJECT_ACTIONS.items():
        if action == subject_action or resource_type == APPROVAL_SUBJECT_RESOURCE_TYPES[subject_type]:
            return subject_type
    if action.startswith("workflow."):
        return ApprovalSubjectType.WORKFLOW
    return ApprovalSubjectType.TOOL


class ApprovalRequestRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    actor_id: str
    trace_id: str
    resource_type: str = "tool"
    resource_id: str
    action: str
    risk_level: RiskLevel
    status: ApprovalStatus = ApprovalStatus.PENDING
    reason: str
    arguments_preview: dict[str, Any] = Field(default_factory=dict)
    arguments: dict[str, Any] = Field(default_factory=dict)
    decided_by: str | None = None
    decided_at: datetime | None = None
    decision_reason: str | None = None
    executed_by: str | None = None
    executed_at: datetime | None = None
    execution_trace_id: str | None = None
    linked_policy_trace_id: str | None = None
    subject_type: ApprovalSubjectType | None = None
    decision_type: ApprovalDecisionType | None = None
    decision_scope: str = "once"
    expires_at: datetime | None = None
    sandbox_profile: str = "locked"
    owner_gate_required: bool = True
    audit_required: bool = True
    policy_snapshot: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def model_post_init(self, __context: Any) -> None:
        if self.subject_type is None:
            self.subject_type = infer_approval_subject_type(self.resource_type, self.action)


class ApprovalDecisionRequest(BaseModel):
    decided_by: str = "anonymous"
    reason: str = ""
    decision_type: ApprovalDecisionType = ApprovalDecisionType.APPROVE_ONCE


class ApprovalSubjectRequest(BaseModel):
    subject_type: ApprovalSubjectType
    resource_id: str
    risk_level: RiskLevel
    reason: str
    arguments_preview: dict[str, Any] = Field(default_factory=dict)
    arguments: dict[str, Any] = Field(default_factory=dict)
    action: str | None = None
    sandbox_profile: str = "locked"
    owner_gate_required: bool = True
    audit_required: bool = True
    policy_snapshot: dict[str, Any] = Field(default_factory=dict)


class ApprovalStore:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._records: dict[str, ApprovalRequestRecord] = {}
        self._lock = RLock()
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path:
            self._load_from_disk()

    def create_tool_approval(
        self,
        *,
        context: RunContext,
        tool_name: str,
        risk_level: RiskLevel,
        reason: str,
        arguments_preview: dict[str, Any],
        arguments: dict[str, Any] | None = None,
    ) -> ApprovalRequestRecord:
        return self.create_approval(
            context=context,
            resource_type="tool",
            resource_id=tool_name,
            action="tool.execute",
            risk_level=risk_level,
            reason=reason,
            arguments_preview=arguments_preview,
            arguments=arguments,
            subject_type=ApprovalSubjectType.TOOL,
        )

    def create_subject_approval(
        self,
        *,
        context: RunContext,
        subject: ApprovalSubjectRequest,
    ) -> ApprovalRequestRecord:
        resource_type = APPROVAL_SUBJECT_RESOURCE_TYPES[subject.subject_type]
        action = subject.action or APPROVAL_SUBJECT_ACTIONS[subject.subject_type]
        return self.create_approval(
            context=context,
            resource_type=resource_type,
            resource_id=subject.resource_id,
            action=action,
            risk_level=subject.risk_level,
            reason=subject.reason,
            arguments_preview=subject.arguments_preview,
            arguments=subject.arguments,
            subject_type=subject.subject_type,
            sandbox_profile=subject.sandbox_profile,
            owner_gate_required=subject.owner_gate_required,
            audit_required=subject.audit_required,
            policy_snapshot=subject.policy_snapshot,
        )

    def create_approval(
        self,
        *,
        context: RunContext,
        resource_type: str,
        resource_id: str,
        action: str,
        risk_level: RiskLevel,
        reason: str,
        arguments_preview: dict[str, Any] | None = None,
        arguments: dict[str, Any] | None = None,
        subject_type: ApprovalSubjectType | None = None,
        sandbox_profile: str = "locked",
        owner_gate_required: bool = True,
        audit_required: bool = True,
        policy_snapshot: dict[str, Any] | None = None,
    ) -> ApprovalRequestRecord:
        normalized_subject = subject_type or infer_approval_subject_type(resource_type, action)
        record = ApprovalRequestRecord(
            tenant_id=context.tenant_id,
            actor_id=context.user_id,
            trace_id=context.trace_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            risk_level=risk_level,
            reason=reason,
            arguments_preview=arguments_preview or {},
            arguments=arguments or {},
            linked_policy_trace_id=context.trace_id,
            subject_type=normalized_subject,
            sandbox_profile=sandbox_profile,
            owner_gate_required=owner_gate_required,
            audit_required=audit_required,
            policy_snapshot=policy_snapshot or {},
        )
        with self._lock:
            self._records[record.id] = record
            self._persist()
        return record

    def list(
        self,
        *,
        limit: int = 50,
        status: ApprovalStatus | None = None,
        tenant_id: str | None = None,
    ) -> list[ApprovalRequestRecord]:
        records = [
            record
            for record in self._records.values()
            if (status is None or record.status == status)
            and (tenant_id is None or record.tenant_id == tenant_id)
        ]
        records.sort(key=lambda record: record.created_at, reverse=True)
        return records[:limit]

    def get(self, approval_id: str) -> ApprovalRequestRecord | None:
        return self._records.get(approval_id)

    def approve(
        self,
        approval_id: str,
        decision: ApprovalDecisionRequest,
    ) -> ApprovalRequestRecord | None:
        if decision.decision_type not in {
            ApprovalDecisionType.APPROVE_ONCE,
            ApprovalDecisionType.APPROVE_FOR_RUN,
            ApprovalDecisionType.APPROVE_FOR_SESSION,
        }:
            return None
        return self._decide(approval_id, ApprovalStatus.APPROVED, decision)

    def reject(
        self,
        approval_id: str,
        decision: ApprovalDecisionRequest,
    ) -> ApprovalRequestRecord | None:
        decision = decision.model_copy(update={"decision_type": ApprovalDecisionType.DENY})
        return self._decide(approval_id, ApprovalStatus.REJECTED, decision)

    def abort(
        self,
        approval_id: str,
        decision: ApprovalDecisionRequest,
    ) -> ApprovalRequestRecord | None:
        decision = decision.model_copy(update={"decision_type": ApprovalDecisionType.ABORT})
        return self._decide(approval_id, ApprovalStatus.ABORTED, decision)

    def mark_executed(
        self,
        approval_id: str,
        *,
        executed_by: str,
        execution_trace_id: str,
        linked_policy_trace_id: str | None = None,
    ) -> ApprovalRequestRecord | None:
        with self._lock:
            record = self._records.get(approval_id)
            if record is None:
                return None
            updated = record.model_copy(
                update={
                    "status": ApprovalStatus.EXECUTED,
                    "executed_by": executed_by,
                    "executed_at": datetime.now(UTC),
                    "execution_trace_id": execution_trace_id,
                    "linked_policy_trace_id": linked_policy_trace_id or record.linked_policy_trace_id,
                }
            )
            self._records[approval_id] = updated
            self._persist()
            return updated

    def count(self) -> int:
        return len(self._records)

    def pending_count(self) -> int:
        return sum(
            1 for record in self._records.values() if record.status == ApprovalStatus.PENDING
        )

    def _decide(
        self,
        approval_id: str,
        status: ApprovalStatus,
        decision: ApprovalDecisionRequest,
    ) -> ApprovalRequestRecord | None:
        with self._lock:
            record = self._records.get(approval_id)
            if record is None:
                return None
            updated = record.model_copy(
                update={
                    "status": status,
                    "decided_by": decision.decided_by,
                    "decided_at": datetime.now(UTC),
                    "decision_reason": decision.reason,
                    "decision_type": decision.decision_type,
                    "decision_scope": self._decision_scope(decision.decision_type),
                }
            )
            self._records[approval_id] = updated
            self._persist()
            return updated

    def _load_from_disk(self) -> None:
        if self._storage_path is None or not self._storage_path.exists():
            return
        with self._storage_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        for item in payload:
            record = ApprovalRequestRecord.model_validate(item)
            self._records[record.id] = record

    def _persist(self) -> None:
        if self._storage_path is None:
            return
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [record.model_dump(mode="json") for record in self.list(limit=10_000)]
        self._storage_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _decision_scope(decision_type: ApprovalDecisionType) -> str:
        if decision_type == ApprovalDecisionType.APPROVE_FOR_RUN:
            return "run"
        if decision_type == ApprovalDecisionType.APPROVE_FOR_SESSION:
            return "session"
        if decision_type == ApprovalDecisionType.ABORT:
            return "abort"
        if decision_type == ApprovalDecisionType.DENY:
            return "deny"
        return "once"
