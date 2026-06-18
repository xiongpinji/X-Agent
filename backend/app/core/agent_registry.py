from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.app.core.storage import atomic_write_json, load_json_array


class AgentRole(StrEnum):
    MAIN = "main"
    SUB = "sub"


class AgentStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class OrganizationUnit(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., min_length=1, max_length=120)
    title: str = Field(default="", max_length=240)
    parent_id: str | None = None
    agent_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrganizationUnitCreate(BaseModel):
    id: str | None = None
    name: str = Field(..., min_length=1, max_length=120)
    title: str = Field(default="", max_length=240)
    parent_id: str | None = None
    agent_name: str | None = Field(default=None, max_length=120)
    instructions: str = Field(default="", max_length=4_000)
    model_provider: str | None = None
    model_name: str | None = None
    create_subagent: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class SubAgentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=1_000)
    instructions: str = Field(default="", max_length=4_000)
    organization_unit_id: str | None = None
    model_provider: str | None = None
    model_name: str | None = None
    tool_scopes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=1_000)
    instructions: str = Field(default="", max_length=8_000)
    role: AgentRole = AgentRole.MAIN
    parent_agent_id: str | None = None
    organization_name: str = Field(default="", max_length=120)
    organization_units: list[OrganizationUnitCreate] = Field(default_factory=list)
    subagents: list[SubAgentCreateRequest] = Field(default_factory=list)
    auto_spawn_subagents: bool = True
    max_dynamic_subagents: int = Field(default=3, ge=0, le=20)
    model_provider: str | None = None
    model_name: str | None = None
    tool_scopes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1_000)
    instructions: str | None = Field(default=None, max_length=8_000)
    status: AgentStatus | None = None
    organization_name: str | None = Field(default=None, max_length=120)
    auto_spawn_subagents: bool | None = None
    max_dynamic_subagents: int | None = Field(default=None, ge=0, le=20)
    model_provider: str | None = None
    model_name: str | None = None
    tool_scopes: list[str] | None = None
    metadata: dict[str, Any] | None = None


class AgentParentUpdateRequest(BaseModel):
    parent_agent_id: str | None = None
    organization_unit_id: str | None = None


class AgentDefinition(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str = "default"
    user_id: str = "anonymous"
    name: str
    description: str = ""
    instructions: str = ""
    role: AgentRole = AgentRole.MAIN
    status: AgentStatus = AgentStatus.ACTIVE
    parent_agent_id: str | None = None
    organization_name: str = ""
    organization_unit_id: str | None = None
    organization_units: list[OrganizationUnit] = Field(default_factory=list)
    auto_spawn_subagents: bool = True
    max_dynamic_subagents: int = 3
    model_provider: str | None = None
    model_name: str | None = None
    tool_scopes: list[str] = Field(default_factory=list)
    subagent_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentTreeResponse(BaseModel):
    agent: AgentDefinition
    subagents: list[AgentDefinition] = Field(default_factory=list)
    organization_units: list[OrganizationUnit] = Field(default_factory=list)
    hierarchy: dict[str, Any] = Field(default_factory=dict)
    organization_tree: list[dict[str, Any]] = Field(default_factory=list)
    snapshot: dict[str, Any] = Field(default_factory=dict)


class AgentRegistrySummary(BaseModel):
    count: int = 0
    main: int = 0
    sub: int = 0
    active: int = 0
    paused: int = 0
    archived: int = 0
    dynamic_subagents: int = 0


class AgentRegistryStore:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._records: dict[str, AgentDefinition] = {}
        self._lock = RLock()
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path:
            self._load_from_disk()

    def list(
        self,
        *,
        role: AgentRole | None = None,
        parent_agent_id: str | None = None,
        tenant_id: str | None = None,
    ) -> list[AgentDefinition]:
        records = list(self._snapshot().values())
        if role is not None:
            records = [record for record in records if record.role == role]
        if parent_agent_id is not None:
            records = [record for record in records if record.parent_agent_id == parent_agent_id]
        if tenant_id is not None:
            records = [record for record in records if record.tenant_id == tenant_id]
        return self._sorted(records)

    def get(self, agent_id: str) -> AgentDefinition | None:
        return self._snapshot().get(agent_id)

    def create_tree(
        self,
        request: AgentCreateRequest,
        *,
        tenant_id: str = "default",
        user_id: str = "anonymous",
    ) -> AgentTreeResponse:
        with self._lock:
            if request.role == AgentRole.SUB and not request.parent_agent_id:
                raise ValueError("Sub agent requires parent_agent_id.")
            if request.parent_agent_id and request.parent_agent_id not in self._records:
                raise ValueError("Parent agent not found.")

            now = datetime.now(UTC)
            units = [
                OrganizationUnit(
                    id=unit.id or str(uuid4()),
                    name=unit.name,
                    title=unit.title,
                    parent_id=unit.parent_id,
                    metadata=unit.metadata,
                )
                for unit in request.organization_units
            ]
            agent = AgentDefinition(
                tenant_id=tenant_id,
                user_id=user_id,
                name=request.name,
                description=request.description,
                instructions=request.instructions,
                role=request.role,
                parent_agent_id=request.parent_agent_id,
                organization_name=request.organization_name,
                organization_units=units if request.role == AgentRole.MAIN else [],
                auto_spawn_subagents=request.auto_spawn_subagents,
                max_dynamic_subagents=request.max_dynamic_subagents,
                model_provider=request.model_provider,
                model_name=request.model_name,
                tool_scopes=list(request.tool_scopes),
                metadata=dict(request.metadata),
                created_at=now,
                updated_at=now,
            )
            self._records[agent.id] = agent
            subagents: list[AgentDefinition] = []

            if agent.role == AgentRole.MAIN:
                for unit, source in zip(units, request.organization_units, strict=False):
                    if not source.create_subagent:
                        continue
                    child = self._create_subagent_unlocked(
                        self._records[agent.id],
                        SubAgentCreateRequest(
                            name=source.agent_name or source.title or source.name,
                            description=source.title,
                            instructions=source.instructions,
                            organization_unit_id=unit.id,
                            model_provider=source.model_provider or request.model_provider,
                            model_name=source.model_name or request.model_name,
                            metadata={"organization_unit": unit.name, **source.metadata},
                        ),
                        tenant_id=tenant_id,
                        user_id=user_id,
                    )
                    unit.agent_id = child.id
                    subagents.append(child)

                for sub_request in request.subagents:
                    subagents.append(
                        self._create_subagent_unlocked(
                            self._records[agent.id],
                            sub_request,
                            tenant_id=tenant_id,
                            user_id=user_id,
                        )
                    )

                current_agent = self._records[agent.id]
                agent = current_agent.model_copy(
                    update={"organization_units": units, "updated_at": datetime.now(UTC)}
                )
                self._records[agent.id] = agent
            elif request.parent_agent_id:
                parent = self._records[request.parent_agent_id]
                self._records[parent.id] = self._append_subagent(parent, agent.id)

            self._persist()
            return self.tree(agent.id)

    def update(self, agent_id: str, request: AgentUpdateRequest) -> AgentDefinition | None:
        with self._lock:
            record = self._records.get(agent_id)
            if record is None:
                return None
            update = request.model_dump(exclude_unset=True)
            update["updated_at"] = datetime.now(UTC)
            updated = record.model_copy(update=update)
            self._records[agent_id] = updated
            self._persist()
            return updated

    def create_subagent(
        self,
        parent_agent_id: str,
        request: SubAgentCreateRequest,
        *,
        tenant_id: str = "default",
        user_id: str = "anonymous",
    ) -> AgentDefinition | None:
        with self._lock:
            parent = self._records.get(parent_agent_id)
            if parent is None:
                return None
            child = self._create_subagent_unlocked(
                parent,
                request,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            self._persist()
            return child

    def ensure_dynamic_subagents(
        self,
        parent_agent_id: str,
        *,
        task: str,
        route: str = "general",
        tenant_id: str = "default",
        user_id: str = "anonymous",
    ) -> list[AgentDefinition]:
        with self._lock:
            parent = self._records.get(parent_agent_id)
            if parent is None:
                return []
            children = [
                self._records[child_id]
                for child_id in parent.subagent_ids
                if child_id in self._records
            ]
            if not parent.auto_spawn_subagents or parent.max_dynamic_subagents <= 0:
                return self._sorted(children)
            dynamic_children = [
                child
                for child in children
                if child.metadata.get("dynamic_subagent") is True
                and child.status == AgentStatus.ACTIVE
            ]
            target = min(parent.max_dynamic_subagents, 3)
            missing = max(0, target - len(dynamic_children))
            if missing == 0:
                return self._sorted(children)

            profiles = [
                ("任务规划子代理", "拆解任务、判断路径、安排工具与协作顺序。"),
                ("执行子代理", "根据主智能体计划调用工具、检索记忆和执行工作流。"),
                ("质检子代理", "复核输出、检查风险、整理可交付结果。"),
            ]
            existing_names = {child.name for child in children}
            for name, instructions in profiles:
                if missing <= 0:
                    break
                if name in existing_names:
                    continue
                children.append(
                    self._create_subagent_unlocked(
                        parent,
                        SubAgentCreateRequest(
                            name=name,
                            description=f"Dynamic subagent for {route} tasks.",
                            instructions=instructions,
                            model_provider=parent.model_provider,
                            model_name=parent.model_name,
                            metadata={
                                "dynamic_subagent": True,
                                "route": route,
                                "task_preview": task[:240],
                            },
                        ),
                        tenant_id=tenant_id,
                        user_id=user_id,
                    )
                )
                missing -= 1
            self._persist()
            return self._sorted(children)

    def tree(self, agent_id: str) -> AgentTreeResponse:
        snapshot = self._snapshot()
        agent = snapshot.get(agent_id)
        if agent is None:
            raise KeyError(agent_id)
        subagents = self._descendants(agent.id, snapshot)
        return AgentTreeResponse(
            agent=agent,
            subagents=self._sorted(subagents),
            organization_units=list(agent.organization_units),
            hierarchy=self._hierarchy_for(agent.id, snapshot),
            organization_tree=self._organization_tree(agent.organization_units),
            snapshot={
                "agent_id": agent.id,
                "role": agent.role,
                "subagents": len(subagents),
                "organization_units": len(agent.organization_units),
                "auto_spawn_subagents": agent.auto_spawn_subagents,
            },
        )

    def move(
        self,
        agent_id: str,
        request: AgentParentUpdateRequest,
    ) -> AgentDefinition | None:
        with self._lock:
            record = self._records.get(agent_id)
            if record is None:
                return None
            if request.parent_agent_id == agent_id:
                raise ValueError("Agent cannot report to itself.")
            if request.parent_agent_id is not None:
                new_parent = self._records.get(request.parent_agent_id)
                if new_parent is None:
                    raise ValueError("Parent agent not found.")
                descendant_ids = {child.id for child in self._descendants(record.id, self._records)}
                if request.parent_agent_id in descendant_ids:
                    raise ValueError("Agent hierarchy cannot contain cycles.")
            if record.parent_agent_id and record.parent_agent_id in self._records:
                old_parent = self._records[record.parent_agent_id]
                self._records[old_parent.id] = old_parent.model_copy(
                    update={
                        "subagent_ids": [
                            child_id
                            for child_id in old_parent.subagent_ids
                            if child_id != agent_id
                        ],
                        "updated_at": datetime.now(UTC),
                    }
                )
            updated = record.model_copy(
                update={
                    "parent_agent_id": request.parent_agent_id,
                    "organization_unit_id": request.organization_unit_id,
                    "updated_at": datetime.now(UTC),
                }
            )
            self._records[agent_id] = updated
            if request.parent_agent_id:
                parent = self._records[request.parent_agent_id]
                self._records[parent.id] = self._append_subagent(parent, agent_id)
            self._persist()
            return self._records[agent_id]

    def delete(self, agent_id: str) -> bool:
        with self._lock:
            record = self._records.get(agent_id)
            if record is None:
                return False
            ids_to_delete = {agent_id, *[child.id for child in self._descendants(agent_id, self._records)]}
            for delete_id in ids_to_delete:
                self._records.pop(delete_id, None)
            if record.parent_agent_id and record.parent_agent_id in self._records:
                parent = self._records[record.parent_agent_id]
                self._records[parent.id] = parent.model_copy(
                    update={
                        "subagent_ids": [
                            child_id
                            for child_id in parent.subagent_ids
                            if child_id not in ids_to_delete
                        ],
                        "updated_at": datetime.now(UTC),
                    }
                )
            self._persist()
            return True

    def summary(self) -> AgentRegistrySummary:
        records = list(self._snapshot().values())
        return AgentRegistrySummary(
            count=len(records),
            main=sum(1 for record in records if record.role == AgentRole.MAIN),
            sub=sum(1 for record in records if record.role == AgentRole.SUB),
            active=sum(1 for record in records if record.status == AgentStatus.ACTIVE),
            paused=sum(1 for record in records if record.status == AgentStatus.PAUSED),
            archived=sum(1 for record in records if record.status == AgentStatus.ARCHIVED),
            dynamic_subagents=sum(
                1 for record in records if record.metadata.get("dynamic_subagent") is True
            ),
        )

    def runtime_context(
        self,
        agent: AgentDefinition,
        subagents: list[AgentDefinition],
    ) -> dict[str, Any]:
        return {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "instructions": agent.instructions,
            "role": agent.role.value,
            "organization_name": agent.organization_name,
            "organization_units": [
                unit.model_dump(mode="json") for unit in agent.organization_units
            ],
            "subagents": [
                {
                    "id": child.id,
                    "name": child.name,
                    "description": child.description,
                    "instructions": child.instructions,
                    "organization_unit_id": child.organization_unit_id,
                    "model_provider": child.model_provider,
                    "model_name": child.model_name,
                }
                for child in subagents
            ],
            "hierarchy": self._hierarchy_for(agent.id, self._snapshot()),
            "auto_spawn_subagents": agent.auto_spawn_subagents,
            "max_dynamic_subagents": agent.max_dynamic_subagents,
            "model_provider": agent.model_provider,
            "model_name": agent.model_name,
        }

    def _create_subagent_unlocked(
        self,
        parent: AgentDefinition,
        request: SubAgentCreateRequest,
        *,
        tenant_id: str,
        user_id: str,
    ) -> AgentDefinition:
        now = datetime.now(UTC)
        child = AgentDefinition(
            tenant_id=tenant_id,
            user_id=user_id,
            name=request.name,
            description=request.description,
            instructions=request.instructions,
            role=AgentRole.SUB,
            parent_agent_id=parent.id,
            organization_name=parent.organization_name,
            organization_unit_id=request.organization_unit_id,
            auto_spawn_subagents=False,
            max_dynamic_subagents=0,
            model_provider=request.model_provider,
            model_name=request.model_name,
            tool_scopes=list(request.tool_scopes),
            metadata=dict(request.metadata),
            created_at=now,
            updated_at=now,
        )
        self._records[child.id] = child
        self._records[parent.id] = self._append_subagent(parent, child.id)
        return child

    def _descendants(
        self,
        agent_id: str,
        snapshot: dict[str, AgentDefinition],
    ) -> list[AgentDefinition]:
        descendants: list[AgentDefinition] = []
        agent = snapshot.get(agent_id)
        if agent is None:
            return descendants
        for child_id in agent.subagent_ids:
            child = snapshot.get(child_id)
            if child is None:
                continue
            descendants.append(child)
            descendants.extend(self._descendants(child.id, snapshot))
        return descendants

    def _hierarchy_for(
        self,
        agent_id: str,
        snapshot: dict[str, AgentDefinition],
    ) -> dict[str, Any]:
        agent = snapshot.get(agent_id)
        if agent is None:
            return {}
        return {
            "id": agent.id,
            "name": agent.name,
            "role": agent.role.value,
            "status": agent.status.value,
            "parent_agent_id": agent.parent_agent_id,
            "organization_unit_id": agent.organization_unit_id,
            "model_provider": agent.model_provider,
            "model_name": agent.model_name,
            "children": [
                self._hierarchy_for(child_id, snapshot)
                for child_id in agent.subagent_ids
                if child_id in snapshot
            ],
        }

    @staticmethod
    def _organization_tree(units: list[OrganizationUnit]) -> list[dict[str, Any]]:
        by_parent: dict[str | None, list[OrganizationUnit]] = {}
        for unit in units:
            by_parent.setdefault(unit.parent_id, []).append(unit)

        def build(parent_id: str | None) -> list[dict[str, Any]]:
            nodes = []
            for unit in sorted(by_parent.get(parent_id, []), key=lambda item: item.name):
                nodes.append({**unit.model_dump(mode="json"), "children": build(unit.id)})
            return nodes

        return build(None)

    @staticmethod
    def _append_subagent(parent: AgentDefinition, child_id: str) -> AgentDefinition:
        ids = list(parent.subagent_ids)
        if child_id not in ids:
            ids.append(child_id)
        return parent.model_copy(update={"subagent_ids": ids, "updated_at": datetime.now(UTC)})

    def _load_from_disk(self) -> None:
        if self._storage_path is None:
            return
        for record in load_json_array(self._storage_path, AgentDefinition):
            self._records[record.id] = record

    def _persist(self) -> None:
        if self._storage_path is None:
            return
        payload = [record.model_dump(mode="json") for record in self._sorted(self._records.values())]
        atomic_write_json(self._storage_path, payload)

    def _snapshot(self) -> dict[str, AgentDefinition]:
        with self._lock:
            return dict(self._records)

    @staticmethod
    def _sorted(records: list[AgentDefinition] | Any) -> list[AgentDefinition]:
        items = list(records)
        items.sort(key=lambda item: (item.role.value, item.created_at.isoformat(), item.id))
        return items
