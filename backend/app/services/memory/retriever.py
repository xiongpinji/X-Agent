from __future__ import annotations

from backend.app.services.memory.qdrant_client import VectorRecord, vector_client
from backend.app.services.observability.langfuse_client import langfuse_client


class MemoryRetriever:
    def search(self, *, tenant_id: str | None = None, query: str, top_k: int = 5) -> list[VectorRecord]:
        results = vector_client.search("memory", tenant_id=tenant_id, query=query, top_k=top_k)
        langfuse_client.log(
            "memory.search",
            tenant_id=tenant_id,
            query=query,
            top_k=top_k,
            hit_count=len(results),
        )
        return results


memory_retriever = MemoryRetriever()
