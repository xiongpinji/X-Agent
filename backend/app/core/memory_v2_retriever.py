"""Memory V2 - Hybrid Retriever (Mixed Retrieval Strategy)

Combines vector, keyword, and graph-based retrieval for optimal results.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Single retrieval result with scoring breakdown."""

    memory_id: str
    content: str
    vector_score: float = 0.0
    keyword_score: float = 0.0
    graph_score: float = 0.0
    combined_score: float = 0.0
    rank: int = 0
    metadata: dict = None


class HybridRetrieverConfig:
    """Configuration for hybrid retriever."""

    def __init__(
        self,
        vector_weight: float = 0.5,
        keyword_weight: float = 0.3,
        graph_weight: float = 0.2,
        top_k: int = 10,
        enable_reranking: bool = True,
        enable_diversity: bool = True,
    ):
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self.graph_weight = graph_weight
        self.top_k = top_k
        self.enable_reranking = enable_reranking
        self.enable_diversity = enable_diversity

        # Validate weights sum to 1.0
        total = vector_weight + keyword_weight + graph_weight
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {total}")


class HybridRetriever:
    """Hybrid retrieval combining vector, keyword, and graph search."""

    def __init__(
        self,
        config: HybridRetrieverConfig | None = None,
        vector_store: Any = None,  # Qdrant client
        keyword_store: Any = None,  # PostgreSQL connection
        graph_store: Any = None,  # Neo4j driver
    ):
        self.config = config or HybridRetrieverConfig()
        self.vector_store = vector_store
        self.keyword_store = keyword_store
        self.graph_store = graph_store

    async def search(
        self,
        query: str,
        tenant_id: str,
        top_k: int | None = None,
        use_vector: bool = True,
        use_keyword: bool = True,
        use_graph: bool = True,
    ) -> list[RetrievalResult]:
        """Perform hybrid search."""

        top_k = top_k or self.config.top_k

        # Parallel retrieval from all sources
        tasks = []

        if use_vector and self.vector_store:
            tasks.append(self._vector_search(query, tenant_id, top_k))

        if use_keyword and self.keyword_store:
            tasks.append(self._keyword_search(query, tenant_id, top_k))

        if use_graph and self.graph_store:
            tasks.append(self._graph_search(query, tenant_id, top_k))

        # Execute in parallel
        results_by_source = await asyncio.gather(*tasks, return_exceptions=True)

        # Combine results
        combined = await self._combine_results(results_by_source, top_k)

        # Rerank if enabled
        if self.config.enable_reranking:
            combined = await self._rerank_results(combined, query)

        # Apply diversity if enabled
        if self.config.enable_diversity:
            combined = self._apply_diversity(combined, top_k)

        return combined[:top_k]

    async def _vector_search(
        self,
        query: str,
        tenant_id: str,
        top_k: int,
    ) -> list[RetrievalResult]:
        """Vector-based semantic search."""

        if not self.vector_store:
            return []

        try:
            # This would call Qdrant in real implementation
            # For now, return empty list
            logger.debug(f"Vector search for: {query}")
            return []
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    async def _keyword_search(
        self,
        query: str,
        tenant_id: str,
        top_k: int,
    ) -> list[RetrievalResult]:
        """Keyword-based lexical search."""

        if not self.keyword_store:
            return []

        try:
            # This would call PostgreSQL in real implementation
            # For now, return empty list
            logger.debug(f"Keyword search for: {query}")
            return []
        except Exception as e:
            logger.error(f"Keyword search failed: {e}")
            return []

    async def _graph_search(
        self,
        query: str,
        tenant_id: str,
        top_k: int,
    ) -> list[RetrievalResult]:
        """Graph-based relationship search."""

        if not self.graph_store:
            return []

        try:
            # This would call Neo4j in real implementation
            # For now, return empty list
            logger.debug(f"Graph search for: {query}")
            return []
        except Exception as e:
            logger.error(f"Graph search failed: {e}")
            return []

    async def _combine_results(
        self,
        results_by_source: list[list[RetrievalResult]],
        top_k: int,
    ) -> list[RetrievalResult]:
        """Combine results from multiple sources."""

        # Normalize scores and combine
        combined: dict[str, RetrievalResult] = {}

        for source_idx, results in enumerate(results_by_source):
            if isinstance(results, Exception):
                continue

            for result in results:
                if result.memory_id not in combined:
                    combined[result.memory_id] = RetrievalResult(
                        memory_id=result.memory_id,
                        content=result.content,
                        metadata=result.metadata or {},
                    )

                # Add weighted score based on source
                if source_idx == 0:  # Vector
                    combined[result.memory_id].vector_score = result.combined_score
                elif source_idx == 1:  # Keyword
                    combined[result.memory_id].keyword_score = result.combined_score
                elif source_idx == 2:  # Graph
                    combined[result.memory_id].graph_score = result.combined_score

        # Calculate combined scores
        for result in combined.values():
            result.combined_score = (
                self.config.vector_weight * result.vector_score +
                self.config.keyword_weight * result.keyword_score +
                self.config.graph_weight * result.graph_score
            )

        # Sort by combined score
        sorted_results = sorted(
            combined.values(),
            key=lambda r: r.combined_score,
            reverse=True,
        )

        # Update ranks
        for i, result in enumerate(sorted_results):
            result.rank = i + 1

        return sorted_results

    async def _rerank_results(
        self,
        results: list[RetrievalResult],
        query: str,
    ) -> list[RetrievalResult]:
        """Rerank results using cross-encoder or other methods."""

        # Simple reranking: boost results with query terms in content
        query_terms = set(query.lower().split())

        for result in results:
            content_terms = set(result.content.lower().split())
            term_overlap = len(query_terms & content_terms) / len(query_terms)
            result.combined_score *= (1.0 + term_overlap * 0.2)

        # Re-sort
        results.sort(key=lambda r: r.combined_score, reverse=True)

        # Update ranks
        for i, result in enumerate(results):
            result.rank = i + 1

        return results

    def _apply_diversity(
        self,
        results: list[RetrievalResult],
        top_k: int,
    ) -> list[RetrievalResult]:
        """Apply diversity to results to avoid redundancy."""

        if not results:
            return results

        diverse_results = [results[0]]
        used_terms = set(results[0].content.lower().split())

        for result in results[1:]:
            if len(diverse_results) >= top_k:
                break

            content_terms = set(result.content.lower().split())
            overlap = len(used_terms & content_terms) / len(used_terms)

            # Add if diversity is sufficient
            if overlap < 0.7:
                diverse_results.append(result)
                used_terms.update(content_terms)

        return diverse_results


# Global instance
hybrid_retriever = HybridRetriever()
