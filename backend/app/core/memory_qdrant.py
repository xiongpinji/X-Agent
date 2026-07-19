"""Qdrant-backed memory system (``memory_backend='qdrant'``).

Until now, selecting ``memory_backend='qdrant'`` silently fell through to the
JSONL store in ``dependencies.build_memory_system``. This module provides the
real backend.

Explicit degradation semantics (no silent fall-through):
- ``strict=True``: missing ``qdrant-client`` package or unreachable server
  raises ``RuntimeError`` at construction.
- ``strict=False`` (default): the same conditions log a WARNING and degrade to
  an embedded JSONL/in-memory :class:`MemorySystem`. The degradation is always
  inspectable via ``backend_status`` / ``degraded_reason`` and is surfaced in
  logs — it is never silent.

Integration (Wave-B wiring, do NOT apply here — dependencies.py is owned by the
integration wave): in ``backend/app/dependencies.py::build_memory_system`` add

    if memory_backend == "qdrant":
        from backend.app.core.memory_qdrant import build_qdrant_memory_system
        return build_qdrant_memory_system(
            url=qdrant_url,                      # settings.qdrant_url
            api_key=qdrant_api_key,              # settings.qdrant_api_key
            embedding_model=embedding_model,     # built as today
            strict=settings.app_mode == "production",
            fallback_storage_path=memory_store_path,
        )

and pass ``qdrant_url=settings.qdrant_url, qdrant_api_key=settings.qdrant_api_key``
through from ``get_memory()``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.core.contracts import RunContext
from backend.app.core.embeddings import EmbeddingModel
from backend.app.core.memory.store import (
    MemoryConsolidationResult,
    MemoryItem,
    MemoryScope,
    MemorySearchHit,
    MemorySystem,
)

logger = logging.getLogger(__name__)

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels
except ImportError:  # pragma: no cover - optional runtime dependency
    QdrantClient = None  # type: ignore[assignment]
    qmodels = None  # type: ignore[assignment]

DEFAULT_COLLECTION = "xagent_memories"


class QdrantMemorySystem:
    """Qdrant vector-store backend with explicit, inspectable degradation."""

    def __init__(
        self,
        *,
        url: str | None = None,
        api_key: str | None = None,
        collection: str = DEFAULT_COLLECTION,
        embedding_model: EmbeddingModel | None = None,
        client: Any | None = None,
        strict: bool = False,
        fallback_storage_path: str | Path | None = None,
        connect_timeout_seconds: float = 5.0,
    ) -> None:
        self.collection = collection
        self._embedding_model = embedding_model
        self._client: Any | None = None
        self._collection_ready = False
        self._collection_vector_size: int | None = None
        self._degraded = False
        self._degraded_reason: str | None = None
        self._fallback: MemorySystem | None = None

        failure: str | None = None
        if client is not None:
            self._client = client
        elif QdrantClient is None:
            failure = "qdrant-client package is not installed"
        else:
            try:
                candidate = QdrantClient(
                    url=url,
                    api_key=api_key,
                    timeout=connect_timeout_seconds,
                    check_compatibility=False,
                )
                candidate.get_collections()  # connectivity probe
                self._client = candidate
            except Exception as exc:
                failure = f"cannot reach Qdrant at {url!r}: {exc}"

        if failure is not None:
            if strict:
                raise RuntimeError(f"memory_backend='qdrant' unavailable: {failure}")
            self._degraded = True
            self._degraded_reason = failure
            self._fallback = MemorySystem(
                storage_path=fallback_storage_path,
                embedding_model=embedding_model,
            )
            logger.warning(
                "memory_backend='qdrant' DEGRADED: %s. Falling back to %s "
                "(set strict=True to fail fast instead).",
                failure,
                f"JSONL store at {fallback_storage_path}"
                if fallback_storage_path
                else "in-memory store",
            )

    # ------------------------------------------------------------------
    # Status surface (explicit degradation is inspectable, never silent)
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        return not self._degraded

    @property
    def backend_status(self) -> str:
        return "degraded" if self._degraded else "ok"

    @property
    def degraded_reason(self) -> str | None:
        return self._degraded_reason

    def status(self) -> dict[str, Any]:
        return {
            "backend": "qdrant",
            "status": self.backend_status,
            "degraded_reason": self._degraded_reason,
            "collection": None if self._degraded else self.collection,
        }

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

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
        if self._fallback is not None:
            return await self._fallback.store(
                context,
                content,
                layer=layer,
                importance=importance,
                tags=tags,
                metadata=metadata,
                session_id=session_id,
                scope=scope,
            )
        item = MemoryItem(
            tenant_id=context.tenant_id,
            agent_id=context.agent_id,
            session_id=session_id,
            content=content,
            layer=max(1, min(int(layer), 10)),
            importance=importance,
            tags=list(tags or []),
            metadata=dict(metadata or {}),
            embedding=await self._embed(content),
        )
        if not item.embedding:
            raise RuntimeError(
                "QdrantMemorySystem requires an embedding model that returns vectors; "
                "got an empty embedding."
            )
        await asyncio.to_thread(self._upsert_item, item)
        return item.id

    def _upsert_item(self, item: MemoryItem) -> None:
        self._ensure_collection(len(item.embedding))
        if self._collection_vector_size != len(item.embedding):
            raise ValueError(
                f"embedding dimension mismatch: collection {self.collection!r} expects "
                f"{self._collection_vector_size}, got {len(item.embedding)}. Use a "
                "consistent embedding backend or a new collection."
            )
        self._client.upsert(
            collection_name=self.collection,
            points=[
                qmodels.PointStruct(
                    id=item.id,
                    vector=item.embedding,
                    payload=self._item_to_payload(item),
                )
            ],
        )

    def _ensure_collection(self, vector_size: int) -> None:
        if self._collection_ready:
            return
        existing = [c.name for c in self._client.get_collections().collections]
        if self.collection not in existing:
            self._client.create_collection(
                collection_name=self.collection,
                vectors_config=qmodels.VectorParams(
                    size=vector_size,
                    distance=qmodels.Distance.COSINE,
                ),
            )
            self._collection_vector_size = vector_size
        else:
            info = self._client.get_collection(self.collection)
            params = info.config.params.vectors
            self._collection_vector_size = getattr(params, "size", None) or vector_size
        self._collection_ready = True

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

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
        if self._fallback is not None:
            return await self._fallback.search_with_scores(
                context, query, layers=layers, top_k=top_k, scope=scope
            )
        query_embedding = await self._embed(query)
        if not query_embedding:
            return []
        points = await asyncio.to_thread(
            self._query_points, query_embedding, context.tenant_id, layers, top_k
        )
        hits: list[MemorySearchHit] = []
        for point in points:
            item = self._payload_to_item(
                point.payload or {}, point_id=str(getattr(point, "id", "") or "")
            )
            if item is None:
                continue
            score = float(getattr(point, "score", 0.0) or 0.0)
            hits.append(
                MemorySearchHit(
                    item=item,
                    score=round(score + item.importance * 0.2, 6),
                    vector_score=round(score, 6),
                    importance_score=item.importance,
                )
            )
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:top_k]

    def _query_points(
        self,
        query_embedding: list[float],
        tenant_id: str,
        layers: list[int] | None,
        top_k: int,
    ) -> list[Any]:
        must = [qmodels.FieldCondition(key="tenant_id", match=qmodels.MatchValue(value=tenant_id))]
        if layers:
            must.append(
                qmodels.FieldCondition(key="layer", match=qmodels.MatchAny(any=list(layers)))
            )
        response = self._client.query_points(
            collection_name=self.collection,
            query=query_embedding,
            query_filter=qmodels.Filter(must=must),
            limit=top_k,
            with_payload=True,
        )
        return list(response.points)

    async def count(self) -> int:
        if self._fallback is not None:
            return self._fallback.count()
        result = await asyncio.to_thread(
            self._client.count, self.collection, None, True
        )
        return int(getattr(result, "count", 0))

    async def consolidate(
        self,
        context: RunContext,
        source_layers: list[int] | None = None,
        target_layer: int = 4,
        max_items: int = 20,
        min_importance: float = 0.0,
    ) -> MemoryConsolidationResult:
        if self._fallback is not None:
            return await self._fallback.consolidate(
                context,
                source_layers=source_layers,
                target_layer=target_layer,
                max_items=max_items,
                min_importance=min_importance,
            )
        candidates = await self._scroll_tenant(context.tenant_id, source_layers or [3, 4, 5, 6, 7, 8])
        selected = [
            item
            for item in candidates
            if item.importance >= min_importance and "consolidated" not in item.tags
        ][:max_items]
        if not selected:
            return MemoryConsolidationResult(source_count=0)
        summary = MemorySystem._consolidation_summary(selected)
        tags = MemorySystem._consolidation_tags(selected)
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

    async def _scroll_tenant(self, tenant_id: str, layers: list[int]) -> list[MemoryItem]:
        def _scroll() -> list[Any]:
            must = [
                qmodels.FieldCondition(key="tenant_id", match=qmodels.MatchValue(value=tenant_id)),
                qmodels.FieldCondition(key="layer", match=qmodels.MatchAny(any=list(layers))),
            ]
            records, _next = self._client.scroll(
                collection_name=self.collection,
                scroll_filter=qmodels.Filter(must=must),
                limit=256,
                with_payload=True,
            )
            return list(records)

        records = await asyncio.to_thread(_scroll)
        items = []
        for record in records:
            item = self._payload_to_item(
                record.payload or {}, point_id=str(getattr(record, "id", "") or "")
            )
            if item is not None:
                items.append(item)
        items.sort(key=lambda item: (item.importance, item.created_at), reverse=True)
        return items

    # ------------------------------------------------------------------
    # Explicitly unsupported MemorySystem conveniences (no fake success)
    # ------------------------------------------------------------------

    def add_revision(self, *args: Any, **kwargs: Any) -> None:
        if self._fallback is not None:
            return self._fallback.add_revision(*args, **kwargs)
        raise NotImplementedError(
            "QdrantMemorySystem does not support revisions; use the JSONL or "
            "postgres backend for revision workflows."
        )

    # ------------------------------------------------------------------
    # Payload conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _item_to_payload(item: MemoryItem) -> dict[str, Any]:
        return {
            "tenant_id": item.tenant_id,
            "agent_id": item.agent_id,
            "session_id": item.session_id,
            "content": item.content,
            "layer": item.layer,
            "importance": item.importance,
            "tags": list(item.tags),
            "metadata": item.metadata,
            "created_at": item.created_at.isoformat(),
        }

    @staticmethod
    def _payload_to_item(
        payload: dict[str, Any], point_id: str = ""
    ) -> MemoryItem | None:
        try:
            created_raw = payload.get("created_at")
            created_at = (
                datetime.fromisoformat(created_raw)
                if isinstance(created_raw, str)
                else datetime.now(UTC)
            )
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)
            item_id = point_id or str(payload.get("id") or payload.get("memory_id") or "")
            if not item_id:
                raise ValueError("payload missing point id")
            return MemoryItem(
                id=item_id,
                tenant_id=str(payload.get("tenant_id", "")),
                agent_id=payload.get("agent_id"),
                session_id=payload.get("session_id"),
                content=str(payload.get("content", "")),
                layer=int(payload.get("layer", 3)),
                importance=float(payload.get("importance", 0.5)),
                tags=list(payload.get("tags", [])),
                metadata=dict(payload.get("metadata", {})),
                created_at=created_at,
            )
        except Exception:
            logger.warning("skipping malformed qdrant payload keys=%s", sorted(payload))
            return None

    async def _embed(self, text: str) -> list[float]:
        if self._embedding_model is None:
            return []
        from inspect import isawaitable

        result = self._embedding_model.embed(text)
        if isawaitable(result):
            return await result
        return result


def build_qdrant_memory_system(
    *,
    url: str | None,
    api_key: str | None = None,
    collection: str = DEFAULT_COLLECTION,
    embedding_model: EmbeddingModel | None = None,
    strict: bool = False,
    fallback_storage_path: str | Path | None = None,
    connect_timeout_seconds: float = 5.0,
) -> QdrantMemorySystem:
    """Factory used by the integration-wave wiring in dependencies.py."""
    return QdrantMemorySystem(
        url=url,
        api_key=api_key,
        collection=collection,
        embedding_model=embedding_model,
        strict=strict,
        fallback_storage_path=fallback_storage_path,
        connect_timeout_seconds=connect_timeout_seconds,
    )
