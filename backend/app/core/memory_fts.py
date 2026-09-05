"""Memory Full-Text Search (FTS5) Engine

Provides SQLite FTS5-based full-text search for cross-session memory recall,
comparable to Hermes Agent's FTS5 + LLM summarization capability.

Features:
- FTS5 full-text indexing with BM25 ranking
- Chinese tokenizer support (simple character-based)
- LLM-powered result summarization
- Cross-session memory retrieval
"""

from __future__ import annotations

import logging
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default FTS database path (X-Agent 主路径约定: data/memory_fts.sqlite3,
# 可被 settings.memory_fts_path / XAGENT_MEMORY_FTS_PATH 覆盖)
DEFAULT_FTS_DB_PATH = Path("data/memory_fts.sqlite3")

# unicode61 把整段无空格 CJK 当作单个 token，导致中文查询无法命中子串。
# 启用中文分词时按字(unigram)切开再入索引/查询，查询端组合为短语(连续字序)。
_CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")
_ASCII_TERM_RE = re.compile(r"[a-z0-9_]{2,}")


def _preprocess_text(text: str) -> str:
    """Insert spaces between CJK characters so unicode61 indexes per-character."""
    if not text:
        return text
    return _CJK_RUN_RE.sub(lambda m: " ".join(m.group(0)), text)


@dataclass
class FTSResult:
    """Full-text search result."""

    memory_id: str
    content: str
    score: float
    session_id: str | None = None
    created_at: float = 0.0
    metadata: dict = field(default_factory=dict)
    snippet: str = ""


@dataclass
class FTSSearchResponse:
    """Response from FTS search."""

    results: list[FTSResult]
    query: str
    total_found: int
    search_time_ms: float
    summary: str | None = None


class MemoryFTSEngine:
    """SQLite FTS5-based full-text search engine for memories.

    Provides Hermes-like cross-session memory recall with:
    - FTS5 indexing with BM25 ranking
    - Chinese text support
    - Session-aware filtering
    - LLM summarization integration
    """

    def __init__(
        self,
        db_path: Path | str = DEFAULT_FTS_DB_PATH,
        enable_chinese_tokenizer: bool = True,
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.enable_chinese_tokenizer = enable_chinese_tokenizer
        self._local = threading.local()
        self._init_db()
        logger.info(f"MemoryFTSEngine initialized at {self.db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0,
            )
            self._local.conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrent read performance
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
        return self._local.conn

    def _init_db(self) -> None:
        """Initialize FTS5 virtual table and metadata table."""
        conn = self._get_conn()

        # Main FTS5 virtual table with content
        # Using simple tokenizer for Chinese compatibility
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                memory_id UNINDEXED,
                content,
                session_id UNINDEXED,
                tenant_id UNINDEXED,
                agent_id UNINDEXED,
                tags,
                tokenize='unicode61'
            )
        """)

        # Metadata table for non-indexed fields
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_meta (
                memory_id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                session_id TEXT,
                tenant_id TEXT,
                agent_id TEXT,
                tags TEXT,
                created_at REAL,
                updated_at REAL,
                access_count INTEGER DEFAULT 0,
                last_accessed REAL
            )
        """)

        # Indexes for common queries
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_meta_tenant
            ON memory_meta(tenant_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_meta_session
            ON memory_meta(session_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_meta_created
            ON memory_meta(created_at)
        """)

        conn.commit()

    def index_memory(
        self,
        memory_id: str,
        content: str,
        session_id: str | None = None,
        tenant_id: str = "default",
        agent_id: str | None = None,
        tags: list[str] | None = None,
    ) -> bool:
        """Index a memory for full-text search.

        Args:
            memory_id: Unique memory identifier
            content: Memory content to index
            session_id: Optional session identifier
            tenant_id: Tenant identifier
            agent_id: Optional agent identifier
            tags: Optional list of tags

        Returns:
            True if indexed successfully
        """
        conn = self._get_conn()
        now = time.time()
        tags_str = " ".join(tags) if tags else ""
        indexed_content = self._prepare(content)
        indexed_tags = self._prepare(tags_str)

        try:
            # Upsert into FTS table
            conn.execute(
                "DELETE FROM memory_fts WHERE memory_id = ?",
                (memory_id,),
            )
            conn.execute(
                """
                INSERT INTO memory_fts (memory_id, content, session_id, tenant_id, agent_id, tags)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (memory_id, indexed_content, session_id, tenant_id, agent_id, indexed_tags),
            )

            # Upsert into metadata table
            conn.execute(
                """
                INSERT OR REPLACE INTO memory_meta
                (memory_id, content, session_id, tenant_id, agent_id, tags, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (memory_id, content, session_id, tenant_id, agent_id, tags_str, now, now),
            )

            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to index memory {memory_id}: {e}")
            conn.rollback()
            return False

    def _prepare(self, text: str) -> str:
        """Preprocess text for the FTS index (CJK unigram spacing when enabled)."""
        if not self.enable_chinese_tokenizer:
            return text
        return _preprocess_text(text)

    def index_memory_bulk(self, items: list[dict[str, Any]]) -> int:
        """Idempotently (re)index many memories in a single transaction.

        Each item dict accepts the same fields as :meth:`index_memory`
        (memory_id + content required). Row count is stable across repeated
        calls: the FTS row is DELETEd then re-INSERTed and metadata is
        INSERT OR REPLACE keyed by memory_id.

        Returns the number of items indexed.
        """
        if not items:
            return 0
        conn = self._get_conn()
        started = time.perf_counter()
        try:
            conn.execute("BEGIN")
            for entry in items:
                memory_id = str(entry["memory_id"])
                content = str(entry.get("content", ""))
                tags = entry.get("tags") or []
                tags_str = " ".join(tags) if isinstance(tags, list) else str(tags or "")
                conn.execute(
                    "DELETE FROM memory_fts WHERE memory_id = ?",
                    (memory_id,),
                )
                conn.execute(
                    """
                    INSERT INTO memory_fts (memory_id, content, session_id, tenant_id, agent_id, tags)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        memory_id,
                        self._prepare(content),
                        entry.get("session_id"),
                        entry.get("tenant_id", "default"),
                        entry.get("agent_id"),
                        self._prepare(tags_str),
                    ),
                )
                now = time.time()
                conn.execute(
                    """
                    INSERT OR REPLACE INTO memory_meta
                    (memory_id, content, session_id, tenant_id, agent_id, tags, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        memory_id,
                        content,
                        entry.get("session_id"),
                        entry.get("tenant_id", "default"),
                        entry.get("agent_id"),
                        tags_str,
                        float(entry.get("created_at", now)),
                        now,
                    ),
                )
            conn.commit()
            logger.debug(
                "FTS bulk index: %d items in %.1fms", len(items), (time.perf_counter() - started) * 1000
            )
            return len(items)
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"FTS bulk index failed: {e}") from e

    def remove_memories(self, memory_ids: list[str]) -> int:
        """Remove many memories from the index in a single transaction."""
        if not memory_ids:
            return 0
        conn = self._get_conn()
        try:
            conn.execute("BEGIN")
            for memory_id in memory_ids:
                conn.execute("DELETE FROM memory_fts WHERE memory_id = ?", (memory_id,))
                conn.execute("DELETE FROM memory_meta WHERE memory_id = ?", (memory_id,))
            conn.commit()
            return len(memory_ids)
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to remove memories in bulk: {e}")
            return 0

    def remove_memory(self, memory_id: str) -> bool:
        """Remove a memory from the index."""
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM memory_fts WHERE memory_id = ?", (memory_id,))
            conn.execute("DELETE FROM memory_meta WHERE memory_id = ?", (memory_id,))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to remove memory {memory_id}: {e}")
            conn.rollback()
            return False

    def search(
        self,
        query: str,
        tenant_id: str = "default",
        session_id: str | None = None,
        limit: int = 10,
        include_summary: bool = False,
    ) -> FTSSearchResponse:
        """Perform full-text search with BM25 ranking.

        Args:
            query: Search query
            tenant_id: Filter by tenant
            session_id: Optional filter by session
            limit: Maximum results
            include_summary: Whether to generate LLM summary

        Returns:
            FTSSearchResponse with ranked results
        """
        start_time = time.perf_counter()
        conn = self._get_conn()

        # Build FTS5 OR-recall query (ASCII terms + CJK unigram phrases)
        safe_query = self._build_match_query(query)

        # Build FTS5 query with BM25 ranking
        # BM25 weights (one per column): content=10.0, tags=5.0, others 0
        sql = """
            SELECT
                m.memory_id,
                m.content,
                m.session_id,
                m.created_at,
                m.tags,
                bm25(memory_fts, 0.0, 10.0, 0.0, 0.0, 0.0, 5.0) as rank,
                snippet(memory_fts, 1, '<b>', '</b>', '...', 32) as snippet
            FROM memory_fts
            JOIN memory_meta m ON memory_fts.memory_id = m.memory_id
            WHERE memory_fts MATCH ?
            AND m.tenant_id = ?
        """
        params: list[Any] = [safe_query, tenant_id]

        if session_id:
            sql += " AND m.session_id = ?"
            params.append(session_id)

        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)

        results: list[FTSResult] = []
        try:
            cursor = conn.execute(sql, params)
            for row in cursor.fetchall():
                # Update access stats
                conn.execute(
                    "UPDATE memory_meta SET access_count = access_count + 1, last_accessed = ? WHERE memory_id = ?",
                    (time.time(), row["memory_id"]),
                )

                results.append(
                    FTSResult(
                        memory_id=row["memory_id"],
                        content=row["content"],
                        score=-row["rank"],  # BM25 returns negative scores
                        session_id=row["session_id"],
                        created_at=row["created_at"],
                        metadata={"tags": row["tags"].split() if row["tags"] else []},
                        snippet=row["snippet"],
                    )
                )
            conn.commit()
        except Exception as e:
            logger.error(f"FTS search failed: {e}")
            # Fallback to LIKE search
            results = self._fallback_search(query, tenant_id, limit)

        search_time = (time.perf_counter() - start_time) * 1000
        logger.debug(
            "FTS search '%s': %d/%d results in %.2fms",
            query[:50],
            len(results),
            limit,
            search_time,
        )

        # Generate summary if requested
        summary = None
        if include_summary and results:
            summary = self._generate_summary(query, results)

        return FTSSearchResponse(
            results=results,
            query=query,
            total_found=len(results),
            search_time_ms=search_time,
            summary=summary,
        )

    def search_cross_session(
        self,
        query: str,
        tenant_id: str = "default",
        limit: int = 20,
    ) -> FTSSearchResponse:
        """Search across all sessions for cross-session recall.

        This is the key Hermes-like capability: remembering context
        from past conversations across different sessions.
        """
        return self.search(
            query=query,
            tenant_id=tenant_id,
            session_id=None,  # No session filter = cross-session
            limit=limit,
            include_summary=True,
        )

    def get_recent_memories(
        self,
        tenant_id: str = "default",
        session_id: str | None = None,
        limit: int = 10,
    ) -> list[FTSResult]:
        """Get most recent memories (for context building)."""
        conn = self._get_conn()

        sql = """
            SELECT memory_id, content, session_id, created_at, tags
            FROM memory_meta
            WHERE tenant_id = ?
        """
        params: list[Any] = [tenant_id]

        if session_id:
            sql += " AND session_id = ?"
            params.append(session_id)

        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        results = []
        try:
            cursor = conn.execute(sql, params)
            for row in cursor.fetchall():
                results.append(
                    FTSResult(
                        memory_id=row["memory_id"],
                        content=row["content"],
                        score=0.0,
                        session_id=row["session_id"],
                        created_at=row["created_at"],
                        metadata={"tags": row["tags"].split() if row["tags"] else []},
                    )
                )
        except Exception as e:
            logger.error(f"Failed to get recent memories: {e}")

        return results

    def get_stats(self, tenant_id: str = "default") -> dict[str, Any]:
        """Get FTS index statistics."""
        conn = self._get_conn()
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM memory_meta WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchone()[0]

            sessions = conn.execute(
                "SELECT COUNT(DISTINCT session_id) FROM memory_meta WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchone()[0]

            return {
                "total_memories": total,
                "unique_sessions": sessions,
                "db_path": str(self.db_path),
                "db_size_bytes": self.db_path.stat().st_size if self.db_path.exists() else 0,
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}

    def _build_match_query(self, query: str) -> str:
        """Build a safe FTS5 MATCH expression with OR recall.

        Mirrors the linear scan's "any term hit survives" filter semantics:
        ASCII word terms become quoted tokens; each CJK run becomes a quoted
        phrase of unigram tokens (contiguous subsequence match). Parts are
        joined with OR so every keyword-exact hit is in the MATCH set.
        """
        normalized = (query or "").casefold()
        parts: list[str] = []
        for term in _ASCII_TERM_RE.findall(normalized):
            parts.append(f'"{term}"')
        if self.enable_chinese_tokenizer:
            for run in _CJK_RUN_RE.findall(normalized):
                if len(run) == 1:
                    parts.append(f'"{run}"')
                else:
                    parts.append('"{}"'.format(" ".join(run)))
        else:
            for run in _CJK_RUN_RE.findall(normalized):
                parts.append(f'"{run}"')
        if not parts:
            return '""'
        return " OR ".join(parts)

    def _fallback_search(
        self,
        query: str,
        tenant_id: str,
        limit: int,
    ) -> list[FTSResult]:
        """Fallback LIKE-based search when FTS fails."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """
                SELECT memory_id, content, session_id, created_at, tags
                FROM memory_meta
                WHERE tenant_id = ? AND content LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (tenant_id, f"%{query}%", limit),
            )
            return [
                FTSResult(
                    memory_id=row["memory_id"],
                    content=row["content"],
                    score=0.5,
                    session_id=row["session_id"],
                    created_at=row["created_at"],
                    metadata={"tags": row["tags"].split() if row["tags"] else []},
                )
                for row in cursor.fetchall()
            ]
        except Exception as e:
            logger.error(f"Fallback search failed: {e}")
            return []

    def _generate_summary(
        self,
        query: str,
        results: list[FTSResult],
    ) -> str | None:
        """Generate LLM summary of search results.

        Uses the configured LLM backend to summarize findings,
        similar to Hermes Agent's FTS5 + LLM summarization.
        """
        if not results:
            return None

        # Build context from top results
        context_parts = []
        for i, r in enumerate(results[:5], 1):
            snippet = r.content[:200] + "..." if len(r.content) > 200 else r.content
            context_parts.append(f"{i}. {snippet}")

        context = "\n".join(context_parts)

        # Try to use LLM for summarization
        try:
            from backend.app.core.llm.backends import get_llm_backend

            llm = get_llm_backend()
            prompt = f"""Based on these memory search results for query "{query}", provide a brief summary:

{context}

Summary (2-3 sentences):"""

            # This is synchronous; in production use async
            import asyncio
            response = asyncio.get_event_loop().run_until_complete(
                llm.chat([{"role": "user", "content": prompt}], [])
            )
            return response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            logger.debug(f"LLM summarization unavailable: {e}")
            # Fallback: extractive summary
            return f"Found {len(results)} relevant memories. Top match: {results[0].content[:100]}..."

    def close(self) -> None:
        """Close database connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None


# Global singleton instance
_fts_engine: MemoryFTSEngine | None = None
_fts_lock = threading.Lock()


def get_fts_engine() -> MemoryFTSEngine:
    """Get or create the global FTS engine instance."""
    global _fts_engine
    if _fts_engine is None:
        with _fts_lock:
            if _fts_engine is None:
                _fts_engine = MemoryFTSEngine()
    return _fts_engine
