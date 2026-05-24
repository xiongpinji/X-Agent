from __future__ import annotations

import json
from datetime import UTC, datetime
from inspect import isawaitable
from typing import Any

from backend.app.core.contracts import RunContext
from backend.app.core.embeddings import EmbeddingModel
from backend.app.core.memory import MemoryConsolidationResult, MemoryItem, MemorySystem

MEMORY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS memories (
    id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    agent_id UUID NULL,
    content TEXT NOT NULL,
    layer INTEGER NOT NULL CHECK (layer BETWEEN 1 AND 4),
    importance DOUBLE PRECISION NOT NULL CHECK (importance >= 0 AND importance <= 1),
    tags TEXT[] NOT NULL DEFAULT '{}',
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memories_tenant_layer_created
    ON memories (tenant_id, layer, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_memories_content_trgm
    ON memories USING gin (content gin_trgm_ops);
"""


class PostgresMemorySystem:
    """PostgreSQL-backed L1-L4 memory store.

    Search is intentionally keyword-based for Phase 0. pgvector/hybrid retrieval can
    be added behind the same methods once embedding generation exists.
    """

    def __init__(
        self,
        database_url: str,
        pool: Any | None = None,
        ensure_schema: bool = True,
        embedding_model: EmbeddingModel | None = None,
        enable_vector_search: bool = False,
        vector_dimensions: int = 1536,
    ) -> None:
        self.database_url = database_url
        self._pool = pool
        self._ensure_schema = ensure_schema
        self._initialized = False
        self._embedding_model = embedding_model
        self._enable_vector_search = enable_vector_search
        self._vector_dimensions = vector_dimensions

    async def store(
        self,
        context: RunContext,
        content: str,
        layer: int = 3,
        importance: float = 0.5,
        tags: list[str] | None = None,
        metadata: dict | None = None,
    ) -> str:
        pool = await self._get_pool()
        item = MemoryItem(
            tenant_id=context.tenant_id,
            agent_id=context.agent_id,
            content=content,
            layer=layer,
            importance=importance,
            tags=tags or [],
            metadata=metadata or {},
        )
        if self._enable_vector_search and self._embedding_model is not None:
            item.embedding = await self._embed(content)
            await pool.execute(
                """
                INSERT INTO memories (
                    id, tenant_id, agent_id, content, layer, importance, tags,
                    metadata, created_at, embedding
                )
                VALUES ($1::uuid, $2, $3::uuid, $4, $5, $6, $7::text[], $8::jsonb, $9, $10::vector)
                """,
                item.id,
                item.tenant_id,
                item.agent_id,
                item.content,
                item.layer,
                item.importance,
                item.tags,
                json.dumps(item.metadata),
                item.created_at,
                self._vector_literal(item.embedding),
            )
        else:
            await pool.execute(
                """
                INSERT INTO memories (
                    id, tenant_id, agent_id, content, layer, importance, tags, metadata, created_at
                )
                VALUES ($1::uuid, $2, $3::uuid, $4, $5, $6, $7::text[], $8::jsonb, $9)
                """,
                item.id,
                item.tenant_id,
                item.agent_id,
                item.content,
                item.layer,
                item.importance,
                item.tags,
                json.dumps(item.metadata),
                item.created_at,
            )
        return item.id

    async def search(
        self,
        context: RunContext,
        query: str,
        layers: list[int] | None = None,
        top_k: int = 5,
    ) -> list[MemoryItem]:
        pool = await self._get_pool()
        normalized_query = self._escape_ilike(query.strip())
        if self._enable_vector_search and self._embedding_model is not None:
            query_embedding = await self._embed(query)
            rows = await pool.fetch(
                """
                SELECT
                    id::text, tenant_id, agent_id::text, content,
                    layer, importance, tags, metadata, created_at
                FROM memories
                WHERE tenant_id = $1
                  AND layer = ANY($2::int[])
                ORDER BY embedding <=> $3::vector, importance DESC, created_at DESC
                LIMIT $4
                """,
                context.tenant_id,
                layers or [1, 2, 3, 4],
                self._vector_literal(query_embedding),
                top_k,
            )
            return [self._row_to_item(row) for row in rows]

        rows = await pool.fetch(
            """
            SELECT
                id::text, tenant_id, agent_id::text, content,
                layer, importance, tags, metadata, created_at
            FROM memories
            WHERE tenant_id = $1
              AND layer = ANY($2::int[])
              AND (
                $3 = ''
                OR content ILIKE ('%' || $3 || '%') ESCAPE '\'
                OR EXISTS (
                    SELECT 1 FROM unnest(tags) AS tag
                    WHERE tag ILIKE ('%' || $3 || '%') ESCAPE '\'
                )
              )
            ORDER BY importance DESC, created_at DESC
            LIMIT $4
            """,
            context.tenant_id,
            layers or [1, 2, 3, 4],
            normalized_query,
            top_k,
        )
        return [self._row_to_item(row) for row in rows]

    async def count(self) -> int:
        pool = await self._get_pool()
        return await pool.fetchval("SELECT COUNT(*) FROM memories")

    async def consolidate(
        self,
        context: RunContext,
        source_layers: list[int] | None = None,
        target_layer: int = 2,
        max_items: int = 20,
        min_importance: float = 0.0,
    ) -> MemoryConsolidationResult:
        candidates = await self.search(
            context,
            "",
            layers=source_layers or [3, 4],
            top_k=max_items,
        )
        selected = [
            item
            for item in candidates
            if item.importance >= min_importance and "consolidated" not in item.tags
        ]
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

    async def _get_pool(self) -> Any:
        if self._pool is None:
            import asyncpg

            self._pool = await asyncpg.create_pool(self.database_url)
        if self._ensure_schema and not self._initialized:
            await self._pool.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
            await self._pool.execute(MEMORY_SCHEMA_SQL)
            if self._enable_vector_search:
                await self._pool.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                await self._pool.execute(
                    f"""
                    ALTER TABLE memories
                    ADD COLUMN IF NOT EXISTS embedding vector({self._vector_dimensions});
                    """
                )
                await self._pool.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_memories_embedding
                    ON memories USING ivfflat (embedding vector_cosine_ops);
                    """
                )
            self._initialized = True
        return self._pool

    @staticmethod
    def _row_to_item(row: Any) -> MemoryItem:
        metadata = row["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        return MemoryItem(
            id=row["id"],
            tenant_id=row["tenant_id"],
            agent_id=row["agent_id"],
            content=row["content"],
            layer=row["layer"],
            importance=row["importance"],
            tags=list(row["tags"]),
            metadata=metadata,
            created_at=created_at,
        )

    async def _embed(self, text: str) -> list[float]:
        if self._embedding_model is None:
            return []
        result = self._embedding_model.embed(text)
        if isawaitable(result):
            return await result
        return result

    @staticmethod
    def _vector_literal(embedding: list[float]) -> str:
        return "[" + ",".join(str(value) for value in embedding) + "]"

    @staticmethod
    def _escape_ilike(text: str) -> str:
        return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
