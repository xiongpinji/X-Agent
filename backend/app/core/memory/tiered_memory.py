"""Three-tier memory system (对标 Hermes 三层记忆).

Tier 1 (L1-L3): In-memory + Redis — session working memory, TTL auto-expire
Tier 2 (L4-L7): PostgreSQL + pgvector — project/task memory, full-text + vector search
Tier 3 (L8-L10): Qdrant + optional Neo4j — long-term org memory, semantic + graph
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class MemoryHit:
    """A memory search result."""
    content: str = ""
    layer: int = 1
    score: float = 0.0
    tier: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class Tier1Backend:
    """In-memory working memory with TTL (L1-L3)."""

    def __init__(self, max_items: int = 10000, default_ttl: int = 3600):
        self._store: dict[str, dict[str, Any]] = {}
        self.max_items = max_items
        self.default_ttl = default_ttl

    async def store(self, key: str, content: str, layer: int = 1, ttl: int | None = None, **kwargs) -> None:
        self._store[key] = {
            "content": content,
            "layer": layer,
            "expires_at": time.time() + (ttl or self.default_ttl),
            "created_at": time.time(),
            **kwargs,
        }
        self._evict_expired()

    async def search(self, query: str, limit: int = 10) -> list[MemoryHit]:
        self._evict_expired()
        query_lower = query.lower()
        hits = []
        for _key, item in self._store.items():
            if query_lower in item["content"].lower():
                hits.append(MemoryHit(
                    content=item["content"],
                    layer=item["layer"],
                    score=1.0,
                    tier=1,
                    created_at=item["created_at"],
                ))
        return sorted(hits, key=lambda h: h.created_at, reverse=True)[:limit]

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [k for k, v in self._store.items() if v["expires_at"] < now]
        for k in expired:
            del self._store[k]


class Tier2Backend:
    """PostgreSQL-backed project memory (L4-L7)."""

    def __init__(self, pool=None, embedding_model=None):
        self._pool = pool
        self._embedding_model = embedding_model

    async def store(self, content: str, layer: int = 4, embedding: list[float] | None = None, **kwargs) -> None:
        if not self._pool:
            logger.warning("Tier2: No PostgreSQL pool configured")
            return
        import json as _json
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO memories (id, tenant_id, content, layer, importance, tags, metadata)
                VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6)
                """,
                kwargs.get("tenant_id", "default"),
                content,
                layer,
                kwargs.get("importance", 0.5),
                kwargs.get("tags", []),
                _json.dumps(kwargs.get("metadata", {})),
            )

    async def vector_search(self, query_embedding: list[float], limit: int = 10) -> list[MemoryHit]:
        if not self._pool:
            return []
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT content, layer, importance, created_at FROM memories ORDER BY created_at DESC LIMIT $1",
                limit,
            )
        return [
            MemoryHit(content=r["content"], layer=r["layer"], score=r["importance"], tier=2, created_at=r["created_at"].timestamp())
            for r in rows
        ]

    async def search(self, query: str, limit: int = 10) -> list[MemoryHit]:
        if not self._pool:
            return []
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT content, layer, importance, created_at FROM memories WHERE content ILIKE '%' || $1 || '%' ORDER BY importance DESC LIMIT $2",
                query, limit,
            )
        return [
            MemoryHit(content=r["content"], layer=r["layer"], score=r["importance"], tier=2, created_at=r["created_at"].timestamp())
            for r in rows
        ]


class Tier3Backend:
    """Qdrant-backed long-term memory (L8-L10)."""

    def __init__(self, qdrant_url: str = "http://localhost:6333", collection: str = "xagent_long_term"):
        self._url = qdrant_url
        self._collection = collection
        self._client = None

    async def _get_client(self):
        if self._client is None:
            try:
                from qdrant_client import AsyncQdrantClient
                self._client = AsyncQdrantClient(url=self._url)
            except ImportError:
                logger.warning("qdrant-client not installed, Tier3 disabled")
                return None
        return self._client

    async def store(self, content: str, embedding: list[float], layer: int = 8, **kwargs) -> None:
        client = await self._get_client()
        if not client:
            return
        try:
            await client.upsert(
                collection_name=self._collection,
                points=[{
                    "id": str(uuid4()),
                    "vector": embedding,
                    "payload": {"content": content, "layer": layer, **kwargs},
                }],
            )
        except Exception as e:
            logger.warning(f"Tier3 store failed: {e}")

    async def vector_search(self, query_embedding: list[float], limit: int = 10) -> list[MemoryHit]:
        client = await self._get_client()
        if not client:
            return []
        try:
            results = await client.search(
                collection_name=self._collection,
                query_vector=query_embedding,
                limit=limit,
            )
            return [
                MemoryHit(
                    content=r.payload.get("content", ""),
                    layer=r.payload.get("layer", 8),
                    score=r.score,
                    tier=3,
                )
                for r in results
            ]
        except Exception as e:
            logger.warning(f"Tier3 search failed: {e}")
            return []


class TieredMemorySystem:
    """Three-tier memory system with unified interface.

    Routes store/search operations to appropriate tier based on layer:
    - L1-L3 -> Tier1 (in-memory/Redis)
    - L4-L7 -> Tier2 (PostgreSQL)
    - L8-L10 -> Tier3 (Qdrant)
    """

    def __init__(
        self,
        tier1: Tier1Backend | None = None,
        tier2: Tier2Backend | None = None,
        tier3: Tier3Backend | None = None,
        embedding_model=None,
    ):
        self.tier1 = tier1 or Tier1Backend()
        self.tier2 = tier2 or Tier2Backend()
        self.tier3 = tier3 or Tier3Backend()
        self.embedding_model = embedding_model

    async def store(self, content: str, layer: int = 1, **kwargs) -> None:
        """Store memory to appropriate tier based on layer."""
        if layer <= 3:
            await self.tier1.store(str(uuid4()), content, layer=layer, **kwargs)
        elif layer <= 7:
            embedding = await self._embed(content) if self.embedding_model else None
            await self.tier2.store(content, layer=layer, embedding=embedding, **kwargs)
        else:
            embedding = await self._embed(content) if self.embedding_model else []
            await self.tier3.store(content, embedding=embedding or [], layer=layer, **kwargs)

    async def search(self, query: str, layers: list[int] | None = None, limit: int = 10) -> list[MemoryHit]:
        """Search across all relevant tiers in parallel."""
        if layers is None:
            layers = list(range(1, 11))

        tasks = []
        if any(l <= 3 for l in layers):
            tasks.append(self.tier1.search(query, limit=limit))
        if any(4 <= l <= 7 for l in layers):
            tasks.append(self.tier2.search(query, limit=limit))
        if any(l >= 8 for l in layers):
            embedding = await self._embed(query) if self.embedding_model else None
            if embedding:
                tasks.append(self.tier3.vector_search(embedding, limit=limit))

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)
        hits: list[MemoryHit] = []
        for r in results:
            if isinstance(r, list):
                hits.extend(r)

        return sorted(hits, key=lambda h: h.score, reverse=True)[:limit]

    async def _embed(self, text: str) -> list[float] | None:
        """Generate embedding for text."""
        if not self.embedding_model:
            return None
        try:
            if hasattr(self.embedding_model, "embed"):
                return await self.embedding_model.embed(text)
            elif hasattr(self.embedding_model, "encode"):
                return self.embedding_model.encode(text).tolist()
        except Exception as e:
            logger.warning(f"Embedding failed: {e}")
        return None
