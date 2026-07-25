"""Unified context management system for X-Agent.

Coordinates context compression, session recovery, and hybrid memory management.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.core.context.code_index import (
    CodebaseIndex,
    CodeMatch,
    IndexStats,
)
from backend.app.core.context.compression import (
    CompressedContext,
    ContextCompressor,
)
from backend.app.core.context.retrieval import (
    ContextItem,
    ContextRetriever,
    RetrievalWeights,
)
from backend.app.core.context.session_recovery import (
    Message,
    SessionRecovery,
    SessionState,
    SessionStats,
)
from backend.app.core.context_compactor import (
    CompactionMetrics,
    CompactionResult,
    ContextCompactor,
)

logger = logging.getLogger(__name__)


@dataclass
class ContextMetrics:
    """Metrics for context management."""

    total_messages: int = 0
    total_tokens: int = 0
    compressed_tokens: int = 0
    compression_ratio: float = 1.0
    compression_count: int = 0
    last_compression_time: datetime | None = None
    average_compression_duration_ms: float = 0.0
    memory_usage_mb: float = 0.0


class ContextManager:
    """Unified context management system.

    Coordinates:
    - Message handling and storage
    - Automatic context compression
    - Session persistence and recovery
    - Hybrid memory system integration
    """

    def __init__(
        self,
        session_recovery: SessionRecovery,
        context_compactor: ContextCompactor,
        hybrid_memory_system: Any | None = None,
        auto_save_interval_seconds: int = 300,
        auto_compress_enabled: bool = True,
        context_compressor: ContextCompressor | None = None,
        context_retriever: ContextRetriever | None = None,
        codebase_index: CodebaseIndex | None = None,
    ) -> None:
        """Initialize context manager.

        Args:
            session_recovery: Session recovery system
            context_compactor: Context compaction system
            hybrid_memory_system: Optional hybrid memory system
            auto_save_interval_seconds: Interval for auto-saving sessions
            auto_compress_enabled: Enable automatic compression
            context_compressor: Optional intelligent context compressor
            context_retriever: Optional intelligent context retriever
            codebase_index: Optional codebase index for code search
        """
        self.session_recovery = session_recovery
        self.context_compactor = context_compactor
        self.hybrid_memory_system = hybrid_memory_system

        self.auto_save_interval_seconds = auto_save_interval_seconds
        self.auto_compress_enabled = auto_compress_enabled

        # New context modules
        self._context_compressor = context_compressor
        self._context_retriever = context_retriever
        self._codebase_index = codebase_index

        # Current session state
        self._current_session: SessionState | None = None
        self._session_id: str | None = None

        # Metrics
        self._metrics = ContextMetrics()

        # Locks for thread safety
        self._lock = asyncio.Lock()
        self._save_task: asyncio.Task | None = None

        logger.info("ContextManager initialized")

    @property
    def current_session(self) -> SessionState | None:
        """当前活跃会话（只读视图；无活跃会话时为 None）。"""
        return self._current_session

    @property
    def current_session_id(self) -> str | None:
        """当前活跃会话 ID（无活跃会话时为 None）。"""
        return self._session_id

    async def initialize_session(
        self,
        session_id: str,
        agent_id: str = "",
        tenant_id: str = "",
        context_window: int = 128_000,
    ) -> SessionState:
        """Initialize or restore a session.

        Args:
            session_id: Session ID
            agent_id: Agent ID
            tenant_id: Tenant ID
            context_window: Token limit for context

        Returns:
            SessionState

        Raises:
            ValueError: 恢复的会话 tenant_id 与请求 tenant_id 不一致时显式报错，
                防止跨租户会话被静默接管（两边均非空时才强制校验）。
        """
        async with self._lock:
            try:
                # Try to restore existing session
                existing_session = await self.session_recovery.load_snapshot(session_id)

                if existing_session:
                    existing_tenant = (existing_session.tenant_id or "").strip()
                    requested_tenant = (tenant_id or "").strip()
                    if existing_tenant and requested_tenant and existing_tenant != requested_tenant:
                        raise ValueError(
                            f"Tenant mismatch for session {session_id}: "
                            f"stored tenant '{existing_tenant}' != requested tenant '{requested_tenant}'"
                        )
                    self._current_session = existing_session
                    self._session_id = session_id
                    logger.info(f"Restored session: {session_id}")
                    return existing_session

                # Create new session
                self._current_session = SessionState(
                    session_id=session_id,
                    agent_id=agent_id,
                    tenant_id=tenant_id,
                    context_window=context_window,
                )
                self._session_id = session_id

                logger.info(f"Created new session: {session_id}")

                return self._current_session

            except Exception as e:
                logger.error(f"Failed to initialize session: {e}")
                raise

    async def add_message(
        self,
        role: str,
        content: str,
        metadata: dict | None = None,
        importance: float = 0.5,
    ) -> Message:
        """Add a message to the current session.

        Args:
            role: Message role (user, assistant, system, tool)
            content: Message content
            metadata: Optional metadata
            importance: Importance score (0.0-1.0)

        Returns:
            Added Message
        """
        async with self._lock:
            if not self._current_session:
                raise ValueError("No active session. Call initialize_session first.")

            try:
                # Create message
                message = Message(
                    role=role,
                    content=content,
                    metadata=metadata or {},
                    importance=importance,
                )

                # Count tokens
                token_count = self.context_compactor.count_tokens(content)
                message.token_count = token_count

                # Add to session
                self._current_session.messages.append(message)
                self._current_session.total_tokens += token_count
                self._current_session.updated_at = datetime.now(UTC)

                # Update metrics
                self._metrics.total_messages += 1
                self._metrics.total_tokens += token_count

                # Sync with context retriever if available
                if self._context_retriever:
                    try:
                        self._context_retriever.add_message(message)
                    except Exception as e:
                        logger.warning(f"Failed to sync message with retriever: {e}")

                # Store in hybrid memory if available
                if self.hybrid_memory_system:
                    try:
                        await self.hybrid_memory_system.store(
                            content=content,
                            metadata={
                                "session_id": self._session_id,
                                "role": role,
                                **(metadata or {}),
                            },
                        )
                    except Exception as e:
                        logger.warning(f"Failed to store in hybrid memory: {e}")

                # Check if compression is needed
                if self.auto_compress_enabled:
                    await self._check_and_compress()

                logger.debug(
                    f"Added message: {role} ({token_count} tokens, "
                    f"total: {self._current_session.total_tokens})"
                )

                return message

            except Exception as e:
                logger.error(f"Failed to add message: {e}")
                raise

    async def get_context(
        self,
        limit: int | None = None,
        include_metadata: bool = False,
    ) -> list[dict[str, Any]]:
        """Get current context as message list.

        Args:
            limit: Maximum number of messages to return
            include_metadata: Include message metadata

        Returns:
            List of messages
        """
        async with self._lock:
            if not self._current_session:
                return []

            try:
                messages = self._current_session.messages

                if limit:
                    messages = messages[-limit:]

                result = []
                for msg in messages:
                    msg_dict = {
                        "id": msg.id,
                        "role": msg.role,
                        "content": msg.content,
                    }

                    if include_metadata:
                        msg_dict.update(
                            {
                                "timestamp": msg.timestamp.isoformat(),
                                "importance": msg.importance,
                                "compressed": msg.compressed,
                                "token_count": msg.token_count,
                                "metadata": msg.metadata,
                            }
                        )

                    result.append(msg_dict)

                return result

            except Exception as e:
                logger.error(f"Failed to get context: {e}")
                return []

    async def compress_if_needed(self) -> CompactionResult | None:
        """Check and compress context if needed.

        Returns:
            CompactionResult if compression was performed, None otherwise
        """
        async with self._lock:
            return await self._check_and_compress()

    async def _check_and_compress(self) -> CompactionResult | None:
        """Check token usage and compress context when over threshold.

        统一行为（两条压缩路径共用）：
        1. 先用 ContextCompactor.should_compress 做阈值门槛 —— 未超阈值绝不压缩
           （修复旧实现中挂载智能压缩器后每次 add_message 都全量压缩的问题）。
        2. 压缩时始终保留最近 min_messages_to_keep 条消息原文，只压缩更早的历史，
           避免整段会话被压成单个 blob 后丢失近期上下文。
        3. 优先使用智能压缩器（ContextCompressor）对旧历史生成摘要；
           失败或不可用时回退到 legacy ContextCompactor 的重要性评分压缩。
        4. 压缩后重算 total_tokens，并返回统一的 CompactionResult。

        Returns:
            CompactionResult if compression was performed, None otherwise
        """
        if not self._current_session or not self.auto_compress_enabled:
            return None

        try:
            messages = [
                {
                    "role": msg.role,
                    "content": msg.content,
                }
                for msg in self._current_session.messages
            ]

            # 统一阈值门槛：两条路径都只在超阈值时触发
            if not self.context_compactor.should_compress(messages):
                return None

            min_keep = max(1, int(getattr(self.context_compactor, "min_messages_to_keep", 3)))
            all_messages = self._current_session.messages
            if len(all_messages) <= min_keep:
                # 全是受保护的近期消息，无法在不丢近期上下文的前提下压缩
                return None

            recent_messages = all_messages[-min_keep:]
            older_messages = all_messages[:-min_keep]
            original_tokens = sum(msg.token_count for msg in all_messages)
            messages_before = len(all_messages)
            started_at = datetime.now(UTC)

            summary_message: Message | None = None
            kept_older: list[Message] = []
            strategy_used = "legacy"

            # 优先：智能压缩器把旧历史压成一条摘要
            if self._context_compressor:
                try:
                    combined_content = "\n".join(
                        f"[{msg.role}]: {msg.content}"
                        for msg in older_messages
                    )
                    compressed = await self._context_compressor.compress_async(
                        content=combined_content,
                        strategy="hybrid",
                        target_ratio=0.5,
                    )
                    if compressed and compressed.content.strip():
                        summary_message = Message(
                            role="system",
                            content=compressed.content,
                            compressed=True,
                            metadata={
                                "compression_ratio": compressed.compression_ratio,
                                "strategy": compressed.strategy,
                                "original_tokens": compressed.original_tokens,
                                "compressed_tokens": compressed.compressed_tokens,
                                "summarized_messages": len(older_messages),
                            },
                        )
                        strategy_used = f"intelligent:{compressed.strategy}"
                    else:
                        logger.warning("Intelligent compressor returned empty content, falling back to legacy")
                except Exception as e:
                    logger.warning(f"Intelligent compressor failed, falling back to legacy: {e}")

            # 回退：legacy 重要性评分压缩旧历史
            if summary_message is None:
                legacy_result = self.context_compactor.compress(
                    [{"role": msg.role, "content": msg.content} for msg in older_messages]
                )
                if not legacy_result.success:
                    logger.warning(f"Compression failed: {legacy_result.error}")
                    return None
                for msg_dict in legacy_result.messages:
                    original = next(
                        (m for m in older_messages if m.content == msg_dict.get("content")),
                        None,
                    )
                    if original is not None:
                        kept_older.append(original)
                    else:
                        kept_older.append(
                            Message(
                                role=msg_dict.get("role", "system"),
                                content=msg_dict.get("content", ""),
                                compressed=True,
                            )
                        )
                strategy_used = "legacy"

            new_messages = ([summary_message] if summary_message is not None else []) + kept_older + recent_messages

            # 重算 token 计数（摘要消息需要计数）
            for msg in new_messages:
                if msg is summary_message or msg.token_count <= 0:
                    msg.token_count = self.context_compactor.count_tokens(msg.content)

            self._current_session.messages = new_messages
            self._current_session.total_tokens = sum(msg.token_count for msg in new_messages)
            self._current_session.compressed_tokens = self._current_session.total_tokens
            compressed_tokens = self._current_session.total_tokens
            compression_ratio = compressed_tokens / original_tokens if original_tokens > 0 else 1.0

            finished_at = datetime.now(UTC)
            duration_ms = (finished_at - started_at).total_seconds() * 1000

            self._current_session.compression_history.append(
                {
                    "timestamp": finished_at.isoformat(),
                    "original_tokens": original_tokens,
                    "compressed_tokens": compressed_tokens,
                    "ratio": compression_ratio,
                    "strategy": strategy_used,
                    "messages_before": messages_before,
                    "messages_after": len(new_messages),
                    "kept_recent": min_keep,
                }
            )

            # Update metrics
            self._metrics.compression_count += 1
            self._metrics.compressed_tokens = compressed_tokens
            self._metrics.compression_ratio = compression_ratio
            self._metrics.last_compression_time = finished_at
            count = self._metrics.compression_count
            self._metrics.average_compression_duration_ms = (
                self._metrics.average_compression_duration_ms * (count - 1) + duration_ms
            ) / count

            logger.info(
                f"Compression successful ({strategy_used}): {messages_before} → "
                f"{len(new_messages)} messages, {original_tokens} → {compressed_tokens} tokens, "
                f"ratio: {compression_ratio:.2%}"
            )

            return CompactionResult(
                success=True,
                messages=[{"role": msg.role, "content": msg.content} for msg in new_messages],
                metrics=CompactionMetrics(
                    original_tokens=original_tokens,
                    compressed_tokens=compressed_tokens,
                    compression_ratio=compression_ratio,
                    messages_before=messages_before,
                    messages_after=len(new_messages),
                ),
                summary=f"Compressed {messages_before - min_keep} older messages ({strategy_used}), kept {min_keep} recent",
            )

        except Exception as e:
            logger.error(f"Error during compression check: {e}")
            return None

    async def save_session(self) -> bool:
        """Save current session to disk.

        Returns:
            True if successful, False otherwise
        """
        async with self._lock:
            if not self._current_session:
                return False

            try:
                await self.session_recovery.save_snapshot(self._current_session)
                logger.info(f"Saved session: {self._session_id}")
                return True

            except Exception as e:
                logger.error(f"Failed to save session: {e}")
                return False

    async def restore_session(
        self,
        session_id: str,
    ) -> SessionState | None:
        """Restore a session from disk.

        Args:
            session_id: Session ID to restore

        Returns:
            SessionState if successful, None otherwise
        """
        async with self._lock:
            try:
                session_state = await self.session_recovery.load_snapshot(session_id)

                if session_state:
                    self._current_session = session_state
                    self._session_id = session_id

                    # Update metrics
                    self._metrics.total_messages = len(session_state.messages)
                    self._metrics.total_tokens = session_state.total_tokens
                    self._metrics.compressed_tokens = session_state.compressed_tokens
                    self._metrics.compression_count = len(session_state.compression_history)

                    logger.info(f"Restored session: {session_id}")

                return session_state

            except Exception as e:
                logger.error(f"Failed to restore session: {e}")
                return None

    async def list_sessions(
        self,
        agent_id: str | None = None,
        limit: int = 100,
        tenant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all sessions.

        Args:
            agent_id: Filter by agent ID
            limit: Maximum number of sessions
            tenant_id: Filter by tenant ID（多租户隔离用）

        Returns:
            List of session metadata
        """
        try:
            sessions = await self.session_recovery.list_sessions(agent_id, limit, tenant_id=tenant_id)

            return [
                {
                    "session_id": s.session_id,
                    "agent_id": s.agent_id,
                    "tenant_id": s.tenant_id,
                    "title": s.title,
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat(),
                    "message_count": s.message_count,
                    "token_count": s.token_count,
                    "last_snapshot": s.last_snapshot.isoformat() if s.last_snapshot else None,
                }
                for s in sessions
            ]

        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []

    async def delete_session(
        self,
        session_id: str,
    ) -> bool:
        """Delete a session.

        Args:
            session_id: Session ID to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            result = await self.session_recovery.delete_session(session_id)

            if result and session_id == self._session_id:
                self._current_session = None
                self._session_id = None

            return result

        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
            return False

    async def get_session_stats(
        self,
        session_id: str | None = None,
    ) -> SessionStats | None:
        """Get statistics for a session.

        Args:
            session_id: Session ID (uses current if not specified)

        Returns:
            SessionStats if found, None otherwise
        """
        try:
            target_session_id = session_id or self._session_id

            if not target_session_id:
                return None

            return await self.session_recovery.get_session_stats(target_session_id)

        except Exception as e:
            logger.error(f"Failed to get session stats: {e}")
            return None

    async def get_metrics(self) -> ContextMetrics:
        """Get current context metrics.

        Returns:
            ContextMetrics
        """
        async with self._lock:
            return self._metrics

    async def start_auto_save(self) -> None:
        """Start automatic session saving."""
        if self._save_task:
            return

        async def auto_save_loop():
            while True:
                try:
                    await asyncio.sleep(self.auto_save_interval_seconds)
                    await self.save_session()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in auto-save loop: {e}")

        self._save_task = asyncio.create_task(auto_save_loop())
        logger.info("Started auto-save loop")

    async def stop_auto_save(self) -> None:
        """Stop automatic session saving."""
        if self._save_task:
            self._save_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._save_task
            self._save_task = None
            logger.info("Stopped auto-save loop")

    async def cleanup(self) -> None:
        """Clean up resources."""
        await self.stop_auto_save()
        await self.save_session()
        logger.info("ContextManager cleanup complete")

    async def compress_context(
        self,
        strategy: str = "hybrid",
    ) -> CompressedContext | None:
        """Compress current context using the intelligent compressor.

        Args:
            strategy: Compression strategy ('hybrid', 'summary', 'semantic')

        Returns:
            CompressedContext if successful, None otherwise
        """
        if not self._context_compressor:
            logger.warning("Context compressor not available")
            return None

        async with self._lock:
            if not self._current_session:
                logger.warning("No active session")
                return None

            try:
                # Combine all messages into single content
                combined_content = "\n".join(
                    f"[{msg.role}]: {msg.content}"
                    for msg in self._current_session.messages
                )

                if not combined_content.strip():
                    logger.warning("No content to compress")
                    return None

                # Compress using new compressor
                compressed = await self._context_compressor.compress_async(
                    content=combined_content,
                    strategy=strategy,
                    target_ratio=0.5,
                )

                logger.info(
                    f"Context compressed: {compressed.original_tokens} → "
                    f"{compressed.compressed_tokens} tokens "
                    f"({compressed.compression_ratio:.2%})"
                )

                return compressed

            except Exception as e:
                logger.error(f"Failed to compress context: {e}")
                return None

    async def retrieve_context(
        self,
        query: str,
        limit: int = 10,
        weights: RetrievalWeights | None = None,
    ) -> list[ContextItem]:
        """Retrieve context items based on query using intelligent retriever.

        Args:
            query: Query string
            limit: Maximum number of items to return
            weights: Optional retrieval weights for hybrid search

        Returns:
            List of ContextItem objects
        """
        if not self._context_retriever:
            logger.warning("Context retriever not available")
            return []

        async with self._lock:
            try:
                if weights:
                    # Use hybrid retrieval with custom weights
                    results = self._context_retriever.retrieve_hybrid(
                        query=query,
                        weights=weights,
                        top_k=limit,
                    )
                else:
                    # Use relevance-based retrieval
                    results = self._context_retriever.retrieve_by_relevance(
                        query=query,
                        top_k=limit,
                    )

                logger.debug(f"Retrieved {len(results)} context items for query: {query}")
                return results

            except Exception as e:
                logger.error(f"Failed to retrieve context: {e}")
                return []

    async def search_codebase(
        self,
        query: str,
        file_types: list[str] | None = None,
        limit: int = 20,
    ) -> list[CodeMatch]:
        """Search codebase using intelligent code index.

        Args:
            query: Search query
            file_types: Optional list of file types to search
            limit: Maximum number of results

        Returns:
            List of CodeMatch objects
        """
        if not self._codebase_index:
            logger.warning("Codebase index not available")
            return []

        try:
            results = self._codebase_index.search(
                query=query,
                file_types=file_types,
                limit=limit,
            )

            logger.debug(f"Found {len(results)} code matches for query: {query}")
            return results

        except Exception as e:
            logger.error(f"Failed to search codebase: {e}")
            return []

    async def index_codebase(
        self,
        root_path: Path | str,
    ) -> IndexStats | None:
        """Build or update codebase index.

        Args:
            root_path: Root path of codebase to index

        Returns:
            IndexStats if successful, None otherwise
        """
        if not self._codebase_index:
            logger.warning("Codebase index not available")
            return None

        try:
            root_path = Path(root_path).resolve()

            if not root_path.exists():
                logger.error(f"Root path does not exist: {root_path}")
                return None

            logger.info(f"Starting codebase indexing: {root_path}")

            stats = self._codebase_index.build_index(root_path)

            logger.info(
                f"Codebase indexing complete: {stats.indexed_files} files, "
                f"{stats.total_symbols} symbols, {stats.index_time_seconds:.2f}s"
            )

            return stats

        except Exception as e:
            logger.error(f"Failed to index codebase: {e}")
            return None

# End of ContextManager — Phase 4 context integration (compression/retrieval/code_index)

