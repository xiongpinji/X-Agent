"""
Memory management engine - handles memory storage and retrieval.

Extracted from AgentLoop to reduce coupling and improve testability.
Responsibilities:
  - Store execution memories
  - Retrieve relevant context
  - Search memory with scoring
  - Manage memory layers
"""

from typing import Any

from backend.app.core.contracts import RunContext
from backend.app.core.memory import MemorySystem


class MemoryManager:
    """Manages agent memory operations."""

    def __init__(self, memory_system: MemorySystem):
        self.memory = memory_system
        self._retrieval_cache: dict[str, list[dict[str, Any]]] = {}

    async def store(
        self,
        context: RunContext,
        content: str,
        layer: int = 3,
        importance: float = 0.5,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> str:
        """
        Store memory in the system.

        Args:
            context: Execution context
            content: Memory content
            layer: Memory layer (1-5)
            importance: Importance score (0-1)
            tags: Memory tags
            metadata: Additional metadata
            session_id: Session ID for grouping

        Returns:
            Memory ID
        """
        tags = tags or []
        metadata = metadata or {}

        memory_id = await self.memory.store(
            context,
            content=content,
            layer=layer,
            importance=importance,
            tags=tags,
            metadata=metadata,
            session_id=session_id,
        )

        # Invalidate cache
        self._retrieval_cache.clear()

        return memory_id

    async def retrieve(
        self,
        context: RunContext,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Retrieve memories matching query.

        Args:
            context: Execution context
            query: Search query
            limit: Maximum results

        Returns:
            List of matching memories
        """
        cache_key = f"{query}:{limit}"
        if cache_key in self._retrieval_cache:
            return self._retrieval_cache[cache_key]

        if hasattr(self.memory, "retrieve"):
            results = await self.memory.retrieve(context, query=query, limit=limit)
        else:
            results = await self.memory.search(context, query=query, top_k=limit) if hasattr(self.memory, "search") else []

        self._retrieval_cache[cache_key] = results
        return results

    async def search(
        self,
        context: RunContext,
        query: str,
        layers: list[int] | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Search memories with scoring.

        Args:
            context: Execution context
            query: Search query
            layers: Memory layers to search
            top_k: Top K results

        Returns:
            List of scored results
        """
        layers = layers or [3, 4, 5]

        if hasattr(self.memory, "search_with_scores"):
            hits = await self.memory.search_with_scores(
                context,
                query=query,
                layers=layers,
                top_k=top_k,
            )
            return [
                {
                    "id": hit.item.id,
                    "content": hit.item.content[:300],
                    "layer": hit.item.layer,
                    "score": hit.score,
                    "tags": hit.item.tags,
                }
                for hit in hits
            ]

        # Fallback to basic search
        results = await self.retrieve(context, query, limit=top_k)
        return results

    async def add_revision(
        self,
        memory_id: str,
        actor_agent_id: str,
        summary: str,
    ) -> None:
        """
        Add revision to existing memory.

        Args:
            memory_id: Memory ID to revise
            actor_agent_id: Agent making revision
            summary: Revision summary
        """
        if hasattr(self.memory, "add_revision"):
            self.memory.add_revision(
                memory_id,
                actor_agent_id=actor_agent_id,
                summary=summary,
            )

    async def append_session_summary(
        self,
        session_id: str,
        summary: str,
    ) -> None:
        """
        Append summary to session.

        Args:
            session_id: Session ID
            summary: Summary to append
        """
        if hasattr(self.memory, "append_session_summary"):
            self.memory.append_session_summary(session_id, summary)

    def get_memory_count(self) -> int:
        """Get total memory count."""
        if hasattr(self.memory, "count"):
            return self.memory.count()
        return 0

    def get_memory_snapshot(self) -> dict[str, Any]:
        """Get memory system snapshot."""
        if hasattr(self.memory, "snapshot"):
            return self.memory.snapshot()
        return {}

    def clear_cache(self) -> None:
        """Clear retrieval cache."""
        self._retrieval_cache.clear()
