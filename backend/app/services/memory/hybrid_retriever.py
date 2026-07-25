"""
Hybrid memory retrieval module for X-Agent.

Implements hybrid search combining vector similarity and keyword matching,
with result reranking for improved retrieval quality.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Represents a single retrieval result."""

    memory_id: str
    content: str
    vector_score: float
    keyword_score: float
    combined_score: float
    rank: int
    metadata: dict


class HybridRetriever:
    """
    Implements hybrid retrieval combining vector and keyword search.

    Uses both semantic similarity (vector) and lexical matching (keyword)
    to improve retrieval quality and relevance.
    """

    def __init__(
        self,
        vector_weight: float = 0.6,
        keyword_weight: float = 0.4,
        top_k: int = 10,
        enable_reranking: bool = True,
    ):
        """
        Initialize the hybrid retriever.

        Args:
            vector_weight: Weight for vector similarity scores
            keyword_weight: Weight for keyword matching scores
            top_k: Default number of top results to return
            enable_reranking: Whether to apply reranking to results
        """
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self.top_k = top_k
        self.enable_reranking = enable_reranking
        self.logger = logger

    def search(
        self,
        query: str,
        memories: list[dict],
        embeddings: np.ndarray | None = None,
        top_k: int | None = None,
        use_hybrid: bool = True,
    ) -> list[RetrievalResult]:
        """
        Perform hybrid search on memories.

        Args:
            query: Search query string
            memories: List of memory dictionaries with 'id' and 'content'
            embeddings: Optional pre-computed embeddings for memories
            top_k: Number of top results to return
            use_hybrid: Whether to use hybrid search or vector-only

        Returns:
            List of RetrievalResult objects sorted by combined score
        """
        if not memories:
            return []

        top_k = top_k or self.top_k

        if use_hybrid:
            results = self._hybrid_search(query, memories, embeddings, top_k)
        else:
            results = self._vector_search(query, memories, embeddings, top_k)

        if self.enable_reranking:
            results = self._rerank_results(results, query)

        return results[:top_k]

    def _hybrid_search(
        self,
        query: str,
        memories: list[dict],
        embeddings: np.ndarray | None,
        top_k: int,
    ) -> list[RetrievalResult]:
        """Perform hybrid search combining vector and keyword scores."""
        results = []

        # Get vector scores
        vector_scores = self._compute_vector_scores(query, embeddings) if embeddings is not None else None

        # Get keyword scores
        keyword_scores = self._compute_keyword_scores(query, memories)

        # Combine scores
        for i, memory in enumerate(memories):
            vector_score = vector_scores[i] if vector_scores is not None else 0.0
            keyword_score = keyword_scores[i]

            combined_score = (
                self.vector_weight * vector_score +
                self.keyword_weight * keyword_score
            )

            result = RetrievalResult(
                memory_id=memory.get("id", f"memory_{i}"),
                content=memory.get("content", ""),
                vector_score=vector_score,
                keyword_score=keyword_score,
                combined_score=combined_score,
                rank=0,
                metadata=memory.get("metadata", {}),
            )
            results.append(result)

        # Sort by combined score
        results.sort(key=lambda x: x.combined_score, reverse=True)

        # Update ranks
        for i, result in enumerate(results):
            result.rank = i + 1

        return results

    def _vector_search(
        self,
        query: str,
        memories: list[dict],
        embeddings: np.ndarray | None,
        top_k: int,
    ) -> list[RetrievalResult]:
        """Perform vector-only search."""
        if embeddings is None:
            self.logger.warning("No embeddings available for vector search")
            return []

        results = []
        vector_scores = self._compute_vector_scores(query, embeddings)

        for i, memory in enumerate(memories):
            result = RetrievalResult(
                memory_id=memory.get("id", f"memory_{i}"),
                content=memory.get("content", ""),
                vector_score=vector_scores[i],
                keyword_score=0.0,
                combined_score=vector_scores[i],
                rank=0,
                metadata=memory.get("metadata", {}),
            )
            results.append(result)

        # Sort by vector score
        results.sort(key=lambda x: x.vector_score, reverse=True)

        # Update ranks
        for i, result in enumerate(results):
            result.rank = i + 1

        return results

    def _compute_vector_scores(
        self,
        query: str,
        embeddings: np.ndarray,
    ) -> np.ndarray:
        """Compute vector similarity scores."""
        try:
            from sklearn.metrics.pairwise import cosine_similarity

            # Create query embedding (simplified)
            query_embedding = self._create_query_embedding(query)

            # Compute cosine similarity
            similarities = cosine_similarity(
                [query_embedding],
                embeddings
            )[0]

            # Normalize to 0-1 range
            scores = (similarities + 1) / 2

            return scores
        except Exception as e:
            self.logger.error(f"Error computing vector scores: {e}")
            return np.zeros(len(embeddings))

    def _compute_keyword_scores(
        self,
        query: str,
        memories: list[dict],
    ) -> list[float]:
        """Compute keyword matching scores."""
        query_terms = set(query.lower().split())
        scores = []

        for memory in memories:
            content = memory.get("content", "").lower()
            content_terms = set(content.split())

            # Jaccard similarity
            intersection = len(query_terms & content_terms)
            union = len(query_terms | content_terms)

            score = intersection / union if union > 0 else 0.0
            scores.append(score)

        return scores

    def _create_query_embedding(self, query: str) -> np.ndarray:
        """Create embedding for query (simplified)."""
        words = query.lower().split()
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1

        # Create fixed-size embedding
        embedding = np.zeros(100)
        for i, (_word, freq) in enumerate(sorted(word_freq.items())[:100]):
            embedding[i] = freq / len(words) if words else 0

        return embedding

    def _rerank_results(
        self,
        results: list[RetrievalResult],
        query: str,
    ) -> list[RetrievalResult]:
        """Rerank results using additional signals."""
        # Apply diversity penalty to similar results
        reranked = []
        seen_content_hashes = set()

        for result in results:
            content_hash = hash(result.content[:100])

            if content_hash not in seen_content_hashes:
                reranked.append(result)
                seen_content_hashes.add(content_hash)
            else:
                # Apply diversity penalty
                result.combined_score *= 0.7

        # Re-sort after reranking
        reranked.sort(key=lambda x: x.combined_score, reverse=True)

        # Update ranks
        for i, result in enumerate(reranked):
            result.rank = i + 1

        return reranked

    def batch_search(
        self,
        queries: list[str],
        memories: list[dict],
        embeddings: np.ndarray | None = None,
        top_k: int | None = None,
    ) -> list[list[RetrievalResult]]:
        """
        Perform batch search for multiple queries.

        Args:
            queries: List of search queries
            memories: List of memory dictionaries
            embeddings: Optional pre-computed embeddings
            top_k: Number of top results per query

        Returns:
            List of result lists, one per query
        """
        results = []
        for query in queries:
            query_results = self.search(query, memories, embeddings, top_k)
            results.append(query_results)

        return results

    def get_retrieval_stats(self, results: list[RetrievalResult]) -> dict:
        """Get statistics from retrieval results."""
        if not results:
            return {
                "total_results": 0,
                "avg_combined_score": 0.0,
                "avg_vector_score": 0.0,
                "avg_keyword_score": 0.0,
            }

        combined_scores = [r.combined_score for r in results]
        vector_scores = [r.vector_score for r in results]
        keyword_scores = [r.keyword_score for r in results]

        return {
            "total_results": len(results),
            "avg_combined_score": np.mean(combined_scores),
            "avg_vector_score": np.mean(vector_scores),
            "avg_keyword_score": np.mean(keyword_scores),
            "max_combined_score": np.max(combined_scores),
            "min_combined_score": np.min(combined_scores),
        }


# Global instance
hybrid_retriever = HybridRetriever()
