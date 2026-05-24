from __future__ import annotations

from datetime import UTC, datetime
from threading import RLock
from uuid import uuid4

from pydantic import BaseModel, Field


class ReflectionRecord(BaseModel):
    reflection_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str = "default"
    agent_id: str = "anonymous"
    task_id: str = ""
    trace_id: str = ""
    task_summary: str = ""
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    lessons: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LearningRecord(BaseModel):
    learning_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str = "default"
    agent_id: str = "anonymous"
    domain: str = "general"
    pattern: str = ""
    outcome: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    promoted: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CapabilityVersion(BaseModel):
    capability_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str = "anonymous"
    name: str = ""
    version: str = "v1"
    description: str = ""
    promoted_from: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EvolutionStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._reflections: list[ReflectionRecord] = []
        self._learnings: list[LearningRecord] = []
        self._capabilities: list[CapabilityVersion] = []

    def add_reflection(self, record: ReflectionRecord) -> ReflectionRecord:
        with self._lock:
            self._reflections.append(record)
        return record

    def add_learning(self, record: LearningRecord) -> LearningRecord:
        with self._lock:
            self._learnings.append(record)
        return record

    def promote_capability(self, record: CapabilityVersion) -> CapabilityVersion:
        with self._lock:
            self._capabilities.append(record)
        return record

    def list_reflections(self, agent_id: str | None = None) -> list[ReflectionRecord]:
        items = self._reflections
        if agent_id is not None:
            items = [item for item in items if item.agent_id == agent_id]
        return list(reversed(items))

    def list_learnings(self, agent_id: str | None = None) -> list[LearningRecord]:
        items = self._learnings
        if agent_id is not None:
            items = [item for item in items if item.agent_id == agent_id]
        return list(reversed(items))

    def list_capabilities(self, agent_id: str | None = None) -> list[CapabilityVersion]:
        items = self._capabilities
        if agent_id is not None:
            items = [item for item in items if item.agent_id == agent_id]
        return list(reversed(items))


evolution_store = EvolutionStore()
