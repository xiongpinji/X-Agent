"""Cold memory store using vector database (Qdrant) for semantic search.

Features:
- Semantic search via embeddings
- Batch embedding support
- Similarity threshold filtering
- Metadata-based filtering
- Long-term storage
"""

from __future__ import annotations

from typing import Any

from backend.app.core.hybrid_memory_system import Memory


class ColdMemoryStore:
    """Vector database-backed cold memory storage.

    Integrates with Qdrant for semantic search and long-term memory storage.
    """

    def __init__(
        self,
        qdrant_client: Any | None = None,
        collection_name: str = "memories",
        vector_size: int = 128,
    ) -> None:
        self.qdrant_client = qdrant_client
        self.collection_name = collection_name
        self.vector_size = vector_size
        self._memory_count = 0

        # Initialize collection if client provided
        if self.qdrant_client:
            self._ensure_collection()

    async def store(
        self,
        memory: Memory,
        embedding: list[float],
    ) -> str:
        """Store memory with embedding in vector database.

        Args:
            memory: Memory to store
            embedding: Vector embedding

        Returns:
            Memory ID
        """
        if not self.qdrant_client:
            return memory.id

        try:
            # Prepare payload
            payload = {
                "id": memory.id,
                "content": memory.content,
                "category": memory.category,
                "importance": memory.importance,
                "tier": "cold",
                "tags": memory.tags,
                "created_at": memory.created_at.isoformat(),
                "updated_at": memory.updated_at.isoformat(),
                "accessed_at": memory.accessed_at.isoformat(),
                "access_count": memory.access_count,
                "related_ids": memory.related_ids,
                "metadata": memory.metadata,
            }

            # Upsert point in Qdrant
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=[
                    {
                        "id": self._hash_id(memory.id),
                        "vector": embedding,
                        "payload": payload,
                    }
                ],
            )

            self._memory_count += 1
            return memory.id

        except Exception as e:
            raise RuntimeError(f"Failed to store memory in cold tier: {e}")

    async def search(
        self,
        query_embedding: list[float],
        limit: int = 10,
        similarity_threshold: float = 0.7,
    ) -> list[Memory]:
        """Search memories by embedding similarity.

        Args:
            query_embedding: Query vector
            limit: Maximum results
            similarity_threshold: Minimum similarity score

        Returns:
            List of matching memories
        """
        if not self.qdrant_client:
            return []

        try:
            results = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=limit,
                score_threshold=similarity_threshold,
            )

            memories: list[Memory] = []
            for result in results:
                payload = result.payload
                memory = Memory(
                    id=payload.get("id", ""),
                    content=payload.get("content", ""),
                    category=payload.get("category", "reference"),
                    importance=payload.get("importance", 0.5),
                    tier="cold",
                    tags=payload.get("tags", []),
                    metadata=payload.get("metadata", {}),
                    created_at=self._parse_datetime(payload.get("created_at")),
                    updated_at=self._parse_datetime(payload.get("updated_at")),
                    accessed_at=self._parse_datetime(payload.get("accessed_at")),
                    access_count=payload.get("access_count", 0),
                    related_ids=payload.get("related_ids", []),
                )
                memories.append(memory)

            return memories

        except Exception as e:
            raise RuntimeError(f"Failed to search cold tier: {e}")

    async def search_by_metadata(self, filters: dict) -> list[Memory]:
        """Search memories by metadata filters.

        Args:
            filters: Metadata filter conditions

        Returns:
            List of matching memories
        """
        if not self.qdrant_client:
            return []

        try:
            # Build filter conditions
            conditions = []
            for key, value in filters.items():
                if isinstance(value, dict):
                    # Handle comparison operators like {">": 5}
                    for op, val in value.items():
                        if op == ">":
                            conditions.append(
                                {
                                    "range": {
                                        "gte": val,
                                    }
                                }
                            )
                        elif op == "<":
                            conditions.append(
                                {
                                    "range": {
                                        "lte": val,
                                    }
                                }
                            )
                else:
                    conditions.append(
                        {
                            "key": key,
                            "match": {
                                "value": value,
                            },
                        }
                    )

            # Search with filters
            results = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                limit=100,
            )

            memories: list[Memory] = []
            for point in results[0]:
                payload = point.payload
                memory = Memory(
                    id=payload.get("id", ""),
                    content=payload.get("content", ""),
                    category=payload.get("category", "reference"),
                    importance=payload.get("importance", 0.5),
                    tier="cold",
                    tags=payload.get("tags", []),
                    metadata=payload.get("metadata", {}),
                    created_at=self._parse_datetime(payload.get("created_at")),
                    updated_at=self._parse_datetime(payload.get("updated_at")),
                    accessed_at=self._parse_datetime(payload.get("accessed_at")),
                    access_count=payload.get("access_count", 0),
                    related_ids=payload.get("related_ids", []),
                )
                memories.append(memory)

            return memories

        except Exception as e:
            raise RuntimeError(f"Failed to search by metadata: {e}")

    async def delete(self, memory_id: str) -> bool:
        """Delete memory from vector database.

        Args:
            memory_id: Memory ID to delete

        Returns:
            Success status
        """
        if not self.qdrant_client:
            return False

        try:
            self.qdrant_client.delete(
                collection_name=self.collection_name,
                points_selector={
                    "ids": [self._hash_id(memory_id)],
                },
            )
            self._memory_count = max(0, self._memory_count - 1)
            return True

        except Exception as e:
            raise RuntimeError(f"Failed to delete memory from cold tier: {e}")

    async def count(self) -> int:
        """Get total memory count in cold tier.

        Returns:
            Number of memories
        """
        if not self.qdrant_client:
            return 0

        try:
            collection_info = self.qdrant_client.get_collection(
                collection_name=self.collection_name
            )
            return collection_info.points_count

        except Exception:
            return self._memory_count

    async def batch_store(
        self,
        memories: list[Memory],
        embeddings: list[list[float]],
    ) -> dict[str, str]:
        """Store multiple memories efficiently.

        Args:
            memories: List of memories
            embeddings: List of embeddings

        Returns:
            Dictionary mapping memory IDs to storage IDs
        """
        if not self.qdrant_client or len(memories) != len(embeddings):
            return {}

        try:
            points = []
            for memory, embedding in zip(memories, embeddings, strict=False):
                payload = {
                    "id": memory.id,
                    "content": memory.content,
                    "category": memory.category,
                    "importance": memory.importance,
                    "tier": "cold",
                    "tags": memory.tags,
                    "created_at": memory.created_at.isoformat(),
                    "updated_at": memory.updated_at.isoformat(),
                    "accessed_at": memory.accessed_at.isoformat(),
                    "access_count": memory.access_count,
                    "related_ids": memory.related_ids,
                    "metadata": memory.metadata,
                }

                points.append(
                    {
                        "id": self._hash_id(memory.id),
                        "vector": embedding,
                        "payload": payload,
                    }
                )

            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=points,
            )

            self._memory_count += len(memories)
            return {mem.id: mem.id for mem in memories}

        except Exception as e:
            raise RuntimeError(f"Failed to batch store memories: {e}")

    def _ensure_collection(self) -> None:
        """Ensure Qdrant collection exists."""
        if not self.qdrant_client:
            return

        try:
            self.qdrant_client.get_collection(self.collection_name)
        except Exception:
            # Collection doesn't exist, create it
            try:
                self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config={
                        "size": self.vector_size,
                        "distance": "Cosine",
                    },
                )
            except Exception as e:
                raise RuntimeError(f"Failed to create Qdrant collection: {e}")

    @staticmethod
    def _hash_id(memory_id: str) -> int:
        """Convert memory ID to integer for Qdrant.

        Args:
            memory_id: String memory ID

        Returns:
            Integer ID
        """
        return int(hash(memory_id) & 0x7FFFFFFF)

    @staticmethod
    def _parse_datetime(datetime_str: str | None) -> Any:
        """Parse ISO datetime string.

        Args:
            datetime_str: ISO format datetime string

        Returns:
            Datetime object or current time
        """
        if not datetime_str:
            from datetime import UTC, datetime
            return datetime.now(UTC)

        try:
            from datetime import datetime
            return datetime.fromisoformat(datetime_str)
        except (ValueError, TypeError):
            from datetime import UTC, datetime
            return datetime.now(UTC)
