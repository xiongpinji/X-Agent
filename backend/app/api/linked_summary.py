from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LinkedSummarySection(BaseModel):
    count: int = 0
    items: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)


class LinkedSummaries(BaseModel):
    primary: LinkedSummarySection = Field(default_factory=LinkedSummarySection)
    trace: LinkedSummarySection = Field(default_factory=LinkedSummarySection)
    run: LinkedSummarySection = Field(default_factory=LinkedSummarySection)
    workflow: LinkedSummarySection = Field(default_factory=LinkedSummarySection)
    audit: LinkedSummarySection = Field(default_factory=LinkedSummarySection)
    approvals: LinkedSummarySection = Field(default_factory=LinkedSummarySection)
    memory: LinkedSummarySection = Field(default_factory=LinkedSummarySection)
    tools: LinkedSummarySection = Field(default_factory=LinkedSummarySection)


class LinkedSummaryEnvelope(BaseModel):
    resource_type: str
    resource_id: str
    linked_summaries: LinkedSummaries = Field(default_factory=LinkedSummaries)
    snapshot: dict[str, Any] = Field(default_factory=dict)


def build_linked_summary_section(
    *,
    count: int = 0,
    items: list[dict[str, Any]] | None = None,
    summary: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
) -> LinkedSummarySection:
    return LinkedSummarySection(
        count=count,
        items=items or [],
        summary=summary or {},
        data=data or {},
    )


def build_linked_summary(
    *,
    resource_type: str,
    resource_id: str,
    primary: dict[str, object],
    trace: dict[str, object] | None = None,
    run: dict[str, object] | None = None,
    workflow: dict[str, object] | None = None,
    audit: dict[str, object] | None = None,
    approvals: dict[str, object] | None = None,
    memory: dict[str, object] | None = None,
    tools: dict[str, object] | None = None,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    linked_summaries = LinkedSummaries(
        primary=build_linked_summary_section(data=primary),
        trace=build_linked_summary_section(data=trace),
        run=build_linked_summary_section(data=run),
        workflow=build_linked_summary_section(data=workflow),
        audit=build_linked_summary_section(data=audit),
        approvals=build_linked_summary_section(data=approvals),
        memory=build_linked_summary_section(data=memory),
        tools=build_linked_summary_section(data=tools),
    )
    payload = LinkedSummaryEnvelope(
        resource_type=resource_type,
        resource_id=resource_id,
        linked_summaries=linked_summaries,
        snapshot={
            "resource_type": resource_type,
            "resource_id": resource_id,
            "linked_summaries": linked_summaries.model_dump(mode="json"),
        },
    )
    if extra:
        payload.snapshot.update(extra)
    return payload.model_dump(mode="json")
