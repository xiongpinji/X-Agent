"""Cross-Session Memory — Hermes-Agent-style five-layer memory (Layer: Semantic/Long-term).

Persists user preferences, corrections and project knowledge *across sessions*.

Features
--------
- Auto-extracts preferences from user corrections ("no, use X instead of Y").
- Knowledge graph of ``entity -> relation -> entity`` triples.
- Conflict resolution: newer information overrides older information.
- Everything is persisted to disk via SQLite (``aiosqlite``) — never
  in-memory only.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CROSS_SESSION_DB_PATH = Path("data/memory_cross_session.db")


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


@dataclass
class UserPreference:
    """A persisted user preference."""

    key: str
    value: str
    confidence: float = 0.5
    source_session: str = ""
    created_at: datetime = field(default_factory=_utcnow)
    last_confirmed: datetime = field(default_factory=_utcnow)
    confirmation_count: int = 1

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["created_at"] = _iso(self.created_at)
        data["last_confirmed"] = _iso(self.last_confirmed)
        return data

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> UserPreference:
        def _parse_dt(val: Any) -> datetime:
            if isinstance(val, datetime):
                return val
            if isinstance(val, str) and val:
                try:
                    return datetime.fromisoformat(val)
                except ValueError:
                    return _utcnow()
            return _utcnow()

        return cls(
            key=str(row.get("key") or ""),
            value=str(row.get("value") or ""),
            confidence=float(row.get("confidence") or 0.5),
            source_session=str(row.get("source_session") or ""),
            created_at=_parse_dt(row.get("created_at")),
            last_confirmed=_parse_dt(row.get("last_confirmed")),
            confirmation_count=int(row.get("confirmation_count") or 1),
        )


@dataclass
class KnowledgeTriple:
    """A knowledge-graph triple: subject -> predicate -> object."""

    subject: str
    predicate: str
    object: str
    confidence: float = 0.5
    evidence: list[str] = field(default_factory=list)
    source_session: str = ""
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    @property
    def key(self) -> str:
        return f"{self.subject}|{self.predicate}".lower()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["created_at"] = _iso(self.created_at)
        data["updated_at"] = _iso(self.updated_at)
        return data

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> KnowledgeTriple:
        def _parse_dt(val: Any) -> datetime:
            if isinstance(val, datetime):
                return val
            if isinstance(val, str) and val:
                try:
                    return datetime.fromisoformat(val)
                except ValueError:
                    return _utcnow()
            return _utcnow()

        evidence = row.get("evidence")
        if isinstance(evidence, str) and evidence:
            try:
                evidence = json.loads(evidence)
            except json.JSONDecodeError:
                evidence = [evidence]
        if not isinstance(evidence, list):
            evidence = []

        return cls(
            subject=str(row.get("subject") or ""),
            predicate=str(row.get("predicate") or ""),
            object=str(row.get("object") or ""),
            confidence=float(row.get("confidence") or 0.5),
            evidence=[str(e) for e in evidence],
            source_session=str(row.get("source_session") or ""),
            created_at=_parse_dt(row.get("created_at")),
            updated_at=_parse_dt(row.get("updated_at")),
        )


# Patterns that signal a user correction, e.g. "no, use pytest instead of unittest"
_CORRECTION_PATTERNS = [
    re.compile(
        r"\b(?:no|not|don'?t|stop|please don'?t)[,\s]+.*?\buse\s+(?P<new>.+?)\s+"
        r"(?:instead\s+of|over|rather\s+than|not)\s+(?P<old>.+?)\.?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bprefer\s+(?P<new>.+?)\s+(?:over|instead\s+of|rather\s+than)\s+(?P<old>.+?)\.?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"\buse\s+(?P<new>.+?)\s+instead\s+of\s+(?P<old>.+?)\.?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bswitch\s+(?:to|from\s+.+?\s+to)\s+(?P<new>.+?)\.?$",
        re.IGNORECASE,
    ),
]


class CrossSessionMemory:
    """Async cross-session memory with disk persistence."""

    def __init__(self, db_path: Path | str = DEFAULT_CROSS_SESSION_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def _connect(self) -> Any:
        import aiosqlite

        conn = await aiosqlite.connect(self.db_path, timeout=30.0)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    async def initialize(self) -> None:
        if self._initialized:
            return
        conn = await self._connect()
        try:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    confidence REAL DEFAULT 0.5,
                    source_session TEXT,
                    created_at TEXT,
                    last_confirmed TEXT,
                    confirmation_count INTEGER DEFAULT 1
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_triples (
                    subject TEXT,
                    predicate TEXT,
                    object TEXT,
                    confidence REAL DEFAULT 0.5,
                    evidence TEXT,
                    source_session TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    PRIMARY KEY (subject, predicate, object)
                )
                """
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_triples_subject ON knowledge_triples(subject)"
            )
            await conn.commit()
            self._initialized = True
        finally:
            await conn.close()

    # ------------------------------------------------------------------
    # Preferences
    # ------------------------------------------------------------------

    async def set_preference(
        self,
        key: str,
        value: str,
        *,
        confidence: float = 0.7,
        source_session: str = "",
    ) -> UserPreference:
        """Set or update a preference (newer info overrides older)."""
        await self.initialize()
        conn = await self._connect()
        try:
            cursor = await conn.execute(
                "SELECT * FROM preferences WHERE key = ?", (key,)
            )
            row = await cursor.fetchone()
            now = _utcnow()
            if row is not None:
                existing = UserPreference.from_row(dict(row))
                # Conflict resolution: newer info overrides older; bump confidence
                existing.value = value
                existing.confidence = min(1.0, max(confidence, existing.confidence))
                existing.last_confirmed = now
                existing.confirmation_count += 1
                if source_session:
                    existing.source_session = source_session
                pref = existing
            else:
                pref = UserPreference(
                    key=key,
                    value=value,
                    confidence=confidence,
                    source_session=source_session,
                    created_at=now,
                    last_confirmed=now,
                )
            await conn.execute(
                """
                INSERT OR REPLACE INTO preferences (
                    key, value, confidence, source_session, created_at,
                    last_confirmed, confirmation_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pref.key,
                    pref.value,
                    pref.confidence,
                    pref.source_session,
                    _iso(pref.created_at),
                    _iso(pref.last_confirmed),
                    pref.confirmation_count,
                ),
            )
            await conn.commit()
            return pref
        finally:
            await conn.close()

    async def get_preference(self, key: str) -> UserPreference | None:
        await self.initialize()
        conn = await self._connect()
        try:
            cursor = await conn.execute(
                "SELECT * FROM preferences WHERE key = ?", (key,)
            )
            row = await cursor.fetchone()
            return UserPreference.from_row(dict(row)) if row else None
        finally:
            await conn.close()

    async def list_preferences(self, *, limit: int = 200) -> list[UserPreference]:
        await self.initialize()
        conn = await self._connect()
        try:
            cursor = await conn.execute(
                "SELECT * FROM preferences ORDER BY last_confirmed DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
            return [UserPreference.from_row(dict(r)) for r in rows]
        finally:
            await conn.close()

    async def extract_preference_from_correction(
        self,
        text: str,
        *,
        source_session: str = "",
    ) -> UserPreference | None:
        """Auto-extract a preference from a user correction.

        Recognizes phrasings like "no, use pytest instead of unittest" and
        stores a preference ``key=old, value=new`` while recording the
        correction as a knowledge triple.
        """
        await self.initialize()
        for pattern in _CORRECTION_PATTERNS:
            match = pattern.search(text.strip())
            if not match:
                continue
            groups = match.groupdict()
            new_val = (groups.get("new") or "").strip().strip(".")
            old_val = (groups.get("old") or "").strip().strip(".")
            if not new_val:
                continue

            key = old_val.lower() if old_val else new_val.lower()
            pref = await self.set_preference(
                key=key,
                value=new_val,
                confidence=0.8,
                source_session=source_session,
            )

            # Record the correction as a knowledge triple for provenance
            if old_val:
                await self.add_triple(
                    subject=old_val,
                    predicate="replaced_by",
                    obj=new_val,
                    confidence=0.8,
                    evidence=[text.strip()],
                    source_session=source_session,
                )
            logger.info("Extracted preference from correction: %s -> %s", key, new_val)
            return pref

        return None

    # ------------------------------------------------------------------
    # Knowledge graph (triples)
    # ------------------------------------------------------------------

    async def add_triple(
        self,
        subject: str,
        predicate: str,
        obj: str,
        *,
        confidence: float = 0.6,
        evidence: list[str] | None = None,
        source_session: str = "",
    ) -> KnowledgeTriple:
        """Add or update a knowledge triple.

        Conflict resolution: if the same (subject, predicate) already points to
        a *different* object, the newer information overrides the older one
        (the old object row is removed).  Re-adding the same triple reinforces
        its confidence and appends evidence.
        """
        await self.initialize()
        subject = subject.strip()
        predicate = predicate.strip()
        obj = obj.strip()
        now = _utcnow()
        conn = await self._connect()
        try:
            # Conflict resolution: drop older triples with same subject+predicate
            # but a different object (newer info overrides older).
            await conn.execute(
                "DELETE FROM knowledge_triples WHERE lower(subject) = ? AND "
                "lower(predicate) = ? AND lower(object) != ?",
                (subject.lower(), predicate.lower(), obj.lower()),
            )

            cursor = await conn.execute(
                "SELECT * FROM knowledge_triples WHERE lower(subject) = ? AND "
                "lower(predicate) = ? AND lower(object) = ?",
                (subject.lower(), predicate.lower(), obj.lower()),
            )
            row = await cursor.fetchone()

            if row is not None:
                triple = KnowledgeTriple.from_row(dict(row))
                triple.confidence = min(1.0, max(confidence, triple.confidence))
                if evidence:
                    for e in evidence:
                        if e not in triple.evidence:
                            triple.evidence.append(e)
                triple.updated_at = now
            else:
                triple = KnowledgeTriple(
                    subject=subject,
                    predicate=predicate,
                    object=obj,
                    confidence=confidence,
                    evidence=evidence or [],
                    source_session=source_session,
                    created_at=now,
                    updated_at=now,
                )

            await conn.execute(
                """
                INSERT OR REPLACE INTO knowledge_triples (
                    subject, predicate, object, confidence, evidence,
                    source_session, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    triple.subject,
                    triple.predicate,
                    triple.object,
                    triple.confidence,
                    json.dumps(triple.evidence, ensure_ascii=False),
                    triple.source_session,
                    _iso(triple.created_at),
                    _iso(triple.updated_at),
                ),
            )
            await conn.commit()
            return triple
        finally:
            await conn.close()

    async def query_triples(
        self,
        *,
        subject: str | None = None,
        predicate: str | None = None,
        obj: str | None = None,
        limit: int = 100,
    ) -> list[KnowledgeTriple]:
        """Query the knowledge graph by any combination of S/P/O."""
        await self.initialize()
        conn = await self._connect()
        try:
            clauses: list[str] = []
            params: list[Any] = []
            if subject:
                clauses.append("lower(subject) = ?")
                params.append(subject.lower())
            if predicate:
                clauses.append("lower(predicate) = ?")
                params.append(predicate.lower())
            if obj:
                clauses.append("lower(object) = ?")
                params.append(obj.lower())

            sql = "SELECT * FROM knowledge_triples"
            if clauses:
                sql += " WHERE " + " AND ".join(clauses)
            sql += " ORDER BY updated_at DESC LIMIT ?"
            params.append(limit)

            cursor = await conn.execute(sql, params)
            rows = await cursor.fetchall()
            return [KnowledgeTriple.from_row(dict(r)) for r in rows]
        finally:
            await conn.close()

    async def get_entity_neighborhood(self, entity: str, *, limit: int = 100) -> dict[str, Any]:
        """Return outgoing and incoming triples for an entity."""
        outgoing = await self.query_triples(subject=entity, limit=limit)
        incoming = await self.query_triples(obj=entity, limit=limit)
        return {
            "entity": entity,
            "outgoing": [t.to_dict() for t in outgoing],
            "incoming": [t.to_dict() for t in incoming],
        }

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    async def get_stats(self) -> dict[str, Any]:
        await self.initialize()
        conn = await self._connect()
        try:
            pref_count = (
                await (await conn.execute("SELECT COUNT(*) FROM preferences")).fetchone()
            )[0]
            triple_count = (
                await (
                    await conn.execute("SELECT COUNT(*) FROM knowledge_triples")
                ).fetchone()
            )[0]
            entities = (
                await (
                    await conn.execute(
                        "SELECT COUNT(DISTINCT lower(subject)) FROM knowledge_triples"
                    )
                ).fetchone()
            )[0]
            return {
                "total_preferences": pref_count,
                "total_triples": triple_count,
                "distinct_subjects": entities,
                "db_path": str(self.db_path),
            }
        finally:
            await conn.close()


# Global instance (persisted to disk by default)
cross_session_memory = CrossSessionMemory()
