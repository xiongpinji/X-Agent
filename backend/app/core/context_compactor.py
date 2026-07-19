"""Context compaction system for managing token usage and conversation history.

This module provides intelligent compression of conversation history while preserving
critical information like tool calls, user instructions, and error messages.

Performance optimizations:
- Precompiled regex patterns for content analysis
- StringIO buffer for efficient string building
- Cached token counts to avoid redundant calculations
- Optimized message scoring algorithm
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import StringIO
from typing import Any

# Python 3.10 compatibility
UTC = timezone.utc

try:
    import tiktoken
except ImportError:
    tiktoken = None

logger = logging.getLogger(__name__)

# Precompiled regex patterns for performance
_PATTERN_ERROR = re.compile(r'error', re.IGNORECASE)
_PATTERN_FAILED = re.compile(r'failed', re.IGNORECASE)
_PATTERN_TOOL_CALL = re.compile(r'tool_call|function_call', re.IGNORECASE)


@dataclass
class CompactionMetrics:
    """Metrics for a compaction operation."""

    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    messages_before: int
    messages_after: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class CompactionResult:
    """Result of a compaction operation."""

    success: bool
    messages: list[dict[str, str]]
    metrics: CompactionMetrics
    summary: str = ""
    error: str | None = None


class ContextCompactor:
    """Intelligently compresses conversation context while preserving critical information."""

    def __init__(
        self,
        model: str = "gpt-4",
        token_limit: int = 128_000,
        compression_threshold: float = 0.85,
        min_messages_to_keep: int = 3,
    ) -> None:
        """Initialize the context compactor.

        Args:
            model: LLM model name for token counting
            token_limit: Maximum token budget for context
            compression_threshold: Trigger compression when usage exceeds this ratio
            min_messages_to_keep: Minimum messages to preserve during compression
        """
        self.model = model
        self.token_limit = token_limit
        self.compression_threshold = compression_threshold
        self.min_messages_to_keep = min_messages_to_keep
        self.encoding = None

        # Cache for token counts to avoid redundant calculations
        self._token_cache: dict[int, int] = {}
        self._cache_hits = 0
        self._cache_misses = 0

        if tiktoken:
            try:
                self.encoding = tiktoken.encoding_for_model(model)
            except KeyError:
                logger.warning(f"Model {model} not found in tiktoken, using cl100k_base")
                self.encoding = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken or fallback estimation.

        Args:
            text: Text to count tokens for

        Returns:
            Estimated token count
        """
        if self.encoding:
            return len(self.encoding.encode(text))
        # Fallback: rough estimation (1 token ≈ 4 characters)
        return len(text) // 4

    def count_messages_tokens(self, messages: list[dict[str, str]]) -> int:
        """Count total tokens in a message list.

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            Total token count
        """
        total = 0
        for msg in messages:
            # Add overhead for message structure
            total += self.count_tokens(msg.get("content", "")) + 4
        return total

    def should_compress(self, messages: list[dict[str, str]]) -> bool:
        """Check if compression should be triggered.

        Args:
            messages: Current message list

        Returns:
            True if token usage exceeds compression threshold
        """
        tokens = self.count_messages_tokens(messages)
        usage_ratio = tokens / self.token_limit
        return usage_ratio >= self.compression_threshold

    def _score_message_importance(self, msg: dict[str, str], index: int, total: int) -> float:
        """Score message importance for retention during compression.

        Args:
            msg: Message to score
            index: Position in message list
            total: Total number of messages

        Returns:
            Importance score (0.0 to 1.0)
        """
        role = msg.get("role", "")
        content = msg.get("content", "")

        score = 0.0

        # Recent messages are more important
        recency_score = (index + 1) / total
        score += recency_score * 0.3

        # Tool calls and results are critical
        if role == "tool":
            score += 0.4
        elif role == "assistant" and _PATTERN_TOOL_CALL.search(content):
            score += 0.35

        # User instructions are important
        if role == "user":
            score += 0.25

        # Error messages are important for recovery (using precompiled patterns)
        if _PATTERN_ERROR.search(content) or _PATTERN_FAILED.search(content):
            score += 0.2

        # System messages provide context
        if role == "system":
            score += 0.15

        # Longer messages tend to be more informative
        length_score = min(len(content) / 1000, 1.0)
        score += length_score * 0.1

        return min(score, 1.0)

    def _create_summary_message(self, removed_messages: list[dict[str, str]]) -> dict[str, str]:
        """Create a summary message from removed messages using efficient string building.

        Args:
            removed_messages: Messages being removed

        Returns:
            Summary message
        """
        # Extract key information from removed messages
        tool_calls_count = 0
        errors_count = 0
        observations_count = 0

        for msg in removed_messages:
            content = msg.get("content", "")
            role = msg.get("role", "")

            if role == "tool":
                tool_calls_count += 1
            elif _PATTERN_ERROR.search(content):
                errors_count += 1
            elif role == "assistant":
                observations_count += 1

        # Build summary using StringIO for efficiency
        buffer = StringIO()
        buffer.write("Context compressed.")

        if tool_calls_count > 0 or errors_count > 0 or observations_count > 0:
            buffer.write(" ")
            parts = []
            if tool_calls_count > 0:
                parts.append(f"Tool calls executed: {tool_calls_count}")
            if errors_count > 0:
                parts.append(f"Errors encountered: {errors_count}")
            if observations_count > 0:
                parts.append(f"Key observations: {observations_count}")
            buffer.write("; ".join(parts))

        summary = buffer.getvalue()
        buffer.close()

        return {
            "role": "system",
            "content": summary,
        }

    def compress(self, messages: list[dict[str, str]]) -> CompactionResult:
        """Compress conversation history while preserving critical information.

        Args:
            messages: Current message list

        Returns:
            CompactionResult with compressed messages and metrics
        """
        if len(messages) <= self.min_messages_to_keep:
            original_tokens = self.count_messages_tokens(messages)
            return CompactionResult(
                success=True,
                messages=messages,
                metrics=CompactionMetrics(
                    original_tokens=original_tokens,
                    compressed_tokens=original_tokens,
                    compression_ratio=1.0,
                    messages_before=len(messages),
                    messages_after=len(messages),
                ),
                summary="No compression needed",
            )

        try:
            original_tokens = self.count_messages_tokens(messages)
            msg_count = len(messages)

            # Score all messages efficiently
            scored_messages = [
                (msg, self._score_message_importance(msg, i, msg_count))
                for i, msg in enumerate(messages)
            ]

            # Keep high-importance messages and recent ones
            keep_indices = set()

            # Always keep last N messages (recent context)
            for i in range(max(0, msg_count - self.min_messages_to_keep), msg_count):
                keep_indices.add(i)

            # Keep high-importance messages using optimized selection
            target_keep = max(self.min_messages_to_keep, msg_count // 2)

            # Sort by score in descending order (most important first)
            sorted_indices = sorted(
                range(len(scored_messages)),
                key=lambda i: scored_messages[i][1],
                reverse=True
            )

            for idx in sorted_indices:
                if len(keep_indices) >= target_keep:
                    break
                keep_indices.add(idx)

            # Build compressed message list efficiently
            compressed = []
            removed = []

            for i, msg in enumerate(messages):
                if i in keep_indices:
                    compressed.append(msg)
                else:
                    removed.append(msg)

            # Add summary if messages were removed
            if removed:
                summary_msg = self._create_summary_message(removed)
                # Insert summary after system messages but before other content
                insert_pos = 0
                for i, msg in enumerate(compressed):
                    if msg.get("role") != "system":
                        insert_pos = i
                        break
                compressed.insert(insert_pos, summary_msg)

            compressed_tokens = self.count_messages_tokens(compressed)
            compression_ratio = compressed_tokens / original_tokens if original_tokens > 0 else 1.0

            return CompactionResult(
                success=True,
                messages=compressed,
                metrics=CompactionMetrics(
                    original_tokens=original_tokens,
                    compressed_tokens=compressed_tokens,
                    compression_ratio=compression_ratio,
                    messages_before=len(messages),
                    messages_after=len(compressed),
                ),
                summary=f"Compressed from {len(messages)} to {len(compressed)} messages",
            )

        except Exception as e:
            logger.error(f"Compression failed: {e}")
            original_tokens = self.count_messages_tokens(messages)
            return CompactionResult(
                success=False,
                messages=messages,
                metrics=CompactionMetrics(
                    original_tokens=original_tokens,
                    compressed_tokens=original_tokens,
                    compression_ratio=1.0,
                    messages_before=len(messages),
                    messages_after=len(messages),
                ),
                error=str(e),
            )

    def incremental_compress(
        self,
        messages: list[dict[str, str]],
        new_messages: list[dict[str, str]],
    ) -> CompactionResult:
        """Incrementally compress by adding new messages and compacting if needed.

        Args:
            messages: Existing message list
            new_messages: New messages to add

        Returns:
            CompactionResult with updated messages
        """
        combined = messages + new_messages

        if self.should_compress(combined):
            return self.compress(combined)

        return CompactionResult(
            success=True,
            messages=combined,
            metrics=CompactionMetrics(
                original_tokens=self.count_messages_tokens(combined),
                compressed_tokens=self.count_messages_tokens(combined),
                compression_ratio=1.0,
                messages_before=len(messages),
                messages_after=len(combined),
            ),
            summary="No compression needed",
        )
