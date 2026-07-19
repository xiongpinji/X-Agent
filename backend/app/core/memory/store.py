from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from inspect import isawaitable
from pathlib import Path
from threading import RLock
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.app.core.contracts import RunContext
from backend.app.core.embeddings import DeterministicEmbeddingModel, EmbeddingModel
from backend.app.core.memory_dedup_adapter import (
    WritePathDeduper,
    canonical_from_store_item,
    dedup_memory_from_canonical,
)
from backend.app.core.memory_graph import MemoryGraph

logger = logging.getLogger(__name__)


class MemoryScope(BaseModel):
    owner_agent_id: str | None = None
    share_scope: str = "private"
    visibility: str = "private"
    shared_with: list[str] = Field(default_factory=list)
    project_id: str | None = None
    room_id: str | None = None
    task_id: str | None = None


class MemoryRevision(BaseModel):
    revision_id: str = Field(default_factory=lambda: str(uuid4()))
    memory_id: str
    actor_agent_id: str | None = None
    summary: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MemoryItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    agent_id: str | None = None
    session_id: str | None = None
    scope: MemoryScope = Field(default_factory=MemoryScope)
    content: str
    layer: int = Field(ge=1, le=10)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    embedding: list[float] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    revisions: list[MemoryRevision] = Field(default_factory=list)


class SessionRecord(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    user_id: str
    agent_id: str | None = None
    title: str = ""
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_memory_id: str | None = None
    shared: bool = False
    room_id: str | None = None
    project_id: str | None = None


class MemorySearchHit(BaseModel):
    item: MemoryItem
    score: float
    keyword_score: float = 0.0
    graph_score: float = 0.0
    vector_score: float = 0.0
    importance_score: float = 0.0
    freshness_score: float = 0.0


class MemoryConsolidationResult(BaseModel):
    source_count: int
    target_memory_id: str | None = None
    summary: str = ""
    tags: list[str] = Field(default_factory=list)


class MemoryUpdateResult(BaseModel):
    memory_id: str
    revision_id: str | None = None
    content: str = ""


class MemoryRollbackResult(BaseModel):
    memory_id: str
    revision_id: str | None = None
    content: str = ""


class MemoryPollutionReport(BaseModel):
    memory_id: str
    risk_level: str
    reasons: list[str] = Field(default_factory=list)
    blocked: bool = False


class MemoryExportBundle(BaseModel):
    memories: list[MemoryItem] = Field(default_factory=list)
    sessions: list[SessionRecord] = Field(default_factory=list)


class MemorySystem:
    """L1-L10 memory implementation for desktop-first X-Agent.

    Memory is isolated by default per tenant, agent, and session. Sharing must be explicit
    through scopes such as room or project. Higher layers capture durable memory and
    identity-level synthesis.

    Write-path deduplication: ``store()``/``store_layer()`` merge duplicate writes
    (exact normalized-content hash, then vector similarity >= threshold via the
    repo's ``MemoryDeduplicatorEnhanced`` engine) into the kept item instead of
    appending. Enabled by default; disable via ``enable_dedup=False`` or
    ``XAGENT_MEMORY_DEDUP=off``. The synchronous ``add()`` is a raw append
    primitive and intentionally does not dedup.
    """

    _LAYER_PROFILES: dict[int, dict[str, str]] = {
        1: {"name": "instant_context", "role": "perception", "scope": "current_turn", "lifetime": "seconds", "access": "private"},
        2: {"name": "session_working", "role": "working", "scope": "active_session", "lifetime": "minutes", "access": "session"},
        3: {"name": "task_memory", "role": "episodic", "scope": "current_task", "lifetime": "task", "access": "task"},
        4: {"name": "collaboration_memory", "role": "collaboration", "scope": "handoff_chain", "lifetime": "collaboration", "access": "team"},
        5: {"name": "tool_memory", "role": "procedural", "scope": "toolchain", "lifetime": "tool_session", "access": "tool"},
        6: {"name": "behavior_memory", "role": "meta", "scope": "behavioral_patterns", "lifetime": "long_session", "access": "agent"},
        7: {"name": "project_memory", "role": "session", "scope": "project", "lifetime": "project", "access": "project"},
        8: {"name": "organization_memory", "role": "reflection", "scope": "organization", "lifetime": "organization", "access": "org"},
        9: {"name": "platform_memory", "role": "strategy", "scope": "platform", "lifetime": "platform", "access": "platform"},
        10: {"name": "long_term_evolution", "role": "identity", "scope": "long_term", "lifetime": "persistent", "access": "persistent"},
    }

    def add(self, content: str, summary: str | None = None, *, tenant_id: str | None = None) -> str:
        """Raw synchronous append primitive (NOT deduplicated by design).

        Use the async store()/store_layer() path for deduplicated writes.
        """
        if tenant_id is None:
            raise ValueError("tenant_id is required for memory isolation.")
        with self._lock:
            item = MemoryItem(
                tenant_id=tenant_id,
                agent_id=None,
                content=content,
                layer=3,
                importance=0.5,
                tags=[],
                metadata={"summary": summary or content},
                embedding=[],
            )
            self._items.append(item)
            self._graph.add_text(content)
            self._append_to_disk(item)
            return item.id

    def __init__(
        self,
        storage_path: str | Path | None = None,
        embedding_model: EmbeddingModel | None = None,
        enable_dedup: bool | None = None,
        dedup_vector_threshold: float | None = None,
        dedup_candidate_limit: int = 2000,
    ) -> None:
        self._items: list[MemoryItem] = []
        self._sessions: dict[str, SessionRecord] = {}
        self._lock = RLock()
        self._storage_path = Path(storage_path) if storage_path else None
        self._embedding_model = embedding_model or DeterministicEmbeddingModel()
        self._graph = MemoryGraph()
        # Write-path deduplication (P1-13): ON by default, env-overridable via
        # XAGENT_MEMORY_DEDUP=off and XAGENT_MEMORY_DEDUP_THRESHOLD=0.95.
        # Only the async store()/store_layer() path dedups; the synchronous
        # add() helper intentionally does NOT (kept as a raw append primitive).
        if enable_dedup is None:
            enable_dedup = os.getenv("XAGENT_MEMORY_DEDUP", "on").strip().lower() not in {
                "off",
                "0",
                "false",
                "no",
            }
        if dedup_vector_threshold is None:
            try:
                dedup_vector_threshold = float(os.getenv("XAGENT_MEMORY_DEDUP_THRESHOLD", "0.95"))
            except ValueError:
                dedup_vector_threshold = 0.95
        self._dedup = (
            WritePathDeduper(vector_threshold=dedup_vector_threshold) if enable_dedup else None
        )
        self._dedup_candidate_limit = max(int(dedup_candidate_limit), 1)
        if self._storage_path:
            self._load_from_disk()

    async def store(
        self,
        context: RunContext,
        content: str,
        layer: int = 3,
        importance: float = 0.5,
        tags: list[str] | None = None,
        metadata: dict | None = None,
        session_id: str | None = None,
        scope: MemoryScope | None = None,
    ) -> str:
        return await self.store_layer(
            context,
            layer=layer,
            content=content,
            importance=importance,
            tags=tags,
            metadata=metadata,
            session_id=session_id,
            scope=scope,
        )

    async def store_layer(
        self,
        context: RunContext,
        layer: int,
        content: str,
        importance: float = 0.5,
        tags: list[str] | None = None,
        metadata: dict | None = None,
        session_id: str | None = None,
        scope: MemoryScope | None = None,
    ) -> str:
        layer = self._normalize_layer(layer)
        tags = self._normalize_tags(tags)
        metadata = self._normalize_metadata(metadata)
        scope = self._normalize_scope(scope, context, session_id, metadata)
        layer_profile = self.layer_profile(layer)
        metadata.setdefault("layer", layer)
        metadata.setdefault("memory_role", layer_profile["role"])
        metadata.setdefault("memory_layer_name", layer_profile["name"])
        metadata.setdefault("memory_layer_scope", layer_profile["scope"])
        metadata.setdefault("memory_layer_lifetime", layer_profile["lifetime"])
        metadata.setdefault("memory_layer_access", layer_profile["access"])
        metadata.setdefault("tenant_id", context.tenant_id)
        metadata.setdefault("user_id", context.user_id)
        metadata.setdefault("agent_id", context.agent_id)
        metadata.setdefault("request_id", context.request_id)
        metadata.setdefault("session_id", session_id)
        metadata.setdefault("share_scope", scope.share_scope)
        metadata.setdefault("visibility", scope.visibility)
        metadata.setdefault("owner_agent_id", scope.owner_agent_id or context.agent_id)
        metadata.setdefault("room_id", scope.room_id)
        metadata.setdefault("project_id", scope.project_id)
        metadata.setdefault("task_id", scope.task_id)
        metadata.setdefault("shared_with", scope.shared_with)
        item = MemoryItem(
            tenant_id=context.tenant_id,
            agent_id=context.agent_id,
            session_id=session_id,
            scope=scope,
            content=content,
            layer=layer,
            importance=importance,
            tags=tags,
            metadata=metadata,
            embedding=await self._embed(content),
        )
        duplicate_id = await self._find_write_duplicate(item)
        with self._lock:
            if duplicate_id is not None:
                existing = self.get_item(duplicate_id)
                if existing is not None:
                    self._merge_duplicate(existing, item)
                    if session_id:
                        self._attach_to_session(context, session_id, existing)
                    self._append_to_disk(existing)
                    return existing.id
            self._items.append(item)
            self._graph.add_text(item.content)
            if session_id:
                self._attach_to_session(context, session_id, item)
            self._append_to_disk(item)
        return item.id

    def start_session(
        self,
        context: RunContext,
        title: str = "",
        tags: list[str] | None = None,
        metadata: dict | None = None,
        shared: bool = False,
        room_id: str | None = None,
        project_id: str | None = None,
    ) -> SessionRecord:
        session = SessionRecord(
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            agent_id=context.agent_id,
            title=title,
            tags=self._normalize_tags(tags),
            metadata=self._normalize_metadata(metadata),
            shared=shared,
            room_id=room_id,
            project_id=project_id,
        )
        with self._lock:
            self._sessions[session.session_id] = session
            self._append_to_disk(session)
        return session

    def get_session(self, session_id: str) -> SessionRecord | None:
        return self._sessions.get(session_id)

    def list_sessions(self, tenant_id: str | None = None, limit: int = 50) -> list[SessionRecord]:
        sessions = list(self._sessions.values())
        if tenant_id is not None:
            sessions = [session for session in sessions if session.tenant_id == tenant_id]
        sessions.sort(key=lambda session: session.updated_at, reverse=True)
        return sessions[:limit]

    def append_session_summary(self, session_id: str, summary: str) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return
        session.summary = self._merge_session_summary(session.summary, summary)
        session.updated_at = datetime.now(UTC)
        self._append_to_disk(session)

    def session_snapshot(self, session_id: str) -> dict[str, object] | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        return {
            "session_id": session.session_id,
            "tenant_id": session.tenant_id,
            "user_id": session.user_id,
            "agent_id": session.agent_id,
            "title": session.title,
            "summary": session.summary,
            "tags": session.tags,
            "metadata": session.metadata,
            "last_memory_id": session.last_memory_id,
            "shared": session.shared,
            "room_id": session.room_id,
            "project_id": session.project_id,
        }

    def add_revision(
        self,
        memory_id: str,
        actor_agent_id: str | None = None,
        summary: str = "",
    ) -> MemoryRevision | None:
        item = self.get_item(memory_id)
        if item is None:
            return None
        revision = MemoryRevision(memory_id=memory_id, actor_agent_id=actor_agent_id, summary=summary)
        item.revisions.append(revision)
        if summary:
            item.content = self._merge_session_summary(item.content, summary)
        item.metadata["revision_count"] = len(item.revisions)
        item.metadata["last_revision_id"] = revision.revision_id
        self._append_to_disk(item)
        return revision

    def detect_pollution(self, memory_id: str) -> MemoryPollutionReport | None:
        item = self.get_item(memory_id)
        if item is None:
            return None
        return self._pollution_for_item(item)

    def list_revisions(self, memory_id: str) -> list[MemoryRevision]:
        item = self.get_item(memory_id)
        if item is None:
            return []
        return list(item.revisions)

    def rollback_memory(self, memory_id: str, revision_id: str | None = None) -> MemoryRollbackResult | None:
        item = self.get_item(memory_id)
        if item is None:
            return None
        if not item.revisions:
            return MemoryRollbackResult(memory_id=memory_id, content=item.content)
        target_revision = None
        if revision_id is None:
            target_revision = item.revisions[-1]
        else:
            for revision in reversed(item.revisions):
                if revision.revision_id == revision_id:
                    target_revision = revision
                    break
        if target_revision is None:
            return None
        item.content = self._merge_session_summary(item.content, target_revision.summary)
        item.metadata["rolled_back_to"] = target_revision.revision_id
        item.metadata["rollback_at"] = datetime.now(UTC).isoformat()
        self._append_to_disk(item)
        return MemoryRollbackResult(memory_id=memory_id, revision_id=target_revision.revision_id, content=item.content)

    def route_shared_memory(self, memory_id: str) -> MemoryItem | None:
        item = self.get_item(memory_id)
        if item is None:
            return None
        report = self._pollution_for_item(item)
        if report.blocked:
            self.unshare_memory(memory_id)
            item.metadata["shared_route"] = "blocked"
            item.metadata["pollution_report"] = report.model_dump(mode="json")
            self._append_to_disk(item)
            return item
        if report.risk_level == "medium" and item.scope.share_scope == "team":
            item.scope.share_scope = "project"
            item.scope.visibility = "shared"
            item.metadata["shared_route"] = "downgraded_to_project"
        else:
            item.metadata["shared_route"] = "accepted"
        item.metadata["pollution_report"] = report.model_dump(mode="json")
        self._append_to_disk(item)
        return item

    def _pollution_for_item(self, item: MemoryItem) -> MemoryPollutionReport:
        reasons: list[str] = []
        risk_level = "low"
        if item.scope.visibility == "shared" and not item.scope.share_scope:
            reasons.append("shared memory missing explicit share scope")
            risk_level = "medium"
        if len(item.revisions) > 8:
            reasons.append("too many revisions on shared memory")
            risk_level = "medium"
        if item.session_id is None and item.scope.visibility == "shared":
            reasons.append("shared memory not anchored to session")
            risk_level = "high"
        if item.importance >= 0.8 and item.scope.visibility == "shared" and item.layer <= 4:
            reasons.append("high-importance low-layer memory entered shared pool")
            risk_level = "high"
        if item.scope.visibility == "shared" and item.scope.share_scope == "team" and item.scope.owner_agent_id is None:
            reasons.append("team shared memory missing owner")
            risk_level = "medium"
        blocked = risk_level == "high"
        return MemoryPollutionReport(memory_id=item.id, risk_level=risk_level, reasons=reasons, blocked=blocked)

    def share_memory(
        self,
        memory_id: str,
        share_scope: str,
        shared_with: list[str] | None = None,
        room_id: str | None = None,
        project_id: str | None = None,
    ) -> MemoryItem | None:
        item = self.get_item(memory_id)
        if item is None:
            return None
        item.scope.share_scope = share_scope
        item.scope.visibility = "shared"
        item.scope.shared_with = self._merge_tags(item.scope.shared_with, shared_with or [])
        item.scope.room_id = room_id or item.scope.room_id
        item.scope.project_id = project_id or item.scope.project_id
        item.metadata["share_scope"] = item.scope.share_scope
        item.metadata["visibility"] = item.scope.visibility
        item.metadata["shared_with"] = item.scope.shared_with
        item.metadata["room_id"] = item.scope.room_id
        item.metadata["project_id"] = item.scope.project_id
        item.metadata["pollution_report"] = self.detect_pollution(memory_id).model_dump(mode="json")
        self._append_to_disk(item)
        return item

    def unshare_memory(self, memory_id: str) -> MemoryItem | None:
        item = self.get_item(memory_id)
        if item is None:
            return None
        item.scope.share_scope = "private"
        item.scope.visibility = "private"
        item.scope.shared_with = []
        item.scope.room_id = None
        item.scope.project_id = None
        item.metadata["share_scope"] = item.scope.share_scope
        item.metadata["visibility"] = item.scope.visibility
        item.metadata["shared_with"] = []
        item.metadata["room_id"] = None
        item.metadata["project_id"] = None
        self._append_to_disk(item)
        return item

    def add_revision(self, memory_id: str, actor_agent_id: str | None, summary: str) -> MemoryRevision | None:
        item = self.get_item(memory_id)
        if item is None:
            return None
        revision = MemoryRevision(memory_id=memory_id, actor_agent_id=actor_agent_id, summary=summary)
        item.revisions.append(revision)
        item.metadata["revision_count"] = len(item.revisions)
        item.metadata["last_revision_id"] = revision.revision_id
        if summary:
            item.content = self._merge_session_summary(item.content, summary)
        self._append_to_disk(item)
        return revision

    async def search(
        self,
        context: RunContext,
        query: str,
        layers: list[int] | None = None,
        top_k: int = 5,
        scope: MemoryScope | None = None,
    ) -> list[MemoryItem]:
        hits = await self.search_with_scores(context, query, layers=layers, top_k=top_k, scope=scope)
        return [hit.item for hit in hits]

    async def search_with_scores(
        self,
        context: RunContext,
        query: str,
        layers: list[int] | None = None,
        top_k: int = 5,
        scope: MemoryScope | None = None,
    ) -> list[MemorySearchHit]:
        query_terms = {term.lower() for term in query.split() if term.strip()}
        graph_query_terms = set(MemoryGraph.extract_terms(query))
        related_terms = self._graph.related_terms(query_terms | graph_query_terms)
        allowed_layers = set(layers or list(range(1, 11)))
        query_embedding = await self._embed(query)
        scope = self._normalize_scope(scope, context, None, {})
        scored: list[MemorySearchHit] = []
        # Snapshot under lock: 循环内有 await，会让出控制权，避免并发 append 致迭代期列表变更（B3）。
        with self._lock:
            items_snapshot = list(self._items)
        for item in items_snapshot:
            if not self._can_access_item(context, item, scope):
                continue
            if item.layer not in allowed_layers:
                continue
            content_terms = set(item.content.lower().split())
            graph_content_terms = set(MemoryGraph.extract_terms(item.content))
            keyword_score = float(len(query_terms & content_terms))
            graph_score = float(len(related_terms & (content_terms | graph_content_terms)))
            vector_score = DeterministicEmbeddingModel.similarity(
                query_embedding,
                await self._embedding_for_item(item),
            )
            if query_terms and keyword_score == 0 and graph_score == 0 and vector_score <= 0.05:
                continue
            importance_score = item.importance
            freshness_score = self._freshness_score(item.created_at)
            scope_bonus = self._scope_bonus(item, scope)
            score = (
                keyword_score
                + (graph_score * 0.4)
                + (max(vector_score, 0.0) * 0.7)
                + (importance_score * 0.2)
                + (freshness_score * 0.1)
                + scope_bonus
            )
            scored.append(
                MemorySearchHit(
                    item=item,
                    score=round(score, 6),
                    keyword_score=keyword_score,
                    graph_score=graph_score,
                    vector_score=round(vector_score, 6),
                    importance_score=importance_score,
                    freshness_score=round(freshness_score, 6),
                )
            )
        scored.sort(key=lambda hit: (hit.score, hit.item.created_at), reverse=True)
        return scored[:top_k]

    def count(self) -> int:
        return len(self._items)

    def export_bundle(self, tenant_id: str | None = None) -> MemoryExportBundle:
        memories = list(self._items)
        sessions = list(self._sessions.values())
        if tenant_id is not None:
            memories = [item for item in memories if item.tenant_id == tenant_id]
            sessions = [session for session in sessions if session.tenant_id == tenant_id]
        return MemoryExportBundle(memories=memories, sessions=sessions)

    def import_bundle(self, bundle: MemoryExportBundle) -> dict[str, int]:
        imported_memories = 0
        imported_sessions = 0
        with self._lock:
            for session in bundle.sessions:
                self._sessions[session.session_id] = session
                imported_sessions += 1
            for item in bundle.memories:
                existing = self.get_item(item.id)
                if existing is None:
                    self._items.append(item)
                else:
                    existing.content = item.content
                    existing.scope = item.scope
                    existing.metadata = item.metadata
                    existing.tags = item.tags
                    existing.embedding = item.embedding
                    existing.revisions = item.revisions
                    existing.updated_at = item.created_at
                imported_memories += 1
        return {"memories": imported_memories, "sessions": imported_sessions}

    def session_count(self) -> int:
        return len(self._sessions)

    @staticmethod
    def _normalize_layer(layer: int) -> int:
        if layer < 1:
            return 1
        if layer > 10:
            return 10
        return layer

    @staticmethod
    def _normalize_tags(tags: list[str] | None) -> list[str]:
        normalized: list[str] = []
        for tag in tags or []:
            text = str(tag).strip()
            if text and text not in normalized:
                normalized.append(text)
        return normalized

    @staticmethod
    def _normalize_metadata(metadata: dict | None) -> dict:
        return dict(metadata or {})

    @staticmethod
    def _normalize_scope(
        scope: MemoryScope | None,
        context: RunContext,
        session_id: str | None,
        metadata: dict,
    ) -> MemoryScope:
        if scope is not None:
            return scope
        return MemoryScope(
            owner_agent_id=context.agent_id,
            share_scope=metadata.get("share_scope", "private"),
            visibility=metadata.get("visibility", "private"),
            shared_with=list(metadata.get("shared_with", [])),
            project_id=metadata.get("project_id"),
            room_id=metadata.get("room_id"),
            task_id=metadata.get("task_id") or session_id,
        )

    @staticmethod
    def _layer_role(layer: int) -> str:
        roles = {
            1: "instant_context",
            2: "session_working",
            3: "task_memory",
            4: "collaboration_memory",
            5: "tool_memory",
            6: "behavior_memory",
            7: "project_memory",
            8: "organization_memory",
            9: "platform_memory",
            10: "long_term_evolution",
        }
        return roles.get(layer, "long_term_evolution")



    def get_item(self, memory_id: str) -> MemoryItem | None:
        with self._lock:
            for item in self._items:
                if item.id == memory_id:
                    return item
        return None

    def layer_profile(self, layer: int) -> dict[str, str]:
        return dict(self._LAYER_PROFILES[self._normalize_layer(layer)])

    def layer_counts(self) -> dict[int, int]:
        counts: dict[int, int] = {layer: 0 for layer in range(1, 11)}
        with self._lock:
            items_snapshot = list(self._items)
        for item in items_snapshot:
            counts[item.layer] = counts.get(item.layer, 0) + 1
        return counts

    def layer_summary(self) -> list[dict[str, object]]:
        counts = self.layer_counts()
        return [
            {"layer": layer, **self.layer_profile(layer), "count": counts.get(layer, 0)}
            for layer in range(1, 11)
        ]

    def layer_roles(self) -> dict[int, str]:
        return {layer: self._layer_role(layer) for layer in range(1, 11)}

    def layer_items(self, layer: int) -> list[MemoryItem]:
        layer = self._normalize_layer(layer)
        with self._lock:
            return [item for item in self._items if item.layer == layer]

    def session_items(self, session_id: str) -> list[MemoryItem]:
        with self._lock:
            return [item for item in self._items if item.session_id == session_id]

    def session_summary(self, session_id: str) -> dict[str, object] | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        items = self.session_items(session_id)
        layer_breakdown: dict[int, int] = {}
        for item in items:
            layer_breakdown[item.layer] = layer_breakdown.get(item.layer, 0) + 1
        return {
            "session": session.model_dump(mode="json"),
            "count": len(items),
            "layer_breakdown": layer_breakdown,
            "layers": sorted(layer_breakdown),
            "latest_memory_id": session.last_memory_id,
            "shared": session.shared,
            "room_id": session.room_id,
            "project_id": session.project_id,
        }

    def session_memory_layers(self, session_id: str) -> list[dict[str, object]]:
        items = self.session_items(session_id)
        grouped: dict[int, list[MemoryItem]] = {}
        for item in items:
            grouped.setdefault(item.layer, []).append(item)
        return [
            {
                "layer": layer,
                "profile": self.layer_profile(layer),
                "count": len(layer_items),
                "items": [it.model_dump(mode="json") for it in layer_items],
            }
            for layer, layer_items in sorted(grouped.items())
        ]

    def agent_items(self, agent_id: str) -> list[MemoryItem]:
        with self._lock:
            return [item for item in self._items if item.agent_id == agent_id]

    def agent_summary(self, agent_id: str) -> dict[str, object] | None:
        agent_items = self.agent_items(agent_id)
        if not agent_items:
            return None
        layer_breakdown: dict[int, int] = {}
        session_ids = []
        for item in agent_items:
            layer_breakdown[item.layer] = layer_breakdown.get(item.layer, 0) + 1
            if item.session_id and item.session_id not in session_ids:
                session_ids.append(item.session_id)
        return {
            "agent_id": agent_id,
            "count": len(agent_items),
            "layer_breakdown": layer_breakdown,
            "layers": sorted(layer_breakdown),
            "session_ids": session_ids,
            "latest_memory_id": agent_items[-1].id if agent_items else None,
        }

    def agent_memory_layers(self, agent_id: str) -> list[dict[str, object]]:
        items = self.agent_items(agent_id)
        grouped: dict[int, list[MemoryItem]] = {}
        for item in items:
            grouped.setdefault(item.layer, []).append(item)
        return [
            {
                "layer": layer,
                "profile": self.layer_profile(layer),
                "count": len(layer_items),
                "items": [it.model_dump(mode="json") for it in layer_items],
            }
            for layer, layer_items in sorted(grouped.items())
        ]

    def snapshot(self) -> dict[str, object]:
        return {
            "count": self.count(),
            "session_count": self.session_count(),
            "layers": self.layer_summary(),
        }

    async def consolidate(
        self,
        context: RunContext,
        source_layers: list[int] | None = None,
        target_layer: int = 4,
        max_items: int = 20,
        min_importance: float = 0.0,
    ) -> MemoryConsolidationResult:
        allowed_layers = set(source_layers or [3, 4, 5, 6, 7, 8])
        candidates = [
            item
            for item in self._items
            if item.tenant_id == context.tenant_id
            and item.layer in allowed_layers
            and item.importance >= min_importance
            and "consolidated" not in item.tags
            and item.metadata.get("request_id") != context.request_id
        ]
        candidates.sort(key=lambda item: (item.importance, item.created_at), reverse=True)
        selected = candidates[:max_items]
        if not selected:
            return MemoryConsolidationResult(source_count=0)
        summary = self._consolidation_summary(selected)
        tags = self._consolidation_tags(selected)
        target_memory_id = await self.store(
            context,
            summary,
            layer=target_layer,
            importance=max(item.importance for item in selected),
            tags=tags,
            metadata={
                "source_memory_ids": [item.id for item in selected],
                "source_count": len(selected),
                "kind": "memory_consolidation",
            },
        )
        return MemoryConsolidationResult(
            source_count=len(selected),
            target_memory_id=target_memory_id,
            summary=summary,
            tags=tags,
        )

    def _can_access_item(self, context: RunContext, item: MemoryItem, scope: MemoryScope) -> bool:
        if item.tenant_id != context.tenant_id:
            return False
        if item.agent_id and context.agent_id and item.agent_id != context.agent_id:
            if item.scope.visibility == "private":
                return False
        if scope.room_id and item.scope.room_id and item.scope.room_id != scope.room_id:
            return False
        if scope.project_id and item.scope.project_id and item.scope.project_id != scope.project_id:
            return False
        if scope.task_id and item.scope.task_id and item.scope.task_id != scope.task_id:
            return False
        if item.scope.visibility == "shared":
            if scope.share_scope == "private":
                return item.scope.owner_agent_id == context.agent_id
            if scope.share_scope == "room" and scope.room_id:
                return item.scope.room_id == scope.room_id
            if scope.share_scope == "project" and scope.project_id:
                return item.scope.project_id == scope.project_id
            if scope.share_scope == "team":
                return context.user_id in item.scope.shared_with or context.agent_id == item.scope.owner_agent_id
        return item.scope.owner_agent_id == context.agent_id or item.agent_id == context.agent_id or item.scope.visibility == "shared"

    @staticmethod
    def _scope_bonus(item: MemoryItem, scope: MemoryScope) -> float:
        bonus = 0.0
        if scope.room_id and item.scope.room_id == scope.room_id:
            bonus += 0.4
        if scope.project_id and item.scope.project_id == scope.project_id:
            bonus += 0.3
        if scope.task_id and item.scope.task_id == scope.task_id:
            bonus += 0.5
        if item.scope.visibility == "shared":
            bonus += 0.2
        return bonus

    def _attach_to_session(self, context: RunContext, session_id: str, item: MemoryItem) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            session = SessionRecord(
                session_id=session_id,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
                agent_id=context.agent_id,
                metadata={"imported": True},
            )
            self._sessions[session_id] = session
        session.updated_at = datetime.now(UTC)
        session.last_memory_id = item.id
        session.summary = self._merge_session_summary(session.summary, item.content)
        session.tags = self._merge_tags(session.tags, item.tags)
        self._append_to_disk(session)

    @staticmethod
    def _merge_session_summary(existing: str, content: str) -> str:
        existing = existing.strip()
        content = " ".join(content.split())
        if not existing:
            return content[:500]
        return f"{existing}\n{content[:240]}"

    @staticmethod
    def _merge_tags(current: list[str], incoming: list[str]) -> list[str]:
        merged: list[str] = []
        for tag in [*current, *incoming]:
            text = str(tag).strip()
            if text and text not in merged:
                merged.append(text)
        return merged[:20]


    def _load_from_disk(self) -> None:
        if self._storage_path is None or not self._storage_path.exists():
            return
        # Upsert-by-id: mutation paths (_append_to_disk on revision/share/merge)
        # re-append the full record, so the latest line for an id wins instead
        # of duplicating the item on every reload.
        index_by_id: dict[str, int] = {}
        with self._storage_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                if payload.get("session_id") and "content" not in payload:
                    session = SessionRecord.model_validate(payload)
                    self._sessions[session.session_id] = session
                    continue
                item = MemoryItem.model_validate(payload)
                if item.id in index_by_id:
                    self._items[index_by_id[item.id]] = item
                else:
                    index_by_id[item.id] = len(self._items)
                    self._items.append(item)
                self._graph.add_text(item.content)

    def _append_to_disk(self, record: MemoryItem | SessionRecord) -> None:
        if self._storage_path is None:
            return
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self._storage_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.model_dump(mode="json"), ensure_ascii=False) + "\n")

    async def _embedding_for_item(self, item: MemoryItem) -> list[float]:
        if item.embedding:
            return item.embedding
        item.embedding = await self._embed(item.content)
        return item.embedding

    # ------------------------------------------------------------------
    # Write-path deduplication (P1-13)
    # ------------------------------------------------------------------

    async def _find_write_duplicate(self, item: MemoryItem) -> str | None:
        """Return the id of an existing tenant-scoped duplicate, or None."""
        if self._dedup is None:
            return None
        with self._lock:
            candidates = [c for c in self._items if c.tenant_id == item.tenant_id]
        if not candidates:
            return None
        if len(candidates) > self._dedup_candidate_limit:
            candidates = candidates[-self._dedup_candidate_limit :]
        # Fast path: exact normalized-content hash (no embedding work needed).
        new_hash = self._dedup.content_hash(item.content)
        for candidate in candidates:
            if self._dedup.content_hash(candidate.content) == new_hash:
                return candidate.id
        if not item.embedding:
            return None
        # Vector path via the repo's dedup engine (MemoryDeduplicatorEnhanced).
        canonical_candidates = []
        for candidate in candidates:
            if not candidate.embedding:
                candidate.embedding = await self._embed(candidate.content)
            canonical_candidates.append(canonical_from_store_item(candidate))
        duplicate = self._dedup.find_duplicate(
            canonical_from_store_item(item),
            canonical_candidates,
        )
        return duplicate.id if duplicate is not None else None

    def _merge_duplicate(self, existing: MemoryItem, incoming: MemoryItem) -> None:
        """Merge a duplicate write into the kept item (kept content wins)."""
        existing.tags = self._merge_tags(existing.tags, incoming.tags)
        existing.importance = max(existing.importance, incoming.importance)
        merges = existing.metadata.setdefault("merged_writes", [])
        merges.append(
            {
                "content": incoming.content[:500],
                "content_hash": (
                    self._dedup.content_hash(incoming.content) if self._dedup else ""
                ),
                "layer": incoming.layer,
                "merged_at": datetime.now(UTC).isoformat(),
            }
        )
        if len(merges) > 20:
            del merges[:-20]
        existing.metadata["merge_count"] = len(merges)
        if self._dedup is not None:
            self._dedup.note_merge()
        logger.info(
            "memory write deduplicated: merged into %s (tenant=%s)",
            existing.id,
            existing.tenant_id,
        )

    def dedup_stats(self) -> dict[str, object]:
        """Expose write-path dedup status (explicit, inspectable)."""
        return {
            "enabled": self._dedup is not None,
            "vector_threshold": self._dedup.vector_threshold if self._dedup else None,
            "merged_writes": self._dedup.merged_writes if self._dedup else 0,
            "candidate_limit": self._dedup_candidate_limit,
        }

    async def deduplicate(self, context: RunContext, strategy: str = "combined") -> dict[str, object]:
        """Batch maintenance dedup over this tenant's memories.

        Runs the existing ``MemoryDeduplicationService`` engine over converted
        canonical memories, removes losers from the store, annotates kept items
        and rewrites the JSONL backing file so removals actually persist.
        """
        if self._dedup is None:
            return {"enabled": False, "removed": 0, "original_count": 0, "deduplicated_count": 0}
        with self._lock:
            items = [c for c in self._items if c.tenant_id == context.tenant_id]
        if len(items) < 2:
            return {
                "enabled": True,
                "removed": 0,
                "original_count": len(items),
                "deduplicated_count": len(items),
            }
        from backend.app.core.memory_deduplication_service import MemoryDeduplicationService

        service = MemoryDeduplicationService(
            vector_similarity_threshold=self._dedup.vector_threshold
        )
        for item in items:
            if not item.embedding:
                item.embedding = await self._embed(item.content)
        # Partition by embedding length: items embedded by different models
        # historically cannot be compared in one similarity matrix.
        partitions: dict[int, list[MemoryItem]] = {}
        for item in items:
            partitions.setdefault(len(item.embedding), []).append(item)

        removed_ids: set[str] = set()
        merge_summary: dict[str, dict] = {}
        total_groups = 0
        for partition in partitions.values():
            if len(partition) < 2:
                continue
            result = await service.deduplicate_memories(
                [
                    dedup_memory_from_canonical(canonical_from_store_item(item))
                    for item in partition
                ],
                strategy=strategy,
            )
            removed_ids.update(result.removed_ids)
            merge_summary.update(result.merge_summary)
            total_groups += len(result.merged_groups)

        if removed_ids:
            with self._lock:
                self._items = [c for c in self._items if c.id not in removed_ids]
                for kept_id, info in merge_summary.items():
                    kept = self.get_item(kept_id)
                    if kept is not None:
                        kept.metadata["dedup_merged_ids"] = list(info.get("merged_ids", []))
                self._rewrite_disk()
        logger.info(
            "batch dedup tenant=%s: %d -> %d (removed %d, groups %d)",
            context.tenant_id,
            len(items),
            len(items) - len(removed_ids),
            len(removed_ids),
            total_groups,
        )
        return {
            "enabled": True,
            "original_count": len(items),
            "deduplicated_count": len(items) - len(removed_ids),
            "removed": len(removed_ids),
            "removed_ids": sorted(removed_ids),
            "merged_groups": total_groups,
        }

    def _rewrite_disk(self) -> None:
        """Rewrite the whole JSONL backing file (used after batch removals)."""
        if self._storage_path is None:
            return
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self._storage_path.open("w", encoding="utf-8") as handle:
            for session in self._sessions.values():
                handle.write(json.dumps(session.model_dump(mode="json"), ensure_ascii=False) + "\n")
            for item in self._items:
                handle.write(json.dumps(item.model_dump(mode="json"), ensure_ascii=False) + "\n")

    async def _embed(self, text: str) -> list[float]:
        result = self._embedding_model.embed(text)
        if isawaitable(result):
            return await result
        return result

    @staticmethod
    def _freshness_score(created_at: datetime) -> float:
        now = datetime.now(UTC)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        age_days = max((now - created_at).total_seconds() / 86_400, 0.0)
        return 1.0 / (1.0 + age_days)

    @staticmethod
    def _consolidation_summary(items: list[MemoryItem]) -> str:
        lines = ["Consolidated memory:"]
        for item in items:
            content = " ".join(item.content.split())
            excerpt = content if len(content) <= 240 else content[:237] + "..."
            lines.append(f"- L{item.layer} importance={item.importance:.2f}: {excerpt}")
        return "\n".join(lines)

    @staticmethod
    def _consolidation_tags(items: list[MemoryItem]) -> list[str]:
        counts: dict[str, int] = {}
        for item in items:
            for tag in item.tags:
                counts[tag] = counts.get(tag, 0) + 1
        ranked = sorted(counts, key=lambda tag: (counts[tag], tag), reverse=True)
        return ["consolidated", *ranked[:8]]


memory_system = MemorySystem()

InMemoryMemorySystem = MemorySystem
