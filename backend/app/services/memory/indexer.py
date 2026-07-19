from __future__ import annotations

from backend.app.services.memory.qdrant_client import VectorRecord, vector_client
from backend.app.services.observability.langfuse_client import langfuse_client


class MemoryIndexer:
    def index(self, *, tenant_id: str, text: str, embedding: list[float] | None = None, **payload):
        record = vector_client.upsert(
            "memory",
            tenant_id=tenant_id,
            text=text,
            embedding=embedding,
            payload=payload,
        )
        langfuse_client.log(
            "memory.indexed",
            tenant_id=tenant_id,
            record_id=record.id,
            text=text,
            **payload,
        )
        return record


memory_indexer = MemoryIndexer()
