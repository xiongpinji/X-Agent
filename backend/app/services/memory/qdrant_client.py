from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels
except ImportError:  # pragma: no cover - optional runtime dependency
    QdrantClient = None  # type: ignore[assignment]
    qmodels = None  # type: ignore[assignment]


@dataclass(slots=True)
class VectorRecord:
    id: str
    tenant_id: str
    text: str
    embedding: list[float] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)


class QdrantVectorClient:
    """Qdrant-backed vector client with deterministic in-memory fallback."""

    def __init__(self, url: str | None = None, api_key: str | None = None) -> None:
        self._collections: dict[str, list[VectorRecord]] = {}
        self._client = (
            QdrantClient(url=url, api_key=api_key, check_compatibility=False)
            if QdrantClient is not None and url
            else None
        )

    @property
    def has_real_client(self) -> bool:
        return self._client is not None

    def ensure_collection(self, collection: str, vector_size: int = 1536) -> bool:
        if self._client is None or qmodels is None:
            return False
        existing = [item.name for item in self._client.get_collections().collections]
        if collection in existing:
            return True
        self._client.create_collection(
            collection_name=collection,
            vectors_config=qmodels.VectorParams(size=vector_size, distance=qmodels.Distance.COSINE),
        )
        return True

    def get_collection_names(self) -> list[str]:
        if self._client is None:
            return list(self._collections.keys())
        return [item.name for item in self._client.get_collections().collections]

    def upsert(
        self,
        collection: str,
        *,
        tenant_id: str,
        text: str,
        embedding: list[float] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> VectorRecord:
        record = VectorRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            text=text,
            embedding=list(embedding or []),
            payload=dict(payload or {}),
        )
        self._collections.setdefault(collection, []).append(record)
        if self._client is not None and qmodels is not None:
            self.ensure_collection(collection, vector_size=len(record.embedding) or 1536)
            self._client.upsert(
                collection_name=collection,
                points=[
                    qmodels.PointStruct(
                        id=record.id,
                        vector=record.embedding or [0.0],
                        payload={
                            "tenant_id": tenant_id,
                            "text": text,
                            **record.payload,
                        },
                    )
                ],
            )
        return record

    def search(
        self,
        collection: str,
        *,
        tenant_id: str | None = None,
        query: str,
        query_embedding: list[float] | None = None,
        top_k: int = 5,
    ) -> list[VectorRecord]:
        if tenant_id is None:
            return []

        # Use real Qdrant vector search when available
        if self._client is not None and qmodels is not None and query_embedding:
            try:
                self.ensure_collection(collection, vector_size=len(query_embedding))
                results = self._client.query_points(
                    collection_name=collection,
                    query=query_embedding,
                    limit=top_k,
                    query_filter=qmodels.Filter(
                        must=[qmodels.FieldCondition(
                            key="tenant_id",
                            match=qmodels.MatchValue(value=tenant_id),
                        )]
                    ),
                    with_payload=True,
                )
                records = []
                for point in results.points:
                    payload = point.payload or {}
                    records.append(VectorRecord(
                        id=str(point.id),
                        tenant_id=tenant_id,
                        text=payload.get("text", ""),
                        payload=payload,
                    ))
                return records
            except Exception:
                pass  # Fall through to keyword search

        # Fallback: keyword-based search on local cache
        items = [
            record
            for record in self._collections.get(collection, [])
            if record.tenant_id == tenant_id
        ]
        query_terms = {term.lower() for term in query.split() if term.strip()}
        items.sort(key=lambda record: self._score(query_terms, record), reverse=True)
        return items[:top_k]

    @staticmethod
    def _score(query_terms: set[str], record: VectorRecord) -> float:
        text_terms = set(record.text.lower().split())
        return float(len(query_terms & text_terms))


from backend.app.settings import get_settings

settings = get_settings()
vector_client = QdrantVectorClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
