"""
Context optimizer for efficient context management.

This module provides utilities for compressing, prioritizing, and retrieving
relevant context to maximize LLM effectiveness within token limits.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


@dataclass
class ContextItem:
    """A single context item."""
    content: str
    priority: float = 0.5  # 0-1, higher = more important
    relevance: float = 0.5  # 0-1, higher = more relevant
    token_count: int = 0
    category: str = "general"
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        """Post-initialization processing."""
        if self.metadata is None:
            self.metadata = {}
        # Estimate token count (rough approximation: 1 token per 4 characters)
        self.token_count = len(self.content) // 4


@dataclass
class CompressionResult:
    """Result of context compression."""
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    compressed_content: str
    removed_items: List[str]


class ContextOptimizer:
    """Optimizes context for efficient LLM usage."""

    def __init__(self, max_context_tokens: int = 8000):
        """Initialize context optimizer.

        Args:
            max_context_tokens: Maximum context tokens allowed.
        """
        self.max_context_tokens = max_context_tokens
        self.compression_history: List[CompressionResult] = []

    def compress_context(
        self,
        context: str,
        max_tokens: int,
        compression_method: str = "summarization",
    ) -> CompressionResult:
        """Compress context to fit within token limit.

        Args:
            context: The context to compress.
            max_tokens: Maximum tokens allowed.
            compression_method: Method to use (summarization, extraction, etc).

        Returns:
            CompressionResult with compressed context.
        """
        logger.info(f"Compressing context to {max_tokens} tokens")

        original_tokens = len(context) // 4  # Rough estimate

        if original_tokens <= max_tokens:
            return CompressionResult(
                original_tokens=original_tokens,
                compressed_tokens=original_tokens,
                compression_ratio=1.0,
                compressed_content=context,
                removed_items=[],
            )

        # Apply compression method
        if compression_method == "summarization":
            compressed = self._compress_by_summarization(context, max_tokens)
        elif compression_method == "extraction":
            compressed = self._compress_by_extraction(context, max_tokens)
        elif compression_method == "abstraction":
            compressed = self._compress_by_abstraction(context, max_tokens)
        else:
            compressed = self._compress_by_truncation(context, max_tokens)

        compressed_tokens = len(compressed) // 4
        compression_ratio = compressed_tokens / original_tokens if original_tokens > 0 else 1.0

        result = CompressionResult(
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            compression_ratio=compression_ratio,
            compressed_content=compressed,
            removed_items=[],
        )

        self.compression_history.append(result)
        logger.info(f"Compression ratio: {compression_ratio:.2%}")

        return result

    def prioritize_context(
        self,
        contexts: List[ContextItem],
        max_tokens: int,
    ) -> List[ContextItem]:
        """Prioritize context items by importance and relevance.

        Args:
            contexts: List of context items.
            max_tokens: Maximum tokens allowed.

        Returns:
            Prioritized list of context items.
        """
        logger.info(f"Prioritizing {len(contexts)} context items")

        # Calculate priority scores
        scored_contexts = []
        for ctx in contexts:
            # Combined score: priority * relevance
            score = ctx.priority * ctx.relevance
            scored_contexts.append((ctx, score))

        # Sort by score (descending)
        scored_contexts.sort(key=lambda x: x[1], reverse=True)

        # Select contexts that fit within token limit
        selected = []
        total_tokens = 0

        for ctx, score in scored_contexts:
            if total_tokens + ctx.token_count <= max_tokens:
                selected.append(ctx)
                total_tokens += ctx.token_count
            else:
                logger.debug(f"Skipped context item (token limit): {ctx.category}")

        logger.info(f"Selected {len(selected)} context items ({total_tokens} tokens)")

        return selected

    def retrieve_relevant(
        self,
        query: str,
        contexts: List[ContextItem],
        top_k: int = 5,
    ) -> List[ContextItem]:
        """Retrieve most relevant context items for a query.

        Args:
            query: The query.
            contexts: List of context items.
            top_k: Number of top items to return.

        Returns:
            List of relevant context items.
        """
        logger.info(f"Retrieving top {top_k} relevant contexts for query")

        # Calculate relevance scores
        scored_contexts = []
        for ctx in contexts:
            relevance = self._calculate_relevance(query, ctx.content)
            scored_contexts.append((ctx, relevance))

        # Sort by relevance (descending)
        scored_contexts.sort(key=lambda x: x[1], reverse=True)

        # Return top K
        relevant = [ctx for ctx, _ in scored_contexts[:top_k]]

        logger.info(f"Retrieved {len(relevant)} relevant contexts")

        return relevant

    def build_optimized_context(
        self,
        primary_context: str,
        supporting_contexts: List[ContextItem],
        max_tokens: int,
        include_metadata: bool = False,
    ) -> str:
        """Build optimized context combining primary and supporting contexts.

        Args:
            primary_context: The primary context (always included).
            supporting_contexts: Supporting context items.
            max_tokens: Maximum tokens allowed.
            include_metadata: Whether to include metadata.

        Returns:
            Optimized context string.
        """
        logger.info("Building optimized context")

        # Start with primary context
        primary_tokens = len(primary_context) // 4
        remaining_tokens = max_tokens - primary_tokens

        if remaining_tokens <= 0:
            logger.warning("Primary context exceeds token limit")
            return primary_context

        # Add supporting contexts
        optimized_parts = [primary_context]

        for ctx in supporting_contexts:
            if ctx.token_count <= remaining_tokens:
                optimized_parts.append(f"\n[{ctx.category}]\n{ctx.content}")
                remaining_tokens -= ctx.token_count
            else:
                logger.debug(f"Skipped context item (insufficient tokens): {ctx.category}")

        optimized_context = "".join(optimized_parts)

        logger.info(f"Built optimized context ({len(optimized_context) // 4} tokens)")

        return optimized_context

    def extract_key_information(
        self,
        context: str,
        num_key_points: int = 5,
    ) -> List[str]:
        """Extract key information from context.

        Args:
            context: The context.
            num_key_points: Number of key points to extract.

        Returns:
            List of key points.
        """
        logger.info(f"Extracting {num_key_points} key points")

        # Split into sentences
        sentences = context.split(".")
        sentences = [s.strip() for s in sentences if s.strip()]

        # Score sentences by importance
        scored_sentences = []
        for i, sentence in enumerate(sentences):
            # Simple scoring: length, position, keyword presence
            score = (
                len(sentence.split()) / 20 +  # Longer sentences often more important
                (1 - i / len(sentences)) * 0.3 +  # Earlier sentences weighted higher
                self._keyword_score(sentence) * 0.3
            )
            scored_sentences.append((sentence, score))

        # Sort by score
        scored_sentences.sort(key=lambda x: x[1], reverse=True)

        # Return top key points
        key_points = [s for s, _ in scored_sentences[:num_key_points]]

        logger.info(f"Extracted {len(key_points)} key points")

        return key_points

    def create_context_summary(
        self,
        context: str,
        summary_length: int = 100,
    ) -> str:
        """Create a summary of context.

        Args:
            context: The context to summarize.
            summary_length: Target summary length in words.

        Returns:
            Summary of context.
        """
        logger.info(f"Creating context summary ({summary_length} words)")

        # Extract key points
        key_points = self.extract_key_information(context, num_key_points=5)

        # Combine into summary
        summary = " ".join(key_points)

        # Truncate to target length
        words = summary.split()
        if len(words) > summary_length:
            summary = " ".join(words[:summary_length]) + "..."

        logger.info(f"Created summary ({len(summary.split())} words)")

        return summary

    def analyze_context_quality(self, context: str) -> Dict[str, Any]:
        """Analyze quality of context.

        Args:
            context: The context to analyze.

        Returns:
            Quality metrics.
        """
        logger.info("Analyzing context quality")

        # Calculate metrics
        lines = context.split("\n")
        sentences = context.split(".")
        words = context.split()

        metrics = {
            "total_characters": len(context),
            "total_tokens": len(context) // 4,
            "total_lines": len(lines),
            "total_sentences": len(sentences),
            "total_words": len(words),
            "average_line_length": len(context) / len(lines) if lines else 0,
            "average_sentence_length": len(words) / len(sentences) if sentences else 0,
            "readability_score": self._calculate_readability(context),
            "information_density": self._calculate_information_density(context),
        }

        logger.info(f"Context quality: {metrics['readability_score']:.2f}/10")

        return metrics

    def optimize_for_task(
        self,
        context: str,
        task_type: str,
        max_tokens: int,
    ) -> str:
        """Optimize context for a specific task type.

        Args:
            context: The context.
            task_type: Type of task (reasoning, coding, analysis, etc).
            max_tokens: Maximum tokens allowed.

        Returns:
            Optimized context for the task.
        """
        logger.info(f"Optimizing context for task type: {task_type}")

        # Task-specific optimization
        if task_type == "reasoning":
            # For reasoning, keep logical flow and key insights
            optimized = self._optimize_for_reasoning(context, max_tokens)
        elif task_type == "coding":
            # For coding, keep code examples and technical details
            optimized = self._optimize_for_coding(context, max_tokens)
        elif task_type == "analysis":
            # For analysis, keep data and statistics
            optimized = self._optimize_for_analysis(context, max_tokens)
        elif task_type == "generation":
            # For generation, keep examples and patterns
            optimized = self._optimize_for_generation(context, max_tokens)
        else:
            # Default: general optimization
            optimized = self._compress_by_extraction(context, max_tokens)

        logger.info(f"Optimized context for {task_type}")

        return optimized

    # Helper methods

    def _compress_by_summarization(self, context: str, max_tokens: int) -> str:
        """Compress by creating summary.

        Args:
            context: The context.
            max_tokens: Maximum tokens.

        Returns:
            Compressed context.
        """
        # Extract key points and create summary
        key_points = self.extract_key_information(context, num_key_points=5)
        summary = " ".join(key_points)

        # Truncate if needed
        while len(summary) // 4 > max_tokens:
            key_points = key_points[:-1]
            summary = " ".join(key_points)

        return summary

    def _compress_by_extraction(self, context: str, max_tokens: int) -> str:
        """Compress by extracting important parts.

        Args:
            context: The context.
            max_tokens: Maximum tokens.

        Returns:
            Compressed context.
        """
        # Extract sentences with high importance scores
        sentences = context.split(".")
        sentences = [s.strip() for s in sentences if s.strip()]

        scored_sentences = []
        for sentence in sentences:
            score = self._keyword_score(sentence)
            scored_sentences.append((sentence, score))

        # Sort by score
        scored_sentences.sort(key=lambda x: x[1], reverse=True)

        # Select sentences that fit
        selected = []
        total_tokens = 0

        for sentence, _ in scored_sentences:
            tokens = len(sentence) // 4
            if total_tokens + tokens <= max_tokens:
                selected.append(sentence)
                total_tokens += tokens

        return ". ".join(selected) + "."

    def _compress_by_abstraction(self, context: str, max_tokens: int) -> str:
        """Compress by abstracting details.

        Args:
            context: The context.
            max_tokens: Maximum tokens.

        Returns:
            Compressed context.
        """
        # Replace detailed examples with abstractions
        abstracted = context

        # Simple abstraction: replace long lists with summaries
        lines = abstracted.split("\n")
        abstracted_lines = []

        for line in lines:
            if len(line) > 100:
                # Summarize long lines
                words = line.split()
                if len(words) > 20:
                    abstracted_lines.append(" ".join(words[:10]) + "... [details omitted]")
                else:
                    abstracted_lines.append(line)
            else:
                abstracted_lines.append(line)

        abstracted = "\n".join(abstracted_lines)

        # Truncate if still too long
        while len(abstracted) // 4 > max_tokens:
            abstracted = abstracted[:len(abstracted) // 2]

        return abstracted

    def _compress_by_truncation(self, context: str, max_tokens: int) -> str:
        """Compress by simple truncation.

        Args:
            context: The context.
            max_tokens: Maximum tokens.

        Returns:
            Compressed context.
        """
        max_chars = max_tokens * 4
        if len(context) > max_chars:
            return context[:max_chars] + "... [truncated]"
        return context

    def _calculate_relevance(self, query: str, context: str) -> float:
        """Calculate relevance of context to query.

        Args:
            query: The query.
            context: The context.

        Returns:
            Relevance score between 0 and 1.
        """
        # Simple word overlap
        query_words = set(query.lower().split())
        context_words = set(context.lower().split())

        if not query_words or not context_words:
            return 0.0

        overlap = len(query_words & context_words)
        return overlap / len(query_words)

    def _keyword_score(self, text: str) -> float:
        """Score text based on keyword importance.

        Args:
            text: The text to score.

        Returns:
            Score between 0 and 1.
        """
        # Keywords that indicate importance
        important_keywords = [
            "important", "critical", "key", "essential", "must",
            "should", "required", "necessary", "significant", "major"
        ]

        score = 0.0
        text_lower = text.lower()

        for keyword in important_keywords:
            if keyword in text_lower:
                score += 0.1

        return min(score, 1.0)

    def _calculate_readability(self, context: str) -> float:
        """Calculate readability score of context.

        Args:
            context: The context.

        Returns:
            Readability score between 0 and 10.
        """
        # Simple readability: based on sentence length
        sentences = context.split(".")
        if not sentences:
            return 5.0

        avg_sentence_length = len(context.split()) / len(sentences)

        # Ideal sentence length is 15-20 words
        if 15 <= avg_sentence_length <= 20:
            return 10.0
        elif 10 <= avg_sentence_length <= 25:
            return 8.0
        elif 5 <= avg_sentence_length <= 30:
            return 6.0
        else:
            return 4.0

    def _calculate_information_density(self, context: str) -> float:
        """Calculate information density of context.

        Args:
            context: The context.

        Returns:
            Information density score between 0 and 1.
        """
        # Information density: ratio of unique words to total words
        words = context.lower().split()
        unique_words = set(words)

        if not words:
            return 0.0

        return len(unique_words) / len(words)

    def _optimize_for_reasoning(self, context: str, max_tokens: int) -> str:
        """Optimize context for reasoning tasks.

        Args:
            context: The context.
            max_tokens: Maximum tokens.

        Returns:
            Optimized context.
        """
        # Keep logical flow and key insights
        return self._compress_by_extraction(context, max_tokens)

    def _optimize_for_coding(self, context: str, max_tokens: int) -> str:
        """Optimize context for coding tasks.

        Args:
            context: The context.
            max_tokens: Maximum tokens.

        Returns:
            Optimized context.
        """
        # Keep code examples and technical details
        lines = context.split("\n")
        code_lines = [l for l in lines if any(c in l for c in ["def ", "class ", "import ", "return ", "if ", "for "])]

        if code_lines:
            return "\n".join(code_lines[:max_tokens // 20])
        else:
            return self._compress_by_extraction(context, max_tokens)

    def _optimize_for_analysis(self, context: str, max_tokens: int) -> str:
        """Optimize context for analysis tasks.

        Args:
            context: The context.
            max_tokens: Maximum tokens.

        Returns:
            Optimized context.
        """
        # Keep data and statistics
        return self._compress_by_extraction(context, max_tokens)

    def _optimize_for_generation(self, context: str, max_tokens: int) -> str:
        """Optimize context for generation tasks.

        Args:
            context: The context.
            max_tokens: Maximum tokens.

        Returns:
            Optimized context.
        """
        # Keep examples and patterns
        return self._compress_by_extraction(context, max_tokens)
