"""Episodic Memory Store — Hermes-Agent-style five-layer memory (Layer: Episodic).

Records every interaction as an *episode* (timestamp, context, action, outcome,
emotion) and persists them to SQLite with an FTS5 full-text index for fast
recall.  Old episodes can be compressed into daily / weekly summaries via an
optional LLM-driven :class:`EpisodeSummarizer` (graceful extractive fallback).

Design goals
------------
- All storage operations are async (``aiosqlite``).
- FTS5 full-text search over episode content.
- Retrieval by: time range, similarity, importance score, tags.
- Importance scoring on a 1-10 scale.
- Automatic summarization of old episode batches.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

# Default database path (persisted to disk under the project data directory)
DEFAULT_EPISODIC_DB_PATH = Path("data/memory_episodic.db")

# Importance bounds (1-10 scale)
IMPORTANCE_MIN = 1
IMPORTANCE_MAX = 10


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


@dataclass
class EpisodeRecord:
    """A single episodic memory record.

    Captures *what happened* during one interaction step.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    session_id: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    actor: str = "agent"
    action: str = ""
    target: str = ""
    outcome: str = ""
    importance: int = 5
    tags: list[str] = field(default_factory=list)
    summary: str = ""
    # Extra descriptive fields used for recall / summarization
    context: str = ""
    emotion: str = ""
    # Whether this record is itself a compressed summary of older episodes
    is_summary: bool = False
    summarized_episode_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Clamp importance to the 1-10 scale
        self.importance = max(IMPORTANCE_MIN, min(IMPORTANCE_MAX, int(self.importance)))

    @property
    def searchable_text(self) -> str:
        """Concatenated text used for the FTS5 index."""
        parts = [
            self.context,
            self.action,
            self.target,
            self.outcome,
            self.summary,
            self.emotion,
            " ".join(self.tags),
        ]
        return " ".join(p for p in parts if p)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["timestamp"] = _iso(self.timestamp)
        return data

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> EpisodeRecord:
        ts = row.get("timestamp")
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts)
            except ValueError:
                ts = _utcnow()
        elif not isinstance(ts, datetime):
            ts = _utcnow()

        def _load_list(raw: Any) -> list[str]:
            if isinstance(raw, list):
                return [str(x) for x in raw]
            if isinstance(raw, str) and raw:
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        return [str(x) for x in parsed]
                except json.JSONDecodeError:
                    pass
            return []

        return cls(
            id=str(row.get("id") or str(uuid4())),
            session_id=str(row.get("session_id") or ""),
            timestamp=ts,
            actor=str(row.get("actor") or "agent"),
            action=str(row.get("action") or ""),
            target=str(row.get("target") or ""),
            outcome=str(row.get("outcome") or ""),
            importance=int(row.get("importance") or 5),
            tags=_load_list(row.get("tags")),
            summary=str(row.get("summary") or ""),
            context=str(row.get("context") or ""),
            emotion=str(row.get("emotion") or ""),
            is_summary=bool(row.get("is_summary") or False),
            summarized_episode_ids=_load_list(row.get("summarized_episode_ids")),
        )


class EpisodeSummarizer:
    """LLM-driven compression of episode batches.

    Falls back to a deterministic extractive summary when no LLM backend is
    available, so summarization never crashes the memory pipeline.
    """

    def __init__(self, llm_backend: Any | None = None) -> None:
        self._llm = llm_backend

    async def summarize(self, episodes: list[EpisodeRecord], period_label: str = "") -> str:
        """Compress a batch of episodes into a single textual summary."""
        if not episodes:
            return ""

        # Deterministic extractive fallback (always available)
        extractive = self._extractive_summary(episodes, period_label)

        if self._llm is None:
            self._llm = self._try_load_llm()

        if self._llm is None:
            return extractive

        try:
            lines = []
            for ep in episodes[:50]:  # cap prompt size
                desc = ep.action or ep.summary or ep.outcome
                lines.append(f"- [{ep.actor}] {desc} -> {ep.outcome}".rstrip(" ->"))
            bullet_block = "\n".join(lines)
            prompt = (
                f"Summarize the following {len(episodes)} agent interaction episodes"
                f"{f' for {period_label}' if period_label else ''} into a concise "
                "paragraph capturing key actions, outcomes and lessons:\n\n"
                f"{bullet_block}"
            )
            response = await self._llm.chat([{"role": "user", "content": prompt}], [])
            content = getattr(response, "content", None) or str(response)
            content = (content or "").strip()
            if content:
                return content
        except Exception as exc:
            logger.debug("LLM episode summarization unavailable: %s", exc)

        return extractive

    @staticmethod
    def _try_load_llm() -> Any | None:
        try:
            from backend.app.core.llm.backends import get_llm_backend

            return get_llm_backend()
        except Exception as exc:
            logger.debug("LLM backend not available for summarization: %s", exc)
            return None

    @staticmethod
    def _extractive_summary(episodes: list[EpisodeRecord], period_label: str) -> str:
        top = sorted(episodes, key=lambda e: e.importance, reverse=True)[:5]
        header = f"Summary of {len(episodes)} episodes"
        if period_label:
            header += f" ({period_label})"
        highlights = "; ".join(
            (e.summary or e.action or e.outcome or "(no content)")[:120] for e in top
        )
        avg_importance = sum(e.importance for e in episodes) / len(episodes)
        return f"{header}. Avg importance {avg_importance:.1f}/10. Highlights: {highlights}."


class EpisodicMemoryStore:
    """Async SQLite + FTS5 episodic memory store."""

    def __init__(
        self,
        db_path: Path | str = DEFAULT_EPISODIC_DB_PATH,
        summarizer: EpisodeSummarizer | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.summarizer = summarizer or EpisodeSummarizer()
        self._initialized = False

    # ------------------------------------------------------------------
    # Connection / schema
    # ------------------------------------------------------------------

    async def _connect(self) -> Any:
        import aiosqlite

        conn = await aiosqlite.connect(self.db_path, timeout=30.0)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    async def initialize(self) -> None:
        """Create tables and the FTS5 index (idempotent)."""
        if self._initialized:
            return
        conn = await self._connect()
        try:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS episodes (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    timestamp TEXT,
                    actor TEXT,
                    action TEXT,
                    target TEXT,
                    outcome TEXT,
                    importance INTEGER,
                    tags TEXT,
                    summary TEXT,
                    context TEXT,
                    emotion TEXT,
                    is_summary INTEGER DEFAULT 0,
                    summarized_episode_ids TEXT
                )
                """
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_episodes_ts ON episodes(timestamp)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_episodes_session ON episodes(session_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_episodes_importance ON episodes(importance)"
            )
            # FTS5 virtual table for full-text search over episode content
            await conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts USING fts5(
                    episode_id UNINDEXED,
                    content,
                    tokenize='unicode61'
                )
                """
            )
            await conn.commit()
            self._initialized = True
        finally:
            await conn.close()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def record_episode(
        self,
        action: str,
        *,
        session_id: str = "",
        actor: str = "agent",
        target: str = "",
        outcome: str = "",
        importance: int = 5,
        tags: list[str] | None = None,
        context: str = "",
        emotion: str = "",
        summary: str = "",
    ) -> EpisodeRecord:
        """Record a new episode and index it for full-text search."""
        await self.initialize()
        episode = EpisodeRecord(
            session_id=session_id,
            actor=actor,
            action=action,
            target=target,
            outcome=outcome,
            importance=importance,
            tags=tags or [],
            context=context,
            emotion=emotion,
            summary=summary,
        )
        conn = await self._connect()
        try:
            await self._insert_episode(conn, episode)
            await conn.commit()
        finally:
            await conn.close()
        logger.info("Episode recorded: %s (importance=%d)", episode.id, episode.importance)
        return episode

    async def _insert_episode(self, conn: Any, episode: EpisodeRecord) -> None:
        await conn.execute(
            """
            INSERT OR REPLACE INTO episodes (
                id, session_id, timestamp, actor, action, target, outcome,
                importance, tags, summary, context, emotion, is_summary,
                summarized_episode_ids
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                episode.id,
                episode.session_id,
                _iso(episode.timestamp),
                episode.actor,
                episode.action,
                episode.target,
                episode.outcome,
                episode.importance,
                json.dumps(episode.tags, ensure_ascii=False),
                episode.summary,
                episode.context,
                episode.emotion,
                1 if episode.is_summary else 0,
                json.dumps(episode.summarized_episode_ids, ensure_ascii=False),
            ),
        )
        await conn.execute(
            "INSERT INTO episodes_fts (episode_id, content) VALUES (?, ?)",
            (episode.id, episode.searchable_text),
        )

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    async def search_episodes(
        self,
        query: str,
        *,
        limit: int = 10,
        session_id: str | None = None,
    ) -> list[EpisodeRecord]:
        """Full-text search over episodes using FTS5 + BM25 ranking."""
        await self.initialize()
        if not query.strip():
            return await self.list_episodes(limit=limit, session_id=session_id)

        conn = await self._connect()
        try:
            safe_query = self._sanitize_fts_query(query)
            if not safe_query:
                return []
            sql = (
                "SELECT e.* FROM episodes_fts f "
                "JOIN episodes e ON e.id = f.episode_id "
                "WHERE episodes_fts MATCH ? "
            )
            params: list[Any] = [safe_query]
            if session_id:
                sql += "AND e.session_id = ? "
                params.append(session_id)
            sql += "ORDER BY bm25(episodes_fts) ASC LIMIT ?"
            params.append(limit)
            cursor = await conn.execute(sql, params)
            rows = await cursor.fetchall()
            return [EpisodeRecord.from_row(dict(r)) for r in rows]
        except Exception as exc:
            logger.debug("FTS query failed (%s); falling back to keyword scan", exc)
            return await self._keyword_fallback(conn, query, limit, session_id)
        finally:
            await conn.close()

    async def _keyword_fallback(
        self, conn: Any, query: str, limit: int, session_id: str | None
    ) -> list[EpisodeRecord]:
        episodes = await self.list_episodes(limit=10000, session_id=session_id)
        terms = set(query.lower().split())
        scored: list[tuple[float, EpisodeRecord]] = []
        for ep in episodes:
            words = set(ep.searchable_text.lower().split())
            if not terms:
                continue
            overlap = len(terms & words) / len(terms)
            if overlap > 0:
                scored.append((overlap, ep))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in scored[:limit]]

    @staticmethod
    def _sanitize_fts_query(query: str) -> str:
        """Build a safe FTS5 query from free text.

        Wraps each alphanumeric/CJK token in double quotes and joins with OR so
        that special FTS5 operators cannot break the query.
        """
        tokens = re.findall(r"[\w\u4e00-\u9fff]+", query, flags=re.UNICODE)
        if not tokens:
            return ""
        return " OR ".join(f'"{t}"' for t in tokens[:32])

    async def list_episodes(
        self,
        *,
        limit: int = 50,
        session_id: str | None = None,
        include_summaries: bool = True,
    ) -> list[EpisodeRecord]:
        """List most recent episodes (newest first)."""
        await self.initialize()
        conn = await self._connect()
        try:
            sql = "SELECT * FROM episodes WHERE 1=1 "
            params: list[Any] = []
            if session_id:
                sql += "AND session_id = ? "
                params.append(session_id)
            if not include_summaries:
                sql += "AND is_summary = 0 "
            sql += "ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            cursor = await conn.execute(sql, params)
            rows = await cursor.fetchall()
            return [EpisodeRecord.from_row(dict(r)) for r in rows]
        finally:
            await conn.close()

    async def recall_by_time_range(
        self,
        start: datetime,
        end: datetime,
        *,
        limit: int = 100,
        session_id: str | None = None,
    ) -> list[EpisodeRecord]:
        """Retrieve episodes within a time range."""
        await self.initialize()
        conn = await self._connect()
        try:
            sql = "SELECT * FROM episodes WHERE timestamp >= ? AND timestamp <= ? "
            params: list[Any] = [_iso(start), _iso(end)]
            if session_id:
                sql += "AND session_id = ? "
                params.append(session_id)
            sql += "ORDER BY timestamp ASC LIMIT ?"
            params.append(limit)
            cursor = await conn.execute(sql, params)
            rows = await cursor.fetchall()
            return [EpisodeRecord.from_row(dict(r)) for r in rows]
        finally:
            await conn.close()

    async def recall_by_importance(
        self,
        min_importance: int = 7,
        *,
        limit: int = 50,
        session_id: str | None = None,
    ) -> list[EpisodeRecord]:
        """Retrieve episodes at or above an importance threshold."""
        await self.initialize()
        conn = await self._connect()
        try:
            sql = "SELECT * FROM episodes WHERE importance >= ? "
            params: list[Any] = [min_importance]
            if session_id:
                sql += "AND session_id = ? "
                params.append(session_id)
            sql += "ORDER BY importance DESC, timestamp DESC LIMIT ?"
            params.append(limit)
            cursor = await conn.execute(sql, params)
            rows = await cursor.fetchall()
            return [EpisodeRecord.from_row(dict(r)) for r in rows]
        finally:
            await conn.close()

    async def recall_by_tags(
        self,
        tags: list[str],
        *,
        limit: int = 50,
        match_all: bool = False,
    ) -> list[EpisodeRecord]:
        """Retrieve episodes matching one or more tags."""
        await self.initialize()
        if not tags:
            return []
        episodes = await self.list_episodes(limit=10000)
        wanted = {t.lower() for t in tags}
        matched: list[tuple[int, EpisodeRecord]] = []
        for ep in episodes:
            ep_tags = {t.lower() for t in ep.tags}
            overlap = len(wanted & ep_tags)
            if match_all:
                if wanted.issubset(ep_tags):
                    matched.append((overlap, ep))
            elif overlap > 0:
                matched.append((overlap, ep))
        matched.sort(key=lambda x: (x[0], x[1].importance), reverse=True)
        return [ep for _, ep in matched[:limit]]

    async def recall_by_similarity(
        self,
        query: str,
        *,
        limit: int = 10,
        session_id: str | None = None,
    ) -> list[tuple[EpisodeRecord, float]]:
        """Recall episodes by lexical similarity (Jaccard over tokens).

        Returns ``(episode, score)`` pairs sorted by descending similarity.
        This is a dependency-free similarity measure; when FTS5 is available it
        is used to pre-filter candidates for speed.
        """
        await self.initialize()
        candidates = await self.search_episodes(
            query, limit=max(limit * 5, 50), session_id=session_id
        )
        if not candidates:
            candidates = await self.list_episodes(limit=500, session_id=session_id)

        query_terms = set(query.lower().split())
        if not query_terms:
            return [(ep, 0.0) for ep in candidates[:limit]]

        scored: list[tuple[EpisodeRecord, float]] = []
        for ep in candidates:
            ep_terms = set(ep.searchable_text.lower().split())
            union = query_terms | ep_terms
            score = len(query_terms & ep_terms) / len(union) if union else 0.0
            # Blend with normalized importance for a recency/importance boost
            score = 0.8 * score + 0.2 * (ep.importance / IMPORTANCE_MAX)
            scored.append((ep, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    # ------------------------------------------------------------------
    # Summarization / consolidation
    # ------------------------------------------------------------------

    async def summarize_old_episodes(
        self,
        *,
        older_than_days: int = 7,
        period_label: str = "",
        min_batch: int = 5,
        delete_originals: bool = False,
    ) -> EpisodeRecord | None:
        """Compress old episodes into a single summary episode.

        Episodes older than ``older_than_days`` that are not themselves
        summaries are batched and compressed via :class:`EpisodeSummarizer`.
        """
        await self.initialize()
        cutoff = _utcnow() - timedelta(days=older_than_days)
        conn = await self._connect()
        try:
            cursor = await conn.execute(
                "SELECT * FROM episodes WHERE timestamp <= ? AND is_summary = 0 "
                "ORDER BY timestamp ASC",
                (_iso(cutoff),),
            )
            rows = await cursor.fetchall()
            old_episodes = [EpisodeRecord.from_row(dict(r)) for r in rows]

            if len(old_episodes) < min_batch:
                return None

            label = period_label or f"before {cutoff.date().isoformat()}"
            summary_text = await self.summarizer.summarize(old_episodes, label)

            summary_ep = EpisodeRecord(
                session_id=old_episodes[0].session_id,
                actor="system",
                action="summarize",
                target=f"{len(old_episodes)} episodes",
                outcome="compressed",
                importance=max(e.importance for e in old_episodes),
                tags=["summary", "consolidated"],
                summary=summary_text,
                context=f"Auto-consolidated {len(old_episodes)} episodes ({label})",
                is_summary=True,
                summarized_episode_ids=[e.id for e in old_episodes],
            )
            await self._insert_episode(conn, summary_ep)

            if delete_originals:
                ids = [e.id for e in old_episodes]
                for eid in ids:
                    await conn.execute("DELETE FROM episodes WHERE id = ?", (eid,))
                    await conn.execute(
                        "DELETE FROM episodes_fts WHERE episode_id = ?", (eid,)
                    )

            await conn.commit()
            logger.info(
                "Consolidated %d episodes into summary %s", len(old_episodes), summary_ep.id
            )
            return summary_ep
        finally:
            await conn.close()

    # ------------------------------------------------------------------
    # Stats / maintenance
    # ------------------------------------------------------------------

    async def get_stats(self) -> dict[str, Any]:
        await self.initialize()
        conn = await self._connect()
        try:
            total = (await (await conn.execute("SELECT COUNT(*) FROM episodes")).fetchone())[0]
            summaries = (
                await (
                    await conn.execute("SELECT COUNT(*) FROM episodes WHERE is_summary = 1")
                ).fetchone()
            )[0]
            avg_imp_row = await (
                await conn.execute("SELECT AVG(importance) FROM episodes")
            ).fetchone()
            avg_imp = avg_imp_row[0] if avg_imp_row and avg_imp_row[0] is not None else 0.0
            return {
                "total_episodes": total,
                "summary_episodes": summaries,
                "raw_episodes": total - summaries,
                "avg_importance": round(float(avg_imp), 2),
                "db_path": str(self.db_path),
            }
        finally:
            await conn.close()


# Global instance (persisted to disk by default)
episodic_memory_store = EpisodicMemoryStore()
